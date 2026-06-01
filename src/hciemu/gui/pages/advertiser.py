"""Advertiser / peripheral page."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, TYPE_CHECKING

from hciemu.gui.pages.base import BasePage
from hciemu.gui.theme import SUCCESS, DANGER, TEXT_MUTED

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui
    from hciemu.app import BLETestingApp


class AdvertiserPage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)
        self._status_lbl: Optional[ttk.Label] = None
        self._start_btn: Optional[ttk.Button] = None
        self._stop_btn: Optional[ttk.Button] = None
        self._build()

    def _build(self) -> None:
        from hciemu.gui.theme import BG
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Scrollable canvas ──────────────────────────────────────────
        canvas = tk.Canvas(self, background=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.grid(row=0, column=0, sticky="nsew")

        inner = ttk.Frame(canvas, style="App.TFrame")
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_resize(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(e):
            canvas.itemconfig(win_id, width=e.width)

        def _on_scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def _bind_scroll(_e=None):
            canvas.bind_all("<MouseWheel>", _on_scroll)

        def _unbind_scroll(_e=None):
            canvas.unbind_all("<MouseWheel>")

        inner.bind("<Configure>", _on_inner_resize)
        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.bind("<Enter>", _bind_scroll)
        canvas.bind("<Leave>", _unbind_scroll)
        inner.bind("<Enter>", _bind_scroll)

        inner.columnconfigure(0, weight=1)

        # ── Status bar ─────────────────────────────────────────────────
        status_bar = ttk.Frame(inner, style="App.TFrame")
        status_bar.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(status_bar, text="Advertising:", style="TLabel").pack(side=tk.LEFT)
        self._status_lbl = ttk.Label(
            status_bar, textvariable=self.gui.adv_status_var,
            font=("Segoe UI Semibold", 10), foreground=DANGER)
        self._status_lbl.pack(side=tk.LEFT, padx=(6, 20))
        ttk.Button(status_bar, text="Refresh", command=self._refresh,
                   style="Neutral.TButton").pack(side=tk.LEFT)

        # ── Parameters ─────────────────────────────────────────────────
        params = ttk.LabelFrame(inner, text="Advertising Parameters", padding=12,
                                 style="Card.TLabelframe")
        params.pack(fill=tk.X, pady=(0, 10))
        params.columnconfigure(1, weight=1)

        self._field(params, "Min interval (ms):", self.gui.adv_interval_min_var, 0, width=12)
        self._field(params, "Max interval (ms):", self.gui.adv_interval_max_var, 1, width=12)
        self._check(params, "Connectable:", self.gui.adv_connectable_var, 2)
        ttk.Button(params, text="Apply Parameters", command=self._apply_params,
                   style="Neutral.TButton").grid(row=3, column=0, columnspan=2,
                                                  sticky="w", pady=(8, 0))

        # ── Payload ────────────────────────────────────────────────────
        payload = ttk.LabelFrame(inner, text="Advertising Payload", padding=12,
                                  style="Card.TLabelframe")
        payload.pack(fill=tk.X, pady=(0, 10))
        payload.columnconfigure(1, weight=1)

        self._field(payload, "Adv data (hex):", self.gui.adv_data_hex_var, 0)
        self._field(payload, "Scan response (hex):", self.gui.adv_scan_rsp_hex_var, 1)
        ttk.Button(payload, text="Apply Payload", command=self._apply_payload,
                   style="Neutral.TButton").grid(row=2, column=0, columnspan=2,
                                                  sticky="w", pady=(8, 0))

        # ── Name ───────────────────────────────────────────────────────
        name_card = ttk.LabelFrame(inner, text="Local Name in Advertising", padding=12,
                                    style="Card.TLabelframe")
        name_card.pack(fill=tk.X, pady=(0, 10))
        name_card.columnconfigure(1, weight=1)

        self._check(name_card, "Include local name:", self.gui.adv_name_enabled_var, 0)
        name_row = ttk.Frame(name_card, style="Card.TFrame")
        name_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        name_row.columnconfigure(1, weight=1)
        ttk.Label(name_row, text="Custom name:", style="Card.TLabel",
                  width=22, anchor="e").grid(row=0, column=0, sticky="e", padx=(0, 8))
        ttk.Entry(name_row, textvariable=self.gui.adv_custom_name_var).grid(
            row=0, column=1, sticky="ew")
        ttk.Label(name_row, text="(empty = hciemu_<bd-addr>)",
                  style="Card.Muted.TLabel", font=("Segoe UI", 9)).grid(
            row=0, column=2, padx=(8, 0))
        ttk.Button(name_card, text="Apply Name", command=self._apply_name,
                   style="Neutral.TButton").grid(row=2, column=0, columnspan=2,
                                                  sticky="w", pady=(8, 0))

        # ── Control ────────────────────────────────────────────────────
        ctrl = ttk.LabelFrame(inner, text="Control", padding=12,
                               style="Card.TLabelframe")
        ctrl.pack(fill=tk.X, pady=(0, 10))

        self._start_btn = ttk.Button(ctrl, text="▶  Start Advertising",
                                      command=self._start, style="Success.TButton")
        self._start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self._stop_btn = ttk.Button(ctrl, text="■  Stop Advertising",
                                     command=self._stop, style="Danger.TButton",
                                     state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _field(parent, label, var, row, width=None):
        kw = {"width": width} if width else {}
        ttk.Label(parent, text=label, style="Card.TLabel",
                  width=22, anchor="e").grid(row=row, column=0, sticky="e",
                                              padx=(0, 8), pady=4)
        ttk.Entry(parent, textvariable=var, **kw).grid(
            row=row, column=1, sticky="w" if width else "ew", pady=4)

    @staticmethod
    def _check(parent, label, var, row):
        ttk.Label(parent, text=label, style="Card.TLabel",
                  width=22, anchor="e").grid(row=row, column=0, sticky="e",
                                              padx=(0, 8), pady=4)
        ttk.Checkbutton(parent, variable=var).grid(row=row, column=1, sticky="w", pady=4)

    def _set_state(self, running: bool) -> None:
        self.gui.adv_status_var.set("Advertising: Running" if running else "Advertising: Stopped")
        if self._status_lbl:
            self._status_lbl.configure(foreground=SUCCESS if running else DANGER)
        if self._start_btn:
            self._start_btn.configure(state=tk.DISABLED if running else tk.NORMAL)
        if self._stop_btn:
            self._stop_btn.configure(state=tk.NORMAL if running else tk.DISABLED)

    # ── Actions ───────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._ensure_backend():
            return

        async def _read(app: "BLETestingApp"):
            return {
                "advertising": app.advertising,
                "interval_min": app.adv_interval_min_ms,
                "interval_max": app.adv_interval_max_ms,
                "connectable": app.adv_connectable,
                "adv_data": app.adv_data_hex,
                "scan_rsp": app.adv_scan_response_hex,
                "name_enabled": app.adv_name_enabled,
                "custom_name": app.adv_custom_name or "",
            }

        def _done(f):
            def _apply():
                try:
                    d = f.result()
                    self.gui.adv_interval_min_var.set(str(d["interval_min"]))
                    self.gui.adv_interval_max_var.set(str(d["interval_max"]))
                    self.gui.adv_connectable_var.set(d["connectable"])
                    self.gui.adv_data_hex_var.set(d["adv_data"])
                    self.gui.adv_scan_rsp_hex_var.set(d["scan_rsp"])
                    self.gui.adv_name_enabled_var.set(d["name_enabled"])
                    self.gui.adv_custom_name_var.set(d["custom_name"])
                    self._set_state(d["advertising"])
                except Exception as exc:
                    self.log(f"Advertiser refresh error: {exc}")
            self.gui.after(0, _apply)

        self.backend.submit(_read).add_done_callback(_done)

    def _apply_params(self) -> None:
        if not self._ensure_backend():
            return
        try:
            imin = float(self.gui.adv_interval_min_var.get().strip())
            imax = float(self.gui.adv_interval_max_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid input", "Interval values must be numbers")
            return
        conn = self.gui.adv_connectable_var.get()
        self.run_action("Apply Adv Parameters",
                        lambda app: app.app_set_advertising_parameters(
                            interval_min_ms=imin, interval_max_ms=imax,
                            connectable=conn))

    def _apply_payload(self) -> None:
        if not self._ensure_backend():
            return
        adv = self.gui.adv_data_hex_var.get().strip()
        rsp = self.gui.adv_scan_rsp_hex_var.get().strip()
        self.run_action("Apply Adv Payload",
                        lambda app: app.app_set_advertising_data(
                            adv_data_hex=adv, scan_response_hex=rsp))

    def _apply_name(self) -> None:
        if not self._ensure_backend():
            return
        enabled = self.gui.adv_name_enabled_var.get()
        name = self.gui.adv_custom_name_var.get().strip() or None
        self.run_action("Apply Adv Name",
                        lambda app: app.app_set_advertising_name(
                            enabled=enabled, name=name))

    def _start(self) -> None:
        if not self._ensure_backend():
            return

        def _after(f):
            def _ui():
                try:
                    f.result()
                    self._set_state(True)
                    self.log("Advertising started")
                except Exception as exc:
                    self.log(f"Start advertising error: {exc}")
            self.gui.after(0, _ui)

        self.backend.submit(lambda app: app.app_start_advertising()).add_done_callback(_after)

    def _stop(self) -> None:
        if not self._ensure_backend():
            return

        def _after(f):
            def _ui():
                try:
                    f.result()
                    self._set_state(False)
                    self.log("Advertising stopped")
                except Exception as exc:
                    self.log(f"Stop advertising error: {exc}")
            self.gui.after(0, _ui)

        self.backend.submit(lambda app: app.app_stop_advertising()).add_done_callback(_after)
