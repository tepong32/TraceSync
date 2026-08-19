import tkinter as tk
from tkinter import ttk

from models.sync_history import SyncFileOutcome, SyncRunRecord
from ui.utils.formatting import (
    format_history_duration,
    format_history_endpoint,
    format_history_timestamp,
    format_sync_file_outcome,
    format_sync_run_outcome,
)


class SyncHistoryDetailsDialog(tk.Toplevel):
    """Displays the durable summary and per-file outcomes for one run."""

    def __init__(self, parent, record: SyncRunRecord) -> None:
        super().__init__(parent)
        self.record = record
        self.issues_only_var = tk.BooleanVar(value=False)
        self.run_id_var = tk.StringVar(value=record.run_id)
        self.version_var = tk.StringVar(value=record.application_version)
        self.outcome_var = tk.StringVar(value=format_sync_run_outcome(record.outcome))
        self.started_var = tk.StringVar(value=format_history_timestamp(record.started_at_utc))
        self.finished_var = tk.StringVar(value=format_history_timestamp(record.finished_at_utc))
        self.direction_var = tk.StringVar(value=record.direction.display_name)
        self.source_var = tk.StringVar(value=format_history_endpoint(record.source))
        self.destination_var = tk.StringVar(value=format_history_endpoint(record.destination))
        self.duration_var = tk.StringVar(value=format_history_duration(record.duration_ms))

        self.title("Synchronization History Details")
        self.geometry("920x590")
        self.minsize(760, 480)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._populate_files()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=15)
        main.pack(fill="both", expand=True)

        summary = ttk.LabelFrame(main, text="Run Summary", padding=10)
        summary.pack(fill="x")
        summary.columnconfigure(1, weight=1)
        summary.columnconfigure(3, weight=1)
        fields = (
            ("Run ID", self.run_id_var, "Application version", self.version_var),
            ("Outcome", self.outcome_var, "Direction", self.direction_var),
            ("Started", self.started_var, "Finished", self.finished_var),
            ("Source", self.source_var, "Destination", self.destination_var),
            ("Duration", self.duration_var, "Counts", tk.StringVar(value=self._counts_text())),
        )
        for row, (left_label, left_var, right_label, right_var) in enumerate(fields):
            ttk.Label(summary, text=f"{left_label}:").grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=2)
            ttk.Label(summary, textvariable=left_var, wraplength=320).grid(row=row, column=1, sticky="nw", padx=(0, 18), pady=2)
            ttk.Label(summary, text=f"{right_label}:").grid(row=row, column=2, sticky="nw", padx=(0, 8), pady=2)
            ttk.Label(summary, textvariable=right_var, wraplength=320).grid(row=row, column=3, sticky="nw", pady=2)

        files_header = ttk.Frame(main)
        files_header.pack(fill="x", pady=(12, 5))
        ttk.Label(files_header, text="Approved File Outcomes", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Checkbutton(
            files_header,
            text="Issues Only",
            variable=self.issues_only_var,
            command=self._populate_files,
        ).pack(side="right")

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill="both", expand=True)
        columns = ("file", "operation", "outcome", "reason", "message")
        self.files_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        headings = {
            "file": "File",
            "operation": "Action",
            "outcome": "Outcome",
            "reason": "Reason",
            "message": "Message",
        }
        widths = {"file": 230, "operation": 90, "outcome": 110, "reason": 130, "message": 280}
        for column in columns:
            self.files_tree.heading(column, text=headings[column])
            self.files_tree.column(column, width=widths[column], stretch=column in {"file", "message"})
        vertical = ttk.Scrollbar(tree_frame, orient="vertical", command=self.files_tree.yview)
        horizontal = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        ttk.Button(main, text="Close", command=self.destroy).pack(anchor="e", pady=(12, 0))

    def _counts_text(self) -> str:
        counts = self.record.counts
        return (
            f"{counts.copied} copied, {counts.overwritten} overwritten, "
            f"{counts.skipped} skipped, {counts.failed} failed, "
            f"{counts.not_attempted} not attempted, {counts.unknown} unknown"
        )

    def _populate_files(self) -> None:
        self.files_tree.delete(*self.files_tree.get_children())
        for item in self.record.files:
            if self.issues_only_var.get() and item.outcome is SyncFileOutcome.COPIED:
                continue
            self.files_tree.insert(
                "",
                "end",
                values=(
                    item.relative_path,
                    item.operation.replace("_", " ").title(),
                    format_sync_file_outcome(item.outcome),
                    item.reason_code.value.replace("_", " ").title() if item.reason_code else "",
                    item.message or "",
                ),
            )
