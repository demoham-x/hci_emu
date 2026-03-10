#!/usr/bin/env python3
"""
Bumble BLE Testing - Interactive Menu Interface
"""

import asyncio
import json
import logging
import sys
from typing import Optional
import os

try:
    from rich.table import Table
    from rich.console import Console
    from rich.panel import Panel
    from rich.logging import RichHandler
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Configure logging - start with DEBUG disabled (NONE mode by default)
if HAS_RICH:
    # Use Rich for beautiful console logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(message)s',
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=True)]
    )
else:
    # Fallback to standard logging
    logging.basicConfig(
        level=logging.WARNING,
        format='[%(asctime)s] %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

logger = logging.getLogger(__name__)

# Suppress HCI bridge (Bumble) logs by default - user sees them where bridge runs
logging.getLogger("bumble").setLevel(logging.WARNING)

if HAS_RICH:
    console = Console()
else:
    console = None

# Import local modules
sys.path.insert(0, os.path.dirname(__file__))
from scanner import BLEScanner
from connector import BLEConnector
from utils import print_section, format_address
from bumble.keys import JsonKeyStore
from hci_snooper import HCISnooper, BumbleHCITransportWrapper


class BLETestingMenu:
    """Interactive BLE Testing Menu"""
    
    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001"):
        self.transport_spec = transport_spec
        self.scanner = BLEScanner(transport_spec)
        self.connector = BLEConnector(transport_spec)
        self.discovered_devices = {}
        self.connected = False
        self.current_device = None
        self.uuid_name_map, self.ad_type_name_map = self._load_resource_maps()
        self._scan_transport = None
        self._scan_device = None
        self._scan_ready = False
        self.filter_name = None
        self.filter_address = None
        self._suppress_adv_printing = False  # Flag to suppress adv printing during connection
        
        # Debug logging configuration
        self.debug_mode = "none"  # none, console, file, both
        self.debug_file_handler = None
        
        # HCI Snoop logging
        self.hci_snooper = None
        self.snoop_enabled = False
        self.ellisys_host = "127.0.0.1"
        self.ellisys_port = 24352
        self.btsnoop_filename = "logs/hci_capture.log"  # .log or .btsnoop format
        self.ellisys_stream = "primary"  # primary, secondary, or tertiary
        
    def print_main_menu(self):
        """Print main menu"""
        print_section("BUMBLE BLE Testing - Main Menu")
        print("A. Bluetooth On")
        print("B. Bluetooth Off")
        print("C. Set Device Filters")
        print(f"D. HCI Snoop Logging (OFF)" if not self.snoop_enabled else f"D. HCI Snoop Logging (ON)")
        print(f"E. Debug Logging ({self.debug_mode.upper()})")
        print("S. SMP Settings")
        print("1. Scan for BLE Devices")
        print("2. Connect to Device")
        print("3. Discover GATT Services")
        print("4. Read Characteristic")
        print("5. Write Characteristic")
        print("6. Write Without Response")
        print("7. Subscribe to Notifications")
        print("8. Subscribe to Indications")
        print("9. Pair / Encrypt Connection")
        print("10. Unpair / Delete Bonding")
        print("11. Disconnect")
        print("12. Burst Write (With Response)")
        print("13. Burst Write (Without Response)")
        print("14. Stop Burst Write")
        print("15. Burst Read")
        print("16. Stop Burst Read")
        print("17. Start CSV Logging")
        print("18. Stop CSV Logging")
        print("0. Exit")
        
        if self.filter_name or self.filter_address:
            print()
            filter_info = []
            if self.filter_name:
                filter_info.append(f"Name: '{self.filter_name}'")
            if self.filter_address:
                filter_info.append(f"Address: '{self.filter_address}'")
            print(f"[Filters Active: {', '.join(filter_info)}]")
        print()
    
    def print_scan_menu(self):
        """Print scan menu"""
        print_section("Discovered Devices")
        if not self.discovered_devices:
            print("No devices discovered yet. Run scan first.\n")
            return
        
        if HAS_RICH:
            table = Table(title="BLE Devices", show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=4)
            table.add_column("Address", style="green", width=20)
            table.add_column("RSSI (dBm)", style="yellow", justify="right", width=12)
            table.add_column("Name", style="white", width=30)
            
            for idx, (addr, info) in enumerate(self.discovered_devices.items(), 1):
                rssi = info.get('rssi', 'N/A')
                name = info.get('name') or "-"
                table.add_row(str(idx), addr, str(rssi), name)
            
            console.print(table)
            print()
        else:
            for idx, (addr, info) in enumerate(self.discovered_devices.items(), 1):
                rssi = info.get('rssi', 'N/A')
                name = info.get('name') or "-"
                print(f"{idx}. {addr:<20} (RSSI: {rssi:>4}) Name: {name}")
            print()

    def _load_resource_maps(self):
        resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resources"))
        uuid_name_map = {}
        ad_type_name_map = {}

        uuid_json_path = os.path.join(resource_dir, "uuid_descriptions.json")
        try:
            with open(uuid_json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for section in ("services", "characteristics", "descriptors"):
                for uuid_str, name in data.get(section, {}).items():
                    for key in self._uuid_aliases(uuid_str):
                        uuid_name_map[key] = name
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug(f"UUID JSON load skipped: {exc}")

        for yaml_name in (
            "service_uuids_sig.yaml",
            "char_uuids_sig.yaml",
            "descriptors_uuid_sig.yaml",
        ):
            yaml_path = os.path.join(resource_dir, yaml_name)
            for entry in self._parse_simple_yaml_list(yaml_path, "uuids"):
                uuid_str = entry.get("uuid")
                name = entry.get("name")
                if uuid_str and name:
                    for key in self._uuid_aliases(uuid_str):
                        uuid_name_map.setdefault(key, name)

        adv_types_path = os.path.join(resource_dir, "adv_types.yaml")
        for entry in self._parse_simple_yaml_list(adv_types_path, "ad_types"):
            value_str = entry.get("value")
            name = entry.get("name")
            if not value_str or not name:
                continue
            try:
                ad_type_value = int(value_str, 0)
            except ValueError:
                continue
            ad_type_name_map[ad_type_value] = name

        return uuid_name_map, ad_type_name_map

    def _parse_simple_yaml_list(self, path: str, list_key: str):
        items = []
        current = None
        in_list = False
        try:
            with open(path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith(f"{list_key}:"):
                        in_list = True
                        continue
                    if not in_list:
                        continue
                    if line.startswith("- "):
                        if current:
                            items.append(current)
                        current = {}
                        line = line[2:].strip()
                    if ":" in line and current is not None:
                        key, value = line.split(":", 1)
                        current[key.strip()] = value.strip()
        except OSError:
            return items
        if current:
            items.append(current)
        return items

    def _uuid_aliases(self, uuid_str: str):
        aliases = []
        cleaned = uuid_str.strip().lower().replace("\"", "")
        if " (" in cleaned:
            cleaned = cleaned.split(" (", 1)[0].strip()
        if cleaned.startswith("uuid-16:"):
            cleaned = cleaned.split("uuid-16:", 1)[1].strip()
        elif cleaned.startswith("uuid-128:"):
            cleaned = cleaned.split("uuid-128:", 1)[1].strip()
        if cleaned.startswith("0x"):
            cleaned = cleaned[2:]
        cleaned = cleaned.strip()

        def add_aliases(hex_value: str):
            hex_value = hex_value.lower()
            if len(hex_value) <= 4:
                padded = hex_value.zfill(4)
                aliases.append(padded)
                aliases.append(f"0000{padded}-0000-1000-8000-00805f9b34fb")
            elif len(hex_value) <= 8:
                padded = hex_value.zfill(8)
                aliases.append(padded)
                aliases.append(f"{padded}-0000-1000-8000-00805f9b34fb")
            else:
                aliases.append(hex_value)

        if "-" in cleaned:
            aliases.append(cleaned)
            plain = cleaned.replace("-", "")
            add_aliases(plain)
        elif all(ch in "0123456789abcdef" for ch in cleaned):
            add_aliases(cleaned)
        else:
            aliases.append(cleaned)

        return list(dict.fromkeys(aliases))

    def _lookup_uuid_name(self, uuid_str: str):
        for key in self._uuid_aliases(uuid_str):
            name = self.uuid_name_map.get(key)
            if name:
                return name
        return None

    def _format_uuid_with_name(self, uuid_str: str):
        name = self._lookup_uuid_name(uuid_str)
        if name:
            return f"{uuid_str} ({name})"
        return uuid_str
    
    def _parse_handle(self, handle_str: str) -> int:
        """Parse handle from string - accepts both decimal and hex (0x prefixed)"""
        handle_str = handle_str.strip()
        if handle_str.lower().startswith('0x'):
            return int(handle_str, 16)
        else:
            return int(handle_str, 10)

    def _format_advertisement_details(self, adv):
        from bumble.core import AdvertisingData, UUID

        details = []
        props = []
        if getattr(adv, "is_legacy", False):
            props.append("legacy")
        else:
            props.append("extended")
        if getattr(adv, "is_connectable", False):
            props.append("connectable")
        if getattr(adv, "is_scannable", False):
            props.append("scannable")
        if getattr(adv, "is_directed", False):
            props.append("directed")
        if getattr(adv, "is_anonymous", False):
            props.append("anonymous")
        if getattr(adv, "is_scan_response", False):
            props.append("scan_response")
        if getattr(adv, "is_truncated", False):
            props.append("truncated")
        if props:
            details.append(("Adv type", ", ".join(props)))

        if not getattr(adv, "data", None):
            return details

        for ad_type, ad_data in adv.data.ad_structures:
            ad_type_id = int(ad_type)
            ad_type_name = self.ad_type_name_map.get(ad_type_id)
            if not ad_type_name:
                ad_type_name = getattr(ad_type, "name", f"0x{ad_type_id:02X}")

            data_str = AdvertisingData.ad_data_to_string(ad_type, ad_data)
            if "]: " in data_str:
                data_str = data_str.split("]: ", 1)[1]
            line = data_str

            try:
                ad_obj = AdvertisingData.ad_data_to_object(ad_type, ad_data)
                if isinstance(ad_obj, list) and ad_obj:
                    named = []
                    for uuid in ad_obj:
                        uuid_str = str(uuid)
                        named.append(self._format_uuid_with_name(uuid_str))
                    line = ", ".join(named)
                elif isinstance(ad_obj, tuple) and ad_obj and isinstance(ad_obj[0], UUID):
                    uuid_str = str(ad_obj[0])
                    line = f"{self._format_uuid_with_name(uuid_str)}, data={ad_obj[1].hex()}"
            except Exception:
                pass

            details.append((ad_type_name, line))

        return details

    def _print_advertisement_details(self, details):
        """Print advertisement details as table or plain text"""
        if not details:
            return

        if HAS_RICH:
            table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
            table.add_column("Type", style="yellow", width=35)
            table.add_column("Value", style="white")

            for ad_type, value in details:
                table.add_row(ad_type, value)

            console.print(Panel(table, expand=False))
        else:
            for ad_type, value in details:
                print(f"      - {ad_type}: {value}")

    def _matches_filters(self, addr_str: str, name: str) -> bool:
        """Check if device matches current filters"""
        if not self.filter_name and not self.filter_address:
            return True
        
        match_name = True
        match_addr = True
        
        if self.filter_name:
            match_name = self.filter_name.lower() in name.lower() if name else False
        
        if self.filter_address:
            match_addr = self.filter_address.lower() in addr_str.lower()
        
        # Match if both filters are set (AND), otherwise match if at least one filter matches
        if self.filter_name and self.filter_address:
            return match_name and match_addr
        elif self.filter_name:
            return match_name
        else:
            return match_addr

    async def menu_set_filters(self):
        """Set device filters for scanning"""
        print_section("Device Filters")
        
        print("Current filters:")
        if self.filter_name or self.filter_address:
            if self.filter_name:
                print(f"  Name filter: '{self.filter_name}'")
            if self.filter_address:
                print(f"  Address filter: '{self.filter_address}'")
        else:
            print("  No filters set (all devices shown)")
        print()
        
        clear = input("Clear all filters? (y/n, default n): ").strip().lower()
        if clear == 'y':
            self.filter_name = None
            self.filter_address = None
            print("✓ Filters cleared\n")
            return
        
        print("\nEnter filter criteria (leave empty to skip):")
        name_input = input("Device name (partial, case-insensitive): ").strip()
        addr_input = input("Device address (partial, e.g., '1E:59:DD'): ").strip()
        
        if not name_input and not addr_input:
            print("No filters set\n")
            return
        
        self.filter_name = name_input if name_input else None
        self.filter_address = addr_input if addr_input else None
        
        print()
        print("✓ Filters updated:")
        if self.filter_name:
            print(f"  - Name contains: '{self.filter_name}'")
        if self.filter_address:
            print(f"  - Address contains: '{self.filter_address}'")
        if self.filter_name and self.filter_address:
            print("  (Both filters must match)")
        print()

    async def menu_toggle_hci_snoop(self):
        """Toggle HCI snoop logging"""
        print_section("HCI Snoop Logging")
        
        if self.snoop_enabled:
            print("HCI Snoop Logging is currently: ON\n")
            print(f"  Ellisys UDP: {self.ellisys_host}:{self.ellisys_port}")
            print(f"  Stream: {self.ellisys_stream.upper()}")
            print(f"  Capture file: {self.btsnoop_filename}\n")
            
            disable = input("Disable HCI snoop logging? (y/n): ").strip().lower()
            if disable == 'y':
                await self._disable_hci_snoop()
                print("\n✓ HCI snoop logging disabled\n")
        else:
            print("HCI Snoop Logging is currently: OFF\n")
            print("Configure HCI snoop settings:\n")
            
            # Get configuration
            ellisys_input = input(f"Ellisys host (default {self.ellisys_host}): ").strip()
            if ellisys_input:
                self.ellisys_host = ellisys_input
            
            port_input = input(f"Ellisys port (default {self.ellisys_port}): ").strip()
            if port_input:
                try:
                    self.ellisys_port = int(port_input)
                except ValueError:
                    print("Invalid port, using default")
            
            print("\nEllisys Data Stream:")
            print("  1. Primary")
            print("  2. Secondary")
            print("  3. Tertiary")
            stream_input = input(f"Select stream (1-3, default 1 for {self.ellisys_stream.upper()}): ").strip()
            if stream_input in ['1', '2', '3']:
                self.ellisys_stream = ['primary', 'secondary', 'tertiary'][int(stream_input) - 1]
            
            print()
            print("Capture file format (.log or .btsnoop - both work with Ellisys/analyzers)")
            file_input = input(f"Filename (default {self.btsnoop_filename}): ").strip()
            if file_input:
                self.btsnoop_filename = file_input
            elif not self.btsnoop_filename.endswith(('.log', '.btsnoop')):
                # Ensure it has a valid extension
                self.btsnoop_filename = "logs/hci_capture.log"
            
            console_log = input("Enable console packet logging? (y/n, default n): ").strip().lower()
            enable_console = console_log == 'y'
            
            enable = input("\nEnable HCI snoop logging with these settings? (y/n): ").strip().lower()
            if enable == 'y':
                await self._enable_hci_snoop(enable_console)
                print("\n✓ HCI snoop logging enabled\n")
                print("Packets will be sent to:")
                print(f"  - Ellisys Analyzer (UDP {self.ellisys_host}:{self.ellisys_port} - {self.ellisys_stream.upper()} stream)")
                print(f"  - Capture file ({self.btsnoop_filename})")
                print(f"    Format: BTSnoop (compatible with Ellisys, Wireshark, etc.)")
                if enable_console:
                    print("  - Console output")
                print()
            else:
                print("\n✗ HCI snoop logging not enabled\n")
    
    async def _enable_hci_snoop(self, enable_console: bool = False):
        """Enable HCI snoop logging"""
        try:
            # Create snooper
            self.hci_snooper = HCISnooper(
                ellisys_host=self.ellisys_host,
                ellisys_port=self.ellisys_port,
                btsnoop_file=self.btsnoop_filename,
                enable_console=enable_console,
                stream=self.ellisys_stream
            )
            
            # Start snooper
            await self.hci_snooper.start()
            self.snoop_enabled = True
            
            # If scan device exists, we need to restart it with wrapped transport
            if self._scan_device:
                print("[INFO] Restarting Bluetooth to apply HCI snoop...")
                await self._close_scan_device()
            
            logger.info("HCI snoop logging enabled")
            
        except Exception as e:
            logger.error(f"Failed to enable HCI snoop: {e}")
            print(f"✗ Failed to enable HCI snoop: {e}")
            self.snoop_enabled = False
    
    async def _disable_hci_snoop(self):
        """Disable HCI snoop logging"""
        try:
            if self.hci_snooper:
                await self.hci_snooper.stop()
                self.hci_snooper = None
            
            self.snoop_enabled = False
            
            # If scan device exists, restart it without wrapper
            if self._scan_device:
                print("[INFO] Restarting Bluetooth to remove HCI snoop...")
                await self._close_scan_device()
            
            logger.info("HCI snoop logging disabled")
            
        except Exception as e:
            logger.error(f"Failed to disable HCI snoop: {e}")
            print(f"✗ Failed to disable HCI snoop: {e}")

    async def menu_debug_logging(self):
        """Configure debug logging level"""
        print_section("Debug Logging Configuration")
        print(f"Current debug logging mode: {self.debug_mode.upper()}\n")
        print("Debug logging modes:")
        print("  1. Console only  - Debug prints to console")
        print("  2. File only     - Debug prints to logs/debug.log")
        print("  3. Both          - Debug prints to console AND file")
        print("  4. None          - Disable debug prints (show required prints only)")
        print("  0. Cancel\n")
        
        choice = input("Select debug mode (0-4): ").strip()
        
        if choice == "1":
            self._configure_debug_logging("console")
            print("\n✓ Debug logging enabled: Console only\n")
        elif choice == "2":
            self._configure_debug_logging("file")
            print("\n✓ Debug logging enabled: File only (logs/debug.log)\n")
        elif choice == "3":
            self._configure_debug_logging("both")
            print("\n✓ Debug logging enabled: Console AND File (logs/debug.log)\n")
        elif choice == "4":
            self._configure_debug_logging("none")
            print("\n✓ Debug logging disabled (required prints only)\n")
        elif choice == "0":
            print()
        else:
            print("\n✗ Invalid choice\n")
    
    def _configure_debug_logging(self, mode: str):
        """Configure debug logging based on mode"""
        self.debug_mode = mode
        root_logger = logging.getLogger()
        bumble_logger = logging.getLogger("bumble")
        app_logger = logging.getLogger(__name__)
        
        # Clear existing debug handlers
        if self.debug_file_handler:
            root_logger.removeHandler(self.debug_file_handler)
            bumble_logger.removeHandler(self.debug_file_handler)
            self.debug_file_handler.close()
            self.debug_file_handler = None
        
        # Always keep Bumble logs at WARNING (user sees them at bridge)
        bumble_logger.setLevel(logging.WARNING)
        
        # Apply new configuration for app logs
        if mode == "none":
            # Disable debug/info logs - only show errors and print() statements
            root_logger.setLevel(logging.WARNING)
            for handler in root_logger.handlers:
                handler.setLevel(logging.WARNING)
        
        elif mode == "console":
            # Enable DEBUG to console (app logs only, not Bumble)
            root_logger.setLevel(logging.DEBUG)
            for handler in root_logger.handlers:
                handler.setLevel(logging.DEBUG)
        
        elif mode == "file":
            # Enable DEBUG to file only
            root_logger.setLevel(logging.DEBUG)
            
            # Set console handlers to WARNING (exclude DEBUG from console)
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(logging.WARNING)
            
            # Create file handler
            try:
                os.makedirs("logs", exist_ok=True)
                self.debug_file_handler = logging.FileHandler("logs/debug.log", encoding='utf-8')
                self.debug_file_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                self.debug_file_handler.setFormatter(formatter)
                root_logger.addHandler(self.debug_file_handler)
            except Exception as e:
                logger.error(f"Failed to create debug log file: {e}")
        
        elif mode == "both":
            # Enable DEBUG to console and file
            root_logger.setLevel(logging.DEBUG)
            
            # Set console handlers to DEBUG
            for handler in root_logger.handlers:
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    handler.setLevel(logging.DEBUG)
            
            # Create file handler
            try:
                os.makedirs("logs", exist_ok=True)
                self.debug_file_handler = logging.FileHandler("logs/debug.log", encoding='utf-8')
                self.debug_file_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                self.debug_file_handler.setFormatter(formatter)
                root_logger.addHandler(self.debug_file_handler)
            except Exception as e:
                logger.error(f"Failed to create debug log file: {e}")

    async def _get_scan_device(self):
        if self._scan_device is not None:
            return self._scan_device

        from bumble.transport import open_transport
        from bumble.device import Device
        from bumble.hci import Address

        logger.info("Opening HCI transport...")
        self._scan_transport = await open_transport(self.transport_spec)
        
        # Wrap transport with HCI snooper if enabled
        if self.snoop_enabled and self.hci_snooper:
            logger.info("Wrapping transport with HCI snooper...")
            wrapper = BumbleHCITransportWrapper(
                self._scan_transport.source,
                self._scan_transport.sink,
                self.hci_snooper
            )
            hci_source = wrapper.source
            hci_sink = wrapper.sink
            print("[HCI SNOOP] ✓ Packet capture active")
        else:
            hci_source = self._scan_transport.source
            hci_sink = self._scan_transport.sink
        
        self._scan_device = Device.with_hci(
            name='BLEScanner',
            address=Address('F0:F1:F2:F3:F4:F5'),
            hci_source=hci_source,
            hci_sink=hci_sink,
        )

        # Enable persistent bonding BEFORE pairing setup
        bonds_file = os.path.join(os.path.dirname(__file__), "..", "configs", "bumble_bonds.json")
        try:
            self._scan_device.keystore = JsonKeyStore(namespace=None, filename=bonds_file)
            logger.info(f"✓ Bumble JsonKeyStore enabled (file: {bonds_file})")
        except Exception as e:
            logger.warning(f"Could not enable persistent bonding: {e}")
        
        # Set up generic SMP pairing on the device (after keystore is ready)
        self.connector.setup_pairing_on_device(self._scan_device)
        
        await self._scan_device.power_on()
        
        # Register device-level connection event handlers
        def on_connection(connection):
            """Handle successful connection establishment"""
            logger.info(f"[CONNECTION] Successfully established to {connection.peer_address}")
            print(f"\n[CONNECTION] ✓ Established to {connection.peer_address}")
        
        def on_connection_failure(error):
            """Handle connection failure"""
            logger.error(f"[CONNECTION FAILED] Error: {error}")
            print(f"\n[CONNECTION FAILED] ✗ {error}")
        
        self._scan_device.on('connection', on_connection)
        self._scan_device.on('connection_failure', on_connection_failure)
        
        self._scan_ready = True
        return self._scan_device

    async def _close_scan_device(self):
        if self._scan_device is None:
            return

        try:
            if getattr(self._scan_device, "scanning", False):
                await self._scan_device.stop_scanning()
        except Exception:
            pass
        try:
            await self._scan_device.power_off()
        except Exception:
            pass
        try:
            if self._scan_transport is not None:
                await self._scan_transport.close()
        except Exception:
            pass

        self._scan_transport = None
        self._scan_device = None
        self._scan_ready = False
    
    async def _do_scan(self, duration: int, filter_duplicates: bool, active_scan: bool):
        """Perform actual BLE scanning"""
        try:
            from bumble.core import AdvertisingData

            device = await self._get_scan_device()
            
            # Clear discovered devices for fresh scan
            self.discovered_devices = {}
            
            scan_mode = "active" if active_scan else "passive"
            dup_mode = "on" if filter_duplicates else "off"
            print(f"Starting LE {scan_mode} scan for {duration} seconds (duplicate filtering: {dup_mode})...\n")
            
            # Subscribe to advertising reports
            found_count = 0
            report_count = 0
            start_time = asyncio.get_event_loop().time()

            def get_local_name(adv):
                if not adv or not adv.data:
                    return ""
                name = adv.data.get(AdvertisingData.COMPLETE_LOCAL_NAME, raw=True)
                if name is None:
                    name = adv.data.get(AdvertisingData.SHORTENED_LOCAL_NAME, raw=True)
                if not name:
                    return ""
                if isinstance(name, bytes):
                    try:
                        return name.decode('utf-8')
                    except UnicodeDecodeError:
                        return name.hex()
                return str(name)
            
            def on_advertisement(adv):
                nonlocal found_count, report_count
                report_count += 1
                addr_str = str(adv.address)
                name = get_local_name(adv)
                
                # Suppress printing if flag is set (e.g., during connection)
                if self._suppress_adv_printing:
                    return
                
                # Apply filters
                if not self._matches_filters(addr_str, name):
                    return
                
                data_bytes = getattr(adv, "data_bytes", b"") or b""
                data_hex = data_bytes.hex()
                is_scan_response = bool(getattr(adv, 'is_scan_response', False))
                event_tag = "SR" if is_scan_response else "ADV"
                name_suffix = f" Name: {name}" if name else ""

                if addr_str not in self.discovered_devices:
                    found_count += 1
                    self.discovered_devices[addr_str] = {
                        'address': addr_str,
                        'rssi': adv.rssi,
                        'data': str(adv.data) if adv.data else "",
                        'data_hex': data_hex,
                        'name': name,
                        'last_printed_data_hex': data_hex,
                        'details_printed': True,  # Track if we've shown details
                    }
                    print(f"  [{found_count}] {event_tag} {addr_str:<20} RSSI: {adv.rssi:4d} dBm{name_suffix}")
                    details = self._format_advertisement_details(adv)
                    self._print_advertisement_details(details)
                    return

                device_info = self.discovered_devices[addr_str]
                device_info['rssi'] = adv.rssi
                if name and name != device_info.get('name'):
                    device_info['name'] = name
                if not device_info.get('data') and adv.data:
                    device_info['data'] = str(adv.data)
                if data_hex:
                    device_info['data_hex'] = data_hex

                # Only print details if data actually changed (not just scan response)
                data_changed = data_hex and data_hex != device_info.get('last_printed_data_hex')
                
                # Only show details if this is truly new/changed data AND we haven't printed details yet
                if data_changed and not device_info.get('details_printed'):
                    details = self._format_advertisement_details(adv)
                    self._print_advertisement_details(details)
                    device_info['last_printed_data_hex'] = data_hex
                    device_info['details_printed'] = True

                if not filter_duplicates:
                    print(f"  [{report_count}] {event_tag} {addr_str:<20} RSSI: {adv.rssi:4d} dBm{name_suffix}")
            
            device.on('advertisement', on_advertisement)
            
            # Start scanning
            await device.start_scanning(active=active_scan, filter_duplicates=filter_duplicates)
            
            # Scan for specified duration
            while asyncio.get_event_loop().time() - start_time < duration:
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                if filter_duplicates:
                    status = f"Found {found_count} devices"
                else:
                    status = f"Found {found_count} devices ({report_count} reports)"
                print(f"  [{elapsed+1}/{duration}] Scanning... {status}", end='\r')
                await asyncio.sleep(1)
            
            # Stop scanning
            await device.stop_scanning()
            
            if filter_duplicates:
                print(f"\n✓ Scan complete. Found {found_count} total devices\n")
            else:
                print(f"\n✓ Scan complete. Found {found_count} devices across {report_count} reports\n")
            
            if found_count > 0:
                print("Discovered devices:")
                self.print_scan_menu()
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n✗ Scan failed: {e}\n")
    
    async def menu_scan_devices(self):
        """Scan for devices"""
        print_section("Scanning for BLE Devices")
        
        try:
            duration = input("Enter scan duration in seconds (default 10): ").strip()
            duration = int(duration) if duration else 10

            dup_input = input("Filter duplicate advertisements? (Y/n): ").strip().lower()
            filter_duplicates = dup_input != 'n'

            active_input = input("Active scan (request scan response)? (Y/n): ").strip().lower()
            active_scan = active_input != 'n'
            
            print(f"\nScanning for {duration} seconds...\n")
            
            # Perform actual scanning through HCI
            await self._do_scan(duration, filter_duplicates, active_scan)
            
            print("\nScan complete!")
            
        except ValueError:
            print("Invalid input!")
        except KeyboardInterrupt:
            print("\nScan cancelled")
        except Exception as e:
            logger.error(f"Scan error: {e}")

    async def menu_bluetooth_on(self):
        """Power on Bluetooth controller"""
        print_section("Bluetooth On")
        try:
            await self._get_scan_device()
            print("✓ Bluetooth is ON\n")
            
            # Show bonding status
            bonds_file = os.path.join(os.path.dirname(__file__), "..", "configs", "bumble_bonds.json")
            if os.path.exists(bonds_file):
                try:
                    with open(bonds_file, 'r') as f:
                        bonds_data = json.load(f)
                    bonded_count = len(bonds_data.get('bonds', {}))
                    print(f"📱 Bonded devices: {bonded_count}")
                    if bonded_count > 0 and bonded_count <= 5:
                        for addr in bonds_data.get('bonds', {}).keys():
                            print(f"   - {addr}")
                    print()
                except Exception as e:
                    logger.debug(f"Could not read bonds file: {e}")
        except Exception as e:
            logger.error(f"Bluetooth on error: {e}")
            print(f"✗ Failed to power on Bluetooth: {e}\n")

    async def menu_bluetooth_off(self):
        """Power off Bluetooth controller"""
        print_section("Bluetooth Off")
        try:
            await self._close_scan_device()
            print("✓ Bluetooth is OFF\n")
        except Exception as e:
            logger.error(f"Bluetooth off error: {e}")
            print(f"✗ Failed to power off Bluetooth: {e}\n")
    
    async def menu_connect_device(self):
        """Connect to device"""
        print_section("Connect to BLE Device")
        
        self.print_scan_menu()
        
        if not self.discovered_devices:
            print("No devices available. Run scan first (option 1)\n")
            return
        
        # Option 1: Select by number
        choice = input("Enter device number from list (or address manually): ").strip()
        
        try:
            # Try as number first
            device_idx = int(choice)
            if 1 <= device_idx <= len(self.discovered_devices):
                address = list(self.discovered_devices.keys())[device_idx - 1]
            else:
                print(f"Invalid number. Enter 1-{len(self.discovered_devices)}\n")
                return
        except ValueError:
            # Assume it's an address
            address = choice
        
        address = format_address(address)
        
        # Verify device is ready
        if self._scan_device is None:
            print("✗ Device not initialized. Run 'A' (Bluetooth On) first.\n")
            return
        
        # Explicitly stop any active scanning
        if getattr(self._scan_device, "scanning", False):
            try:
                logger.info("Stopping scan before connection")
                await self._scan_device.stop_scanning()
                await asyncio.sleep(1)  # Give time for scan to stop
            except Exception as e:
                logger.warning(f"Failed to stop scan: {e}")
                print(f"✗ Warning: Could not stop scan cleanly: {e}\n")
                return
        
        # Use the existing scan device for connection
        try:
            from bumble.hci import Address
            
            logger.info(f"[MAIN] Connecting to device: {address}")
            
            device = self._scan_device
            target_address = Address(address)
            
            print(f"\nConnecting to {address}...")
            print("(This may take a few seconds... press Ctrl+C to cancel)\n")
            logger.info(f"[MAIN] Calling device.connect() to {address}")
            
            # Use timeout to prevent indefinite hanging
            try:
                # Suppress advertisement printing during connection
                self._suppress_adv_printing = True
                connect_task = None
                try:
                    connect_task = asyncio.create_task(
                        device.connect(target_address)
                    )
                    self.connector.connected_device = await asyncio.wait_for(
                        connect_task,
                        timeout=30.0  # 30 second timeout
                    )
                except asyncio.TimeoutError:
                    # Cancel the connection task and HCI command
                    logger.error(f"Connection timeout to {address}")
                    if connect_task:
                        connect_task.cancel()
                    # Try to cancel pending connection at HCI level
                    try:
                        from bumble.hci import HCI_LE_Create_Connection_Cancel_Command
                        await device.send_command(HCI_LE_Create_Connection_Cancel_Command())
                        logger.info(f"Sent HCI_LE_Create_Connection_Cancel to {address}")
                    except Exception as e:
                        logger.debug(f"Could not cancel HCI connection: {e}")
                    self._suppress_adv_printing = False
                    print(f"\n✗ Connection timeout - device not responding after 30 seconds")
                    print("  Check HCI bridge logs above for error details")
                    print("  - Is device powered on and in range?")
                    print("  - Try scanning again (option 1)")
                    print()
                    return
                self._suppress_adv_printing = False
            except Exception as e:
                self._suppress_adv_printing = False
                raise
            
            self.connector.device = device  # Reuse the same device
            
            # Register disconnection event handler
            def on_disconnection(reason):
                """Handle remote disconnection event"""
                logger.info(f"[DISCONNECTION] Remote device disconnected, reason: {reason}")
                print(f"\n[DISCONNECTION] Remote device disconnected (reason: {reason})")
                self.connected = False
                self.current_device = None
                self.connector.connected_device = None
            
            self.connector.connected_device.on('disconnection', on_disconnection)
            
            self.connected = True
            self.current_device = address
            print(f"✓ Successfully connected to {address}")
            
            # Check if device is already bonded
            is_bonded = self.connector.is_device_bonded(address)
            
            if is_bonded:
                print("✓ Device is already bonded - no pairing needed\n")
                logger.info("[MAIN] Device already bonded, no pairing required")
            else:
                print("\nInitiating pairing (peer requested security)...\n")
                
                self.current_connection = self.connector.connected_device
                
                # Peer initiated security request, respond with pairing
                try:
                    logger.info("[MAIN] Responding to peer security request with pairing")
                    print("🔐 Responding to peer's security request...\n")
                    await asyncio.wait_for(
                        device.pair(self.connector.connected_device),
                        timeout=30.0
                    )
                    print("\n✓ Pairing completed!\n")
                except asyncio.TimeoutError:
                    print("\n⏱ Pairing timeout - peer didn't respond in time\n")
                    logger.warning("[MAIN] Pairing timeout")
                except Exception as e:
                    logger.warning(f"[MAIN] Pairing didn't complete immediately: {e}")
                    print(f"Note: Pairing may complete in background. Check bridge logs.\n")
            
            print("Connection ready.\n")
            print("Next steps:")
            print("  - Option 9: Encrypt connection (if bonded)")
            print("  - Option 3: Discover GATT Services")
            print("  - Option 11: Disconnect\n")
        except KeyboardInterrupt:
            self._suppress_adv_printing = False
            print("\n✗ Connection cancelled\n")
            logger.info("Connection cancelled by user")
        except Exception as e:
            self._suppress_adv_printing = False
            logger.error(f"Connection failed: {e}", exc_info=True)
            print(f"✗ Connection error: {e}")
            print("\nFull traceback above in logs")
    
    async def menu_discover_services(self):
        """Discover GATT services"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Discovering GATT Services")
        print(f"Device: {self.current_device}\n")
        
        # Always do fresh discovery for this standalone option
        services = await self.connector.discover_services(force_fresh=True)

        if services:
            if HAS_RICH and console:
                details = self.connector.service_details
                table = Table(
                    title="BLE Services & Characteristics",
                    box=box.MINIMAL_HEAVY_HEAD,
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("Type", style="cyan", no_wrap=True)
                table.add_column("UUID", style="green")
                table.add_column("Handle", style="yellow", no_wrap=True)
                table.add_column("Properties", style="magenta")
                table.add_column("Description", style="white")

                for svc_index, service in enumerate(details):
                    service_uuid = service.get("uuid", "-")
                    svc_desc = self._lookup_uuid_name(service_uuid) or "-"

                    start_handle = service.get("handle")
                    end_handle = service.get("end_group_handle")
                    if start_handle is not None and end_handle is not None:
                        handle_str = f"0x{start_handle:04X}-0x{end_handle:04X} ({start_handle}-{end_handle})"
                    elif start_handle is not None:
                        handle_str = f"0x{start_handle:04X} ({start_handle})"
                    else:
                        handle_str = "-"

                    table.add_row("[bold]SERVICE[/bold]", service_uuid, handle_str, "-", svc_desc)

                    chars = service.get("characteristics", [])
                    if chars:
                        for char in chars:
                            char_uuid = char.get("uuid", "-")
                            char_desc = self._lookup_uuid_name(char_uuid) or "-"
                            char_handle = char.get("handle")
                            char_props = char.get("properties") or "-"
                            if char_handle is not None:
                                char_handle_str = f"0x{char_handle:04X} ({char_handle})"
                            else:
                                char_handle_str = "-"

                            table.add_row(
                                "  └─ [yellow]CHAR[/yellow]",
                                char_uuid,
                                char_handle_str,
                                char_props,
                                char_desc,
                            )

                            descriptors = char.get("descriptors", [])
                            for desc in descriptors:
                                desc_uuid = desc.get("uuid", "-")
                                desc_desc = self._lookup_uuid_name(desc_uuid) or "-"
                                desc_handle = desc.get("handle")
                                if desc_handle is not None:
                                    desc_handle_str = f"0x{desc_handle:04X} ({desc_handle})"
                                else:
                                    desc_handle_str = "-"
                                table.add_row(
                                    "     └─ [blue]DESC[/blue]",
                                    desc_uuid,
                                    desc_handle_str,
                                    "-",
                                    desc_desc,
                                )
                    else:
                        table.add_row(
                            "  └─ [yellow]CHAR[/yellow]",
                            "-",
                            "-",
                            "-",
                            "[dim]No characteristics[/dim]",
                        )

                    if svc_index < len(details) - 1:
                        table.add_row(
                            "[dim]----------[/dim]",
                            "[dim]------------------------------------[/dim]",
                            "[dim]------------[/dim]",
                            "[dim]--------------------[/dim]",
                            "[dim]------------------------------[/dim]",
                        )

                console.print(table)
            else:
                print(f"Found {len(services)} services:")
                for uuid, chars in services.items():
                    print(f"  Service: {uuid}")
                    for char in chars:
                        print(f"    - {char}")
        else:
            print("No services found")
        print()

    async def _maybe_show_discovery_table(self, operation: str = "read"):
        """Optionally show characteristics table for the operation"""
        prompt = input("Show characteristics? (y/N): ").strip().lower()
        if prompt == "y":
            await self._show_characteristics_table(operation)

    async def _show_characteristics_table(self, operation: str = "read"):
        """Display only characteristics table with relevant properties highlighted"""
        if not self.connector.service_details:
            await self.connector.discover_services()
        
        details = self.connector.service_details
        chars_with_props = []
        
        # Collect characteristics that support the operation
        for service in details:
            chars = service.get("characteristics", [])
            for char in chars:
                char_uuid = char.get("uuid", "-")
                char_handle = char.get("handle")
                char_props = char.get("properties", "")
                char_desc = self._lookup_uuid_name(char_uuid) or "-"
                
                if char_handle is not None:
                    char_handle_str = f"0x{char_handle:04X} ({char_handle})"
                else:
                    char_handle_str = "-"
                
                # Parse properties - distinguish write vs write without response
                props_lower = char_props.lower()
                has_read = "read" in props_lower
                has_write = "write" in props_lower and "write_without" not in props_lower
                has_notify = "notify" in props_lower
                has_indicate = "indicate" in props_lower
                has_write_no_resp = "write_without" in props_lower
                
                # Filter based on operation
                supports_operation = False
                if operation == "read" and has_read:
                    supports_operation = True
                elif operation == "write" and has_write:
                    supports_operation = True
                elif operation == "write_without_response" and has_write_no_resp:
                    supports_operation = True
                elif operation == "burst_write" and (has_write or has_write_no_resp):
                    supports_operation = True
                elif operation == "notify" and has_notify:
                    supports_operation = True
                elif operation == "indicate" and has_indicate:
                    supports_operation = True
                elif operation == "burst_read" and has_read:
                    supports_operation = True
                
                # Only add if supports this operation
                if supports_operation:
                    # Build property string
                    props_list = []
                    if has_read:
                        props_list.append("R" if operation == "read" else "r")
                    if has_write:
                        props_list.append("W" if operation == "write" else "w")
                    if has_write_no_resp:
                        props_list.append("WWR" if operation in ("write_without_response", "burst_write") else "wwr")
                    if has_notify:
                        props_list.append("N" if operation == "notify" else "n")
                    if has_indicate:
                        props_list.append("I" if operation == "indicate" else "i")
                    
                    props_str = ",".join(props_list) if props_list else "-"
                    
                    chars_with_props.append({
                        "uuid": char_uuid,
                        "handle": char_handle_str,
                        "props": props_str,
                        "description": char_desc,
                    })
        
        if not chars_with_props:
            print("No characteristics found that support this operation.\n")
            return
        
        if HAS_RICH and console:
            table = Table(
                title="Available Characteristics",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Handle", style="yellow", no_wrap=True)
            table.add_column("UUID", style="green")
            table.add_column("Prop*", style="magenta", justify="center", no_wrap=True)
            table.add_column("Description", style="white")
            
            for char_info in chars_with_props:
                table.add_row(
                    char_info["handle"],
                    char_info["uuid"],
                    char_info["props"],
                    char_info["description"],
                )
            
            console.print(table)
            print("* Properties: R=Read, W=Write, WWR=Write Without Response, N=Notify, I=Indicate (only supported for this operation)\n")
        else:
            print("\nCharacteristics:")
            for idx, char_info in enumerate(chars_with_props, 1):
                print(f"{idx}. {char_info['handle']:<20} Props: {char_info['props']:<10} UUID: {char_info['uuid']}")
                print(f"   Description: {char_info['description']}\n")

    def _print_read_value(self, handle: int, value: bytes, title: Optional[str] = None):
        """Print read result in the same format as menu_read_characteristic."""
        if HAS_RICH and console:
            table = Table(
                title=title or f"Read Result - Handle 0x{handle:04X}",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("Property", style="yellow", no_wrap=True)
            table.add_column("Value", style="green")

            table.add_row("Handle", f"0x{handle:04X} (decimal: {handle})")
            table.add_row("Length", f"{len(value)} bytes")
            table.add_row("Hex", value.hex())
            table.add_row("Hex (spaced)", " ".join(f"{b:02x}" for b in value))

            ascii_val = value.decode("utf-8", errors="replace")
            printable_ascii = "".join(
                c if c.isprintable() or c in "\n\r\t" else "." for c in ascii_val
            )
            table.add_row("ASCII", printable_ascii)

            if len(value) == 1:
                table.add_row("Uint8", str(value[0]))
            elif len(value) == 2:
                import struct

                table.add_row("Uint16 (LE)", str(struct.unpack("<H", value)[0]))
                table.add_row("Uint16 (BE)", str(struct.unpack(">H", value)[0]))
            elif len(value) == 4:
                import struct

                table.add_row("Uint32 (LE)", str(struct.unpack("<I", value)[0]))
                table.add_row("Uint32 (BE)", str(struct.unpack(">I", value)[0]))

            console.print()
            console.print(table)
            console.print()
        else:
            print(f"\n✓ Value: {value.hex()}")
            print(f"  Length: {len(value)} bytes")
            print(f"  ASCII: {value.decode('utf-8', errors='replace')}")
    
    async def menu_read_characteristic(self):
        """Read a characteristic"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Read Characteristic")
        
        try:
            await self._maybe_show_discovery_table("read")
            handle = self._parse_handle(input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip())
            
            value = await self.connector.read_characteristic(handle)
            
            if value is not None:
                self._print_read_value(handle, value)
            else:
                print(f"\n✗ Failed to read handle 0x{handle:04X} ({handle})")
                
        except ValueError:
            print("Invalid handle\n")
        except Exception as e:
            logger.error(f"Error: {e}")
        
        print()
    
    async def menu_write_characteristic(self):
        """Write to characteristic"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Write Characteristic")
        
        try:
            await self._maybe_show_discovery_table("write")
            handle = self._parse_handle(input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip())
            hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
            
            # Parse hex
            hex_value = hex_value.replace(' ', '')
            value = bytes.fromhex(hex_value)
            
            if await self.connector.write_characteristic(handle, value):
                print(f"\n✓ Successfully wrote to handle 0x{handle:04X} ({handle})\n")
            else:
                print(f"\n✗ Failed to write to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError as e:
            print(f"Invalid input: {e}\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")
    
    async def menu_write_without_response(self):
        """Write without response"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Write Without Response")
        
        try:
            await self._maybe_show_discovery_table("write_without_response")
            handle = self._parse_handle(input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip())
            hex_value = input("Enter value (hex): ").strip()
            
            hex_value = hex_value.replace(' ', '')
            value = bytes.fromhex(hex_value)
            
            if await self.connector.write_without_response(handle, value):
                print(f"\n✓ Successfully sent to handle 0x{handle:04X} ({handle})\n")
            else:
                print(f"\n✗ Failed to send to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError as e:
            print(f"Invalid input: {e}\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")
    
    async def menu_subscribe(self):
        """Subscribe to notifications"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Subscribe to Notifications")
        
        try:
            await self._maybe_show_discovery_table("notify")
            handle = self._parse_handle(input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip())
            
            if await self.connector.subscribe_notifications(handle):
                print(f"\n✓ Subscribed to notifications on handle 0x{handle:04X} ({handle})")
                print("Notifications will be printed when received.\n")
            else:
                print(f"\n✗ Failed to subscribe to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError:
            print("Invalid handle\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")
    
    async def menu_subscribe_indications(self):
        """Subscribe to indications"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Subscribe to Indications")
        
        try:
            await self._maybe_show_discovery_table("indicate")
            handle = self._parse_handle(input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip())
            
            if await self.connector.subscribe_indications(handle):
                print(f"\n✓ Subscribed to indications on handle 0x{handle:04X} ({handle})")
                print("Indications will be printed when received.\n")
            else:
                print(f"\n✗ Failed to subscribe to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError:
            print("Invalid handle\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_burst_write(self):
        """Burst write with response"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Write (With Response)")

        try:
            await self._maybe_show_discovery_table("burst_write")
            handle = self._parse_handle(
                input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
            )
            hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
            hex_value = hex_value.replace(" ", "")
            value = bytes.fromhex(hex_value)

            count_str = input("Count (0 = infinite, default 0): ").strip()
            count = int(count_str) if count_str else 0
            interval_str = input("Interval ms (default 100): ").strip()
            interval_ms = int(interval_str) if interval_str else 100

            await self.connector.start_burst_write(
                handle,
                value,
                with_response=True,
                count=count,
                interval_ms=interval_ms,
            )
            print("Burst write started in background.\n")
        except ValueError as e:
            print(f"Invalid input: {e}\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_burst_write_without_response(self):
        """Burst write without response"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Write (Without Response)")

        try:
            await self._maybe_show_discovery_table("burst_write")
            handle = self._parse_handle(
                input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
            )
            hex_value = input("Enter value (hex, space-separated or continuous): ").strip()
            hex_value = hex_value.replace(" ", "")
            value = bytes.fromhex(hex_value)

            count_str = input("Count (0 = infinite, default 0): ").strip()
            count = int(count_str) if count_str else 0
            interval_str = input("Interval ms (default 100): ").strip()
            interval_ms = int(interval_str) if interval_str else 100

            await self.connector.start_burst_write(
                handle,
                value,
                with_response=False,
                count=count,
                interval_ms=interval_ms,
            )
            print("Burst write started in background.\n")
        except ValueError as e:
            print(f"Invalid input: {e}\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_stop_burst_write(self):
        """Stop burst write"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Stop Burst Write")

        try:
            stopped = await self.connector.stop_burst_write()
            if stopped:
                print("Burst write stopped.\n")
            else:
                print("No active burst write to stop.\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_burst_read(self):
        """Burst read"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Read")

        try:
            await self._maybe_show_discovery_table("burst_read")
            handle = self._parse_handle(
                input("Enter characteristic handle (hex 0x0054 or decimal 84): ").strip()
            )

            count_str = input("Count (0 = infinite, default 0): ").strip()
            count = int(count_str) if count_str else 0
            interval_str = input("Interval ms (default 100): ").strip()
            interval_ms = int(interval_str) if interval_str else 100

            print_choice = input("Print each read to console? (y/N): ").strip().lower()
            should_print = print_choice == "y"

            def _burst_read_printer(burst_handle: int, value: bytes, read_count: int):
                title = f"Burst Read #{read_count} - Handle 0x{burst_handle:04X}"
                self._print_read_value(burst_handle, value, title=title)

            callback = _burst_read_printer if should_print else None

            await self.connector.start_burst_read(
                handle,
                count=count,
                interval_ms=interval_ms,
                on_value=callback,
            )
            print("Burst read started in background.\n")
        except ValueError as e:
            print(f"Invalid input: {e}\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_stop_burst_read(self):
        """Stop burst read"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Stop Burst Read")

        try:
            stopped = await self.connector.stop_burst_read()
            if stopped:
                print("Burst read stopped.\n")
            else:
                print("No active burst read to stop.\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_start_csv_logging(self):
        """Start CSV logging"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Start CSV Logging")

        try:
            filename = input("CSV filename (default: notifications_TIMESTAMP.csv): ").strip()
            filename = filename if filename else None
            if self.connector.start_csv_logging(filename):
                print("CSV logging started.\n")
            else:
                print("CSV logging is already active or failed to start.\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_stop_csv_logging(self):
        """Stop CSV logging"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Stop CSV Logging")

        try:
            if self.connector.stop_csv_logging():
                print("CSV logging stopped.\n")
            else:
                print("No active CSV logging to stop.\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def menu_smp_settings(self):
        """SMP Settings Menu - Configure pairing parameters"""
        while True:
            print_section("SMP (Secure Manager Protocol) Settings")

            config = self.connector.get_smp_config()

            print("Current Configuration:")
            print(f"  1. IO Capability: {config['io_capability']}")
            print(f"  2. MITM Required: {'YES' if config['mitm_required'] else 'NO'}")
            print(
                f"  3. LE Secure Connections: {'ENABLED' if config['le_secure_connections'] else 'DISABLED'}"
            )
            print(
                f"  4. Encryption Key Size: {config['min_enc_key_size']}-{config['max_enc_key_size']} bytes"
            )
            print(f"  5. Bonding: {'ENABLED' if config['bonding_enabled'] else 'DISABLED'}")
            print("  0. Back to Main Menu\n")

            choice = input("Select option: ").strip()

            if choice == "0":
                break
            elif choice == "1":
                await self.menu_smp_io_capability()
            elif choice == "2":
                await self.menu_smp_mitm_required()
            elif choice == "3":
                await self.menu_smp_secure_connections()
            elif choice == "4":
                await self.menu_smp_encryption_key_size()
            elif choice == "5":
                await self.menu_smp_bonding()
            else:
                print("Invalid option\n")

    async def menu_smp_io_capability(self):
        """Configure SMP IO Capability"""
        print_section("IO Capability Configuration")

        current = self.connector.get_smp_config()['io_capability']
        print(f"Current: {current}\n")
        print("Available IO Capabilities:")
        print("  1. DISPLAY_ONLY - Can display only")
        print("  2. KEYBOARD_ONLY - Has keyboard input only")
        print("  3. NO_INPUT_NO_OUTPUT - No input/output capability")
        print("  4. KEYBOARD_DISPLAY - Has both keyboard and display")
        print("  5. DISPLAY_OUTPUT_AND_KEYBOARD_INPUT - Display and keyboard (recommended)")
        print("  0. Cancel\n")

        choice = input("Select IO capability: ").strip()

        io_map = {
            "1": "DISPLAY_ONLY",
            "2": "KEYBOARD_ONLY",
            "3": "NO_INPUT_NO_OUTPUT",
            "4": "KEYBOARD_DISPLAY",
            "5": "DISPLAY_OUTPUT_AND_KEYBOARD_INPUT",
        }

        if choice in io_map:
            if self.connector.set_smp_io_capability(io_map[choice]):
                print(f"✓ IO Capability set to: {io_map[choice]}\n")
            else:
                print("✗ Failed to set IO capability\n")
        elif choice != "0":
            print("Invalid option\n")

    async def menu_smp_mitm_required(self):
        """Configure MITM Protection Requirement"""
        print_section("MITM Protection Configuration")

        current = self.connector.get_smp_config()['mitm_required']
        print(f"Current: {'YES (REQUIRED)' if current else 'NO (NOT REQUIRED)'}\n")
        print("MITM Protection prevents Man-in-the-Middle attacks during pairing.")
        print("  1. Enable MITM Protection (Recommended for security-sensitive devices)")
        print("  2. Disable MITM Protection (Easier pairing, less secure)")
        print("  0. Cancel\n")

        choice = input("Select option: ").strip()

        if choice == "1":
            self.connector.set_smp_mitm_required(True)
            print("✓ MITM Protection: ENABLED\n")
        elif choice == "2":
            self.connector.set_smp_mitm_required(False)
            print("✓ MITM Protection: DISABLED\n")
        elif choice != "0":
            print("Invalid option\n")

    async def menu_smp_secure_connections(self):
        """Configure LE Secure Connections"""
        print_section("LE Secure Connections Configuration")

        current = self.connector.get_smp_config()['le_secure_connections']
        print(f"Current: {'ENABLED' if current else 'DISABLED'}\n")
        print("LE Secure Connections (ECDH):")
        print("  - Uses ECDH for key agreement (more secure)")
        print("  - Prevents passive eavesdropping")
        print("  - Required for some BLE features\n")
        print("  1. Enable LE Secure Connections (Recommended)")
        print("  2. Disable LE Secure Connections (Legacy pairing)")
        print("  0. Cancel\n")

        choice = input("Select option: ").strip()

        if choice == "1":
            self.connector.set_smp_secure_connections(True)
            print("✓ LE Secure Connections: ENABLED\n")
        elif choice == "2":
            self.connector.set_smp_secure_connections(False)
            print("✓ LE Secure Connections: DISABLED\n")
        elif choice != "0":
            print("Invalid option\n")

    async def menu_smp_encryption_key_size(self):
        """Configure Encryption Key Size"""
        print_section("Encryption Key Size Configuration")

        config = self.connector.get_smp_config()
        current_min = config['min_enc_key_size']
        current_max = config['max_enc_key_size']
        print(f"Current: {current_min}-{current_max} bytes\n")
        print("Encryption Key Size: 7-16 bytes (7=56-bit, 16=128-bit)")
        print("  - Larger keys are more secure but may be slower")
        print("  - Most devices support 16-byte keys\n")

        try:
            min_input = input("Enter minimum key size (7-16, default 7): ").strip()
            min_size = int(min_input) if min_input else 7

            max_input = input("Enter maximum key size (7-16, default 16): ").strip()
            max_size = int(max_input) if max_input else 16

            if self.connector.set_smp_encryption_key_size(min_size, max_size):
                print(f"✓ Encryption Key Size: {min_size}-{max_size} bytes\n")
            else:
                print("✗ Invalid key size range (must be 7-16, min <= max)\n")
        except ValueError:
            print("✗ Invalid input - must be numeric\n")

    async def menu_smp_bonding(self):
        """Configure Bonding Enable/Disable"""
        print_section("Bonding Configuration")

        current = self.connector.get_smp_config()['bonding_enabled']
        print(f"Current: {'ENABLED' if current else 'DISABLED'}\n")
        print("Bonding - Store link keys for future re-pairing:")
        print("  - When ENABLED: Link keys are saved automatically")
        print("  - When DISABLED: Keys are not saved, must re-pair on reconnect")
        print("  - Keys are stored in: configs/bumble_bonds.json\n")
        print("  1. Enable Bonding (Recommended)")
        print("  2. Disable Bonding")
        print("  0. Cancel\n")

        choice = input("Select option: ").strip()

        if choice == "1":
            self.connector.set_smp_bonding_enabled(True)
            print("✓ Bonding: ENABLED\n")
        elif choice == "2":
            self.connector.set_smp_bonding_enabled(False)
            print("✓ Bonding: DISABLED\n")
        elif choice != "0":
            print("Invalid option\n")
    
    async def menu_pair(self):
        """Pair with device or encrypt connection if bonded"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Pairing / Encryption")
        print(f"Device: {self.current_device}\n")
        
        # Check if device is bonded
        is_bonded = self.connector.is_device_bonded(self.current_device)
        
        if is_bonded:
            print("✓ Device is bonded\n")
            print("Bonded keys are automatically used for encryption.")
            print("The connection may already be encrypted.\n")
            
            confirm = input("Check/verify encryption status? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Cancelled\n")
                return
            
            print("\nVerifying security status...")
            try:
                success = await asyncio.wait_for(
                    self.connector.establish_security(),
                    timeout=10.0
                )
                if success:
                    print("\n✓ Security verified or established!\n")
                else:
                    print("\n⚠ Could not verify encryption\n")
            except asyncio.TimeoutError:
                print("\n✗ Security check timeout\n")
            except Exception as e:
                logger.error(f"Security check error: {e}")
                print(f"⚠ Security check: {e}\n")
        else:
            print("Device is not yet bonded - initiating pairing...\n")
            confirm = input("Initiate pairing? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Cancelled\n")
                return
            
            print("\nInitiating SMP pairing...")
            print("(Watch for pairing prompts - you may need to:")
            print("  - Enter a passkey")
            print("  - Confirm a numeric comparison code")
            print("  - Or just accept)\n")
            
            try:
                # Give it up to 60 seconds to complete pairing
                success = await asyncio.wait_for(
                    self.connector.pair(),
                    timeout=60.0
                )
                
                if success:
                    print("\n✓ Pairing successful!\n")
                    print("Device is now bonded.")
                    print("Use this option again to verify encryption on future connections.\n")
                else:
                    print("\n✗ Pairing failed - check messages above\n")
            except asyncio.TimeoutError:
                print("\n✗ Pairing timeout - device did not respond\n")
            except Exception as e:
                logger.error(f"Pairing error: {e}")
                print(f"✗ Pairing error: {e}\n")
    
    async def menu_unpair(self):
        """Unpair / Delete bonding"""
        print_section("Unpair / Delete Bonding")
        
        # List bonded devices
        bonded = self.connector.get_bonded_devices()
        
        if not bonded:
            print("No bonded devices found.\n")
            return
        
        print(f"Found {len(bonded)} bonded device(s):\n")
        
        if HAS_RICH:
            table = Table(title="Bonded Devices", show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=4)
            table.add_column("Address", style="green", width=20)
            
            for idx, addr in enumerate(bonded.keys(), 1):
                table.add_row(str(idx), addr)
            
            console.print(table)
        else:
            for idx, addr in enumerate(bonded.keys(), 1):
                print(f"{idx}. {addr}")
        
        print()
        choice = input("Enter number to unpair (or press Enter to cancel): ").strip()
        
        if not choice:
            print("Cancelled\n")
            return
        
        try:
            idx = int(choice) - 1
            addresses = list(bonded.keys())
            if 0 <= idx < len(addresses):
                target_addr = addresses[idx]
                confirm = input(f"\nUnpair {target_addr}? (y/n): ").strip().lower()
                if confirm == 'y':
                    if self.connector.delete_bonding(target_addr):
                        print(f"\n✓ Bonding deleted for {target_addr}\n")
                    else:
                        print(f"\n✗ Failed to delete bonding for {target_addr}\n")
                else:
                    print("Cancelled\n")
            else:
                print("Invalid number\n")
        except ValueError:
            print("Invalid input\n")
    
    async def menu_disconnect(self):
        """Disconnect from device"""
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        try:
            if self.connector.connected_device:
                await self.connector.connected_device.disconnect()
                self.connector.connected_device = None
            
            self.connected = False
            self.current_device = None
            print("✓ Disconnected\n")
        except Exception as e:
            logger.error(f"Disconnect failed: {e}")
            print(f"✗ Disconnect failed: {e}\n")
    
    async def run(self):
        """Run the interactive menu"""
        print_section("BUMBLE BLE TESTING FRAMEWORK")
        print(f"Transport: {self.transport_spec}\n")

        async def _prompt(text: str) -> str:
            return await asyncio.to_thread(input, text)
        
        try:
            while True:
                self.print_main_menu()

                choice = (await _prompt("Select option: ")).strip()
                
                try:
                    if choice.lower() == "a":
                        await self.menu_bluetooth_on()
                    elif choice.lower() == "b":
                        await self.menu_bluetooth_off()
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
                        await self.menu_discover_services()
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
                        await self.menu_pair()
                    elif choice == "10":
                        await self.menu_unpair()
                    elif choice == "11":
                        await self.menu_disconnect()
                    elif choice == "12":
                        await self.menu_burst_write()
                    elif choice == "13":
                        await self.menu_burst_write_without_response()
                    elif choice == "14":
                        await self.menu_stop_burst_write()
                    elif choice == "15":
                        await self.menu_burst_read()
                    elif choice == "16":
                        await self.menu_stop_burst_read()
                    elif choice == "17":
                        await self.menu_start_csv_logging()
                    elif choice == "18":
                        await self.menu_stop_csv_logging()
                    elif choice == "0":
                        print("\nExiting...")
                        break
                    else:
                        print("Invalid option\n")
                        
                except KeyboardInterrupt:
                    print("\n\nCancelled")
                except Exception as e:
                    logger.error(f"Error: {e}\n")
        finally:
            await self._close_scan_device()


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Bumble BLE Testing Framework")
    parser.add_argument(
        "--transport",
        default="tcp-client:127.0.0.1:9001",
        help="HCI transport specification",
    )
    parser.add_argument(
        "-v", "--verbose",
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
