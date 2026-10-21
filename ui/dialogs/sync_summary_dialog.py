import tkinter as tk
from tkinter import ttk

from models.sync_job import SyncJob
from models.sync_history import SyncFileOutcome
from ui.theme import AMBER


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
        ttk.Label(frame, text=f"Files failed: {summary.failed_files}").pack(anchor="w")
        ttk.Label(frame, text=f"Files not attempted: {summary.not_attempted_files}").pack(anchor="w")
        ttk.Label(frame, text=f"Errors: {len(summary.errors)}").pack(anchor="w")
        ttk.Label(frame, text=f"Elapsed time: {summary.elapsed_seconds:.1f}s").pack(anchor="w")
        if summary.errors:
            error_text = "\n".join(f"• {error.relative_path}: {error.message}" for error in summary.errors)
            ttk.Label(frame, text=error_text, foreground="#a00000", wraplength=550).pack(anchor="w", pady=(10, 0))
        notes = [outcome for outcome in summary.file_outcomes
                 if outcome.outcome is SyncFileOutcome.COPIED and outcome.message]
        if notes:
            ttk.Label(frame, text="Copy notes - review before running again", foreground=AMBER).pack(anchor="w", pady=(10, 4))
            note_frame = ttk.Frame(frame)
            note_frame.pack(fill="both", expand=True)
            text = tk.Text(note_frame, height=6, width=70, wrap="word", foreground=AMBER)
            scrollbar = ttk.Scrollbar(note_frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            text.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            text.insert("1.0", "\n\n".join(f"{outcome.relative_path}: {outcome.message}" for outcome in notes))
            text.configure(state="disabled")
        ttk.Button(frame, text="Close", command=self.destroy).pack(side="right", pady=(15, 0))
