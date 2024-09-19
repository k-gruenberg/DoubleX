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
import json
import traceback
import multiprocessing
from multiprocessing import Process
import queue
from typing import Tuple, Any

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


def get_javascript_loc(directory):
    r"""
    Given the path to the directory of an unpacked extension,
    determines the total no. of JavaScript lines of code (LoC) using the following shell command:

    find . -name "*.js" -exec sh -c "js-beautify {} | wc -l" \; | awk '{s+=$1} END {print s}'

    Returns -1 on error.
    """
    cmd = """find """ + directory +\
        r""" -name "*.js" -exec sh -c "js-beautify {} | wc -l" \; | awk '{s+=$1} END {print s}'"""
    try:
        return int(os.popen(cmd).read())
    except:
        return -1  # signifies an error


def print_progress(done, total, of_what="", suffix="", width_in_chars=50, done_char='\u2588', undone_char='\u2591'):
    no_done_chars = round((done/total) * width_in_chars)
    no_undone_chars: int | Any = width_in_chars - no_done_chars
    print(f"[{done_char * no_done_chars}{undone_char * no_undone_chars}] {done} / {total} {of_what} {suffix}")


def format_seconds_to_printable_time(no_of_seconds):
    if no_of_seconds < 3600*24:
        # a trick to convert seconds into HH:MM:SS format, see:
        #   https://stackoverflow.com/questions/1384406/convert-seconds-to-hhmmss-in-python
        return time.strftime('%H:%M:%S', time.gmtime(no_of_seconds))
    else:
        return f"{no_of_seconds/(3600*24)} days"


def analyze_extensions_in_sequence(process_idx: int,
                                   crxs_queue: multiprocessing.Queue,
                                   results_queue: multiprocessing.Queue,
                                   unpack_dest_dir: str):
    """
    Parameters:
        process_idx: simply an identifier for each process worker, used in prints only
        crxs_queue: a queue of strings representing paths to CRX files (input queue)
        results_queue: a queue of Tuple[dict, dict] (where the first dict contains some info on the CRX analyzed, while
                       the second dict is the actual `result_dict` as returned by kim_and_lee_analyze_extension())
                       (output queue);
                       the info dict contains the following keys:
                       "crx", "extension_size_unpacked", "js_loc", "analysis_time", "unpacked_ext_dir"
        unpack_dest_dir: the directory into which to unpack the given CRX files

    This is the code of each worker process.
    By default, there are (number of CPUs)/2 worker processes.
    """
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Start of process #{process_idx}.")
    try:
        while True:
            # (1): Take a CRX file from the global CRXs queue:
            crx = crxs_queue.get(block=False)
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Process #{process_idx} took CRX '{crx}'")

            # (2): Unpack the CRX file:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking '{crx}' ...")
            unpacked_ext_dir = unpack_extension(extension_crx=crx, dest=unpack_dest_dir)
            extension_size_unpacked = f"{get_directory_size(unpacked_ext_dir):_}"
            js_loc = f"{get_javascript_loc(unpacked_ext_dir):_}"
            info: dict = {
                "crx": crx,
                "extension_size_unpacked": extension_size_unpacked,
                "js_loc": js_loc,
                "js_code_avg_lengths": "N/A",
                "analysis_time": "N/A",
                "unpacked_ext_dir": unpacked_ext_dir,
            }
            if unpacked_ext_dir is None:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking failed: '{crx}'")
                # Simply continue with next extension...
                # ...but don't forget to still put a result into the results_queue:
                analysis_result = {
                    "benchmarks": {
                        "crashes": ["Unpacking failed"]
                    }
                }
                results_queue.put((info, analysis_result), block=False)
                continue
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Unpacked '{crx}' into '{unpacked_ext_dir}'")

            # After unpacking, there are now JS files for CS and BP that can be analyzed in the next step:
            cs = os.path.join(unpacked_ext_dir, "content_scripts.js")
            bp = os.path.join(unpacked_ext_dir, "background.js")

            # (3): Analyze the unpacked extension:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyzing '{crx}' ...")
            analysis_start = time.time()
            try:
                res_dict = kim_and_lee_analyze_extension(cs, bp)
                info["analysis_time"] = time.time() - analysis_start
                results_queue.put((info, res_dict), block=False)
            except queue.Full:
                raise AssertionError("Results queue was full. This should *never* happen!")
            except Exception as e:
                print(traceback.format_exc())
                print(f"[Error] Exception analyzing '{crx}': {e}")
                # Simply continue with next extension...
                # ...but don't forget to still put a result into the results_queue:
                analysis_result = {
                    "benchmarks": {
                        "crashes": [f"Python Exception: {repr(e)}"]
                    }
                }
                info["analysis_time"] = time.time() - analysis_start
                results_queue.put((info, analysis_result), block=False)
                continue
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done analyzing '{crx}' after "
                  f"{info['analysis_time']} seconds")
    except queue.Empty:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] End of process #{process_idx}. "
              f"No more extensions left in queue.")


