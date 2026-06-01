"""GUI-based pairing delegate for BLE pairing flows."""
from __future__ import annotations

import asyncio
import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from hciemu.gui.main import HCIEMUGui


class GUIPairingDelegate:
    """BLE pairing delegate that shows GUI dialogs instead of terminal prompts."""

    def __init__(self, gui: "HCIEMUGui"):
        """Initialize with reference to main GUI window."""
        self.gui = gui
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._setup_delegate()

    def _setup_delegate(self) -> None:
        """Create the actual Bumble pairing delegate class."""
        from bumble.pairing import PairingDelegate as BumblePairingDelegate

        gui = self.gui
        self_ref = self

        class _GUIPairingDelegateImpl(BumblePairingDelegate):
            async def accept(delegate_self) -> bool:
                """Accept/reject pairing request."""
                gui.log("[PAIRING] Pairing request received")
                result = await self_ref._show_yes_no_dialog(
                    "Pairing Request",
                    "Accept pairing request from peer?"
                )
                return result

            async def confirm(delegate_self, auto: bool = False) -> bool:
                """Confirm Just Works pairing."""
                if auto:
                    gui.log("[PAIRING] Auto-confirming Just Works")
                    return True
                gui.log("[PAIRING] Confirm Just Works pairing")
                result = await self_ref._show_yes_no_dialog(
                    "Confirm Pairing",
                    "Confirm Just Works pairing?"
                )
                return result

            async def compare_numbers(delegate_self, number: int, digits: int) -> bool:
                """Handle Numeric Comparison (Secure Connections)."""
                code = f"{number:0{digits}d}"
                gui.log(f"[PAIRING] Numeric Comparison: {code}")
                result = await self_ref._show_yes_no_dialog(
                    "Confirm Numeric Code",
                    f"Verify this code matches the peer device:\n\n{code}"
                )
                return result

            async def get_number(delegate_self) -> Optional[int]:
                """Get passkey from user."""
                gui.log("[PAIRING] Passkey entry required")
                passkey = await self_ref._show_passkey_dialog()
                if passkey is not None:
                    gui.log(f"[PAIRING] Passkey entered: {passkey}")
                return passkey

            async def display_number(delegate_self, number: int, digits: int) -> None:
                """Display passkey to user."""
                code = f"{number:0{digits}d}"
                gui.log(f"[PAIRING] Display passkey: {code}")
                await self_ref._show_passkey_display(code)

        self.delegate_impl = _GUIPairingDelegateImpl()

    async def _show_yes_no_dialog(self, title: str, message: str) -> bool:
        """Show a yes/no dialog in the main thread and wait for response."""
        # Get the current event loop (running on BLE backend thread)
        loop = asyncio.get_event_loop()
        
        # Create a future on the correct loop
        future: asyncio.Future[bool] = loop.create_future()

        def _show_dialog():
            """Runs in Tkinter main thread."""
            try:
                result = messagebox.askyesno(title, message, parent=self.gui)
                # Set result using thread-safe call to asyncio loop
                loop.call_soon_threadsafe(future.set_result, result if result else False)
            except Exception as exc:
                loop.call_soon_threadsafe(future.set_exception, exc)

        # Schedule dialog in Tkinter main thread
        self.gui.after(0, _show_dialog)
        return await future

    async def _show_passkey_dialog(self) -> Optional[int]:
        """Show a passkey entry dialog in the main thread and wait for response."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[Optional[int]] = loop.create_future()

        def _show_dialog():
            """Runs in Tkinter main thread."""
            try:
                result = simpledialog.askinteger(
                    "Enter Passkey",
                    "Enter 6-digit passkey:\n(0-999999)",
                    minvalue=0,
                    maxvalue=999999,
                    parent=self.gui
                )
                loop.call_soon_threadsafe(future.set_result, result)
            except Exception as exc:
                loop.call_soon_threadsafe(future.set_exception, exc)

        # Schedule dialog in Tkinter main thread
        self.gui.after(0, _show_dialog)
        return await future

    async def _show_passkey_display(self, code: str) -> None:
        """Show passkey display message in the main thread and wait for close."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[None] = loop.create_future()

        def _show_dialog():
            """Runs in Tkinter main thread."""
            try:
                messagebox.showinfo(
                    "Passkey to Enter",
                    f"Enter this passkey on peer device:\n\n{code}",
                    parent=self.gui
                )
                loop.call_soon_threadsafe(future.set_result, None)
            except Exception as exc:
                loop.call_soon_threadsafe(future.set_exception, exc)

        # Schedule dialog in Tkinter main thread
        self.gui.after(0, _show_dialog)
        await future

    def get_delegate(self):
        """Return the Bumble pairing delegate instance."""
        return self.delegate_impl

