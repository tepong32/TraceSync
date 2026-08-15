from collections import Counter
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.sync_service import SyncService
from models.compare_status import CompareStatus
from models.sync_direction import SyncDirection
from models.comparison_decision import ConfidenceLevel
from ui.dialogs.file_details_dialog import FileDetailsDialog
from ui.dialogs.ignore_settings_dialog import IgnoreSettingsDialog
from ui.dialogs.sync_confirmation_dialog import SyncConfirmationDialog
from ui.dialogs.sync_progress_dialog import SyncProgressDialog
from ui.dialogs.sync_summary_dialog import SyncSummaryDialog
from utils.settings import SettingsService


class MainWindow(tk.Tk):
    """Coordinates the comparison and reviewed one-way synchronization workflow."""

    def __init__(self):
        super().__init__()
        self.title("TraceSync v0.6.0")
        self.geometry("1000x650")
        self.minsize(800, 500)
        self.results = []
        self.visible_results = []
        self.current_filter = None
        self.filter_buttons = {}
        self.sync_service = SyncService()
        self.settings = SettingsService.load()
        self._needs_attention_filter_key = "NEEDS_ATTENTION"
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No comparison results.")
        self.provider_options = [
            "Local Folder (active)",
            "OneDrive (coming soon)",
            "Google Drive (coming soon)",
            "Dropbox (coming soon)",
        ]
        self.source_provider_var = tk.StringVar(value=self.provider_options[0])
        self.destination_provider_var = tk.StringVar(value=self.provider_options[0])
        self.source_provider_status_var = tk.StringVar(value="")
        self.destination_provider_status_var = tk.StringVar(value="")
        self._build_ui()
        self._load_saved_folders()
        self._refresh_provider_status()

    def _build_ui(self):
        style = ttk.Style()
        style.configure("PrimaryNeutral.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8), background="#d9dde5", foreground="#111827")
        style.map(
            "PrimaryNeutral.TButton",
            foreground=[("disabled", "#6b7280"), ("pressed", "#111827"), ("active", "#111827")],
            background=[
                ("disabled", "#eef1f6"),
                ("pressed", "#c9d0dd"),
                ("active", "#d4dae4"),
                ("!disabled", "#d9dde5"),
            ],
        )
        style.configure(
            "MediumNeutral.TButton",
            font=("Segoe UI", 10),
            padding=(10, 7),
            background="#eceff4",
            foreground="#111827",
        )
        style.map(
            "MediumNeutral.TButton",
            foreground=[("disabled", "#6b7280"), ("pressed", "#111827"), ("active", "#111827")],
            background=[
                ("disabled", "#f5f6f8"),
                ("pressed", "#e0e4ec"),
                ("active", "#e6eaf0"),
                ("!disabled", "#eceff4"),
            ],
        )
        style.configure(
            "UtilityNeutral.TButton",
            font=("Segoe UI", 9),
            padding=(8, 6),
            background="#f6f7f9",
            foreground="#1f2937",
        )
        style.map(
            "UtilityNeutral.TButton",
            foreground=[("disabled", "#9aa3ad"), ("pressed", "#111827"), ("active", "#111827")],
            background=[
                ("disabled", "#f9fafb"),
                ("pressed", "#e7eaf0"),
                ("active", "#eef1f5"),
                ("!disabled", "#f6f7f9"),
            ],
        )
        style.configure("FilterNeutral.TButton", font=("Segoe UI", 9), padding=(8, 6), background="#eceff4", foreground="#1f2937")
        style.configure(
            "ActiveFilter.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(8, 6),
            background="#d9dde5",
            foreground="#111827",
        )
        style.map(
            "FilterNeutral.TButton",
            foreground=[("disabled", "#9aa3ad"), ("pressed", "#111827"), ("active", "#111827")],
            background=[
                ("pressed", "#e0e4ec"),
                ("active", "#e6eaf0"),
                ("!disabled", "#eceff4"),
            ],
        )
        style.map(
            "ActiveFilter.TButton",
            foreground=[("disabled", "#6b7280"), ("pressed", "#111827"), ("active", "#111827")],
            background=[
                ("pressed", "#c9d0dd"),
                ("active", "#d4dae4"),
                ("!disabled", "#d9dde5"),
            ],
        )

        folder_frame = ttk.Frame(self, padding=10)
        folder_frame.pack(fill="x")
        folder_frame.columnconfigure((0, 1), weight=1)
        self.local_var = tk.StringVar()
        self.server_var = tk.StringVar()
        self._build_folder_panel(folder_frame, 0, "Local Folder", self.local_var, self.browse_local, (0, 5))
        self._build_folder_panel(folder_frame, 1, "Server Folder", self.server_var, self.browse_server, (5, 0))

        provider_panel = ttk.LabelFrame(self, text="Provider Onboarding (Planned)", padding=10)
        provider_panel.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Label(provider_panel, text="Source provider:").grid(row=0, column=0, sticky="w")
        source_provider_combo = ttk.Combobox(
            provider_panel,
            textvariable=self.source_provider_var,
            values=self.provider_options,
            state="readonly",
            width=36,
        )
        source_provider_combo.grid(row=0, column=1, sticky="w", padx=(10, 0))
        source_provider_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self._refresh_provider_status(),
        )

        ttk.Label(
            provider_panel,
            textvariable=self.source_provider_status_var,
            foreground="#4b5563",
        ).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(4, 10))

        ttk.Button(
            provider_panel,
            text="Connect Source Provider",
            state="disabled",
            style="UtilityNeutral.TButton",
        ).grid(row=0, column=2, padx=(10, 0), sticky="w")

        ttk.Label(provider_panel, text="Destination provider:").grid(row=2, column=0, sticky="w")
        destination_provider_combo = ttk.Combobox(
            provider_panel,
            textvariable=self.destination_provider_var,
            values=self.provider_options,
            state="readonly",
            width=36,
        )
        destination_provider_combo.grid(row=2, column=1, sticky="w", padx=(10, 0))
        destination_provider_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self._refresh_provider_status(),
        )

        ttk.Label(
            provider_panel,
            textvariable=self.destination_provider_status_var,
            foreground="#4b5563",
        ).grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(4, 10))

        ttk.Button(
            provider_panel,
            text="Connect Destination Provider",
            state="disabled",
            style="UtilityNeutral.TButton",
        ).grid(row=2, column=2, padx=(10, 0), sticky="w")

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(
            toolbar,
            text="Ignore Settings",
            command=self.edit_ignore_settings,
            style="MediumNeutral.TButton",
            width=16,
        ).pack(side="left")
        ttk.Button(
            toolbar,
            text="View Decision Details",
            command=self.open_selected_decision_details,
            style="MediumNeutral.TButton",
            width=24,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            toolbar,
            text="Compare Folders",
            command=self.compare_folders,
            style="MediumNeutral.TButton",
            width=25,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(self, textvariable=self.summary_var, anchor="w", padding=(10, 5)).pack(fill="x")

        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=(0, 5))
        for status, label in (
                [(None, "All")]
                + [(status, status.value) for status in CompareStatus]
                + [(self._needs_attention_filter_key, "Needs Attention")]
        ):
            button = ttk.Button(
                filter_frame,
                text=label,
                style="FilterNeutral.TButton",
                command=lambda value=status: self.apply_filter(value),
            )
            button.pack(side="left", padx=(0, 5))
            self.filter_buttons[status] = button

        ttk.Label(self, text="Results").pack(anchor="w", padx=10, pady=(5, 5))
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = ttk.Treeview(tree_frame, columns=("status", "relative_path"), show="headings")
        self.tree.heading("status", text="Status")
        self.tree.heading("relative_path", text="File")
        self.tree.column("status", width=130, anchor="center", stretch=False)
        self.tree.column("relative_path", width=600, stretch=True)
        for status, color in {
            CompareStatus.LOCAL_NEWER: "#d4edda", CompareStatus.SERVER_NEWER: "#d1ecf1",
            CompareStatus.LOCAL_ONLY: "#fff3cd", CompareStatus.SERVER_ONLY: "#ffe5b4", CompareStatus.SAME: "#ffffff",
        }.items():
            self.tree.tag_configure(status.name, background=color)
        self.tree.tag_configure("NEEDS_ATTENTION", background="#fff3cd")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected_details)

        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 5)).pack(fill="x")
        action_frame = ttk.Frame(self, padding=10)
        action_frame.pack(fill="x")
        action_frame.columnconfigure((0, 1), weight=1)
        self.local_to_server_button = ttk.Button(
            action_frame,
            text="Copy from Local → Server",
            command=lambda: self.prepare_sync(SyncDirection.LOCAL_TO_SERVER),
            state="disabled",
            style="PrimaryNeutral.TButton",
        )
        self.server_to_local_button = ttk.Button(
            action_frame,
            text="Copy from Server → Local",
            command=lambda: self.prepare_sync(SyncDirection.SERVER_TO_LOCAL),
            state="disabled",
            style="PrimaryNeutral.TButton",
        )
        self.local_to_server_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.server_to_local_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    @staticmethod
    def _build_folder_panel(parent, column, title, variable, command, padding):
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.grid(row=0, column=column, sticky="nsew", padx=padding)
        frame.columnconfigure(0, weight=1)
        ttk.Entry(frame, textvariable=variable).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(frame, text="Browse", command=command).grid(row=0, column=1)

    def _load_saved_folders(self):
        self.local_var.set(self.settings.get("local_folder", ""))
        self.server_var.set(self.settings.get("server_folder", ""))

    def browse_local(self):
        self._browse_folder(self.local_var, "local_folder")

    def browse_server(self):
        self._browse_folder(self.server_var, "server_folder")

    def _browse_folder(self, variable, setting_name):
        folder = filedialog.askdirectory()
        if folder:
            variable.set(folder)
            self.settings[setting_name] = folder
            SettingsService.save(self.settings)

    def compare_folders(self):
        local_folder, server_folder = self.local_var.get().strip(), self.server_var.get().strip()
        if not local_folder or not server_folder:
            messagebox.showwarning("Missing Folder", "Please select both a Local Folder and a Server Folder.")
            return
        try:
            self.status_var.set("Comparing folders...")
            self.update_idletasks()
            self.results = self.sync_service.compare(
                local_folder,
                server_folder,
                user_ignore_patterns=self.settings.get("ignore_patterns", []),
            )
            self._show_comparison_results()
        except (OSError, ValueError) as exc:
            self._set_sync_buttons(False)
            messagebox.showerror("Comparison Error", str(exc))
            self.status_var.set("Comparison failed.")

    def _show_comparison_results(self):
        self._refresh_filter_labels()
        counts = Counter(result.status for result in self.results)
        counts_text = " | ".join(f"{status.value}: {counts[status]}" for status in CompareStatus)
        status_lines = [counts_text, self._build_ignore_status_line()]
        self.summary_var.set("\n".join(line for line in status_lines if line))
        self.apply_filter(self.current_filter)
        self._set_sync_buttons(True)

    def _build_ignore_status_line(self) -> str:
        parts: list[str] = []
        ignored_count = getattr(self.sync_service, "last_ignored_count", 0)
        if ignored_count:
            parts.append(f"{ignored_count} extra office files are being skipped.")
        local_folder = self.local_var.get().strip()
        if local_folder and Path(local_folder, ".tracesyncignore").is_file():
            parts.append(".tracesyncignore is active for this comparison.")
        if self.settings.get("ignore_patterns"):
            parts.append("Your custom ignore patterns are in use.")
        return " ".join(parts)

    def _refresh_provider_status(self):
        local_ready = "Local folder mode is active. Remote providers are listed for future setup."
        remote_planned = "Remote provider integration is planned and not active yet."
        self.source_provider_status_var.set(
            local_ready if self.source_provider_var.get() == self.provider_options[0] else remote_planned
        )
        self.destination_provider_status_var.set(
            local_ready if self.destination_provider_var.get() == self.provider_options[0] else remote_planned
        )

    def apply_filter(self, status):
        self.current_filter = status
        if status == self._needs_attention_filter_key:
            self.visible_results = [result for result in self.results if self._needs_attention(result)]
        else:
            self.visible_results = self.results if status is None else [result for result in self.results if result.status is status]
        for button_status, button in self.filter_buttons.items():
            button.configure(style="ActiveFilter.TButton" if button_status is status else "FilterNeutral.TButton")
        self.populate_tree(self.visible_results)
        if status is None:
            label = "all files"
        elif status == self._needs_attention_filter_key:
            if len(self.visible_results) == 1:
                label = "file needing attention"
            else:
                label = "files needing attention"
        else:
            label = f"{status.value} files"
        self.status_var.set(f"Showing {len(self.visible_results)} {label}")
        self._refresh_filter_labels()

    def _needs_attention(self, result):
        if result.decision is None:
            return False
        return result.decision.confidence == ConfidenceLevel.LOW

    def _needs_attention_count(self) -> int:
        return sum(1 for result in self.results if self._needs_attention(result))

    def _needs_attention_filter_text(self) -> str:
        return f"Needs Attention ({self._needs_attention_count()})"

    def _status_filter_text(self, status: CompareStatus) -> str:
        status_count = sum(1 for result in self.results if result.status is status)
        return f"{status.value} ({status_count})"

    def _all_filter_text(self) -> str:
        return f"All ({len(self.results)})"

    def _refresh_filter_labels(self):
        for button_status, button in self.filter_buttons.items():
            if button_status is None:
                button.configure(text=self._all_filter_text())
            elif button_status == self._needs_attention_filter_key:
                button.configure(text=self._needs_attention_filter_text())
            else:
                button.configure(text=self._status_filter_text(button_status))

    def populate_tree(self, results):
        self.tree.delete(*self.tree.get_children())
        for result in results:
            tags = [result.status.name]
            if self._needs_attention(result):
                tags.append("NEEDS_ATTENTION")
            self.tree.insert("", "end", values=(result.status.value, result.relative_path), tags=tuple(tags))

    def _open_selected_details(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        path = self.tree.item(selection[0], "values")[1]
        result = next((item for item in self.results if item.relative_path == path), None)
        if result:
            FileDetailsDialog(self, result)

    def open_selected_decision_details(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No selection", "Select a row first to view decision details.")
            return
        self._open_selected_details()

    def prepare_sync(self, direction: SyncDirection):
        preview = self.sync_service.create_preview(self.results, direction)
        if not preview.items:
            messagebox.showinfo("Nothing to Synchronize", "There are no eligible files to copy in this direction.")
            return
        dialog = SyncConfirmationDialog(self, preview)
        self.wait_window(dialog)
        if not dialog.confirmed:
            self.status_var.set("Synchronization cancelled before any files were copied.")
            return
        selected_items = dialog.get_selected_items()
        if not selected_items:
            self.status_var.set("Synchronization cancelled: no files selected.")
            return
        selected_preview = preview.with_selected_items({item.relative_path for item in selected_items})
        if not selected_preview.items:
            self.status_var.set("Synchronization cancelled: no files selected.")
            return
        if len(selected_preview.items) < len(preview.items):
            self.status_var.set(f"Synchronizing {len(selected_preview.items)} of {len(preview.items)} selected file(s).")
        job = self.sync_service.create_job(selected_preview)
        self._set_sync_buttons(False)
        self.sync_service.start_job(job, selected_preview)
        SyncProgressDialog(self, job, self._sync_completed)

    def _sync_completed(self, job):
        job_state = job.snapshot()
        summary = job.summary()
        try:
            self.results = self.sync_service.compare(
                user_ignore_patterns=self.settings.get("ignore_patterns", []),
            )
            self._show_comparison_results()
        except OSError:
            self._set_sync_buttons(False)
        self.status_var.set(f"Synchronization {job_state.status.value.lower()}: {summary.copied_files} copied, {len(summary.errors)} errors.")
        SyncSummaryDialog(self, job)

    def edit_ignore_settings(self):
        dialog = IgnoreSettingsDialog(self, self.settings.get("ignore_patterns", []))
        self.wait_window(dialog)
        if not dialog.confirmed:
            return
        self.settings["ignore_patterns"] = dialog.patterns
        SettingsService.save(self.settings)
        self.status_var.set(f"Ignore rules saved ({len(dialog.patterns)} pattern(s)).")
        if self.results:
            self.compare_folders()

    def _set_sync_buttons(self, enabled: bool):
        state = "normal" if enabled and self.results else "disabled"
        self.local_to_server_button.configure(state=state)
        self.server_to_local_button.configure(state=state)
