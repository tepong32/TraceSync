import gc
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from ui.dialogs.google_drive_setup_dialog import GoogleDriveSetupDialog
from ui.main_window import MainWindow


class GoogleDialogTests(unittest.TestCase):
    def test_shared_dialog_labels_scope_and_saved_pair_editing(self):
        gc.collect()
        root = tk.Tk();root.withdraw()
        self.addCleanup(root.destroy)
        service = Mock();service.saved_pairs.return_value=[]
        dialog = GoogleDriveSetupDialog(root,service)
        self.addCleanup(dialog.destroy)
        self.assertIn("Google Drive",dialog.title())
        self.assertEqual(dialog.provider_name,"Google Drive")
        self.assertIn("disabled",dialog.use_button.state())
        labels=[]
        def visit(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "TLabel":
                    labels.append(str(child.cget("text")))
                visit(child)
        visit(dialog)
        self.assertTrue(any("reading all Drive files" in text for text in labels))
        root.deiconify()
        dialog.deiconify()
        dialog.geometry("640x580")
        root.update()
        for widget in (dialog.save_button, dialog.use_button, dialog.close_button,
                       dialog.edit_button, dialog.delete_button, dialog.cancel_edit_button):
            bottom = widget.winfo_rooty() - dialog.winfo_rooty() + widget.winfo_height()
            self.assertLessEqual(bottom, dialog.winfo_height())

    def test_main_window_google_activation_is_provider_neutral_and_transient(self):
        settings={"folder_pairs":[],"providers":{},"ignore_patterns":[]}
        with patch("ui.main_window.SettingsService.load",return_value=settings), \
                patch("ui.main_window.SettingsService.save") as save:
            window=MainWindow();window.withdraw();self.addCleanup(window.destroy)
            provider=Mock(folder_name="Synthetic folder")
            pair={"name":"Google","local_folder":"C:/disposable",
                  "server_endpoint":{"provider":"google_drive","account_name":"synthetic@example.invalid"}}
            with patch("ui.main_window.GoogleDriveSetupDialog") as setup,patch.object(window,"wait_window"):
                setup.return_value.selected_connection=(pair,provider)
                window.open_google_drive_setup()
            self.assertIs(window._cloud_connection[1],provider)
            self.assertEqual(window.server_var.get(),"Google Drive: Synthetic folder (synthetic@example.invalid)")
            self.assertFalse(window.comparison_completed)
            self.assertNotIn("Google Drive:",str(save.call_args_list))

    def test_copy_controls_and_guide_use_eligible_preview_not_raw_difference_status(self):
        from models.compare_status import CompareStatus
        from types import SimpleNamespace
        from models.sync_direction import SyncDirection
        settings={"folder_pairs":[],"providers":{},"ignore_patterns":[]}
        with patch("ui.main_window.SettingsService.load",return_value=settings),patch("ui.main_window.SettingsService.save"):
            window=MainWindow();window.withdraw();self.addCleanup(window.destroy)
            window._applying_cloud=True
            window.local_var.set("C:/disposable");window.server_var.set("Google Drive: Synthetic")
            window._applying_cloud=False
            window._cloud_connection=({},Mock())
            window.results=[SimpleNamespace(status=CompareStatus.LOCAL_ONLY)]
            window.comparison_completed=True
            def preview(results,direction):
                return SimpleNamespace(items=[object()] if direction is SyncDirection.SERVER_TO_LOCAL else [])
            with patch.object(window.sync_service,"create_preview",side_effect=preview):
                window._set_sync_buttons(True)
                window._refresh_workflow_guidance()
            self.assertIn("disabled",window.local_to_server_button.state())
            self.assertNotIn("disabled",window.server_to_local_button.state())
            self.assertIn("Server files to Local",window.workflow_hint_var.get())
