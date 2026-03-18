#!/usr/bin/env python3
"""
Interactive menu wrapper that uses BLETestingApp APIs.

This keeps main.py untouched while providing a menu-driven interface
that delegates all BLE operations to src/app.py.
"""

import asyncio
import logging

from app import BLETestingApp
from utils import print_section, format_address

try:
    from rich.console import Console
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None
    Table = None


logger = logging.getLogger(__name__)


class BLETestingMenu:
    """Interactive menu that delegates operations to BLETestingApp."""

    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001"):
        self.app = BLETestingApp(transport_spec)
        self.console = Console() if HAS_RICH else None

    def _prompt_yes_no(self, prompt: str, default: bool = False) -> bool:
        """Prompt yes/no with default support."""
        raw = input(prompt).strip().lower()
        if not raw:
            return default
        return raw == "y"

    def _prompt_int(self, prompt: str, default: int) -> int:
        """Prompt integer with default fallback."""
        raw = input(prompt).strip()
        return int(raw) if raw else default

    async def _prompt_text_async(self, prompt: str) -> str:
        """Prompt text without blocking the asyncio event loop."""
        return (await asyncio.to_thread(input, prompt)).strip()

    def print_main_menu(self):
        print_section("BUMBLE BLE Testing - Main Menu")
        entries = [
            ("A", "Bluetooth On"),
            ("B", "Bluetooth Off"),
            ("C", "Set Device Filters"),
            ("D", "HCI Snoop Logging (ON)" if self.app.snoop_enabled else "HCI Snoop Logging (OFF)"),
            ("E", f"Debug Logging ({self.app.debug_mode.upper()})"),
            ("S", "SMP Settings"),
            ("1", "Scan for BLE Devices"),
            ("2", "Connect to Device"),
            ("3", "Discover GATT Services"),
            ("4", "Read Characteristic"),
            ("5", "Write Characteristic"),
            ("6", "Write Without Response"),
            ("7", "Subscribe to Notifications"),
            ("8", "Subscribe to Indications"),
            ("9", "Pair / Encrypt Connection"),
            ("10", "Unpair / Delete Bonding"),
            ("11", "Disconnect"),
            ("12", "Burst Write (With Response)"),
            ("13", "Burst Write (Without Response)"),
            ("14", "Stop Burst Write"),
            ("15", "Burst Read"),
            ("16", "Stop Burst Read"),
            ("17", "Start CSV Logging"),
            ("18", "Stop CSV Logging"),
            ("0", "Exit"),
        ]

        if HAS_RICH and self.console:
            table = Table(show_header=False)
            table.add_column("Option", style="cyan", width=4)
            table.add_column("Action", style="white")
            for key, label in entries:
                table.add_row(key, label)
            self.console.print(table)
        else:
            for key, label in entries:
                print(f"{key}. {label}")

        if self.app.filter_name or self.app.filter_address:
            print()
            filter_info = []
            if self.app.filter_name:
                filter_info.append(f"Name: '{self.app.filter_name}'")
            if self.app.filter_address:
                filter_info.append(f"Address: '{self.app.filter_address}'")
            print(f"[Filters Active: {', '.join(filter_info)}]")
        print()

    async def menu_set_filters(self):
        print_section("Device Filters")
        print("Current filters:")
        if self.app.filter_name or self.app.filter_address:
            if self.app.filter_name:
                print(f"  Name filter: '{self.app.filter_name}'")
            if self.app.filter_address:
                print(f"  Address filter: '{self.app.filter_address}'")
        else:
            print("  No filters set (all devices shown)")
        print()

        clear = self._prompt_yes_no("Clear all filters? (y/n, default n): ", default=False)
        if clear:
            await self.app.app_set_filters(clear=True)
            return

        print("\nEnter filter criteria (leave empty to skip):")
        name_input = input("Device name (partial, case-insensitive): ").strip() or None
        addr_input = input("Device address (partial, e.g., '1E:59:DD'): ").strip() or None
        await self.app.app_set_filters(name_filter=name_input, address_filter=addr_input)

    async def menu_toggle_hci_snoop(self):
        print_section("HCI Snoop Logging")

        if self.app.snoop_enabled:
            print("HCI Snoop Logging is currently: ON\n")
            disable = self._prompt_yes_no("Disable HCI snoop logging? (y/n): ", default=False)
            if disable:
                await self.app.app_toggle_hci_snoop(enable=False)
            return

        print("HCI Snoop Logging is currently: OFF\n")
        ellisys_host = input(f"Ellisys host (default {self.app.ellisys_host}): ").strip() or None

        port_input = input(f"Ellisys port (default {self.app.ellisys_port}): ").strip()
        ellisys_port = int(port_input) if port_input else None

        print("\nEllisys Data Stream:")
        print("  1. Primary")
        print("  2. Secondary")
        print("  3. Tertiary")
        stream_input = input(f"Select stream (1-3, default {self.app.ellisys_stream.upper()}): ").strip()
        stream_map = {"1": "primary", "2": "secondary", "3": "tertiary"}
        ellisys_stream = stream_map.get(stream_input)

        btsnoop_filename = input(f"Capture file (default {self.app.btsnoop_filename}): ").strip() or None

        default_ellisys = "y" if self.app.snoop_ellisys_enabled else "n"
        enable_ellisys_input = input(f"Enable Ellisys UDP output? (y/n, default {default_ellisys}): ").strip().lower()
        enable_ellisys = None if not enable_ellisys_input else enable_ellisys_input == "y"

        default_file = "y" if self.app.snoop_file_enabled else "n"
        enable_file_input = input(f"Enable capture file storage? (y/n, default {default_file}): ").strip().lower()
        enable_file = None if not enable_file_input else enable_file_input == "y"

        default_console = "y" if self.app.snoop_console_logging else "n"
        enable_console_input = input(f"Enable console packet logging? (y/n, default {default_console}): ").strip().lower()
        enable_console = None if not enable_console_input else enable_console_input == "y"

        enable = self._prompt_yes_no("\nEnable HCI snoop logging with these settings? (y/n): ", default=False)
        if not enable:
            print("\nHCI snoop logging not enabled\n")
            return

        await self.app.app_toggle_hci_snoop(
            enable=True,
            ellisys_host=ellisys_host,
            ellisys_port=ellisys_port,
            ellisys_stream=ellisys_stream,
            btsnoop_filename=btsnoop_filename,
            enable_ellisys=enable_ellisys,
            enable_file=enable_file,
            enable_console=enable_console,
        )

    async def menu_debug_logging(self):
        print_section("Debug Logging Configuration")
        print(f"Current debug logging mode: {self.app.debug_mode.upper()}\n")
        print("Debug logging modes:")
        print("  1. Console only")
        print("  2. File only")
        print("  3. Both")
        print("  4. None")
        print("  0. Cancel\n")

        choice = input("Select debug mode (0-4): ").strip()
        mode_map = {"1": "console", "2": "file", "3": "both", "4": "none"}
        if choice == "0":
            print()
            return
        mode = mode_map.get(choice)
        if not mode:
            print("\nInvalid choice\n")
            return
        await self.app.app_debug_logging(mode)

    async def menu_scan_devices(self):
        print_section("Scanning for BLE Devices")
        duration = self._prompt_int("Enter scan duration in seconds (default 10): ", default=10)

        filter_duplicates = self._prompt_yes_no("Filter duplicate advertisements? (Y/n): ", default=True)

        active_scan = self._prompt_yes_no("Active scan (request scan response)? (Y/n): ", default=True)

        await self.app.app_scan_devices(
            duration=duration,
            filter_duplicates=filter_duplicates,
            active_scan=active_scan,
        )

    async def menu_connect_device(self):
        print_section("Connect to BLE Device")
        self.app.print_scan_menu()

        if not self.app.discovered_devices:
            print("No devices available. Run scan first (option 1)\n")
            return

        choice = input("Enter device number from list (or address manually): ").strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(self.app.discovered_devices):
                address = list(self.app.discovered_devices.keys())[idx - 1]
            else:
                print(f"Invalid number. Enter 1-{len(self.app.discovered_devices)}\n")
                return
        except ValueError:
            address = choice

        address = format_address(address)
        await self.app.connect(address)

    def _ask_show_table(self) -> bool:
        return input("Show characteristics? (y/N): ").strip().lower() == "y"

    async def _show_characteristics_table_if_requested(self, operation: str) -> bool:
        """Ask once and show table before collecting operation inputs."""
        show_table = self._ask_show_table()
        if show_table:
            await self.app._show_characteristics_table(operation)
        return show_table

    async def menu_read_characteristic(self):
        await self._show_characteristics_table_if_requested("read")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        await self.app.app_read_characteristic(handle=handle, show_table=False)

    async def menu_write_characteristic(self):
        await self._show_characteristics_table_if_requested("write")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
        await self.app.app_write_characteristic(handle=handle, hex_value=hex_value, show_table=False)

    async def menu_write_without_response(self):
        await self._show_characteristics_table_if_requested("write_without_response")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        hex_value = input("Enter value (hex): ").strip()
        await self.app.app_write_without_response(handle=handle, hex_value=hex_value, show_table=False)

    async def menu_subscribe(self):
        await self._show_characteristics_table_if_requested("notify")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        await self.app.app_subscribe(handle=handle, show_table=False)

    async def menu_subscribe_indications(self):
        await self._show_characteristics_table_if_requested("indicate")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        await self.app.app_subscribe_indications(handle=handle, show_table=False)

    async def menu_burst_write(self):
        await self._show_characteristics_table_if_requested("burst_write")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
        count = self._prompt_int("Count (0 = infinite, default 0): ", default=0)
        interval_ms = self._prompt_int("Interval ms (default 100): ", default=100)
        await self.app.app_burst_write(
            handle=handle,
            hex_value=hex_value,
            count=count,
            interval_ms=interval_ms,
            show_table=False,
        )

    async def menu_burst_write_without_response(self):
        await self._show_characteristics_table_if_requested("burst_write")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
        count = self._prompt_int("Count (0 = infinite, default 0): ", default=0)
        interval_ms = self._prompt_int("Interval ms (default 100): ", default=100)
        await self.app.app_burst_write_without_response(
            handle=handle,
            hex_value=hex_value,
            count=count,
            interval_ms=interval_ms,
            show_table=False,
        )

    async def menu_burst_read(self):
        await self._show_characteristics_table_if_requested("burst_read")
        handle = input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
        count = self._prompt_int("Count (0 = infinite, default 0): ", default=0)
        interval_ms = self._prompt_int("Interval ms (default 100): ", default=100)
        print_each_read = self._prompt_yes_no("Print each read to console? (y/N): ", default=False)

        await self.app.app_burst_read(
            handle=handle,
            count=count,
            interval_ms=interval_ms,
            print_each_read=print_each_read,
            show_table=False,
        )

    async def menu_start_csv_logging(self):
        filename = input("CSV filename (default: notifications_TIMESTAMP.csv): ").strip() or None
        await self.app.app_start_csv_logging(filename=filename)

    async def menu_smp_settings(self):
        while True:
            print_section("SMP (Secure Manager Protocol) Settings")
            config = self.app.connector.get_smp_config()
            print("Current Configuration:")
            print(f"  1. IO Capability: {config['io_capability']}")
            print(f"  2. MITM Required: {'YES' if config['mitm_required'] else 'NO'}")
            print(f"  3. LE Secure Connections: {'ENABLED' if config['le_secure_connections'] else 'DISABLED'}")
            print(f"  4. Encryption Key Size: {config['min_enc_key_size']}-{config['max_enc_key_size']} bytes")
            print(f"  5. Bonding: {'ENABLED' if config['bonding_enabled'] else 'DISABLED'}")
            print("  6. Auto Pair/Encrypt on Security Request: "
                  f"{'ENABLED' if config.get('auto_pair_encrypt_on_security_request', True) else 'DISABLED'}")
            print("  7. Auto Encrypt If Bonded: "
                f"{'ENABLED' if config.get('auto_encrypt_if_bonded', True) else 'DISABLED'}")
            print("  0. Back to Main Menu\n")

            choice = input("Select option: ").strip()
            if choice == "0":
                break
            if choice == "1":
                io_choice = input(
                    "IO Capability (DISPLAY_ONLY, KEYBOARD_ONLY, NO_INPUT_NO_OUTPUT, KEYBOARD_DISPLAY, DISPLAY_OUTPUT_AND_KEYBOARD_INPUT): "
                ).strip()
                await self.app.app_smp_io_capability(io_choice)
            elif choice == "2":
                required = self._prompt_yes_no("MITM required? (y/N): ", default=False)
                await self.app.app_smp_mitm_required(required)
            elif choice == "3":
                enabled = self._prompt_yes_no("Enable LE Secure Connections? (Y/n): ", default=True)
                await self.app.app_smp_secure_connections(enabled)
            elif choice == "4":
                min_size = self._prompt_int("Min key size (7-16, default 7): ", default=7)
                max_size = self._prompt_int("Max key size (7-16, default 16): ", default=16)
                await self.app.app_smp_encryption_key_size(min_size=min_size, max_size=max_size)
            elif choice == "5":
                enabled = self._prompt_yes_no("Enable bonding? (Y/n): ", default=True)
                await self.app.app_smp_bonding(enabled)
            elif choice == "6":
                enabled = self._prompt_yes_no("Enable auto pair/encrypt on security request? (Y/n): ", default=True)
                await self.app.app_smp_auto_pair_encrypt(enabled)
            elif choice == "7":
                enabled = self._prompt_yes_no("Enable auto encrypt if bonded? (Y/n): ", default=True)
                await self.app.app_smp_auto_encrypt_if_bonded(enabled)
            else:
                print("Invalid option\n")

    async def menu_unpair(self):
        bonded = self.app.connector.get_bonded_devices()
        if not bonded:
            print("No bonded devices found.\n")
            return

        print_section("Bonded Devices")
        addresses = self.app.print_bonded_devices(bonded, title="Bonded Devices")
        if not addresses:
            return

        choice = input("Enter bonded device index to unpair (or Enter to cancel): ").strip()
        if not choice:
            print("Cancelled\n")
            return
        try:
            idx = int(choice)
        except ValueError:
            print("Invalid input\n")
            return
        if idx < 1 or idx > len(addresses):
            print(f"Invalid number. Enter 1-{len(addresses)}\n")
            return
        await self.app.app_unpair(index=idx, show_bonded_devices=False)

    async def run(self):
        print_section("BUMBLE BLE TESTING FRAMEWORK")
        print(f"Transport: {self.app.transport_spec}\n")

        # Respect persisted UI setting: auto-enable snoop before first menu render.
        await self.app._auto_enable_hci_snoop_on_startup()

        while True:
            self.print_main_menu()
            choice = await self._prompt_text_async("Select option: ")

            try:
                if choice.lower() == "a":
                    await self.app.app_bluetooth_on()
                elif choice.lower() == "b":
                    await self.app.app_bluetooth_off()
                elif choice.lower() == "c":
                    await self.menu_set_filters()
                elif choice.lower() == "d":
                    await self.menu_toggle_hci_snoop()
                elif choice.lower() == "e":
                    await self.menu_debug_logging()
                elif choice.lower() == "s":
                    await self.menu_smp_settings()
                elif choice == "1":
                    await self.menu_scan_devices()
                elif choice == "2":
                    await self.menu_connect_device()
                elif choice == "3":
                    await self.app.app_discover_services()
                elif choice == "4":
                    await self.menu_read_characteristic()
                elif choice == "5":
                    await self.menu_write_characteristic()
                elif choice == "6":
                    await self.menu_write_without_response()
                elif choice == "7":
                    await self.menu_subscribe()
                elif choice == "8":
                    await self.menu_subscribe_indications()
                elif choice == "9":
                    await self.app.app_pair()
                elif choice == "10":
                    await self.menu_unpair()
                elif choice == "11":
                    await self.app.app_disconnect()
                elif choice == "12":
                    await self.menu_burst_write()
                elif choice == "13":
                    await self.menu_burst_write_without_response()
                elif choice == "14":
                    await self.app.app_stop_burst_write()
                elif choice == "15":
                    await self.menu_burst_read()
                elif choice == "16":
                    await self.app.app_stop_burst_read()
                elif choice == "17":
                    await self.menu_start_csv_logging()
                elif choice == "18":
                    await self.app.app_stop_csv_logging()
                elif choice == "0":
                    print("\nExiting...")
                    break
                else:
                    print("Invalid option\n")
            except KeyboardInterrupt:
                print("\n\nCancelled")
            except Exception as exc:
                logger.error(f"Error: {exc}\n")

        await self.app.app_bluetooth_off()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bumble BLE Testing Menu (app.py-backed)")
    parser.add_argument(
        "--transport",
        default="tcp-client:127.0.0.1:9001",
        help="HCI transport specification",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
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
