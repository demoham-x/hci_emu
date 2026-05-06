#!/usr/bin/env python3
"""VS Code-inspired GUI shell for HCIEMU that delegates page logic to pages/."""

from __future__ import annotations

import concurrent.futures
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional

# Support direct script execution: `python src/hciemu/gui/main.py`
if __package__ in (None, ""):
    src_root = Path(__file__).resolve().parents[2]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

from hciemu.gui.backend import AsyncBLEBackend
from hciemu.gui.theme import (
    apply_theme,
    SIDEBAR_BG, SIDEBAR_HOVER, SIDEBAR_SEL, SIDEBAR_SEL_TEXT,
    SIDEBAR_TEXT, BG, CARD_BG, CARD_BORDER, TEXT, TEXT_MUTED,
    ACCENT, LOG_BG, ENTRY_BG, SUCCESS, SUCCESS_DIM, DANGER, DANGER_DIM,
    WARNING, NEUTRAL, NEUTRAL_HOVER,
)

# â”€â”€ Workbench metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_NAV = [
    ("scan",       "S", "Controller + Scan"),
    ("gatt",       "G", "GATT Explorer"),
    ("security",   "Q", "Security"),
    ("bridge",     "B", "Bridge"),
    ("advertiser", "A", "Advertiser"),
    ("settings",   "T", "Settings"),
]

_PAGE_META = {
    key: {"glyph": glyph, "label": label}
    for key, glyph, label in _NAV
}


