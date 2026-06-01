"""Bridge page — runs the bumble HCI bridge in-process."""
from __future__ import annotations

import asyncio
import io
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional, Tuple, TYPE_CHECKING

from hciemu.gui.pages.base import BasePage
from hciemu.gui.theme import (
    CARD_BG, CARD_BORDER, TEXT, TEXT_MUTED, ACCENT,
    ENTRY_BG, BG, SIDEBAR_BG, LOG_BG,
)

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui


# ── In-process bridge ────────────────────────────────────────────────────────

class _StreamToQueue(io.TextIOBase):
    """Forwards written text line-by-line to a queue."""

    def __init__(self, q: "queue.Queue[str]"):
        self._q = q
        self._buf = ""

    def write(self, s: str) -> int:  # type: ignore[override]
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._q.put(line)
        return len(s)

    def flush(self) -> None:
        if self._buf:
            self._q.put(self._buf)
            self._buf = ""


class _InProcessBridge:
    """Runs bumble HCI bridge inside a daemon thread with its own asyncio loop."""

    def __init__(self, source: str, target: str, out_queue: "queue.Queue[str]"):
        self._source = source
        self._target = target
        self._q = out_queue
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="hci-bridge-loop"
        )
        self._thread.start()

    def stop(self) -> None:
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._cancel_all)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _cancel_all(self) -> None:
        loop = self._loop
        if loop:
            for task in asyncio.all_tasks(loop):
                task.cancel()

    def _run(self) -> None:
        from bumble.apps.hci_bridge import async_main  # type: ignore
        writer = _StreamToQueue(self._q)
        saved_out, saved_err = sys.stdout, sys.stderr
        saved_argv = sys.argv[:]
        sys.stdout = writer  # type: ignore[assignment]
        sys.stderr = writer  # type: ignore[assignment]
        sys.argv = ["hci_bridge", self._source, self._target]
        try:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            loop.run_until_complete(async_main())
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._q.put(f"[Bridge error] {exc}")
        finally:
            sys.stdout = saved_out
            sys.stderr = saved_err
            sys.argv = saved_argv
            loop = self._loop
            if loop and not loop.is_closed():
                loop.close()
            self._loop = None


# ── ANSI colour codes → hex ───────────────────────────────────────────────────
_ANSI_COLORS = {
    30: "#c0c0c0", 31: "#d32f2f", 32: "#2e7d32", 33: "#f9a825",
    34: "#5c8ee0", 35: "#8e24aa", 36: "#00838f", 37: "#e0e0e0",
    90: "#757575", 91: "#ef5350", 92: "#66bb6a", 93: "#ffeb3b",
    94: "#42a5f5", 95: "#ab47bc", 96: "#26c6da", 97: "#ffffff",
}
_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


