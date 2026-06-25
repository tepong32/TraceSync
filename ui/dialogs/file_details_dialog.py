import tkinter as tk
from tkinter import ttk

from models.comparison_result import ComparisonResult


class FileDetailsDialog(tk.Toplevel):
    def __init__(
        self,
        parent,
        result: ComparisonResult,
    ):
        super().__init__(parent)

        self.result = result

        self.file_relative_path_var = tk.StringVar()
        self.file_status_var = tk.StringVar()

        self.local_path_var = tk.StringVar()
        self.local_modified_var = tk.StringVar()
        self.local_size_var = tk.StringVar()

        self.server_path_var = tk.StringVar()
        self.server_modified_var = tk.StringVar()
        self.server_size_var = tk.StringVar()

        self.title("File Details")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()
        self.focus()
        self.lift()

        self._build_ui()
        self._populate()
        self.geometry("650x420")

    def _build_ui(self):
        main_frame = ttk.Frame(
            self,
            padding=15,
        )

        main_frame.pack(
            fill="both",
            expand=True,
        )

        self._build_summary_frame(main_frame)

        self.local_frame = self._build_file_frame(
            parent=main_frame,
            title="Local File",
            path_var=self.local_path_var,
            modified_var=self.local_modified_var,
            size_var=self.local_size_var,
        )

        self.server_frame = self._build_file_frame(
            parent=main_frame,
            title="Server File",
            path_var=self.server_path_var,
            modified_var=self.server_modified_var,
            size_var=self.server_size_var,
        )

        self._build_button_frame(main_frame)

    def _populate(self):
        pass

    def _build_summary_frame(self, parent):
        summary_frame = ttk.LabelFrame(
            parent,
            text="File Summary",
            padding=10,
        )

        summary_frame.pack(
            fill="x",
            pady=(0, 10),
        )

        ttk.Label(
            summary_frame,
            text="Relative Path:",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            summary_frame,
            textvariable=self.file_relative_path_var,
        ).grid(
            row=0,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Label(
            summary_frame,
            text="Status:",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            summary_frame,
            textvariable=self.file_status_var,
        ).grid(
            row=1,
            column=1,
            sticky="w",
            pady=2,
        )

    def _build_file_frame(
        self,
        parent,
        title,
        path_var,
        modified_var,
        size_var,
    ):
        file_frame = ttk.LabelFrame(
            parent,
            text=title,
            padding=10,
        )

        file_frame.pack(
            fill="x",
            pady=(0, 10),
        )

        ttk.Label(
            file_frame,
            text="Path:",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            file_frame,
            textvariable=path_var,
        ).grid(
            row=0,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Label(
            file_frame,
            text="Modified:",
        ).grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            file_frame,
            textvariable=modified_var,
        ).grid(
            row=1,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Label(
            file_frame,
            text="Size:",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            file_frame,
            textvariable=size_var,
        ).grid(
            row=2,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Button(
            file_frame,
            text="Copy Path",
        ).grid(
            row=3,
            column=1,
            sticky="e",
            pady=(10, 0),
        )
        self.bind(
            "<Escape>",
            lambda event: self.destroy(),
        )
        return file_frame

    def _build_button_frame(self, parent):
        button_frame = ttk.Frame(parent)

        button_frame.pack(
            fill="x",
            pady=(5, 0),
        )

        ttk.Button(
            button_frame,
            text="Close",
            command=self.destroy,
        ).pack(
            side="right",
        )