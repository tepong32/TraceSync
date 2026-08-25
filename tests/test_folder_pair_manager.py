import tkinter as tk
import unittest
from unittest.mock import patch

from ui.dialogs.folder_pair_manager_dialog import FolderPairManagerDialog


class FolderPairManagerNamingTests(unittest.TestCase):
    def test_suggest_name_uses_common_folder_name_when_both_match(self):
        self.assertEqual(
            FolderPairManagerDialog._suggest_name(
                r"C:\Users\Tita\2026 ORs CTCs RPT",
                r"\\server\Accounting\2026 ORs CTCs RPT",
            ),
            "2026 ORs CTCs RPT",
        )

    def test_suggest_name_distinguishes_different_folder_names(self):
        self.assertEqual(
            FolderPairManagerDialog._suggest_name(
                r"C:\Users\Tita\Local ORs",
                r"\\server\Accounting\Server ORs",
            ),
            "Local ORs ↔ Server ORs",
        )


class FolderPairManagerDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.dialog = FolderPairManagerDialog(
                self.root,
                [
                    {
                        "name": "Accounting",
                        "local_folder": r"C:\Local\Accounting",
                        "server_folder": r"\\server\Accounting",
                    }
                ],
                current_local=r"C:\Current",
                current_server=r"\\server\Current",
                selected_name="Accounting",
            )
            self.dialog.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tkinter unavailable for UI tests: {exc}")

    def tearDown(self):
        try:
            self.dialog.destroy()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_manage_mode_selects_the_active_pair_for_editing(self):
        self.assertEqual(self.dialog.name_var.get(), "Accounting")
        self.assertEqual(self.dialog.local_var.get(), r"C:\Local\Accounting")
        self.assertEqual(self.dialog._selected_index, 0)

    def test_new_pair_is_added_without_changing_files(self):
        self.dialog._start_new_pair()
        self.dialog.name_var.set("HR")
        self.dialog.local_var.set(r"C:\Local\HR")
        self.dialog.server_var.set(r"\\server\HR")

        self.dialog._save_pair()

        self.assertTrue(self.dialog.confirmed)
        self.assertEqual(self.dialog.pairs[-1]["name"], "HR")
        self.assertEqual(len(self.dialog.pairs), 2)

    def test_duplicate_name_is_rejected_case_insensitively(self):
        self.dialog._start_new_pair()
        self.dialog.name_var.set("accounting")
        self.dialog.local_var.set(r"C:\Other")
        self.dialog.server_var.set(r"\\server\Other")

        with patch(
            "ui.dialogs.folder_pair_manager_dialog.messagebox.showwarning",
        ) as showwarning:
            self.dialog._save_pair()

        self.assertFalse(self.dialog.confirmed)
        self.assertEqual(len(self.dialog.pairs), 1)
        showwarning.assert_called_once()

    def test_browsing_updates_an_untouched_suggested_name(self):
        self.dialog._start_new_pair()
        with patch(
            "ui.dialogs.folder_pair_manager_dialog.filedialog.askdirectory",
            side_effect=[r"C:\Office\Reports", r"\\server\Published Reports"],
        ):
            self.dialog._browse_local()
            self.dialog._browse_server()

        self.assertEqual(self.dialog.name_var.get(), "Reports ↔ Published Reports")


if __name__ == "__main__":
    unittest.main()
