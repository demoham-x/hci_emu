"""Shared base class for all HCIEMU GUI pages."""
from __future__ import annotations

import asyncio
import concurrent.futures
from tkinter import messagebox
from tkinter import ttk
from typing import Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui
    from hciemu.app import BLETestingApp


class BasePage(ttk.Frame):
    """A page frame that carries a reference to the root GUI for shared state."""

    def __init__(self, parent, gui: "HCIEMUGui"):
        super().__init__(parent, style="App.TFrame")
        self.gui = gui

    # ── Proxy helpers ─────────────────────────────────────────────────────

    def log(self, message: str) -> None:
        self.gui.log(message)

    def _ensure_backend(self) -> bool:
        return self.gui._ensure_backend()

    def run_action(
        self,
        label: str,
        coro_factory: Callable[["BLETestingApp"], asyncio.Future],
        on_success: Optional[Callable[[], None]] = None,
    ) -> None:
        self.gui.run_action(label, coro_factory, on_success)

    @property
    def backend(self):
        return self.gui.backend
