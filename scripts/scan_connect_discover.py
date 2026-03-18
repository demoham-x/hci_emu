#!/usr/bin/env python3
"""
Scan, connect, discover services, then disconnect.

Uses the filter settings from configs/ui_config.json (filter_name / filter_address).
The first device matching the active filter is used for connection.

Usage:
    python scripts/scan_connect_discover.py [--transport <spec>] [--scan-duration <sec>] [-v]
"""

import asyncio
import argparse
import logging
import os
import sys

# Locate src/ relative to this script so it works from any cwd.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "..", "src")
sys.path.insert(0, SRC_DIR)

from app import BLETestingApp


async def run(transport: str, scan_duration: int) -> None:
    app = BLETestingApp(transport)

    # 1. Enable HCI snoop first (if configured) so the transport is wrapped from
    #    the start – avoids a mid-flow device restart inside connect().
    await app._auto_enable_hci_snoop_on_startup()

    # 2. Bluetooth on
    await app.app_bluetooth_on()

    # 3. Scan (respects filter_name / filter_address loaded from ui_config.json)
    filter_info = []
    if app.filter_name:
        filter_info.append(f"name='{app.filter_name}'")
    if app.filter_address:
        filter_info.append(f"address='{app.filter_address}'")
    if filter_info:
        print(f"[SCRIPT] Active filters: {', '.join(filter_info)}")
    else:
        print("[SCRIPT] No filters active — scanning all devices")

    await app.app_scan_devices(duration=scan_duration, filter_duplicates=True, active_scan=True)

    if not app.discovered_devices:
        print("[SCRIPT] No devices found. Exiting.")
        await app.app_bluetooth_off()
        return

    # 4. Pick target: first discovered device (filters already applied during scan)
    target_address = next(iter(app.discovered_devices))
    target_name = app.discovered_devices[target_address].get("name") or "(unknown)"
    print(f"\n[SCRIPT] Target: {target_address}  Name: {target_name}")

    # 5. Connect
    await app.connect(target_address)

    if not app.connected:
        print("[SCRIPT] Connection failed. Exiting.")
        await app.app_bluetooth_off()
        return

    # 6. Discover GATT services
    await app.app_discover_services()

    # 7. Disconnect
    await app.app_disconnect()

    # 8. Bluetooth off
    await app.app_bluetooth_off()

    print("[SCRIPT] Done.")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scan → Connect → Discover → Disconnect")
    parser.add_argument(
        "--transport",
        default="tcp-client:127.0.0.1:9001",
        help="HCI transport specification (default: tcp-client:127.0.0.1:9001)",
    )
    parser.add_argument(
        "--scan-duration",
        type=int,
        default=10,
        metavar="SEC",
        help="Scan duration in seconds (default: 10)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    await run(args.transport, args.scan_duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nCancelled")
    except asyncio.CancelledError:
        print("\n\nOperation cancelled")
