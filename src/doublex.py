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

from vulnerability_detection import analyze_extension
from unpack_extension import unpack_extension

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


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

        for crx in crxs:
            # Unpack .CRX file into a temp directory:
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking '{crx}' ...")
            dest2 = unpack_extension(extension_crx=crx, dest=dest1)
            if dest2 is None:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacking failed: '{crx}'")
            else:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Unpacked '{crx}' into '{dest2}'")

                cs = os.path.join(dest2, "content_scripts.js")
                bp = os.path.join(dest2, "background.js")

                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analyzing '{crx}' ...")
                analyze_extension(cs, bp, json_analysis=args.analysis, chrome=not args.not_chrome,
                                  war=args.war, json_apis=args.apis, manifest_path=args.manifest)
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done analyzing '{crx}'")


if __name__ == "__main__":
    main()
