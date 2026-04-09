#!/usr/bin/env python3
"""
BLE Device Connector - Connect, Pair, and GATT operations
"""

import asyncio
import json
import logging
import sys
import os
import csv
from datetime import datetime
from typing import Optional, List, Dict, Callable, Any
from bumble.keys import JsonKeyStore
from bumble import att
from hciemu.paths import ensure_user_files, get_user_config_path

logger = logging.getLogger(__name__)


class GenericPairingDelegate:
    """Generic SMP pairing handler that works with any BLE peripheral"""
    
    def __init__(self, interactive: bool = True, io_capability=None):
        """
        Initialize pairing delegate
        
        Args:
            interactive: If True, prompt user for pairing decisions.
                        If False, auto-accept all pairing requests.
        """
        from bumble.pairing import PairingDelegate as BumblePairingDelegate
        
        self.interactive = interactive
        
        # Properly inherit from Bumble's PairingDelegate
        class _PairingDelegateImpl(BumblePairingDelegate):
            async def accept(delegate_self) -> bool:
                """Accept pairing request"""
                print("\n[PAIRING DELEGATE] accept() called", flush=True)
                sys.stdout.flush()
                if self.interactive:
                    response = input("🔐 Accept pairing request? (y/n): ").strip().lower()
                    print(f"[PAIRING DELEGATE] User response: {response}", flush=True)
                    sys.stdout.flush()
                    return response == 'y'
                print("✓ Accepting pairing request...", flush=True)
                logger.info("[PAIRING] auto-accepting pairing")
                return True
            
            async def confirm(delegate_self, auto: bool = False) -> bool:
                """Confirm Just Works pairing"""
                print(f"\n[PAIRING DELEGATE] confirm(auto={auto}) called", flush=True)
                sys.stdout.flush()
                if self.interactive and not auto:
                    print("[TIP] If prompt input appears stuck, wait a few seconds, then press Enter once to refresh.", flush=True)
                    response = input("🔐 Confirm Just Works pairing? (y/n): ").strip().lower()
                    print(f"[PAIRING DELEGATE] User response: {response}", flush=True)
                    sys.stdout.flush()
                    return response == 'y'
                print("✓ Just Works pairing confirmed", flush=True)
                logger.info("[PAIRING] auto-confirming just works")
                return True
            
            async def compare_numbers(delegate_self, number: int, digits: int) -> bool:
                """Handle Numeric Comparison (Secure Connections)"""
                code = f"{number:0{digits}d}"
                print(f"\n[PAIRING DELEGATE] compare_numbers() called")
                print(f"🔐 NUMERIC COMPARISON CODE: {code}")
                print("   Verify this code appears on the peer device and matches!\n")
                
                if self.interactive:
                    print("[TIP] If prompt input appears stuck, wait a few seconds, then press Enter once to refresh.")
                    response = input("Do the codes match? (y/n): ").strip().lower()
                    print(f"[PAIRING DELEGATE] User response: {response}")
                    return response == 'y'
                logger.info(f"[PAIRING] auto-confirming numeric comparison: {code}")
                return True
            
            async def get_number(delegate_self) -> Optional[int]:
                """Get passkey (for Passkey Entry as input)"""
                print(f"\n[PAIRING DELEGATE] get_number() called")
                print("\n📱 PASSKEY REQUIRED")
                print("[TIP] If passkey input appears stuck, wait a few seconds, then press Enter once to refresh the prompt.")
                passkey_str = input("Enter 6-digit passkey: ").strip()
                
                try:
                    passkey = int(passkey_str)
                    if 0 <= passkey <= 999999:
                        print(f"[PAIRING DELEGATE] Passkey entered: {passkey}")
                        logger.info(f"[PAIRING] passkey entered: {passkey}")
                        return passkey
                    print("✗ Passkey must be between 0-999999")
                    return None
                except ValueError:
                    print("✗ Invalid passkey, must be numeric")
                    return None
            
            async def display_number(delegate_self, number: int, digits: int) -> None:
                """Display passkey to user"""
                code = f"{number:0{digits}d}"
                print(f"\n[PAIRING DELEGATE] display_number({code}) called")
                print(f"\n🔑 PASSKEY TO DISPLAY: {code}")
                print("   Enter this code on the peer device!\n")
                logger.info(f"[PAIRING] passkey to display: {code}")
            
            async def get_string(delegate_self, max_length: int) -> Optional[str]:
                """Get PIN (for Classic pairing)"""
                print(f"\n[PAIRING DELEGATE] get_string() called")
                pin_str = input(f"Enter PIN (up to {max_length} chars): ").strip()
                print(f"[PAIRING DELEGATE] PIN entered: {pin_str if pin_str else '(empty)'}")
                return pin_str if pin_str else None
        
        # Create instance with selected IO capability (or class default if not provided).
        self.delegate_instance = _PairingDelegateImpl(
            io_capability=(
                io_capability
                if io_capability is not None
                else BumblePairingDelegate.IoCapability.DISPLAY_OUTPUT_AND_KEYBOARD_INPUT
            ),
            local_initiator_key_distribution=(
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY |
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY |
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_SIGNING_KEY
            ),
            local_responder_key_distribution=(
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY |
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY |
                BumblePairingDelegate.KeyDistribution.DISTRIBUTE_SIGNING_KEY
            ),
        )
        logger.info("[PAIRING] GenericPairingDelegate initialized")
    
    def get_delegate(self):
        """Get the actual Bumble PairingDelegate instance"""
        return self.delegate_instance


