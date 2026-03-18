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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExit")
    except asyncio.CancelledError:
        print("\n\nOperation cancelled")
