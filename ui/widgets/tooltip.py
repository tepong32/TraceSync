import tkinter as tk


class HoverTooltip:
    """Show concise helper text after the pointer rests on a widget."""

    def __init__(
        self,
        widget,
        text: str,
        *,
        delay_ms: int = 450,
        wraplength: int = 320,
    ) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel_scheduled_show()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_scheduled_show(self) -> None:
        if self._after_id is None:
            return
        try:
            self.widget.after_cancel(self._after_id)
        except tk.TclError:
            pass
        self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None or not self.widget.winfo_exists():
            return

        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        try:
            window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        window.wm_geometry(
            f"+{self.widget.winfo_pointerx() + 14}+{self.widget.winfo_pointery() + 12}"
        )
        tk.Label(
            window,
            text=self.text,
            justify="left",
            wraplength=self.wraplength,
            background="#fff8dc",
            foreground="#1f2937",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            font=("Segoe UI", 9),
        ).pack()
        self._window = window

    def _hide(self, _event=None) -> None:
        self._cancel_scheduled_show()
        if self._window is None:
            return
        try:
            self._window.destroy()
        except tk.TclError:
            pass
        self._window = None
