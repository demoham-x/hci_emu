"""Scan / Controller page."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, TYPE_CHECKING

from hciemu.gui.pages.base import BasePage
from hciemu.gui.theme import (
    CARD_BG, CARD_BORDER, TEXT, TEXT_MUTED,
    ACCENT, ENTRY_SELECT, LOG_BG, SUCCESS_DIM, DANGER_DIM,
)

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui
    from hciemu.app import BLETestingApp


class ScanPage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, style="App.TFrame")
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)

        workspace = ttk.LabelFrame(top, text="Scan Workspace", padding=14,
                                   style="Card.TLabelframe")
        workspace.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        workspace.columnconfigure(0, weight=1)
        workspace.columnconfigure(1, weight=1)

        summary = tk.Frame(workspace, background=CARD_BG)
        summary.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        summary.columnconfigure(0, weight=1)
        summary.columnconfigure(1, weight=1)
        summary.columnconfigure(2, weight=1)
        self._make_stat_card(summary, 0, "RADIO", "Bluetooth adapter control", SUCCESS_DIM)
        self._make_stat_card(summary, 1, "SCAN", "Discovery session ready", ENTRY_SELECT)
        self._make_stat_card(summary, 2, "TARGET", "Direct connect workflow", DANGER_DIM)

        # ── Controller controls ────────────────────────────────────────
        ctrl = ttk.Frame(workspace, style="Card.TFrame")
        ctrl.grid(row=1, column=0, columnspan=2, sticky="ew")
        ctrl.columnconfigure(1, weight=1)
        ctrl.columnconfigure(3, weight=1)

        power = ttk.LabelFrame(ctrl, text="Controller", padding=12,
                               style="Card.TLabelframe")
        power.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ttk.Button(power, text="Bluetooth ON",
                   command=lambda: self.run_action("Bluetooth ON", lambda a: a.app_bluetooth_on()),
                   style="Success.TButton").grid(row=0, column=0, padx=(0, 6), pady=4)
        ttk.Button(power, text="Bluetooth OFF",
                   command=lambda: self.run_action("Bluetooth OFF", lambda a: a.app_bluetooth_off()),
                   style="Danger.TButton").grid(row=0, column=1, pady=4)

        scan_ops = ttk.LabelFrame(ctrl, text="Scan Options", padding=12,
                                  style="Card.TLabelframe")
        scan_ops.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        scan_ops.columnconfigure(1, weight=1)

        ttk.Label(scan_ops, text="Duration", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))
        ttk.Entry(scan_ops, textvariable=self.gui.scan_duration_var, width=8).grid(
            row=0, column=1, sticky="w", pady=(0, 6))
        ttk.Checkbutton(scan_ops, text="Active scan",
                        variable=self.gui.scan_active_var,
                        style="TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(scan_ops, text="Filter duplicates",
                        variable=self.gui.scan_duplicates_var,
                        style="TCheckbutton").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Button(scan_ops, text="Run Scan", command=self.scan_devices,
                   style="Accent.TButton").grid(row=3, column=0, columnspan=2,
                                                 sticky="w", pady=(10, 0))

        connect = ttk.LabelFrame(top, text="Connection Target", padding=14,
                                 style="Card.TLabelframe")
        connect.grid(row=0, column=1, sticky="nsew")
        connect.columnconfigure(0, weight=1)

        ttk.Label(connect, text="Selected device address", style="Card.Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(connect, textvariable=self.gui.connect_target_var, width=36).grid(
            row=1, column=0, sticky="ew", pady=(6, 10))
        ttk.Button(connect, text="Connect", command=self.connect_selected,
                   style="Accent.TButton").grid(row=2, column=0, sticky="w")
        ttk.Button(connect, text="Disconnect",
                   command=lambda: self.run_action("Disconnect", lambda a: a.app_disconnect()),
                   style="Danger.TButton").grid(row=2, column=0, sticky="e")
        hint = tk.Label(
            connect,
            text="Pick a device from the list below or paste an address to connect directly.",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            justify=tk.LEFT,
            wraplength=240,
        )
        hint.grid(row=3, column=0, sticky="ew", pady=(12, 0))

        # ── Device list ────────────────────────────────────────────────
        list_card = ttk.LabelFrame(self, text="Discovered Devices", padding=8,
                                    style="Card.TLabelframe")
        list_card.grid(row=1, column=0, sticky="nsew")
        list_card.columnconfigure(0, weight=1)
        list_card.rowconfigure(1, weight=1)

        list_hdr = tk.Frame(list_card, background=CARD_BG)
        list_hdr.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        tk.Label(list_hdr, text="Address | RSSI | Name", bg=CARD_BG, fg=TEXT_MUTED,
                 font=("Consolas", 9)).pack(side=tk.LEFT)
        tk.Label(list_hdr, text="Double-click a row to set the connect target", bg=CARD_BG,
                 fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        self.device_list = tk.Listbox(
            list_card,
            background=LOG_BG,
            foreground=TEXT,
            selectbackground=ENTRY_SELECT,
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            font=("Consolas", 10),
            selectborderwidth=0,
        )
        self.device_list.grid(row=1, column=0, sticky="nsew")
        self.device_list.bind("<<ListboxSelect>>", self._on_device_selected)
        self.device_list.bind("<Double-Button-1>", lambda _e: self.connect_selected())

        vsb = ttk.Scrollbar(list_card, orient=tk.VERTICAL,
                             command=self.device_list.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        self.device_list.configure(yscrollcommand=vsb.set)

    def _make_stat_card(self, parent, column: int, title: str, subtitle: str, stripe: str) -> None:
        card = tk.Frame(parent, background=LOG_BG, highlightthickness=1,
                        highlightbackground=CARD_BORDER)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 8) if column < 2 else (0, 0))
        card.columnconfigure(1, weight=1)
        tk.Frame(card, background=stripe, width=4, height=46).grid(row=0, column=0, sticky="ns")
        body = tk.Frame(card, background=LOG_BG)
        body.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        tk.Label(body, text=title, bg=LOG_BG, fg=TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(body, text=subtitle, bg=LOG_BG, fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(anchor="w")

    # ── Actions ───────────────────────────────────────────────────────────

    def _on_device_selected(self, _event=None) -> None:
        sel = self.device_list.curselection()
        if not sel:
            return
        line = self.device_list.get(sel[0])
        parts = line.split("|")
        if len(parts) >= 2:
            self.gui.connect_target_var.set(parts[1].strip())

    def scan_devices(self) -> None:
        if not self._ensure_backend():
            return
        try:
            duration = int(self.gui.scan_duration_var.get().strip() or "10")
        except ValueError:
            from tkinter import messagebox
            messagebox.showerror("Invalid input", "Scan duration must be an integer")
            return

        self.run_action(
            "Scan Devices",
            lambda app: app.app_scan_devices(
                duration=duration,
                filter_duplicates=self.gui.scan_duplicates_var.get(),
                active_scan=self.gui.scan_active_var.get(),
            ),
            on_success=self._refresh_device_list,
        )

    def _refresh_device_list(self) -> None:
        if not self._ensure_backend():
            return

        async def _snap(app: "BLETestingApp"):
            return [
                (addr, str(info.get("rssi", "N/A")), str(info.get("name") or "—"))
                for addr, info in app.discovered_devices.items()
            ]

        def _done(f):
            def _fill():
                try:
                    rows = f.result()
                    self.device_list.delete(0, tk.END)
                    for i, (addr, rssi, name) in enumerate(rows, 1):
                        self.device_list.insert(
                            tk.END, f"{i:>2}  |  {addr:<20}  |  RSSI {rssi:<4}  |  {name}"
                        )
                    self.log(f"Loaded {len(rows)} discovered devices")
                except Exception as exc:
                    self.log(f"Device list refresh error: {exc}")
            self.gui.after(0, _fill)

        self.backend.submit(_snap).add_done_callback(_done)

    def connect_selected(self) -> None:
        target = self.gui.connect_target_var.get().strip()
        if not target:
            from tkinter import messagebox
            messagebox.showerror("Missing target",
                                 "Select a discovered device or type an address")
            return
        self.run_action("Connect", lambda app: app.connect(target))
