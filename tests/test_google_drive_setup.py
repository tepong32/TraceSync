import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.google_drive_setup_service import GoogleDriveSetupService, GoogleSetupError
from utils import settings


class GoogleSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(settings, "SETTINGS_FILE", self.root / "settings.json")
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.local_pair = {"name": "Local", "local_folder": "C:/a", "server_folder": "C:/b"}
        settings.SettingsService.save({"folder_pairs": [self.local_pair], "active_folder_pair": "Local"})
        self.api = Mock()
        self.api.files.return_value.get.side_effect = self.folder
        self.api.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "docs", "name": "Documents"}]}
        self.connection = SimpleNamespace(account_id="account-a", account_name="synthetic@example.invalid",
            credentials=object(), service=self.api)
        self.auth = Mock()
        self.auth.connect.return_value = self.connection
        self.auth.acquire_for_account.return_value = self.connection
        self.service = GoogleDriveSetupService(self.auth)

    def folder(self, **kwargs):
        item = {"id": "root-id" if kwargs["fileId"] == "root" else kwargs["fileId"],
            "name": "Documents", "mimeType": "application/vnd.google-apps.folder",
            "capabilities": {"canListChildren": True}}
        return Mock(execute=Mock(return_value=item))

    def saved(self):
        root = self.service.connect()
        self.service.list_folders(root.id)
        return self.service.save_pair("Google", str(self.root), "docs")

    def test_connect_choose_save_and_restore_exact_account(self):
        pair = self.saved()
        self.assertEqual(self.service.saved_pairs(), [pair])
        loaded = settings.SettingsService.load()
        self.assertEqual(loaded["folder_pairs"][0], self.local_pair)
        self.assertEqual(loaded["active_folder_pair"], "Local")
        self.assertNotIn("credentials", (self.root / "settings.json").read_text())
        restored, provider = self.service.prepare_comparison("Google")
        self.auth.acquire_for_account.assert_called_once_with("account-a")
        self.assertEqual(restored, pair)
        self.assertEqual(provider.folder_id, "docs")
        self.assertTrue(provider.create_only)

    def test_reconnect_and_wrong_account_fail_closed_without_settings_changes(self):
        pair = self.saved()
        original = (self.root / "settings.json").read_bytes()
        self.service.restore_pair(pair["name"], interactive=True)
        self.auth.connect.assert_called_with(expected_account="account-a")
        self.connection.account_id = "other"
        with self.assertRaises(GoogleSetupError):
            self.service.restore_pair(pair["name"])
        self.assertIsNone(self.service._connection)
        self.assertEqual((self.root / "settings.json").read_bytes(), original)

    def test_edit_delete_are_offline_and_never_remove_saved_signin_or_files(self):
        pair = self.saved()
        self.service._clear()
        updated = self.service.edit_pair(pair, "Renamed", str(self.root))
        self.assertEqual(updated["server_endpoint"], pair["server_endpoint"])
        self.service.delete_pair(updated)
        self.assertEqual(self.service.saved_pairs(), [])
        self.auth.forget_account.assert_not_called()
        self.assertTrue(self.root.is_dir())

    def test_stale_or_duplicate_edits_and_foreign_folder_selection_rejected(self):
        pair = self.saved()
        for name in ("Local", " "):
            with self.assertRaises(GoogleSetupError):
                self.service.edit_pair(pair, name, str(self.root))
        updated = self.service.edit_pair(pair, "Renamed", str(self.root))
        with self.assertRaises(GoogleSetupError):
            self.service.delete_pair(pair)
        self.connection.account_id = "other"
        self.service.account_id = "other"
        with self.assertRaises(GoogleSetupError):
            self.service.edit_pair(updated, "New", str(self.root), "docs")

    def test_disconnect_is_account_scoped_and_keeps_pair(self):
        pair = self.saved()
        self.service.disconnect_pair("Google")
        self.auth.forget_account.assert_called_once_with("account-a")
        self.assertEqual(self.service.saved_pairs(), [pair])

    def test_repeated_pages_or_listing_failure_does_not_save_partial_selection(self):
        root = self.service.connect()
        self.api.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "partial", "name": "Partial"}], "nextPageToken": "repeat"}
        with self.assertRaises(GoogleSetupError):
            self.service.list_folders(root.id)
        self.assertNotIn("partial", self.service._known)
        self.assertEqual(self.service.saved_pairs(), [])

    def test_missing_local_path_can_be_repaired_offline(self):
        pair = self.saved()
        new = self.service.edit_pair(pair, "Google", str(self.root))
        with self.assertRaises(GoogleSetupError):
            self.service.edit_pair(new, "Google", str(self.root / "missing"))

    def test_errors_do_not_expose_sdk_response_or_save_settings(self):
        self.auth.connect.side_effect = RuntimeError("secret-token-response")
        before = (self.root / "settings.json").read_bytes()
        with self.assertRaises(GoogleSetupError) as caught:
            self.service.connect()
        self.assertNotIn("secret-token-response", str(caught.exception))
        self.assertEqual((self.root / "settings.json").read_bytes(), before)

    def test_relative_local_folder_is_persisted_as_a_stable_absolute_path(self):
        import os
        original=os.getcwd()
        try:
            os.chdir(self.root)
            self.service.connect()
            pair=self.service.save_pair("Relative",".","root-id")
        finally:
            os.chdir(original)
        self.assertEqual(Path(pair["local_folder"]),self.root.resolve())
