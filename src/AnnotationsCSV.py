import os.path
from typing import List, Optional


class AnnotationsCSV:
    def __init__(self, path: str):
        self.path = path
        if not os.path.isfile(path):
            if os.path.exists(path):
                raise Exception(f"{path} already exists but is not a file!")
            else:
                # Create an empty file:
                open(path, 'a').close()
                print(f"Created {path}")

    def add_annotation(self, extension: str, vulnerability: str, true_positive: bool, comment: str):
        with open(self.path, 'a') as csv_file:
            csv_file.write(f"{extension},{vulnerability},{true_positive},{comment}\n")

    # ToDo: also allow for updating annotations !!!

    def get_annotations(self, extension: str) -> List[str]:
        result: List[str] = list()
        with open(self.path, 'r') as csv_file:
            for line in csv_file:
                if line.startswith(extension + ","):
                    result.append(line.rstrip())
        return result

    def get_annotation_bool(self, extension: str, vulnerability: str) -> Optional[bool]:
        with open(self.path, 'r') as csv_file:
            for line in csv_file:
                if line.startswith(extension + "," + vulnerability + ","):
                    true_positive: str = line.split(",", maxsplit=3)[2]
                    if true_positive == "True":
                        return True
                    elif true_positive == "False":
                        return False
                    else:
                        return None
        return None

    def get_annotation_comment(self, extension: str, vulnerability: str) -> str:
        with open(self.path, 'r') as csv_file:
            for line in csv_file:
                if line.startswith(extension + "," + vulnerability + ","):
                    comment: str = line.split(",", maxsplit=3)[3].rstrip()
                    return comment
        return ""
