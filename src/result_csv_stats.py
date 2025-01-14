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


def print_result_csv_stats(result_csv_path: str):
    no_ext: int = 0
    no_vuln_ext: int = 0
    no_vuln_ext_exploitable: int = 0
    no_dangers: int = 0
    no_dangers_exploitable: int = 0
    analysis_times: List[float] = []
    extension_common_prefix: Optional[str] = None

    with open(result_csv_path) as csv_file:
        # Determine the relevant column indices using the CSV header line:
        header_line: List[str] = next(csv_file).split(",")
        col_idx_extension: int = header_line.index("Extension")  # = the path to the .CRX file on the original machine
        col_idx_cs_injected_into: int = header_line.index("CS injected into")
        col_idx_analysis_time: int = header_line.index("analysis time in seconds")
        col_idx_total_dangers: int = header_line.index("total dangers")

        for line in csv_file:
            line_split: List[str] = line.split(",")
            extension: str = line_split[col_idx_extension]
            cs_injected_into: List[str] = line_split[col_idx_cs_injected_into].split(" | ")
            analysis_time: float = float(line_split[col_idx_analysis_time])
            total_dangers: int = int(line_split[col_idx_total_dangers])

            if extension_common_prefix is None:
                extension_common_prefix = extension
            else:
                extension_common_prefix = longest_common_prefix(extension_common_prefix, extension)

            no_ext += 1
            no_dangers += total_dangers
            if total_dangers > 0:
                no_vuln_ext += 1
            analysis_times.append(analysis_time)

            exploitable: bool = any(is_an_injected_everywhere_url_pattern(url_pattern)
                                    for url_pattern in cs_injected_into)

            if exploitable:
                no_dangers_exploitable += total_dangers
                if total_dangers > 0:
                    no_vuln_ext_exploitable += 1

    print("")
    print("***** result.csv stats: *****")
    print(f"Result.csv file: {result_csv_path}")
    print(f"Extension common prefix: {extension_common_prefix}")
    print(f"No. of extensions: {no_ext}")
    print(f"No. of vulnerable extensions: {no_vuln_ext} ({no_vuln_ext_exploitable} exploitable)")
    print(f"No. of vulnerabilities/dangers found: {no_dangers} ({no_dangers_exploitable} exploitable)")
    print(f"Median analysis time: {statistics.median(analysis_times)}")
    print("")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 result_csv_stats.py <RESULT_CSV_FILE> ...")
        exit(1)
    else:
        for result_csv_path in sys.argv[1:]:
            if os.path.isfile(result_csv_path):
                print_result_csv_stats(result_csv_path=result_csv_path)
            else:
                print()
                print(f"Error: {result_csv_path} is not a file!")
                print()


if __name__ == "__main__":
    main()
