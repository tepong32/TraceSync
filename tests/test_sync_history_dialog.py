import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from models.sync_direction import SyncDirection
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncFileOutcomeRecord,
    SyncReasonCode,
    SyncRunCounts,
    SyncRunOutcome,
    SyncRunRecord,
)
from ui.dialogs.sync_history_details_dialog import SyncHistoryDetailsDialog
from ui.dialogs.sync_history_dialog import SyncHistoryDialog


def make_record(*, interrupted: bool = False) -> SyncRunRecord:
    copied = SyncFileOutcomeRecord(
        relative_path="copied.xlsx",
        operation="copy",
        overwrite=False,
        outcome=SyncFileOutcome.COPIED,
    )
    issue = SyncFileOutcomeRecord(
        relative_path="changed.docx",
        operation="overwrite",
        overwrite=True,
        outcome=SyncFileOutcome.UNKNOWN if interrupted else SyncFileOutcome.SKIPPED,
        reason_code=(SyncReasonCode.INTERRUPTED if interrupted else SyncReasonCode.DESTINATION_CHANGED),
        message="The destination could not be safely updated.",
    )
    return SyncRunRecord(
        run_id=str(uuid4()),
        application_version="0.8.5",
        outcome=SyncRunOutcome.INTERRUPTED if interrupted else SyncRunOutcome.COMPLETED_WITH_ISSUES,
        started_at_utc="2026-08-19T01:02:03.000Z",
        finished_at_utc=None if interrupted else "2026-08-19T01:02:04.250Z",
        duration_ms=None if interrupted else 1250,
        direction=SyncDirection.LOCAL_TO_SERVER,
        source=StorageEndpointSnapshot("local", "Local Folder", "C:/source"),
        destination=StorageEndpointSnapshot("local", "Server Folder", "D:/destination"),
        counts=SyncRunCounts(
            planned=2,
            planned_overwrites=1,
            copied=1,
            skipped=0 if interrupted else 1,
            unknown=1 if interrupted else 0,
        ),
        files=(copied, issue),
    )


class SyncHistoryDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tkinter unavailable for UI tests: {exc}")
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.store = JsonSyncHistoryStore(Path(self.workspace.name) / "history" / "runs")
        self.service = SyncHistoryService(self.store)

    def tearDown(self):
        if hasattr(self, "root"):
            try:
                for child in self.root.winfo_children():
                    child.destroy()
            finally:
                self.root.destroy()

    def test_empty_history_has_clear_empty_state(self):
        dialog = SyncHistoryDialog(self.root, self.service)

        self.assertEqual(dialog.history_tree.get_children(), ())
        self.assertIn("No synchronization history", dialog.empty_var.get())
        self.assertEqual(dialog.warning_var.get(), "")

    def test_populated_history_displays_interrupted_run(self):
        record = make_record(interrupted=True)
        self.store.create(record)

        dialog = SyncHistoryDialog(self.root, self.service)

        rows = dialog.history_tree.get_children()
        self.assertEqual(rows, (record.run_id,))
        values = dialog.history_tree.item(rows[0], "values")
        self.assertIn("Interrupted", values)
        self.assertIn("Local", values[1])
        self.assertEqual(str(values[4]), "1")
        self.assertEqual(str(values[5]), "1")

    def test_details_show_run_and_filter_to_issues(self):
        record = make_record()
        dialog = SyncHistoryDetailsDialog(self.root, record)

        self.assertEqual(dialog.run_id_var.get(), record.run_id)
        self.assertEqual(dialog.outcome_var.get(), "Completed with issues")
        self.assertEqual(len(dialog.files_tree.get_children()), 2)

        dialog.issues_only_var.set(True)
        dialog._populate_files()

        rows = dialog.files_tree.get_children()
        self.assertEqual(len(rows), 1)
        values = dialog.files_tree.item(rows[0], "values")
        self.assertEqual(values[0], "changed.docx")
        self.assertEqual(values[2], "Skipped")
        self.assertEqual(values[3], "Destination Changed")

    def test_corrupt_record_warning_does_not_hide_valid_history(self):
        record = make_record()
        self.store.create(record)
        self.store.history_directory.joinpath("corrupt.json").write_text("not json", encoding="utf-8")

        dialog = SyncHistoryDialog(self.root, self.service)

        self.assertEqual(dialog.history_tree.get_children(), (record.run_id,))
        self.assertIn("1 history record", dialog.warning_var.get())
        self.assertIn("Other valid records", dialog.warning_var.get())

    def test_clear_history_requires_confirmation_and_refreshes(self):
        self.store.create(make_record())
        dialog = SyncHistoryDialog(self.root, self.service)

        with patch("ui.dialogs.sync_history_dialog.messagebox.askyesno", return_value=False):
            dialog._clear_history()
        self.assertEqual(len(self.store.list_records().records), 1)

        with patch("ui.dialogs.sync_history_dialog.messagebox.askyesno", return_value=True):
            dialog._clear_history()

        self.assertEqual(self.store.list_records().records, ())
        self.assertIn("cleared", dialog.empty_var.get())


if __name__ == "__main__":
    unittest.main()
