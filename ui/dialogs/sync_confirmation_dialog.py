import tkinter as tk
from tkinter import ttk

from ui.utils.formatting import (
    format_decision_confidence,
    format_decision_reason,
    format_decision_recommendation,
)
from models.sync_preview import SyncPreview


class SyncConfirmationDialog(tk.Toplevel):
    """Shows the complete reviewed plan before any irreversible copy starts."""

    def __init__(self, parent, preview: SyncPreview) -> None:
        super().__init__(parent)
        self.confirmed = False
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
        ttk.Label(frame, text=f"Direction: {preview.direction.display_name}", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Files to copy: {preview.total_files}").pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, text=f"Create: {preview.create_count}    Replace existing: {preview.overwrite_count}").pack(anchor="w")
        ttk.Label(frame, text=f"Needs attention: {preview.low_confidence_count}").pack(anchor="w")
        if preview.warnings:
            warnings = "\n".join(f"\u2022 {warning}" for warning in preview.warnings)
            ttk.Label(frame, text=warnings, foreground="#8a4b00", wraplength=500).pack(anchor="w", pady=(10, 0))

        preview_frame = ttk.LabelFrame(frame, text="Planned actions", padding=6)
        preview_frame.pack(fill="both", expand=True, pady=12)
        tree = ttk.Treeview(
            preview_frame,
            columns=("file", "action", "confidence"),
            show="headings",
            height=min(10, max(3, preview.total_files)),
            selectmode="browse",
        )
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

        self._decision_items = {item.relative_path: item for item in preview.items}
        tree.bind("<<TreeviewSelect>>", lambda _event: self._show_selection_reason(tree))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Start Synchronization", command=self._confirm).pack(side="right", padx=(0, 8))

        if preview.items:
            first_item_id = tree.get_children()[0]
            tree.selection_set(first_item_id)
            self._show_selection_reason(tree)

    def _confirm(self) -> None:
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
