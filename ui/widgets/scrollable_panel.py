"""Bounded optional settings area that leaves primary workflow controls visible."""

import tkinter as tk
from tkinter import ttk

from ui.theme import SURFACE


class ScrollablePanel(ttk.Frame):
    def __init__(self, parent, *, height=190):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0,
                                background=SURFACE, takefocus=False)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.canvas)
        self._content_id = self.canvas.create_window(0, 0, window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._content_changed)
        self.canvas.bind("<Configure>", self._resize_content)
        # Scope these bindings to this toplevel and descendants of this panel;
        # do not steal combobox-list or other window scrolling.
        parent.bind("<MouseWheel>", self._scroll, add="+")
        parent.bind("<FocusIn>", self._reveal_focus, add="+")

    def _contains(self, widget):
        while widget is not None:
            if widget is self:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _content_changed(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event):
        self.canvas.itemconfigure(self._content_id, width=event.width)

    def _scroll(self, event):
        if self._contains(event.widget):
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

    def _reveal_focus(self, event):
        if not self._contains(event.widget) or not self.winfo_ismapped():
            return
        top = event.widget.winfo_rooty() - self.content.winfo_rooty()
        bottom = top + event.widget.winfo_height()
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + self.canvas.winfo_height()
        if top < visible_top:
            self.canvas.yview_moveto(top / max(1, self.content.winfo_height()))
        elif bottom > visible_bottom:
            self.canvas.yview_moveto(
                (bottom - self.canvas.winfo_height()) / max(1, self.content.winfo_height())
            )
