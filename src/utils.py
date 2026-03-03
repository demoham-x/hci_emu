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
