import gc
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import patch

from models.compare_status import CompareStatus
from models.comparison_decision import ConfidenceLevel
from ui.main_window import MainWindow
from ui.theme import AMBER, GREEN, GREEN_PALE


class MaterialWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.enterContext(patch.dict(os.environ, {"LOCALAPPDATA": self.workspace.name}))
        self.enterContext(patch("utils.settings.SETTINGS_FILE", Path(self.workspace.name) / "settings.json"))
        try:
            self.window = MainWindow()
        except tk.TclError as exc:
            self.skipTest(f"Tk unavailable: {exc}")
        self.window.withdraw()
        self.addCleanup(self._close)
        self.style = ttk.Style(self.window)

    def _close(self):
        self.window.update_idletasks()
        self.window.destroy()
        self.window = None
        gc.collect()

    def test_next_step_is_green_but_disabled_state_is_not(self):
        self.assertEqual(self.style.theme_use(), "clam")
        self.assertEqual(self.window.local_browse_button.cget("style"), "GuideNext.TButton")
        self.assertEqual(self.style.lookup("GuideNext.TButton", "background"), GREEN)
        self.assertNotEqual(self.style.lookup("GuideNext.TButton", "background", ("disabled",)), GREEN)
        self.assertEqual(self.style.lookup("Workflow.TFrame", "background"), GREEN_PALE)

    def test_both_directions_remain_amber_and_require_review(self):
        self.window.local_var.set("C:/Local")
        self.window.server_var.set("D:/Server")
        self.window.results = [SimpleNamespace(status=CompareStatus.LOCAL_ONLY),
                               SimpleNamespace(status=CompareStatus.SERVER_ONLY)]
        self.window.comparison_completed = True
        self.window._refresh_workflow_guidance()
        for button in (self.window.local_to_server_button, self.window.server_to_local_button):
            self.assertEqual(button.cget("style"), "GuideCopy.TButton")
        self.assertEqual(self.style.lookup("GuideCopy.TButton", "foreground"), AMBER)
        self.assertIn("review", self.window.workflow_hint_var.get())
        self.assertNotEqual(self.window.compare_button.cget("style"), "GuideNext.TButton")

    def test_attention_only_results_never_claim_folders_match(self):
        self.window.workflow_guide.refresh(
            local_folder="Local", server_folder="Server", comparison_completed=True,
            results=[SimpleNamespace(status=CompareStatus.SAME,
                     decision=SimpleNamespace(confidence=ConfidenceLevel.LOW))],
        )
        self.assertIn("needing attention", self.window.workflow_hint_var.get())
        self.assertEqual(str(self.window.workflow_guide.hint_label.cget("foreground")), AMBER)

    def test_busy_state_removes_next_step_highlight(self):
        self.window.workflow_guide.show_progress("Comparing...")
        self.assertEqual(self.window.local_browse_button.cget("style"), "UtilityNeutral.TButton")
        self.assertEqual(self.window.workflow_hint_var.get(), "Comparing...")

    def test_unready_side_does_not_highlight_disabled_browse(self):
        self.window.local_browse_button.configure(state="disabled")
        self.window.workflow_guide.refresh(
            local_folder="", server_folder="Server", comparison_completed=False, results=[],
            local_ready=False, local_setup_hint="choose the endpoint",
        )
        self.assertEqual(self.window.local_browse_button.cget("style"), "UtilityNeutral.TButton")
        self.assertIn("endpoint", self.window.workflow_hint_var.get())

    def test_attention_filter_and_row_retain_warning_priority(self):
        self.window.results = [SimpleNamespace(status=CompareStatus.SAME,
            relative_path="review.xlsx", decision=SimpleNamespace(confidence=ConfidenceLevel.LOW))]
        self.window.apply_filter(self.window._needs_attention_filter_key)
        button = self.window.filter_buttons[self.window._needs_attention_filter_key]
        self.assertEqual(button.cget("style"), "ActiveWarningFilter.TButton")
        row = self.window.tree.get_children()[0]
        self.assertEqual(self.window.tree.item(row, "tags")[0], "NEEDS_ATTENTION")

    def test_provider_toggle_stays_visible_at_minimum_size(self):
        self.window.geometry("850x600")
        self.window.deiconify()
        self.window.toggle_provider_section()
        self.window.update()
        for button in (self.window.provider_toggle_button, self.window.compare_button,
                       self.window.local_to_server_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 self.window.winfo_rooty() + self.window.winfo_height())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 self.window.winfo_rootx() + self.window.winfo_width())
        self.assertLess(self.window.provider_section.canvas.winfo_height(),
                        self.window.provider_section.content.winfo_reqheight())

    def test_keyboard_focus_reveals_lower_provider_controls(self):
        self.window.deiconify()
        self.window.toggle_provider_section()
        self.window.update()
        panel = self.window.provider_section
        panel._reveal_focus(SimpleNamespace(widget=self.window.destination_provider_combo))
        self.window.update_idletasks()
        button = self.window.destination_provider_combo
        self.assertGreaterEqual(button.winfo_rooty(), panel.canvas.winfo_rooty())
        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                             panel.canvas.winfo_rooty() + panel.canvas.winfo_height())

    def test_history_recovery_controls_and_counts_survive_compact_layout(self):
        from tests.test_sync_history_dialog import make_record
        from ui.dialogs.sync_history_details_dialog import SyncHistoryDetailsDialog
        from ui.dialogs.sync_history_dialog import SyncHistoryDialog
        from unittest.mock import Mock
        self.window.deiconify()
        service = Mock()
        service.list_records.return_value = SimpleNamespace(records=[], unreadable_files=[])
        for kind in ("details", "history"):
            if kind == "details":
                dialog = SyncHistoryDetailsDialog(self.window, make_record(), service)
                button = dialog.restore_button
                self.assertTrue(dialog.tk.getvar(str(dialog.counts_var)))
                dialog.geometry("760x480")
            else:
                dialog = SyncHistoryDialog(self.window, service)
                button = dialog.details_button
                dialog.geometry("800x420")
            try:
                dialog.update()
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                     dialog.winfo_rooty() + dialog.winfo_height())
            finally:
                dialog.destroy()
