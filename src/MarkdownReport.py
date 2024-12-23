from typing import List
import time
import socket
import multiprocessing
import os
import json
import traceback
import re
import sys


def markdown_escape(unescaped_str: str) -> str:
    """
    Markdown has special characters, which you need to escape if you want to output a string literally.
    """
    # List of characters that need to be escaped in Markdown
    #   (see also: https://github.com/mattcone/markdown-guide/blob/master/_basic-syntax/escaping-characters.md):
    special_chars: List[str] =\
        ["\\", "`", "*", "_", "{", "}", "[", "]", "<", ">", "(", ")", "#", "+", "-", ".", "!", "|"]
    trans = str.maketrans({char: f"\\{char}" for char in special_chars})
    return unescaped_str.translate(trans)


def read_from_source_file(filename: str, location: str,
                          lines_before: int = 10, lines_after: int = 10, max_no_of_lines: int = 100) -> str:
    """
    Parameters:
        filename: e.g.: "/extension/path/background.js"
        location: e.g.: "4:12 - 4:33"
        lines_before: how many additional preceding lines to include as well (if possible); default: 10
        lines_after: how many additional subsequent lines to include as well (if possible); default: 10
        max_no_of_lines: the maximum number of lines to read; default: 100
    """
    [start, end] = location.split(" - ")
    start_line: int = int(start.split(":")[0])
    end_line: int = int(end.split(":")[0])

    start_line = start_line - lines_before
    end_line = end_line + lines_after

    lines: List[str] = []

    with open(filename, "r") as f:
        for current_line_num, line in enumerate(f, start=1):
            if len(lines) >= max_no_of_lines:
                break  # stop reading
            elif start_line <= current_line_num <= end_line:
                lines.append(line)
            elif current_line_num > end_line:
                break  # stop reading

    return "".join(lines)


