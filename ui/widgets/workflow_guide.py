import tkinter as tk
from tkinter import ttk

from models.compare_status import CompareStatus
from models.comparison_decision import ConfidenceLevel
from ui.theme import AMBER, GREEN, MUTED, configure_workflow_styles


class WorkflowGuide(ttk.Frame):
    """Displays and styles the next safe action in the main workflow."""

    NEXT_COLOR = GREEN
    COPY_COLOR = AMBER
    COMPLETE_COLOR = GREEN
    BUSY_COLOR = MUTED

    def __init__(self, parent) -> None:
        super().__init__(parent, padding=(16, 12), style="Workflow.TFrame")
        self.hint_var = tk.StringVar(value="")
        ttk.Label(
            self, text="WORKFLOW GUIDE", style="WorkflowTitle.TLabel",
        ).pack(anchor="w")
        self.hint_label = ttk.Label(
            self, textvariable=self.hint_var, style="Workflow.TLabel",
            font=("Segoe UI", 10, "bold"), justify="left", wraplength=700,
        )
        self.hint_label.pack(fill="x", pady=(4, 0))
        self.bind("<Configure>", self._resize_hint)
        self._controls = None

    def _resize_hint(self, event) -> None:
        self.hint_label.configure(wraplength=max(100, event.width - 32))

    @staticmethod
    def configure_styles(style: ttk.Style) -> None:
        configure_workflow_styles(style)

    def bind_controls(
        self,
        *,
        local_browse_button,
        server_browse_button,
        compare_button,
        local_to_server_button,
        server_to_local_button,
    ) -> None:
        self._controls = {
            "local_browse": local_browse_button,
            "server_browse": server_browse_button,
            "compare": compare_button,
            "local_to_server": local_to_server_button,
            "server_to_local": server_to_local_button,
        }

    def show_progress(self, text: str) -> None:
        self._reset_styles()
        self._set_hint(text, self.BUSY_COLOR)

    def refresh(
        self,
        *,
        local_folder: str,
        server_folder: str,
        comparison_completed: bool,
        results,
        local_ready: bool | None = None,
        server_ready: bool | None = None,
        local_setup_hint: str = "choose the Local folder",
        server_setup_hint: str = "choose the Server folder",
        local_to_server_available: bool | None = None,
        server_to_local_available: bool | None = None,
    ) -> None:
        self._reset_styles()
        controls = self._require_controls()
        if local_ready is None:
            local_ready = bool(local_folder.strip())
        if server_ready is None:
            server_ready = bool(server_folder.strip())
        if not local_ready:
            if str(controls["local_browse"].cget("state")) != "disabled":
                controls["local_browse"].configure(style="GuideNext.TButton")
            self._set_hint(f"Next: {local_setup_hint}.", self.NEXT_COLOR)
            return
        if not server_ready:
            if str(controls["server_browse"].cget("state")) != "disabled":
                controls["server_browse"].configure(style="GuideNext.TButton")
            self._set_hint(f"Next: {server_setup_hint}.", self.NEXT_COLOR)
            return
        if not comparison_completed:
            controls["compare"].configure(style="GuideNext.TButton")
            self._set_hint("Next: compare the selected folders.", self.NEXT_COLOR)
            return

        status_local_to_server_ready = any(
            result.status in {CompareStatus.LOCAL_NEWER, CompareStatus.LOCAL_ONLY}
            for result in results
        )
        status_server_to_local_ready = any(
            result.status in {CompareStatus.SERVER_NEWER, CompareStatus.SERVER_ONLY}
            for result in results
        )
        local_to_server_ready = (
            status_local_to_server_ready
            if local_to_server_available is None
            else local_to_server_available
        )
        server_to_local_ready = (
            status_server_to_local_ready
            if server_to_local_available is None
            else server_to_local_available
        )
        if local_to_server_ready:
            controls["local_to_server"].configure(style="GuideCopy.TButton")
        if server_to_local_ready:
            controls["server_to_local"].configure(style="GuideCopy.TButton")

        if local_to_server_ready and server_to_local_ready:
            hint = "Next: review the results, then choose a highlighted copy direction."
        elif local_to_server_ready:
            hint = "Next: review the results, then copy eligible Local files to Server."
        elif server_to_local_ready:
            hint = "Next: review the results, then copy eligible Server files to Local."
        elif status_local_to_server_ready or status_server_to_local_ready:
            self._set_hint(
                "No safe copy action is available for the selected destination provider.",
                self.COPY_COLOR,
            )
            return
        elif any(
            result.status == CompareStatus.NEEDS_REVIEW
            or getattr(getattr(result, "decision", None), "confidence", None) == ConfidenceLevel.LOW
            for result in results
        ):
            self._set_hint("Next: review files needing attention before choosing a copy action.", self.COPY_COLOR)
            return
        else:
            self._set_hint("Folders match; no copy action is needed.", self.COMPLETE_COLOR)
            return
        self._set_hint(hint, self.COPY_COLOR)

    def _reset_styles(self) -> None:
        controls = self._require_controls()
        controls["local_browse"].configure(style="UtilityNeutral.TButton")
        controls["server_browse"].configure(style="UtilityNeutral.TButton")
        controls["compare"].configure(style="MediumNeutral.TButton")
        controls["local_to_server"].configure(style="PrimaryNeutral.TButton")
        controls["server_to_local"].configure(style="PrimaryNeutral.TButton")

    def _set_hint(self, text: str, color: str) -> None:
        self.hint_var.set(text)
        self.hint_label.configure(foreground=color)

    def _require_controls(self):
        if self._controls is None:
            raise RuntimeError("Workflow guide controls have not been configured.")
        return self._controls
