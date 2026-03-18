#!/usr/bin/env python3
"""
Bumble BLE Testing Framework - Entry point.

Parses CLI arguments and launches the interactive menu (menu.py),
which delegates all BLE operations to the app layer (app.py).

Usage:
    python src/main.py [--transport <spec>] [-v]
    python src/main.py --transport tcp-client:127.0.0.1:9001
"""

import asyncio
import argparse
import logging
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(__file__))

from menu import BLETestingMenu


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bumble BLE Testing Framework")
    parser.add_argument(
        "--transport",
        default="tcp-client:127.0.0.1:9001",
        help="HCI transport specification (default: tcp-client:127.0.0.1:9001)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    menu = BLETestingMenu(args.transport)
    await menu.run()


def run_cli() -> None:
    """Synchronous CLI entrypoint for console_scripts."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExit")
    except asyncio.CancelledError:
        print("\n\nOperation cancelled")


def run_bridge_cli() -> None:
    """Synchronous bridge entrypoint for console_scripts."""
    parser = argparse.ArgumentParser(description="Run Bumble HCI bridge")
    parser.add_argument(
        "source",
        nargs="?",
        default="usb:0",
        help="Bridge source transport (default: usb:0)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="tcp-server:127.0.0.1:9001",
        help="Bridge target transport (default: tcp-server:127.0.0.1:9001)",
    )
    args = parser.parse_args()

    command = ["bumble-hci-bridge", args.source, args.target]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    run_cli()
