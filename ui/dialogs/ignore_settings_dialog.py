import tkinter as tk
from tkinter import ttk


class IgnoreSettingsDialog(tk.Toplevel):
    """Simple, non-technical dialog for managing optional ignore patterns."""

    def __init__(self, parent, patterns: list[str] | None = None) -> None:
        super().__init__(parent)
        self.confirmed = False
        self.patterns: list[str] = []
        self._build_ui(patterns or [])
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self, patterns: list[str]) -> None:
        self.title("Ignore Settings")
        self.geometry("520x420")
        self.resizable(False, False)
        self.transient(self.master)
        self.grab_set()

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        self._pattern_count_var = tk.StringVar(value=f"Currently ignoring {len(patterns)} pattern(s).")

        ttk.Label(
            frame,
            text=(
                "Add file and folder patterns you want TraceSync to ignore while comparing."
            ),
            wraplength=480,
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=(
                "Example: \"*.tmp\" to skip temporary files"
            ),
            foreground="#4d4d4d",
        ).pack(anchor="w", pady=(4, 8))

        ttk.Label(frame, textvariable=self._pattern_count_var).pack(anchor="w")
        self._pattern_count_var.set(f"Currently ignoring {len(patterns)} pattern(s).")

        self.pattern_text = tk.Text(
            frame,
            width=62,
            height=14,
            wrap="none",
        )
        self.pattern_text.pack(fill="both", expand=True, pady=(4, 8))
        self.pattern_text.insert("1.0", "\n".join(patterns))
        self.pattern_text.bind("<KeyRelease>", self._update_pattern_count)

        helper = ttk.Label(
            frame,
            text="Use one pattern per line. Blank lines and comments (#) are ignored.",
            foreground="#4d4d4d",
            wraplength=480,
        )
        helper.pack(anchor="w")

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=(12, 0))
        ttk.Button(
            button_frame,
            text="Cancel",
            style="UtilityNeutral.TButton",
            command=self.destroy,
        ).pack(side="right")
        ttk.Button(button_frame, text="Save", command=self._save).pack(side="right", padx=(0, 8))

    def _update_pattern_count(self, _event=None) -> None:
        count = len(self._normalise_patterns())
        self._pattern_count_var.set(f"Currently ignoring {count} pattern(s).")

    def _normalise_patterns(self) -> list[str]:
        raw_text = self.pattern_text.get("1.0", "end-1c")
        patterns: list[str] = []
        for line in raw_text.splitlines():
            pattern = line.strip()
            if not pattern or pattern.startswith("#"):
                continue
            patterns.append(pattern)
        return patterns

    def _save(self) -> None:
        self.patterns = self._normalise_patterns()
        self.confirmed = True
        self.destroy()
