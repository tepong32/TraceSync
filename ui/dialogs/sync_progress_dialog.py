import tkinter as tk
from tkinter import ttk

from models.sync_job import SyncJob


class SyncProgressDialog(tk.Toplevel):
    """Polls a job object so the Tkinter event loop remains responsive."""

    def __init__(self, parent, job: SyncJob, on_complete) -> None:
        super().__init__(parent)
        self.job = job
        self.on_complete = on_complete
        self.title("Synchronizing Files")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.current_file_var = tk.StringVar(value="Preparing synchronization...")
        self.count_var = tk.StringVar(value="0 of 0 files")
        self.time_var = tk.StringVar(value="Elapsed: 0s")
        self.remaining_var = tk.StringVar(value="Estimated remaining: calculating...")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._request_cancel)
        self.after(100, self._refresh)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.current_file_var, wraplength=500).pack(anchor="w")
        self.progress = ttk.Progressbar(frame, length=500, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(12, 5))
        ttk.Label(frame, textvariable=self.count_var).pack(anchor="w")
        ttk.Label(frame, textvariable=self.time_var).pack(anchor="w", pady=(3, 10))
        ttk.Label(frame, textvariable=self.remaining_var).pack(anchor="w", pady=(0, 10))
        self.cancel_button = ttk.Button(frame, text="Cancel after current file", command=self._request_cancel)
        self.cancel_button.pack(side="right")

    def _request_cancel(self) -> None:
        self.job.request_cancel()
        self.cancel_button.configure(state="disabled")
        self.current_file_var.set("Stopping after the current file...")

    def _refresh(self) -> None:
        state = self.job.snapshot()
        self.progress["value"] = state.percentage
        self.current_file_var.set(state.current_file or "Finishing synchronization...")
        self.count_var.set(f"{state.completed_files} of {state.total_files} files ({state.percentage:.0f}%)")
        self.time_var.set(f"Elapsed: {state.elapsed_seconds:.1f}s")
        if state.completed_files:
            average = state.elapsed_seconds / state.completed_files
            remaining = average * (state.total_files - state.completed_files)
            self.remaining_var.set(f"Estimated remaining: {remaining:.1f}s")
        if state.is_finished:
            self.destroy()
            self.on_complete(self.job)
            return
        self.after(100, self._refresh)