class _ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(350, self._show)

    def _cancel(self):
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        if self.tip_window is not None or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            bg=CARD_BG,
            fg=TEXT,
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
        )
        label.pack()

    def _hide(self, _event=None):
        self._cancel()
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class HCIEMUGui(tk.Tk):
    """Dark sidebar GUI that hosts all BLE page frames."""

    def __init__(self):
        super().__init__()
        self.title("HCIEMU")
        self.geometry("1240x820")
        self.minsize(1000, 680)
        self.configure(background=BG)
        apply_theme(self)

        # â”€â”€ Shared tk.Vars â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.transport_var = tk.StringVar(value="tcp-client:127.0.0.1:9001")
        self.scan_duration_var = tk.StringVar(value="10")
        self.scan_active_var = tk.BooleanVar(value=True)
        self.scan_duplicates_var = tk.BooleanVar(value=True)
        self.connect_target_var = tk.StringVar()

        self.read_handle_var = tk.StringVar()
        self.write_handle_var = tk.StringVar()
        self.write_value_var = tk.StringVar()

        self.bridge_source_var = tk.StringVar(value="usb:0")
        self.bridge_target_var = tk.StringVar(value="tcp-server:127.0.0.1:9001")
        self.bridge_status_var = tk.StringVar(value="Stopped")
        self.connection_status_var = tk.StringVar(value="Disconnected")
        self.security_pair_var = tk.StringVar(value="Pair: No")
        self.security_auth_var = tk.StringVar(value="Auth: No")

        # Advertiser vars
        self.adv_interval_min_var = tk.StringVar(value="100.0")
        self.adv_interval_max_var = tk.StringVar(value="120.0")
        self.adv_connectable_var = tk.BooleanVar(value=True)
        self.adv_data_hex_var = tk.StringVar(value="020106")
        self.adv_scan_rsp_hex_var = tk.StringVar()
        self.adv_name_enabled_var = tk.BooleanVar(value=True)
        self.adv_custom_name_var = tk.StringVar()
        self.adv_status_var = tk.StringVar(value="Stopped")

        # Settings vars â€” ui_config
        self.cfg_filter_name = tk.StringVar()
        self.cfg_filter_address = tk.StringVar()
        self.cfg_debug_mode = tk.StringVar(value="none")
        self.cfg_auto_restore_cccd = tk.BooleanVar(value=True)
        self.cfg_snoop_enabled = tk.BooleanVar(value=False)
        self.cfg_snoop_ellisys = tk.BooleanVar(value=True)
        self.cfg_snoop_file = tk.BooleanVar(value=True)
        self.cfg_snoop_console = tk.BooleanVar(value=False)
        self.cfg_ellisys_host = tk.StringVar(value="127.0.0.1")
        self.cfg_ellisys_port = tk.StringVar(value="24352")
        self.cfg_ellisys_stream = tk.StringVar(value="primary")
        self.cfg_btsnoop_filename = tk.StringVar()
        # Settings vars â€” smp_config
        self.cfg_io_capability = tk.StringVar(value="KEYBOARD_ONLY")
        self.cfg_mitm = tk.BooleanVar(value=False)
        self.cfg_secure_conn = tk.BooleanVar(value=True)
        self.cfg_bonding = tk.BooleanVar(value=True)
        self.cfg_auto_pair = tk.BooleanVar(value=True)
        self.cfg_auto_encrypt = tk.BooleanVar(value=True)
        self.cfg_min_key = tk.StringVar(value="7")
        self.cfg_max_key = tk.StringVar(value="16")

        self.backend: Optional[AsyncBLEBackend] = None
        self._pages: Dict[str, tk.Frame] = {}
        self._nav_labels: Dict[str, tk.Label] = {}
        self._activity_buttons: Dict[str, tk.Label] = {}
        self._active_page: str = ""
        self._editor_tab_var = tk.StringVar(value="")
        self._editor_context_var = tk.StringVar(value="")
        self._active_panel_var = tk.StringVar(value="scan")
        self._conn_status_value_label: Optional[tk.Label] = None
        self._sidebar_conn_status_label: Optional[tk.Label] = None
        self._bridge_status_label: Optional[tk.Label] = None
        self._adv_status_label: Optional[tk.Label] = None
        self._pair_status_label: Optional[tk.Label] = None
        self._auth_status_label: Optional[tk.Label] = None
        self._backend_toggle_btn = None
        self._disconnect_btn = None

        self.adv_status_var.trace_add("write", self._on_adv_status_var_changed)
        self.bridge_status_var.trace_add("write", self._on_bridge_status_var_changed)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # â”€â”€ Layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_ui(self) -> None:
        # Lazy imports to avoid circular dependency
        from hciemu.gui.pages.scan import ScanPage
        from hciemu.gui.pages.gatt import GATTPage
        from hciemu.gui.pages.security import SecurityPage
        from hciemu.gui.pages.bridge import BridgePage
        from hciemu.gui.pages.advertiser import AdvertiserPage
        from hciemu.gui.pages.settings import SettingsPage

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)   # header
        self.rowconfigure(1, weight=0)   # status bar
        self.rowconfigure(2, weight=1)   # paned area

        # Header bar
        hdr = tk.Frame(self, background=SIDEBAR_BG, height=64, highlightthickness=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.columnconfigure(1, weight=1)

        brand = tk.Frame(hdr, background=SIDEBAR_BG)
        brand.grid(row=0, column=0, sticky="w", padx=(18, 22))
        tk.Label(brand, text="HCIEMU", font=("Segoe UI Semibold", 15),
                 bg=SIDEBAR_BG, fg=TEXT).pack(anchor="w")
        tk.Label(brand, text="BLE workbench", font=("Segoe UI", 9),
                 bg=SIDEBAR_BG, fg=TEXT_MUTED).pack(anchor="w")

        transport_group = tk.Frame(hdr, background=SIDEBAR_BG)
        transport_group.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=10)
        transport_group.columnconfigure(1, weight=1)
        tk.Label(transport_group, text="TRANSPORT", bg=SIDEBAR_BG,
                 fg=TEXT_MUTED, font=("Segoe UI Semibold", 8)).grid(
                     row=0, column=0, sticky="w", padx=(0, 10))
        tk.Entry(transport_group, textvariable=self.transport_var,
                 bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=CARD_BORDER, highlightcolor=ACCENT).grid(
                     row=0, column=1, sticky="ew", ipady=7)

        bar = tk.Frame(self, background=CARD_BG, height=56, highlightthickness=1,
                       highlightbackground=CARD_BORDER)
        bar.grid(row=1, column=0, sticky="ew", padx=14, pady=(10, 0))
        bar.grid_propagate(False)
        bar.columnconfigure(0, weight=1)

        status_row = tk.Frame(bar, background=CARD_BG)
        status_row.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        status_row.columnconfigure(0, weight=1)

        status_left = tk.Frame(status_row, background=CARD_BG)
        status_left.grid(row=0, column=0, sticky="w")

        self._conn_status_value_label = self._make_status_chip(
            status_left, self.connection_status_var, NEUTRAL, "Connection status"
        )
        self._pair_status_label = self._make_status_chip(
            status_left, self.security_pair_var, NEUTRAL, "Pairing / bonding status"
        )
        self._auth_status_label = self._make_status_chip(
            status_left, self.security_auth_var, NEUTRAL, "Authentication / encryption status"
        )
        self._adv_status_label = self._make_status_chip(
            status_left, self.adv_status_var, DANGER_DIM, "Advertising status"
        )
        self._bridge_status_label = self._make_status_chip(
            status_left, self.bridge_status_var, DANGER_DIM, "Bridge process status"
        )

        actions = tk.Frame(status_row, background=CARD_BG)
        actions.grid(row=0, column=1, sticky="e")

        self._backend_toggle_btn = self._make_action_button(
            actions,
            "Backend",
            self.toggle_backend,
            SUCCESS,
            SUCCESS,
            "Start backend",
        )
        self._make_action_separator(actions)
        self._disconnect_btn = self._make_action_button(
            actions,
            "Disconnect",
            self.disconnect_device,
            NEUTRAL,
            NEUTRAL_HOVER,
            "Disconnect current device",
        )
        self._disconnect_btn.configure(state=tk.DISABLED)
        self._make_action_separator(actions)
        self._make_action_button(
            actions,
            "Adv On",
            self.start_advertising_quick,
            ACCENT,
            ACCENT,
            "Start advertising",
        )
        self._make_action_button(
            actions,
            "Adv Off",
            self.stop_advertising_quick,
            DANGER,
            DANGER,
            "Stop advertising",
        )
        self._make_action_separator(actions)
        self._make_action_button(
            actions,
            "Bridge On",
            self.start_bridge_quick,
            SUCCESS,
            SUCCESS,
            "Start HCI bridge",
        )
        self._make_action_button(
            actions,
            "Bridge Off",
            self.stop_bridge_quick,
            DANGER,
            DANGER,
            "Stop HCI bridge",
        )
        self._make_action_separator(actions)
        self._make_action_button(
            actions,
            "Pair",
            self.pair_encrypt_quick,
            ACCENT,
            ACCENT,
            "Pair or encrypt current connection",
        )
        self._make_action_button(
            actions,
            "Secure",
            self.security_request_quick,
            WARNING,
            WARNING,
            "Send security request",
        )

        # Vertical PanedWindow (top = sidebar + content, bottom = log)
        paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                                bg=SIDEBAR_BG, sashwidth=5, sashpad=0,
                                sashrelief="flat", handlesize=0,
                                opaqueresize=True)
        paned.grid(row=2, column=0, sticky="nsew")

        # Top pane: sidebar + content side by side
        top_pane = tk.Frame(paned, background=BG)
        paned.add(top_pane, stretch="always", minsize=300)

        # Activity bar + sidebar (inside top_pane)
        activity_bar = tk.Frame(top_pane, background=SIDEBAR_BG, width=54)
        activity_bar.pack(side=tk.LEFT, fill=tk.Y)
        activity_bar.pack_propagate(False)

        activity_top = tk.Frame(activity_bar, background=SIDEBAR_BG)
        activity_top.pack(fill=tk.X, pady=(10, 6))
        tk.Label(activity_top, text="HC", bg=SIDEBAR_BG, fg=TEXT,
                 font=("Segoe UI Semibold", 10), pady=8).pack(fill=tk.X)

        for key, glyph, label in _NAV:
            btn = tk.Label(
                activity_bar,
                text=glyph,
                bg=SIDEBAR_BG,
                fg=SIDEBAR_TEXT,
                font=("Segoe UI Semibold", 10),
                width=4,
                pady=10,
                cursor="hand2",
            )
            btn.pack(fill=tk.X, padx=0, pady=1)
            btn.bind("<Button-1>", lambda _e, k=key: self._show_page(k))
            btn.bind("<Enter>", lambda _e, w=btn: self._hover_activity_button(w, True))
            btn.bind("<Leave>", lambda _e, w=btn, k=key: self._hover_activity_button(w, False, k))
            btn._tooltip = _ToolTip(btn, label)
            self._activity_buttons[key] = btn

        activity_bottom = tk.Frame(activity_bar, background=SIDEBAR_BG)
        activity_bottom.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))
        tk.Label(activity_bottom, text="LOG", bg=SIDEBAR_BG, fg=TEXT_MUTED,
                 font=("Segoe UI", 8), pady=8).pack(fill=tk.X)

        sidebar = tk.Frame(top_pane, background=CARD_BG, width=232,
                           highlightthickness=1, highlightbackground=CARD_BORDER)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="EXPLORER", bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=14, pady=(10, 6))

        workspace_card = tk.Frame(sidebar, background=CARD_BG)
        workspace_card.pack(fill=tk.X, padx=12, pady=(0, 8))
        tk.Label(workspace_card, text="HCIEMU", bg=CARD_BG, fg=TEXT,
                 font=("Segoe UI Semibold", 10)).pack(anchor="w")
        tk.Label(workspace_card, text="Bluetooth workbench", bg=CARD_BG, fg=TEXT_MUTED,
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        status_card = tk.Frame(sidebar, background=CARD_BG, highlightthickness=1,
                               highlightbackground=CARD_BORDER)
        status_card.pack(fill=tk.X, padx=12, pady=(12, 8))

        tk.Label(status_card, text="CONNECTION", bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=10, pady=(8, 2))

        self._sidebar_conn_status_label = tk.Label(
            status_card,
            textvariable=self.connection_status_var,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Consolas", 9),
            anchor="w",
            justify=tk.LEFT,
        )
        self._sidebar_conn_status_label.pack(anchor="w", fill=tk.X, padx=10, pady=(0, 8))

        tk.Label(sidebar, text="OPEN EDITORS",
                 bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=16, pady=(18, 4))

        for key, _glyph, label in _NAV:
            lbl = tk.Label(sidebar, text=label, bg=CARD_BG, fg=SIDEBAR_TEXT,
                           font=("Segoe UI", 10), anchor="w", cursor="hand2",
                           padx=16, pady=8)
            lbl.pack(fill=tk.X, padx=8)
            lbl.bind("<Button-1>", lambda _e, k=key: self._show_page(k))
            lbl.bind("<Enter>", lambda _e, w=lbl: w.configure(
                bg=SIDEBAR_HOVER if w.cget("bg") != SIDEBAR_SEL else SIDEBAR_SEL))
            lbl.bind("<Leave>", lambda _e, w=lbl, k=key: w.configure(
                bg=SIDEBAR_SEL if self._active_page == k else CARD_BG))
            self._nav_labels[key] = lbl

        # Content area (inside top_pane)
        content = tk.Frame(top_pane, background=BG)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)

        editor_bar = tk.Frame(content, background=CARD_BG, height=36,
                              highlightthickness=1, highlightbackground=CARD_BORDER)
        editor_bar.grid(row=0, column=0, sticky="ew")
        editor_bar.grid_propagate(False)
        editor_bar.columnconfigure(1, weight=1)

        tab_frame = tk.Frame(editor_bar, background=SIDEBAR_BG)
        tab_frame.grid(row=0, column=0, sticky="w")
        tk.Label(tab_frame, textvariable=self._editor_tab_var, bg=BG, fg=TEXT,
                 font=("Segoe UI", 10), padx=14, pady=9).pack(side=tk.LEFT)
        tk.Frame(tab_frame, width=1, bg=CARD_BORDER, height=36).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(editor_bar, textvariable=self._editor_context_var, bg=CARD_BG,
                 fg=TEXT_MUTED, font=("Segoe UI", 9)).grid(
                     row=0, column=1, sticky="w", padx=(14, 0))

        page_host = tk.Frame(content, background=BG)
        page_host.grid(row=1, column=0, sticky="nsew")
        page_host.columnconfigure(0, weight=1)
        page_host.rowconfigure(0, weight=1)

        page_map = {
            "scan":       ScanPage,
            "gatt":       GATTPage,
            "security":   SecurityPage,
            "bridge":     BridgePage,
            "advertiser": AdvertiserPage,
            "settings":   SettingsPage,
        }
        for key, PageCls in page_map.items():
            page = PageCls(page_host, self)
            page.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
            page.grid_remove()
            self._pages[key] = page

        # Bottom pane: tabbed workbench panel
        log_strip = tk.Frame(paned, background=SIDEBAR_BG)
        paned.add(log_strip, stretch="never", minsize=60, height=160)
        log_strip.columnconfigure(0, weight=1)
        log_strip.rowconfigure(0, weight=1)

        panel_notebook = ttk.Notebook(log_strip)
        panel_notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=(6, 6))

        output_tab = ttk.Frame(panel_notebook, style="Card.TFrame")
        output_tab.columnconfigure(0, weight=1)
        output_tab.rowconfigure(1, weight=1)
        panel_notebook.add(output_tab, text="OUTPUT")

        output_hdr = tk.Frame(output_tab, background=CARD_BG)
        output_hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 0))
        tk.Label(output_hdr, text="Session output", bg=CARD_BG,
                 fg=TEXT_MUTED, font=("Segoe UI Semibold", 9)).pack(side=tk.LEFT)
        ttk.Button(output_hdr, text="Clear", command=self._clear_log,
                   style="Neutral.TButton").pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            output_tab, wrap=tk.WORD,
            background=LOG_BG, foreground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0,
            insertbackground=TEXT,
            padx=10, pady=4, font=("Consolas", 9),
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(2, 8))
        log_vsb = ttk.Scrollbar(output_tab, orient=tk.VERTICAL,
                                 command=self.log_text.yview)
        log_vsb.grid(row=1, column=1, sticky="ns", pady=(2, 8), padx=(0, 10))
        self.log_text.configure(yscrollcommand=log_vsb.set, state=tk.DISABLED)

        state_tab = ttk.Frame(panel_notebook, style="Card.TFrame", padding=12)
        state_tab.columnconfigure(0, weight=1)
        state_tab.columnconfigure(1, weight=1)
        panel_notebook.add(state_tab, text="STATE")

        self._make_state_panel_row(state_tab, 0, "Active panel", self._active_panel_var)
        self._make_state_panel_row(state_tab, 1, "Transport", self.transport_var)
        self._make_state_panel_row(state_tab, 2, "Connection", self.connection_status_var)
        self._make_state_panel_row(state_tab, 3, "Pairing", self.security_pair_var)
        self._make_state_panel_row(state_tab, 4, "Authentication", self.security_auth_var)
        self._make_state_panel_row(state_tab, 5, "Advertising", self.adv_status_var)
        self._make_state_panel_row(state_tab, 6, "Bridge", self.bridge_status_var)

        # Show the first page
        self._show_page("scan")

    # â”€â”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _show_page(self, name: str) -> None:
        if self._active_page:
            self._pages[self._active_page].grid_remove()
            prev = self._nav_labels.get(self._active_page)
            if prev:
                prev.configure(bg=CARD_BG, fg=SIDEBAR_TEXT)
            prev_activity = self._activity_buttons.get(self._active_page)
            if prev_activity:
                prev_activity.configure(bg=SIDEBAR_BG, fg=SIDEBAR_TEXT)

        self._pages[name].grid()
        self._active_page = name
        lbl = self._nav_labels.get(name)
        if lbl:
            lbl.configure(bg=SIDEBAR_SEL, fg=SIDEBAR_SEL_TEXT)
        activity_btn = self._activity_buttons.get(name)
        if activity_btn:
            activity_btn.configure(bg=SIDEBAR_SEL, fg=SIDEBAR_SEL_TEXT)

        meta = _PAGE_META[name]
        self._active_panel_var.set(meta["label"])
        self._editor_tab_var.set(meta["label"])
        self._editor_context_var.set("HCIEMU")

        if name == "security":
            self.refresh_security_bonded_list()

    # â”€â”€ Log â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def log(self, message: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _make_status_chip(self, parent, variable: tk.StringVar, bg_color: str, tooltip: str):
        label = tk.Label(
            parent,
            textvariable=variable,
            bg=bg_color,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
            padx=10,
            pady=6,
        )
        label.pack(side=tk.LEFT, padx=(0, 8))
        _ToolTip(label, tooltip)
        return label

    def _make_state_panel_row(self, parent, row: int, label: str, variable: tk.Variable) -> None:
        ttk.Label(parent, text=label, style="Card.Muted.TLabel", width=14).grid(
            row=row, column=0, sticky="w", pady=4, padx=(0, 12)
        )
        value = tk.Label(
            parent,
            textvariable=variable,
            bg=LOG_BG,
            fg=TEXT,
            font=("Consolas", 9),
            anchor="w",
            padx=10,
            pady=6,
        )
        value.grid(row=row, column=1, sticky="ew", pady=4)

    def _hover_activity_button(self, button, hovering: bool, key: Optional[str] = None) -> None:
        is_active = key is not None and self._active_page == key
        if is_active:
            button.configure(bg=SIDEBAR_SEL, fg=SIDEBAR_SEL_TEXT)
            return
        button.configure(
            bg=SIDEBAR_HOVER if hovering else SIDEBAR_BG,
            fg=TEXT if hovering else SIDEBAR_TEXT,
        )

    def _make_action_separator(self, parent) -> None:
        tk.Frame(parent, width=1, height=24, bg=CARD_BORDER).pack(side=tk.LEFT, padx=6)

    def _make_action_button(
        self,
        parent,
        text: str,
        command,
        bg_color: str,
        active_color: str,
        tooltip: str,
    ):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg_color,
            fg=TEXT,
            activebackground=active_color,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            width=max(8, len(text) + 1),
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            padx=8,
            pady=4,
        )
        btn.pack(side=tk.LEFT, padx=(0, 6))
        btn._tooltip = _ToolTip(btn, tooltip)
        return btn

    def _set_button_tooltip(self, button, text: str) -> None:
        tooltip = getattr(button, "_tooltip", None)
        if tooltip is not None:
            tooltip.text = text

    def _update_backend_toggle_visual(self) -> None:
        if self._backend_toggle_btn is None:
            return
        running = self.backend is not None
        self._backend_toggle_btn.configure(
            bg=DANGER if running else SUCCESS,
            activebackground=DANGER if running else SUCCESS,
        )
        self._set_button_tooltip(
            self._backend_toggle_btn,
            "Stop backend" if running else "Start backend",
        )

    def toggle_backend(self) -> None:
        if self.backend is None:
            self.start_backend()
        else:
            self.stop_backend()

    def handle_status_message(self, message: str) -> None:
        """Handle app status callback lines and route to interested pages."""
        self._update_security_bar_from_status(message)
        consumed = False
        for page in self._pages.values():
            if hasattr(page, "on_status_message"):
                try:
                    if page.on_status_message(message):
                        consumed = True
                except Exception:
                    pass
        if not consumed:
            self.log(message)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def update_connection_status(self, peer_address: Optional[str]) -> None:
        """Update sidebar connection status text and color."""
        if peer_address:
            self.connection_status_var.set(f"Connected: {peer_address}")
            if self._conn_status_value_label is not None:
                self._conn_status_value_label.configure(bg=SUCCESS_DIM, fg=TEXT)
            if self._sidebar_conn_status_label is not None:
                self._sidebar_conn_status_label.configure(fg=ACCENT)
            if self._disconnect_btn is not None:
                self._disconnect_btn.configure(state=tk.NORMAL)
            bonded = False
            try:
                if self.backend is not None and self.backend.app is not None:
                    bonded = bool(self.backend.app.connector.is_device_bonded(peer_address))
            except Exception:
                bonded = False
            self._set_pair_status(bonded)
        else:
            self.connection_status_var.set("Disconnected")
            if self._conn_status_value_label is not None:
                self._conn_status_value_label.configure(bg=NEUTRAL, fg=TEXT)
            if self._sidebar_conn_status_label is not None:
                self._sidebar_conn_status_label.configure(fg=TEXT_MUTED)
            if self._disconnect_btn is not None:
                self._disconnect_btn.configure(state=tk.DISABLED)
            self._set_pair_status(False)
            self._set_auth_status(False)

    def update_advertising_state(self, running: bool) -> None:
        """Notify Advertiser page of advertising state changes."""
        advertiser = self._pages.get("advertiser")
        if advertiser is not None and hasattr(advertiser, "_set_state"):
            advertiser._set_state(running)
        self.adv_status_var.set("ADV On" if running else "ADV Off")

    def _on_adv_status_var_changed(self, *_args) -> None:
        if self._adv_status_label is None:
            return
        running = self.adv_status_var.get().strip().lower() in {"adv on", "running"}
        self._adv_status_label.configure(bg=SUCCESS_DIM if running else DANGER_DIM)

    def _on_bridge_status_var_changed(self, *_args) -> None:
        if self._bridge_status_label is None:
            return
        running = self.bridge_status_var.get().strip().lower() == "running"
        self._bridge_status_label.configure(bg=SUCCESS_DIM if running else DANGER_DIM)

    def _set_pair_status(self, paired: bool) -> None:
        self.security_pair_var.set("Pair: Yes" if paired else "Pair: No")
        if self._pair_status_label is not None:
            self._pair_status_label.configure(bg=SUCCESS_DIM if paired else NEUTRAL)

    def _set_auth_status(self, authenticated: bool) -> None:
        self.security_auth_var.set("Auth: Yes" if authenticated else "Auth: No")
        if self._auth_status_label is not None:
            self._auth_status_label.configure(bg=SUCCESS_DIM if authenticated else NEUTRAL)

    def _update_security_bar_from_status(self, message: str) -> None:
        if message == "[PAIRING] Completed":
            self._set_pair_status(True)
        elif message == "[PAIRING] Failed":
            self._set_pair_status(False)
            self._set_auth_status(False)
        elif message == "[SECURITY] Encryption state changed":
            self._set_auth_status(True)

    def disconnect_device(self) -> None:
        self.run_action("Disconnect", lambda app: app.app_disconnect(), on_success=self.refresh_security_bonded_list)

    def start_advertising_quick(self) -> None:
        self.run_action("Start Advertising", lambda app: app.app_start_advertising())

    def stop_advertising_quick(self) -> None:
        self.run_action("Stop Advertising", lambda app: app.app_stop_advertising())

    def start_bridge_quick(self) -> None:
        bridge_page = self._pages.get("bridge")
        if bridge_page is not None and hasattr(bridge_page, "start_bridge"):
            bridge_page.start_bridge()

    def stop_bridge_quick(self) -> None:
        bridge_page = self._pages.get("bridge")
        if bridge_page is not None and hasattr(bridge_page, "stop_bridge"):
            bridge_page.stop_bridge()

    def pair_encrypt_quick(self) -> None:
        self.run_action("Pair / Encrypt", lambda app: app.app_pair(), on_success=self.refresh_security_bonded_list)

    def security_request_quick(self) -> None:
        self.run_action("Security Request", lambda app: app.app_send_security_request(), on_success=self.refresh_security_bonded_list)

    # â”€â”€ Backend â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def refresh_security_bonded_list(self) -> None:
        """Refresh the bonded devices list on the Security page."""
        security = self._pages.get("security")
        if security is not None and hasattr(security, "refresh_bonded_devices"):
            security.refresh_bonded_devices()

    def _ensure_backend(self) -> bool:
        if self.backend is None:
            messagebox.showerror("Backend not running",
                                  "Start the GUI backend first.")
            return False
        return True

    def start_backend(self) -> None:
        if self.backend is not None:
            return
        try:
            from hciemu.gui.pairing_delegate import GUIPairingDelegate
            # Create GUI pairing delegate for user interaction
            gui_pairing_delegate = GUIPairingDelegate(self)
            self.backend = AsyncBLEBackend(
                self.transport_var.get().strip(),
                gui_pairing_delegate=gui_pairing_delegate
            )
            self.backend.start()
            self.update_connection_status(None)
            self._update_backend_toggle_visual()
            self.log("Backend started â€” Bluetooth ready")
            # Refresh settings page if it's been built
            settings = self._pages.get("settings")
            if settings is not None:
                settings._refresh_settings()
        except Exception as exc:
            self.backend = None
            messagebox.showerror("Start failed", str(exc))

    def stop_backend(self) -> None:
        if self.backend is None:
            return
        self.log("Stopping backend...")
        self.backend.stop()
        self.backend = None
        self.update_connection_status(None)
        self.adv_status_var.set("ADV Off")
        self._update_backend_toggle_visual()
        self.log("Backend stopped")

    def run_action(
        self,
        label: str,
        coro_factory: Callable,
        on_success: Optional[Callable[[], None]] = None,
    ) -> None:
        if not self._ensure_backend():
            return
        self.log(f"Running: {label}")
        future = self.backend.submit(coro_factory)

        def _done(f: concurrent.futures.Future) -> None:
            def _finalize() -> None:
                try:
                    f.result()
                    self.log(f"Done: {label}")
                    if on_success:
                        on_success()
                except Exception as exc:
                    self.log(f"Error: {label}: {exc}")
                    messagebox.showerror("Action failed", f"{label} failed:\n{exc}")
            self.after(0, _finalize)

        future.add_done_callback(_done)

    def _on_close(self) -> None:
        bridge_page = self._pages.get("bridge")
        if bridge_page is not None:
            bridge_page.stop_bridge()
        self.stop_backend()
        self.destroy()


def run_gui() -> None:
    """Launch the desktop GUI."""
    app = HCIEMUGui()
    app.mainloop()


if __name__ == "__main__":
    run_gui()


