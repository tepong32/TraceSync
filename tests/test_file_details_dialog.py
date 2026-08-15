import unittest
import tkinter as tk

from core.comparison_confidence import build_decision
from models.comparison_result import ComparisonResult
from models.compare_status import CompareStatus
from models.file_record import FileRecord
from ui.dialogs.file_details_dialog import FileDetailsDialog
from ui.utils.formatting import (
    format_decision_confidence,
    format_file_type,
    format_decision_reason,
    format_decision_recommendation,
)


class FileDetailsDialogTests(unittest.TestCase):
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

    def make_result(self, status: CompareStatus, local_record, server_record):
        result = ComparisonResult(
            relative_path="dpcr 2026.xlsx",
            status=status,
            local_record=local_record,
            server_record=server_record,
        )
        result.decision = build_decision(result)
        return result

    def test_file_details_dialog_shows_decision_context_for_normal_confidence(self):
        result = self.make_result(
            CompareStatus.LOCAL_NEWER,
            FileRecord("C:/local/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 128),
            FileRecord("C:/server/dpcr 2026.xlsx", "dpcr 2026.xlsx", 999.0, 128),
        )

        dialog = FileDetailsDialog(self.root, result)
        try:
            self.assertEqual(dialog.file_relative_path_var.get(), "dpcr 2026.xlsx")
            self.assertEqual(dialog.file_status_var.get(), "The Local copy appears more recent.")
            self.assertEqual(dialog.file_type_var.get(), format_file_type("dpcr 2026.xlsx"))
            self.assertEqual(dialog.file_type_var.get(), "Excel Spreadsheet")
            self.assertEqual(dialog.file_recommendation_var.get(), format_decision_recommendation(result.decision.recommendation))
            self.assertEqual(dialog.file_confidence_var.get(), format_decision_confidence(result.decision.confidence))
            self.assertEqual(dialog.file_reason_var.get(), format_decision_reason(result.decision.reason))
            self.assertNotEqual(dialog.file_recommendation_var.get(), "")
        finally:
            dialog.destroy()

    def test_file_details_dialog_shows_decision_context_for_low_confidence(self):
        result = self.make_result(
            CompareStatus.SAME,
            FileRecord("C:/local/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 128),
            FileRecord("C:/server/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 129),
        )

        dialog = FileDetailsDialog(self.root, result)
        try:
            self.assertEqual(dialog.file_confidence_var.get(), format_decision_confidence(result.decision.confidence))
            self.assertIn("timestamps match", dialog.file_reason_var.get())
            self.assertEqual(dialog.file_confidence_var.get(), "Needs attention")
            self.assertEqual(dialog.file_recommendation_var.get(), format_decision_recommendation(result.decision.recommendation))
            self.assertEqual(dialog.file_reason_var.get(), format_decision_reason(result.decision.reason))
        finally:
            dialog.destroy()


if __name__ == "__main__":
    unittest.main()
