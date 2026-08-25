import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.backup_service import BackupService
from core.sync_history_service import SyncHistoryService
from models.sync_history import SyncFileOutcome, SyncFileOutcomeRecord, SyncRunRecord
from ui.utils.formatting import (
    format_history_duration,
    format_history_endpoint,
    format_history_timestamp,
    format_sync_file_outcome,
    format_sync_run_outcome,
)


class SyncHistoryDetailsDialog(tk.Toplevel):
    """Displays the durable summary and per-file outcomes for one run."""

    def __init__(
        self,
        parent,
        record: SyncRunRecord,
        history_service: SyncHistoryService,
        backup_service: BackupService | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self.history_service = history_service
        self.backup_service = backup_service
        self.files_by_row: dict[str, SyncFileOutcomeRecord] = {}
        self.backup_ids_by_row: dict[str, str] = {}
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
        columns = ("file", "operation", "outcome", "backup", "reason", "message")
        self.files_tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        headings = {
            "file": "File",
            "operation": "Action",
            "outcome": "Outcome",
            "backup": "Backup",
            "reason": "Reason",
            "message": "Message",
        }
        widths = {
            "file": 210,
            "operation": 85,
            "outcome": 105,
            "backup": 75,
            "reason": 125,
            "message": 250,
        }
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
        self.files_tree.bind("<<TreeviewSelect>>", self._on_file_selection)

        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(
            buttons,
            text="Export Run to CSV...",
            command=self._export_csv,
        ).pack(side="left")
        self.restore_button = ttk.Button(
            buttons,
            text="Restore Selected Backup...",
            command=self._restore_selected_backup,
            state="disabled",
        )
        self.restore_button.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")

    def _counts_text(self) -> str:
        counts = self.record.counts
        return (
            f"{counts.copied} copied, {counts.overwritten} overwritten, "
            f"{counts.skipped} skipped, {counts.failed} failed, "
            f"{counts.not_attempted} not attempted, {counts.unknown} unknown"
        )

    def _populate_files(self) -> None:
        self.files_tree.delete(*self.files_tree.get_children())
        self.files_by_row.clear()
        self.backup_ids_by_row.clear()
        discovered_backups = (
            self.backup_service.backup_ids_for_run(self.record.run_id)
            if self.backup_service is not None
            else {}
        )
        for item in self.record.files:
            if self.issues_only_var.get() and item.outcome is SyncFileOutcome.COPIED:
                continue
            backup_id = item.backup_id or discovered_backups.get(item.relative_path)
            row_id = self.files_tree.insert(
                "",
                "end",
                values=(
                    item.relative_path,
                    item.operation.replace("_", " ").title(),
                    format_sync_file_outcome(item.outcome),
                    "Available" if backup_id else "",
                    item.reason_code.value.replace("_", " ").title() if item.reason_code else "",
                    item.message or "",
                ),
            )
            self.files_by_row[row_id] = item
            if backup_id:
                self.backup_ids_by_row[row_id] = backup_id
        self._on_file_selection()

    def _on_file_selection(self, _event=None) -> None:
        selected = self.files_tree.selection()
        item = self.files_by_row.get(selected[0]) if selected else None
        available = (
            self.backup_service is not None
            and item is not None
            and selected[0] in self.backup_ids_by_row
        )
        self.restore_button.configure(state="normal" if available else "disabled")

    def _restore_selected_backup(self) -> None:
        selected = self.files_tree.selection()
        item = self.files_by_row.get(selected[0]) if selected else None
        backup_id = self.backup_ids_by_row.get(selected[0]) if selected else None
        if self.backup_service is None or not backup_id:
            return
        if not messagebox.askyesno(
            "Restore Backup",
            (
                f"Restore the saved destination version of:\n\n{item.relative_path}\n\n"
                "The file currently at the destination will first receive its own safety backup. "
                "Restoring this history item again will use the latest recovery point."
            ),
            parent=self,
        ):
            return
        try:
            result = self.backup_service.restore(backup_id)
        except (OSError, RuntimeError, ValueError, NotImplementedError) as exc:
            messagebox.showerror("Backup Not Restored", str(exc), parent=self)
            return
        safety_note = (
            "\n\nA safety backup of the replaced file was also created and is now the latest "
            f"recovery point (ID {result.safety_backup_id})."
            if result.safety_backup_id
            else ""
        )
        messagebox.showinfo(
            "Backup Restored",
            f"The backup was restored successfully.{safety_note}",
            parent=self,
        )

    def _export_csv(self) -> None:
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Export Synchronization Run",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            initialfile=f"tracesync-sync-{self.record.run_id}.csv",
        )
        if not destination:
            return
        try:
            self.history_service.export_run(self.record.run_id, Path(destination))
        except (OSError, ValueError) as exc:
            messagebox.showerror("History Not Exported", str(exc), parent=self)
            return
        messagebox.showinfo(
            "History Exported",
            "The selected synchronization run was exported successfully.",
            parent=self,
        )
