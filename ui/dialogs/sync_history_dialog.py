import tkinter as tk
from tkinter import messagebox, ttk

from core.sync_history_service import SyncHistoryService
from models.sync_history import SyncRunRecord
from ui.dialogs.sync_history_details_dialog import SyncHistoryDetailsDialog
from ui.utils.formatting import (
    format_history_duration,
    format_history_endpoint,
    format_history_timestamp,
    format_sync_run_outcome,
)


class SyncHistoryDialog(tk.Toplevel):
    """Lists recent synchronization runs without coupling storage to Tkinter."""

    DISPLAY_LIMIT = 100

    def __init__(self, parent, history_service: SyncHistoryService) -> None:
        super().__init__(parent)
        self.history_service = history_service
        self.records_by_id: dict[str, SyncRunRecord] = {}
        self.warning_var = tk.StringVar(value="")
        self.empty_var = tk.StringVar(value="")

        self.title("Synchronization History")
        self.geometry("980x520")
        self.minsize(800, 420)
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._load_history()

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=15)
        main.pack(fill="both", expand=True)
        ttk.Label(
            main,
            text="Recent Synchronizations",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            main,
            textvariable=self.warning_var,
            foreground="#8a4b08",
            wraplength=900,
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(main, textvariable=self.empty_var, foreground="#4b5563").pack(anchor="w", pady=(4, 0))

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill="both", expand=True, pady=(10, 0))
        columns = ("date", "direction", "endpoints", "outcome", "copied", "issues", "duration")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "date": "Date / Time",
            "direction": "Direction",
            "endpoints": "Source → Destination",
            "outcome": "Outcome",
            "copied": "Copied",
            "issues": "Issues",
            "duration": "Duration",
        }
        widths = {
            "date": 165,
            "direction": 125,
            "endpoints": 330,
            "outcome": 145,
            "copied": 65,
            "issues": 65,
            "duration": 80,
        }
        for column in columns:
            self.history_tree.heading(column, text=headings[column])
            self.history_tree.column(column, width=widths[column], stretch=column == "endpoints")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.history_tree.bind("<<TreeviewSelect>>", self._on_selection_changed)
        self.history_tree.bind("<Double-1>", self._view_details)

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Clear History", command=self._clear_history).pack(side="left")
        self.details_button = ttk.Button(buttons, text="View Details", command=self._view_details, state="disabled")
        self.details_button.pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def _load_history(self) -> None:
        loaded = self.history_service.list_records(limit=self.DISPLAY_LIMIT)
        self.history_tree.delete(*self.history_tree.get_children())
        self.records_by_id = {record.run_id: record for record in loaded.records}
        for record in loaded.records:
            self.history_tree.insert(
                "",
                "end",
                iid=record.run_id,
                values=(
                    format_history_timestamp(record.started_at_utc),
                    record.direction.display_name,
                    f"{format_history_endpoint(record.source)} → {format_history_endpoint(record.destination)}",
                    format_sync_run_outcome(record.outcome),
                    record.counts.copied,
                    record.counts.issue_count,
                    format_history_duration(record.duration_ms),
                ),
            )

        unreadable_count = len(loaded.unreadable_files)
        self.warning_var.set(
            (
                f"Warning: {unreadable_count} history record(s) could not be read. "
                "Other valid records are still shown."
            )
            if unreadable_count
            else ""
        )
        self.empty_var.set("No synchronization history is available." if not loaded.records else "")
        self.details_button.configure(state="disabled")

    def _on_selection_changed(self, _event=None) -> None:
        self.details_button.configure(state="normal" if self.history_tree.selection() else "disabled")

    def _selected_record(self) -> SyncRunRecord | None:
        selection = self.history_tree.selection()
        if not selection:
            return None
        return self.records_by_id.get(selection[0])

    def _view_details(self, _event=None) -> None:
        record = self._selected_record()
        if record is not None:
            SyncHistoryDetailsDialog(self, record, self.history_service)

    def _clear_history(self) -> None:
        if not messagebox.askyesno(
            "Clear Synchronization History",
            "Permanently clear all synchronization history on this computer?",
            parent=self,
        ):
            return
        try:
            deleted = self.history_service.clear_history()
        except (OSError, RuntimeError) as exc:
            messagebox.showerror("History Not Cleared", str(exc), parent=self)
            return
        self._load_history()
        self.empty_var.set(f"Synchronization history cleared ({deleted} record(s) removed).")
