import os.path
from typing import List, Optional
import re


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

    def has_annotation_for(self, extension: str, vulnerability: str) -> bool:
        with open(self.path, 'r') as csv_file:
            for line in csv_file:
                if line.startswith(extension + "," + vulnerability + ","):
                    return True
        return False

    def add_or_update_annotation(self, extension: str, vulnerability: str, true_positive: bool, comment: str):
        """
        Adds a new line to the annotations.csv file.
        If the (extension, vulnerability) pair is already present in the annotations.csv file however,
        no new line is added and instead the existing boolean value (FP/TP) and comment updated with the values given.
        """
        if self.has_annotation_for(extension=extension, vulnerability=vulnerability):
            # Update existing annotation:
            # (1) Read entire annotations.csv file:
            with open(self.path, 'r') as file:
                file_content = file.read()
            # (2) Update line of interest:
            file_content = re.sub(
                pattern=f"{extension},{vulnerability},.+,.*\n",
                repl=f"{extension},{vulnerability},{true_positive},{comment}\n",
                string=file_content,
                count=1,
            )
            # (3) Write entire content back to file (replacing all existing content):
            with open(self.path, 'w') as file:  # 'w' = open for writing, truncating the file first
                file.write(file_content)
        else:
            # Add new annotation:
            with open(self.path, 'a') as csv_file:
                csv_file.write(f"{extension},{vulnerability},{true_positive},{comment}\n")

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
