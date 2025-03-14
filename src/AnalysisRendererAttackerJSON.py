import json
from typing import Optional, List
from INJECTED_EVERYWHERE_PATTERNS import is_an_injected_everywhere_url_pattern


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
