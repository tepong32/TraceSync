"""Non-blocking setup presentation; service owns auth, browsing and persistence."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ui.theme import AMBER
from core.onedrive_setup_service import OneDriveSetupError, OneDriveSetupService


class OneDriveSetupDialog(tk.Toplevel):
    def __init__(self, parent, service=None):
        super().__init__(parent)
        self.service = service or OneDriveSetupService()
        self.title("OneDrive Folder Pair — setup preview")
        self.geometry("720x640")
        self.minsize(640, 580)
        self.transient(parent)
        self.grab_set()
        self._queue = queue.Queue()
        self._busy = False
        self._saving = False
        self._closed = False
        self._poll_id = None
        self._editing = None
        self._path = []
        self._folders = []
        self.selected_connection = None
        self.account = tk.StringVar(value="No account connected")
        self.location = tk.StringVar(value="Choose a cloud folder after connecting")
        self.name = tk.StringVar()
        self.local = tk.StringVar()
        self.status = tk.StringVar(value="Next: connect your personal Microsoft account.")
        self.saved_name = tk.StringVar()
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)
        ttk.Label(body, text="Connect account → Choose folder → Save Folder Pair",
                  style="WorkflowTitle.TLabel", padding=10).grid(row=0, column=0, sticky="ew")
        ttk.Label(body, text="Development preview: reviewed new-file copies only. Existing files are never replaced.",
                  wraplength=650, foreground=AMBER).grid(row=1, column=0, sticky="w", pady=10)
        self.connect_button = ttk.Button(body, text="Connect account", command=self._connect,
                                         style="GuideNext.TButton")
        self.connect_button.grid(row=2, column=0, sticky="w")
        ttk.Label(body, textvariable=self.account).grid(row=3, column=0, sticky="w", pady=8)
        browser = ttk.LabelFrame(body, text="Choose OneDrive folder", padding=8)
        browser.grid(row=4, column=0, sticky="nsew")
        browser.columnconfigure(0, weight=1)
        browser.rowconfigure(1, weight=1)
        ttk.Label(browser, textvariable=self.location, wraplength=580).grid(row=0, column=0, columnspan=3, sticky="w")
        self.folders = tk.Listbox(browser, exportselection=False, height=7)
        self.folders.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=8)
        scroll = ttk.Scrollbar(browser, command=self.folders.yview)
        scroll.grid(row=1, column=2, sticky="ns")
        self.folders.configure(yscrollcommand=scroll.set)
        self.folders.bind("<Double-1>", lambda event: self._open())
        self.open_button = ttk.Button(browser, text="Open selected folder", command=self._open)
        self.open_button.grid(row=2, column=0, sticky="w")
        self.up_button = ttk.Button(browser, text="Up", command=self._up)
        self.up_button.grid(row=2, column=1, sticky="e")
        editor = ttk.Frame(body)
        editor.grid(row=5, column=0, sticky="ew", pady=10)
        editor.columnconfigure(1, weight=1)
        ttk.Label(editor, text="Local folder").grid(row=0, column=0, sticky="w")
        self.local_entry = ttk.Entry(editor, textvariable=self.local)
        self.local_entry.grid(row=0, column=1, sticky="ew", padx=8)
        self.browse_button = ttk.Button(editor, text="Browse...", command=self._browse)
        self.browse_button.grid(row=0, column=2)
        ttk.Label(editor, text="Pair name").grid(row=1, column=0, sticky="w", pady=8)
        self.name_entry = ttk.Entry(editor, textvariable=self.name)
        self.name_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=8)
        self.save_button = ttk.Button(body, text="Save pair with current cloud folder", command=self._save,
                                      style="GuideNext.TButton")
        self.save_button.grid(row=6, column=0, sticky="w")
        self.use_button = ttk.Button(body, text="Use saved pair", command=self._use_pair, style="GuideNext.TButton")
        self.use_button.grid(row=6, column=0, sticky="e")
        ttk.Label(body, textvariable=self.status, wraplength=650).grid(row=7, column=0, sticky="w", pady=8)
        saved = ttk.LabelFrame(body, text="Saved OneDrive pairs", padding=4)
        saved.grid(row=8, column=0, sticky="ew")
        saved.columnconfigure(0, weight=1)
        self.saved_combo = ttk.Combobox(saved, textvariable=self.saved_name, state="readonly", width=18)
        self.saved_combo.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.saved_combo.bind("<<ComboboxSelected>>", lambda event: self._controls())
        self.reopen_button = ttk.Button(saved, text="Open", command=self._restore)
        self.reopen_button.grid(row=0, column=1)
        self.reconnect_button = ttk.Button(saved, text="Reconnect", command=lambda: self._restore(interactive=True))
        self.reconnect_button.grid(row=0, column=2)
        self.disconnect_button = ttk.Button(saved, text="Disconnect", command=self._disconnect)
        self.disconnect_button.grid(row=0, column=3)
        self.edit_button = ttk.Button(saved, text="Edit", command=self._edit)
        self.edit_button.grid(row=1, column=1, pady=(4, 0))
        self.delete_button = ttk.Button(saved, text="Delete", command=self._delete)
        self.delete_button.grid(row=1, column=2, pady=(4, 0))
        self.cancel_edit_button = ttk.Button(saved, text="Cancel edit", command=self._cancel_edit)
        self.cancel_edit_button.grid(row=1, column=3, pady=(4, 0))
        self.close_button = ttk.Button(body, text="Close", command=self._close)
        self.close_button.grid(row=9, column=0, sticky="e", pady=(8, 0))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda event: self._close())
        self._show_saved()
        self._controls()

    def _show_saved(self):
        pairs = self.service.saved_pairs()
        names = [pair["name"] for pair in pairs]
        self.saved_combo.configure(values=names)
        if self.saved_name.get() not in names:
            self.saved_name.set(names[0] if names else "")

    def _controls(self):
        self.connect_button.configure(state="disabled" if self._busy else "normal",
                                      style="TButton" if self._path else "GuideNext.TButton")
        for widget in (self.open_button, self.save_button):
            widget.configure(state="normal" if self._path and not self._busy else "disabled")
        self.up_button.configure(state="normal" if len(self._path) > 1 and not self._busy else "disabled")
        for widget in (self.browse_button, self.local_entry, self.name_entry):
            widget.configure(state="disabled" if self._busy else "normal")
        self.close_button.configure(state="disabled" if self._saving else "normal")
        self.saved_combo.configure(state="disabled" if self._busy or self._editing else "readonly")
        for widget in (self.reopen_button, self.reconnect_button, self.disconnect_button):
            widget.configure(state="normal" if self.saved_name.get() and not self._busy and not self._editing else "disabled")
        self.use_button.configure(state="normal" if self.saved_name.get() and not self._busy and not self._editing else "disabled")
        for widget in (self.edit_button, self.delete_button):
            widget.configure(state="normal" if self.saved_name.get() and not self._busy else "disabled")
        self.cancel_edit_button.configure(state="normal" if self._editing and not self._busy else "disabled")
        self.save_button.configure(text="Save changes" if self._editing else "Save pair with current cloud folder",
            state="normal" if (self._editing or self._path) and not self._busy else "disabled")

    def _edit(self):
        if self._busy:
            return
        pair = next((pair for pair in self.service.saved_pairs() if pair["name"] == self.saved_name.get()), None)
        if pair is None:
            return
        self._editing = pair
        self._path, self._folders = [], []
        self.folders.delete(0, "end")
        self.name.set(pair["name"])
        self.local.set(pair["local_folder"])
        self.account.set(pair["server_endpoint"]["account_name"])
        self.location.set(pair["server_endpoint"]["folder_name"] + " (saved; not verified)")
        self.status.set("Editing saved pair. Rename or change local folder offline. Connect the same account to choose a different cloud folder.")
        self._controls()

    def _cancel_edit(self):
        if self._busy:
            return
        self._editing = None
        self._path, self._folders = [], []
        self.folders.delete(0, "end")
        self.name.set("")
        self.local.set("")
        self.location.set("No cloud folder selected")
        self.account.set("No account selected")
        self.status.set("Edit cancelled. Saved definitions are unchanged.")
        self._controls()

    def _delete(self):
        if self._busy:
            return
        pair = next((pair for pair in self.service.saved_pairs() if pair["name"] == self.saved_name.get()), None)
        if pair is None or not messagebox.askyesno("Delete saved Folder Pair?",
                f"Delete '{pair['name']}' from saved pairs? Local and cloud files and saved sign-in are kept.", parent=self):
            return
        service = self.service
        self._saving = True
        def deleted(_result):
            self._cancel_edit()
            self._show_saved()
            self.status.set("Saved pair deleted. Files and saved sign-in are unchanged.")
        self._run(lambda: service.delete_pair(pair), deleted, "Deleting saved pair…")

    def _use_pair(self):
        if self._busy or self._editing or not self.saved_name.get():
            return
        service, name = self.service, self.saved_name.get()
        def ready(connection):
            self.selected_connection = connection
            self._close()
        self._run(lambda: service.prepare_comparison(name), ready, "Verifying account before comparison…")

    def _run(self, operation, completed, message):
        if self._busy:
            return
        self._busy = True
        self.status.set(message)
        self._controls()
        result_queue = self._queue
        def worker():
            try:
                result_queue.put((True, operation()))
            except OneDriveSetupError as error:
                result_queue.put((False, str(error)))
            except Exception:
                result_queue.put((False, "Setup could not finish. Check your connection or settings and try again."))
        threading.Thread(target=worker, daemon=True).start()
        self._poll_id = self.after(50, lambda: self._poll(completed))

    def _poll(self, completed):
        if self._closed:
            return
        try:
            success, result = self._queue.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(50, lambda: self._poll(completed))
            return
        self._poll_id = None
        self._busy = self._saving = False
        if success:
            completed(result)
        else:
            if not self._path:
                self.account.set("No account connected")
            self.status.set(result)
        if not self._closed:
            self._controls()

    def _connect(self):
        if self._busy:
            return
        self._path = []
        self._folders = []
        self.folders.delete(0, "end")
        self.account.set("Connecting…")
        self.location.set("No cloud folder selected")
        service = self.service
        def connect():
            root = service.connect()
            return root, service.list_folders(root.id)
        def connected(result):
            root, folders = result
            self.account.set(self.service.account_name)
            self._display([root], folders)
        self._run(connect, connected, "Complete sign-in in your browser. Closing setup discards folder selection; browser sign-in may still finish.")

    def _display(self, path, folders):
        self._path, self._folders = path, folders
        self.location.set(" / ".join(folder.name for folder in path))
        self.folders.delete(0, "end")
        for folder in folders:
            self.folders.insert("end", folder.name)
        self.status.set("Next: open a folder, or use this folder; choose a local folder and a pair name.")

    def _restore(self, *, interactive=False):
        if self._busy or not self.saved_name.get():
            return
        name = self.saved_name.get()
        self._path, self._folders = [], []
        self.folders.delete(0, "end")
        self.location.set("Verifying saved account and folder…")
        self.account.set("Checking saved account…")
        def restored(result):
            pair, folder, children = result
            self.account.set(self.service.account_name)
            self.local.set(pair["local_folder"])
            self.name.set(pair["name"])
            self._display([folder], children)
            self.status.set("Saved pair verified. Choose Use saved pair to compare and review new-file copies.")
        service = self.service
        self._run(lambda: service.restore_pair(name, interactive=interactive), restored,
                  "Reconnect the saved account in your browser…" if interactive else "Checking saved sign-in and folder access…")

    def _disconnect(self):
        if self._busy or not self.saved_name.get():
            return
        if not messagebox.askyesno("Disconnect Microsoft account?",
                                   "Remove this account's saved sign-in on this device? All pairs using it will need to reconnect. "
                                   "Saved pairs and cloud files are kept; browser sign-in is unchanged.", parent=self):
            return
        name = self.saved_name.get()
        self._path, self._folders = [], []
        self.folders.delete(0, "end")
        self.account.set("No account connected")
        self.location.set("No cloud folder selected")
        self._saving = True
        service = self.service
        self._run(lambda: service.disconnect_pair(name),
                  lambda result: self.status.set("Saved sign-in removed. Reconnect before opening this account's pairs."),
                  "Removing the saved sign-in…")

    def _navigate(self, path):
        service = self.service
        self._run(lambda: service.list_folders(path[-1].id),
                  lambda folders: self._display(path, folders), "Opening folder…")

    def _open(self):
        selected = self.folders.curselection()
        if selected and not self._busy and self._path:
            self._navigate([*self._path, self._folders[selected[0]]])

    def _up(self):
        if len(self._path) > 1 and not self._busy:
            self._navigate(self._path[:-1])

    def _browse(self):
        selected = filedialog.askdirectory(parent=self)
        if selected:
            self.local.set(selected)

    def _save(self):
        if self._busy or (not self._path and not self._editing):
            return
        name, local = self.name.get(), self.local.get()
        folder_id = self._path[-1].id if self._path else None
        expected = self._editing
        self._saving = True
        def saved(pair):
            self.status.set(f"Saved '{pair['name']}'. Choose Use saved pair to compare before copying.")
            self._editing = None
            self._show_saved()
            self.saved_name.set(pair["name"])
        service = self.service
        operation = (lambda: service.edit_pair(expected, name, local, folder_id)) if expected else (lambda: service.save_pair(name, local, folder_id))
        self._run(operation, saved, "Verifying folder and saving pair…")

    def _close(self):
        if self._saving:
            return
        self._closed = True
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
        self.grab_release()
        self.destroy()
