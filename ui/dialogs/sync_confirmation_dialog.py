import tkinter as tk
from tkinter import messagebox, ttk

from models.sync_preview import SyncPreview
from ui.utils.formatting import (
    format_decision_confidence,
    format_decision_reason,
    format_decision_recommendation,
)


class SyncConfirmationDialog(tk.Toplevel):
    """Shows the complete reviewed plan before any irreversible copy starts."""

    def __init__(self, parent, preview: SyncPreview) -> None:
        super().__init__(parent)
        self.confirmed = False
        self._decision_items: dict[str, object] = {}
        self._tree: ttk.Treeview | None = None

        self.title("Confirm Synchronization")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build_ui(preview)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self, preview: SyncPreview) -> None:
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        self._details_var = tk.StringVar(value="Select a file to see why this recommendation was made.")
        self._selection_var = tk.StringVar(value="")
        self._decision_items = {item.relative_path: item for item in preview.items}

        ttk.Label(frame, text=f"Direction: {preview.direction.display_name}", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        ttk.Label(frame, text=f"Files to copy: {preview.total_files}").pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, text=f"Create: {preview.create_count}    Replace existing: {preview.overwrite_count}").pack(
            anchor="w"
        )
        ttk.Label(frame, text=f"Needs attention: {preview.low_confidence_count}").pack(anchor="w")
        ttk.Label(frame, textvariable=self._selection_var, foreground="#4b5563").pack(anchor="w")

        if preview.warnings:
            warnings = "\n".join(f"\u2022 {warning}" for warning in preview.warnings)
            ttk.Label(frame, text=warnings, foreground="#8a4b00", wraplength=500).pack(anchor="w", pady=(10, 0))

        preview_frame = ttk.LabelFrame(frame, text="Planned actions", padding=6)
        preview_frame.pack(fill="both", expand=True, pady=12)

        select_controls = ttk.Frame(preview_frame)
        select_controls.pack(fill="x", pady=(0, 4))
        ttk.Button(
            select_controls,
            text="Select all",
            style="UtilityNeutral.TButton",
            command=self._select_all_items,
        ).pack(side="left")
        ttk.Button(
            select_controls,
            text="Clear selection",
            style="UtilityNeutral.TButton",
            command=self._clear_selection,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            select_controls,
            text="Tip: click rows to adjust selected files for this sync. All files are selected by default.",
            foreground="#4b5563",
        ).pack(side="left", padx=(12, 0))

        tree = ttk.Treeview(
            preview_frame,
            columns=("file", "action", "confidence"),
            show="headings",
            height=min(10, max(3, preview.total_files)),
            selectmode="extended",
        )
        self._tree = tree
        tree.heading("file", text="File")
        tree.heading("action", text="Recommended Action")
        tree.heading("confidence", text="Confidence")
        tree.column("file", width=320)
        tree.column("action", width=240, anchor="center")
        tree.column("confidence", width=125, anchor="center")
        for item in preview.items:
            action = format_decision_recommendation(item.decision_recommendation)
            confidence = format_decision_confidence(item.decision_confidence)
            tree.insert("", "end", values=(item.relative_path, action, confidence))
        tree.pack(fill="both", expand=True)

        ttk.Label(
            preview_frame,
            text="Why this recommendation:",
            padding=(0, 8, 0, 4),
        ).pack(anchor="w")
        ttk.Label(
            preview_frame,
            textvariable=self._details_var,
            justify="left",
            wraplength=500,
            foreground="#333333",
        ).pack(fill="x")

        tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="Cancel",
            style="UtilityNeutral.TButton",
            command=self.destroy,
        ).pack(side="right")
        ttk.Button(
            buttons,
            text="Start Synchronization",
            style="PrimaryNeutral.TButton",
            command=self._confirm,
        ).pack(side="right", padx=(0, 8))

        if preview.items:
            children = tree.get_children()
            tree.selection_set(*children)
            self._on_tree_select()

    def _on_tree_select(self, _event=None) -> None:
        if not self._tree:
            self._selection_var.set("No files selected")
            return
        selected_count = len(self._tree.selection())
        self._selection_var.set(f"{selected_count} {self._pluralize('file', selected_count)} selected")
        self._show_selection_reason(self._tree)

    def _select_all_items(self) -> None:
        if not self._tree:
            return
        self._tree.selection_set(*self._tree.get_children())
        self._on_tree_select()

    def _clear_selection(self) -> None:
        if not self._tree:
            return
        self._tree.selection_remove(*self._tree.get_children())
        self._selection_var.set("No files selected")

    def _pluralize(self, singular: str, count: int) -> str:
        if count == 1:
            return singular
        return f"{singular}s"

    @property
    def selected_item_count(self) -> int:
        return len(self.get_selected_items())

    def get_selected_items(self) -> tuple:
        if not self._tree:
            return ()
        selected_paths = []
        for item_id in self._tree.selection():
            values = self._tree.item(item_id, "values")
            if values:
                selected_paths.append(values[0])
        return tuple(self._decision_items[path] for path in selected_paths if path in self._decision_items)

    def _confirm(self) -> None:
        if not self.get_selected_items():
            messagebox.showwarning("No files selected", "Select at least one file before starting synchronization.")
            return
        self.confirmed = True
        self.destroy()

    def _show_selection_reason(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            return
        selected_values = tree.item(selected[0], "values")
        if len(selected_values) < 1:
            return
        selected_path = selected_values[0]
        item = self._decision_items.get(selected_path)
        if not item:
            self._details_var.set("Decision reason is not available.")
            return

        recommendation = format_decision_recommendation(item.decision_recommendation)
        confidence = format_decision_confidence(item.decision_confidence)
        reason = format_decision_reason(item.decision_reason)
        self._details_var.set(
            f"{recommendation}\nConfidence: {confidence}\nReason: {reason}"
        )
