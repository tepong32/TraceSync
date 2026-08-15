import unittest
import tkinter as tk

from models.compare_status import CompareStatus
from models.sync_direction import SyncDirection
from models.sync_preview import SyncOperation, SyncPreview, SyncPreviewItem
from ui.dialogs.sync_confirmation_dialog import SyncConfirmationDialog


class SyncConfirmationDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tkinter unavailable for UI tests: {exc}")

    def tearDown(self):
        try:
            for child in self.root.winfo_children():
                child.destroy()
        finally:
            self.root.destroy()

    @staticmethod
    def make_item(relative_path: str) -> SyncPreviewItem:
        return SyncPreviewItem(
            relative_path=relative_path,
            source="C:/src",
            destination="C:/dst",
            direction=SyncDirection.LOCAL_TO_SERVER,
            comparison_status=CompareStatus.LOCAL_NEWER,
            operation=SyncOperation.COPY,
            overwrite=False,
            reason="",
        )

    def test_confirmation_defaults_select_all(self):
        preview = SyncPreview(
            direction=SyncDirection.LOCAL_TO_SERVER,
            items=(
                self.make_item("alpha.txt"),
                self.make_item("beta.txt"),
                self.make_item("gamma.txt"),
            ),
        )
        dialog = SyncConfirmationDialog(self.root, preview)
        try:
            self.assertEqual(dialog.selected_item_count, 3)
            self.assertEqual(dialog._selection_var.get(), "3 files selected")
        finally:
            dialog.destroy()

    def test_selection_updates_with_clear(self):
        preview = SyncPreview(
            direction=SyncDirection.LOCAL_TO_SERVER,
            items=(self.make_item("alpha.txt"), self.make_item("beta.txt")),
        )
        dialog = SyncConfirmationDialog(self.root, preview)
        try:
            dialog._clear_selection()
            self.assertEqual(dialog.selected_item_count, 0)
            self.assertEqual(dialog._selection_var.get(), "No files selected")
            self.assertEqual(dialog.get_selected_items(), ())
        finally:
            dialog.destroy()

    def test_get_selected_items_matches_tree_selection(self):
        preview = SyncPreview(
            direction=SyncDirection.LOCAL_TO_SERVER,
            items=(self.make_item("alpha.txt"), self.make_item("beta.txt")),
        )
        dialog = SyncConfirmationDialog(self.root, preview)
        try:
            tree = dialog._tree
            assert tree is not None
            tree.selection_remove(*tree.get_children())
            first_row = tree.get_children()[0]
            second_row = tree.get_children()[1]
            tree.selection_add(first_row)
            tree.selection_add(second_row)
            dialog._on_tree_select()
            selected = dialog.get_selected_items()
            self.assertEqual(len(selected), 2)
            self.assertEqual(selected[0].relative_path, "alpha.txt")
            self.assertEqual(selected[1].relative_path, "beta.txt")
        finally:
            dialog.destroy()


class SyncPreviewSelectionTests(unittest.TestCase):
    def test_with_selected_items_filters_preview(self):
        first_item = SyncConfirmationDialogTests.make_item("alpha.txt")
        second_item = SyncConfirmationDialogTests.make_item("beta.txt")
        preview = SyncPreview(
            direction=SyncDirection.LOCAL_TO_SERVER,
            items=(first_item, second_item),
        )
        selected = preview.with_selected_items({"alpha.txt"})

        self.assertEqual(selected.total_files, 1)
        self.assertEqual(selected.items[0].relative_path, "alpha.txt")
        self.assertFalse(selected.warnings)


if __name__ == "__main__":
    unittest.main()
