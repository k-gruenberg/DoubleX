import json
import sys
from typing import Optional, List
from INJECTED_EVERYWHERE_PATTERNS import is_an_injected_everywhere_url_pattern


# From https://gist.github.com/rene-d/9e584a7dd2935d0f461904b9f2950007:
RED = "\033[0;31m"
GREEN = "\033[0;32m"
BLUE = "\033[0;34m"
END_COLOR = "\033[0m"


class AnalysisRendererAttackerJSON:
    def __init__(self, path):
        self.path = path
        with open(path) as analysis_json_file:
            self.json = json.load(analysis_json_file)

    def __getitem__(self, item):
        return self.json[item]

    def bp_exfiltration_danger_count(self) -> int:
        return len(self.json["bp"]["exfiltration_dangers"])\
            if "bp" in self.json and "exfiltration_dangers" in self.json["bp"] else 0

    def bp_infiltration_danger_count(self) -> int:
        return len(self.json["bp"]["infiltration_dangers"]) \
            if "bp" in self.json and "infiltration_dangers" in self.json["bp"] else 0

    def bp_danger_count(self) -> int:
        return self.bp_exfiltration_danger_count() + self.bp_infiltration_danger_count()

    def cs_exfiltration_danger_count(self) -> int:
        return len(self.json["cs"]["exfiltration_dangers"])\
            if "cs" in self.json and "exfiltration_dangers" in self.json["cs"] else 0

    def cs_infiltration_danger_count(self) -> int:
        return len(self.json["cs"]["infiltration_dangers"]) \
            if "cs" in self.json and "infiltration_dangers" in self.json["cs"] else 0

    def cs_danger_count(self) -> int:
        return self.cs_exfiltration_danger_count() + self.cs_infiltration_danger_count()

    def total_danger_count(self) -> int:
        return self.bp_danger_count() + self.cs_danger_count()

    def get_dangers_in_str_repr(self) -> List[str]:
        result = list()

        if "bp" in self.json:
            if "exfiltration_dangers" in self.json["bp"]:
                for i, danger in enumerate(self.json["bp"]["exfiltration_dangers"]):
                    result.append(f"BP exfiltration danger #{i+1} with rendezvous @ {danger['rendezvous']['location']}")
            if "infiltration_dangers" in self.json["bp"]:
                for i, danger in enumerate(self.json["bp"]["infiltration_dangers"]):
                    result.append(f"BP infiltration danger #{i+1} with rendezvous @ {danger['rendezvous']['location']}")

        if "cs" in self.json:
            if "exfiltration_dangers" in self.json["cs"]:
                for i, danger in enumerate(self.json["cs"]["exfiltration_dangers"]):
                    result.append(f"CS exfiltration danger #{i+1} with rendezvous @ {danger['rendezvous']['location']}")
            if "infiltration_dangers" in self.json["cs"]:
                for i, danger in enumerate(self.json["cs"]["infiltration_dangers"]):
                    result.append(f"CS infiltration danger #{i+1} with rendezvous @ {danger['rendezvous']['location']}")

        return result

    def extension_cs_is_injected_everywhere(self) -> bool:
        """
        Returns True if and only if at least one content script of the extension (to which this
        analysis_renderer_attacker.json refers) is injected everywhere (e.g., using the "*://*/*" pattern).
        """
        return any(is_an_injected_everywhere_url_pattern(url_pattern)
                   for url_pattern in self.json["content_script_injected_into"])

    def print_summary(self, max_code_length: int = 150):
        """
        Prints a summary of this AnalysisRendererAttackerJSON to console.
        Useful for verifying vulnerabilities with *many* different possible flows as TP or FP!
        """
        print("")
        print(f"##### {self.path}: #####")
        print("")
        print(f"Total dangers: {self.total_danger_count()}")
        print(f"BP dangers: {self.bp_danger_count()} "
              f"({self.bp_exfiltration_danger_count()} exf. and {self.bp_infiltration_danger_count()} inf. dangers)")
        print(f"CS dangers: {self.cs_danger_count()} "
              f"({self.cs_exfiltration_danger_count()} exf. and {self.cs_infiltration_danger_count()} inf. dangers)")
        print("")

        # Select only the category with the highest danger count and print statistics about all its flow pairs:
        dangers_name: str
        dangers: list[dict]
        max_danger_count: int = max(
            self.bp_exfiltration_danger_count(),
            self.bp_infiltration_danger_count(),
            self.cs_exfiltration_danger_count(),
            self.cs_infiltration_danger_count(),
        )
        if self.bp_exfiltration_danger_count() == max_danger_count:
            dangers_name = "BP exfiltration dangers"
            dangers = self.json["bp"]["exfiltration_dangers"]
        elif self.bp_infiltration_danger_count() == max_danger_count:
            dangers_name = "BP infiltration dangers"
            dangers = self.json["bp"]["infiltration_dangers"]
        elif self.cs_exfiltration_danger_count() == max_danger_count:
            dangers_name = "CS exfiltration dangers"
            dangers = self.json["cs"]["exfiltration_dangers"]
        elif self.cs_infiltration_danger_count() == max_danger_count:
            dangers_name = "CS infiltration dangers"
            dangers = self.json["cs"]["infiltration_dangers"]
        else:
            raise Exception("this can't be")
        print(f"## {max_danger_count} {dangers_name}: ##")
        print("")
        from_flows: list[list] = [d["from_flow"] for d in dangers]
        no_of_different_from_flows: int = len(set(';'.join(node['location'] for node in f) for f in from_flows))
        from_flow_lengths: list[int] = sorted(set(len(f) for f in from_flows))
        to_flows: list[list] = [d["to_flow"] for d in dangers]
        no_of_different_to_flows: int = len(set(';'.join(node['location'] for node in t) for t in to_flows))
        to_flow_lengths: list[int] = sorted(set(len(t) for t in to_flows))
        rendezvous: list[dict] = [d["rendezvous"] for d in dangers]
        rendezvous_locations: set = set(r["location"] for r in rendezvous)
        rendezvous_locations_sorted: list = sorted(
            rendezvous_locations,
            key=lambda loc: (int(loc.split(":")[0]), int(loc.split(":")[1].split(" ")[0]))
        )
        print(f"No. of different from flows: {no_of_different_from_flows} (lengths: {from_flow_lengths})")
        print(f"No. of different to flows: {no_of_different_to_flows} (lengths: {to_flow_lengths})")
        print(f"No. of different rendezvous: "
              f"{len(rendezvous_locations)} "
              f"({', '.join(sorted(set(r["type"] for r in rendezvous)))} ; "
              f"locations: {', '.join(rendezvous_locations_sorted)})")
        print("")

        if no_of_different_from_flows == 1:
            print("# From flow: #")
            print(json.dumps(from_flows[0], indent=4))
        else:
            print("# From flows: #")
            for i in range(min(from_flow_lengths)):
                ith_node_options: list[dict] = flows_get_ith_node_options(flows=from_flows, i=i)
                print(f"Node #{i+1}: {len(ith_node_options)} options:")
                for ith_node in ith_node_options:
                    print(f'\t"{ith_node['identifier']}" @ {ith_node['location']}:    '
                          f'{highlight(ith_node['line_of_code'], ith_node['location'], RED).lstrip()[:max_code_length]}{END_COLOR}')
            last_node_options: list[dict] = flows_get_last_node_options(flows=from_flows)
            print(f"Last node: {len(last_node_options)} options:")
            for last_node in last_node_options:
                print(f'\t"{last_node['identifier']}" @ {last_node['location']}:    '
                      f'{highlight(last_node['line_of_code'], last_node['location'], RED).lstrip()[:max_code_length]}{END_COLOR}')
        print("")

        if no_of_different_to_flows == 1:
            print("# To flow: #")
            print(json.dumps(to_flows[0], indent=4))
        else:
            print("# To flows: #")
            for i in range(min(to_flow_lengths)):
                ith_node_options: list[dict] = flows_get_ith_node_options(flows=to_flows, i=i)
                print(f"Node #{i + 1}: {len(ith_node_options)} options:")
                for ith_node in ith_node_options:
                    print(f'\t"{ith_node['identifier']}" @ {ith_node['location']}:    '
                          f'{highlight(ith_node['line_of_code'], ith_node['location'], GREEN).lstrip()[:max_code_length]}{END_COLOR}')
            last_node_options: list[dict] = flows_get_last_node_options(flows=to_flows)
            print(f"Last node: {len(last_node_options)} options:")
            for last_node in last_node_options:
                print(f'\t"{last_node['identifier']}" @ {last_node['location']}:    '
                      f'{highlight(last_node['line_of_code'], last_node['location'], GREEN).lstrip()[:max_code_length]}{END_COLOR}')
        print("")

        print("# Rendezvous: #")
        for idx, r_location in enumerate(rendezvous_locations_sorted):
            r = [r for r in rendezvous if r['location'] == r_location][0]
            r_type: str = r['type']
            r_type += " " * (len("AssignmentExpression") - len(r_type))
            print(f"({idx+1}) {r_type} @ {r['location']}:\t"
                  f"{highlight(r['line_of_code'], r['location'], BLUE).lstrip()[:max_code_length]}{END_COLOR}")
        print("")

        print("# Bottlenecks (lines occurring in either the from flow or the to flow of *every* danger): #")
        bottleneck_lines: set[int] | None = None
        all_line_contents: dict[int, str] = dict()
        for danger in dangers:
            line_contents: dict[int, str] = dict()
            for node in danger["from_flow"]:
                line_contents[int(node["location"].split(":")[0])] = node["line_of_code"]
            for node in danger["to_flow"]:
                line_contents[int(node["location"].split(":")[0])] = node["line_of_code"]
            all_line_contents.update(line_contents)
            if bottleneck_lines is None:
                bottleneck_lines = set(line_contents.keys())
            else:
                bottleneck_lines = bottleneck_lines.intersection(line_contents.keys())
        for line in sorted(bottleneck_lines):
            print(f"Line {line}:\t{all_line_contents[line].lstrip()}")
        print("")


def flows_get_ith_node_options(flows: list[list], i: int) -> list[dict]:
    node_options: list[dict] = list()
    for flow in flows:
        ith_node = flow[i]
        if not any(n["location"] == ith_node["location"] for n in node_options):  # (do not add duplicates)
            node_options.append(ith_node)
    return node_options


def flows_get_last_node_options(flows: list[list]) -> list[dict]:
    return flows_get_ith_node_options(flows=flows, i=-1)


def highlight(text: str, location: str, color: str):
    start, end = location.split(" - ")
    start_line, start_col = map(int, start.split(":"))
    end_line, end_col = map(int, end.split(":"))
    if start_line != end_line:
        return text
    else:
        return text[:start_col] + color + text[start_col:end_col] + END_COLOR + text[end_col:]


def main():
    if len(sys.argv) <= 1:
        print("Argument missing: <PATH_TO_ANALYSIS_RENDERER_ATTACKER_JSON>")
        exit(1)
    path: str = sys.argv[1]
    analysis_renderer_attacker_json: AnalysisRendererAttackerJSON = AnalysisRendererAttackerJSON(path=path)
    analysis_renderer_attacker_json.print_summary()


if __name__ == "__main__":
    main()
