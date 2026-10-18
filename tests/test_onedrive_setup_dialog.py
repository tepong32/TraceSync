import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from core.onedrive_setup_service import CloudFolder
from ui.dialogs.onedrive_setup_dialog import OneDriveSetupDialog
from ui.main_window import MainWindow


class OneDriveSetupDialogTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.service = Mock(account_name="person@example.invalid")
        self.service.saved_pairs.return_value = []
        self.service.connect.return_value = CloudFolder("root", "My files")
        self.service.list_folders.return_value = [CloudFolder("docs", "Documents")]
        self.dialog = OneDriveSetupDialog(self.root, self.service)
        self.addCleanup(self.root.destroy)

    def wait_idle(self):
        end = time.monotonic() + 3
        while self.dialog._busy and time.monotonic() < end:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.dialog._busy)

    def test_setup_navigation_and_save_never_change_main_endpoints(self):
        self.assertIn("disabled", self.dialog.save_button.state())
        self.dialog._connect()
        self.wait_idle()
        self.assertEqual(self.dialog.account.get(), "person@example.invalid")
        self.dialog.folders.selection_set(0)
        self.dialog._open()
        self.wait_idle()
        self.assertEqual(self.dialog._path[-1].id, "docs")
        self.dialog.name.set("Personal")
        self.dialog.local.set("C:/Documents")
        self.service.save_pair.return_value = {"name": "Personal"}
        self.dialog._save()
        self.wait_idle()
        self.service.save_pair.assert_called_once_with("Personal", "C:/Documents", "docs")
        self.assertIn("not enabled", self.dialog.status.get())

    def test_close_before_worker_result_does_not_apply_result(self):
        import threading
        ready = threading.Event()
        done = threading.Event()
        def connect():
            ready.wait(2)
            done.set()
            return CloudFolder("root", "My files")
        self.service.connect.side_effect = connect
        self.dialog._connect()
        self.dialog._close()
        ready.set()
        self.assertTrue(done.wait(2))
        self.root.update()
        self.service.save_pair.assert_not_called()

    def test_local_selector_ignores_cloud_pair(self):
        window = Mock()
        window.settings = {"folder_pairs": [{"name": "cloud", "server_endpoint": {"provider": "onedrive"}},
                                             {"name": "local", "local_folder": "a", "server_folder": "b"}]}
        self.assertEqual(MainWindow._local_folder_pairs(window), [window.settings["folder_pairs"][1]])

    def test_setup_actions_fit_minimum_window(self):
        self.dialog.geometry("640x580")
        self.root.update()
        for widget in (self.dialog.connect_button, self.dialog.save_button, self.dialog.close_button):
            bottom = widget.winfo_rooty() - self.dialog.winfo_rooty() + widget.winfo_height()
            self.assertLessEqual(bottom, self.dialog.winfo_height())

    def test_local_manager_keeps_cloud_definitions_and_reserves_their_names(self):
        window = Mock()
        cloud = {"name": "Personal", "server_endpoint": {"provider": "onedrive"}}
        local = {"name": "Office", "local_folder": "a", "server_folder": "b"}
        window.settings = {"folder_pairs": [cloud, local]}
        window._local_folder_pairs.return_value = [local]
        window.local_var.get.return_value = "a"
        window.server_var.get.return_value = "b"
        with patch("ui.main_window.FolderPairManagerDialog") as factory, patch("ui.main_window.SettingsService.save"):
            factory.return_value.confirmed = True
            factory.return_value.pairs = [dict(local, name="Renamed")]
            MainWindow._show_folder_pair_manager(window, start_new=False)
        self.assertEqual(factory.call_args.kwargs["reserved_names"], ["Personal"])
        self.assertEqual(window.settings["folder_pairs"], [dict(local, name="Renamed"), cloud])
