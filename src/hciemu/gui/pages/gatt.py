"""GATT Explorer page."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from hciemu.gui.pages.base import BasePage
from hciemu.gui.theme import CARD_BG, LOG_BG, TEXT, TEXT_MUTED

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui
    from hciemu.app import BLETestingApp


class GATTPage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)
        self._read_choice_var = tk.StringVar()
        self._write_choice_var = tk.StringVar()
        self._selected_handle_var = tk.StringVar(value="No characteristic selected")
        self._subscription_summary_var = tk.StringVar(value="No active subscriptions")
        self._services_tree: Optional[ttk.Treeview] = None
        self._read_choice_combo = None
        self._write_choice_combo = None
        self._read_choices: List[Dict[str, Any]] = []
        self._write_choices: List[Dict[str, Any]] = []
        self._row_handle_by_iid: Dict[str, int] = {}
        self._subscription_modes: Dict[int, str] = {}
        self._read_history_tree: Optional[ttk.Treeview] = None
        self._packet_history_tree: Optional[ttk.Treeview] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._read_tab = None
        self._write_tab = None
        self._last_tree_click: Optional[tuple[int, str, str]] = None
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        workspace = ttk.LabelFrame(self, text="GATT Workspace", padding=12, style="Card.TLabelframe")
        workspace.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        workspace.columnconfigure(1, weight=1)

        ttk.Button(
            workspace,
            text="Discover Services",
            command=self.discover_services,
            style="Accent.TButton",
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))

        ttk.Label(workspace, text="Selected handle", style="Card.Muted.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        selection = tk.Label(
            workspace,
            textvariable=self._selected_handle_var,
            bg=LOG_BG,
            fg=TEXT,
            font=("Consolas", 9),
            padx=10,
            pady=7,
            anchor="w",
        )
        selection.grid(row=1, column=1, sticky="ew", padx=(0, 12))

        subscription = tk.Label(
            workspace,
            textvariable=self._subscription_summary_var,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            anchor="e",
            justify=tk.RIGHT,
        )
        subscription.grid(row=0, column=2, rowspan=2, sticky="e")

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky="nsew")
        self._notebook = notebook

        services_tab = ttk.Frame(notebook, style="App.TFrame")
        read_tab = ttk.Frame(notebook, style="App.TFrame")
        write_tab = ttk.Frame(notebook, style="App.TFrame")
        packets_tab = ttk.Frame(notebook, style="App.TFrame")
        self._read_tab = read_tab
        self._write_tab = write_tab

        notebook.add(services_tab, text="Services")
        notebook.add(read_tab, text="Read")
        notebook.add(write_tab, text="Write")
        notebook.add(packets_tab, text="Notifications")

        self._build_services_tab(services_tab)
        self._build_read_tab(read_tab)
        self._build_write_tab(write_tab)
        self._build_packets_tab(packets_tab)

    def _build_services_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        actions = ttk.LabelFrame(parent, text="Characteristic Actions", padding=12, style="Card.TLabelframe")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ttk.Button(actions, text="Read Selected", command=self._read_selected_from_services,
                   style="Neutral.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Open Write Page", command=self._open_write_for_selected,
                   style="Neutral.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Subscribe Notify", command=self.subscribe_notify,
                   style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Subscribe Indicate", command=self.subscribe_indicate,
                   style="Neutral.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Unsubscribe", command=self.unsubscribe_current,
                   style="Danger.TButton").pack(side=tk.LEFT)

        table_card = ttk.LabelFrame(parent, text="Discovered Characteristics", padding=8,
                                    style="Card.TLabelframe")
        table_card.grid(row=1, column=0, sticky="nsew")
        table_card.columnconfigure(0, weight=1)
        table_card.rowconfigure(0, weight=1)

        cols = ("handle", "service", "uuid", "properties", "description", "subscription")
        self._services_tree = ttk.Treeview(
            table_card,
            columns=cols,
            show="headings",
            selectmode="browse",
            style="Treeview",
        )
        self._services_tree.heading("handle", text="Handle")
        self._services_tree.heading("service", text="Service")
        self._services_tree.heading("uuid", text="Characteristic UUID")
        self._services_tree.heading("properties", text="Properties")
        self._services_tree.heading("description", text="Description")
        self._services_tree.heading("subscription", text="Subscription")
        self._services_tree.column("handle", width=120, stretch=False)
        self._services_tree.column("service", width=220, stretch=False)
        self._services_tree.column("uuid", width=270, stretch=False)
        self._services_tree.column("properties", width=190, stretch=False)
        self._services_tree.column("description", width=280, stretch=True)
        self._services_tree.column("subscription", width=130, stretch=False, anchor=tk.CENTER)
        self._services_tree.grid(row=0, column=0, sticky="nsew")
        self._services_tree.bind("<<TreeviewSelect>>", self._on_service_selected)
        self._services_tree.bind("<Double-Button-1>", lambda _e: self._read_selected_from_services())
        self._bind_tree_copy(self._services_tree)

        vsb = ttk.Scrollbar(table_card, orient=tk.VERTICAL, command=self._services_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(table_card, orient=tk.HORIZONTAL, command=self._services_tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._services_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    def _build_read_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        read_ops = ttk.LabelFrame(parent, text="Read Operations", padding=12, style="Card.TLabelframe")
        read_ops.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        read_ops.columnconfigure(1, weight=1)

        ttk.Label(read_ops, text="Handle:", style="Card.TLabel").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4
        )
        ttk.Entry(read_ops, textvariable=self.gui.read_handle_var, width=16).grid(
            row=0, column=1, sticky="w", pady=4
        )
        ttk.Button(read_ops, text="Read Handle", command=self.read_characteristic,
                   style="Accent.TButton").grid(row=0, column=2, padx=(10, 0), pady=4)

        ttk.Label(read_ops, text="Readable characteristic:", style="Card.TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4
        )
        self._read_choice_combo = ttk.Combobox(
            read_ops,
            textvariable=self._read_choice_var,
            state="readonly",
            width=72,
            values=[],
        )
        self._read_choice_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self._read_choice_combo.bind("<<ComboboxSelected>>", self._on_read_choice_selected)

        ttk.Button(read_ops, text="Read Selected", command=self.read_selected_characteristic,
                   style="Neutral.TButton").grid(row=1, column=2, padx=(10, 0), pady=4)
        ttk.Button(read_ops, text="Clear History", command=self.clear_read_history,
                   style="Neutral.TButton").grid(row=2, column=2, padx=(10, 0), pady=(8, 0))

        history_card = ttk.LabelFrame(parent, text="Read Responses", padding=8, style="Card.TLabelframe")
        history_card.grid(row=1, column=0, sticky="nsew")
        history_card.columnconfigure(0, weight=1)
        history_card.rowconfigure(0, weight=1)

        cols = ("handle", "description", "length", "value")
        self._read_history_tree = ttk.Treeview(
            history_card,
            columns=cols,
            show="tree headings",
            selectmode="extended",
            style="Treeview",
        )
        self._read_history_tree.heading("#0", text="Packet")
        self._read_history_tree.heading("handle", text="Handle")
        self._read_history_tree.heading("description", text="Description")
        self._read_history_tree.heading("length", text="Length")
        self._read_history_tree.heading("value", text="Value")
        self._read_history_tree.column("#0", width=150, stretch=False)
        self._read_history_tree.column("handle", width=130, stretch=False)
        self._read_history_tree.column("description", width=260, stretch=True)
        self._read_history_tree.column("length", width=90, stretch=False, anchor=tk.CENTER)
        self._read_history_tree.column("value", width=420, stretch=True)
        self._read_history_tree.tag_configure("packet", foreground=TEXT)
        self._read_history_tree.tag_configure("detail", foreground=TEXT_MUTED)
        self._read_history_tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(history_card, orient=tk.VERTICAL, command=self._read_history_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(history_card, orient=tk.HORIZONTAL, command=self._read_history_tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._read_history_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._bind_tree_copy(self._read_history_tree)

    def _build_write_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        write_ops = ttk.LabelFrame(parent, text="Write Operations", padding=12, style="Card.TLabelframe")
        write_ops.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        write_ops.columnconfigure(1, weight=1)

        ttk.Label(write_ops, text="Handle:", style="Card.TLabel").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=4
        )
        ttk.Entry(write_ops, textvariable=self.gui.write_handle_var, width=16).grid(
            row=0, column=1, sticky="w", pady=4
        )

        ttk.Label(write_ops, text="Writable characteristic:", style="Card.TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=4
        )
        self._write_choice_combo = ttk.Combobox(
            write_ops,
            textvariable=self._write_choice_var,
            state="readonly",
            width=72,
            values=[],
        )
        self._write_choice_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self._write_choice_combo.bind("<<ComboboxSelected>>", self._on_write_choice_selected)

        ttk.Label(write_ops, text="Hex value:", style="Card.TLabel").grid(
            row=2, column=0, sticky="e", padx=(0, 8), pady=4
        )
        ttk.Entry(write_ops, textvariable=self.gui.write_value_var, width=48).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Button(write_ops, text="Write", command=self.write_characteristic,
                   style="Accent.TButton").grid(row=2, column=2, padx=(10, 6), pady=4)
        ttk.Button(write_ops, text="Write NoRsp", command=self.write_without_response,
                   style="Neutral.TButton").grid(row=2, column=3, pady=4)

        preview_card = ttk.LabelFrame(parent, text="Write Notes", padding=12, style="Card.TLabelframe")
        preview_card.grid(row=1, column=0, sticky="nsew")
        preview = tk.Label(
            preview_card,
            text=(
                "Pick a writable characteristic from discovery, enter a hex payload, and use Write or "
                "Write NoRsp depending on the characteristic properties."
            ),
            bg=CARD_BG,
            fg=TEXT_MUTED,
            justify=tk.LEFT,
            wraplength=760,
            padx=4,
            pady=4,
        )
        preview.pack(anchor="w")

    def _build_packets_tab(self, parent) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        actions = ttk.LabelFrame(parent, text="Notifications & Indications", padding=12, style="Card.TLabelframe")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(actions, text="Clear Packets", command=self.clear_packet_history,
                   style="Neutral.TButton").pack(side=tk.RIGHT)
        tk.Label(
            actions,
            text="Incoming packets from subscribed characteristics appear here.",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
        ).pack(side=tk.LEFT)

        packets_card = ttk.LabelFrame(parent, text="Packet History", padding=8, style="Card.TLabelframe")
        packets_card.grid(row=1, column=0, sticky="nsew")
        packets_card.columnconfigure(0, weight=1)
        packets_card.rowconfigure(0, weight=1)

        cols = ("type", "handle", "description", "length", "value")
        self._packet_history_tree = ttk.Treeview(
            packets_card,
            columns=cols,
            show="tree headings",
            selectmode="extended",
            style="Treeview",
        )
        self._packet_history_tree.heading("#0", text="Packet")
        self._packet_history_tree.heading("type", text="Type")
        self._packet_history_tree.heading("handle", text="Handle")
        self._packet_history_tree.heading("description", text="Description")
        self._packet_history_tree.heading("length", text="Length")
        self._packet_history_tree.heading("value", text="Value")
        self._packet_history_tree.column("#0", width=160, stretch=False)
        self._packet_history_tree.column("type", width=120, stretch=False)
        self._packet_history_tree.column("handle", width=130, stretch=False)
        self._packet_history_tree.column("description", width=260, stretch=True)
        self._packet_history_tree.column("length", width=90, stretch=False, anchor=tk.CENTER)
        self._packet_history_tree.column("value", width=360, stretch=True)
        self._packet_history_tree.tag_configure("packet", foreground=TEXT)
        self._packet_history_tree.tag_configure("detail", foreground=TEXT_MUTED)
        self._packet_history_tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(packets_card, orient=tk.VERTICAL, command=self._packet_history_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(packets_card, orient=tk.HORIZONTAL, command=self._packet_history_tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self._packet_history_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._bind_tree_copy(self._packet_history_tree)

    def _bind_tree_copy(self, tree: ttk.Treeview) -> None:
        tree.bind("<Button-1>", lambda event, t=tree: self._on_tree_click(t, event), add="+")
        tree.bind("<Button-3>", lambda event, t=tree: self._show_tree_context_menu(t, event), add="+")
        tree.bind("<Control-c>", lambda event, t=tree: self._copy_tree_selection(t, event), add="+")
        tree.bind("<Control-C>", lambda event, t=tree: self._copy_tree_selection(t, event), add="+")

    def _on_tree_click(self, tree: ttk.Treeview, event) -> None:
        row = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if row:
            self._last_tree_click = (id(tree), row, col)

    def _show_tree_context_menu(self, tree: ttk.Treeview, event):
        row = tree.identify_row(event.y)
        col = tree.identify_column(event.x)
        if row:
            tree.selection_set(row)
            tree.focus(row)
            self._last_tree_click = (id(tree), row, col)

        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Copy Cell", command=lambda t=tree: self._copy_tree_cell_from_last_click(t))
        menu.add_command(label="Copy Row", command=lambda t=tree: self._copy_tree_row_from_focus(t))
        menu.add_command(label="Copy Selected Rows", command=lambda t=tree: self._copy_tree_selection(t))
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    @staticmethod
    def _tree_cell_text(tree: ttk.Treeview, row: str, col: str) -> str:
        item = tree.item(row)
        if col == "#0":
            return str(item.get("text") or "")

        if not col.startswith("#"):
            return ""
        try:
            index = int(col[1:]) - 1
        except ValueError:
            return ""

        values = item.get("values", ())
        if 0 <= index < len(values):
            return str(values[index])
        return ""

    def _copy_text_to_clipboard(self, text: str) -> None:
        if not text:
            return
        self.gui.clipboard_clear()
        self.gui.clipboard_append(text)
        self.gui.update_idletasks()

    def _copy_tree_cell_from_last_click(self, tree: ttk.Treeview) -> bool:
        if self._last_tree_click is None:
            return False
        tree_id, row, col = self._last_tree_click
        if tree_id != id(tree):
            return False
        text = self._tree_cell_text(tree, row, col).strip()
        if not text:
            return False
        self._copy_text_to_clipboard(text)
        return True

    def _copy_tree_row_from_focus(self, tree: ttk.Treeview) -> bool:
        focused = tree.focus()
        if not focused:
            return False
        item = tree.item(focused)
        row_parts = []
        text = str(item.get("text") or "").strip()
        if text:
            row_parts.append(text)
        row_parts.extend(str(value) for value in item.get("values", ()))
        payload = "\t".join(row_parts).strip()
        if not payload:
            return False
        self._copy_text_to_clipboard(payload)
        return True

    def _copy_tree_selection(self, tree: ttk.Treeview, _event=None):
        if self._copy_tree_cell_from_last_click(tree):
            return "break"

        selected = list(tree.selection())
        if not selected:
            focused = tree.focus()
            if focused:
                selected = [focused]
        if not selected:
            return "break"

        lines: List[str] = []
        for iid in selected:
            item = tree.item(iid)
            row_parts = []
            text = str(item.get("text") or "").strip()
            if text:
                row_parts.append(text)
            row_parts.extend(str(value) for value in item.get("values", ()))
            lines.append("\t".join(row_parts).rstrip())

        text_payload = "\n".join(lines).strip()
        if text_payload:
            self._copy_text_to_clipboard(text_payload)
        return "break"

    def discover_services(self) -> None:
        if not self._ensure_backend():
            return
        self.log("Running: Discover Services")

        async def _do(app: "BLETestingApp"):
            return await app.app_discover_services()

        def _done(f):
            def _fill():
                try:
                    details = f.result()
                    self._populate_services_table(details)
                    self._set_readable_choices_from_details(details)
                    self._set_writable_choices_from_details(details)
                    self.log(f"Done: Discover Services - {len(details)} service(s)")
                except Exception as exc:
                    self.log(f"Error: Discover Services: {exc}")
                    messagebox.showerror("Discover Services failed", str(exc))
            self.gui.after(0, _fill)

        self.backend.submit(_do).add_done_callback(_done)

    def _populate_services_table(self, details: list) -> None:
        if self._services_tree is None:
            return

        tree = self._services_tree
        tree.delete(*tree.get_children())
        self._row_handle_by_iid.clear()

        def _lookup_name(uuid_value: str) -> str:
            try:
                return self.backend.app._lookup_uuid_name(uuid_value) or ""
            except Exception:
                return ""

        rows: List[Dict[str, Any]] = []
        for service in details or []:
            service_uuid = str(service.get("uuid", ""))
            service_name = _lookup_name(service_uuid) or service_uuid or "-"
            for char in service.get("characteristics", []):
                handle = char.get("handle")
                if handle is None:
                    continue
                char_uuid = str(char.get("uuid", ""))
                char_name = _lookup_name(char_uuid) or char_uuid or "-"
                properties = str(char.get("properties", ""))
                rows.append(
                    {
                        "handle": int(handle),
                        "service": service_name,
                        "uuid": char_uuid or "-",
                        "properties": properties,
                        "description": char_name,
                    }
                )

        rows.sort(key=lambda row: row["handle"])
        for row in rows:
            handle = row["handle"]
            iid = f"char_{handle}"
            self._row_handle_by_iid[iid] = handle
            subscription = self._subscription_modes.get(handle, "off").title()
            tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    f"0x{handle:04X} ({handle})",
                    row["service"],
                    row["uuid"],
                    row["properties"],
                    row["description"],
                    subscription,
                ),
            )

    def _set_readable_choices_from_details(self, details: list) -> None:
        self._read_choices = self._build_characteristic_choices(details, lambda props: "read" in props.lower())
        self._apply_choice_values(self._read_choice_combo, self._read_choice_var, self._read_choices)

    def _set_writable_choices_from_details(self, details: list) -> None:
        def _is_writable(properties: str) -> bool:
            return "write" in properties.lower()

        self._write_choices = self._build_characteristic_choices(details, _is_writable)
        self._apply_choice_values(self._write_choice_combo, self._write_choice_var, self._write_choices)

    def _build_characteristic_choices(self, details: list, predicate) -> List[Dict[str, Any]]:
        lookup_name = None
        try:
            if self.backend is not None and self.backend.app is not None:
                lookup_name = self.backend.app._lookup_uuid_name
        except Exception:
            lookup_name = None

        items: List[Dict[str, Any]] = []
        for service in details or []:
            for char in service.get("characteristics", []):
                handle = char.get("handle")
                if handle is None:
                    continue
                properties = str(char.get("properties", ""))
                if not predicate(properties):
                    continue
                uuid = str(char.get("uuid", ""))
                description = lookup_name(uuid) if lookup_name else ""
                description = description or ""
                label = f"0x{int(handle):04X} ({int(handle)})"
                if description:
                    label = f"{label} - {description}"
                elif uuid:
                    label = f"{label} - {uuid}"
                items.append(
                    {
                        "handle": int(handle),
                        "uuid": uuid,
                        "description": description,
                        "properties": properties,
                        "label": label,
                    }
                )

        items.sort(key=lambda item: int(item["handle"]))
        return items

    def _apply_choice_values(self, combo, variable: tk.StringVar, items: List[Dict[str, Any]]) -> None:
        labels = [item["label"] for item in items]
        if combo is not None:
            combo.configure(values=labels)
        if labels:
            current = variable.get().strip()
            if current not in labels:
                variable.set(labels[0])
        else:
            variable.set("")

    def _on_service_selected(self, _event=None) -> None:
        handle = self._selected_service_handle()
        if handle is not None:
            self._sync_selected_handle(handle)

    def _selected_service_handle(self) -> Optional[int]:
        if self._services_tree is None:
            return None
        selection = self._services_tree.selection()
        if not selection:
            return None
        return self._row_handle_by_iid.get(selection[0])

    def _sync_selected_handle(self, handle: int) -> None:
        self.gui.read_handle_var.set(str(handle))
        self.gui.write_handle_var.set(str(handle))
        self._selected_handle_var.set(f"0x{handle:04X} ({handle})")
        self._select_choice_for_handle(self._read_choices, self._read_choice_var, handle)
        self._select_choice_for_handle(self._write_choices, self._write_choice_var, handle)

    @staticmethod
    def _select_choice_for_handle(items: List[Dict[str, Any]], variable: tk.StringVar, handle: int) -> None:
        for item in items:
            if int(item.get("handle", -1)) == handle:
                variable.set(item.get("label", ""))
                break

    def _read_selected_from_services(self) -> None:
        handle = self._selected_service_handle()
        if handle is None:
            messagebox.showerror("Missing selection", "Select a characteristic from the Services table first")
            return
        self._sync_selected_handle(handle)
        if self._notebook is not None and self._read_tab is not None:
            self._notebook.select(self._read_tab)
        self._read_handle_async(str(handle))

    def _open_write_for_selected(self) -> None:
        handle = self._selected_service_handle()
        if handle is None:
            messagebox.showerror("Missing selection", "Select a characteristic from the Services table first")
            return
        self._sync_selected_handle(handle)
        if self._notebook is not None and self._write_tab is not None:
            self._notebook.select(self._write_tab)

    def _read_handle_async(self, handle_text: str) -> None:
        if not self._ensure_backend():
            return

        async def _do(app: "BLETestingApp"):
            await app.app_read_characteristic(handle_text, show_table=False)

        def _done(f):
            def _apply():
                try:
                    f.result()
                except ValueError:
                    messagebox.showerror("Invalid handle", "Handle must be decimal or 0x-prefixed hex")
                except Exception as exc:
                    self.log(f"Read error: {exc}")
                    messagebox.showerror("Read failed", str(exc))
            self.gui.after(0, _apply)

        self.backend.submit(_do).add_done_callback(_done)

    def read_characteristic(self) -> None:
        handle = self.gui.read_handle_var.get().strip()
        if not handle:
            messagebox.showerror("Missing handle", "Enter a characteristic handle")
            return
        self._read_handle_async(handle)

    def read_selected_characteristic(self) -> None:
        handle = self._selected_dropdown_handle(self._read_choices, self._read_choice_var)
        if handle is None:
            messagebox.showerror("Missing selection", "Select a readable characteristic first")
            return
        self._sync_selected_handle(handle)
        self._read_handle_async(str(handle))

    def clear_read_history(self) -> None:
        if self._read_history_tree is None:
            return
        self._read_history_tree.delete(*self._read_history_tree.get_children())
        self.log("Read history cleared")

    def clear_packet_history(self) -> None:
        if self._packet_history_tree is None:
            return
        self._packet_history_tree.delete(*self._packet_history_tree.get_children())
        self.log("Notification history cleared")

    @staticmethod
    def _selected_dropdown_handle(items: List[Dict[str, Any]], variable: tk.StringVar) -> Optional[int]:
        label = variable.get().strip()
        if not label:
            return None
        for item in items:
            if item.get("label") == label:
                return int(item.get("handle"))
        return None

    def _on_read_choice_selected(self, _event=None) -> None:
        handle = self._selected_dropdown_handle(self._read_choices, self._read_choice_var)
        if handle is not None:
            self._sync_selected_handle(handle)

    def _on_write_choice_selected(self, _event=None) -> None:
        handle = self._selected_dropdown_handle(self._write_choices, self._write_choice_var)
        if handle is not None:
            self._sync_selected_handle(handle)

    def _append_read_response(self, payload: dict) -> None:
        if self._read_history_tree is None:
            return
        index = len(self._read_history_tree.get_children()) + 1
        label = f"Read #{index}"
        description = payload.get("description") or payload.get("uuid") or "-"
        self._append_packet_record(self._read_history_tree, payload, label, description, packet_type="Read")

    def _append_notification_packet(self, payload: dict) -> None:
        if self._packet_history_tree is None:
            return
        packet_type = str(payload.get("event_type") or "packet").title()
        index = len(self._packet_history_tree.get_children()) + 1
        label = f"{packet_type} #{index}"
        description = payload.get("description") or payload.get("uuid") or "-"
        self._append_packet_record(self._packet_history_tree, payload, label, description, packet_type=packet_type)

    def _append_packet_record(
        self,
        tree: ttk.Treeview,
        payload: dict,
        label: str,
        description: str,
        *,
        packet_type: str,
    ) -> None:
        handle = int(payload.get("handle", 0))
        handle_text = f"0x{handle:04X} ({handle})"
        length = int(payload.get("length", 0))
        hex_value = payload.get("hex", "")
        ascii_value = payload.get("ascii", "")
        uuid = payload.get("uuid") or "-"
        service_uuid = payload.get("service_uuid") or "-"
        preview = hex_value[:48] + ("..." if len(hex_value) > 48 else "")
        has_type_column = "type" in tuple(tree["columns"])

        if has_type_column:
            parent_values = (packet_type, handle_text, description, str(length), preview or "expand for packet details")
            uuid_values = ("", "UUID", uuid, "", uuid)
            service_values = ("", "Service", service_uuid, "", service_uuid)
            hex_values = ("", "HEX", "", "", hex_value)
            ascii_values = ("", "ASCII", "", "", ascii_value)
            length_values = ("", "Length", "", "", str(length))
        else:
            parent_values = (handle_text, description, str(length), preview or "expand for packet details")
            uuid_values = ("", "UUID", "", uuid)
            service_values = ("", "Service", "", service_uuid)
            hex_values = ("", "HEX", "", hex_value)
            ascii_values = ("", "ASCII", "", ascii_value)
            length_values = ("", "Length", "", str(length))

        parent = tree.insert(
            "",
            tk.END,
            text=label,
            values=parent_values,
            tags=("packet",),
            open=False,
        )
        tree.insert(parent, tk.END, text="", values=uuid_values, tags=("detail",))
        tree.insert(parent, tk.END, text="", values=service_values, tags=("detail",))
        tree.insert(parent, tk.END, text="", values=hex_values, tags=("detail",))
        tree.insert(parent, tk.END, text="", values=ascii_values, tags=("detail",))
        tree.insert(parent, tk.END, text="", values=length_values, tags=("detail",))
        tree.see(parent)
        tree.selection_set(parent)
        tree.focus(parent)

    def on_status_message(self, message: str) -> bool:
        read_prefix = "[READ_RESPONSE_JSON] "
        if message.startswith(read_prefix):
            try:
                payload = json.loads(message[len(read_prefix):].strip())
            except Exception as exc:
                self.log(f"Read response parse error: {exc}")
                return True

            self._append_read_response(payload)
            handle = int(payload.get("handle", 0))
            length = int(payload.get("length", 0))
            self.log(f"Read OK: 0x{handle:04X} ({handle}), {length} byte(s)")
            return True

        packet_prefix = "[GATT_PACKET_JSON] "
        if not message.startswith(packet_prefix):
            return False

        try:
            payload = json.loads(message[len(packet_prefix):].strip())
        except Exception as exc:
            self.log(f"GATT packet parse error: {exc}")
            return True

        self._append_notification_packet(payload)
        packet_type = str(payload.get("event_type") or "packet").title()
        handle = int(payload.get("handle", 0))
        length = int(payload.get("length", 0))
        self.log(f"{packet_type} packet: 0x{handle:04X} ({handle}), {length} byte(s)")
        return True

    def write_characteristic(self) -> None:
        handle = self.gui.write_handle_var.get().strip()
        value = self.gui.write_value_var.get().strip()
        if not handle or not value:
            messagebox.showerror("Missing input", "Enter handle and hex value")
            return
        self.run_action("Write", lambda app: app.app_write_characteristic(handle, value, show_table=False))

    def write_without_response(self) -> None:
        handle = self.gui.write_handle_var.get().strip()
        value = self.gui.write_value_var.get().strip()
        if not handle or not value:
            messagebox.showerror("Missing input", "Enter handle and hex value")
            return
        self.run_action("Write NoRsp", lambda app: app.app_write_without_response(handle, value, show_table=False))

    def _current_handle(self) -> Optional[int]:
        selected = self._selected_service_handle()
        if selected is not None:
            return selected
        for value in (self.gui.read_handle_var.get().strip(), self.gui.write_handle_var.get().strip()):
            if not value:
                continue
            try:
                return int(value, 0)
            except ValueError:
                continue
        return None

    def subscribe_notify(self) -> None:
        handle = self._current_handle()
        if handle is None:
            messagebox.showerror("Missing handle", "Select a characteristic handle first")
            return

        self._sync_selected_handle(handle)
        self.run_action(
            "Subscribe Notify",
            lambda app: app.app_subscribe(str(handle), show_table=False),
            on_success=lambda: self._set_subscription_mode(handle, "notify"),
        )

    def subscribe_indicate(self) -> None:
        handle = self._current_handle()
        if handle is None:
            messagebox.showerror("Missing handle", "Select a characteristic handle first")
            return

        self._sync_selected_handle(handle)
        self.run_action(
            "Subscribe Indicate",
            lambda app: app.app_subscribe_indications(str(handle), show_table=False),
            on_success=lambda: self._set_subscription_mode(handle, "indicate"),
        )

    def unsubscribe_current(self) -> None:
        handle = self._current_handle()
        if handle is None:
            messagebox.showerror("Missing handle", "Select a characteristic handle first")
            return

        self._sync_selected_handle(handle)
        self.run_action(
            "Unsubscribe",
            lambda app: app.app_unsubscribe(str(handle)),
            on_success=lambda: self._clear_subscription_mode(handle),
        )

    def _set_subscription_mode(self, handle: int, mode: str) -> None:
        self._subscription_modes[handle] = mode
        self._refresh_subscription_labels()
        self._refresh_service_row(handle)

    def _clear_subscription_mode(self, handle: int) -> None:
        self._subscription_modes.pop(handle, None)
        self._refresh_subscription_labels()
        self._refresh_service_row(handle)

    def _refresh_subscription_labels(self) -> None:
        if not self._subscription_modes:
            self._subscription_summary_var.set("No active subscriptions")
            return
        parts = [f"0x{handle:04X} {mode}" for handle, mode in sorted(self._subscription_modes.items())]
        self._subscription_summary_var.set("Subscriptions: " + ", ".join(parts))

    def _refresh_service_row(self, handle: int) -> None:
        if self._services_tree is None:
            return
        iid = f"char_{handle}"
        if iid not in self._services_tree.get_children():
            return
        values = list(self._services_tree.item(iid, "values"))
        if len(values) >= 6:
            values[5] = self._subscription_modes.get(handle, "off").title()
            self._services_tree.item(iid, values=values)