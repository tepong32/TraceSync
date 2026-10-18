import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui.main_window import MainWindow
from models.sync_direction import SyncDirection
from tests.test_onedrive_transfer import Graph
from core.onedrive_provider import OneDriveProvider


class CloudMainWindowTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph = Graph()
        self.provider = OneDriveProvider("drive", "root", "Cloud", lambda: "token", self.graph)
        self.settings = {"folder_pairs": [], "providers": {}, "ignore_patterns": []}
        self.load = patch("ui.main_window.SettingsService.load", return_value=self.settings)
        self.save = patch("ui.main_window.SettingsService.save")
        self.load.start(); self.save.start()
        self.addCleanup(self.load.stop); self.addCleanup(self.save.stop)
        self.window = MainWindow()
        self.addCleanup(self.window.destroy)
        self.window.withdraw()

    def activate(self):
        pair = {"name": "Cloud pair", "local_folder": str(self.root)}
        with patch("ui.main_window.OneDriveSetupDialog") as setup, patch.object(self.window, "wait_window"):
            setup.return_value.selected_connection = (pair, self.provider)
            self.window.open_onedrive_setup()

    def test_cloud_activation_compare_and_cancel_confirmation_never_uploads(self):
        (self.root / "new.txt").write_bytes(b"data")
        self.activate()
        self.window.compare_folders()
        self.assertTrue(self.window.comparison_completed)
        self.assertEqual(len(self.window.results), 1)
        self.assertIs(self.window.sync_service.server_provider, self.provider)
        self.assertNotIn("OneDrive:", str(self.settings))
        with patch("ui.main_window.SyncConfirmationDialog") as confirmation, patch.object(self.window, "wait_window"):
            confirmation.return_value.confirmed = False
            self.window.prepare_sync(SyncDirection.LOCAL_TO_SERVER)
        self.assertFalse(any(call[0] != "GET" for call in self.graph.calls))

    def test_endpoint_changes_and_reopening_setup_clear_cloud_context(self):
        self.activate()
        self.window.comparison_completed = True
        self.window.local_var.set(str(self.root / "other"))
        self.assertIsNone(self.window._cloud_connection)
        self.assertFalse(self.window.comparison_completed)
        self.assertEqual(self.window.server_var.get(), "")
        with patch.object(self.window.sync_service, "create_preview") as preview:
            self.window.prepare_sync(SyncDirection.LOCAL_TO_SERVER)
        preview.assert_not_called()

    def test_readonly_comparison_failure_disables_sync_without_network_writes(self):
        self.activate()
        with patch.object(self.graph, "request", side_effect=OSError("secret")), patch("ui.main_window.messagebox.showerror") as error:
            self.window.compare_folders()
        self.assertFalse(self.window.comparison_completed)
        self.assertIn("disabled", self.window.local_to_server_button.state())
        self.assertNotIn("secret", str(error.call_args))
