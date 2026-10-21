import gc
import tkinter as tk
import unittest

from models.sync_history import SyncFileOutcome, SyncFileOutcomeRecord
from models.sync_job import SyncJob, SyncJobStatus
from ui.dialogs.sync_summary_dialog import SyncSummaryDialog
from ui.theme import AMBER


class SyncSummaryNotesTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def show(self, outcomes):
        job = SyncJob(total_files=len(outcomes), copied_files=len(outcomes),
                      status=SyncJobStatus.COMPLETED, file_outcomes=outcomes)
        dialog = SyncSummaryDialog(self.root, job)
        self.addCleanup(dialog.destroy)
        self.root.update_idletasks()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        return list(descendants(dialog))

    def test_confirmed_copy_warning_is_visible_in_amber_without_becoming_a_failure(self):
        message = "File copied; preserving its modification time was not confirmed. No retry attempted."
        widgets = self.show([SyncFileOutcomeRecord("empty.txt", "copy", False,
            SyncFileOutcome.COPIED, message=message)])
        text = next(widget for widget in widgets if isinstance(widget, tk.Text))
        self.assertIn(message, text.get("1.0", "end"))
        self.assertIn("empty.txt", text.get("1.0", "end"))
        self.assertEqual(str(text.cget("state")), "disabled")
        self.assertEqual(str(text.cget("foreground")), AMBER)
        labels = [widget.cget("text") for widget in widgets if widget.winfo_class() == "TLabel"]
        self.assertIn("Files copied: 1", labels)
        self.assertIn("Files failed: 0", labels)

    def test_many_copy_notes_are_scrollable_and_not_silently_truncated(self):
        widgets = self.show([SyncFileOutcomeRecord(f"file-{i}.txt", "copy", False,
            SyncFileOutcome.COPIED, message=f"Synthetic note {i}") for i in range(30)])
        text = next(widget for widget in widgets if isinstance(widget, tk.Text))
        self.assertIn("Synthetic note 29", text.get("1.0", "end"))
        self.assertTrue(any(widget.winfo_class() == "TScrollbar" for widget in widgets))
        self.assertEqual(int(text.cget("height")), 6)

    def test_success_without_notes_keeps_the_existing_compact_summary(self):
        widgets = self.show([SyncFileOutcomeRecord("ordinary.txt", "copy", False, SyncFileOutcome.COPIED)])
        self.assertFalse(any(isinstance(widget, tk.Text) for widget in widgets))