class BridgePage(BasePage):
    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, gui)

        self._inproc: Optional[_InProcessBridge] = None
        self._output_queue: queue.Queue[str] = queue.Queue()
        self._poll_job: Optional[str] = None
        self.bridge_window: Optional[tk.Toplevel] = None
        self.bridge_detached = False
        self.bridge_log_lines: List[str] = []
        self.bridge_log_text: Optional[tk.Text] = None
        self.bridge_window_log_text: Optional[tk.Text] = None

        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Bridge controls ────────────────────────────────────────────
        ctrl = ttk.LabelFrame(self, text="Bridge Control", padding=14,
                               style="Card.TLabelframe")
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ctrl.columnconfigure(1, weight=1)

        ttk.Label(ctrl, text="Source:", style="Card.TLabel").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(ctrl, textvariable=self.gui.bridge_source_var).grid(
            row=0, column=1, sticky="ew", pady=5)

        ttk.Label(ctrl, text="Target:", style="Card.TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(ctrl, textvariable=self.gui.bridge_target_var).grid(
            row=1, column=1, sticky="ew", pady=5)

        btn_row = ttk.Frame(ctrl, style="Card.TFrame")
        btn_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(btn_row, text="▶  Start Bridge", command=self.start_bridge,
                   style="Success.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="■  Stop Bridge", command=self.stop_bridge,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 18))
        ttk.Label(btn_row, text="Status:", style="Card.Muted.TLabel").pack(
            side=tk.LEFT, padx=(0, 6))
        self._status_label = ttk.Label(btn_row, textvariable=self.gui.bridge_status_var,
                                        style="Card.TLabel",
                                        font=("Segoe UI Semibold", 10),
                                        foreground=TEXT_MUTED)
        self._status_label.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Open in Window", command=self.detach,
                   style="Neutral.TButton").pack(side=tk.RIGHT)

        # ── Bridge log ─────────────────────────────────────────────────
        log_card = ttk.LabelFrame(self, text="Bridge Log", padding=8,
                                   style="Card.TLabelframe")
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(0, weight=1)

        self.bridge_log_text = tk.Text(
            log_card, wrap=tk.WORD,
            background=LOG_BG, foreground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0,
            insertbackground=TEXT,
            padx=10, pady=8, font=("Consolas", 10),
        )
        self.bridge_log_text.grid(row=0, column=0, sticky="nsew")
        self.bridge_log_text.configure(state=tk.DISABLED)
        self._setup_ansi_tags(self.bridge_log_text)

        vsb = ttk.Scrollbar(log_card, orient=tk.VERTICAL,
                             command=self.bridge_log_text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.bridge_log_text.configure(yscrollcommand=vsb.set)

    # ── Bridge process ────────────────────────────────────────────────────

    def start_bridge(self) -> None:
        if self._inproc is not None and self._inproc.is_alive():
            messagebox.showinfo("Bridge running", "Bridge is already running.")
            return
        source = self.gui.bridge_source_var.get().strip() or "usb:0"
        target = self.gui.bridge_target_var.get().strip() or "tcp-server:127.0.0.1:9001"
        try:
            self._inproc = _InProcessBridge(source, target, self._output_queue)
            self._inproc.start()
            self.gui.bridge_status_var.set("Bridge: Running")
            self._update_status_color()
            self.bridge_log(f"Bridge started: {source}  →  {target}")
            if self._poll_job is None:
                self._poll_output()
        except Exception as exc:
            self._inproc = None
            self.gui.bridge_status_var.set("Bridge: Stopped")
            messagebox.showerror("Bridge error", str(exc))

    def stop_bridge(self) -> None:
        if self._inproc is not None:
            self._inproc.stop()
            self._inproc = None
        self.gui.bridge_status_var.set("Bridge: Stopped")
        self._update_status_color()
        self.bridge_log("Bridge stopped")

    def _poll_output(self) -> None:
        while True:
            try:
                self.bridge_log(self._output_queue.get_nowait())
            except queue.Empty:
                break
        if self._inproc is not None and self._inproc.is_alive():
            self._poll_job = self.gui.after(200, self._poll_output)
            return
        if self._inproc is not None:
            self.bridge_log("Bridge finished")
            self._inproc = None
            self.gui.bridge_status_var.set("Bridge: Stopped")
            self._update_status_color()
        self._poll_job = None

    def _update_status_color(self) -> None:
        running = "running" in self.gui.bridge_status_var.get().strip().lower()
        from hciemu.gui.theme import SUCCESS, DANGER
        try:
            self._status_label.configure(foreground=SUCCESS if running else DANGER)
        except Exception:
            pass

    # ── Bridge log ─────────────────────────────────────────────────────────

    def bridge_log(self, message: str) -> None:
        self.bridge_log_lines.append(message)
        self._append_colored(self.bridge_log_text, message)
        self._append_colored(self.bridge_window_log_text, message)

    def _setup_ansi_tags(self, widget: tk.Text) -> None:
        widget.tag_configure("_default", foreground=TEXT)
        for code, color in _ANSI_COLORS.items():
            widget.tag_configure(f"_ansi{code}", foreground=color)

    def _parse_ansi(self, line: str) -> List[Tuple[str, str]]:
        segments: List[Tuple[str, str]] = []
        last = 0
        tag = "_default"
        for m in _ANSI_RE.finditer(line):
            s, e = m.span()
            if s > last:
                segments.append((line[last:s], tag))
            codes = m.group(1)
            if codes in ("", "0"):
                tag = "_default"
            else:
                for part in codes.split(";"):
                    try:
                        c = int(part)
                        if c == 0:
                            tag = "_default"
                        elif c in _ANSI_COLORS:
                            tag = f"_ansi{c}"
                    except ValueError:
                        pass
            last = e
        if last < len(line):
            segments.append((line[last:], tag))
        return segments or [(line, "_default")]

    def _append_colored(self, widget: Optional[tk.Text], message: str) -> None:
        if widget is None:
            return
        widget.configure(state=tk.NORMAL)
        for chunk, tag in self._parse_ansi(message):
            if chunk:
                widget.insert(tk.END, chunk, tag)
        widget.insert(tk.END, "\n", "_default")
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    # ── Detach / reattach ──────────────────────────────────────────────────

    def detach(self) -> None:
        if self.bridge_detached:
            if self.bridge_window:
                self.bridge_window.lift()
            return
        win = tk.Toplevel(self.gui)
        win.title("Bridge Control")
        win.geometry("860x560")
        win.configure(bg=BG)
        win.protocol("WM_DELETE_WINDOW", self.reattach)
        self.bridge_window = win
        self.bridge_detached = True

        f = ttk.Frame(win, padding=16, style="App.TFrame")
        f.pack(fill=tk.BOTH, expand=True)
        self._build_detached_controls(f)
        self.bridge_log("Bridge opened in separate window")

    def reattach(self) -> None:
        if self.bridge_window:
            self.bridge_window.destroy()
            self.bridge_window = None
        self.bridge_window_log_text = None
        self.bridge_detached = False
        self.bridge_log("Bridge window closed")

    def _build_detached_controls(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(4, weight=1)

        ttk.Label(parent, text="Source:", style="TLabel").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(parent, textvariable=self.gui.bridge_source_var, width=40).grid(
            row=0, column=1, sticky="ew", pady=5)

        ttk.Label(parent, text="Target:", style="TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        ttk.Entry(parent, textvariable=self.gui.bridge_target_var, width=40).grid(
            row=1, column=1, sticky="ew", pady=5)

        btn_row = ttk.Frame(parent, style="App.TFrame")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(btn_row, text="▶  Start", command=self.start_bridge,
                   style="Success.TButton").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="■  Stop", command=self.stop_bridge,
                   style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 18))
        ttk.Label(btn_row, textvariable=self.gui.bridge_status_var,
                  font=("Segoe UI Semibold", 10)).pack(side=tk.LEFT, padx=(0, 18))
        ttk.Button(btn_row, text="Dock Back", command=self.reattach,
                   style="Neutral.TButton").pack(side=tk.LEFT)

        log_card = ttk.LabelFrame(parent, text="Bridge Log", padding=8,
                                   style="Card.TLabelframe")
        log_card.grid(row=4, column=0, columnspan=2, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(0, weight=1)

        self.bridge_window_log_text = tk.Text(
            log_card, wrap=tk.WORD,
            background=LOG_BG, foreground=TEXT,
            relief="flat", borderwidth=0, highlightthickness=0,
            insertbackground=TEXT,
            padx=10, pady=8, font=("Consolas", 10),
        )
        self.bridge_window_log_text.grid(row=0, column=0, sticky="nsew")
        self.bridge_window_log_text.configure(state=tk.DISABLED)
        self._setup_ansi_tags(self.bridge_window_log_text)

        vsb = ttk.Scrollbar(log_card, orient=tk.VERTICAL,
                             command=self.bridge_window_log_text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.bridge_window_log_text.configure(yscrollcommand=vsb.set)

        # replay existing log
        for line in self.bridge_log_lines:
            self._append_colored(self.bridge_window_log_text, line)
