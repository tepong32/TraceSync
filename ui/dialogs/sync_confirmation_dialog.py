import tkinter as tk
from tkinter import ttk

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
        ttk.Label(frame, text=f"Direction: {preview.direction.display_name}", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Files to copy: {preview.total_files}").pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, text=f"Create: {preview.create_count}    Replace existing: {preview.overwrite_count}").pack(anchor="w")
        ttk.Label(frame, text=f"Potentially uncertain files: {preview.low_confidence_count}").pack(anchor="w")
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
        )
        tree.heading("file", text="File")
        tree.heading("action", text="Recommended Action")
        tree.heading("confidence", text="Confidence")
        tree.column("file", width=320)
        tree.column("action", width=200, anchor="center")
        tree.column("confidence", width=90, anchor="center")
        for item in preview.items:
            action = item.decision_recommendation or ("Replace existing" if item.overwrite else "Create new")
            confidence = item.decision_confidence or "Unknown"
            tree.insert("", "end", values=(item.relative_path, action, confidence))
        tree.pack(fill="both", expand=True)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Start Synchronization", command=self._confirm).pack(side="right", padx=(0, 8))

    def _confirm(self) -> None:
        self.confirmed = True
        self.destroy()
