import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils import settings


class SettingsStorageTests(unittest.TestCase):
    def test_legacy_load_then_atomic_save_uses_user_directory_without_removing_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/"legacy.json";destination=root/"profile/TraceSync/settings.json"
            original=json.dumps({"local_folder":"C:/synthetic/local", "server_folder":"C:/synthetic/server"})
            legacy.write_text(original)
            with patch.object(settings,"SETTINGS_FILE",destination), \
                    patch.object(settings,"DEFAULT_SETTINGS_FILE",destination), \
                    patch.object(settings,"LEGACY_SETTINGS_FILE",legacy):
                loaded=settings.SettingsService.load()
                self.assertEqual(loaded["server_folder"],"C:/synthetic/server")
                self.assertFalse(destination.exists())
                settings.SettingsService.save(loaded)
                self.assertEqual(settings.SettingsService.load()["local_folder"],"C:/synthetic/local")
            self.assertEqual(legacy.read_text(),original)
            self.assertTrue(destination.is_file())

    def test_existing_user_config_takes_priority_and_test_override_never_adopts_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);legacy=root/"legacy.json";destination=root/"current.json"
            legacy.write_text('{"server_folder":"legacy"}')
            destination.write_text('{"server_folder":"current"}')
            with patch.object(settings,"SETTINGS_FILE",destination),patch.object(settings,"LEGACY_SETTINGS_FILE",legacy):
                self.assertEqual(settings.SettingsService.load()["server_folder"],"current")
                destination.unlink()
                self.assertNotIn("server_folder",settings.SettingsService.load())

    def test_failed_atomic_publication_preserves_previous_config(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"settings.json";target.write_text('{"server_folder":"old"}')
            with patch.object(settings,"SETTINGS_FILE",target), \
                    patch.object(settings.os,"replace",side_effect=PermissionError("synthetic")):
                with self.assertRaises(PermissionError):
                    settings.SettingsService.save({"server_folder":"new"})
            self.assertEqual(json.loads(target.read_text())["server_folder"],"old")
            self.assertEqual(list(Path(directory).glob(".tracesync-settings-*")),[])