class BLEConnector:
    """BLE Device Connection Manager"""
    
    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001", interactive: bool = True):
        ensure_user_files()
        self.transport_spec = transport_spec
        self.device = None
        self.connected_device = None
        self.gatt_client = None
        self.services = {}
        self.characteristics = {}
        self.service_details = []
        self.interactive = interactive
        self.pairing_delegate = None
        self._smp_config_path = str(get_user_config_path("smp_config.json"))
        
        # SMP Configuration Parameters
        self.smp_config = {
            'io_capability': 'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT',  # Default IO capability
            'mitm_required': True,  # Man-in-the-Middle protection
            'le_secure_connections': True,  # LE Secure Connections (SC)
            'min_enc_key_size': 7,  # Minimum encryption key size
            'max_enc_key_size': 16,  # Maximum encryption key size (max is 16)
            'bonding_enabled': True,  # Bonding/key storage
            'auto_pair_encrypt_on_security_request': True,  # Auto-pair on connect, auto-handle security requests
            'auto_encrypt_if_bonded': True,  # Auto-encrypt bonded links after connect
        }
        self._load_smp_config()
        
        # Burst data operations
        self._burst_write_task = None
        self._burst_write_stop_event = None
        self._burst_read_task = None
        self._burst_read_stop_event = None
        self._burst_read_callback = None
        self._burst_read_inflight = None
        
        # CSV notification logging
        self._csv_file = None
        self._csv_writer = None
        self._csv_filename = None
        self._cccd_state_key = "_hciemu_cccd"

        # ATT MTU state for the active connection.
        self.current_att_mtu = 23

        # L2CAP CoC/ECOC channel tracking.
        self._l2cap_channels: Dict[int, Any] = {}
        self._l2cap_servers: Dict[int, Any] = {}
        self._l2cap_event_callback: Optional[Callable[[str, Any, Any], None]] = None

    def set_l2cap_event_callback(self, callback: Optional[Callable[[str, Any, Any], None]]) -> None:
        """Register callback invoked on L2CAP channel lifecycle and data events."""
        self._l2cap_event_callback = callback

    def _emit_l2cap_event(self, event_name: str, channel: Any, payload: Any = None) -> None:
        if not self._l2cap_event_callback:
            return
        try:
            self._l2cap_event_callback(event_name, channel, payload)
        except Exception as exc:
            logger.debug(f"[L2CAP] event callback error: {exc}")

    def _get_l2cap_manager(self):
        if not self.device:
            raise RuntimeError("Device is not initialized")
        manager = getattr(self.device, "l2cap_channel_manager", None)
        if not manager:
            raise RuntimeError("L2CAP channel manager is not available")
        return manager

    def _register_l2cap_channel(self, channel: Any, channel_type: str) -> None:
        source_cid = getattr(channel, "source_cid", None)
        if source_cid is None:
            raise RuntimeError("L2CAP channel does not expose source_cid")

        self._l2cap_channels[int(source_cid)] = channel

        def _on_open():
            self._emit_l2cap_event("open", channel, {"type": channel_type})

        def _on_close():
            self._l2cap_channels.pop(int(source_cid), None)
            self._emit_l2cap_event("close", channel, {"type": channel_type})

        def _on_att_mtu_update(mtu: int):
            self._emit_l2cap_event("att_mtu_update", channel, {"mtu": mtu, "type": channel_type})

        def _on_data(data: bytes):
            self._emit_l2cap_event("data", channel, data)

        # Bumble updates channel credits via on_credits(...) without emitting an
        # EventEmitter event, so we wrap that method to surface credit updates.
        original_on_credits = getattr(channel, "on_credits", None)

        def _on_credits(credits: int):
            if callable(original_on_credits):
                original_on_credits(credits)
            self._emit_l2cap_event(
                "credits",
                channel,
                {
                    "delta": int(credits),
                    "total": getattr(channel, "credits", None),
                    "type": channel_type,
                },
            )

        if callable(original_on_credits):
            setattr(channel, "on_credits", _on_credits)

        channel.on("open", _on_open)
        channel.on("close", _on_close)
        channel.on("att_mtu_update", _on_att_mtu_update)
        channel.sink = _on_data

        # Channel may already be connected when registered.
        self._emit_l2cap_event("open", channel, {"type": channel_type})

    def get_open_l2cap_channels(self) -> List[Dict[str, Any]]:
        """Return open L2CAP channels with CBFC/ECBFC details."""
        channels: List[Dict[str, Any]] = []
        for source_cid, channel in sorted(self._l2cap_channels.items()):
            channels.append(
                {
                    "source_cid": source_cid,
                    "destination_cid": getattr(channel, "destination_cid", None),
                    "psm": getattr(channel, "psm", None),
                    "mtu": getattr(channel, "mtu", None),
                    "peer_mtu": getattr(channel, "peer_mtu", None),
                    "mps": getattr(channel, "mps", None),
                    "peer_mps": getattr(channel, "peer_mps", None),
                    "credits_ours": getattr(channel, "credits", None),
                    "credits_peer": getattr(channel, "peer_credits", None),
                    "state": getattr(getattr(channel, "state", None), "name", str(getattr(channel, "state", None))),
                }
            )
        return channels

    def list_l2cap_servers(self) -> List[Dict[str, Any]]:
        """Return active LE CoC servers registered by this connector."""
        servers: List[Dict[str, Any]] = []
        for psm in sorted(self._l2cap_servers.keys()):
            servers.append({"psm": psm})
        return servers

    def _require_l2cap_channel(self, source_cid: int):
        channel = self._l2cap_channels.get(int(source_cid))
        if not channel:
            raise RuntimeError(f"No L2CAP channel found with source CID {source_cid}")
        return channel

    async def start_l2cap_cbfc_server(
        self,
        psm: int,
        mtu: int = 2048,
        mps: int = 2048,
        max_credits: int = 256,
    ) -> Dict[str, Any]:
        """Register LE CoC server to accept inbound CBFC requests on a PSM."""
        if not self.device:
            raise RuntimeError("Bluetooth device is not initialized")

        if int(psm) in self._l2cap_servers:
            raise RuntimeError(f"L2CAP server already active on PSM {psm}")

        from bumble import l2cap

        spec = l2cap.LeCreditBasedChannelSpec(
            psm=int(psm),
            mtu=int(mtu),
            mps=int(mps),
            max_credits=int(max_credits),
        )

        def _on_channel(channel: Any):
            self._register_l2cap_channel(channel, channel_type="cbfc-server")

        server = self.device.create_l2cap_server(spec=spec, handler=_on_channel)
        self._l2cap_servers[int(psm)] = server
        return {"psm": int(psm)}

    def stop_l2cap_cbfc_server(self, psm: int) -> bool:
        """Stop LE CoC server on a given PSM."""
        server = self._l2cap_servers.pop(int(psm), None)
        if not server:
            return False
        try:
            server.close()
        except Exception as exc:
            logger.debug(f"[L2CAP] server close failed for PSM {psm}: {exc}")
        return True

    async def create_l2cap_cbfc_channel(
        self,
        psm: int,
        mtu: int = 2048,
        mps: int = 2048,
        max_credits: int = 256,
    ) -> Dict[str, Any]:
        """Create one LE Credit-Based Flow Control channel (CBFC)."""
        if not self.connected_device:
            raise RuntimeError("Not connected to any device")

        from bumble import l2cap

        spec = l2cap.LeCreditBasedChannelSpec(
            psm=int(psm),
            mtu=int(mtu),
            mps=int(mps),
            max_credits=int(max_credits),
        )
        channel = await self.connected_device.create_l2cap_channel(spec=spec)
        self._register_l2cap_channel(channel, channel_type="cbfc")
        return {
            "source_cid": int(channel.source_cid),
            "destination_cid": int(channel.destination_cid),
            "psm": int(channel.psm),
        }

    async def create_l2cap_ecbfc_channels(
        self,
        psm: int,
        count: int,
        mtu: int = 2048,
        mps: int = 2048,
        max_credits: int = 256,
    ) -> List[Dict[str, Any]]:
        """Create Enhanced Credit-Based channels (ECBFC) as a channel set."""
        if not self.connected_device:
            raise RuntimeError("Not connected to any device")

        from bumble import l2cap

        manager = self._get_l2cap_manager()
        spec = l2cap.LeCreditBasedChannelSpec(
            psm=int(psm),
            mtu=int(mtu),
            mps=int(mps),
            max_credits=int(max_credits),
        )
        channels = await manager.create_enhanced_credit_based_channels(
            connection=self.connected_device,
            spec=spec,
            count=int(count),
        )

        created = []
        for channel in channels:
            self._register_l2cap_channel(channel, channel_type="ecbfc")
            created.append(
                {
                    "source_cid": int(channel.source_cid),
                    "destination_cid": int(channel.destination_cid),
                    "psm": int(channel.psm),
                }
            )
        return created

    async def disconnect_l2cap_channel(self, source_cid: int) -> None:
        """Disconnect a tracked L2CAP channel by local source CID."""
        channel = self._require_l2cap_channel(int(source_cid))
        await channel.disconnect()

    def send_l2cap_data(self, source_cid: int, data: bytes) -> None:
        """Queue payload for transmission on a connected L2CAP channel."""
        channel = self._require_l2cap_channel(int(source_cid))
        channel.write(data)

    async def drain_l2cap_channel(self, source_cid: int) -> None:
        """Wait for queued channel payload to drain."""
        channel = self._require_l2cap_channel(int(source_cid))
        await channel.drain()

    def send_l2cap_credits(self, source_cid: int, credits: int) -> None:
        """Send LE flow-control credits to peer for one channel."""
        if credits <= 0:
            raise ValueError("Credits must be > 0")

        from bumble import l2cap

        channel = self._require_l2cap_channel(int(source_cid))
        manager = self._get_l2cap_manager()
        manager.send_control_frame(
            channel.connection,
            l2cap.L2CAP_LE_SIGNALING_CID,
            l2cap.L2CAP_LE_Flow_Control_Credit(
                identifier=manager.next_identifier(channel.connection),
                cid=channel.source_cid,
                credits=int(credits),
            ),
        )

    async def reconfigure_l2cap_ecbfc_channels(
        self,
        source_cids: List[int],
        mtu: int,
        mps: int,
    ) -> bool:
        """Reconfigure enhanced credit-based channel set when supported by Bumble API."""
        del source_cids, mtu, mps

        # Bumble in this workspace exposes ECBFC channel creation but does not
        # expose public request/response handlers for L2CAP reconfigure.
        return False

    def get_connection_att_mtu(self, connection=None) -> int:
        """Read ATT MTU from active connection/client with default fallback."""
        connection = connection or self.connected_device
        for source in (connection, getattr(connection, "gatt_client", None) if connection else None):
            if source is None:
                continue
            mtu = getattr(source, "att_mtu", None)
            if isinstance(mtu, int):
                return mtu
            mtu = getattr(source, "mtu", None)
            if isinstance(mtu, int):
                return mtu
        return 23

    def sync_connection_mtu(self, connection=None) -> int:
        """Refresh and return current ATT MTU from the active connection."""
        self.current_att_mtu = self.get_connection_att_mtu(connection)
        return self.current_att_mtu

    def on_connection_att_mtu_update(self, *args) -> int:
        """Update cached ATT MTU from the active connection state."""
        # Bumble emits this event without MTU args, so read negotiated MTU from
        # the active connection state.
        mtu = self.get_connection_att_mtu()

        self.current_att_mtu = mtu

        return mtu

    def reset_connection_mtu_state(self) -> None:
        """Reset MTU cache/waiter when connection is closed or replaced."""
        self.current_att_mtu = 23

    async def exchange_att_mtu(self, mtu_size: int = 247) -> None:
        """Request ATT MTU exchange and return immediately after request call."""
        if not self.connected_device:
            raise RuntimeError("Not connected to any device")

        requested_mtu = int(mtu_size)
        if requested_mtu < 23 or requested_mtu > 517:
            raise ValueError("MTU must be between 23 and 517")

        connection = self.connected_device
        self.current_att_mtu = self.get_connection_att_mtu(connection)

        # Use Bumble's explicit Peer.request_mtu API for ATT MTU exchange.
        from bumble.device import Peer

        peer = Peer(connection)
        await peer.request_mtu(requested_mtu)

        logger.info(f"[MTU] Requested ATT MTU exchange: {requested_mtu}")

    def _bonds_file_path(self) -> str:
        return str(get_user_config_path("bumble_bonds.json"))

    def _load_bonds_data(self) -> Dict:
        bonds_file = self._bonds_file_path()
        if not os.path.exists(bonds_file):
            return {}

        try:
            with open(bonds_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Could not load bonds data: {e}")
            return {}

    def _save_bonds_data(self, bonds_data: Dict) -> bool:
        bonds_file = self._bonds_file_path()
        try:
            with open(bonds_file, "w", encoding="utf-8") as handle:
                json.dump(bonds_data, handle, indent=2)
                handle.write("\n")
            return True
        except Exception as e:
            logger.warning(f"Could not save bonds data: {e}")
            return False

    def _find_peer_bond_entry(self, bonds_data: Dict, peer_address: str):
        for _local_addr, peers in bonds_data.items():
            if isinstance(peers, dict) and peer_address in peers and isinstance(peers[peer_address], dict):
                return peers[peer_address]
        return None

    def _record_cccd_preference(self, handle: int, mode: str) -> None:
        if not self.connected_device:
            return

        try:
            peer_address = str(self.connected_device.peer_address)
            bonds_data = self._load_bonds_data()
            peer_entry = self._find_peer_bond_entry(bonds_data, peer_address)
            if not peer_entry:
                logger.debug(f"[CCCD] No bonded entry yet for {peer_address}; skipping CCCD persistence")
                return

            cccd_map = peer_entry.get(self._cccd_state_key)
            if not isinstance(cccd_map, dict):
                cccd_map = {}
                peer_entry[self._cccd_state_key] = cccd_map

            cccd_map[str(handle)] = mode
            if self._save_bonds_data(bonds_data):
                logger.info(f"[CCCD] Persisted {mode} subscription for handle 0x{handle:04X} ({handle})")
        except Exception as e:
            logger.debug(f"[CCCD] Failed to persist CCCD preference: {e}")

    def _get_persisted_cccd_preferences(self) -> Dict[int, str]:
        if not self.connected_device:
            return {}

        try:
            peer_address = str(self.connected_device.peer_address)
            bonds_data = self._load_bonds_data()
            peer_entry = self._find_peer_bond_entry(bonds_data, peer_address)
            if not peer_entry:
                return {}

            cccd_map = peer_entry.get(self._cccd_state_key)
            if not isinstance(cccd_map, dict):
                return {}

            parsed = {}
            for handle_str, mode in cccd_map.items():
                if mode not in {"notify", "indicate"}:
                    continue
                try:
                    parsed[int(handle_str)] = mode
                except (TypeError, ValueError):
                    continue
            return parsed
        except Exception as e:
            logger.debug(f"[CCCD] Failed to load CCCD preferences: {e}")
            return {}

    async def _restore_persisted_cccd_preferences(self) -> None:
        prefs = self._get_persisted_cccd_preferences()
        if not prefs:
            return

        restored = 0
        for handle, mode in prefs.items():
            if handle not in self.characteristics:
                continue

            ok = False
            if mode == "notify":
                ok = await self.subscribe_notifications(handle)
            elif mode == "indicate":
                ok = await self.subscribe_indications(handle)

            if ok:
                restored += 1

        if restored:
            logger.info(f"[CCCD] Restored {restored} persisted subscription(s)")

    def _load_smp_config(self):
        """Load SMP configuration from disk; keep defaults on any error."""
        if not os.path.exists(self._smp_config_path):
            return

        try:
            with open(self._smp_config_path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)

            if not isinstance(loaded, dict):
                logger.warning("[SMP] Ignoring invalid config file format (expected object)")
                return

            merged = self.smp_config.copy()
            merged.update(loaded)
            self.smp_config = self._normalize_smp_config(merged)
            logger.info(f"[SMP] Loaded configuration from {self._smp_config_path}")
        except Exception as e:
            logger.warning(f"[SMP] Could not load config from {self._smp_config_path}: {e}")

    def _save_smp_config(self):
        """Persist current SMP configuration to disk."""
        try:
            os.makedirs(os.path.dirname(self._smp_config_path), exist_ok=True)
            with open(self._smp_config_path, "w", encoding="utf-8") as handle:
                json.dump(self.smp_config, handle, indent=2)
                handle.write("\n")
            logger.info(f"[SMP] Saved configuration to {self._smp_config_path}")
        except Exception as e:
            logger.warning(f"[SMP] Failed to save config to {self._smp_config_path}: {e}")

    def _normalize_smp_config(self, config: dict) -> dict:
        """Normalize and validate SMP settings loaded from disk."""
        normalized = self.smp_config.copy()

        valid_io = {
            'DISPLAY_ONLY',
            'KEYBOARD_ONLY',
            'NO_INPUT_NO_OUTPUT',
            'KEYBOARD_DISPLAY',
            'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT',
        }

        io_value = config.get('io_capability')
        if io_value in valid_io:
            normalized['io_capability'] = io_value

        normalized['mitm_required'] = bool(config.get('mitm_required', normalized['mitm_required']))
        normalized['le_secure_connections'] = bool(
            config.get('le_secure_connections', normalized['le_secure_connections'])
        )
        normalized['bonding_enabled'] = bool(config.get('bonding_enabled', normalized['bonding_enabled']))
        normalized['auto_pair_encrypt_on_security_request'] = bool(
            config.get(
                'auto_pair_encrypt_on_security_request',
                normalized['auto_pair_encrypt_on_security_request'],
            )
        )
        normalized['auto_encrypt_if_bonded'] = bool(
            config.get(
                'auto_encrypt_if_bonded',
                config.get(
                    'auto_pair_encrypt_on_security_request',
                    normalized['auto_encrypt_if_bonded'],
                ),
            )
        )

        try:
            min_size = int(config.get('min_enc_key_size', normalized['min_enc_key_size']))
            max_size = int(config.get('max_enc_key_size', normalized['max_enc_key_size']))
            if 7 <= min_size <= 16 and 7 <= max_size <= 16 and min_size <= max_size:
                normalized['min_enc_key_size'] = min_size
                normalized['max_enc_key_size'] = max_size
        except (TypeError, ValueError):
            pass

        return normalized
    
    def _resolve_io_capability(self, option_name: str):
        """Resolve configured IO capability to Bumble enum across library versions."""
        from bumble.pairing import PairingDelegate

        io_cls = PairingDelegate.IoCapability

        # Different Bumble versions expose slightly different enum member names.
        candidate_names = {
            'DISPLAY_ONLY': [
                'DISPLAY_ONLY',
                'DISPLAY_OUTPUT_ONLY',
            ],
            'KEYBOARD_ONLY': [
                'KEYBOARD_ONLY',
                'KEYBOARD_INPUT_ONLY',
            ],
            'NO_INPUT_NO_OUTPUT': [
                'NO_INPUT_NO_OUTPUT',
                'NO_OUTPUT_NO_INPUT',
            ],
            'KEYBOARD_DISPLAY': [
                'KEYBOARD_DISPLAY',
                'DISPLAY_OUTPUT_AND_YES_NO_INPUT',
            ],
            'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT': [
                'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT',
                'KEYBOARD_DISPLAY',
                'DISPLAY_OUTPUT_AND_YES_NO_INPUT',
            ],
        }

        requested = candidate_names.get(option_name, [])
        fallback = candidate_names['DISPLAY_OUTPUT_AND_KEYBOARD_INPUT']

        for name in requested + fallback:
            if hasattr(io_cls, name):
                return getattr(io_cls, name)

        raise RuntimeError(
            f"No compatible PairingDelegate.IoCapability found in Bumble for option '{option_name}'"
        )

    def setup_pairing_on_device(self, device):
        """
        Set up generic SMP pairing on a device
        
        Args:
            device: Bumble Device instance
        """
        from bumble.pairing import PairingConfig
        from bumble import smp
        
        logger.info("[PAIRING SETUP] Starting pairing configuration")
        
        resolved_io_capability = self._resolve_io_capability(self.smp_config['io_capability'])

        # Create pairing delegate wrapper with configured IO capability
        self.pairing_delegate = GenericPairingDelegate(
            interactive=self.interactive,
            io_capability=resolved_io_capability,
        )
        delegate = self.pairing_delegate.get_delegate()
        
        logger.info(f"[PAIRING SETUP] Created delegate: {delegate}")
        
        # Configure pairing factory for device
        def pairing_config_factory(connection):
            logger.info(f"[PAIRING SETUP] pairing_config_factory called for connection {connection}")
            config = PairingConfig(
                sc=self.smp_config['le_secure_connections'],  # Secure Connections (LE SC)
                mitm=self.smp_config['mitm_required'],  # Man-in-the-Middle protection
                bonding=self.smp_config['bonding_enabled'],  # Store keys for future connections
                delegate=delegate,
                identity_address_type=PairingConfig.AddressType.RANDOM
            )
            logger.info(f"[PAIRING SETUP] Created PairingConfig: {config}")
            return config
        
        device.pairing_config_factory = pairing_config_factory
        
        logger.info("[PAIRING SETUP] Generic SMP pairing factory configured successfully")
        logger.info(f"[PAIRING SETUP] Config: SC={self.smp_config['le_secure_connections']}, "
                   f"MITM={self.smp_config['mitm_required']}, "
                   f"Bonding={self.smp_config['bonding_enabled']}, "
                   f"IO={self.smp_config['io_capability']}")

    def get_smp_config(self):
        """Get current SMP configuration"""
        return self.smp_config.copy()
    
    def set_smp_io_capability(self, io_capability: str) -> bool:
        """Set SMP IO capability
        
        Args:
            io_capability: One of 'DISPLAY_ONLY', 'KEYBOARD_ONLY', 'NO_INPUT_NO_OUTPUT', 
                          'KEYBOARD_DISPLAY', 'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT'
        
        Returns:
            True if valid, False otherwise
        """
        valid_options = {
            'DISPLAY_ONLY',
            'KEYBOARD_ONLY', 
            'NO_INPUT_NO_OUTPUT',
            'KEYBOARD_DISPLAY',
            'DISPLAY_OUTPUT_AND_KEYBOARD_INPUT'
        }
        if io_capability in valid_options:
            self.smp_config['io_capability'] = io_capability
            logger.info(f"[SMP] IO Capability set to: {io_capability}")
            self._save_smp_config()
            return True
        return False
    
    def set_smp_mitm_required(self, required: bool):
        """Set MITM protection requirement"""
        self.smp_config['mitm_required'] = required
        logger.info(f"[SMP] MITM Required: {required}")
        self._save_smp_config()
    
    def set_smp_secure_connections(self, enabled: bool):
        """Set LE Secure Connections enable/disable"""
        self.smp_config['le_secure_connections'] = enabled
        logger.info(f"[SMP] LE Secure Connections: {enabled}")
        self._save_smp_config()
    
    def set_smp_encryption_key_size(self, min_size: int, max_size: int) -> bool:
        """Set encryption key size range
        
        Args:
            min_size: Minimum key size (7-16)
            max_size: Maximum key size (7-16)
        
        Returns:
            True if valid, False otherwise
        """
        if not (7 <= min_size <= 16 and 7 <= max_size <= 16 and min_size <= max_size):
            return False
        self.smp_config['min_enc_key_size'] = min_size
        self.smp_config['max_enc_key_size'] = max_size
        logger.info(f"[SMP] Encryption Key Size: {min_size}-{max_size}")
        self._save_smp_config()
        return True
    
    def set_smp_bonding_enabled(self, enabled: bool):
        """Set bonding enable/disable"""
        self.smp_config['bonding_enabled'] = enabled
        logger.info(f"[SMP] Bonding Enabled: {enabled}")
        self._save_smp_config()

    def set_smp_auto_pair_encrypt_on_security_request(self, enabled: bool):
        """Set auto pair/encrypt behavior for connection and security requests."""
        self.smp_config['auto_pair_encrypt_on_security_request'] = enabled
        logger.info(f"[SMP] Auto Pair/Encrypt on Security Request: {enabled}")
        self._save_smp_config()

    def set_smp_auto_encrypt_if_bonded(self, enabled: bool):
        """Set automatic encryption behavior for bonded devices after connection."""
        self.smp_config['auto_encrypt_if_bonded'] = enabled
        logger.info(f"[SMP] Auto Encrypt If Bonded: {enabled}")
        self._save_smp_config()

    
    async def connect_device(self, device_address: str) -> bool:
        """
        Connect to a BLE device
        
        Args:
            device_address: Target device address (e.g., "80:E4:BA:42:E9:AF")
            
        Returns:
            True if connection successful
        """
        try:
            from bumble.transport import open_transport
            from bumble.device import Device
            from bumble.hci import Address
            
            logger.info(f"Connecting to device: {device_address}")
            
            # Open transport
            self.transport = await open_transport(self.transport_spec)
            
            # Create device using proper initialization
            self.device = Device.with_hci(
                name='BLEConnector',
                address=Address('F0:F1:F2:F3:F4:F5'),
                hci_source=self.transport.source,
                hci_sink=self.transport.sink,
            )
            
            # Parse target address
            target_address = Address(device_address)
            
            # Connect (skip power_on if controller doesn't support reset)
            logger.info("Initiating connection...")
            self.connected_device = await self.device.connect(target_address)
            
            logger.info(f"Connected to {device_address}")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def establish_security(self) -> bool:
        """
        Establish security/encryption on a bonded connection.
        For bonded connections, this will use stored LTK to enable encryption.
        
        Returns:
            True if security is established
        """
        if not self.connected_device or not self.device:
            logger.error("No device connected")
            return False

        try:
            logger.info("Checking security status on bonded connection...")
            
            # Check if already encrypted
            if self.connected_device.is_encrypted:
                logger.info("✓ Connection is encrypted")
                print("[SECURITY] ✓ Connection is already encrypted")
                return True
            
            # For bonded connections, explicitly enable encryption
            # This will send HCI_LE_ENABLE_ENCRYPTION_COMMAND with stored LTK
            logger.info("Connection not encrypted - enabling encryption with bonded keys...")
            print("[SECURITY] Enabling encryption with bonded keys...")
            
            # Call encrypt() to enable encryption using keystore LTK
            await asyncio.wait_for(
                self.connected_device.encrypt(),
                timeout=10.0
            )
            
            logger.info("✓ Encryption enabled successfully")
            print("[SECURITY] ✓ Encryption enabled")
            return True
            
        except asyncio.TimeoutError:
            logger.warning("Encryption timeout - peer may not have accepted")
            print("[SECURITY] ⚠ Encryption timed out")
            return False
        except Exception as e:
            logger.error(f"Encryption failed: {e}", exc_info=True)
            print(f"[SECURITY] ✗ Encryption failed: {e}")
            return False

    def send_security_request(self) -> bool:
        """Send an SMP Security Request on the active connection."""
        if not self.connected_device:
            logger.error("No device connected")
            return False

        try:
            self.connected_device.request_pairing()
            logger.info(
                f"[SECURITY REQUEST] Sent SMP Security Request to {self.connected_device.peer_address}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send SMP Security Request: {e}", exc_info=True)
            return False
    
    async def pair(self) -> bool:
        """
        Initiate pairing with connected device
        
        Returns:
            True if pairing successful
        """
        if not self.connected_device or not self.device:
            logger.error("No device connected")
            return False
        
        try:
            peer_address = str(self.connected_device.peer_address)
            logger.info(f"Starting SMP pairing with {peer_address}...")
            
            # Initiate pairing through the device's SMP manager
            # This will trigger the pairing delegate's methods based on the pairing method
            await self.device.pair(self.connected_device)
            
            logger.info("✓ Pairing completed successfully")
            
            # Manually store bonding keys after successful pairing
            # Bumble's auto-storage doesn't always work, so we do it explicitly
            await asyncio.sleep(0.5)  # Wait for keys to be generated
            self._save_bonding_keys(peer_address)
            
            return True
            
        except asyncio.TimeoutError:
            logger.error("Pairing timeout - device not responding")
            return False
        except asyncio.CancelledError as e:
            # Bumble cancels the pairing future when a disconnection occurs.
            logger.warning(f"Pairing cancelled: {e}")
            return False
        except Exception as e:
            logger.error(f"Pairing failed: {e}", exc_info=True)
            return False
    
    def _save_bonding_keys(self, peer_address: str):
        """
        Verify bonding keys were saved by Bumble keystore.
        Bumble handles key persistence automatically - this just logs it.
        
        Args:
            peer_address: The bonded device address
        """
        try:
            bonds_file = self._bonds_file_path()
            
            # Wait a moment for keystore to sync
            import time
            time.sleep(0.1)
            
            if os.path.exists(bonds_file):
                with open(bonds_file, 'r') as f:
                    bonds_data = json.load(f)
                
                # Check if this device is in the bonds file (Bumble format: {local_addr: {peer_addr: keys}})
                for local_addr, peers in bonds_data.items():
                    if isinstance(peers, dict) and peer_address in peers:
                        device_keys = peers[peer_address]
                        has_ltk = "ltk" in device_keys or "ltk_central" in device_keys or "ltk_peripheral" in device_keys
                        irk_entry = device_keys.get("irk")
                        irk_value = irk_entry.get("value", "") if isinstance(irk_entry, dict) else ""
                        has_irk = bool(irk_entry) and irk_value.replace("0", "") != ""
                        has_csrk = "csrk" in device_keys
                        
                        logger.info(f"[BONDING] ✓ Keys saved for {peer_address}")
                        logger.info(f"  - LTK (encryption): {has_ltk}")
                        logger.info(f"  - IRK (identity): {has_irk}")
                        logger.info(f"  - CSRK (signing): {has_csrk}")
                        
                        print(f"[BONDING] ✓ Keys stored:")
                        if has_ltk:
                            print(f"  ✓ LTK (encryption key)")
                        if has_irk:
                            print(f"  ✓ IRK (identity key)")
                        if has_csrk:
                            print(f"  ✓ CSRK (signing key)")
                        return
                
                logger.warning(f"[BONDING] Device {peer_address} not found in bonds file yet")
            else:
                logger.info(f"[BONDING] Bonds file created at: {bonds_file}")
                
        except Exception as e:
            logger.debug(f"[BONDING] Error verifying keys: {e}")
    
    def is_device_bonded(self, device_address: str) -> bool:
        """
        Check if a device is already bonded
        
        Args:
            device_address: The peer device address to check
            
        Returns:
            True if device is bonded, False otherwise
        """
        try:
            bonds_file = self._bonds_file_path()
            
            if not os.path.exists(bonds_file):
                return False
            
            with open(bonds_file, 'r') as f:
                bonds_data = json.load(f)
            
            # Bumble stores bonds in format: {local_addr: {peer_addr: {keys...}}}
            # Check in all local device entries
            for local_addr, peers in bonds_data.items():
                if isinstance(peers, dict):
                    if device_address in peers:
                        logger.info(f"✓ Device {device_address} is already bonded (found under {local_addr})")
                        return True
            
            logger.info(f"Device {device_address} is not bonded")
            return False
            
        except Exception as e:
            logger.warning(f"Could not check bonding status: {e}")
            return False
    
    def get_bonded_devices(self) -> Dict:
        """
        Get list of bonded devices from persistent storage
        
        Returns:
            Dictionary of bonded addresses and their info
        """
        try:
            bonds_file = self._bonds_file_path()
            
            if not os.path.exists(bonds_file):
                logger.info("No bonding file found")
                return {}
            
            bonded_devices = {}
            
            with open(bonds_file, 'r') as f:
                bonds_data = json.load(f)
            
            # Bumble stores bonds in format: {local_addr: {peer_addr: {keys...}}}
            # Extract peer addresses from all local device entries
            for local_addr, peers in bonds_data.items():
                if isinstance(peers, dict):
                    for peer_addr in peers.keys():
                        bonded_devices[peer_addr] = {
                            'address': peer_addr,
                            'bonded': True,
                            'local_address': local_addr
                        }
            
            logger.info(f"Found {len(bonded_devices)} bonded devices")
            return bonded_devices
            
        except FileNotFoundError:
            logger.info("Bonds file not found")
            return {}
        except Exception as e:
            logger.warning(f"Could not retrieve bonded devices: {e}")
            return {}
    
    def delete_bonding(self, device_address: str) -> bool:
        """
        Delete bonding keys for a device from persistent storage
        
        Args:
            device_address: Address of device to unpair
            
        Returns:
            True if bonding deleted successfully
        """
        try:
            bonds_file = self._bonds_file_path()
            
            if not os.path.exists(bonds_file):
                logger.warning(f"Bonds file not found: {bonds_file}")
                return False
            
            # Load bonds data
            with open(bonds_file, 'r') as f:
                bonds_data = json.load(f)
            
            # Bumble format: {local_addr: {peer_addr: {keys...}}}
            # Search through all local addresses to find and delete the peer
            deleted = False
            for local_addr, peers in list(bonds_data.items()):
                if isinstance(peers, dict) and device_address in peers:
                    del bonds_data[local_addr][device_address]
                    deleted = True
                    logger.info(f"✓ Deleted bonding for {device_address} (under {local_addr})")
                    
                    # If this local address has no more peers, remove it
                    if not bonds_data[local_addr]:
                        del bonds_data[local_addr]
                        logger.info(f"Removed empty local address entry: {local_addr}")
                    break
            
            if deleted:
                # Save updated bonds data
                with open(bonds_file, 'w') as f:
                    json.dump(bonds_data, f, indent=2)
                return True
            else:
                logger.warning(f"Device {device_address} not found in bonds")
                return False
            
        except Exception as e:
            logger.error(f"Failed to delete bonding: {e}", exc_info=True)
            return False
    
    async def discover_services(self, force_fresh: bool = False, restore_persisted_cccd: bool = False) -> Dict:
        """
        Discover GATT services
        
        Args:
            force_fresh: If True, bypass cache and do a fresh discovery
            restore_persisted_cccd: If True, restore persisted notification/indication
                subscriptions after discovery completes
        
        Returns:
            Dictionary of services and characteristics
        """
        if not self.connected_device:
            logger.error("No device connected")
            return {}
        
        # Return cached results if available (unless force_fresh is True)
        if self.service_details and not force_fresh:
            logger.info("Using cached discovery results")
            return self.services
        
        try:
            logger.info("Discovering services...")
            if getattr(self.connected_device, "gatt_client", None) is None:
                logger.error("No GATT client available on connection")
                return {}

            self.gatt_client = self.connected_device.gatt_client
            services_list = await self.gatt_client.discover_services()

            services = {}
            characteristics = {}
            service_details = []

            for service in services_list:
                char_proxies = await self.gatt_client.discover_characteristics((), service)

                service_uuid = str(service.uuid)
                char_list = []
                service_info = {
                    "uuid": service_uuid,
                    "handle": getattr(service, "handle", None),
                    "end_group_handle": getattr(service, "end_group_handle", None),
                    "characteristics": [],
                }

                for char in char_proxies:
                    char_uuid = str(char.uuid)
                    handle = getattr(char, "handle", None)
                    props = getattr(char, "properties", None)

                    props_str = ""
                    if props is not None:
                        if isinstance(props, (list, tuple, set)):
                            props_str = ",".join([getattr(p, "name", str(p)).lower() for p in props])
                        elif hasattr(props, "__iter__") and not isinstance(props, (str, bytes)):
                            props_str = ",".join([getattr(p, "name", str(p)).lower() for p in props])
                        else:
                            props_str = str(props)

                    if handle is not None:
                        char_desc = f"{char_uuid} (handle=0x{handle:04X}/{handle}{', ' + props_str if props_str else ''})"
                        characteristics[handle] = char
                    else:
                        char_desc = f"{char_uuid}{' (' + props_str + ')' if props_str else ''}"

                    char_list.append(char_desc)
                    char_info = {
                        "uuid": char_uuid,
                        "handle": handle,
                        "end_group_handle": getattr(char, "end_group_handle", None),
                        "properties": props_str,
                        "descriptors": [],
                    }

                    try:
                        descriptors = await char.discover_descriptors()
                        for desc in descriptors:
                            char_info["descriptors"].append(
                                {
                                    "uuid": str(desc.type),
                                    "handle": getattr(desc, "handle", None),
                                }
                            )
                    except Exception as exc:
                        logger.debug(f"Descriptor discovery skipped for {char_uuid}: {exc}")

                    service_info["characteristics"].append(char_info)

                services[service_uuid] = char_list
                service_details.append(service_info)

            logger.info(f"Found {len(services)} services")
            self.services = services
            self.characteristics = characteristics
            self.service_details = service_details
            if restore_persisted_cccd:
                await self._restore_persisted_cccd_preferences()

            return services
            
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return {}
    
    async def read_characteristic(self, handle: int) -> Optional[bytes]:
        """
        Read a characteristic value
        
        Args:
            handle: Characteristic handle
            
        Returns:
            Characteristic value as bytes
        """
        if not self.connected_device:
            logger.error("No device connected")
            return None
        
        if not self.gatt_client:
            logger.error("No GATT client available")
            return None
        
        try:
            logger.info(f"Reading handle 0x{handle:04X} ({handle})...")
            value = await self.gatt_client.read_value(handle)
            logger.info(f"Read {len(value)} bytes: {value.hex()}")
            return value
            
        except att.ATT_Error as e:
            # Handle specific ATT errors
            if e.error_code == att.ErrorCode.INSUFFICIENT_ENCRYPTION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient encryption required")
            elif e.error_code == att.ErrorCode.INSUFFICIENT_AUTHORIZATION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient authorization")
            elif e.error_code == att.ErrorCode.READ_NOT_PERMITTED:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Read not permitted")
            else:
                logger.error(f"ATT Error 0x{e.error_code:02X}: {e.error_name}")
            return None
            
        except asyncio.TimeoutError:
            logger.error("GATT timeout - peer not responding")
            return None
        except Exception as e:
            logger.error(f"Read failed: {e}")
            return None
    
    async def write_characteristic(self, handle: int, value: bytes) -> bool:
        """
        Write to a characteristic
        
        Args:
            handle: Characteristic handle
            value: Value to write
            
        Returns:
            True if write successful
        """
        if not self.connected_device:
            logger.error("No device connected")
            return False
        
        if not self.gatt_client:
            logger.error("No GATT client available")
            return False
        
        try:
            logger.info(f"Writing to handle 0x{handle:04X} ({handle}): {value.hex()}")
            await self.gatt_client.write_value(handle, value, with_response=True)
            logger.info("Write successful")
            return True
            
        except att.ATT_Error as e:
            if e.error_code == att.ErrorCode.INSUFFICIENT_ENCRYPTION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient encryption required")
            elif e.error_code == att.ErrorCode.INSUFFICIENT_AUTHORIZATION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient authorization")
            elif e.error_code == att.ErrorCode.WRITE_NOT_PERMITTED:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Write not permitted")
            else:
                logger.error(f"ATT Error 0x{e.error_code:02X}: {e.error_name}")
            return False
            
        except asyncio.TimeoutError:
            logger.error("GATT timeout - peer not responding")
            return False
        except Exception as e:
            logger.error(f"Write failed: {e}")
            return False
    
    async def write_without_response(self, handle: int, value: bytes) -> bool:
        """
        Write without response
        
        Args:
            handle: Characteristic handle
            value: Value to write
            
        Returns:
            True if write successful
        """
        if not self.connected_device:
            logger.error("No device connected")
            return False
        
        if not self.gatt_client:
            logger.error("No GATT client available")
            return False
        
        try:
            logger.info(f"Writing (no response) to handle 0x{handle:04X} ({handle}): {value.hex()}")
            await self.gatt_client.write_value(handle, value, with_response=False)
            logger.info("Write command sent")
            return True
            
        except att.ATT_Error as e:
            if e.error_code == att.ErrorCode.INSUFFICIENT_ENCRYPTION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient encryption required")
            elif e.error_code == att.ErrorCode.INSUFFICIENT_AUTHORIZATION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient authorization")
            elif e.error_code == att.ErrorCode.WRITE_NOT_PERMITTED:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Write not permitted")
            else:
                logger.error(f"ATT Error 0x{e.error_code:02X}: {e.error_name}")
            return False
            
        except asyncio.TimeoutError:
            logger.error("Write timeout - peer not responding")
            return False
        except Exception as e:
            logger.error(f"Write failed: {e}")
            return False
    
    async def subscribe_notifications(self, handle: int) -> bool:
        """
        Subscribe to notifications on a characteristic (unacknowledged)
        
        Args:
            handle: Characteristic handle
            
        Returns:
            True if subscription successful
        """
        if not self.connected_device:
            logger.error("No device connected")
            return False
        
        if not self.gatt_client:
            logger.error("No GATT client available")
            return False
        
        try:
            logger.info(f"Subscribing to notifications on handle 0x{handle:04X} ({handle})...")
            
            # Get the characteristic proxy from our stored characteristics
            if handle not in self.characteristics:
                logger.error(f"Handle 0x{handle:04X} ({handle}) not found in discovered characteristics")
                return False
            
            char_proxy = self.characteristics[handle]
            
            # Define notification handler
            def notification_handler(value: bytes):
                logger.info(f"[NOTIFICATION] Handle 0x{handle:04X} ({handle}): {value.hex()}")
                print(f"\n[NOTIFY] 0x{handle:04X} ({handle}): {value.hex()}")
                # Log to CSV if enabled
                self._log_to_csv("NOTIFY", handle, value)
            
            # Subscribe using the proxy (prefer_notify=True means notifications)
            await self.gatt_client.subscribe(char_proxy, notification_handler, prefer_notify=True)
            logger.info("Notification subscription successful")
            self._record_cccd_preference(handle, "notify")
            return True
            
        except att.ATT_Error as e:
            if e.error_code == att.ErrorCode.INSUFFICIENT_ENCRYPTION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient encryption required")
            elif e.error_code == att.ErrorCode.INSUFFICIENT_AUTHORIZATION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient authorization")
            else:
                logger.error(f"ATT Error 0x{e.error_code:02X}: {e.error_name}")
            return False
            
        except asyncio.TimeoutError:
            logger.error("Subscribe timeout - peer not responding")
            return False
        except Exception as e:
            logger.error(f"Subscribe failed: {e}")
            return False
    
    async def subscribe_indications(self, handle: int) -> bool:
        """
        Subscribe to indications on a characteristic (acknowledged)
        
        Args:
            handle: Characteristic handle
            
        Returns:
            True if subscription successful
        """
        if not self.connected_device:
            logger.error("No device connected")
            return False
        
        if not self.gatt_client:
            logger.error("No GATT client available")
            return False
        
        try:
            logger.info(f"Subscribing to indications on handle 0x{handle:04X} ({handle})...")
            
            # Get the characteristic proxy from our stored characteristics
            if handle not in self.characteristics:
                logger.error(f"Handle 0x{handle:04X} ({handle}) not found in discovered characteristics")
                return False
            
            char_proxy = self.characteristics[handle]
            
            # Define indication handler
            def indication_handler(value: bytes):
                logger.info(f"[INDICATION] Handle 0x{handle:04X} ({handle}): {value.hex()}")
                print(f"\n[INDICATE] 0x{handle:04X} ({handle}): {value.hex()}")
                # Log to CSV if enabled
                self._log_to_csv("INDICATE", handle, value)
            
            # Subscribe using the proxy (prefer_notify=False means indications)
            await self.gatt_client.subscribe(char_proxy, indication_handler, prefer_notify=False)
            logger.info("Indication subscription successful")
            self._record_cccd_preference(handle, "indicate")
            return True
            
        except att.ATT_Error as e:
            if e.error_code == att.ErrorCode.INSUFFICIENT_ENCRYPTION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient encryption required")
            elif e.error_code == att.ErrorCode.INSUFFICIENT_AUTHORIZATION:
                logger.error(f"ATT Error 0x{e.error_code:02X}: Insufficient authorization")
            else:
                logger.error(f"ATT Error 0x{e.error_code:02X}: {e.error_name}")
            return False
            
        except asyncio.TimeoutError:
            logger.error("Subscribe timeout - peer not responding")
            return False
        except Exception as e:
            logger.error(f"Subscribe failed: {e}")
            return False

    async def _burst_write_sender(
        self,
        handle: int,
        data: bytes,
        with_response: bool,
        count: int,
        interval_ms: int,
    ):
        """Internal function to send burst data."""
        sent_count = 0
        interval_sec = interval_ms / 1000.0

        try:
            logger.info(f"Starting burst write on handle 0x{handle:04X} ({handle})")
            logger.info(f"Mode: {'with response' if with_response else 'without response'}")
            logger.info(f"Count: {'infinite' if count == 0 else count}, Interval: {interval_ms}ms")
            logger.info(f"Data (hex): {data.hex()}")

            while True:
                if self._burst_write_stop_event and self._burst_write_stop_event.is_set():
                    logger.info(f"Burst write stopped by user after {sent_count} sends")
                    print(f"\n[BURST WRITE] Stopped after {sent_count} packets")
                    break

                if not self.connected_device:
                    logger.warning(f"Device disconnected during burst write after {sent_count} sends")
                    print(f"\n[BURST WRITE] Device disconnected after {sent_count} packets")
                    break

                try:
                    if with_response:
                        await self.write_characteristic(handle, data)
                    else:
                        await self.write_without_response(handle, data)

                    sent_count += 1

                    if count <= 20 or sent_count % 10 == 0:
                        print(f"[BURST WRITE] Packet #{sent_count} sent")

                    if count > 0 and sent_count >= count:
                        logger.info(f"Burst write completed: {sent_count} packets sent")
                        print(f"\n[BURST WRITE] Completed: {sent_count} packets sent")
                        break

                    await asyncio.sleep(interval_sec)

                except Exception as e:
                    logger.error(f"Error during burst write (packet {sent_count + 1}): {e}")
                    print(f"\n[BURST WRITE] Error on packet {sent_count + 1}: {e}")
                    await asyncio.sleep(interval_sec)

        except asyncio.CancelledError:
            logger.info(f"Burst write cancelled after {sent_count} sends")
            print(f"\n[BURST WRITE] Cancelled after {sent_count} packets")
        except Exception as e:
            logger.error(f"Burst write error: {e}")
            print(f"\n[BURST WRITE] Error: {e}")
        finally:
            print(f"[BURST WRITE] Total packets sent: {sent_count}")

    async def start_burst_write(
        self,
        handle: int,
        data: bytes,
        with_response: bool = True,
        count: int = 0,
        interval_ms: int = 100,
    ):
        """Start burst data writing."""
        if self._burst_write_task and not self._burst_write_task.done():
            logger.info("Stopping existing burst write...")
            await self.stop_burst_write()

        self._burst_write_stop_event = asyncio.Event()
        self._burst_write_task = asyncio.create_task(
            self._burst_write_sender(handle, data, with_response, count, interval_ms)
        )

        await asyncio.sleep(0.01)
        logger.info("Burst write started in background")

    async def stop_burst_write(self) -> bool:
        """Stop ongoing burst write."""
        if not self._burst_write_task or self._burst_write_task.done():
            logger.info("No active burst write to stop")
            return False

        logger.info("Stopping burst write...")

        if self._burst_write_stop_event:
            self._burst_write_stop_event.set()

        try:
            await asyncio.wait_for(self._burst_write_task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Burst write task did not stop gracefully, cancelling...")
            self._burst_write_task.cancel()
            try:
                await self._burst_write_task
            except asyncio.CancelledError:
                pass

        self._burst_write_task = None
        self._burst_write_stop_event = None
        logger.info("Burst write stopped")
        return True

    async def _burst_read_reader(self, handle: int, count: int, interval_ms: int):
        """Internal function to read burst data."""
        read_count = 0
        interval_sec = interval_ms / 1000.0

        try:
            logger.info(f"Starting burst read on handle 0x{handle:04X} ({handle})")
            logger.info(f"Count: {'infinite' if count == 0 else count}, Interval: {interval_ms}ms")

            while True:
                if self._burst_read_stop_event and self._burst_read_stop_event.is_set():
                    logger.info(f"Burst read stopped by user after {read_count} reads")
                    print(f"\n[BURST READ] Stopped after {read_count} reads")
                    break

                if not self.connected_device:
                    logger.warning(f"Device disconnected during burst read after {read_count} reads")
                    print(f"\n[BURST READ] Device disconnected after {read_count} reads", flush=True)
                    break

                if not self.gatt_client:
                    self.gatt_client = getattr(self.connected_device, "gatt_client", None)
                    if not self.gatt_client:
                        logger.warning("No GATT client available for burst read")
                        print("\n[BURST READ] No GATT client available. Discover services first (Option 3).", flush=True)
                        break

                try:
                    target_read = read_count + 1
                    print(f"[BURST READ] Starting read #{target_read}", flush=True)
                    value = await asyncio.wait_for(
                        self.gatt_client.read_value(handle),
                        timeout=5.0,
                    )

                    if value is not None:
                        read_count += 1
                        print(f"[BURST READ] Read #{read_count}", flush=True)

                        if self._burst_read_callback:
                            try:
                                self._burst_read_callback(handle, value, read_count)
                            except Exception as e:
                                logger.warning(f"Burst read callback failed: {e}")
                        else:
                            print(f"  Handle: 0x{handle:04X} ({handle})")
                            print(f"  Length: {len(value)} bytes")
                            print(f"  Hex: {value.hex()}")
                            print(f"  ASCII: {value.decode('utf-8', errors='replace')}")

                        if count > 0 and read_count >= count:
                            logger.info(f"Burst read completed: {read_count} reads performed")
                            print(f"\n[BURST READ] Completed: {read_count} reads performed", flush=True)
                            break
                    else:
                        logger.warning(f"Read failed on burst read #{read_count + 1}")
                        print(f"[BURST READ] Read #{read_count + 1} failed", flush=True)

                    await asyncio.sleep(interval_sec)

                except asyncio.TimeoutError:
                    logger.warning(f"Burst read timeout on read #{read_count + 1}")
                    print(f"[BURST READ] Read #{read_count + 1} timed out", flush=True)
                    await asyncio.sleep(interval_sec)
                except Exception as e:
                    logger.error(f"Error during burst read (read {read_count + 1}): {e}")
                    print(f"\n[BURST READ] Error on read {read_count + 1}: {e}", flush=True)
                    await asyncio.sleep(interval_sec)

        except asyncio.CancelledError:
            logger.info(f"Burst read cancelled after {read_count} reads")
            print(f"\n[BURST READ] Cancelled after {read_count} reads", flush=True)
        except Exception as e:
            logger.error(f"Burst read error: {e}")
            print(f"\n[BURST READ] Error: {e}", flush=True)
        finally:
            print(f"[BURST READ] Total reads performed: {read_count}", flush=True)

    async def start_burst_read(
        self,
        handle: int,
        count: int = 0,
        interval_ms: int = 100,
        on_value: Optional[Callable[[int, bytes, int], None]] = None,
    ):
        """Start burst data reading."""
        if not self.connected_device:
            raise RuntimeError("No device connected")

        if not self.gatt_client:
            self.gatt_client = getattr(self.connected_device, "gatt_client", None)
        if not self.gatt_client:
            raise RuntimeError("No GATT client available (run service discovery first)")

        if self._burst_read_task and not self._burst_read_task.done():
            logger.info("Stopping existing burst read...")
            await self.stop_burst_read()

        self._burst_read_stop_event = asyncio.Event()
        self._burst_read_callback = on_value
        self._burst_read_task = asyncio.create_task(
            self._burst_read_reader(handle, count, interval_ms)
        )

        await asyncio.sleep(0.01)
        logger.info("Burst read started in background")

    async def stop_burst_read(self) -> bool:
        """Stop ongoing burst read."""
        if not self._burst_read_task or self._burst_read_task.done():
            logger.info("No active burst read to stop")
            return False

        logger.info("Stopping burst read...")

        if self._burst_read_stop_event:
            self._burst_read_stop_event.set()

        if self._burst_read_inflight and not self._burst_read_inflight.done():
            self._burst_read_inflight.cancel()
            try:
                await self._burst_read_inflight
            except asyncio.CancelledError:
                pass
            self._burst_read_inflight = None

        try:
            await asyncio.wait_for(self._burst_read_task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Burst read task did not stop gracefully, cancelling...")
            self._burst_read_task.cancel()
            try:
                await self._burst_read_task
            except asyncio.CancelledError:
                pass

        self._burst_read_task = None
        self._burst_read_stop_event = None
        self._burst_read_callback = None
        logger.info("Burst read stopped")
        return True

    def start_csv_logging(self, filename: Optional[str] = None) -> bool:
        """Start logging notifications/indications to a CSV file."""
        if self._csv_file:
            logger.warning("CSV logging already active")
            return False

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"notifications_{timestamp}.csv"

        try:
            self._csv_filename = filename
            self._csv_file = open(filename, "w", newline="", encoding="utf-8")
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow(
                [
                    "Timestamp",
                    "Type",
                    "Handle",
                    "Handle (Hex)",
                    "Length",
                    "Data (Hex)",
                    "Data (ASCII)",
                ]
            )
            self._csv_file.flush()
            logger.info(f"CSV logging started: {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to start CSV logging: {e}")
            return False

    def stop_csv_logging(self) -> bool:
        """Stop CSV logging."""
        if not self._csv_file:
            logger.info("No active CSV logging to stop")
            return False

        try:
            self._csv_file.close()
            logger.info(f"CSV logging stopped: {self._csv_filename}")
            print(f"[CSV] Log saved: {self._csv_filename}")
            self._csv_file = None
            self._csv_writer = None
            self._csv_filename = None
            return True
        except Exception as e:
            logger.error(f"Error stopping CSV logging: {e}")
            return False

    def _log_to_csv(self, data_type: str, handle: int, value: Optional[bytes]):
        """Log notification/indication data to CSV."""
        if not self._csv_writer or value is None:
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            handle_hex = f"0x{handle:04X}"
            length = len(value)
            data_hex = value.hex()
            data_ascii = value.decode("utf-8", errors="replace")

            self._csv_writer.writerow(
                [timestamp, data_type, handle, handle_hex, length, data_hex, data_ascii]
            )
            self._csv_file.flush()
        except Exception as e:
            logger.error(f"Error writing to CSV: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from device"""
        try:
            # Stop burst operations
            if hasattr(self, '_burst_write_task') and self._burst_write_task and not self._burst_write_task.done():
                await self.stop_burst_write()
            if hasattr(self, '_burst_read_task') and self._burst_read_task and not self._burst_read_task.done():
                await self.stop_burst_read()
            
            # Stop CSV logging
            if hasattr(self, '_csv_file') and self._csv_file:
                self.stop_csv_logging()
            
            if self.connected_device:
                logger.info("Disconnecting...")
                await self.connected_device.disconnect()
                self.connected_device = None
            
            # Clear cached discovery results on disconnect
            self.service_details = []
            self.services = {}
            self.characteristics = {}
            self.gatt_client = None
            
            if self.device:
                await self.device.close()
                self.device = None
            
            logger.info("Disconnected")
            return True
            
        except Exception as e:
            logger.error(f"Disconnect failed: {e}")
            return False


async def connect_and_explore(device_address: str, transport_spec: str = "tcp-client:127.0.0.1:9001"):
    """Connect to device and explore GATT"""
    connector = BLEConnector(transport_spec)
    
    if await connector.connect_device(device_address):
        await connector.discover_services()
        await connector.disconnect()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Connect to BLE device")
    parser.add_argument("address", help="BLE device address")
    parser.add_argument("--transport", default="tcp-client:127.0.0.1:9001")
    
    args = parser.parse_args()
    
    asyncio.run(connect_and_explore(args.address, args.transport))


if __name__ == "__main__":
    main()
