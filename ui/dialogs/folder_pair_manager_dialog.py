import ntpath
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class FolderPairManagerDialog(tk.Toplevel):
    """Edit named folder relationships without scanning or copying files."""

    def __init__(
        self,
        parent,
        pairs,
        *,
        current_local="",
        current_server="",
        selected_name="",
        start_new=False,
    ):
        super().__init__(parent)
        self.title("Folder Pairs")
        self.geometry("760x430")
        self.minsize(680, 380)
        self.transient(parent)
        self.grab_set()

        self.pairs = [dict(pair) for pair in pairs]
        self.confirmed = False
        self._selected_index = None
        self._suggested_name = None
        self._current_local = current_local.strip()
        self._current_server = current_server.strip()

        self.name_var = tk.StringVar()
        self.local_var = tk.StringVar()
        self.server_var = tk.StringVar()

        self._build_ui()
        self._populate_list()
        if start_new or not self._select_pair_by_name(selected_name):
            self._start_new_pair()

        self.bind("<Escape>", lambda _event: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _folder_name(folder_path: str) -> str:
        if not folder_path:
            return ""
        normalized_path = folder_path.rstrip("\\/")
        folder_name = ntpath.basename(normalized_path)
        if folder_name:
            return folder_name

        drive, _tail = ntpath.splitdrive(normalized_path)
        if drive.startswith("\\\\"):
            return drive.rstrip("\\/").rsplit("\\", 1)[-1]
        return drive.rstrip(":")

    @classmethod
    def _suggest_name(cls, local_folder: str, server_folder: str) -> str:
        local_name = cls._folder_name(local_folder)
        server_name = cls._folder_name(server_folder)
        if local_name and server_name and local_name.casefold() == server_name.casefold():
            return local_name
        if local_name and server_name:
            return f"{local_name} ↔ {server_name}"
        return local_name or server_name or "New Folder Pair"

    def _build_ui(self):
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(
            body,
            text="Saved Folder Pairs",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(
            body,
            text="Save a Local ↔ Server relationship once, then select it from the main window.",
            wraplength=500,
            justify="left",
        ).grid(row=0, column=1, sticky="w", padx=(14, 0), pady=(0, 6))

        list_frame = ttk.Frame(body)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        self.pair_list = tk.Listbox(list_frame, width=30, exportselection=False)
        self.pair_list.grid(row=0, column=0, sticky="nsew")
        list_scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.pair_list.yview,
        )
        list_scrollbar.grid(row=0, column=1, sticky="ns")
        self.pair_list.configure(yscrollcommand=list_scrollbar.set)
        self.pair_list.bind("<<ListboxSelect>>", self._on_pair_selected)

        editor = ttk.LabelFrame(body, text="Folder Pair", padding=10)
        editor.grid(row=1, column=1, sticky="nsew", padx=(14, 0))
        editor.columnconfigure(1, weight=1)

        ttk.Label(editor, text="Name:").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.name_entry = ttk.Entry(editor, textvariable=self.name_var)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(editor, text="Local Folder:").grid(row=1, column=0, sticky="w", pady=(0, 8))
        local_frame = ttk.Frame(editor)
        local_frame.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        local_frame.columnconfigure(0, weight=1)
        ttk.Entry(local_frame, textvariable=self.local_var).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )
        ttk.Button(local_frame, text="Browse", command=self._browse_local).grid(row=0, column=1)

        ttk.Label(editor, text="Server Folder:").grid(row=2, column=0, sticky="w", pady=(0, 8))
        server_frame = ttk.Frame(editor)
        server_frame.grid(row=2, column=1, sticky="ew", pady=(0, 8))
        server_frame.columnconfigure(0, weight=1)
        ttk.Entry(server_frame, textvariable=self.server_var).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 6),
        )
        ttk.Button(server_frame, text="Browse", command=self._browse_server).grid(row=0, column=1)

        ttk.Label(
            editor,
            text="A folder pair only remembers the two paths. Selecting one never copies files by itself.",
            foreground="#4b5563",
            wraplength=500,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        button_frame = ttk.Frame(body)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(button_frame, text="New", command=self._start_new_pair).pack(side="left")
        ttk.Button(button_frame, text="Save", command=self._save_pair).pack(side="left", padx=(6, 0))
        ttk.Button(button_frame, text="Delete", command=self._delete_pair).pack(side="left", padx=(6, 0))
        ttk.Button(button_frame, text="Close", command=self._close).pack(side="right")

    def _populate_list(self):
        self.pair_list.delete(0, tk.END)
        for pair in self.pairs:
            self.pair_list.insert(tk.END, pair["name"])

    def _select_pair_by_name(self, selected_name):
        if not selected_name:
            return False
        selected_key = selected_name.casefold()
        for index, pair in enumerate(self.pairs):
            if pair["name"].casefold() == selected_key:
                self.pair_list.selection_set(index)
                self.pair_list.activate(index)
                self.pair_list.see(index)
                self._load_pair(index)
                return True
        return False

    def _start_new_pair(self):
        self._selected_index = None
        self.pair_list.selection_clear(0, tk.END)
        self._suggested_name = self._suggest_name(
            self._current_local,
            self._current_server,
        )
        self.name_var.set(self._suggested_name)
        self.local_var.set(self._current_local)
        self.server_var.set(self._current_server)
        self.name_entry.focus_set()
        self.name_entry.selection_range(0, tk.END)

    def _load_pair(self, index):
        self._selected_index = index
        self._suggested_name = None
        pair = self.pairs[index]
        self.name_var.set(pair["name"])
        self.local_var.set(pair["local_folder"])
        self.server_var.set(pair["server_folder"])

    def _on_pair_selected(self, _event=None):
        selection = self.pair_list.curselection()
        if selection:
            self._load_pair(selection[0])

    def _validate_fields(self):
        name = self.name_var.get().strip()
        local_folder = self.local_var.get().strip()
        server_folder = self.server_var.get().strip()
        if not name:
            messagebox.showwarning(
                "Missing Name",
                "Please give this folder pair a name.",
                parent=self,
            )
            return None
        if not local_folder or not server_folder:
            messagebox.showwarning(
                "Missing Folder",
                "Please select both a Local Folder and a Server Folder.",
                parent=self,
            )
            return None
        for index, pair in enumerate(self.pairs):
            if index == self._selected_index:
                continue
            if pair["name"].casefold() == name.casefold():
                messagebox.showwarning(
                    "Duplicate Name",
                    "A folder pair with this name already exists. Please choose another name.",
                    parent=self,
                )
                return None
        return {
            "name": name,
            "local_folder": local_folder,
            "server_folder": server_folder,
        }

    def _save_pair(self):
        pair = self._validate_fields()
        if pair is None:
            return

        if self._selected_index is None:
            self.pairs.append(pair)
            self._selected_index = len(self.pairs) - 1
        else:
            self.pairs[self._selected_index] = pair
        self._suggested_name = None
        self._populate_list()
        self.pair_list.selection_set(self._selected_index)
        self.pair_list.activate(self._selected_index)
        self.pair_list.see(self._selected_index)
        self.confirmed = True

    def _delete_pair(self):
        if self._selected_index is None:
            return
        pair = self.pairs[self._selected_index]
        if not messagebox.askyesno(
            "Delete Folder Pair",
            f"Delete the saved folder pair '{pair['name']}'?\n\nNo files will be changed.",
            parent=self,
        ):
            return
        del self.pairs[self._selected_index]
        self.confirmed = True
        self._populate_list()
        self._start_new_pair()

    def _update_suggested_name(self):
        current_name = self.name_var.get().strip()
        if current_name and current_name != self._suggested_name:
            return
        self._suggested_name = self._suggest_name(
            self.local_var.get().strip(),
            self.server_var.get().strip(),
        )
        self.name_var.set(self._suggested_name)

    def _browse_local(self):
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self.local_var.set(folder)
            if self._selected_index is None:
                self._update_suggested_name()

    def _browse_server(self):
        folder = filedialog.askdirectory(parent=self)
        if folder:
            self.server_var.set(folder)
            if self._selected_index is None:
                self._update_suggested_name()

    def _close(self):
        self.grab_release()
        self.destroy()
