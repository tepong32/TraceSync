from collections import Counter
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from core.sync_service import SyncService
from utils.settings import SettingsService



### for testing file dialogs
from ui.dialogs.file_details_dialog import FileDetailsDialog
from models.comparison_result import ComparisonResult
from models.compare_status import CompareStatus
from models.file_record import FileRecord


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"TraceSync v0.3.0")
        self.geometry("1000x600")
        self.minsize(800, 500)

        self.results = []
        self.current_filter = None
        self.filter_buttons = {}

        self.sync_service = SyncService()
        self.settings = SettingsService.load()
        self.status_var = tk.StringVar(
            value="Ready"
        )


        self._build_ui()
        self._update_sync_buttons()
        self._load_saved_folders()

    def _build_ui(self):
        # ------------------------------
        # Widget Styles
        # ------------------------------
        style = ttk.Style()

        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "Filter.TButton",
        )

        style.configure(
            "ActiveFilter.TButton",
            font=("Segoe UI", 9, "bold"),
        )
        # ------------------------------
        # Folder Selection Area
        # ------------------------------
        folder_frame = ttk.Frame(
            self,
            padding=10,
        )
        folder_frame.pack(
            fill="x",
        )

        folder_frame.columnconfigure(
            0,
            weight=1,
        )

        folder_frame.columnconfigure(
            1,
            weight=1,
        )

        # LEFT PANEL
        left_frame = ttk.LabelFrame(
            folder_frame,
            text="Local Folder",
            padding=10,
        )

        left_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 5),
        )

        left_frame.columnconfigure(
            0,
            weight=1,
        )

        self.local_var = tk.StringVar()

        ttk.Entry(
            left_frame,
            textvariable=self.local_var,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )

        ttk.Button(
            left_frame,
            text="Browse",
            command=self.browse_local,
        ).grid(
            row=0,
            column=1,
        )

        # RIGHT PANEL
        right_frame = ttk.LabelFrame(
            folder_frame,
            text="Server Folder",
            padding=10,
        )

        right_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
        )

        right_frame.columnconfigure(
            0,
            weight=1,
        )

        self.server_var = tk.StringVar()

        ttk.Entry(
            right_frame,
            textvariable=self.server_var,
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )

        ttk.Button(
            right_frame,
            text="Browse",
            command=self.browse_server,
        ).grid(
            row=0,
            column=1,
        )

        # ------------------------------
        # Compare Button
        # ------------------------------
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 10),
        )

        # Primary application action
        ttk.Button(
            toolbar_frame,
            text="🔍 Compare Folders",
            command=self.compare_folders,
            style="Primary.TButton",
            width=25,
        ).pack(
            side="left",
            padx=(0, 10),
        )

        ### DEVELOPMENT ONLY
        # Remove before merging v0.2.1 into master.
        ttk.Button(
            toolbar_frame,
            text="Test Dialog",
            command=self._test_file_details_dialog,
        ).pack(
            side="left",
        )

        # ------------------------------
        # Summary Bar
        # ------------------------------
        self.summary_var = tk.StringVar(
            value="No comparison results."
        )

        
        summary_label = ttk.Label(
            self,
            textvariable=self.summary_var,
            anchor="w",
            padding=(10, 5),
        )

        summary_label.pack(
            fill="x",
        )

        # ------------------------------
        # Filter Buttons
        # ------------------------------
        filter_frame = ttk.Frame(self)

        filter_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 5),
        )

        # All Filter
        all_button = ttk.Button(
            filter_frame,
            text="All",
            style="ActiveFilter.TButton",
            command=lambda: self.apply_filter(None),
        )

        all_button.pack(
            side="left",
            padx=(0, 5),
        )

        self.filter_buttons[None] = all_button

        # Status Filters
        for status in CompareStatus:
            btn = ttk.Button(
                filter_frame,
                text=status.value,
                style="Filter.TButton",
                command=lambda s=status: self.apply_filter(s),
            )

            btn.pack(
                side="left",
                padx=(0, 5),
            )

            self.filter_buttons[status] = btn

        # ------------------------------
        # Results Treeview
        # ------------------------------
        ttk.Label(
            self,
            text="Results",
        ).pack(
            anchor="w",
            padx=10,
            pady=(5, 5),
        )

        tree_frame = ttk.Frame(self)
        tree_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10),
        )

        columns = (
            "status",
            "relative_path",
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
        )

        # defining row colors
        self.tree.tag_configure(
            CompareStatus.LOCAL_NEWER.name,
            background="#d4edda",
        )

        self.tree.tag_configure(
            CompareStatus.SERVER_NEWER.name,
            background="#d1ecf1",
        )

        self.tree.tag_configure(
            CompareStatus.LOCAL_ONLY.name,
            background="#fff3cd",
        )

        self.tree.tag_configure(
            CompareStatus.SERVER_ONLY.name,
            background="#ffe5b4",
        )

        self.tree.tag_configure(
            CompareStatus.SAME.name,
            background="#ffffff",
        )

        self.tree.heading(
            "status",
            text="Status",
        )

        self.tree.heading(
            "relative_path",
            text="File",
        )

        self.tree.column(
            "status",
            width=120,
            anchor="center",
            stretch=False,
        )

        self.tree.column(
            "relative_path",
            width=600,
            stretch=True,
        )

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview,
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set,
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        status_label = ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(10, 5),
        )

        status_label.pack(
            fill="x",
        )

        # ------------------------------
        # Action Bar
        # ------------------------------
        action_frame = ttk.Frame(
            self,
            padding=10,
        )

        action_frame.pack(
            fill="x",
        )

        action_frame.columnconfigure(
            0,
            weight=1,
        )

        action_frame.columnconfigure(
            1,
            weight=1,
        )

        self.copy_local_button = ttk.Button(
            action_frame,
            text="Copy from Local → Server",
            state="disabled",
        )

        self.copy_local_button.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )

        self.copy_server_button = ttk.Button(
            action_frame,
            text="Copy from Server → Local",
            state="disabled",
        )

        self.copy_server_button.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(5, 0),
        )

    def _load_saved_folders(self):
        self.local_var.set(
            self.settings.get(
                "local_folder",
                "",
            )
        )

        self.server_var.set(
            self.settings.get(
                "server_folder",
                "",
            )
        )

    def browse_local(self):
        folder = filedialog.askdirectory()

        if folder:
            self.local_var.set(folder)

            self.settings["local_folder"] = folder
            SettingsService.save(self.settings)

    def browse_server(self):
        folder = filedialog.askdirectory()

        if folder:
            self.server_var.set(folder)

            self.settings["server_folder"] = folder
            SettingsService.save(self.settings)

    def populate_tree(self, results):
        self.tree.delete(
            *self.tree.get_children()
        )

        for result in results:
            self.tree.insert(
                "",
                "end",
                values=(
                    result.status.value,
                    result.relative_path,
                ),
                tags=(result.status.name,),
            )

    def _update_filter_button_styles(
        self,
        active_status):
        """
        Visually highlight
        the currently selected filter.
        """

        for status, button in self.filter_buttons.items():

            if status == active_status:
                button.configure(
                    style="ActiveFilter.TButton"
                )
            else:
                button.configure(
                    style="Filter.TButton"
                )

    def apply_filter(self, status):
        self.current_filter = status
        self._update_filter_button_styles(
            status)

        if status is None:
            filtered_results = self.results

            self.status_var.set(
                f"Showing all {len(filtered_results)} files"
            )

        else:
            filtered_results = [
                result
                for result in self.results
                if result.status == status
            ]

            self.status_var.set(
                f"Showing {len(filtered_results)} {status.value} files"
            )

        self.populate_tree(filtered_results)

    def _update_sync_buttons(self):
        """
        Enable or disable synchronization buttons based on
        the currently available synchronization candidates.
        """

        local_candidates = (
            self.sync_service.get_local_to_server_candidates(
                self.results
            )
        )

        server_candidates = (
            self.sync_service.get_server_to_local_candidates(
                self.results
            )
        )

        self.copy_local_button.configure(
            state="normal" if local_candidates else "disabled"
        )

        self.copy_server_button.configure(
            state="normal" if server_candidates else "disabled"
        )

    def compare_folders(self):
        local_folder = self.local_var.get().strip()
        server_folder = self.server_var.get().strip()

        if not local_folder:
            messagebox.showwarning(
                "Missing Folder",
                "Please select a Local Folder.",
            )
            return

        if not server_folder:
            messagebox.showwarning(
                "Missing Folder",
                "Please select a Server Folder.",
            )
            return

        try:
            self.status_var.set(
                "Comparing folders..."
            )

            self.update_idletasks()
            results = self.sync_service.compare(
                local_folder,
                server_folder,
            )
            self.results = results
            counts = Counter(
                result.status
                for result in results
            )

            summary_text = (
                f"Local Newer: {counts.get(CompareStatus.LOCAL_NEWER, 0)} | "
                f"Server Newer: {counts.get(CompareStatus.SERVER_NEWER, 0)} | "
                f"Same: {counts.get(CompareStatus.SAME, 0)} | "
                f"Local Only: {counts.get(CompareStatus.LOCAL_ONLY, 0)} | "
                f"Server Only: {counts.get(CompareStatus.SERVER_ONLY, 0)}"
            )

            self.summary_var.set(summary_text)

            self.apply_filter(
                self.current_filter
            )

            self._update_sync_buttons()

        except Exception as exc:
            messagebox.showerror(
                "Comparison Error",
                str(exc),
            )

        

    ### test dialog button
    def _test_file_details_dialog(self):
        local_record = FileRecord(
            absolute_path=r"C:\Reports\2026\Budget.xlsx",
            relative_path=r"Reports\2026\Budget.xlsx",
            modified_time=1750846200.0,
            size=421376,
        )

        server_record = FileRecord(
            absolute_path=r"\\SERVER\Accounting\Reports\2026\Budget.xlsx",
            relative_path=r"Reports\2026\Budget.xlsx",
            modified_time=1750587000.0,
            size=418912,
        )

        result = ComparisonResult(
            relative_path=r"Reports\2026\Budget.xlsx",
            status=CompareStatus.LOCAL_NEWER,
            local_record=local_record,
            server_record=server_record,
        )

        FileDetailsDialog(
            parent=self,
            result=result,
        )