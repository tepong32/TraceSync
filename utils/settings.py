import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")

def _default_settings():
    return {
        "recent_pairs": [],
        "providers": {},
        "sync_preferences": {},
    }


class SettingsService:

    @staticmethod
    def load():
        settings = _default_settings()
        if not SETTINGS_FILE.exists():
            return settings

        try:
            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:
                loaded_settings = json.load(f)
                if not isinstance(loaded_settings, dict):
                    return settings
                settings.update(loaded_settings)
                return settings

        except (
            json.JSONDecodeError,
            OSError,
        ):
            return settings

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
