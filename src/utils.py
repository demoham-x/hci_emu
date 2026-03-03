#!/usr/bin/env python3
"""
Utility functions for Bumble BLE testing
"""

import asyncio
from typing import Optional, Callable, Any
import logging

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich import box
    _HAS_RICH = True
    _CONSOLE = Console()
except ImportError:
    _HAS_RICH = False
    _CONSOLE = None

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run an async coroutine and return the result"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return loop.run_in_executor(pool, asyncio.run, coro)
        else:
            return asyncio.run(coro)
    except RuntimeError:
        return asyncio.run(coro)


def format_address(addr: str) -> str:
    """Format BLE address to uppercase with colons"""
    addr = addr.replace('-', ':').upper()
    return addr


def parse_hex(hex_str: str) -> bytes:
    """Parse hex string to bytes"""
    try:
        # Remove spaces and convert
        hex_str = hex_str.replace(' ', '').replace('0x', '').replace('0X', '')
        return bytes.fromhex(hex_str)
    except ValueError as e:
        logger.error(f"Invalid hex string: {hex_str}")
        raise


def format_uuid(uuid_val: Any) -> str:
    """Format UUID for display"""
    if isinstance(uuid_val, str):
        return uuid_val
    return str(uuid_val)


def print_section(title: str):
    """Print a formatted section header"""
    if _HAS_RICH and _CONSOLE is not None:
        _CONSOLE.print(Panel(f"{title}", box=box.ASCII, expand=False))
        print()
        return
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_device_info(device_info: dict):
    """Pretty print device information"""
    for key, value in device_info.items():
        print(f"  {key:.<40} {value}")


def apply_legacy_le_mode(device) -> None:
    """Force Bumble to use legacy (non-extended) LE procedures.

    After ``device.power_on()`` the host has queried the controller for its
    supported commands and LE features.  This helper clears the two bits that
    Bumble inspects before choosing between extended and legacy HCI commands:

    * ``LeFeatureMask.LE_EXTENDED_ADVERTISING`` – guards ``start_scanning``
      (when *legacy* kwarg is omitted) and ``start_advertising``.
    * The supported-commands mask for ``HCI_LE_Extended_Create_Connection``
      (0x2043) – guards ``connect_le``.

    Clearing these bits causes Bumble to issue the legacy opcodes
    0x200B / 0x200C (scan), 0x2006 / 0x2008 / 0x2009 / 0x200A (advertising)
    and 0x200D (create connection) instead of the extended equivalents.
    """
    try:
        from bumble import hci as _hci

        # Strip LE_EXTENDED_ADVERTISING feature bit so that start_scanning and
        # start_advertising fall back to legacy commands.
        device.host.local_le_features &= ~int(
            _hci.LeFeatureMask.LE_EXTENDED_ADVERTISING
        )

        # Strip the LE Extended Create Connection command support bit so that
        # connect_le uses HCI_LE_Create_Connection instead of the extended form.
        ext_conn_mask = _hci.HCI_SUPPORTED_COMMANDS_MASKS.get(
            _hci.HCI_LE_EXTENDED_CREATE_CONNECTION_COMMAND, 0
        )
        device.host.local_supported_commands &= ~ext_conn_mask

        logger.info(
            "Legacy LE mode active: extended scan/adv/connect commands disabled"
        )
    except Exception as exc:
        logger.warning(f"Could not apply legacy LE mode: {exc}")
