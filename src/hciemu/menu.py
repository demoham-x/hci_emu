#!/usr/bin/env python3
"""
Interactive menu wrapper that uses BLETestingApp APIs.

This keeps main.py untouched while providing a menu-driven interface
that delegates all BLE operations to src/app.py.
"""

import asyncio
import logging

from hciemu.app import BLETestingApp
from hciemu.utils import print_section, format_address

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
        return int(raw, 0) if raw else default

    def _prompt_float(self, prompt: str, default: float) -> float:
        """Prompt float with default fallback."""
        raw = input(prompt).strip()
        return float(raw) if raw else default

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
            ("", "--- Connection / Link (1-20) ---"),
            ("1", "Scan for BLE Devices"),
            ("2", "Connect to Device"),
            ("3", "Disconnect"),
            ("", "--- ATT / GATT (21-40) ---"),
            ("21", "Discover GATT Services"),
            ("22", "Read Characteristic"),
            ("23", "Write Characteristic"),
            ("24", "Write Without Response"),
            ("25", "Subscribe to Notifications"),
            ("26", "Subscribe to Indications"),
            ("27", "Burst Write (With Response)"),
            ("28", "Burst Write (Without Response)"),
            ("29", "Stop Burst Write"),
            ("30", "Burst Read"),
            ("31", "Stop Burst Read"),
            ("32", "Start CSV Logging"),
            ("33", "Stop CSV Logging"),
            ("34", "Exchange GATT MTU"),
            ("35", "Apple Services (ANCS / AMS)"),
            ("", "--- SMP (41-50) ---"),
            ("41", "Pair / Encrypt Connection"),
            ("42", "Send SMP Security Request"),
            ("43", "SMP Settings"),
            ("44", "Unpair / Delete Bonding"),
            ("", "--- Advertising (51-60) ---"),
            ("51", "Advertising Menu"),
            ("", "--- L2CAP (61-80) ---"),
            ("61", "L2CAP Operations (CBFC/ECBFC)"),
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

    async def menu_exchange_mtu(self):
        print_section("Exchange GATT MTU")
        mtu_size = self._prompt_int("Requested ATT MTU (23-517, default 247): ", default=247)
        await self.app.app_exchange_mtu(mtu_size=mtu_size)

    async def menu_apple_services(self):
        while True:
            print_section("Apple Services")
            print("  1. Initialize / Refresh Apple Services")
            print("  2. Show Apple Service Status")
            print("  3. Subscribe ANCS")
            print("  4. Request ANCS Notification Attributes")
            print("  5. Request ANCS App Attributes")
            print("  6. Perform ANCS Action")
            print("  7. Subscribe AMS")
            print("  8. Register AMS Entity Updates")
            print("  9. Read AMS Entity Attribute")
            print("  10. Send AMS Remote Command")
            print("  0. Back to Main Menu\n")

            choice = await self._prompt_text_async("Select option: ")
            if choice == "0":
                print()
                return

            if choice == "1":
                await self.app.app_apple_initialize()
            elif choice == "2":
                await self.app.app_apple_initialize(discover_if_needed=False)
            elif choice == "3":
                auto_fetch = self._prompt_yes_no(
                    "Auto request ANCS notification attributes when events arrive? (Y/n): ",
                    default=True,
                )
                auto_fetch_app = self._prompt_yes_no(
                    "Auto request ANCS app display name after notification attributes? (Y/n): ",
                    default=True,
                )
                await self.app.app_apple_subscribe_ancs(
                    auto_fetch_details=auto_fetch,
                    auto_fetch_app_attributes=auto_fetch_app,
                )
            elif choice == "4":
                notification_uid = input("Notification UID (decimal or hex, e.g. 0x12345678): ").strip()
                await self.app.app_apple_request_ancs_notification_attributes(notification_uid)
            elif choice == "5":
                app_identifier = input("App Identifier (for example com.apple.mobilephone): ").strip()
                if not app_identifier:
                    print("App identifier is required\n")
                    continue
                await self.app.app_apple_request_ancs_app_attributes(app_identifier)
            elif choice == "6":
                notification_uid = input("Notification UID (decimal or hex): ").strip()
                action = input("Action (positive/negative): ").strip()
                await self.app.app_apple_perform_ancs_action(notification_uid, action)
            elif choice == "7":
                register_defaults = self._prompt_yes_no(
                    "Register default AMS player/queue/track updates after subscribe? (Y/n): ",
                    default=True,
                )
                auto_read_truncated = self._prompt_yes_no(
                    "Auto read full AMS values when notifications are truncated? (Y/n): ",
                    default=True,
                )
                await self.app.app_apple_subscribe_ams(
                    register_defaults=register_defaults,
                    auto_read_truncated=auto_read_truncated,
                )
            elif choice == "8":
                entity = input("Entity (player, queue, track): ").strip()
                attributes_raw = input(
                    "Attributes (comma-separated, e.g. name,playback_info or title,artist): "
                ).strip()
                attributes = [part.strip() for part in attributes_raw.split(",") if part.strip()]
                if not attributes:
                    print("At least one AMS attribute is required\n")
                    continue
                await self.app.app_apple_register_ams_updates(entity, attributes)
            elif choice == "9":
                entity = input("Entity (player, queue, track): ").strip()
                attribute = input("Attribute: ").strip()
                await self.app.app_apple_read_ams_attribute(entity, attribute)
            elif choice == "10":
                command = input(
                    "AMS command (play, pause, toggle_play_pause, next_track, previous_track, volume_up, volume_down, skip_forward, skip_backward): "
                ).strip()
                await self.app.app_apple_send_ams_command(command)
            else:
                print("Invalid option\n")

    async def menu_l2cap_operations(self):
        while True:
            print_section("L2CAP Operations")
            print("  1. Start CBFC server (listen)")
            print("  2. Stop CBFC server")
            print("  3. Create CBFC channel")
            print("  4. Create ECBFC channel set")
            print("  5. View open channels")
            print("  6. View active L2CAP servers")
            print("  7. Send data on channel")
            print("  8. Send credits on channel")
            print("  9. Disconnect channel")
            print("  10. Reconfigure ECBFC (MTU/MPS)")
            print("  0. Back to Main Menu\n")

            choice = await self._prompt_text_async("Select option: ")
            if choice == "0":
                print()
                return

            if choice == "1":
                await self.menu_l2cap_start_server()
            elif choice == "2":
                await self.menu_l2cap_stop_server()
            elif choice == "3":
                await self.menu_l2cap_create_cbfc()
            elif choice == "4":
                await self.menu_l2cap_create_ecbfc()
            elif choice == "5":
                await self.app.app_l2cap_list_channels()
            elif choice == "6":
                await self.app.app_l2cap_list_servers()
            elif choice == "7":
                await self.menu_l2cap_send_data()
            elif choice == "8":
                await self.menu_l2cap_send_credits()
            elif choice == "9":
                await self.menu_l2cap_disconnect_channel()
            elif choice == "10":
                await self.menu_l2cap_reconfigure_ecbfc()
            else:
                print("Invalid option\n")

    async def menu_l2cap_start_server(self):
        print_section("Start L2CAP CBFC Server")
        psm = self._prompt_int("LE PSM (hex like 0x0080 or decimal): ", default=0x0080)
        mtu = self._prompt_int("Local MTU (default 2048): ", default=2048)
        mps = self._prompt_int("Local MPS (default 2048): ", default=2048)
        max_credits = self._prompt_int("Initial max credits (default 256): ", default=256)
        await self.app.app_l2cap_start_cbfc_server(
            psm=psm,
            mtu=mtu,
            mps=mps,
            max_credits=max_credits,
        )

    async def menu_l2cap_stop_server(self):
        print_section("Stop L2CAP CBFC Server")
        psm = self._prompt_int("LE PSM to stop (hex like 0x0080 or decimal): ", default=0x0080)
        await self.app.app_l2cap_stop_cbfc_server(psm=psm)

    async def menu_l2cap_create_cbfc(self):
        print_section("Create L2CAP CBFC")
        psm = self._prompt_int("LE PSM (hex like 0x0080 or decimal): ", default=0x0080)
        mtu = self._prompt_int("Local MTU (default 2048): ", default=2048)
        mps = self._prompt_int("Local MPS (default 2048): ", default=2048)
        max_credits = self._prompt_int("Initial max credits (default 256): ", default=256)
        await self.app.app_l2cap_create_cbfc(psm=psm, mtu=mtu, mps=mps, max_credits=max_credits)

    async def menu_l2cap_create_ecbfc(self):
        print_section("Create L2CAP ECBFC")
        psm = self._prompt_int("SPSM/LE PSM (hex like 0x0080 or decimal): ", default=0x0080)
        count = self._prompt_int("Channel count (default 2): ", default=2)
        mtu = self._prompt_int("Local MTU (default 2048): ", default=2048)
        mps = self._prompt_int("Local MPS (default 2048): ", default=2048)
        max_credits = self._prompt_int("Initial max credits (default 256): ", default=256)
        await self.app.app_l2cap_create_ecbfc(
            psm=psm,
            count=count,
            mtu=mtu,
            mps=mps,
            max_credits=max_credits,
        )

    def _print_l2cap_channels_inline(self):
        """Print open L2CAP channels as a compact table, used before CID prompts."""
        channels = self.app.connector.get_open_l2cap_channels()
        if not channels:
            print("  (no open L2CAP channels)")
        else:
            print("  Open channels:")
            for ch in channels:
                print(
                    f"    CID={ch['source_cid']}  PSM={ch['psm']}  "
                    f"MTU={ch['mtu']}/{ch['peer_mtu']}  "
                    f"credits(ours/peer)={ch['credits_ours']}/{ch['credits_peer']}  "
                    f"state={ch['state']}"
                )
        print()

    async def menu_l2cap_disconnect_channel(self):
        print_section("Disconnect L2CAP Channel")
        self._print_l2cap_channels_inline()
        source_cid = self._prompt_int("Source CID to disconnect (decimal): ", default=64)
        await self.app.app_l2cap_disconnect_channel(source_cid=source_cid)

    async def menu_l2cap_send_credits(self):
        print_section("Send L2CAP Credits")
        self._print_l2cap_channels_inline()
        source_cid = self._prompt_int("Source CID (decimal): ", default=64)
        credits = self._prompt_int("Credits to send (default 1): ", default=1)
        await self.app.app_l2cap_send_credits(source_cid=source_cid, credits=credits)

    async def menu_l2cap_send_data(self):
        print_section("Send L2CAP Data")
        self._print_l2cap_channels_inline()
        source_cid = self._prompt_int("Source CID (decimal): ", default=64)
        hex_data = input("Payload (hex, space-separated or continuous): ").strip()
        wait_drain = self._prompt_yes_no("Wait for channel drain? (Y/n): ", default=True)
        await self.app.app_l2cap_send_data(
            source_cid=source_cid,
            hex_data=hex_data,
            wait_drain=wait_drain,
        )

    async def menu_l2cap_reconfigure_ecbfc(self):
        print_section("Reconfigure L2CAP ECBFC")
        self._print_l2cap_channels_inline()
        source_cids_raw = input("Source CIDs (comma-separated, e.g. 64,65): ").strip()
        if not source_cids_raw:
            print("No source CIDs provided\n")
            return

        try:
            source_cids = [int(part.strip()) for part in source_cids_raw.split(",") if part.strip()]
        except ValueError:
            print("Invalid CID list\n")
            return

        mtu = self._prompt_int("New MTU: ", default=2048)
        mps = self._prompt_int("New MPS: ", default=2048)
        await self.app.app_l2cap_reconfigure_ecbfc(source_cids=source_cids, mtu=mtu, mps=mps)

    async def menu_set_advertising_parameters(self):
        print_section("Set Advertising Parameters")
        interval_min_ms = self._prompt_float(
            f"Min interval ms (default {self.app.adv_interval_min_ms}): ",
            default=self.app.adv_interval_min_ms,
        )
        interval_max_ms = self._prompt_float(
            f"Max interval ms (default {self.app.adv_interval_max_ms}): ",
            default=self.app.adv_interval_max_ms,
        )
        connectable = self._prompt_yes_no(
            f"Connectable advertising? (Y/n, current {'Y' if self.app.adv_connectable else 'N'}): ",
            default=self.app.adv_connectable,
        )
        await self.app.app_set_advertising_parameters(
            interval_min_ms=interval_min_ms,
            interval_max_ms=interval_max_ms,
            connectable=connectable,
        )

    async def menu_set_advertising_data(self):
        print_section("Set Advertising Data")
        adv_data_hex = (
            input(f"Advertising data hex (default {self.app.adv_data_hex}): ").strip()
            or self.app.adv_data_hex
        )
        scan_rsp_hex = input(
            "Scan response hex (optional, leave empty for none): "
        ).strip()
        await self.app.app_set_advertising_data(
            adv_data_hex=adv_data_hex,
            scan_response_hex=scan_rsp_hex,
        )

    async def menu_set_advertising_name(self):
        print_section("Set Advertising Device Name")
        enabled = self._prompt_yes_no(
            f"Enable local name in advertising data? (Y/n, current {'Y' if self.app.adv_name_enabled else 'N'}): ",
            default=self.app.adv_name_enabled,
        )

        if not enabled:
            await self.app.app_set_advertising_name(enabled=False)
            return

        current_name = self.app.adv_custom_name or "hciemu_<bd-address>"
        custom_name = input(
            f"Custom local name (leave empty for default, current {current_name}): "
        ).strip()
        await self.app.app_set_advertising_name(
            enabled=True,
            name=custom_name or None,
        )

    async def menu_advertising(self):
        while True:
            print_section("Advertising Menu")
            print(
                "Current: "
                f"{'ON' if self.app.advertising else 'OFF'}, "
                f"interval {self.app.adv_interval_min_ms:.2f}-{self.app.adv_interval_max_ms:.2f} ms, "
                f"connectable={'YES' if self.app.adv_connectable else 'NO'}"
            )
            print(f"Adv Data: {self.app.adv_data_hex or '(empty)'}")
            print(
                "Scan Response: "
                f"{self.app.adv_scan_response_hex if self.app.adv_scan_response_hex else '(empty)'}"
            )
            name_status = "ON" if self.app.adv_name_enabled else "OFF"
            name_value = self.app.adv_custom_name or "hciemu_<bd-address>"
            print(f"Local Name: {name_status} ({name_value})")
            print()
            print("  1. Set Advertising Parameters")
            print("  2. Set Advertising Data")
            print("  3. Set Advertising Device Name")
            print("  4. Start Advertising")
            print("  5. Stop Advertising")
            print("  0. Back to Main Menu\n")

            choice = await self._prompt_text_async("Select option: ")
            if choice == "0":
                print()
                return
            if choice == "1":
                await self.menu_set_advertising_parameters()
            elif choice == "2":
                await self.menu_set_advertising_data()
            elif choice == "3":
                await self.menu_set_advertising_name()
            elif choice == "4":
                await self.app.app_start_advertising()
            elif choice == "5":
                await self.app.app_stop_advertising()
            else:
                print("Invalid option\n")

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
            print("  8. Auto Restore CCCD on Reconnect: "
                f"{'ENABLED' if self.app.auto_restore_cccd_on_reconnect else 'DISABLED'}")
            print("  0. Back to Main Menu\n")

            choice = await self._prompt_text_async("Select option: ")
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
            elif choice == "8":
                enabled = self._prompt_yes_no("Enable auto restore CCCD on reconnect? (Y/n): ", default=True)
                await self.app.app_auto_restore_cccd_on_reconnect(enabled)
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
                elif choice == "1":
                    await self.menu_scan_devices()
                elif choice == "2":
                    await self.menu_connect_device()
                elif choice == "3":
                    await self.app.app_disconnect()
                elif choice == "21":
                    await self.app.app_discover_services()
                elif choice == "22":
                    await self.menu_read_characteristic()
                elif choice == "23":
                    await self.menu_write_characteristic()
                elif choice == "24":
                    await self.menu_write_without_response()
                elif choice == "25":
                    await self.menu_subscribe()
                elif choice == "26":
                    await self.menu_subscribe_indications()
                elif choice == "27":
                    await self.menu_burst_write()
                elif choice == "28":
                    await self.menu_burst_write_without_response()
                elif choice == "29":
                    await self.app.app_stop_burst_write()
                elif choice == "30":
                    await self.menu_burst_read()
                elif choice == "31":
                    await self.app.app_stop_burst_read()
                elif choice == "32":
                    await self.menu_start_csv_logging()
                elif choice == "33":
                    await self.app.app_stop_csv_logging()
                elif choice == "34":
                    await self.menu_exchange_mtu()
                elif choice == "35":
                    await self.menu_apple_services()
                elif choice == "41":
                    await self.app.app_pair()
                elif choice == "42":
                    await self.app.app_send_security_request()
                elif choice == "43" or choice.lower() == "s":
                    await self.menu_smp_settings()
                elif choice == "44":
                    await self.menu_unpair()
                elif choice == "51":
                    await self.menu_advertising()
                elif choice == "61":
                    await self.menu_l2cap_operations()
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
