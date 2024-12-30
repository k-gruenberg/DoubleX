import json
from typing import Optional


class ManifestJSON:
    def __init__(self, path):
        self.path = path
        with open(path) as manifest_json_file:
            self.json = json.load(manifest_json_file)

    def __getitem__(self, item):
        return self.json[item]

    def get_name(self) -> Optional[str]:
        """
        Returns the "name" field of this manifest.json file.
        If not (or only placeholder value) present, returns the "default_title" field of the "browser_action" field.
        If not (or only placeholder value) present here, too, returns `None`.
        """
        manifest = self.json
        ext_name = manifest['name'].replace("\n", "\\n") if 'name' in manifest else ""
        ext_browser_action_default_title = \
            manifest['browser_action']['default_title'].replace("\n", "\\n") \
                if 'browser_action' in manifest and 'default_title' in manifest['browser_action'] else ""
        # Note:
        #   Some fields may start with "__MSG_" due to internationalization:
        #   => cf. https://developer.chrome.com/docs/extensions/reference/api/i18n
        if ext_name != "" and not ext_name.startswith("__MSG_"):
            return ext_name
        elif ext_browser_action_default_title != "" and not ext_browser_action_default_title.startswith("__MSG_"):
            return ext_browser_action_default_title
        else:
            return None

    def get_name_or_else(self, default: str) -> str:
        name = self.get_name()
        return name if name is not None else default

    def get_description(self) -> Optional[str]:
        if "description" in self.json:
            description = self.json["description"]
            return description if not description.startswith("__MSG_") else None
        else:
            return None

    def get_description_or_else(self, default: str) -> str:
        description = self.get_description()
        return description if description is not None else default
