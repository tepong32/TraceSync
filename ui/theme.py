"""Shared, material-inspired ttk presentation; no workflow or provider policy."""

from tkinter import ttk


SURFACE = "#f5f7f5"
WHITE = "#ffffff"
TEXT = "#23352c"
MUTED = "#59685f"
BORDER = "#d5dfd7"
GREEN = "#176b45"
GREEN_DARK = "#105236"
GREEN_PALE = "#e8f3eb"
AMBER = "#854d0e"
AMBER_PALE = "#fff4d6"


def _button(style, name, *, fill=WHITE, foreground=TEXT, hover=GREEN_PALE,
            pressed="#dce9df", padding=(12, 8), bold=False):
    style.configure(
        name, font=("Segoe UI", 10, "bold" if bold else "normal"),
        padding=padding, background=fill, foreground=foreground,
        bordercolor=BORDER, lightcolor=fill, darkcolor=fill,
        borderwidth=1, relief="flat", focusthickness=2,
        focuscolor=foreground, anchor="center",
    )
    style.map(
        name,
        background=[("disabled", "#edf0ed"), ("pressed", pressed),
                    ("active", hover), ("!disabled", fill)],
        foreground=[("disabled", "#747e77"), ("!disabled", foreground)],
        bordercolor=[("focus", GREEN), ("!focus", BORDER)],
        lightcolor=[("disabled", "#edf0ed"), ("pressed", pressed),
                    ("active", hover), ("!disabled", fill)],
        darkcolor=[("disabled", "#edf0ed"), ("pressed", pressed),
                   ("active", hover), ("!disabled", fill)],
    )


def configure_workflow_styles(style):
    _button(style, "GuideNext.TButton", fill=GREEN, foreground=WHITE,
            hover="#1c7c51", pressed=GREEN_DARK, bold=True)
    _button(style, "GuideCopy.TButton", fill=AMBER_PALE, foreground=AMBER,
            hover="#ffebbb", pressed="#f7df9f", bold=True)
    style.configure("Workflow.TFrame", background=GREEN_PALE)
    style.configure("Workflow.TLabel", background=GREEN_PALE, foreground=GREEN)
    style.configure("WorkflowTitle.TLabel", background=GREEN_PALE,
                    foreground=GREEN, font=("Segoe UI", 9, "bold"))


def configure_theme(window):
    """Use clam so Windows native drawing cannot silently discard accent fills."""
    style = ttk.Style(window)
    style.theme_use("clam")
    window.configure(background=SURFACE)
    style.configure(".", font=("Segoe UI", 10), background=SURFACE,
                    foreground=TEXT, bordercolor=BORDER)
    style.configure("TFrame", background=SURFACE)
    style.configure("TLabel", background=SURFACE, foreground=TEXT)
    style.configure("TLabelframe", background=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, relief="solid")
    style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"),
                    foreground=MUTED, background=SURFACE)
    style.configure("TEntry", padding=(8, 7), fieldbackground=WHITE,
                    bordercolor=BORDER, lightcolor=WHITE, darkcolor=WHITE)
    style.configure("TCombobox", padding=(8, 6), fieldbackground=WHITE,
                    background=WHITE, arrowsize=14, bordercolor=BORDER)
    for name in ("TEntry", "TCombobox"):
        style.map(name, bordercolor=[("focus", GREEN)],
                  fieldbackground=[("disabled", "#edf0ed"), ("!disabled", WHITE)],
                  foreground=[("disabled", "#747e77"), ("!disabled", TEXT)])
    for name in ("TButton", "MediumNeutral.TButton", "UtilityNeutral.TButton"):
        _button(style, name)
    _button(style, "PrimaryNeutral.TButton", bold=True)
    _button(style, "FilterNeutral.TButton", padding=(10, 5))
    _button(style, "ActiveFilter.TButton", fill=GREEN_PALE,
            foreground=GREEN_DARK, padding=(10, 5), bold=True)
    _button(style, "WarningFilter.TButton", fill=AMBER_PALE,
            foreground=AMBER, hover="#ffebbb", padding=(10, 5))
    _button(style, "ActiveWarningFilter.TButton", fill="#f7df9f",
            foreground=AMBER, hover="#ffebbb", padding=(10, 5), bold=True)
    style.configure("Treeview", background=WHITE, fieldbackground=WHITE,
                    foreground=TEXT, rowheight=32, borderwidth=1,
                    lightcolor=BORDER, darkcolor=BORDER)
    style.configure("Treeview.Heading", background="#eaf0eb", foreground=MUTED,
                    font=("Segoe UI", 10, "bold"), padding=(12, 9), relief="flat")
    style.map("Treeview", background=[("selected", GREEN_PALE)],
              foreground=[("selected", GREEN_DARK)])
    style.map("Treeview.Heading", background=[("active", "#dce9df")])
    style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    configure_workflow_styles(style)
    return style
