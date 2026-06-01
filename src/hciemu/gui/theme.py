"""Dark theme palette and ttk style definitions for HCIEMU GUI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ── Palette ───────────────────────────────────────────────────────────────────
SIDEBAR_BG       = "#181818"
SIDEBAR_HOVER    = "#2a2d2e"
SIDEBAR_SEL      = "#37373d"
SIDEBAR_SEL_TEXT = "#ffffff"
SIDEBAR_TEXT     = "#9da1a6"

BG           = "#1e1e1e"
CARD_BG      = "#252526"
CARD_BORDER  = "#313131"

TEXT         = "#d4d4d4"
TEXT_MUTED   = "#9da1a6"

ACCENT       = "#0e639c"
ACCENT_HOVER = "#1177bb"
ACCENT_DIM   = "#244f70"

DANGER       = "#a1260d"
DANGER_HOVER = "#c2391a"
DANGER_DIM   = "#5c2318"

SUCCESS      = "#2f7d32"
SUCCESS_HOVER= "#3b9140"
SUCCESS_DIM  = "#1f4e21"

WARNING      = "#a6751a"

NEUTRAL      = "#3c3c3c"
NEUTRAL_HOVER= "#4a4a4a"

ENTRY_BG     = "#3c3c3c"
ENTRY_FG     = TEXT
ENTRY_SELECT = "#094771"

LOG_BG       = "#1b1b1c"
LOG_FG       = TEXT
LOG_TIMESTAMP= "#7f848e"


def apply_theme(root: tk.Tk) -> None:
    """Apply the dark theme to all ttk widgets on *root*."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # ── Global defaults ────────────────────────────────────────────────
    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        font=("Segoe UI", 10),
        borderwidth=0,
        relief="flat",
    )

    # ── Frames ────────────────────────────────────────────────────────
    style.configure("App.TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD_BG)
    style.configure("Sidebar.TFrame", background=SIDEBAR_BG)

    # ── Labels ────────────────────────────────────────────────────────
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT)
    style.configure("Card.Muted.TLabel", background=CARD_BG, foreground=TEXT_MUTED)
    style.configure("Sidebar.TLabel", background=SIDEBAR_BG, foreground=SIDEBAR_TEXT)
    style.configure("PageTitle.TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI Semibold", 16))
    style.configure("PageSub.TLabel", background=BG, foreground=TEXT_MUTED,
                    font=("Segoe UI", 10))

    # ── LabelFrames ───────────────────────────────────────────────────
    style.configure(
        "Card.TLabelframe",
        background=CARD_BG,
        bordercolor=CARD_BORDER,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=CARD_BG,
        foreground=TEXT_MUTED,
        font=("Segoe UI Semibold", 10),
    )

    # ── Entry ─────────────────────────────────────────────────────────
    style.configure(
        "TEntry",
        fieldbackground=ENTRY_BG,
        foreground=ENTRY_FG,
        insertcolor=TEXT,
          bordercolor=CARD_BORDER,
          lightcolor=CARD_BORDER,
          darkcolor=CARD_BORDER,
          padding=7,
    )
    style.map("TEntry",
              fieldbackground=[("readonly", CARD_BG), ("disabled", CARD_BG), ("focus", ENTRY_BG)],
              foreground=[("disabled", TEXT_MUTED)])

    # ── Combobox ──────────────────────────────────────────────────────
    style.configure(
        "TCombobox",
        fieldbackground=ENTRY_BG,
        foreground=ENTRY_FG,
        selectbackground=ENTRY_SELECT,
        selectforeground="#ffffff",
        arrowcolor=TEXT_MUTED,
        bordercolor=CARD_BORDER,
        lightcolor=CARD_BORDER,
        darkcolor=CARD_BORDER,
        padding=6,
    )
    style.map("TCombobox",
              fieldbackground=[("readonly", ENTRY_BG)],
              selectbackground=[("readonly", ACCENT)])

    # ── Checkbutton ───────────────────────────────────────────────────
    style.configure("TCheckbutton", background=CARD_BG, foreground=TEXT,
                    indicatorcolor=ENTRY_BG, indicatordiameter=14)
    style.map("TCheckbutton",
              background=[("active", CARD_BG)],
              foreground=[("active", TEXT)],
              indicatorcolor=[("selected", ACCENT), ("pressed", ACCENT_HOVER)])

    # ── Buttons ───────────────────────────────────────────────────────
    style.configure("TButton", padding=[12, 7], relief="flat", borderwidth=0,
                    font=("Segoe UI Semibold", 10))

    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
    style.map("Accent.TButton",
              background=[("pressed", ACCENT_HOVER), ("active", ACCENT_HOVER),
                          ("disabled", ACCENT_DIM)],
              foreground=[("disabled", "#9060c8")])

    style.configure("Danger.TButton", background=DANGER, foreground="#ffffff")
    style.map("Danger.TButton",
              background=[("pressed", DANGER_HOVER), ("active", DANGER_HOVER),
                          ("disabled", DANGER_DIM)],
              foreground=[("disabled", "#a05050")])

    style.configure("Success.TButton", background=SUCCESS, foreground="#ffffff")
    style.map("Success.TButton",
              background=[("pressed", SUCCESS_HOVER), ("active", SUCCESS_HOVER),
                          ("disabled", SUCCESS_DIM)],
              foreground=[("disabled", "#3a9070")])

    style.configure("Neutral.TButton", background=NEUTRAL, foreground=TEXT)
    style.map("Neutral.TButton",
              background=[("pressed", NEUTRAL_HOVER), ("active", NEUTRAL_HOVER)])

    # ── Scrollbar ─────────────────────────────────────────────────────
    style.configure("TScrollbar", background=NEUTRAL, troughcolor=BG,
                    arrowcolor=TEXT_MUTED, borderwidth=0, relief="flat",
                    arrowsize=12)
    style.map("TScrollbar",
              background=[("active", NEUTRAL_HOVER), ("pressed", NEUTRAL_HOVER)])

    # ── Treeview ──────────────────────────────────────────────────────
    style.configure("Treeview",
                    background=CARD_BG,
                    fieldbackground=CARD_BG,
                    foreground=TEXT,
                    rowheight=26,
                    borderwidth=0,
                    font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                    background=SIDEBAR_BG,
                    foreground=TEXT_MUTED,
                    font=("Segoe UI Semibold", 10),
                    relief="flat",
                    borderwidth=0)
    style.map("Treeview",
              background=[("selected", ENTRY_SELECT)],
              foreground=[("selected", "#ffffff")])
    style.map("Treeview.Heading",
              background=[("active", SIDEBAR_HOVER)])

    # ── Separator ─────────────────────────────────────────────────────
    style.configure("TSeparator", background=CARD_BORDER)

    # ── Notebook (used in Toplevels) ──────────────────────────────────
    style.configure("TNotebook", background=CARD_BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=[14, 8], background=CARD_BG,
                    foreground=TEXT_MUTED, font=("Segoe UI Semibold", 10))
    style.map("TNotebook.Tab",
              background=[("selected", BG), ("active", SIDEBAR_HOVER)],
              foreground=[("selected", ACCENT)])
