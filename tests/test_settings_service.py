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
