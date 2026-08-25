import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")
PROVIDER_OPTIONS = (
    "Local Folder (active)",
    "OneDrive (coming soon)",
    "Google Drive (coming soon)",
    "Dropbox (coming soon)",
)
DEFAULT_PROVIDER = PROVIDER_OPTIONS[0]


def _normalize_provider_value(raw_provider, provider_options):
    if raw_provider in provider_options:
        return raw_provider
    return DEFAULT_PROVIDER


def _normalize_provider_settings(raw_providers) -> dict[str, str]:
    normalized = {
        "source_provider": DEFAULT_PROVIDER,
        "destination_provider": DEFAULT_PROVIDER,
    }
    if not isinstance(raw_providers, dict):
        return normalized

    normalized["source_provider"] = _normalize_provider_value(
        raw_providers.get("source_provider"),
        PROVIDER_OPTIONS,
    )
    normalized["destination_provider"] = _normalize_provider_value(
        raw_providers.get("destination_provider"),
        PROVIDER_OPTIONS,
    )
    return normalized


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


def _normalize_folder_pairs(raw_pairs) -> list[dict[str, str]]:
    """Return valid, uniquely named Local/Server folder relationships."""
    normalized: list[dict[str, str]] = []
    seen_names: set[str] = set()
    if not isinstance(raw_pairs, (list, tuple)):
        return normalized

    for pair in raw_pairs:
        if not isinstance(pair, dict):
            continue

        name = pair.get("name")
        local_folder = pair.get("local_folder")
        server_folder = pair.get("server_folder")
        if not all(
            isinstance(value, str)
            for value in (name, local_folder, server_folder)
        ):
            continue

        normalized_pair = {
            "name": name.strip(),
            "local_folder": local_folder.strip(),
            "server_folder": server_folder.strip(),
        }
        if not all(normalized_pair.values()):
            continue

        name_key = normalized_pair["name"].casefold()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        normalized.append(normalized_pair)

    return normalized


def _normalize_active_folder_pair(raw_name, folder_pairs) -> str:
    """Resolve an active pair name to its canonical persisted capitalization."""
    if not isinstance(raw_name, str):
        return ""

    name_key = raw_name.strip().casefold()
    if not name_key:
        return ""

    for pair in folder_pairs:
        if pair["name"].casefold() == name_key:
            return pair["name"]
    return ""


def _default_settings():
    return {
        "recent_pairs": [],
        "folder_pairs": [],
        "active_folder_pair": "",
        "providers": {
            "source_provider": DEFAULT_PROVIDER,
            "destination_provider": DEFAULT_PROVIDER,
        },
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
                settings["providers"] = _normalize_provider_settings(
                    settings.get("providers"),
                )
                settings["ignore_patterns"] = _normalize_ignore_patterns(
                    settings.get("ignore_patterns"),
                )
                if "folder_pairs" in loaded_settings:
                    raw_folder_pairs = loaded_settings.get("folder_pairs")
                else:
                    raw_folder_pairs = loaded_settings.get("recent_pairs", [])
                settings["folder_pairs"] = _normalize_folder_pairs(
                    raw_folder_pairs,
                )
                settings["active_folder_pair"] = _normalize_active_folder_pair(
                    settings.get("active_folder_pair"),
                    settings["folder_pairs"],
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
            settings_copy["providers"] = _normalize_provider_settings(
                settings_copy.get("providers"),
            )
            settings_copy["folder_pairs"] = _normalize_folder_pairs(
                settings_copy.get(
                    "folder_pairs",
                    settings_copy.get("recent_pairs", []),
                ),
            )
            settings_copy["active_folder_pair"] = _normalize_active_folder_pair(
                settings_copy.get("active_folder_pair"),
                settings_copy["folder_pairs"],
            )
            json.dump(
                settings_copy,
                f,
                indent=4,
            )
