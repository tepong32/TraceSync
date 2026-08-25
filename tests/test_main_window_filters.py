import unittest
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch

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


class MainWindowProviderSectionTests(unittest.TestCase):
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

    def test_provider_section_is_hidden_by_default(self):
        self.assertEqual(self.window.provider_section.winfo_manager(), "")
        self.assertEqual(
            self.window.provider_toggle_button.cget("text"),
            "Show Provider Options",
        )

    def test_folder_pair_controls_are_present_without_showing_provider_ui(self):
        self.assertIsNotNone(self.window.folder_pair_combo)
        self.assertIsNotNone(self.window.folder_pair_manage_button)
        self.assertIsNotNone(self.window.folder_pair_save_button)
        self.assertEqual(self.window.provider_section.winfo_manager(), "")

    def test_selecting_folder_pair_invalidates_previous_comparison(self):
        self.window.settings["folder_pairs"] = [
            {
                "name": "Accounting",
                "local_folder": r"C:\Local\Accounting",
                "server_folder": r"\\server\Accounting",
            }
        ]
        self.window._refresh_folder_pair_values()
        self.window.results = [object()]
        self.window.visible_results = list(self.window.results)
        self.window.comparison_completed = True
        self.window._set_sync_buttons(True)
        self.window.folder_pair_var.set("Accounting")

        with patch("ui.main_window.SettingsService.save") as save_settings:
            self.window._on_folder_pair_selected()

        self.assertEqual(self.window.local_var.get(), r"C:\Local\Accounting")
        self.assertEqual(self.window.server_var.get(), r"\\server\Accounting")
        self.assertEqual(self.window.results, [])
        self.assertFalse(self.window.comparison_completed)
        self.assertEqual(str(self.window.local_to_server_button.cget("state")), "disabled")
        self.assertEqual(str(self.window.server_to_local_button.cget("state")), "disabled")
        self.assertEqual(self.window.folder_pair_var.get(), "Accounting")
        save_settings.assert_called_once()

    def test_manual_equivalent_paths_select_the_saved_pair(self):
        self.window.settings["folder_pairs"] = [
            {
                "name": "Accounting",
                "local_folder": r"C:\Local\Accounting",
                "server_folder": r"\\server\Accounting",
            }
        ]
        self.window._refresh_folder_pair_values()

        self.window.local_var.set("c:/local/accounting/")
        self.window.server_var.set("//SERVER/ACCOUNTING/")

        self.assertEqual(self.window.folder_pair_var.get(), "Accounting")
        self.assertEqual(self.window.settings["active_folder_pair"], "Accounting")

    def test_manage_and_save_current_open_distinct_manager_modes(self):
        dialog = SimpleNamespace(confirmed=False)
        with (
            patch("ui.main_window.FolderPairManagerDialog", return_value=dialog) as dialog_type,
            patch.object(self.window, "wait_window"),
        ):
            self.window.open_folder_pair_manager()
            manage_call = dialog_type.call_args
            self.window.save_current_folder_pair()
            save_call = dialog_type.call_args

        self.assertFalse(manage_call.kwargs["start_new"])
        self.assertTrue(save_call.kwargs["start_new"])

    def test_results_list_requests_fifteen_visible_rows(self):
        self.assertEqual(int(self.window.tree.cget("height")), 15)

    def test_sync_actions_are_reserved_in_a_bottom_dock(self):
        self.assertEqual(self.window.action_dock.pack_info()["side"], "bottom")
        self.assertIs(self.window.local_to_server_button.master.master, self.window.action_dock)
        self.assertIs(self.window.server_to_local_button.master.master, self.window.action_dock)

    def test_workflow_guide_highlights_the_next_available_step(self):
        self.window.results = []
        self.window.local_var.set("")
        self.window.server_var.set("")

        self.assertEqual(self.window.local_browse_button.cget("style"), "GuideNext.TButton")
        self.assertIn("Local folder", self.window.workflow_hint_var.get())

        self.window.local_var.set("C:/Local")

        self.assertEqual(self.window.server_browse_button.cget("style"), "GuideNext.TButton")
        self.assertIn("Server folder", self.window.workflow_hint_var.get())

        self.window.server_var.set("D:/Server")

        self.assertEqual(self.window.compare_button.cget("style"), "GuideNext.TButton")
        self.assertIn("compare", self.window.workflow_hint_var.get())

    def test_workflow_guide_highlights_available_copy_directions(self):
        self.window.local_var.set("C:/Local")
        self.window.server_var.set("D:/Server")
        self.window.results = [
            SimpleNamespace(status=CompareStatus.LOCAL_ONLY),
            SimpleNamespace(status=CompareStatus.SERVER_NEWER),
        ]
        self.window.comparison_completed = True

        self.window._refresh_workflow_guidance()

        self.assertEqual(self.window.local_to_server_button.cget("style"), "GuideCopy.TButton")
        self.assertEqual(self.window.server_to_local_button.cget("style"), "GuideCopy.TButton")
        self.assertIn("highlighted copy direction", self.window.workflow_hint_var.get())

    def test_primary_workflow_controls_have_hover_help(self):
        tooltip_text = {
            tooltip.widget: tooltip.text
            for tooltip in self.window._tooltips
        }

        self.assertIn(self.window.local_entry, tooltip_text)
        self.assertIn(self.window.server_entry, tooltip_text)
        self.assertIn(self.window.folder_pair_combo, tooltip_text)
        self.assertIn(self.window.folder_pair_manage_button, tooltip_text)
        self.assertIn(self.window.folder_pair_save_button, tooltip_text)
        self.assertIn(self.window.compare_button, tooltip_text)
        self.assertIn(self.window.local_to_server_button, tooltip_text)
        self.assertIn(self.window.server_to_local_button, tooltip_text)
        self.assertIn("does not copy", tooltip_text[self.window.compare_button])
        self.assertTrue(self.window.compare_button.bind("<Enter>"))
        self.assertTrue(self.window.compare_button.bind("<Leave>"))

    def test_provider_section_can_be_shown_and_hidden(self):
        self.window.toggle_provider_section()

        self.assertEqual(self.window.provider_section.winfo_manager(), "pack")
        self.assertEqual(
            self.window.provider_toggle_button.cget("text"),
            "Hide Provider Options",
        )

        self.window.toggle_provider_section()

        self.assertEqual(self.window.provider_section.winfo_manager(), "")
        self.assertEqual(
            self.window.provider_toggle_button.cget("text"),
            "Show Provider Options",
        )


if __name__ == "__main__":
    unittest.main()
