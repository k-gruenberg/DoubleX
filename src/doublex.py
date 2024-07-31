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

from vulnerability_detection import analyze_extension

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def main():
    """ Parsing command line parameters. """

    parser = argparse.ArgumentParser(prog='doublex',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="Static analysis of a browser extension to detect "
                                                 "suspicious data flows")

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

    cs = args.cs
    bp = args.bp
    if cs is None:
        cs = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'contentscript.js')
    if bp is None:
        bp = os.path.join(os.path.dirname(SRC_PATH), 'empty', 'background.js')

    analyze_extension(cs, bp, json_analysis=args.analysis, chrome=not args.not_chrome,
                      war=args.war, json_apis=args.apis, manifest_path=args.manifest)


if __name__ == "__main__":
    main()
