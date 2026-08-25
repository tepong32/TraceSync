import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.settings as settings_module


class SettingsServiceTests(unittest.TestCase):
    def test_provider_preferences_default_when_missing_or_invalid(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            settings_file.write_text(
                json.dumps(
                    {
                        "providers": {
                            "source_provider": "Google Drive (coming soon)",
                            "destination_provider": "Not a real option",
                        },
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                loaded = settings_module.SettingsService.load()

            self.assertEqual(
                loaded["providers"]["source_provider"],
                "Google Drive (coming soon)",
            )
            self.assertEqual(
                loaded["providers"]["destination_provider"],
                settings_module.DEFAULT_PROVIDER,
            )

    def test_provider_preferences_are_persisted(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                settings = settings_module.SettingsService.load()
                settings["providers"] = {
                    "source_provider": "Dropbox (coming soon)",
                    "destination_provider": "OneDrive (coming soon)",
                }
                settings_module.SettingsService.save(settings)

                reloaded = settings_module.SettingsService.load()

            self.assertEqual(
                reloaded["providers"]["source_provider"],
                "Dropbox (coming soon)",
            )
            self.assertEqual(
                reloaded["providers"]["destination_provider"],
                "OneDrive (coming soon)",
            )

    def test_folder_pairs_are_normalized_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            settings_file.write_text(
                json.dumps(
                    {
                        "folder_pairs": [
                            {
                                "name": " Accounting ",
                                "local_folder": " C:/local ",
                                "server_folder": " C:/server ",
                            },
                            {
                                "name": "accounting",
                                "local_folder": "C:/duplicate",
                                "server_folder": "C:/duplicate-server",
                            },
                            {"name": "Incomplete", "local_folder": "C:/only-local"},
                            "not a pair",
                        ]
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                loaded = settings_module.SettingsService.load()

            self.assertEqual(
                loaded["folder_pairs"],
                [
                    {
                        "name": "Accounting",
                        "local_folder": "C:/local",
                        "server_folder": "C:/server",
                    }
                ],
            )

    def test_legacy_recent_pairs_migrate_only_when_folder_pairs_are_missing(self):
        legacy_pair = {
            "name": "Accounting",
            "local_folder": "C:/local",
            "server_folder": "C:/server",
        }
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                settings_file.write_text(
                    json.dumps({"recent_pairs": [legacy_pair]}),
                    encoding="utf-8",
                )
                migrated = settings_module.SettingsService.load()

                settings_file.write_text(
                    json.dumps({"recent_pairs": [legacy_pair], "folder_pairs": []}),
                    encoding="utf-8",
                )
                explicit_empty = settings_module.SettingsService.load()

            self.assertEqual(migrated["folder_pairs"], [legacy_pair])
            self.assertEqual(explicit_empty["folder_pairs"], [])

    def test_folder_pairs_and_canonical_active_name_are_persisted(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                settings = settings_module.SettingsService.load()
                settings["folder_pairs"] = [
                    {
                        "name": "Accounting – ORs / CTCs / RPTs",
                        "local_folder": "C:/local/2026 ORs CTCs RPT",
                        "server_folder": "//server/accounting/ORs CTCs RPTs",
                    }
                ]
                settings["active_folder_pair"] = "accounting – ors / ctcs / rpts"
                settings_module.SettingsService.save(settings)
                reloaded = settings_module.SettingsService.load()

            self.assertEqual(
                reloaded["active_folder_pair"],
                "Accounting – ORs / CTCs / RPTs",
            )

    def test_invalid_active_folder_pair_is_cleared(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            settings_file.write_text(
                json.dumps(
                    {
                        "folder_pairs": [
                            {
                                "name": "Accounting",
                                "local_folder": "C:/local",
                                "server_folder": "C:/server",
                            }
                        ],
                        "active_folder_pair": "Missing Pair",
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                loaded = settings_module.SettingsService.load()

            self.assertEqual(loaded["active_folder_pair"], "")
