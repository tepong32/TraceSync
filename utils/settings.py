import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")


class SettingsService:

    @staticmethod
    def load():
        if not SETTINGS_FILE.exists():
            return {}

        try:
            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                return json.load(f)

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {}

    @staticmethod
    def save(settings):
        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                settings,
                f,
                indent=4,
            )