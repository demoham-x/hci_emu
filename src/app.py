#!/usr/bin/env python3
"""
Bumble BLE Testing - Application logic layer.
"""
"""
~~~~NOT USED~~~~

This module needs to be developed for wrapper to bumble to be used for scripts and interactive menu.
The idea is to have a single app class that manages the BLE operations, state, and user interactions,
while the main script can be a simple entry point that creates the app instance and runs the menu loop.
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


class BLETestingApp:
    """Application layer containing BLE operation logic."""
    
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
        self._scan_adv_handler = None
        self.filter_name = None
        self.filter_address = None
        self._suppress_adv_printing = False  # Flag to suppress adv printing during connection
        self._ui_config_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "configs", "ui_config.json")
        )
        
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
        self.snoop_console_logging = False
        self.snoop_auto_enable = False
        self.snoop_ellisys_enabled = True
        self.snoop_file_enabled = True
        self._connect_in_progress = False
        self._connect_target_address = None
        self._post_connect_task = None
        self._connect_auto_encrypt_if_bonded = self.connector.get_smp_config().get(
            "auto_encrypt_if_bonded", True
        )
        self._security_request_task = None
        self._pairing_task = None
        self._pairing_in_progress = False
        self._load_ui_config()
        self._configure_debug_logging(self.debug_mode, persist=False)

    def _load_ui_config(self):
        """Load UI/runtime configuration from disk."""
        if not os.path.exists(self._ui_config_path):
            return

        try:
            with open(self._ui_config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)

            if not isinstance(config, dict):
                return

            self.filter_name = config.get("filter_name") or None
            self.filter_address = config.get("filter_address") or None

            debug_mode = config.get("debug_mode")
            if debug_mode in {"none", "console", "file", "both"}:
                self.debug_mode = debug_mode

            hci_snoop = config.get("hci_snoop", {})
            if isinstance(hci_snoop, dict):
                if isinstance(hci_snoop.get("ellisys_host"), str):
                    self.ellisys_host = hci_snoop["ellisys_host"]

                try:
                    port_value = int(hci_snoop.get("ellisys_port", self.ellisys_port))
                    if 0 <= port_value <= 65535:
                        self.ellisys_port = port_value
                except (TypeError, ValueError):
                    pass

                if isinstance(hci_snoop.get("btsnoop_filename"), str):
                    self.btsnoop_filename = hci_snoop["btsnoop_filename"]

                stream = hci_snoop.get("ellisys_stream")
                if stream in {"primary", "secondary", "tertiary"}:
                    self.ellisys_stream = stream

                self.snoop_console_logging = bool(
                    hci_snoop.get("snoop_console_logging", self.snoop_console_logging)
                )
                self.snoop_auto_enable = bool(
                    hci_snoop.get("enabled", self.snoop_auto_enable)
                )
                self.snoop_ellisys_enabled = bool(
                    hci_snoop.get("enable_ellisys", self.snoop_ellisys_enabled)
                )
                self.snoop_file_enabled = bool(
                    hci_snoop.get("enable_file", self.snoop_file_enabled)
                )
        except Exception as e:
            logger.debug(f"UI config load skipped: {e}")

    def _save_ui_config(self):
        """Persist UI/runtime configuration to disk."""
        try:
            os.makedirs(os.path.dirname(self._ui_config_path), exist_ok=True)
            config = {
                "filter_name": self.filter_name,
                "filter_address": self.filter_address,
                "debug_mode": self.debug_mode,
                "hci_snoop": {
                    "enabled": self.snoop_auto_enable,
                    "enable_ellisys": self.snoop_ellisys_enabled,
                    "enable_file": self.snoop_file_enabled,
                    "ellisys_host": self.ellisys_host,
                    "ellisys_port": self.ellisys_port,
                    "btsnoop_filename": self.btsnoop_filename,
                    "ellisys_stream": self.ellisys_stream,
                    "snoop_console_logging": self.snoop_console_logging,
                },
            }
            with open(self._ui_config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
                handle.write("\n")
        except Exception as e:
            logger.debug(f"UI config save skipped: {e}")

    def _event_names_from_emitter(self, emitter):
        """Return all EVENT_* string constants defined on an emitter class."""
        event_names = set()
        for attr_name in dir(type(emitter)):
            if not attr_name.startswith("EVENT_"):
                continue
            attr_value = getattr(type(emitter), attr_name, None)
            if isinstance(attr_value, str):
                event_names.add(attr_value)
        return sorted(event_names)

    def _register_device_events(self, device):
        """Register all device-level events in one place."""

        def on_connection(connection):
            self.connector.connected_device = connection
            self.connected = True
            self.current_device = str(connection.peer_address)
            logger.info(f"[CONNECTION] Successfully established to {connection.peer_address}")
            print(f"\n[CONNECTION] Established to {connection.peer_address}")
            if self._connect_in_progress:
                self._post_connect_task = asyncio.create_task(
                    self._handle_connection_ready(connection)
                )

        def on_connection_failure(error):
            self.connected = False
            self.current_device = None
            self.connector.connected_device = None
            self._connect_in_progress = False
            self._connect_target_address = None
            logger.error(f"[CONNECTION FAILED] Error: {error}")
            print(f"\n[CONNECTION FAILED] {error}")

        custom_handlers = {
            "connection": on_connection,
            "connection_failure": on_connection_failure,
        }

        for event_name in self._event_names_from_emitter(device):
            if event_name in custom_handlers:
                device.on(event_name, custom_handlers[event_name])
                continue

            def on_event(*args, _event=event_name):
                logger.debug(f"[DEVICE EVENT] {_event}: {args!r}")

            device.on(event_name, on_event)

    def _register_connection_events(self, connection):
        """Register all connection-level events in one place."""

        def on_disconnection(reason):
            logger.info(f"[DISCONNECTION] Remote device disconnected, reason: {reason}")
            print(f"\n[DISCONNECTION] Remote device disconnected (reason: {reason})")
            self.connected = False
            self.current_device = None
            self.connector.connected_device = None

        custom_handlers = {
            "disconnection": on_disconnection,
            "connection_encryption_change": self._on_connection_encryption_change,
            "connection_encryption_failure": self._on_connection_encryption_failure,
            "connection_encryption_key_refresh": self._on_connection_encryption_key_refresh,
            "connection_parameters_update": self._on_connection_parameters_update,
            "pairing_start": self._on_pairing_start,
            "pairing": self._on_pairing_complete,
            "pairing_failure": self._on_pairing_failure,
            "security_request": self._on_security_request,
        }

        for event_name in self._event_names_from_emitter(connection):
            if event_name in custom_handlers:
                connection.on(event_name, custom_handlers[event_name])
                continue

            def on_event(*args, _event=event_name):
                logger.debug(f"[CONNECTION EVENT] {_event}: {args!r}")

            connection.on(event_name, on_event)

    def _on_pairing_start(self, *args):
        """Handle LE pairing_start event."""
        self._pairing_in_progress = True
        logger.info(f"[PAIRING EVENT] pairing_start: {args!r}")
        print("[PAIRING] Started")

    def _on_connection_encryption_change(self, *args):
        """Handle LE connection_encryption_change event."""
        logger.info(f"[SECURITY EVENT] connection_encryption_change: {args!r}")
        print("[SECURITY] Encryption state changed")

    def _on_connection_encryption_failure(self, *args):
        """Handle LE connection_encryption_failure event."""
        logger.warning(f"[SECURITY EVENT] connection_encryption_failure: {args!r}")
        print("[SECURITY] Encryption failed")

    def _on_connection_encryption_key_refresh(self, *args):
        """Handle LE connection_encryption_key_refresh event."""
        logger.info(f"[SECURITY EVENT] connection_encryption_key_refresh: {args!r}")
        print("[SECURITY] Encryption key refreshed")

    def _on_connection_parameters_update(self, *args):
        """Handle LE connection_parameters_update event."""
        logger.info(f"[CONNECTION EVENT] connection_parameters_update: {args!r}")
        print("[CONNECTION] Parameters updated")

    def _on_pairing_complete(self, *args):
        """Handle LE pairing completion event."""
        self._pairing_in_progress = False
        logger.info(f"[PAIRING EVENT] pairing: {args!r}")
        print("[PAIRING] Completed")

    def _on_pairing_failure(self, *args):
        """Handle LE pairing failure event."""
        self._pairing_in_progress = False
        logger.warning(f"[PAIRING EVENT] pairing_failure: {args!r}")
        print("[PAIRING] Failed")

    def _start_pairing_non_blocking(self, connection, source: str):
        """Start pairing without blocking; completion is tracked by LE events."""
        if self._pairing_in_progress:
            logger.info(f"[PAIRING] Pairing already in progress, source={source}")
            return

        if self._pairing_task and not self._pairing_task.done():
            logger.info(f"[PAIRING] Pairing task already running, source={source}")
            return

        if not self._scan_device:
            logger.warning("[PAIRING] Cannot start pairing: scan device is not ready")
            return

        logger.info(f"[PAIRING] Starting non-blocking pairing from {source}")
        self._pairing_in_progress = True
        self._pairing_task = asyncio.create_task(self._scan_device.pair(connection))

        def _on_done(task):
            try:
                task.result()
            except Exception as e:
                self._pairing_in_progress = False
                logger.warning(f"[PAIRING] Pairing task ended with error: {e}")

        self._pairing_task.add_done_callback(_on_done)

    def _on_security_request(self, auth_req: int):
        """Handle SMP security request from peer - always honor peer requests."""
        logger.info(f"[SECURITY REQUEST] auth_req=0x{auth_req:02X}")
        print(f"\n[SECURITY REQUEST] Peer requested security (auth_req=0x{auth_req:02X})")

        if self._security_request_task and not self._security_request_task.done():
            logger.debug("Security request handling already in progress")
            return

        self._security_request_task = asyncio.create_task(
            self._handle_security_request_async()
        )

    async def _handle_security_request_async(self):
        """Auto pair or encrypt in response to peer security request."""
        connection = self.connector.connected_device
        if not connection:
            return

        try:
            address = self.current_device or str(connection.peer_address)
            is_bonded = self.connector.is_device_bonded(address)

            if is_bonded:
                logger.info("[SECURITY REQUEST] Device bonded, establishing encryption")
                print("[SECURITY REQUEST] Device bonded, establishing encryption...")
                success = await asyncio.wait_for(self.connector.establish_security(), timeout=15.0)
                if success:
                    print("[SECURITY REQUEST] Encryption established")
                else:
                    print("[SECURITY REQUEST] Could not establish encryption")
            else:
                logger.info("[SECURITY REQUEST] Device not bonded, starting pairing")
                print("[SECURITY REQUEST] Device not bonded, initiating pairing...")
                self._start_pairing_non_blocking(connection, source="security_request")
        except Exception as e:
            logger.warning(f"[SECURITY REQUEST] Auto security handling failed: {e}")
            print(f"[SECURITY REQUEST] Auto security handling failed: {e}")

    async def _cancel_connect_on_timeout(self, device, address: str, connect_task):
        """Cancel a pending connect task and issue HCI cancel when timer expires."""
        if connect_task.done():
            return

        logger.error(f"Connection timeout to {address}")
        connect_task.cancel()
        try:
            from bumble.hci import HCI_LE_Create_Connection_Cancel_Command

            await device.send_command(HCI_LE_Create_Connection_Cancel_Command())
            logger.info("Sent HCI_LE_Create_Connection_Cancel to device")
        except Exception as e:
            logger.debug(f"Could not cancel HCI connection: {e}")

        self._connect_in_progress = False
        self._connect_target_address = None
        self._suppress_adv_printing = False
        print("✗ Connection timeout - device not responding after timeout")
        print("  - Is device powered on and in range?")
        print("  - Try scanning again (option 1)\n")

    async def _handle_connection_ready(self, connection):
        """Handle post-connection setup from event callback."""
        address = self._connect_target_address or str(connection.peer_address)
        auto_pair_on_security_request = self.connector.get_smp_config().get(
            "auto_pair_encrypt_on_security_request", True
        )
        auto_encrypt_if_bonded = self._connect_auto_encrypt_if_bonded
        self.connector.device = self._scan_device
        self._register_connection_events(connection)

        print(f"✓ Successfully connected to {address}")

        is_bonded = self.connector.is_device_bonded(address)

        if auto_pair_on_security_request and not is_bonded:
            print("\n[SECURITY] Device is not bonded.")
            print("[SECURITY] Waiting for peer security request to initiate pairing...\n")
            print("[SECURITY] You can also initiate pairing manually from menu Option 9 (Pair / Encrypt Connection).\n")
            logger.info("[APP] Waiting for peer security request before starting pairing")
        elif not auto_pair_on_security_request and not is_bonded:
            print("\n[INFO] Auto-pairing is disabled. Device not bonded.\n")
            logger.info("[APP] Auto-pairing disabled, skipping pairing")
        elif is_bonded:
            print("✓ Device is already bonded - no pairing needed\n")
            if auto_encrypt_if_bonded:
                print("[SECURITY] Bonded device detected. Establishing encryption...")
                try:
                    encrypted = await asyncio.wait_for(
                        self.connector.establish_security(),
                        timeout=15.0,
                    )
                    if encrypted:
                        print("[SECURITY] Encryption established\n")
                    else:
                        print("[SECURITY] Could not establish encryption automatically\n")
                except asyncio.TimeoutError:
                    print("[SECURITY] Encryption attempt timed out\n")
                except Exception as e:
                    logger.warning(f"[SECURITY] Auto encryption failed: {e}")
                    print(f"[SECURITY] Auto encryption failed: {e}\n")
            else:
                print("[SECURITY] Auto encryption for bonded devices is disabled\n")

        print("Connection ready.\n")
        print("Next steps:")
        print("  - Option 9: Encrypt connection (if bonded)")
        print("  - Option 3: Discover GATT Services")
        print("  - Option 11: Disconnect\n")

        self._connect_in_progress = False
        self._connect_target_address = None
        self._connect_auto_encrypt_if_bonded = self.connector.get_smp_config().get(
            "auto_encrypt_if_bonded", True
        )

    async def connect(self, address: str, timeout: float = 30.0, auto_encrypt_if_bonded: Optional[bool] = None):
        """Reusable connect wrapper for both scripts and menu UI.

        Args:
            address: Peer BLE address, for example "AA:BB:CC:DD:EE:FF".
            timeout: Connection timeout in seconds. Typical values are 10-60.
            auto_encrypt_if_bonded: If True, automatically establish encryption when
                peer is already bonded. If None, uses SMP config value
                auto_encrypt_if_bonded.
        """
        from bumble.hci import Address

        await self._auto_enable_hci_snoop_on_startup()

        address = format_address(address)
        print(f"\nConnecting to {address}...")
        print("(This may take a few seconds... press Ctrl+C to cancel)\n")

        try:
            if self._scan_device is None:
                print("✗ Device not initialized. Run Bluetooth On first.\n")
                await self._get_scan_device()

            if getattr(self._scan_device, "scanning", False):
                await self._scan_device.stop_scanning()
                await asyncio.sleep(1)

            self._connect_in_progress = True
            self._connect_target_address = address
            self._post_connect_task = None
            if auto_encrypt_if_bonded is None:
                auto_encrypt_if_bonded = self.connector.get_smp_config().get(
                    "auto_encrypt_if_bonded", True
                )
            self._connect_auto_encrypt_if_bonded = auto_encrypt_if_bonded

            self._suppress_adv_printing = True
            connect_task = asyncio.create_task(self._scan_device.connect(Address(address)))
            loop = asyncio.get_running_loop()
            timeout_handle = loop.call_later(
                timeout,
                lambda: asyncio.create_task(
                    self._cancel_connect_on_timeout(self._scan_device, address, connect_task)
                ),
            )

            try:
                self.connector.connected_device = await connect_task
            except asyncio.CancelledError:
                return
            finally:
                timeout_handle.cancel()
                self._suppress_adv_printing = False

            if self._post_connect_task:
                await self._post_connect_task
        except Exception as e:
            self._connect_in_progress = False
            self._connect_target_address = None
            self._connect_auto_encrypt_if_bonded = self.connector.get_smp_config().get(
                "auto_encrypt_if_bonded", True
            )
            self._suppress_adv_printing = False
            logger.error(f"Connection failed: {e}", exc_info=True)
            print(f"✗ Connection error: {e}")
            print("  - Is device powered on and in range?")
            print("  - Try scanning again (option 1)\n")
        
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

    def print_bonded_devices(self, bonded=None, title: str = "Bonded Devices"):
        """Print bonded devices with Rich table when available.

        Args:
            bonded: Optional mapping of bonded addresses. If None, reads from connector.
            title: Optional title for rendered output.

        Returns:
            List of bonded addresses in displayed order.
        """
        if bonded is None:
            bonded = self.connector.get_bonded_devices() or {}

        addresses = list(bonded.keys())
        if not addresses:
            print("No bonded devices found.\n")
            return addresses

        if HAS_RICH and console:
            table = Table(title=title, show_header=True, header_style="bold magenta")
            table.add_column("#", style="cyan", width=4)
            table.add_column("Address", style="green", width=20)
            for idx, addr in enumerate(addresses, 1):
                table.add_row(str(idx), addr)
            console.print(table)
            print()
        else:
            print(f"{title}:")
            for idx, addr in enumerate(addresses, 1):
                print(f"{idx}. {addr}")
            print()

        return addresses

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

    async def app_set_filters(
        self,
        clear: bool = False,
        name_filter: Optional[str] = None,
        address_filter: Optional[str] = None,
    ):
        """Set device filters for scanning without interactive prompts.

        Args:
            clear: True clears both filters.
            name_filter: Case-insensitive substring to match advertised local name.
            address_filter: Case-insensitive substring to match advertiser address.
        """
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
        
        if clear:
            self.filter_name = None
            self.filter_address = None
            self._save_ui_config()
            print("✓ Filters cleared\n")
            return

        if not name_filter and not address_filter:
            print("No filters set\n")
            return

        self.filter_name = name_filter if name_filter else None
        self.filter_address = address_filter if address_filter else None
        self._save_ui_config()
        
        print()
        print("✓ Filters updated:")
        if self.filter_name:
            print(f"  - Name contains: '{self.filter_name}'")
        if self.filter_address:
            print(f"  - Address contains: '{self.filter_address}'")
        if self.filter_name and self.filter_address:
            print("  (Both filters must match)")
        print()

    async def app_toggle_hci_snoop(
        self,
        enable: Optional[bool] = None,
        ellisys_host: Optional[str] = None,
        ellisys_port: Optional[int] = None,
        ellisys_stream: Optional[str] = None,
        btsnoop_filename: Optional[str] = None,
        enable_ellisys: Optional[bool] = None,
        enable_file: Optional[bool] = None,
        enable_console: Optional[bool] = None,
    ):
        """Enable/disable HCI snoop logging without interactive prompts.

        Args:
            enable: True to enable snoop, False to disable snoop.
            ellisys_host: Ellisys UDP destination host.
            ellisys_port: Ellisys UDP destination port (0-65535).
            ellisys_stream: One of "primary", "secondary", "tertiary".
            btsnoop_filename: Capture file path, usually ending with .log or .btsnoop.
            enable_ellisys: Enable/disable UDP output.
            enable_file: Enable/disable file output.
            enable_console: Enable/disable console packet logging.
        """
        print_section("HCI Snoop Logging")

        if enable is None:
            print("Provide enable=True or enable=False to change snoop state.\n")
            return

        if self.snoop_enabled:
            print("HCI Snoop Logging is currently: ON\n")
            print(f"  Ellisys UDP: {self.ellisys_host}:{self.ellisys_port}")
            print(f"  Stream: {self.ellisys_stream.upper()}")
            print(f"  Capture file: {self.btsnoop_filename}\n")

            if not enable:
                await self._disable_hci_snoop()
                print("\n✓ HCI snoop logging disabled\n")
            else:
                print("HCI snoop logging is already enabled.\n")
        else:
            print("HCI Snoop Logging is currently: OFF\n")

            if ellisys_host:
                self.ellisys_host = ellisys_host
            if ellisys_port is not None:
                try:
                    port_value = int(ellisys_port)
                    if 0 <= port_value <= 65535:
                        self.ellisys_port = port_value
                    else:
                        print("Invalid port, keeping previous value")
                except (TypeError, ValueError):
                    print("Invalid port, keeping previous value")

            if ellisys_stream in {"primary", "secondary", "tertiary"}:
                self.ellisys_stream = ellisys_stream

            if btsnoop_filename:
                self.btsnoop_filename = btsnoop_filename
            elif not self.btsnoop_filename.endswith((".log", ".btsnoop")):
                self.btsnoop_filename = "logs/hci_capture.log"

            if enable_ellisys is not None:
                self.snoop_ellisys_enabled = bool(enable_ellisys)

            if enable_file is not None:
                self.snoop_file_enabled = bool(enable_file)

            if not self.snoop_ellisys_enabled and not self.snoop_file_enabled:
                print("\n✗ At least one output must be enabled (Ellisys UDP or capture file).\n")
                return

            if enable_console is not None:
                self.snoop_console_logging = bool(enable_console)

            enable_console_output = self.snoop_console_logging

            self._save_ui_config()

            if enable:
                await self._enable_hci_snoop(enable_console_output)
                if self.snoop_enabled:
                    print("\n✓ HCI snoop logging enabled\n")
                    print("Packets will be sent to:")
                    if self.snoop_ellisys_enabled:
                        print(f"  - Ellisys Analyzer (UDP {self.ellisys_host}:{self.ellisys_port} - {self.ellisys_stream.upper()} stream)")
                    if self.snoop_file_enabled:
                        print(f"  - Capture file ({self.btsnoop_filename})")
                        print(f"    Format: BTSnoop (compatible with Ellisys, Wireshark, etc.)")
                    if enable_console_output:
                        print("  - Console output")
                    print()
            else:
                print("\n✗ HCI snoop logging not enabled\n")

    async def _auto_enable_hci_snoop_on_startup(self):
        """Enable HCI snoop automatically if configured in UI settings."""
        if not self.snoop_auto_enable or self.snoop_enabled:
            return

        print("[HCI SNOOP] Auto-enable from config is ON. Starting...")
        await self._enable_hci_snoop(self.snoop_console_logging)
        if self.snoop_enabled:
            print(
                f"[HCI SNOOP] Auto-enabled: UDP {self.ellisys_host}:{self.ellisys_port} ({self.ellisys_stream.upper()})"
            )
        else:
            print("[HCI SNOOP] Auto-enable failed. Review logs and configuration.")
    
    async def _enable_hci_snoop(self, enable_console: bool = False):
        """Enable HCI snoop logging"""
        try:
            self.snoop_console_logging = enable_console
            # Create snooper
            self.hci_snooper = HCISnooper(
                ellisys_host=self.ellisys_host,
                ellisys_port=self.ellisys_port,
                btsnoop_file=self.btsnoop_filename if self.snoop_file_enabled else None,
                enable_ellisys=self.snoop_ellisys_enabled,
                enable_console=enable_console,
                stream=self.ellisys_stream
            )
            
            # Start snooper
            started = await self.hci_snooper.start()
            if not started:
                raise RuntimeError("HCI snooper failed to start")

            self.snoop_enabled = True
            self.snoop_auto_enable = True
            
            # If scan device exists, we need to restart it with wrapped transport
            if self._scan_device:
                print("[INFO] Restarting Bluetooth to apply HCI snoop...")
                await self._close_scan_device()
            
            logger.info("HCI snoop logging enabled")
            self._save_ui_config()
            
        except Exception as e:
            logger.error(f"Failed to enable HCI snoop: {e}")
            print(f"✗ Failed to enable HCI snoop: {e}")
            self.snoop_enabled = False
            self.snoop_auto_enable = False
            self.hci_snooper = None
    
    async def _disable_hci_snoop(self):
        """Disable HCI snoop logging"""
        try:
            if self.hci_snooper:
                await self.hci_snooper.stop()
                self.hci_snooper = None
            
            self.snoop_enabled = False
            self.snoop_auto_enable = False
            
            # If scan device exists, restart it without wrapper
            if self._scan_device:
                print("[INFO] Restarting Bluetooth to remove HCI snoop...")
                await self._close_scan_device()
            
            logger.info("HCI snoop logging disabled")
            self._save_ui_config()
            
        except Exception as e:
            logger.error(f"Failed to disable HCI snoop: {e}")
            print(f"✗ Failed to disable HCI snoop: {e}")

    async def app_debug_logging(self, mode: str):
        """Configure debug logging level without interactive prompts.

        Args:
            mode: One of "none", "console", "file", "both".
        """
        print_section("Debug Logging Configuration")
        print(f"Current debug logging mode: {self.debug_mode.upper()}\n")

        if mode == "console":
            self._configure_debug_logging("console")
            print("\n✓ Debug logging enabled: Console only\n")
        elif mode == "file":
            self._configure_debug_logging("file")
            print("\n✓ Debug logging enabled: File only (logs/debug.log)\n")
        elif mode == "both":
            self._configure_debug_logging("both")
            print("\n✓ Debug logging enabled: Console AND File (logs/debug.log)\n")
        elif mode == "none":
            self._configure_debug_logging("none")
            print("\n✓ Debug logging disabled (required prints only)\n")
        else:
            print("\n✗ Invalid debug mode. Use: none, console, file, both\n")
    
    def _configure_debug_logging(self, mode: str, persist: bool = True):
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

        if persist:
            self._save_ui_config()

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

        self._register_device_events(self._scan_device)
        
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

            # Always start a scan with a fresh device list (no stale entries).
            self.discovered_devices = {}

            device = await self._get_scan_device()
            
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

            # Remove any stale scan callback before registering a fresh one.
            if self._scan_adv_handler is not None:
                try:
                    device.remove_listener('advertisement', self._scan_adv_handler)
                except Exception:
                    pass
                self._scan_adv_handler = None

            device.on('advertisement', on_advertisement)
            self._scan_adv_handler = on_advertisement

            try:
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
            finally:
                # Stop active scan and always detach this scan callback.
                try:
                    await device.stop_scanning()
                except Exception:
                    pass
                if self._scan_adv_handler is not None:
                    try:
                        device.remove_listener('advertisement', self._scan_adv_handler)
                    except Exception:
                        pass
                    self._scan_adv_handler = None
            
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
    
    async def app_scan_devices(
        self,
        duration: int = 10,
        filter_duplicates: bool = True,
        active_scan: bool = True,
    ):
        """Scan for devices without interactive prompts.

        Args:
            duration: Scan duration in seconds.
            filter_duplicates: True to suppress repeated advertising reports.
            active_scan: True for active scan (requests scan response), False for passive.
        """
        print_section("Scanning for BLE Devices")

        try:
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

    async def app_bluetooth_on(self):
        """Power on Bluetooth controller"""
        print_section("Bluetooth On")
        try:
            await self._get_scan_device()
            print("✓ Bluetooth is ON\n")

            # Show bonding status using shared renderer.
            bonded = self.connector.get_bonded_devices() or {}
            print(f"📱 Bonded devices: {len(bonded)}")
            if bonded:
                self.print_bonded_devices(bonded, title="Bonded Devices")
            else:
                print()
        except Exception as e:
            logger.error(f"Bluetooth on error: {e}")
            print(f"✗ Failed to power on Bluetooth: {e}\n")

    async def app_bluetooth_off(self):
        """Power off Bluetooth controller"""
        print_section("Bluetooth Off")
        try:
            await self._close_scan_device()
            print("✓ Bluetooth is OFF\n")
        except Exception as e:
            logger.error(f"Bluetooth off error: {e}")
            print(f"✗ Failed to power off Bluetooth: {e}\n")
    
    async def app_discover_services(self):
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

    async def _maybe_show_discovery_table(self, operation: str = "read", show_table: bool = False):
        """Optionally show characteristics table for the operation."""
        if show_table:
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
        """Print read result in the same format as app_read_characteristic."""
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
    
    async def app_read_characteristic(self, handle: str, show_table: bool = False):
        """Read a characteristic without interactive prompts.

        Args:
            handle: Attribute handle as decimal string ("84") or hex string ("0x0054").
            show_table: True to print supported characteristic table before operation.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Read Characteristic")
        
        try:
            await self._maybe_show_discovery_table("read", show_table=show_table)
            handle = self._parse_handle(handle)
            
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
    
    async def app_write_characteristic(self, handle: str, hex_value: str, show_table: bool = False):
        """Write to characteristic without interactive prompts.

        Args:
            handle: Attribute handle as decimal string ("84") or hex string ("0x0054").
            hex_value: Hex payload, spaced or unspaced, for example "0102A0" or "01 02 A0".
            show_table: True to print supported characteristic table before operation.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Write Characteristic")
        
        try:
            await self._maybe_show_discovery_table("write", show_table=show_table)
            handle = self._parse_handle(handle)
            
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
            print(f"✗ Burst read failed: {e}\n")
    
    async def app_write_without_response(self, handle: str, hex_value: str, show_table: bool = False):
        """Write without response without interactive prompts.

        Args:
            handle: Attribute handle as decimal string ("84") or hex string ("0x0054").
            hex_value: Hex payload, spaced or unspaced.
            show_table: True to print supported characteristic table before operation.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Write Without Response")
        
        try:
            await self._maybe_show_discovery_table("write_without_response", show_table=show_table)
            handle = self._parse_handle(handle)
            
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
    
    async def app_subscribe(self, handle: str, show_table: bool = False):
        """Subscribe to notifications without interactive prompts.

        Args:
            handle: Characteristic handle as decimal or hex string.
            show_table: True to print notifiable characteristic table before subscribe.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Subscribe to Notifications")
        
        try:
            await self._maybe_show_discovery_table("notify", show_table=show_table)
            handle = self._parse_handle(handle)
            
            if await self.connector.subscribe_notifications(handle):
                print(f"\n✓ Subscribed to notifications on handle 0x{handle:04X} ({handle})")
                print("Notifications will be printed when received.\n")
            else:
                print(f"\n✗ Failed to subscribe to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError:
            print("Invalid handle\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")
    
    async def app_subscribe_indications(self, handle: str, show_table: bool = False):
        """Subscribe to indications without interactive prompts.

        Args:
            handle: Characteristic handle as decimal or hex string.
            show_table: True to print indicatable characteristic table before subscribe.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return
        
        print_section("Subscribe to Indications")
        
        try:
            await self._maybe_show_discovery_table("indicate", show_table=show_table)
            handle = self._parse_handle(handle)
            
            if await self.connector.subscribe_indications(handle):
                print(f"\n✓ Subscribed to indications on handle 0x{handle:04X} ({handle})")
                print("Indications will be printed when received.\n")
            else:
                print(f"\n✗ Failed to subscribe to handle 0x{handle:04X} ({handle})\n")
                
        except ValueError:
            print("Invalid handle\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def app_burst_write(
        self,
        handle: str,
        hex_value: str,
        count: int = 0,
        interval_ms: int = 100,
        show_table: bool = False,
    ):
        """Burst write with response without interactive prompts.

        Args:
            handle: Characteristic handle as decimal or hex string.
            hex_value: Hex payload for each write.
            count: Number of writes. Use 0 for infinite until stopped.
            interval_ms: Delay between writes in milliseconds.
            show_table: True to print writable characteristic table before start.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Write (With Response)")

        try:
            await self._maybe_show_discovery_table("burst_write", show_table=show_table)
            handle = self._parse_handle(handle)
            hex_value = hex_value.replace(" ", "")
            value = bytes.fromhex(hex_value)

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

    async def app_burst_write_without_response(
        self,
        handle: str,
        hex_value: str,
        count: int = 0,
        interval_ms: int = 100,
        show_table: bool = False,
    ):
        """Burst write without response without interactive prompts.

        Args:
            handle: Characteristic handle as decimal or hex string.
            hex_value: Hex payload for each write.
            count: Number of writes. Use 0 for infinite until stopped.
            interval_ms: Delay between writes in milliseconds.
            show_table: True to print writable characteristic table before start.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Write (Without Response)")

        try:
            await self._maybe_show_discovery_table("burst_write", show_table=show_table)
            handle = self._parse_handle(handle)
            hex_value = hex_value.replace(" ", "")
            value = bytes.fromhex(hex_value)

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

    async def app_stop_burst_write(self):
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

    async def app_burst_read(
        self,
        handle: str,
        count: int = 0,
        interval_ms: int = 100,
        print_each_read: bool = False,
        show_table: bool = False,
    ):
        """Burst read without interactive prompts.

        Args:
            handle: Characteristic handle as decimal or hex string.
            count: Number of reads. Use 0 for infinite until stopped.
            interval_ms: Delay between reads in milliseconds.
            print_each_read: True to print each read payload as it arrives.
            show_table: True to print readable characteristic table before start.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Burst Read")

        try:
            await self._maybe_show_discovery_table("burst_read", show_table=show_table)
            handle = self._parse_handle(handle)

            def _burst_read_printer(burst_handle: int, value: bytes, read_count: int):
                title = f"Burst Read #{read_count} - Handle 0x{burst_handle:04X}"
                self._print_read_value(burst_handle, value, title=title)

            callback = _burst_read_printer if print_each_read else None

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

    async def app_stop_burst_read(self):
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

    async def app_start_csv_logging(self, filename: Optional[str] = None):
        """Start CSV logging without interactive prompts.

        Args:
            filename: Optional output file path. If None, default timestamp naming is used.
        """
        if not self.connected:
            print("✗ Not connected to any device\n")
            return

        print_section("Start CSV Logging")

        try:
            filename = filename if filename else None
            if self.connector.start_csv_logging(filename):
                print("CSV logging started.\n")
            else:
                print("CSV logging is already active or failed to start.\n")
        except Exception as e:
            logger.error(f"Error: {e}\n")

    async def app_stop_csv_logging(self):
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

    async def app_smp_settings(self):
        """Display current SMP configuration (non-interactive)."""
        print_section("SMP (Secure Manager Protocol) Settings")

        config = self.connector.get_smp_config()

        print("Current Configuration:")
        print(f"  IO Capability: {config['io_capability']}")
        print(f"  MITM Required: {'YES' if config['mitm_required'] else 'NO'}")
        print(f"  LE Secure Connections: {'ENABLED' if config['le_secure_connections'] else 'DISABLED'}")
        print(f"  Encryption Key Size: {config['min_enc_key_size']}-{config['max_enc_key_size']} bytes")
        print(f"  Bonding: {'ENABLED' if config['bonding_enabled'] else 'DISABLED'}")
        print(
            "  Auto Pair/Encrypt on Security Request: "
            f"{'ENABLED' if config.get('auto_pair_encrypt_on_security_request', True) else 'DISABLED'}"
        )
        print(
            "  Auto Encrypt If Bonded: "
            f"{'ENABLED' if config.get('auto_encrypt_if_bonded', True) else 'DISABLED'}"
        )
        print()

    async def app_smp_auto_pair_encrypt(self, enabled: bool):
        """Toggle auto pair/encrypt behavior and persist to SMP config.

        Args:
            enabled: True enables auto pair/encrypt on security request, False disables.
        """
        print_section("Auto Pair/Encrypt on Security Request")

        current = self.connector.get_smp_config().get(
            "auto_pair_encrypt_on_security_request", True
        )
        print(f"Current: {'ENABLED' if current else 'DISABLED'}")

        if enabled:
            self.connector.set_smp_auto_pair_encrypt_on_security_request(True)
            print("✓ Auto pair/encrypt enabled\n")
        else:
            self.connector.set_smp_auto_pair_encrypt_on_security_request(False)
            print("✓ Auto pair/encrypt disabled\n")

    async def app_smp_auto_encrypt_if_bonded(self, enabled: bool):
        """Toggle automatic encryption for bonded devices on connect.

        Args:
            enabled: True enables automatic encryption for bonded peers.
        """
        print_section("Auto Encrypt If Bonded")

        current = self.connector.get_smp_config().get("auto_encrypt_if_bonded", True)
        print(f"Current: {'ENABLED' if current else 'DISABLED'}")

        self.connector.set_smp_auto_encrypt_if_bonded(bool(enabled))
        self._connect_auto_encrypt_if_bonded = bool(enabled)
        if enabled:
            print("✓ Auto encrypt if bonded enabled\n")
        else:
            print("✓ Auto encrypt if bonded disabled\n")

    async def app_smp_io_capability(self, io_capability: str):
        """Configure SMP IO Capability without interactive prompts.

        Args:
            io_capability: One of DISPLAY_ONLY, KEYBOARD_ONLY, NO_INPUT_NO_OUTPUT,
                KEYBOARD_DISPLAY, DISPLAY_OUTPUT_AND_KEYBOARD_INPUT.
        """
        print_section("IO Capability Configuration")

        current = self.connector.get_smp_config()['io_capability']
        print(f"Current: {current}\n")
        if self.connector.set_smp_io_capability(io_capability):
            print(f"✓ IO Capability set to: {io_capability}\n")
        else:
            print("✗ Failed to set IO capability\n")

    async def app_smp_mitm_required(self, required: bool):
        """Configure MITM Protection Requirement without interactive prompts.

        Args:
            required: True to require MITM, False to allow non-MITM pairing.
        """
        print_section("MITM Protection Configuration")

        current = self.connector.get_smp_config()['mitm_required']
        print(f"Current: {'YES (REQUIRED)' if current else 'NO (NOT REQUIRED)'}\n")
        if required:
            self.connector.set_smp_mitm_required(True)
            print("✓ MITM Protection: ENABLED\n")
        else:
            self.connector.set_smp_mitm_required(False)
            print("✓ MITM Protection: DISABLED\n")

    async def app_smp_secure_connections(self, enabled: bool):
        """Configure LE Secure Connections without interactive prompts.

        Args:
            enabled: True enables LE Secure Connections, False uses legacy mode.
        """
        print_section("LE Secure Connections Configuration")

        current = self.connector.get_smp_config()['le_secure_connections']
        print(f"Current: {'ENABLED' if current else 'DISABLED'}\n")
        if enabled:
            self.connector.set_smp_secure_connections(True)
            print("✓ LE Secure Connections: ENABLED\n")
        else:
            self.connector.set_smp_secure_connections(False)
            print("✓ LE Secure Connections: DISABLED\n")

    async def app_smp_encryption_key_size(self, min_size: int = 7, max_size: int = 16):
        """Configure Encryption Key Size without interactive prompts.

        Args:
            min_size: Minimum key size in bytes, valid range 7-16.
            max_size: Maximum key size in bytes, valid range 7-16, must be >= min_size.
        """
        print_section("Encryption Key Size Configuration")

        config = self.connector.get_smp_config()
        current_min = config['min_enc_key_size']
        current_max = config['max_enc_key_size']
        print(f"Current: {current_min}-{current_max} bytes\n")
        print("Encryption Key Size: 7-16 bytes (7=56-bit, 16=128-bit)")
        print("  - Larger keys are more secure but may be slower")
        print("  - Most devices support 16-byte keys\n")

        if self.connector.set_smp_encryption_key_size(min_size, max_size):
            print(f"✓ Encryption Key Size: {min_size}-{max_size} bytes\n")
        else:
            print("✗ Invalid key size range (must be 7-16, min <= max)\n")

    async def app_smp_bonding(self, enabled: bool):
        """Configure Bonding Enable/Disable without interactive prompts.

        Args:
            enabled: True enables bond storage, False disables bond storage.
        """
        print_section("Bonding Configuration")

        current = self.connector.get_smp_config()['bonding_enabled']
        print(f"Current: {'ENABLED' if current else 'DISABLED'}\n")
        if enabled:
            self.connector.set_smp_bonding_enabled(True)
            print("✓ Bonding: ENABLED\n")
        else:
            self.connector.set_smp_bonding_enabled(False)
            print("✓ Bonding: DISABLED\n")
    
    async def app_pair(self):
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
    
    async def app_unpair(
        self,
        index: Optional[int] = None,
        address: Optional[str] = None,
        show_bonded_devices: bool = True,
    ):
        """Unpair / Delete bonding without interactive prompts.

        Args:
            index: 1-based index from the printed bonded-device list.
            address: Exact bonded device address to remove.
                Provide either index or address.
            show_bonded_devices: When True, prints the bonded devices table/list.
        """
        print_section("Unpair / Delete Bonding")
        
        # List bonded devices
        bonded = self.connector.get_bonded_devices()
        
        if not bonded:
            print("No bonded devices found.\n")
            return
        
        if show_bonded_devices:
            print(f"Found {len(bonded)} bonded device(s):\n")
            self.print_bonded_devices(bonded, title="Bonded Devices")

        target_addr = None
        addresses = list(bonded.keys())
        if address:
            target_addr = address
        elif index is not None:
            idx = int(index) - 1
            if 0 <= idx < len(addresses):
                target_addr = addresses[idx]
            else:
                print("Invalid number\n")
                return
        else:
            print("Provide index or address to unpair.\n")
            return

        if self.connector.delete_bonding(target_addr):
            print(f"\n✓ Bonding deleted for {target_addr}\n")
        else:
            print(f"\n✗ Failed to delete bonding for {target_addr}\n")
    
    async def app_disconnect(self):
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
    
    async def run(self, choices):
        """Run the menu loop using a provided iterable of choices.

        Args:
            choices: Iterable of menu-choice values, for example ["a", "1", "0"].
        """
        print_section("BUMBLE BLE TESTING FRAMEWORK")
        print(f"Transport: {self.transport_spec}\n")
        await self._auto_enable_hci_snoop_on_startup()

        try:
            for choice in choices:
                self.print_main_menu()
                choice = str(choice).strip()
                
                try:
                    if choice.lower() == "a":
                        await self.app_bluetooth_on()
                    elif choice.lower() == "b":
                        await self.app_bluetooth_off()
                    elif choice.lower() == "c":
                        await self.app_set_filters()
                    elif choice.lower() == "d":
                        print("Use app_toggle_hci_snoop(enable=...) directly in non-interactive mode\n")
                    elif choice.lower() == "e":
                        print("Use app_debug_logging(mode=...) directly in non-interactive mode\n")
                    elif choice.lower() == "s":
                        await self.app_smp_settings()
                    elif choice == "1":
                        await self.app_scan_devices()
                    elif choice == "2":
                        print("app_connect_device is not available in BLETestingApp\n")
                    elif choice == "3":
                        await self.app_discover_services()
                    elif choice == "4":
                        print("Use app_read_characteristic(handle=...) directly in non-interactive mode\n")
                    elif choice == "5":
                        print("Use app_write_characteristic(handle=..., hex_value=...) directly in non-interactive mode\n")
                    elif choice == "6":
                        print("Use app_write_without_response(handle=..., hex_value=...) directly in non-interactive mode\n")
                    elif choice == "7":
                        print("Use app_subscribe(handle=...) directly in non-interactive mode\n")
                    elif choice == "8":
                        print("Use app_subscribe_indications(handle=...) directly in non-interactive mode\n")
                    elif choice == "9":
                        await self.app_pair()
                    elif choice == "10":
                        print("Use app_unpair(index=... or address=...) directly in non-interactive mode\n")
                    elif choice == "11":
                        await self.app_disconnect()
                    elif choice == "12":
                        print("Use app_burst_write(handle=..., hex_value=...) directly in non-interactive mode\n")
                    elif choice == "13":
                        print("Use app_burst_write_without_response(handle=..., hex_value=...) directly in non-interactive mode\n")
                    elif choice == "14":
                        await self.app_stop_burst_write()
                    elif choice == "15":
                        print("Use app_burst_read(handle=...) directly in non-interactive mode\n")
                    elif choice == "16":
                        await self.app_stop_burst_read()
                    elif choice == "17":
                        await self.app_start_csv_logging()
                    elif choice == "18":
                        await self.app_stop_csv_logging()
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
