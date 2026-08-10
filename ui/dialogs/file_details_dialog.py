import tkinter as tk
from tkinter import ttk
from pathlib import Path
from ui.utils.formatting import format_bytes, format_file_type, format_timestamp
from models.comparison_result import ComparisonResult
from models.compare_status import CompareStatus


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
        self.file_type_var = tk.StringVar()

        self.local_path_var = tk.StringVar()
        self.local_modified_var = tk.StringVar()
        self.local_size_var = tk.StringVar()
        self.local_type_var = tk.StringVar()
        self.local_extension_var = tk.StringVar()

        self.server_path_var = tk.StringVar()
        self.server_modified_var = tk.StringVar()
        self.server_size_var = tk.StringVar()
        self.server_type_var = tk.StringVar()
        self.server_extension_var = tk.StringVar()

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
        self.file_relative_path_var.set(
            self.result.relative_path
        )

        self.file_status_var.set(
            self._friendly_status(self.result.status)
        )
        self.file_type_var.set(self._derive_file_type())

        self._populate_record(
            self.result.local_record,
            self.local_path_var,
            self.local_modified_var,
            self.local_size_var,
            self.local_type_var,
            self.local_extension_var,
        )

        self._populate_record(
            self.result.server_record,
            self.server_path_var,
            self.server_modified_var,
            self.server_size_var,
            self.server_type_var,
            self.server_extension_var,
        )
    def _friendly_status(self, status):
        messages = {
            CompareStatus.LOCAL_NEWER:
                "The Local copy appears more recent.",

            CompareStatus.SERVER_NEWER:
                "The Server copy appears more recent.",

            CompareStatus.LOCAL_ONLY:
                "The file exists only in the Local folder.",

            CompareStatus.SERVER_ONLY:
                "The file exists only in the Server folder.",

            CompareStatus.SAME:
                "Files are identical.",
        }

        return messages.get(
            status,
            status.value,
        )

    

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

        ttk.Label(
            summary_frame,
            text="File Type:",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            summary_frame,
            textvariable=self.file_type_var,
        ).grid(
            row=2,
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
        type_var,
        extension_var,
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

        ttk.Label(
            file_frame,
            text="Extension:",
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            file_frame,
            textvariable=extension_var,
        ).grid(
            row=3,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Label(
            file_frame,
            text="Type:",
        ).grid(
            row=4,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )

        ttk.Label(
            file_frame,
            textvariable=type_var,
        ).grid(
            row=4,
            column=1,
            sticky="w",
            pady=2,
        )

        ttk.Button(
            file_frame,
            text="Copy Path",
            command=lambda value=path_var: self._copy_path(value),
        ).grid(
            row=5,
            column=1,
            sticky="e",
            pady=(10, 0),
        )
        self.bind(
            "<Escape>",
            lambda event: self.destroy(),
        )
        return file_frame

    def _copy_path(self, path_var):
        path = path_var.get()
        if path in {"—", "Not Available"}:
            return
        self.clipboard_clear()
        self.clipboard_append(path)

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

    def _populate_record(
        self,
        record,
        path_var,
        modified_var,
        size_var,
        type_var,
        extension_var,
    ):
        if record is None:
            path_var.set("Not Available")
            modified_var.set("Not Available")
            size_var.set("—")
            type_var.set("Not Available")
            extension_var.set("Not Available")
            return

        path_var.set(record.absolute_path)
        extension = Path(record.absolute_path).suffix.lower()
        extension_var.set(extension or "No extension")

        modified_var.set(
            format_timestamp(
                record.modified_time
            )
        )

        size_var.set(
            format_bytes(
                record.size
            )
        )
        type_var.set(format_file_type(record.absolute_path))

    def _derive_file_type(self) -> str:
        if not self.result or not (self.result.local_record or self.result.server_record):
            return "Unknown"

        record = self.result.local_record or self.result.server_record
        if record is None:
            return "Unknown"
        return format_file_type(record.absolute_path)