def main():
    """ Parsing command line parameters. """

    parser = argparse.ArgumentParser(prog='doublex',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="Static analysis of a browser extension to detect "
                                                 "suspicious data flows")

    parser.add_argument("--crx", dest='crx', metavar="path", type=str, action='append', nargs='+',
                        help="Path(s) of the .CRX file(s) to unpack and analyze. "
                             "If used, the -cs and -bp arguments will be ignored. "
                             "May only be used in combination with --renderer-attacker!")

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
                             "Default: parent-path-of-content-script/analysis.json "
                             "Note that this parameter will be ignored when using --crx and, instead, the above "
                             "default value will always be used!")
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
                        help="Display the EDG (Extension Dependence Graph). "
                             "Won't work in combination with --renderer-attacker.")

    parser.add_argument("--print-pdgs", dest='print_pdgs', action='store_true',
                        help="Print the PDGs (Program Dependence Graphs) of CS and BP to console.")

    parser.add_argument("--renderer-attacker", dest='renderer_attacker', action='store_true',
                        help="Instead of running the regular DoubleX, analyze the given extension for vulnerabilities "
                             "exploitable by a renderer attacker (those considered by Young Min Kim and Byoungyoung "
                             "Lee in their 2023 paper 'Extending a Hand to Attackers: Browser Privilege Escalation "
                             "Attacks via Extensions'). "
                             "Note that --crx may only be used in combination with --renderer-attacker.")

    parser.add_argument("--return-multiple-flow-variants", dest='return_multiple_flow_variants',
                        action='store_true',
                        help="When this flag is set and there exist multiple data flows for a certain vulnerability "
                             "category, *all* of them will be returned (in analysis_renderer_attacker.json) instead of "
                             "just one; even multiple ones between the same source and the same sink! "
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
                             "found, by type. "
                             "No .CSV file will be created when the --csv-out argument isn't supplied.")

    parser.add_argument("--consider-http-as-safe", dest='consider_http_as_safe',
                        action='store_true',
                        help="Disables the default behavior of considering HTTP URL sender checks unsafe (they would "
                             "be exploitable by a renderer + network attacker).")
    # Note that a pure network attacker is not sufficient as we can regard such an attacker to be equivalent to a web
    #   attacker. Namely, a network attacker alone will not be able to forge extension messages!
    # A network attacker *with* renderer attacker capabilities however can forge extension messages, even without
    #   luring the user into visiting a crafted malicious site, if the BP accepts messages from HTTP origins.

    parser.add_argument("--include-31-violations-without-privileged-api-access",
                        dest='include_31_violations_without_privileged_api_access',
                        action='store_true',
                        help="Include violations of Security Requirement 3.1 (Extension Message Authentication), "
                             "even when no privileged API (like chrome.cookies, chrome.scripting or indexedDB) "
                             "is accessed (4.1).")

    parser.add_argument("--sort-crxs-by-size-ascending",
                        dest='sort_crxs_by_size_ascending',
                        action='store_true',
                        help="Sort all .CRX files given via the --crx argument by file size, ascending, before "
                             "starting to unpack and analyze them in that order. The idea is to begin with extensions "
                             "that are probably(!) quicker to analyze.")

    group3 = parser.add_mutually_exclusive_group(required=True)
    group3.add_argument('--prod', action='store_true',
                        help="Enables production mode. Program will continue after Exceptions.")
    group3.add_argument('--debug', action='store_true',
                        help="Enables debug mode. "
                             "Program will do some unnecessary computations that may find subtle bugs during "
                             "development however.")

    parser.add_argument("--timeout", metavar="seconds", type=int, default=600,
                        help="The timeout (in seconds) for analyzing each extension (including prior PDG generation). "
                             "Does *not* include the time needed for *unpacking* each CRX file! "
                             "(When not using the --renderer-attacker model, this timeout specifies the analysis "
                             "timeout *without* prior PDG generation and message linking.) "
                             "Default: 600 (i.e., 10 minutes)")

    parser.add_argument("--parallelize", metavar="no_extensions", type=int,
                        default=multiprocessing.cpu_count()//2,
                        help="The no. of extensions that will be analyzed in parallel. "
                             "Only has an effect in combination with --crx. "
                             "Default: CPU count/2 (as BP and CS of each extension will be analyzed in parallel, too)")

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

    if args.consider_http_as_safe:
        os.environ['CONSIDER_HTTP_AS_SAFE'] = "yes"

    if args.include_31_violations_without_privileged_api_access:
        os.environ['INCLUDE_31_VIOLATIONS_WITHOUT_PRIVILEGED_API_ACCESS'] = "yes"

    if args.debug:
        os.environ['DEBUG'] = "yes"
        print("[Info] Debug mode.")
    elif args.prod:
        print("[Info] Production mode.")
    else:
        raise AssertionError("neither args.debug nor args.prod is set")

    os.environ['TIMEOUT'] = str(args.timeout)

    if args.crx is None:  # No --crx argument supplied: Use -cs and -bp arguments:
        print("Analyzing a single, unpacked extension...")
        cs = args.cs
        bp = args.bp
        if cs is None:
            cs = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'contentscript.js')
        if bp is None:
            bp = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'background.js')

        # Whether to use the original DoubleX extension analysis,
        #   or whether to look for vulnerabilities exploitable by a renderer attacker:
        analyze_extension = doublex_analyze_extension
        if args.renderer_attacker:
            analyze_extension = kim_and_lee_analyze_extension

        analyze_extension(cs, bp, json_analysis=args.analysis, chrome=not args.not_chrome,
                          war=args.war, json_apis=args.apis, manifest_path=args.manifest)

    else:  # Ignore -cs and -bp arguments when --crx argument is supplied:
        if not args.renderer_attacker:
            print("--crx may only be used in combination with --renderer-attacker!")
            exit(1)

        # Flatten the --crx / args.crx argument:
        #     => example: "--crx a b --crx x y" becomes: [['a', 'b'], ['x', 'y']]
        crxs = [c for cs in args.crx for c in cs]
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyzing {len(crxs)} packed extensions...")

        # Use the folder in which the first .CRX file is situated in, create a subfolder called "unpacked" and use that:
        unpack_dest_dir = os.path.join(Path(crxs[0]).parent.absolute(), "unpacked")
        Path(unpack_dest_dir).mkdir(parents=False, exist_ok=True)
        print(f"Unpacking into folder: {unpack_dest_dir}")

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
            csv_out.write("Extension,name,browser action default title,version,manifest version,description,"
                          "permissions,optional permissions,host permissions,optional host permissions,"
                          "extension size (packed),extension size (unpacked),JS LoC,"
                          "BP code stats,CS code stats,"
                          "CS injected into,crashes,analysis time in seconds,total dangers,"
                          "BP exfiltration dangers,BP infiltration dangers,BP 3.1 violations w/o API danger,"
                          "CS exfiltration dangers,CS infiltration dangers,files and line numbers\n")
            csv_out.flush() # ToDo: add no. of UXSS vulnerabilities!

        if args.sort_crxs_by_size_ascending:
            print(f"Sorting {len(crxs)} .CRX files by file size...")
            crxs.sort(key=lambda crx_file: os.path.getsize(crx_file))
            print(f"Sorted {len(crxs)} .CRX files by file size.")

        # Put all .CRX files into a multiprocessing.Queue:
        crxs_queue = multiprocessing.Queue(maxsize=len(crxs))
        for crx in crxs:
            crxs_queue.put(crx)

        # Create and start N processes working off this queue and putting their results into a separate results queue:
        results_queue: multiprocessing.Queue[Tuple[dict, dict]] = multiprocessing.Queue(maxsize=len(crxs))
        processes = [Process(target=analyze_extensions_in_sequence,
                             args=[process_idx, crxs_queue, results_queue, unpack_dest_dir])
                     for process_idx in range(args.parallelize)]
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"Starting {len(processes)} worker processes...")
        for process in processes:
            process.start()

        # Main thread: Collect results and store them in the result CSV:
        start_time = time.time()
        results_collected: int = 0
        while results_collected < len(crxs):
            # Print progress to console:
            seconds_passed_so_far = int(time.time() - start_time)
            formatted_time_passed_so_far = format_seconds_to_printable_time(seconds_passed_so_far)
            print_progress(done=results_collected, total=len(crxs), of_what="CRXs",
                           suffix=f"({formatted_time_passed_so_far} passed so far)")

            info, analysis_result = results_queue.get(block=True)  # blocks until a result is available
            crx = info["crx"]
            extension_size_unpacked = info["extension_size_unpacked"]
            js_loc = info["js_loc"]
            bp_code_stats: str = " | ".join([f"{k}:{v}" for k, v in analysis_result['bp']['code_stats'].items()])
            cs_code_stats: str = " | ".join([f"{k}:{v}" for k, v in analysis_result['cs']['code_stats'].items()])
            analysis_time = info["analysis_time"]
            unpacked_ext_dir = info["unpacked_ext_dir"]

            results_collected += 1

            if args.csv_out != "":
                # Write analysis results, as well as lots of additional info on the extension, into the result CSV:

                # (1): Extension size (packed):
                try:
                    extension_size_packed = f"{os.path.getsize(crx):_}"
                except OSError:
                    extension_size_packed = "?"

                # (2): All sorts of additional info that can be extracted out of the manifest.json file:
                manifest_path = os.path.join(unpacked_ext_dir, 'manifest.json')  # == os.path.dirname(cs)
                manifest = json.load(open(manifest_path))
                ext_name = \
                    manifest['name'].replace(",", "").replace("\n", "") \
                        if 'name' in manifest else ""
                ext_browser_action_default_title = \
                    manifest['browser_action']['default_title'].replace(",", "").replace("\n", "") \
                        if 'browser_action' in manifest and 'default_title' in manifest['browser_action'] else ""
                ext_version = \
                    manifest['version'].replace(",", "").replace("\n", "") \
                        if 'version' in manifest else ""
                ext_manifest_version = \
                    str(manifest['manifest_version']).replace(",", "").replace("\n", "") \
                        if 'manifest_version' in manifest else ""
                ext_description = \
                    manifest['description'][:100].replace(",", "").replace("\n", "") \
                        if 'description' in manifest else ""
                ext_permissions = \
                    " | ".join(manifest['permissions']).replace(",", "").replace("\n", "")\
                        if 'permissions' in manifest else ""
                ext_optional_permissions = \
                    " | ".join(manifest['optional_permissions']).replace(",", "").replace("\n", "")\
                        if 'optional_permissions' in manifest else ""
                ext_host_permissions = \
                    " | ".join(manifest['host_permissions']).replace(",", "").replace("\n", "")\
                        if 'host_permissions' in manifest else ""
                ext_optional_host_permissions = \
                    " | ".join(manifest['optional_host_permissions']).replace(",", "").replace("\n", "")\
                        if 'optional_host_permissions' in manifest else ""

                # (3): Analysis results:
                content_script_injected_into = \
                    " | ".join(analysis_result['content_script_injected_into']).replace(",", "").replace("\n", "")\
                        if 'content_script_injected_into' in analysis_result else ""
                crashes = analysis_result['benchmarks']['crashes']\
                        if 'benchmarks' in analysis_result and 'crashes' in analysis_result['benchmarks'] else []
                crashes_bp = analysis_result['benchmarks']['bp']['crashes']\
                        if 'benchmarks' in analysis_result and 'bp' in analysis_result['benchmarks']\
                           and 'crashes' in analysis_result['benchmarks']['bp'] else []
                crashes_cs = analysis_result['benchmarks']['cs']['crashes']\
                        if 'benchmarks' in analysis_result and 'cs' in analysis_result['benchmarks']\
                           and 'crashes' in analysis_result['benchmarks']['cs'] else []
                crashes_all = " | ".join(crashes + crashes_bp + crashes_cs)\
                                .replace(",", "").replace("\n", "")
                bp_exfiltration_dangers = len(analysis_result['bp']['exfiltration_dangers'])\
                    if 'bp' in analysis_result and 'exfiltration_dangers' in analysis_result['bp'] else "N/A"
                bp_infiltration_dangers = len(analysis_result['bp']['infiltration_dangers'])\
                    if 'bp' in analysis_result and 'infiltration_dangers' in analysis_result['bp'] else "N/A"
                bp_31_violations_wo_api_danger = \
                    len(analysis_result['bp']['31_violations_without_sensitive_api_access']) \
                        if 'bp' in analysis_result\
                           and '31_violations_without_sensitive_api_access' in analysis_result['bp'] else "N/A"
                cs_exfiltration_dangers = len(analysis_result['cs']['exfiltration_dangers'])\
                    if 'cs' in analysis_result and 'exfiltration_dangers' in analysis_result['cs'] else "N/A"
                cs_infiltration_dangers = len(analysis_result['cs']['infiltration_dangers'])\
                    if 'cs' in analysis_result and 'infiltration_dangers' in analysis_result['cs'] else "N/A"
                total_no_of_dangers = sum(0 if d == "N/A" else d
                                          for d in [bp_exfiltration_dangers, bp_infiltration_dangers,
                                                    cs_exfiltration_dangers, cs_infiltration_dangers])
                files_and_line_numbers = ""  # ToDo: write once more types of vuln. are supported!

                # (4): Write all of that information into a new line in the output CSV file (and flush afterward):
                csv_out.write(f"{crx},{ext_name},{ext_browser_action_default_title},{ext_version},"
                              f"{ext_manifest_version},"
                              f"{ext_description},{ext_permissions},{ext_optional_permissions},"
                              f"{ext_host_permissions},{ext_optional_host_permissions},"
                              f"{extension_size_packed},{extension_size_unpacked},{js_loc},"
                              f"{bp_code_stats},{cs_code_stats},"
                              f"{content_script_injected_into},{crashes_all},"
                              f"{analysis_time},{total_no_of_dangers},"
                              f"{bp_exfiltration_dangers},{bp_infiltration_dangers},"
                              f"{bp_31_violations_wo_api_danger},"
                              f"{cs_exfiltration_dangers},{cs_infiltration_dangers},"
                              f"{files_and_line_numbers}\n")
                csv_out.flush()

        # Join all worker processes (all joins should terminate immediately as all extensions have been processed):
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"Joining all {len(processes)} worker processes; this should finish in no time...")
        for process in processes:
            process.join()

        # Close CSV output file:
        if args.csv_out != "":
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Closing CSV output file...")
            csv_out.close()

        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done." +
              (f" {results_collected} results collected in CSV file: {args.csv_out}" if args.csv_out != '' else ''))


if __name__ == "__main__":
    main()
