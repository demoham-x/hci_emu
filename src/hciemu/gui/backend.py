"""AsyncBLEBackend — runs BLETestingApp on a dedicated asyncio thread."""
from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional, TYPE_CHECKING

from hciemu.app import BLETestingApp

if TYPE_CHECKING:
    from hciemu.gui.pairing_delegate import GUIPairingDelegate


class AsyncBLEBackend:
    """Wraps BLETestingApp on a dedicated asyncio event-loop thread."""

    def __init__(self, transport_spec: str, gui_pairing_delegate: Optional["GUIPairingDelegate"] = None):
        self.transport_spec = transport_spec
        self.gui_pairing_delegate = gui_pairing_delegate
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self._ready = threading.Event()
        self.app: Optional[BLETestingApp] = None

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self._initialize())
        self.loop.run_forever()

    async def _initialize(self) -> None:
        self.app = BLETestingApp(self.transport_spec)
        # Apply GUI pairing delegate if provided
        if self.gui_pairing_delegate is not None:
            delegate = self.gui_pairing_delegate.get_delegate()
            try:
                io_name = self.app.connector.get_smp_config().get(
                    "io_capability", "DISPLAY_OUTPUT_AND_KEYBOARD_INPUT"
                )
                delegate.io_capability = self.app.connector._resolve_io_capability(io_name)
            except Exception:
                # Keep delegate default if IO capability mapping is unavailable.
                pass
            self.app.connector.set_pairing_delegate(delegate)
            gui = self.gui_pairing_delegate.gui

            def _status_to_gui(message: str) -> None:
                gui.after(0, lambda: gui.handle_status_message(message))

            def _connection_to_gui(peer_address: Optional[str]) -> None:
                gui.after(0, lambda: gui.update_connection_status(peer_address))

            def _adv_state_to_gui(running: bool) -> None:
                gui.after(0, lambda: gui.update_advertising_state(running))

            self.app.set_status_callback(_status_to_gui)
            self.app.set_connection_status_callback(_connection_to_gui)
            self.app.set_advertising_state_callback(_adv_state_to_gui)
        # Resolve snoop config and open HCI transport once so connect() never
        # needs to tear-down and reopen the device (avoids spurious HCI_RESET).
        await self.app._auto_enable_hci_snoop_on_startup()
        await self.app.app_bluetooth_on()
        self._ready.set()

    def start(self) -> None:
        self.thread.start()
        self._ready.wait(timeout=10)
        if self.app is None:
            raise RuntimeError("Failed to initialize BLE backend")

    def submit(self, coro_factory: Callable[[BLETestingApp], asyncio.Future]):
        if self.app is None:
            raise RuntimeError("BLE backend not initialized")
        return asyncio.run_coroutine_threadsafe(coro_factory(self.app), self.loop)

    def stop(self) -> None:
        if self.app is not None:
            try:
                future = self.submit(lambda app: app.app_bluetooth_off())
                future.result(timeout=5)
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)
