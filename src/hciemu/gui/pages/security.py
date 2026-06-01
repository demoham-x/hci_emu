"""Security / SMP page."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Dict, List, Optional

from hciemu.gui.pages.base import BasePage

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui


class SecurityPage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)
        self._bonded_tree: Optional[ttk.Treeview] = None
        self._row_address_by_iid: Dict[str, str] = {}
        self.pairing_status_var = tk.StringVar(value="Status: Idle")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        pair_card = ttk.LabelFrame(
            self, text="Pairing & Encryption", padding=14, style="Card.TLabelframe"
        )
        pair_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(pair_card, textvariable=self.pairing_status_var, style="Card.Muted.TLabel").pack(
            anchor="w", pady=(0, 10)
        )

        ttk.Button(
            pair_card,
            text="Pair / Encrypt",
            command=lambda: self.run_action(
                "Pair / Encrypt",
                lambda a: a.app_pair(),
                on_success=self._on_pairing_action_success,
            ),
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            pair_card,
            text="Send Security Request",
            command=lambda: self.run_action(
                "Security Request",
                lambda a: a.app_send_security_request(),
                on_success=self._on_pairing_action_success,
            ),
            style="Neutral.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            pair_card,
            text="Refresh Devices",
            command=self.refresh_bonded_devices,
            style="Neutral.TButton",
        ).pack(side=tk.LEFT)

        bond_card = ttk.LabelFrame(
            self, text="Quick Unpair by Index", padding=14, style="Card.TLabelframe"
        )
        bond_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        bond_card.columnconfigure(1, weight=1)

        ttk.Label(
            bond_card,
            text="Unpair by index (1-based):",
            style="Card.TLabel",
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=6)

        self.unpair_index_var = tk.StringVar()
        ttk.Entry(bond_card, textvariable=self.unpair_index_var, width=10).grid(
            row=0, column=1, sticky="w", pady=6
        )

        ttk.Button(
            bond_card, text="Unpair", command=self._unpair_by_index, style="Danger.TButton"
        ).grid(row=0, column=2, padx=(10, 0))

        bond_list_card = ttk.LabelFrame(
            self,
            text="Known Devices (Bonded / Not Bonded)",
            padding=0,
            style="Card.TLabelframe",
        )
        bond_list_card.grid(row=2, column=0, sticky="nsew")
        bond_list_card.columnconfigure(0, weight=1)
        bond_list_card.rowconfigure(0, weight=1)

        tree_frame = ttk.Frame(bond_list_card)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.grid(row=0, column=1, sticky="ns")

        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.grid(row=1, column=0, sticky="ew")

        self._bonded_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "address", "bonded", "action"),
            height=10,
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            style="Treeview",
        )
        self._bonded_tree.grid(row=0, column=0, sticky="nsew")
        vsb.config(command=self._bonded_tree.yview)
        hsb.config(command=self._bonded_tree.xview)

        self._bonded_tree.column("#0", width=0, stretch=False)
        self._bonded_tree.column("name", anchor=tk.W, width=200)
        self._bonded_tree.column("address", anchor=tk.W, width=220)
        self._bonded_tree.column("bonded", anchor=tk.CENTER, width=120)
        self._bonded_tree.column("action", anchor=tk.CENTER, width=120)

        self._bonded_tree.heading("#0", text="", anchor=tk.W)
        self._bonded_tree.heading("name", text="Device Name", anchor=tk.W)
        self._bonded_tree.heading("address", text="Address", anchor=tk.W)
        self._bonded_tree.heading("bonded", text="Bonded", anchor=tk.CENTER)
        self._bonded_tree.heading("action", text="Action", anchor=tk.CENTER)

        self._bonded_tree.bind("<Button-1>", self._on_tree_click)

        self.refresh_bonded_devices()

    def _on_pairing_action_success(self) -> None:
        self.pairing_status_var.set("Status: Pairing/security operation completed")
        self.refresh_bonded_devices()

    def _collect_known_devices(self) -> List[Dict[str, str]]:
        app = self.backend.app
        connector = app.connector

        bonded_map = connector.get_bonded_devices()
        discovered = getattr(app, "discovered_devices", {}) or {}
        # Only show the connected-but-not-bonded device when truly connected
        current_addr = app.current_device if app.connected else None

        merged: Dict[str, Dict[str, str]] = {}

        for address in bonded_map.keys():
            display_name = address
            info = discovered.get(address, {}) if isinstance(discovered, dict) else {}
            if isinstance(info, dict):
                maybe_name = (info.get("name") or "").strip()
                if maybe_name:
                    display_name = maybe_name
            merged[address] = {
                "name": display_name,
                "address": address,
                "bonded": "Yes",
                "action": "Unpair",
            }

        if current_addr and current_addr not in merged:
            current_name = current_addr
            info = discovered.get(current_addr, {}) if isinstance(discovered, dict) else {}
            if isinstance(info, dict):
                maybe_name = (info.get("name") or "").strip()
                if maybe_name:
                    current_name = maybe_name
            merged[current_addr] = {
                "name": current_name,
                "address": current_addr,
                "bonded": "No",
                "action": "",
            }

        devices = list(merged.values())
        devices.sort(key=lambda d: (d["bonded"] != "Yes", d["address"]))
        return devices

    def refresh_bonded_devices(self) -> None:
        if not self._bonded_tree:
            return

        self._row_address_by_iid.clear()
        for item in self._bonded_tree.get_children():
            self._bonded_tree.delete(item)

        if self.backend is None or self.backend.app is None:
            self.pairing_status_var.set("Status: Start backend to view device security status")
            return

        try:
            devices = self._collect_known_devices()
            if not devices:
                self.pairing_status_var.set("Status: No known devices yet")
                return

            bonded_count = sum(1 for d in devices if d["bonded"] == "Yes")
            self.pairing_status_var.set(
                f"Status: {bonded_count} bonded device(s), {len(devices)} known device(s)"
            )

            for idx, device in enumerate(devices):
                iid = f"dev_{idx}"
                self._row_address_by_iid[iid] = device["address"]
                self._bonded_tree.insert(
                    "",
                    tk.END,
                    iid=iid,
                    values=(
                        device["name"],
                        device["address"],
                        device["bonded"],
                        device["action"],
                    ),
                )
        except Exception as exc:
            self.log(f"Error loading devices: {exc}")
            self.pairing_status_var.set("Status: Failed to load security device list")

    def _on_tree_click(self, event) -> None:
        if not self._bonded_tree:
            return

        item = self._bonded_tree.identify("item", event.x, event.y)
        col = self._bonded_tree.identify_column(event.x)
        if not item or col != "#4":
            return

        values = self._bonded_tree.item(item, "values")
        if len(values) < 4 or values[3] != "Unpair":
            return

        address = self._row_address_by_iid.get(item)
        if address:
            self._unpair_by_address(address)

    def _unpair_by_address(self, address: str) -> None:
        if not messagebox.askyesno(
            "Confirm Unpair",
            f"Unpair device {address}?\n\nBonding keys will be deleted.",
        ):
            return

        def _on_success() -> None:
            self.refresh_bonded_devices()

        self.run_action(
            f"Unpair {address}",
            lambda app: app.app_unpair(address=address, show_bonded_devices=False),
            on_success=_on_success,
        )

    def _unpair_by_index(self) -> None:
        raw = self.unpair_index_var.get().strip()
        if not raw:
            messagebox.showerror("Missing index", "Enter 1-based bonded device index")
            return

        try:
            index = int(raw)
        except ValueError:
            messagebox.showerror("Invalid index", "Index must be an integer")
            return

        def _on_success() -> None:
            self.refresh_bonded_devices()

        self.run_action(
            "Unpair",
            lambda app: app.app_unpair(index=index, show_bonded_devices=False),
            on_success=_on_success,
        )
