import tkinter as tk
from tkinter import ttk

from models.compare_status import CompareStatus


class WorkflowGuide(ttk.Frame):
    """Displays and styles the next safe action in the main workflow."""

    NEXT_COLOR = "#1d4ed8"
    COPY_COLOR = "#92400e"
    COMPLETE_COLOR = "#166534"
    BUSY_COLOR = "#4b5563"

    def __init__(self, parent) -> None:
        super().__init__(parent, padding=(10, 0, 10, 8))
        self.hint_var = tk.StringVar(value="")
        ttk.Label(
            self,
            text="Workflow guide:",
            foreground="#4b5563",
        ).pack(side="left")
        self.hint_label = ttk.Label(
            self,
            textvariable=self.hint_var,
            font=("Segoe UI", 9, "bold"),
            foreground=self.NEXT_COLOR,
        )
        self.hint_label.pack(side="left", padx=(6, 0))
        self._controls = None

    @staticmethod
    def configure_styles(style: ttk.Style) -> None:
        style.configure(
            "GuideNext.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 7),
            background="#dbeafe",
            foreground="#1e3a8a",
        )
        style.map(
            "GuideNext.TButton",
            foreground=[
                ("disabled", "#6b7280"),
                ("pressed", "#172554"),
                ("active", "#172554"),
            ],
            background=[
                ("disabled", "#eef1f6"),
                ("pressed", "#bfdbfe"),
                ("active", "#eff6ff"),
                ("!disabled", "#dbeafe"),
            ],
        )
        style.configure(
            "GuideCopy.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 8),
            background="#fef3c7",
            foreground="#78350f",
        )
        style.map(
            "GuideCopy.TButton",
            foreground=[
                ("disabled", "#6b7280"),
                ("pressed", "#451a03"),
                ("active", "#451a03"),
            ],
            background=[
                ("disabled", "#eef1f6"),
                ("pressed", "#fde68a"),
                ("active", "#fffbeb"),
                ("!disabled", "#fef3c7"),
            ],
        )

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
    ) -> None:
        self._reset_styles()
        controls = self._require_controls()
        if not local_folder.strip():
            controls["local_browse"].configure(style="GuideNext.TButton")
            self._set_hint("Next: choose the Local folder.", self.NEXT_COLOR)
            return
        if not server_folder.strip():
            controls["server_browse"].configure(style="GuideNext.TButton")
            self._set_hint("Next: choose the Server folder.", self.NEXT_COLOR)
            return
        if not comparison_completed:
            controls["compare"].configure(style="GuideNext.TButton")
            self._set_hint("Next: compare the selected folders.", self.NEXT_COLOR)
            return

        local_to_server_ready = any(
            result.status in {CompareStatus.LOCAL_NEWER, CompareStatus.LOCAL_ONLY}
            for result in results
        )
        server_to_local_ready = any(
            result.status in {CompareStatus.SERVER_NEWER, CompareStatus.SERVER_ONLY}
            for result in results
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