class MarkdownReport:
    """
    This class handles the creating of the human-readable Markdown report.
    Cf. --md-out command line argument.
    """

    def __init__(self, md_path: str, no_worker_processes_used: int, timeout_used: int, append: bool = False):
        """
        Parameters:
            md_path: the path to the .md (Markdown) file to create;
                     file shall not exist yet (if append=False), file *must* exist (if append=True);
                     existing content is overwritten ("w" flag), unless append=True
            no_worker_processes_used: the number of worker processes used
            timeout_used: the timeout used (in seconds)
            append: set to True if you want to append to an *existing* Markdown file (default: False)

        Raises:
            IOError if append=False and file already exists, or if append=True and file *doesn't* exist
        """
        if append:
            if not os.path.exists(md_path):
                raise IOError(f"MarkdownReport: cannot append to non-existing MarkdownReport @ {md_path}")

            self.f = open(md_path, "a")
            print(f"[Info] Appending to existing Markdown report file: {md_path}")
            self.f.write("\n")
            self.f.write(f"----- Continued analysis on {time.strftime('%Y-%m-%d %H:%M:%S')} -----  \n")
            self.f.write("\n")
            self.f.flush()
        else:
            if os.path.exists(md_path):
                raise IOError(f"MarkdownReport: cannot write MarkdownReport @ {md_path} (already exists)")

            self.f = open(md_path, "w")
            print(f"[Info] Created Markdown report file: {md_path}")
            self.f.write(
                "# Vulnerability Report\n"
                "\n"
                f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n"
                "\n"
                "**Machine:**  \n"
                f"Hostname: {markdown_escape(socket.gethostname())}  \n"
                f"No. of cores: {multiprocessing.cpu_count()}  \n"
                "\n"
                f"No. of worker processes used: {no_worker_processes_used}  \n"
                f"Timeout used: {timeout_used} sec  \n"
                "\n"
                "**Command line arguments:**  \n"
                f"{"  \n".join(f'{idx}: {markdown_escape(arg)}' for idx, arg in enumerate(sys.argv))}"
                "\n"
            )
            self.f.flush()

    def add_extension(self, info: dict, analysis_result: dict):
        """
        Parameters:
            info: dictionary; shall contain the following keys:
                  "crx", "extension_size_unpacked", "js_loc", "js_code_avg_lengths", "analysis_time", "unpacked_ext_dir"
            analysis_result: dictionary; shall contain the following keys:
                             "benchmarks";
                             will contain the return value of (kim_and_lee_)analyze_extension() on success
        """
        try:
            # BP:
            bp_exfiltration_dangers: list = analysis_result['bp']['exfiltration_dangers'] \
                if 'bp' in analysis_result and 'exfiltration_dangers' in analysis_result['bp'] else []
            bp_infiltration_dangers: list = analysis_result['bp']['infiltration_dangers'] \
                if 'bp' in analysis_result and 'infiltration_dangers' in analysis_result['bp'] else []

            # CS:
            cs_exfiltration_dangers: list = analysis_result['cs']['exfiltration_dangers'] \
                if 'cs' in analysis_result and 'exfiltration_dangers' in analysis_result['cs'] else []
            cs_infiltration_dangers: list = analysis_result['cs']['infiltration_dangers'] \
                if 'cs' in analysis_result and 'infiltration_dangers' in analysis_result['cs'] else []

            total_no_of_dangers: int = sum(len(d)
                                           for d in [bp_exfiltration_dangers, bp_infiltration_dangers,
                                                     cs_exfiltration_dangers, cs_infiltration_dangers])

            # Only add extensions to the Markdown report that have at least 1 (real) danger:
            if total_no_of_dangers > 0:
                # Some info on the extension needs to be extracted from the manifest.json file:
                unpacked_ext_dir = info["unpacked_ext_dir"]
                manifest_path = os.path.join(unpacked_ext_dir, 'manifest.json')
                manifest = json.load(open(manifest_path))
                # Name:
                ext_name = \
                    manifest['name'].replace("\n", "\\n") \
                        if 'name' in manifest else ""
                ext_browser_action_default_title = \
                    manifest['browser_action']['default_title'].replace("\n", "\\n") \
                        if 'browser_action' in manifest and 'default_title' in manifest['browser_action'] else ""
                # Note:
                #   Some fields may start with "__MSG_" due to internationalization:
                #   => cf. https://developer.chrome.com/docs/extensions/reference/api/i18n
                if ext_name != "" and not ext_name.startswith("__MSG_"):
                    extension_name = ext_name
                elif ext_browser_action_default_title != "" and not ext_browser_action_default_title.startswith("__MSG_"):
                    extension_name = ext_browser_action_default_title
                else:
                    extension_name = "<Extension with unknown name>"
                # Version:
                ext_version = \
                    manifest['version'].replace("\n", "\\n") \
                        if 'version' in manifest else "N/A"
                # Manifest Version:
                ext_manifest_version = \
                    str(manifest['manifest_version']).replace("\n", "\\n") \
                        if 'manifest_version' in manifest else "N/A"
                # Description:
                ext_description = \
                    manifest['description'][:100].replace("\n", "\\n") \
                        if 'description' in manifest else "N/A"

                # CS injected into:
                content_script_injected_into = \
                        analysis_result['content_script_injected_into'] \
                        if 'content_script_injected_into' in analysis_result else "N/A"

                # Host permissions:
                host_permissions = \
                    manifest['host_permissions'] \
                        if 'host_permissions' in manifest else "N/A"

                # Optional host permissions:
                optional_host_permissions = \
                    manifest['optional_host_permissions'] \
                        if 'optional_host_permissions' in manifest else "N/A"

                # Extension size (packed):
                try:
                    extension_size_packed = f"{os.path.getsize(info['crx']):_}"
                except (KeyError, OSError):
                    extension_size_packed = "?"

                # Crashes:
                crashes = analysis_result['benchmarks']['crashes'] \
                    if 'benchmarks' in analysis_result and 'crashes' in analysis_result['benchmarks'] else None
                crashes_bp = analysis_result['benchmarks']['bp']['crashes'] \
                    if 'benchmarks' in analysis_result and 'bp' in analysis_result['benchmarks'] \
                       and 'crashes' in analysis_result['benchmarks']['bp'] else None
                crashes_cs = analysis_result['benchmarks']['cs']['crashes'] \
                    if 'benchmarks' in analysis_result and 'cs' in analysis_result['benchmarks'] \
                       and 'crashes' in analysis_result['benchmarks']['cs'] else None

                self.f.write(
                    f"## {markdown_escape(extension_name)} (version {markdown_escape(ext_version)}, MV{ext_manifest_version})\n"
                    "\n"
                    f"**Description:** {markdown_escape(ext_description)}  \n"
                    f"**Extension Path:** {markdown_escape(info.get('crx'))}  \n"
                    f"**Extension Path (unpacked):** {markdown_escape(unpacked_ext_dir)}  \n"
                    "\n"
                    f"**CS injected into:** {markdown_escape(str(content_script_injected_into))}  \n"
                    "\n"
                    f"**Host permissions:** {markdown_escape(str(host_permissions))}  \n"
                    f"**Optional host permissions:** {markdown_escape(str(optional_host_permissions))}  \n"
                    "\n"
                    "**Extension stats:**  \n"
                    f"**JavaScript LoC:** {info.get('js_loc')}  \n"
                    f"**Extension size (packed):** {extension_size_packed} B  \n"
                    f"**Extension size (unpacked):** {info.get('extension_size_unpacked')} B  \n"
                    "\n"
                    "**Analysis:**  \n"
                    f"**Analysis time:** {info.get('analysis_time')} sec  \n"
                    f"**BP Crashes:** {markdown_escape(str(crashes_bp))}  \n"
                    f"**CS Crashes:** {markdown_escape(str(crashes_cs))}  \n"
                    f"**Other Crashes:** {markdown_escape(str(crashes))}  \n"
                    "\n"
                )

                # BP exfiltration dangers:
                for i, bp_exf_danger in enumerate(bp_exfiltration_dangers):
                    self.f.write(
                        f"### BP exfiltration danger no.{i+1}\n"
                        "\n"
                        "```json\n"
                        f"{json.dumps(bp_exf_danger, indent=4, sort_keys=False, skipkeys=True)}\n"
                        "```\n"
                        "\n"
                        "Code excerpt:\n"
                        "```js\n"
                        f"{read_from_source_file(bp_exf_danger['rendezvous']['filename'], bp_exf_danger['rendezvous']['location'])}\n"
                        "```\n"
                        "\n"
                    )

                # BP infiltration dangers:
                for i, bp_inf_danger in enumerate(bp_infiltration_dangers):
                    self.f.write(
                        f"### BP infiltration danger no.{i + 1}\n"
                        "\n"
                        "```json\n"
                        f"{json.dumps(bp_inf_danger, indent=4, sort_keys=False, skipkeys=True)}\n"
                        "```\n"
                        "\n"
                        "Code excerpt:\n"
                        "```js\n"
                        f"{read_from_source_file(bp_inf_danger['rendezvous']['filename'], bp_inf_danger['rendezvous']['location'])}\n"
                        "```\n"
                        "\n"
                    )

                # CS exfiltration dangers:
                for i, cs_exf_danger in enumerate(cs_exfiltration_dangers):
                    self.f.write(
                        f"### CS exfiltration danger no.{i + 1}\n"
                        "\n"
                        "```json\n"
                        f"{json.dumps(cs_exf_danger, indent=4, sort_keys=False, skipkeys=True)}\n"
                        "```\n"
                        "\n"
                        "Code excerpt:\n"
                        "```js\n"
                        f"{read_from_source_file(cs_exf_danger['rendezvous']['filename'], cs_exf_danger['rendezvous']['location'])}\n"
                        "```\n"
                        "\n"
                    )

                # CS infiltration dangers:
                for i, cs_inf_danger in enumerate(cs_infiltration_dangers):
                    self.f.write(
                        f"### CS infiltration danger no.{i + 1}\n"
                        "\n"
                        "```json\n"
                        f"{json.dumps(cs_inf_danger, indent=4, sort_keys=False, skipkeys=True)}\n"
                        "```\n"
                        "\n"
                        "Code excerpt:\n"
                        "```js\n"
                        f"{read_from_source_file(cs_inf_danger['rendezvous']['filename'], cs_inf_danger['rendezvous']['location'])}\n"
                        "```\n"
                        "\n"
                    )

                self.f.flush()

        except Exception as e:  # Fail gracefully on any Exception:
            print(traceback.format_exc())
            print(f"[Error] Exception occurred during MarkdownReport.add_extension(): {e}")

    def close_file(self):
        self.f.write(
            "\n"
            "\n"
            "\n"
            f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n"
        )
        self.f.close()
