"""Modal progress for read-only provider work; Tk stays on the owning thread."""
import queue
import threading
import tkinter as tk
from tkinter import ttk


class ReadonlyTaskDialog(tk.Toplevel):
    def __init__(self, parent, operation):
        super().__init__(parent)
        self.title("Comparing folders")
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.error = None
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        ttk.Label(self, text="Comparing files. No files are being changed.", padding=24).pack()
        progress = ttk.Progressbar(self, mode="indeterminate")
        progress.pack(fill="x", padx=24, pady=(0, 24))
        progress.start()
        results = queue.Queue()
        def worker():
            try:
                results.put((True, operation()))
            except Exception:
                results.put((False, "OneDrive comparison failed. Check access and reconnect, then compare again."))
        threading.Thread(target=worker, daemon=True).start()
        def poll():
            try:
                success, value = results.get_nowait()
            except queue.Empty:
                self.after(50, poll)
                return
            if success:
                self.result = value
            else:
                self.error = value
            progress.stop()
            self.grab_release()
            self.destroy()
        self.after(50, poll)
