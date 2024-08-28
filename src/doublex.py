#import logging
#logging.basicConfig(level=logging.DEBUG)  # has to be executed before any other piece of code has the chance to (!!!)

# Copyright (C) 2021 Aurore Fass
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""
    To call DoubleX from the command-line.
"""

import os
import argparse
import datetime
from pathlib import Path
import time

# Original DoubleX extension analysis:
from vulnerability_detection import analyze_extension as doublex_analyze_extension

# My extension analysis to find vulnerabilities of the types considered by Young Min Kim and Byoungyoung Lee
# in their 2023 paper "Extending a Hand to Attackers: Browser Privilege Escalation Attacks via Extensions";
# unlike the vulnerabilities considered by DoubleX, these require a stronger assumption, namely that of a renderer
# attacker, i.e., an attacker that has gained full read-/write-access to a browser's renderer process:
from kim_and_lee_vulnerability_detection import analyze_extension as kim_and_lee_analyze_extension

from unpack_extension import unpack_extension

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def get_directory_size(start_path):
    """
    Determines the size of a directory.
    Source: https://stackoverflow.com/questions/1392413/calculating-a-directorys-size-using-python
    """
    total_size = 0
    for dir_path, _dir_names, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dir_path, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size


def main():
    """ Parsing command line parameters. """

    parser = argparse.ArgumentParser(prog='doublex',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="Static analysis of a browser extension to detect "
                                                 "suspicious data flows")

    parser.add_argument("--crx", dest='crx', metavar="path", type=str, action='append', nargs='+',
                        help="Path(s) of the .CRX file(s) to unpack and analyze. "
                             "If used, the -cs and -bp arguments will be ignored. ")

    parser.add_argument("-cs", "--content-script", dest='cs', metavar="path", type=str,
                        help="path of the content script. "
                        "Default: empty/contentscript.js (i.e., empty JS file)")
    parser.add_argument("-bp", "--background-page", dest='bp', metavar="path", type=str,
                        help="path of the background page "
                             "or path of the WAR if the parameter '--war' is given. "
                             "Default for background: empty/background.js (i.e., empty JS file)")

    parser.add_argument("--war", action='store_true',
                        help="indicate that the parameter '-bp' is the path of a WAR")
    parser.add_argument("--not-chrome", dest='not_chrome', action='store_true',
                        help="indicate that the extension is not based on Chromium, e.g., for a Firefox extension")

    parser.add_argument("--manifest", metavar="path", type=str,
                        help="path of the extension manifest.json file. "
                             "Default: parent-path-of-content-script/manifest.json")
    parser.add_argument("--analysis", metavar="path", type=str,
                        help="path of the file to store the analysis results in. "
                             "Default: parent-path-of-content-script/analysis.json")
    parser.add_argument("--apis", metavar="str", type=str, default='permissions',
                        help='''specify the sensitive APIs to consider for the analysis:
    - 'permissions' (default): DoubleX selected APIs iff the extension has the corresponding permissions;
    - 'all': DoubleX selected APIs irrespective of the extension permissions;
    - 'empoweb': APIs from the EmPoWeb paper; to use ONLY on the EmPoWeb ground-truth dataset;
    - path: APIs listed in the corresponding json file; a template can be found in src/suspicious_apis/README.md.''')

    group1 = parser.add_mutually_exclusive_group(required=True)
    group1.add_argument('--esprima', action='store_true',
                        help="""Use the Esprima parser for AST generation (old) (what DoubleX originally did).""")
    group1.add_argument('--espree', action='store_true',
                        help="""Use the Espree parser for AST generation (new) (recommended).""")

    group2 = parser.add_mutually_exclusive_group(required=True)
    group2.add_argument('--src-type-script', action='store_true',
                        help="""Sets the sourceType option to "script" for the (Esprima/Espree) parser.""")
    group2.add_argument('--src-type-module', action='store_true',
                        help="""Sets the sourceType option to "module" for the (Esprima/Espree) parser.
                        This is what the original DoubleX by Aurore Fass used.""")
    group2.add_argument('--src-type-commonjs', action='store_true',
                        help="""Sets the sourceType option to "commonjs" for the (Espree) parser.""")

    parser.add_argument("--display-edg", dest='display_edg', action='store_true',
                        help="Display the EDG (Extension Dependence Graph).")

    parser.add_argument("--print-pdgs", dest='print_pdgs', action='store_true',
                        help="Print the PDGs (Program Dependence Graphs) of CS and BP to console.")

    parser.add_argument("--renderer-attacker", dest='renderer_attacker', action='store_true',
                        help="Instead of running the regular DoubleX, analyze the given extension for vulnerabilities "
                             "exploitable by a renderer attacker (those considered by Young Min Kim and Byoungyoung "
                             "Lee in their 2023 paper 'Extending a Hand to Attackers: Browser Privilege Escalation "
                             "Attacks via Extensions').")

    parser.add_argument("--return-multiple-flow-variants", dest='return_multiple_flow_variants',
                        action='store_true',
                        help="When this flag is set and there exist multiple data flows between the same source and "
                             "the same sink, *all* of those will be returned in analysis_renderer_attacker.json. "
                             "This will result in a more elaborate but also verbose listing of vulnerabilities. "
                             "Use this flag when trying to fix vulnerabilities / when wanting to report a complete "
                             "list of attack vectors.")

    parser.add_argument("--return-safe-flows-verified", dest='return_safe_flows_verified',
                        action='store_true',
                        help="Return data flows even when they should be safe because the URL/origin of each message"
                             "sender is correctly verified (Kim+Lee Sec. Req. 3.1 Extension Message Authentication).")

    # ToDo:
    parser.add_argument("--return-safe-flows-sanitized", dest='return_safe_flows_sanitized',
                        action='store_true',
                        help="Return UXSS data flows even when they should be safe because of correct sanitization.")

    parser.add_argument("--csv-out", metavar="path", type=str, default="",
                        help="Path of the .CSV output file. "
                             "Only has an effect in combination with the --crx and --renderer-attacker parameters. "
                             "CSV file will contain list of all extensions analyzed and number of vulnerabilities"
                             "found, by type."
                             "No .CSV file will be created when the --csv-out argument is supplied.")

    # TODO: control verbosity of logging?

    args = parser.parse_args()

    if args.esprima:
        os.environ['PARSER'] = "esprima"
    elif args.espree:
        os.environ['PARSER'] = "espree"
    else:
        print("No parser specified.")
        return

    if args.src_type_script:
        os.environ['SOURCE_TYPE'] = "script"
    elif args.src_type_module:
        os.environ['SOURCE_TYPE'] = "module"
    elif args.src_type_commonjs:
        if args.esprima:
            print("Esprima only supports 'script' and 'module' source types.")
            return
        os.environ['SOURCE_TYPE'] = "commonjs"
    else:
        print("No sourceType specified.")
        return

    if args.display_edg:
        os.environ['DISPLAY_EDG'] = "yes"

    if args.print_pdgs:
        os.environ['PRINT_PDGS'] = "yes"

    if args.return_multiple_flow_variants:
        os.environ['RETURN_MULTIPLE_FLOW_VARIANTS'] = "yes"

    if args.return_safe_flows_verified:
        os.environ['RETURN_SAFE_FLOWS_VERIFIED'] = "yes"

    if args.return_safe_flows_sanitized:
        os.environ['RETURN_SAFE_FLOWS_SANITIZED'] = "yes"

    # Whether to use the original DoubleX extension analysis,
    #   or whether to look for vulnerabilities exploitable by a renderer attacker:
    analyze_extension = doublex_analyze_extension
    if args.renderer_attacker:
        analyze_extension = kim_and_lee_analyze_extension

    if args.crx is None:  # No --crx argument supplied: Use -cs and -bp arguments:
        print("Analyzing a single, unpacked extension...")
        cs = args.cs
        bp = args.bp
        if cs is None:
            cs = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'contentscript.js')
        if bp is None:
            bp = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'background.js')

        analyze_extension(cs, bp, json_analysis=args.analysis, chrome=not args.not_chrome,
                          war=args.war, json_apis=args.apis, manifest_path=args.manifest)

    else:  # Ignore -cs and -bp arguments when --crx argument is supplied:
        # Flatten the --crx / args.crx argument:
        #     => example: "--crx a b --crx x y" becomes: [['a', 'b'], ['x', 'y']]
        crxs = [c for cs in args.crx for c in cs]
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyzing {len(crxs)} packed extensions...")

        # Use the folder in which the first .CRX file is situated in, create a subfolder called "unpacked" and use that:
        dest1 = os.path.join(Path(crxs[0]).parent.absolute(), "unpacked")
        Path(dest1).mkdir(parents=False, exist_ok=True)
        print(f"Unpacking into folder: {dest1}")

        # If user activated output of vulnerabilities found into a CSV file by supplying the --csv-out argument:
        if args.csv_out != "":
            if not args.renderer_attacker:
                print(f"Error: the --csv-out argument may only be supplied in combination with the --renderer-attacker "
                      f"argument.")
                exit(1)
            elif os.path.exists(args.csv_out):
                print(f"Error: '{args.csv_out}' file already exists, please supply another file as --csv-out.")
                exit(1)
            csv_out = open(args.csv_out, "w")
            csv_out.write("Extension,extension size (packed),extension size (unpacked),"
                          "CS injected into,crashes,analysis time in seconds,total dangers,"
                          "BP exfiltration dangers,BP infiltration dangers,"
                          "CS exfiltration dangers,CS infiltration dangers,files and line numbers\n")
            csv_out.flush()

        for crx in crxs:
            try:
                extension_size_packed = f"{os.path.getsize(crx):_}"
            except OSError:
                extension_size_packed = "?"
            # Unpack .CRX file into a temp directory:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking '{crx}' ...")
            dest2 = unpack_extension(extension_crx=crx, dest=dest1)
            extension_size_unpacked = f"{get_directory_size(dest2):_}"
            if dest2 is None:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking failed: '{crx}'")
            else:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacked '{crx}' into '{dest2}'")

                cs = os.path.join(dest2, "content_scripts.js")
                bp = os.path.join(dest2, "background.js")

                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyzing '{crx}' ...")
                analysis_start = time.time()
                analysis_result = analyze_extension(cs, bp, json_analysis=args.analysis, chrome=not args.not_chrome,
                                  war=args.war, json_apis=args.apis, manifest_path=args.manifest)
                # Note that analysis_result will be None if analyze_extension = doublex_analyze_extension!
                analysis_end = time.time()
                analysis_time = analysis_end - analysis_start  # gives the elapsed time in seconds(!)
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done analyzing '{crx}' after "
                      f"{analysis_time} seconds")

                if args.csv_out != "":
                    content_script_injected_into = " | ".join(analysis_result['content_script_injected_into'])\
                        if 'content_script_injected_into' in analysis_result else ""
                    crashes = " | ".join(analysis_result['benchmarks']['crashes'])\
                        if 'benchmarks' in analysis_result and 'crashes' in analysis_result['benchmarks'] else ""
                    bp_exfiltration_dangers = analysis_result['bp']['exfiltration_dangers']
                    bp_infiltration_dangers = analysis_result['bp']['infiltration_dangers']
                    cs_exfiltration_dangers = analysis_result['cs']['exfiltration_dangers']
                    cs_infiltration_dangers = analysis_result['cs']['infiltration_dangers']
                    total_no_of_dangers = sum(len(x) for x in [bp_exfiltration_dangers, bp_infiltration_dangers,
                                                               cs_exfiltration_dangers, cs_infiltration_dangers])
                    files_and_line_numbers = "" # ToDo: write once more types of vuln. are supported!
                    csv_out.write(f"{crx},{extension_size_packed},{extension_size_unpacked},"
                                  f"{content_script_injected_into},{crashes},"
                                  f"{analysis_time},{total_no_of_dangers},"
                                  f"{len(bp_exfiltration_dangers)},{len(bp_infiltration_dangers)},"
                                  f"{len(cs_exfiltration_dangers)},{len(cs_infiltration_dangers)},"
                                  f"{files_and_line_numbers}\n")
                    # ToDo: also output: LoC (beautified)
                    csv_out.flush()

        if args.csv_out != "":
            csv_out.close()


if __name__ == "__main__":
    main()
