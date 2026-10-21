import time
import gc
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from core.onedrive_setup_service import CloudFolder
from ui.dialogs.onedrive_setup_dialog import OneDriveSetupDialog
from ui.main_window import MainWindow


class OneDriveSetupDialogTests(unittest.TestCase):
    def setUp(self):
        # Collect prior destroyed Tk fixtures on their owning thread before workers start.
        gc.collect()
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
        self.assertIn("compare before copying", self.dialog.status.get())

    def prepare_saved_pair(self):
        pair = {"name": "Personal", "local_folder": "C:/missing", "server_endpoint": {
            "provider": "onedrive", "account_name": "person", "folder_name": "Documents"}}
        self.service.saved_pairs.return_value = [pair]
        self.dialog._show_saved()
        return pair

    def test_edit_offline_save_and_cancel(self):
        pair = self.prepare_saved_pair()
        self.dialog._edit()
        self.assertIn("disabled", self.dialog.use_button.state())
        self.assertEqual(self.dialog.local.get(), "C:/missing")
        self.dialog.name.set("Changed")
        self.dialog.local.set("C:/repaired")
        updated = dict(pair, name="Changed", local_folder="C:/repaired")
        self.service.edit_pair.return_value = updated
        self.service.saved_pairs.return_value = [updated]
        self.dialog._save()
        self.wait_idle()
        self.service.edit_pair.assert_called_once_with(pair, "Changed", "C:/repaired", None)
        self.assertIsNone(self.dialog._editing)
        self.dialog._edit()
        self.dialog._cancel_edit()
        self.assertIsNone(self.dialog._editing)
        self.assertEqual(self.service.edit_pair.call_count, 1)

    def test_delete_confirmation_cancel_and_success(self):
        pair = self.prepare_saved_pair()
        with patch("ui.dialogs.onedrive_setup_dialog.messagebox.askyesno", return_value=False):
            self.dialog._delete()
        self.service.delete_pair.assert_not_called()
        with patch("ui.dialogs.onedrive_setup_dialog.messagebox.askyesno", return_value=True):
            self.dialog._delete()
        self.wait_idle()
        self.service.delete_pair.assert_called_once_with(pair)
        self.assertIn("Files and saved sign-in are unchanged", self.dialog.status.get())

    def test_failed_edit_preserves_unsaved_fields_and_definition(self):
        from core.onedrive_setup_service import OneDriveSetupError
        self.prepare_saved_pair()
        self.dialog._edit()
        self.dialog.name.set("Unsaved")
        self.service.edit_pair.side_effect = OneDriveSetupError("Settings could not be saved")
        self.dialog._save()
        self.wait_idle()
        self.assertEqual(self.dialog.name.get(), "Unsaved")
        self.assertIsNotNone(self.dialog._editing)
        self.assertFalse(self.dialog._saving)
        self.assertIn("could not be saved", self.dialog.status.get())

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
        self.root.deiconify()
        self.dialog.deiconify()
        self.dialog.geometry("640x580")
        self.root.update()
        for widget in (self.dialog.connect_button, self.dialog.save_button, self.dialog.close_button,
                       self.dialog.reopen_button, self.dialog.reconnect_button, self.dialog.disconnect_button,
                       self.dialog.edit_button, self.dialog.delete_button, self.dialog.cancel_edit_button):
            bottom = widget.winfo_rooty() - self.dialog.winfo_rooty() + widget.winfo_height()
            self.assertLessEqual(bottom, self.dialog.winfo_height())

    def test_reopen_uses_silent_path_and_populates_only_after_verification(self):
        self.dialog.saved_name.set("Personal")
        self.service.restore_pair.return_value = (
            {"name": "Personal", "local_folder": "C:/Saved"}, CloudFolder("docs", "Documents"), [])
        self.dialog._restore()
        self.wait_idle()
        self.service.restore_pair.assert_called_once_with("Personal", interactive=False)
        self.assertEqual(self.dialog.local.get(), "C:/Saved")
        self.assertEqual(self.dialog._path[-1].id, "docs")

    def test_failed_reopen_clears_old_selection_and_disables_save(self):
        from core.onedrive_setup_service import OneDriveSetupError
        self.dialog._path = [CloudFolder("old", "Old account")]
        self.dialog.saved_name.set("Personal")
        self.service.restore_pair.side_effect = OneDriveSetupError("Reconnect required")
        self.dialog._restore()
        self.wait_idle()
        self.assertFalse(self.dialog._path)
        self.assertIn("disabled", self.dialog.save_button.state())
        self.assertIn("Reconnect", self.dialog.status.get())

    def test_disconnect_cancel_keeps_existing_connection(self):
        self.dialog.saved_name.set("Personal")
        self.dialog._path = [CloudFolder("old", "Existing")]
        with patch("ui.dialogs.onedrive_setup_dialog.messagebox.askyesno", return_value=False):
            self.dialog._disconnect()
        self.assertTrue(self.dialog._path)
        self.service.disconnect_pair.assert_not_called()

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
