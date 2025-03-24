import argparse
import sys
import os
import statistics
from typing import List, Optional

from INJECTED_EVERYWHERE_PATTERNS import is_an_injected_everywhere_url_pattern


def longest_common_prefix(a: str, b: str) -> str:
    common_prefix: str = ""
    i: int = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        common_prefix += a[i]
        i += 1
    return common_prefix


def print_result_csv_stats(result_csv_path: str,
                           list_vuln_ext: bool,
                           list_vuln_exploitable_ext: bool):
    no_ext: int = 0  # (number of extensions)
    no_vuln_ext: int = 0  # (number of vulnerable extensions)
    no_vuln_ext_exploitable: int = 0  # (number of vulnerable, exploitable extensions)
    no_dangers: int = 0  # (number of dangers)
    no_dangers_exploitable: int = 0  # (number of exploitable dangers)
    # ----- -----
    bp_exf_no_ext: int = 0  # (number of extensions with at least 1 BP exfiltration danger)
    bp_exf_no_dangers: int = 0  # (number of BP exfiltration dangers)
    bp_exf_no_ext_exploitable: int = 0  # (number of exploitable extensions with at least 1 BP exfiltration danger)
    bp_exf_no_dangers_exploitable: int = 0  # (number of BP exfiltration dangers in exploitable extensions)
    bp_inf_no_ext: int = 0
    bp_inf_no_dangers: int = 0
    bp_inf_no_ext_exploitable: int = 0
    bp_inf_no_dangers_exploitable: int = 0
    # ---
    cs_exf_no_ext: int = 0
    cs_exf_no_dangers: int = 0
    cs_exf_no_ext_exploitable: int = 0
    cs_exf_no_dangers_exploitable: int = 0
    cs_inf_no_ext: int = 0
    cs_inf_no_dangers: int = 0
    cs_inf_no_ext_exploitable: int = 0
    cs_inf_no_dangers_exploitable: int = 0
    # ----- -----
    analysis_times: List[float] = []
    analysis_times_vuln_ext: List[float] = []
    extension_common_prefix: Optional[str] = None
    vulnerable_extensions: List[str] = []
    vulnerable_exploitable_extensions: List[str] = []

    with open(result_csv_path) as csv_file:
        # Determine the relevant column indices using the CSV header line:
        header_line: List[str] = next(csv_file).split(",")
        col_idx_extension: int = header_line.index("Extension")  # = the path to the .CRX file on the original machine
        col_idx_cs_injected_into: int = header_line.index("CS injected into")
        col_idx_analysis_time: int = header_line.index("analysis time in seconds")
        col_idx_total_dangers: int = header_line.index("total dangers")
        # -----
        col_idx_bp_exfiltration_dangers: int = header_line.index("BP exfiltration dangers")
        col_idx_bp_infiltration_dangers: int = header_line.index("BP infiltration dangers")
        col_idx_cs_exfiltration_dangers: int = header_line.index("CS exfiltration dangers")
        col_idx_cs_infiltration_dangers: int = header_line.index("CS infiltration dangers")

        for line in csv_file:
            line_split: List[str] = line.split(",")
            try:
                extension: str = line_split[col_idx_extension]
                cs_injected_into: List[str] = line_split[col_idx_cs_injected_into].split(" | ")
                analysis_time: float = float(line_split[col_idx_analysis_time])
                total_dangers: int = int(line_split[col_idx_total_dangers])
                # -----
                no_bp_exfiltration_dangers: int = int(line_split[col_idx_bp_exfiltration_dangers])
                no_bp_infiltration_dangers: int = int(line_split[col_idx_bp_infiltration_dangers])
                no_cs_exfiltration_dangers: int = int(line_split[col_idx_cs_exfiltration_dangers])
                no_cs_infiltration_dangers: int = int(line_split[col_idx_cs_infiltration_dangers])
            except IndexError:
                print(f"CSV error: Line has too few commas: {line_split}")
                exit(1)

            if extension_common_prefix is None:
                extension_common_prefix = extension
            else:
                extension_common_prefix = longest_common_prefix(extension_common_prefix, extension)

            no_ext += 1
            no_dangers += total_dangers
            if total_dangers > 0:
                no_vuln_ext += 1
                vulnerable_extensions.append(extension)
                analysis_times_vuln_ext.append(analysis_time)
            analysis_times.append(analysis_time)

            exploitable: bool = any(is_an_injected_everywhere_url_pattern(url_pattern)
                                    for url_pattern in cs_injected_into)

            if exploitable:
                no_dangers_exploitable += total_dangers
                if total_dangers > 0:
                    no_vuln_ext_exploitable += 1
                    vulnerable_exploitable_extensions.append(extension)

            # BP exfiltration dangers:
            bp_exf_no_dangers += no_bp_exfiltration_dangers
            if no_bp_exfiltration_dangers > 0:
                bp_exf_no_ext += 1
            if exploitable:
                bp_exf_no_dangers_exploitable += no_bp_exfiltration_dangers
                if no_bp_exfiltration_dangers > 0:
                    bp_exf_no_ext_exploitable += 1

            # BP infiltration dangers:
            bp_inf_no_dangers += no_bp_infiltration_dangers
            if no_bp_infiltration_dangers > 0:
                bp_inf_no_ext += 1
            if exploitable:
                bp_inf_no_dangers_exploitable += no_bp_infiltration_dangers
                if no_bp_infiltration_dangers > 0:
                    bp_inf_no_ext_exploitable += 1

            # CS exfiltration dangers:
            cs_exf_no_dangers += no_cs_exfiltration_dangers
            if no_cs_exfiltration_dangers > 0:
                cs_exf_no_ext += 1
            if exploitable:
                cs_exf_no_dangers_exploitable += no_cs_exfiltration_dangers
                if no_cs_exfiltration_dangers > 0:
                    cs_exf_no_ext_exploitable += 1

            # CS infiltration dangers:
            cs_inf_no_dangers += no_cs_infiltration_dangers
            if no_cs_infiltration_dangers > 0:
                cs_inf_no_ext += 1
            if exploitable:
                cs_inf_no_dangers_exploitable += no_cs_infiltration_dangers
                if no_cs_infiltration_dangers > 0:
                    cs_inf_no_ext_exploitable += 1

    print("")
    print("***** result.csv stats: *****")
    print(f"Result.csv file: {result_csv_path}")
    print(f"Extension common prefix: {extension_common_prefix}")
    print(f"No. of extensions: {no_ext}")
    print(f"No. of vulnerable extensions: {no_vuln_ext} ({no_vuln_ext_exploitable} exploitable)")
    print(f"No. of vulnerabilities/dangers found: {no_dangers} ({no_dangers_exploitable} exploitable)")
    print("-----")
    print(f"BP exfiltration: {bp_exf_no_dangers} dangers in {bp_exf_no_ext} extensions (exploitable: {bp_exf_no_dangers_exploitable} dangers in {bp_exf_no_ext_exploitable} extensions)")
    print(f"BP UXSS/infiltration: {bp_inf_no_dangers} dangers in {bp_inf_no_ext} extensions (exploitable: {bp_inf_no_dangers_exploitable} dangers in {bp_inf_no_ext_exploitable} extensions)")
    print(f"CS exfiltration: {cs_exf_no_dangers} dangers in {cs_exf_no_ext} extensions (exploitable: {cs_exf_no_dangers_exploitable} dangers in {cs_exf_no_ext_exploitable} extensions)")
    print(f"CS UXSS/infiltration: {cs_inf_no_dangers} dangers in {cs_inf_no_ext} extensions (exploitable: {cs_inf_no_dangers_exploitable} dangers in {cs_inf_no_ext_exploitable} extensions)")
    print("-----")
    print(f"Median analysis time: {statistics.median(analysis_times)}")
    print(f"Median analysis time of vulnerable extensions: {statistics.median(analysis_times_vuln_ext)}")
    print("")

    if list_vuln_ext:
        vulnerable_extensions.sort()
        print(f"Vulnerable extensions (count: {len(vulnerable_extensions)}):")
        for vuln_ext in vulnerable_extensions:
            print(vuln_ext)
        print("")

    if list_vuln_exploitable_ext:
        vulnerable_exploitable_extensions.sort()
        print(f"Vulnerable exploitable extensions (count: {len(vulnerable_exploitable_extensions)}):")
        for vuln_exploitable_ext in vulnerable_exploitable_extensions:
            print(vuln_exploitable_ext)
        print("")


def main():
    parser = argparse.ArgumentParser(prog='result_csv_stats',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     description="Reads a result.csv file and prints statistics.")

    parser.add_argument('RESULT_CSV_FILE', nargs='+')

    parser.add_argument("--list-vuln-ext", dest='list_vuln_ext', action='store_true',
                        help="List all vulnerable extensions in alphabetical order.")

    parser.add_argument("--list-vuln-exploitable-ext", dest='list_vuln_exploitable_ext',
                        action='store_true',
                        help="List all vulnerable exploitable(!) extensions in alphabetical order.")

    args = parser.parse_args()

    for result_csv_path in args.RESULT_CSV_FILE:
        if os.path.isfile(result_csv_path):
            print_result_csv_stats(result_csv_path=result_csv_path,
                                   list_vuln_ext=args.list_vuln_ext,
                                   list_vuln_exploitable_ext=args.list_vuln_exploitable_ext,
                                   )
        else:
            print()
            print(f"Error: {result_csv_path} is not a file!")
            print()


if __name__ == "__main__":
    main()
