"""Settings page — paths display, ui_config and smp_config editing."""
from __future__ import annotations

import json
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, TYPE_CHECKING

from hciemu.gui.pages.base import BasePage
from hciemu.gui.theme import CARD_BG, BG, ENTRY_BG, TEXT, TEXT_MUTED

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui
    from hciemu.app import BLETestingApp


class SettingsPage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)
        self._paths_labels: Dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Scrollable content area ────────────────────────────────────
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

        # ── Paths ──────────────────────────────────────────────────────
        paths = ttk.LabelFrame(inner, text="Paths  (read-only)", padding=12,
                                style="Card.TLabelframe")
        paths.pack(fill=tk.X, padx=2, pady=(0, 10))
        paths.columnconfigure(1, weight=1)

        for key in ("mode", "ui_config", "smp_config", "bonds_file",
                    "resources_dir", "logs_dir", "debug_log", "capture_log"):
            var = tk.StringVar(value="—")
            self._paths_labels[key] = var
            row = ttk.Frame(paths, style="Card.TFrame")
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=f"{key.replace('_', ' ').title()}:",
                      width=18, anchor="e", style="Card.TLabel").pack(side=tk.LEFT)
            e = ttk.Entry(row, textvariable=var, state="readonly")
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        btn_row = ttk.Frame(paths, style="Card.TFrame")
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Reveal Configs Folder",
                   command=self._open_configs_folder,
                   style="Neutral.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Reveal Logs Folder",
                   command=self._open_logs_folder,
                   style="Neutral.TButton").pack(side=tk.LEFT)

        # ── UI Config ─────────────────────────────────────────────────
        ui = ttk.LabelFrame(inner, text="UI Config  (ui_config.json)", padding=12,
                             style="Card.TLabelframe")
        ui.pack(fill=tk.X, padx=2, pady=(0, 10))
        ui.columnconfigure(1, weight=1)

        self._cfg_row(ui, "Filter name:", ttk.Entry(ui, textvariable=self.gui.cfg_filter_name), 0)
        self._cfg_row(ui, "Filter address:", ttk.Entry(ui, textvariable=self.gui.cfg_filter_address), 1)
        self._cfg_row(ui, "Debug mode:",
                      ttk.Combobox(ui, textvariable=self.gui.cfg_debug_mode,
                                   values=["none", "console", "file", "both"],
                                   state="readonly", width=14), 2)
        self._cfg_row(ui, "Auto-restore CCCD on reconnect:",
                      ttk.Checkbutton(ui, variable=self.gui.cfg_auto_restore_cccd), 3)

        snoop = ttk.LabelFrame(ui, text="HCI Snoop", padding=10,
                                style="Card.TLabelframe")
        snoop.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        snoop.columnconfigure(1, weight=1)

        self._cfg_row(snoop, "Auto-enable snoop:",
                      ttk.Checkbutton(snoop, variable=self.gui.cfg_snoop_enabled), 0, width=28)
        self._cfg_row(snoop, "Enable Ellisys UDP:",
                      ttk.Checkbutton(snoop, variable=self.gui.cfg_snoop_ellisys), 1, width=28)
        self._cfg_row(snoop, "Enable capture file:",
                      ttk.Checkbutton(snoop, variable=self.gui.cfg_snoop_file), 2, width=28)
        self._cfg_row(snoop, "Console packet logging:",
                      ttk.Checkbutton(snoop, variable=self.gui.cfg_snoop_console), 3, width=28)
        self._cfg_row(snoop, "Ellisys host:",
                      ttk.Entry(snoop, textvariable=self.gui.cfg_ellisys_host), 4, width=28)
        self._cfg_row(snoop, "Ellisys port:",
                      ttk.Entry(snoop, textvariable=self.gui.cfg_ellisys_port, width=10), 5, width=28)
        self._cfg_row(snoop, "Ellisys stream:",
                      ttk.Combobox(snoop, textvariable=self.gui.cfg_ellisys_stream,
                                   values=["primary", "secondary", "tertiary"],
                                   state="readonly", width=14), 6, width=28)
        self._cfg_row(snoop, "Capture file path:",
                      ttk.Entry(snoop, textvariable=self.gui.cfg_btsnoop_filename), 7, width=28)

        # ── SMP Config ────────────────────────────────────────────────
        smp = ttk.LabelFrame(inner, text="SMP Config  (smp_config.json)", padding=12,
                              style="Card.TLabelframe")
        smp.pack(fill=tk.X, padx=2, pady=(0, 10))
        smp.columnconfigure(1, weight=1)

        io_caps = ["NO_INPUT_NO_OUTPUT", "DISPLAY_ONLY", "DISPLAY_YES_NO",
                   "KEYBOARD_ONLY", "KEYBOARD_DISPLAY"]
        self._cfg_row(smp, "IO capability:",
                      ttk.Combobox(smp, textvariable=self.gui.cfg_io_capability,
                                   values=io_caps, state="readonly", width=26), 0)
        self._cfg_row(smp, "MITM required:",
                      ttk.Checkbutton(smp, variable=self.gui.cfg_mitm), 1)
        self._cfg_row(smp, "LE Secure Connections:",
                      ttk.Checkbutton(smp, variable=self.gui.cfg_secure_conn), 2)
        self._cfg_row(smp, "Bonding enabled:",
                      ttk.Checkbutton(smp, variable=self.gui.cfg_bonding), 3)
        self._cfg_row(smp, "Auto pair on security request:",
                      ttk.Checkbutton(smp, variable=self.gui.cfg_auto_pair), 4)
        self._cfg_row(smp, "Auto encrypt if bonded:",
                      ttk.Checkbutton(smp, variable=self.gui.cfg_auto_encrypt), 5)
        self._cfg_row(smp, "Min enc key size:",
                      ttk.Entry(smp, textvariable=self.gui.cfg_min_key, width=6), 6)
        self._cfg_row(smp, "Max enc key size:",
                      ttk.Entry(smp, textvariable=self.gui.cfg_max_key, width=6), 7)

        # ── Action buttons ────────────────────────────────────────────
        actions = ttk.Frame(inner, style="App.TFrame")
        actions.pack(fill=tk.X, padx=2, pady=(0, 14))
        ttk.Button(actions, text="Refresh from App",
                   command=self._refresh_settings,
                   style="Neutral.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Apply & Save",
                   command=self._apply_settings,
                   style="Accent.TButton").pack(side=tk.LEFT)

    @staticmethod
    def _cfg_row(parent, label: str, widget, row: int, width: int = 30) -> None:
        ttk.Label(parent, text=label, anchor="e", width=width,
                  style="Card.TLabel").grid(row=row, column=0, sticky="e",
                                             pady=3, padx=(0, 8))
        widget.grid(row=row, column=1, sticky="we", pady=3)

    # ── Actions ───────────────────────────────────────────────────────────

    def _refresh_settings(self) -> None:
        if not self._ensure_backend():
            return

        async def _snapshot(app: "BLETestingApp"):
            from hciemu.paths import (
                get_capture_log_path, get_debug_log_path, get_log_dir,
                get_resource_dir, get_user_config_path, is_repo_checkout,
            )
            smp = app.connector.get_smp_config()
            return {
                "mode": "repo" if is_repo_checkout() else "installed-package",
                "ui_config": str(get_user_config_path("ui_config.json")),
                "smp_config": str(get_user_config_path("smp_config.json")),
                "bonds_file": str(get_user_config_path("bumble_bonds.json")),
                "resources_dir": str(get_resource_dir()),
                "logs_dir": str(get_log_dir()),
                "debug_log": str(get_debug_log_path()),
                "capture_log": str(get_capture_log_path()),
                "filter_name": app.filter_name or "",
                "filter_address": app.filter_address or "",
                "debug_mode": app.debug_mode,
                "auto_restore_cccd": app.auto_restore_cccd_on_reconnect,
                "snoop_enabled": app.snoop_auto_enable,
                "snoop_ellisys": app.snoop_ellisys_enabled,
                "snoop_file": app.snoop_file_enabled,
                "snoop_console": app.snoop_console_logging,
                "ellisys_host": app.ellisys_host,
                "ellisys_port": str(app.ellisys_port),
                "ellisys_stream": app.ellisys_stream,
                "btsnoop_filename": app.btsnoop_filename,
                "io_capability": smp.get("io_capability", "KEYBOARD_ONLY"),
                "mitm": smp.get("mitm_required", False),
                "secure_conn": smp.get("le_secure_connections", True),
                "bonding": smp.get("bonding_enabled", True),
                "auto_pair": smp.get("auto_pair_encrypt_on_security_request", True),
                "auto_encrypt": smp.get("auto_encrypt_if_bonded", True),
                "min_key": str(smp.get("min_enc_key_size", 7)),
                "max_key": str(smp.get("max_enc_key_size", 16)),
            }

        def _done(f):
            def _apply():
                try:
                    d = f.result()
                    for key, var in self._paths_labels.items():
                        var.set(d.get(key, "—"))
                    g = self.gui
                    g.cfg_filter_name.set(d["filter_name"])
                    g.cfg_filter_address.set(d["filter_address"])
                    g.cfg_debug_mode.set(d["debug_mode"])
                    g.cfg_auto_restore_cccd.set(d["auto_restore_cccd"])
                    g.cfg_snoop_enabled.set(d["snoop_enabled"])
                    g.cfg_snoop_ellisys.set(d["snoop_ellisys"])
                    g.cfg_snoop_file.set(d["snoop_file"])
                    g.cfg_snoop_console.set(d["snoop_console"])
                    g.cfg_ellisys_host.set(d["ellisys_host"])
                    g.cfg_ellisys_port.set(d["ellisys_port"])
                    g.cfg_ellisys_stream.set(d["ellisys_stream"])
                    g.cfg_btsnoop_filename.set(d["btsnoop_filename"])
                    g.cfg_io_capability.set(d["io_capability"])
                    g.cfg_mitm.set(d["mitm"])
                    g.cfg_secure_conn.set(d["secure_conn"])
                    g.cfg_bonding.set(d["bonding"])
                    g.cfg_auto_pair.set(d["auto_pair"])
                    g.cfg_auto_encrypt.set(d["auto_encrypt"])
                    g.cfg_min_key.set(d["min_key"])
                    g.cfg_max_key.set(d["max_key"])
                    self.log("Settings refreshed from app")
                except Exception as exc:
                    self.log(f"Settings refresh error: {exc}")
            self.gui.after(0, _apply)

        self.backend.submit(_snapshot).add_done_callback(_done)

    def _apply_settings(self) -> None:
        if not self._ensure_backend():
            return

        g = self.gui
        try:
            min_key = int(g.cfg_min_key.get().strip())
            max_key = int(g.cfg_max_key.get().strip())
            port = int(g.cfg_ellisys_port.get().strip())
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        async def _save(app: "BLETestingApp") -> None:
            from hciemu.paths import get_user_config_path

            app.filter_name = g.cfg_filter_name.get().strip() or None
            app.filter_address = g.cfg_filter_address.get().strip() or None
            app.debug_mode = g.cfg_debug_mode.get()
            app.auto_restore_cccd_on_reconnect = g.cfg_auto_restore_cccd.get()
            app.snoop_auto_enable = g.cfg_snoop_enabled.get()
            app.snoop_ellisys_enabled = g.cfg_snoop_ellisys.get()
            app.snoop_file_enabled = g.cfg_snoop_file.get()
            app.snoop_console_logging = g.cfg_snoop_console.get()
            app.ellisys_host = g.cfg_ellisys_host.get().strip()
            app.ellisys_port = port
            app.ellisys_stream = g.cfg_ellisys_stream.get()
            app.btsnoop_filename = g.cfg_btsnoop_filename.get().strip()
            app._save_ui_config()

            smp_path = str(get_user_config_path("smp_config.json"))
            smp = {
                "io_capability": g.cfg_io_capability.get(),
                "mitm_required": g.cfg_mitm.get(),
                "le_secure_connections": g.cfg_secure_conn.get(),
                "min_enc_key_size": min_key,
                "max_enc_key_size": max_key,
                "bonding_enabled": g.cfg_bonding.get(),
                "auto_pair_encrypt_on_security_request": g.cfg_auto_pair.get(),
                "auto_encrypt_if_bonded": g.cfg_auto_encrypt.get(),
            }
            os.makedirs(os.path.dirname(smp_path), exist_ok=True)
            with open(smp_path, "w", encoding="utf-8") as fh:
                json.dump(smp, fh, indent=2)
                fh.write("\n")

            # Apply SMP settings immediately to the running backend as well.
            app.connector.smp_config = app.connector._normalize_smp_config(smp)
            custom_delegate = getattr(app.connector, "_custom_pairing_delegate", None)
            if custom_delegate is not None and hasattr(custom_delegate, "io_capability"):
                try:
                    io_name = app.connector.smp_config.get(
                        "io_capability", "DISPLAY_OUTPUT_AND_KEYBOARD_INPUT"
                    )
                    custom_delegate.io_capability = app.connector._resolve_io_capability(io_name)
                except Exception:
                    pass

            await app.app_debug_logging(app.debug_mode)

        def _done(f):
            def _finalize():
                try:
                    f.result()
                    self.log("Settings saved")
                except Exception as exc:
                    self.log(f"Settings save error: {exc}")
                    messagebox.showerror("Save failed", str(exc))
            self.gui.after(0, _finalize)

        self.backend.submit(_save).add_done_callback(_done)

    def _open_configs_folder(self) -> None:
        if not self._ensure_backend():
            return

        async def _path(app: "BLETestingApp"):
            from hciemu.paths import get_user_config_path
            return str(get_user_config_path("ui_config.json").parent)

        def _done(f):
            def _open():
                try:
                    subprocess.Popen(["explorer", f.result()])
                except Exception as exc:
                    self.log(f"Could not open folder: {exc}")
            self.gui.after(0, _open)

        self.backend.submit(_path).add_done_callback(_done)

    def _open_logs_folder(self) -> None:
        if not self._ensure_backend():
            return

        async def _path(app: "BLETestingApp"):
            from hciemu.paths import get_log_dir
            return str(get_log_dir())

        def _done(f):
            def _open():
                try:
                    subprocess.Popen(["explorer", f.result()])
                except Exception as exc:
                    self.log(f"Could not open folder: {exc}")
            self.gui.after(0, _open)

        self.backend.submit(_path).add_done_callback(_done)
