import tkinter as tk
from tkinter import ttk

from models.sync_job import SyncJob


class SyncSummaryDialog(tk.Toplevel):
    """Displays a clear outcome after a synchronization job finishes."""

    def __init__(self, parent, job: SyncJob) -> None:
        super().__init__(parent)
        summary = job.summary()
        job_state = job.snapshot()
        self.title("Synchronization Summary")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)
        heading = "Synchronization cancelled" if summary.cancelled else job_state.status.value
        ttk.Label(frame, text=heading, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Files copied: {summary.copied_files}").pack(anchor="w", pady=(10, 0))
        ttk.Label(frame, text=f"Files overwritten: {summary.overwritten_files}").pack(anchor="w")
        ttk.Label(frame, text=f"Files skipped: {summary.skipped_files}").pack(anchor="w")
        ttk.Label(frame, text=f"Errors: {len(summary.errors)}").pack(anchor="w")
        ttk.Label(frame, text=f"Elapsed time: {summary.elapsed_seconds:.1f}s").pack(anchor="w")
        if summary.errors:
            error_text = "\n".join(f"• {error.relative_path}: {error.message}" for error in summary.errors)
            ttk.Label(frame, text=error_text, foreground="#a00000", wraplength=550).pack(anchor="w", pady=(10, 0))
        ttk.Button(frame, text="Close", command=self.destroy).pack(side="right", pady=(15, 0))
