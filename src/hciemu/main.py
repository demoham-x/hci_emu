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
import sys
import subprocess

from hciemu.menu import BLETestingMenu
# Import your diagnostic engine
from hciemu.ai_diagnostics import get_ai_fix 


def global_async_error_handler(loop, context):
    """
    Global interceptor for any unhandled exception that happens
    inside background tasks or async loops.
    """
    exception = context.get('exception')
    
    if exception:
        print("\n" + "!" * 60)
        print("[!] Background Async Crash Detected. Calling Cloud AI Engine...")
        print("!" * 60 + "\n")
        
        # Build immediate execution context for Gemini
        app_context = {
            "async_message": context.get('message'),
            "failed_future": str(context.get('future')),
            "failed_handle": str(context.get('handle'))
        }
        
        # Pull suggestions from Gemini
        ai_suggestion = get_ai_fix(exception, app_context)
        
        print("\n" + "=" * 60)
        print(ai_suggestion)
        print("=" * 60 + "\n")
    else:
        print(f"\n[!] Async loop issue: {context.get('message')}\n")


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

    # 1. Register the global exception hook right as the async app launches
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(global_async_error_handler)

    try:
        menu = BLETestingMenu(args.transport)
        await menu.run()
    except Exception as exc:
        # 2. Catches errors occurring explicitly on the main menu execution thread
        print("\n" + "!" * 60)
        print("[!] Menu Controller Crash Detected. Calling Cloud AI Engine...")
        print("!" * 60 + "\n")
        
        app_context = {"transport_used": args.transport, "layer": "Main Interactive Menu"}
        ai_suggestion = get_ai_fix(exc, app_context)
        
        print("\n" + "=" * 60)
        print(ai_suggestion)
        print("=" * 60 + "\n")
        raise exc


def run_cli() -> None:
    """Synchronous CLI entrypoint for console_scripts."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExit")
    except asyncio.CancelledError:
        print("\n\nOperation cancelled")
    except Exception as exc:
        # 3. Last line of defense if something goes wrong outside the async environment
        print(f"\n[!] Critical System Crash: {exc}")


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
    try:
        return_code = subprocess.call(command)
        raise SystemExit(return_code)
    except (FileNotFoundError, OSError) as exc:
        print(
            "Error: could not execute 'bumble-hci-bridge'. "
            "Make sure it is installed, on your PATH, and that any "
            "required virtual environment is activated.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run_cli()
