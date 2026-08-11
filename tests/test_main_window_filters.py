import unittest
import tkinter as tk

from core.comparison_confidence import build_decision
from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from models.file_record import FileRecord
from ui.main_window import MainWindow


class MainWindowNeedsAttentionTests(unittest.TestCase):
    def setUp(self):
        try:
            self.window = MainWindow()
            self.window.withdraw()
        except tk.TclError as exc:
            self.skipTest(f"Tkinter unavailable for UI tests: {exc}")

    def tearDown(self):
        try:
            self.window.destroy()
        except Exception:
            pass

    @staticmethod
    def make_result(
        status: CompareStatus,
        local_record,
        server_record,
        relative_path: str,
    ) -> ComparisonResult:
        result = ComparisonResult(
            relative_path=relative_path,
            status=status,
            local_record=local_record,
            server_record=server_record,
        )
        result.decision = build_decision(result)
        return result

    def test_filter_button_shows_needs_attention_count(self):
        local_only = FileRecord("C:/local/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 128)
        server_only = FileRecord("C:/server/plan.xlsx", "plan.xlsx", 1_000.0, 128)
        mismatched_sizes = self.make_result(
            CompareStatus.SAME,
            local_only,
            FileRecord("C:/server/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 129),
            "dpcr 2026.xlsx",
        )
        local_newer = self.make_result(
            CompareStatus.LOCAL_ONLY,
            server_only,
            None,
            "plan.xlsx",
        )

        self.window.results = [mismatched_sizes, local_newer]
        self.window._refresh_filter_labels()

        needs_attention_button = self.window.filter_buttons[self.window._needs_attention_filter_key]
        self.assertEqual(needs_attention_button.cget("text"), "Needs Attention (1)")

        all_button = self.window.filter_buttons[None]
        self.assertEqual(all_button.cget("text"), "All (2)")

    def test_filter_shows_only_needs_attention_rows(self):
        mismatched_sizes = self.make_result(
            CompareStatus.SAME,
            FileRecord("C:/local/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 128),
            FileRecord("C:/server/dpcr 2026.xlsx", "dpcr 2026.xlsx", 1_000.0, 129),
            "dpcr 2026.xlsx",
        )
        local_newer = self.make_result(
            CompareStatus.LOCAL_ONLY,
            FileRecord("C:/local/plan.xlsx", "plan.xlsx", 1_500.0, 64),
            None,
            "plan.xlsx",
        )

        self.window.results = [mismatched_sizes, local_newer]
        self.window.apply_filter(self.window._needs_attention_filter_key)

        self.assertEqual(len(self.window.visible_results), 1)
        self.assertEqual(self.window.visible_results[0].relative_path, "dpcr 2026.xlsx")
        self.assertIn(
            "NEEDS_ATTENTION",
            self.window.tree.item(self.window.tree.get_children()[0], "tags"),
        )
        self.assertEqual(self.window.status_var.get(), "Showing 1 file needing attention")


if __name__ == "__main__":
    unittest.main()
