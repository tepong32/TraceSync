import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.onedrive_setup_service import CloudFolder, OneDriveSetupError, OneDriveSetupGateway, OneDriveSetupService
from utils import settings as settings_module


class OneDriveSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name)
        self.file = self.local / "settings.json"
        self.patch = patch.object(settings_module, "SETTINGS_FILE", self.file)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.original = {"folder_pairs": [{"name": "Local", "local_folder": "C:/a", "server_folder": "C:/b"}],
                         "active_folder_pair": "Local", "sftp_profiles": [{"name": "preserved"}]}
        settings_module.SettingsService.save(self.original)
        self.auth = Mock()
        self.auth.connect.return_value = ("secret-access-token", {"refresh_token": "secret-refresh-token"})
        self.gateway = Mock()
        self.gateway.identity.return_value = ("account", "person@example.invalid", "drive")
        self.gateway.folder.side_effect = lambda drive, item="root": CloudFolder(item, "Documents" if item != "root" else "My files")
        self.gateway.children.return_value = [CloudFolder("docs", "Documents")]
        self.service = OneDriveSetupService(self.auth, lambda token: self.gateway)

    def connect_and_save(self):
        self.service.connect()
        self.service.list_folders("root")
        return self.service.save_pair("Personal", str(self.local), "docs")

    def test_connect_browse_save_roundtrip_preserves_local_and_sftp_settings(self):
        pair = self.connect_and_save()
        loaded = settings_module.SettingsService.load()
        self.assertEqual(loaded["folder_pairs"], [*self.original["folder_pairs"], pair])
        self.assertEqual(loaded["active_folder_pair"], "Local")
        self.assertEqual(loaded["sftp_profiles"], self.original["sftp_profiles"])
        self.assertEqual(self.service.saved_pairs(), [pair])
        self.assertNotIn("token", self.file.read_text())
        self.assertNotIn("server_folder", pair)

    def test_cannot_save_or_browse_without_connecting(self):
        before = self.file.read_bytes()
        with self.assertRaises(OneDriveSetupError):
            self.service.save_pair("name", str(self.local), "root")
        with self.assertRaises(OneDriveSetupError):
            self.service.list_folders("root")
        self.assertEqual(before, self.file.read_bytes())

    def test_unseen_folder_and_duplicate_name_rejected(self):
        self.service.connect()
        before = self.file.read_bytes()
        for name, folder in (("local", "root"), ("other", "unseen")):
            with self.subTest(name=name):
                with self.assertRaises(OneDriveSetupError):
                    self.service.save_pair(name, str(self.local), folder)
        self.assertEqual(before, self.file.read_bytes())

    def test_deleted_folder_does_not_save(self):
        self.service.connect()
        self.gateway.folder.side_effect = OneDriveSetupError("Folder no longer exists")
        before = self.file.read_bytes()
        with self.assertRaises(OneDriveSetupError):
            self.service.save_pair("Personal", str(self.local), "root")
        self.assertEqual(before, self.file.read_bytes())

    def test_failed_settings_commit_preserves_previous_pairs_and_cleans_staging(self):
        self.service.connect()
        before = self.file.read_bytes()
        with patch.object(settings_module.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.service.save_pair("Personal", str(self.local), "root")
        self.assertEqual(before, self.file.read_bytes())
        self.assertEqual(list(self.local.glob(".tracesync-settings-*")), [])

    def test_failed_reconnect_clears_old_identity_and_cannot_save(self):
        self.service.connect()
        self.auth.connect.side_effect = RuntimeError("secret-token")
        with self.assertRaises(OneDriveSetupError) as error:
            self.service.connect()
        self.assertNotIn("secret-token", str(error.exception))
        self.assertEqual(self.service.account_id, "")
        with self.assertRaises(OneDriveSetupError):
            self.service.save_pair("Personal", str(self.local), "root")

    def test_cloud_pair_normalization_strips_secrets_and_never_activates_as_local(self):
        pair = self.connect_and_save()
        pair["server_endpoint"]["access_token"] = "secret"
        pair["refresh_token"] = "secret"
        settings_module.SettingsService.save({"folder_pairs": [pair], "active_folder_pair": "Personal"})
        loaded = settings_module.SettingsService.load()
        self.assertEqual(loaded["active_folder_pair"], "")
        self.assertNotIn("secret", self.file.read_text())
        self.assertNotIn("access_token", loaded["folder_pairs"][0]["server_endpoint"])

    def test_malformed_cloud_endpoint_cannot_fall_back_to_local(self):
        pair = {"name": "bad", "local_folder": "C:/a", "server_folder": "C:/b",
                "server_endpoint": {"provider": "unknown"}}
        settings_module.SettingsService.save({"folder_pairs": [pair]})
        self.assertEqual(settings_module.SettingsService.load()["folder_pairs"], [])


class OneDriveGatewayTests(unittest.TestCase):
    def response(self, data, status=200):
        result = Mock(status_code=status)
        result.json.return_value = data
        return result

    def test_pagination_only_lists_owned_folders_and_disables_redirects(self):
        session = Mock()
        session.get.side_effect = [self.response({"value": [
            {"id": "f", "name": "Folder", "folder": {}},
            {"id": "shortcut", "name": "Other drive", "folder": {}, "remoteItem": {}},
            {"id": "file", "name": "File"}],
            "@odata.nextLink": OneDriveSetupGateway.ROOT + "/next"}),
            self.response({"value": [{"id": "f2", "name": "Another", "folder": {}}]})]
        gateway = OneDriveSetupGateway("token", session)
        self.assertEqual([f.id for f in gateway.children("drive", "root")], ["f2", "f"])
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])

    def test_untrusted_paging_link_never_receives_token(self):
        session = Mock()
        session.get.return_value = self.response({"value": [], "@odata.nextLink": "https://evil.invalid/"})
        with self.assertRaises(OneDriveSetupError):
            OneDriveSetupGateway("token", session).children("drive", "root")
        self.assertEqual(session.get.call_count, 1)

    def test_cyclic_paging_fails_without_looping(self):
        session = Mock()
        session.get.return_value = self.response({"value": [], "@odata.nextLink": OneDriveSetupGateway.ROOT + "/loop"})
        with self.assertRaises(OneDriveSetupError):
            OneDriveSetupGateway("token", session).children("drive", "root")
        self.assertEqual(session.get.call_count, 2)

    def test_reconnect_message_and_network_errors_do_not_leak_secrets(self):
        for status in (401, 403, 302):
            with self.subTest(status=status):
                session = Mock()
                session.get.return_value = self.response({"error": "secret"}, status)
                with self.assertRaises(OneDriveSetupError) as error:
                    OneDriveSetupGateway("secret", session).folder("drive")
                self.assertNotIn("secret", str(error.exception))
        session.get.side_effect = RuntimeError("secret")
        with self.assertRaises(OneDriveSetupError) as error:
            OneDriveSetupGateway("secret", session).folder("drive")
        self.assertNotIn("secret", str(error.exception))

    def test_business_account_is_rejected(self):
        session = Mock()
        session.get.side_effect = [self.response({"id": "account", "displayName": "Person"}),
                                   self.response({"id": "drive", "driveType": "business"})]
        with self.assertRaises(OneDriveSetupError):
            OneDriveSetupGateway("token", session).identity()
