"""
A helper utility for moving/copying away all non-vulnerable extensions in a folder into a new separate folder.
The given folder is assumed to contain .CRX files and a folder named "unpacked", i.e., to look like this:

.
|-- aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.crx
|-- bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.crx
|-- cccccccccccccccccccccccccccccccc.crx
|-- report.md
|-- result.csv
`-- unpacked
    |-- aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    |   |-- analysis_renderer_attacker.json
    |   |-- background.js
    |   |-- content_scripts.js
    |   |-- manifest.json
    |   `-- wars.js
    |-- bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
    |   |-- analysis_renderer_attacker.json
    |   |-- background.js
    |   |-- content_scripts.js
    |   |-- manifest.json
    |   `-- wars.js
    |-- cccccccccccccccccccccccccccccccc
    |   |-- analysis_renderer_attacker.json
    |   |-- background.js
    |   |-- content_scripts.js
    |   |-- manifest.json
    |   `-- wars.js

After calling

$ python3 sort_out_non_vuln . /dest/folder

all folders inside /unpacked whose "analysis_renderer_attacker.json" file lists 0 vulnerabilities
("exfiltration_dangers": [], "infiltration_dangers": []) will be moved to /dest/folder/unpacked.
All corresponding .CRX files will be moved to /dest/folder.

When the -cp flag is supplied, the files are copied (i.e., duplicated) instead of moved.
When the -vuln flag is supplied, the logic is inverted and all *vulnerable* extensions are moved/copied!
"""


import argparse
import os.path
import shutil

from AnalysisRendererAttackerJSON import AnalysisRendererAttackerJSON


def main():
    parser = argparse.ArgumentParser(prog='sort_out_non_vuln',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="A helper utility for moving/copying away all non-vulnerable "
                                                 "extensions in a folder into a new separate folder.")

    parser.add_argument('SRC')

    parser.add_argument('DEST')

    parser.add_argument("-cp", dest='cp', action='store_true',
                        help="Copy files instead of moving them.")

    parser.add_argument("-vuln", dest='vuln', action='store_true',
                        help="Move/copy all *vulnerable* extensions instead of all non-vulnerable extensions.")

    parser.add_argument("-verbose", dest='verbose', action='store_true',
                        help="Verbose prints to console.")

    args = parser.parse_args()

    # 1. Check that the $src$/unpacked subdirectory exists:
    src_unpacked_dir = os.path.join(args.SRC, "unpacked")
    if not os.path.exists(src_unpacked_dir):
        print(f"Error: Source {args.SRC} contains no /unpacked subdirectory!")
        exit(1)
    elif not os.path.isdir(src_unpacked_dir):
        print(f"Error: {src_unpacked_dir} is not a directory!")
        exit(1)

    # 2. Create the $dest$ directory if it does not exist yet:
    if not os.path.exists(args.DEST):
        os.mkdir(args.DEST)
        print(f"Info: Created {args.DEST} directory.")
    elif os.path.isfile(args.DEST):
        print(f"Error: {args.DEST} already exists and it's a file, not a directory!")
        exit(1)

    # 3. In the exact same fashion, create the $dest$/unpacked directory if it does not exist yet:
    dest_unpacked_dir = os.path.join(args.DEST, "unpacked")
    if not os.path.exists(dest_unpacked_dir):
        os.mkdir(dest_unpacked_dir)
        print(f"Info: Created {dest_unpacked_dir} directory.")
    elif os.path.isfile(dest_unpacked_dir):
        print(f"Error: {dest_unpacked_dir} already exists and it's a file, not a directory!")
        exit(1)

    no_of_moves_performed: int = 0

    # 4. Iterate through all subfolders inside $src$/unpacked and perform a move/copy whenever the
    #    "analysis_renderer_attacker.json" file lists 0 vulnerabilities:
    with os.scandir(src_unpacked_dir) as directory_items:
        for subfolder in directory_items:
            if os.path.isdir(subfolder):
                analysis_json_file = os.path.join(subfolder, "analysis_renderer_attacker.json")
                if not os.path.exists(analysis_json_file):
                    print(f"Warning: {analysis_json_file} does not exist!")
                else:
                    analysis_json = AnalysisRendererAttackerJSON(analysis_json_file)
                    total_danger_count: int = analysis_json.total_danger_count()
                    if args.vuln and total_danger_count == 0:
                        if args.verbose:
                            print(f"Info: Not copying {subfolder} as no vulnerabilities were found.")
                    elif not args.vuln and total_danger_count > 0:
                        if args.verbose:
                            print(f"Info: Not copying {subfolder} as vulnerabilities were found.")
                    else:
                        # Perform move/copy of subfolder to /dest/folder/unpacked,
                        # as well as move/copy of the corresponding .CRX file one level up to /dest/folder:
                        extension_id = subfolder.name
                        crx_file = os.path.join(args.SRC, f"{extension_id}.crx")
                        if args.verbose:
                            print(f"Info: Copying {subfolder} and {crx_file} ...")
                        if args.cp:
                            shutil.copytree(subfolder, os.path.join(dest_unpacked_dir, subfolder.name), dirs_exist_ok=True)
                            shutil.copy(crx_file, args.DEST)  # Copies file. Destination may be a directory.
                        else:
                            shutil.move(subfolder, dest_unpacked_dir)  # If dst is an existing directory, then src is moved inside that directory.
                            shutil.move(crx_file, args.DEST)  # Moves file. Destination may be a directory.

                        no_of_moves_performed += 1

    print(f"Done. {no_of_moves_performed} {'copies' if args.cp else 'moves'} performed.")


if __name__ == "__main__":
    main()
