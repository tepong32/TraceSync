from collections import Counter
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.sync_service import SyncService
from models.compare_status import CompareStatus
from models.sync_direction import SyncDirection
from ui.dialogs.file_details_dialog import FileDetailsDialog
from ui.dialogs.sync_confirmation_dialog import SyncConfirmationDialog
from ui.dialogs.sync_progress_dialog import SyncProgressDialog
from ui.dialogs.sync_summary_dialog import SyncSummaryDialog
from utils.settings import SettingsService


class MainWindow(tk.Tk):
    """Coordinates the comparison and reviewed one-way synchronization workflow."""

    def __init__(self):
        super().__init__()
        self.title("TraceSync v0.3.2")
        self.geometry("1000x650")
        self.minsize(800, 500)
        self.results = []
        self.visible_results = []
        self.current_filter = None
        self.filter_buttons = {}
        self.sync_service = SyncService()
        self.settings = SettingsService.load()
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No comparison results.")
        self._build_ui()
        self._load_saved_folders()

    def _build_ui(self):
        style = ttk.Style()
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("ActiveFilter.TButton", font=("Segoe UI", 9, "bold"))

        folder_frame = ttk.Frame(self, padding=10)
        folder_frame.pack(fill="x")
        folder_frame.columnconfigure((0, 1), weight=1)
        self.local_var = tk.StringVar()
        self.server_var = tk.StringVar()
        self._build_folder_panel(folder_frame, 0, "Local Folder", self.local_var, self.browse_local, (0, 5))
        self._build_folder_panel(folder_frame, 1, "Server Folder", self.server_var, self.browse_server, (5, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(toolbar, text="Compare Folders", command=self.compare_folders, style="Primary.TButton", width=25).pack(side="left")
        ttk.Label(self, textvariable=self.summary_var, anchor="w", padding=(10, 5)).pack(fill="x")

        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", padx=10, pady=(0, 5))
        for status, label in [(None, "All")] + [(status, status.value) for status in CompareStatus]:
            button = ttk.Button(filter_frame, text=label, command=lambda value=status: self.apply_filter(value))
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
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected_details)

        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 5)).pack(fill="x")
        action_frame = ttk.Frame(self, padding=10)
        action_frame.pack(fill="x")
        action_frame.columnconfigure((0, 1), weight=1)
        self.local_to_server_button = ttk.Button(action_frame, text="Copy from Local → Server", command=lambda: self.prepare_sync(SyncDirection.LOCAL_TO_SERVER), state="disabled")
        self.server_to_local_button = ttk.Button(action_frame, text="Copy from Server → Local", command=lambda: self.prepare_sync(SyncDirection.SERVER_TO_LOCAL), state="disabled")
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
            self.results = self.sync_service.compare(local_folder, server_folder)
            self._show_comparison_results()
        except (OSError, ValueError) as exc:
            self._set_sync_buttons(False)
            messagebox.showerror("Comparison Error", str(exc))
            self.status_var.set("Comparison failed.")

    def _show_comparison_results(self):
        counts = Counter(result.status for result in self.results)
        self.summary_var.set(" | ".join(f"{status.value}: {counts[status]}" for status in CompareStatus))
        self.apply_filter(self.current_filter)
        self._set_sync_buttons(True)

    def apply_filter(self, status):
        self.current_filter = status
        self.visible_results = self.results if status is None else [result for result in self.results if result.status is status]
        for button_status, button in self.filter_buttons.items():
            button.configure(style="ActiveFilter.TButton" if button_status is status else "TButton")
        self.populate_tree(self.visible_results)
        label = "all" if status is None else status.value
        self.status_var.set(f"Showing {len(self.visible_results)} {label} files")

    def populate_tree(self, results):
        self.tree.delete(*self.tree.get_children())
        for result in results:
            self.tree.insert("", "end", values=(result.status.value, result.relative_path), tags=(result.status.name,))

    def _open_selected_details(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        path = self.tree.item(selection[0], "values")[1]
        result = next((item for item in self.results if item.relative_path == path), None)
        if result:
            FileDetailsDialog(self, result)

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
        job = self.sync_service.create_job(preview)
        self._set_sync_buttons(False)
        self.sync_service.start_job(job, preview)
        SyncProgressDialog(self, job, self._sync_completed)

    def _sync_completed(self, job):
        job_state = job.snapshot()
        summary = job.summary()
        try:
            self.results = self.sync_service.compare()
            self._show_comparison_results()
        except OSError:
            self._set_sync_buttons(False)
        self.status_var.set(f"Synchronization {job_state.status.value.lower()}: {summary.copied_files} copied, {len(summary.errors)} errors.")
        SyncSummaryDialog(self, job)

    def _set_sync_buttons(self, enabled: bool):
        state = "normal" if enabled and self.results else "disabled"
        self.local_to_server_button.configure(state=state)
        self.server_to_local_button.configure(state=state)
