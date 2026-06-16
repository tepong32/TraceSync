from collections import Counter
from models.compare_status import CompareStatus
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from core.sync_service import SyncService


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("TraceSync v0.1.0")
        self.geometry("1000x600")
        self.minsize(800, 500)

        self.results = []
        self.current_filter = None

        self.sync_service = SyncService()
        self.status_var = tk.StringVar(
            value="Ready"
        )


        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill="x")

        # ------------------------------
        # Local Folder
        # ------------------------------
        ttk.Label(
            top_frame,
            text="Local Folder"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 5),
        )

        self.local_var = tk.StringVar()

        ttk.Entry(
            top_frame,
            textvariable=self.local_var,
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )

        ttk.Button(
            top_frame,
            text="Browse",
            command=self.browse_local,
        ).grid(
            row=1,
            column=1,
        )

        # ------------------------------
        # Server Folder
        # ------------------------------
        ttk.Label(
            top_frame,
            text="Server Folder"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 5),
        )

        self.server_var = tk.StringVar()

        ttk.Entry(
            top_frame,
            textvariable=self.server_var,
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=(0, 5),
        )

        ttk.Button(
            top_frame,
            text="Browse",
            command=self.browse_server,
        ).grid(
            row=3,
            column=1,
        )

        # ------------------------------
        # Compare Button
        # ------------------------------
        ttk.Button(
            top_frame,
            text="Compare",
            command=self.compare_folders,
        ).grid(
            row=4,
            column=0,
            sticky="w",
            pady=15,
        )

        top_frame.columnconfigure(0, weight=1)

        # ------------------------------
        # Filter Buttons
        # ------------------------------
        filter_frame = ttk.Frame(self)
        filter_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 5),
        )

        ttk.Button(
            filter_frame,
            text="All",
            command=lambda: self.apply_filter(None),
        ).pack(
            side="left",
            padx=(0, 5),
        )

        for status in CompareStatus:
            ttk.Button(
                filter_frame,
                text=status.value,
                command=lambda s=status: self.apply_filter(s),
            ).pack(
                side="left",
                padx=(0, 5),
            )

        # ------------------------------
        # Results Treeview
        # ------------------------------
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
            text="Relative Path",
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

    def browse_local(self):
        folder = filedialog.askdirectory()

        if folder:
            self.local_var.set(folder)

    def browse_server(self):
        folder = filedialog.askdirectory()

        if folder:
            self.server_var.set(folder)

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

    def apply_filter(self, status):
        self.current_filter = status

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

        except Exception as exc:
            messagebox.showerror(
                "Comparison Error",
                str(exc),
            )

        


            