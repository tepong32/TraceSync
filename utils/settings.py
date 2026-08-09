import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")


def _normalize_ignore_patterns(raw_patterns) -> list[str]:
    """Normalize ignore patterns for safe, stable storage and usage."""
    normalized: list[str] = []
    if raw_patterns is None:
        return normalized

    if isinstance(raw_patterns, str):
        raw_patterns = raw_patterns.splitlines()
    elif not isinstance(raw_patterns, (list, tuple, set)):
        return normalized

    for pattern in raw_patterns:
        if not isinstance(pattern, str):
            continue

        normalized_pattern = pattern.strip()
        if not normalized_pattern or normalized_pattern.startswith("#"):
            continue

        normalized.append(normalized_pattern)

    return normalized


def _default_settings():
    return {
        "recent_pairs": [],
        "providers": {},
        "sync_preferences": {},
        "ignore_patterns": [],
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
                settings["ignore_patterns"] = _normalize_ignore_patterns(
                    settings.get("ignore_patterns"),
                )
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
            settings_copy = dict(settings)
            settings_copy["ignore_patterns"] = _normalize_ignore_patterns(
                settings_copy.get("ignore_patterns"),
            )
            json.dump(
                settings_copy,
                f,
                indent=4,
            )
