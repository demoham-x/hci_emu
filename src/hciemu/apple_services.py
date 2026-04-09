#!/usr/bin/env python3
"""Apple ANCS and AMS helpers built on top of the generic GATT connector."""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None
    Panel = None
    Table = None
    box = None

logger = logging.getLogger(__name__)

if HAS_RICH:
    console = Console()
else:
    console = None

if TYPE_CHECKING:
    from hciemu.connector import BLEConnector


ANCS_SERVICE_UUID = "7905F431-B5CE-4E99-A40F-4B1E122D00D0"
ANCS_NOTIFICATION_SOURCE_UUID = "9FBF120D-6301-42D9-8C58-25E699A21DBD"
ANCS_CONTROL_POINT_UUID = "69D1D8F3-45E1-49A8-9821-9BBDFDAAD9D9"
ANCS_DATA_SOURCE_UUID = "22EAC6E9-24D6-4BB5-BE44-B36ACE7C7BFB"

AMS_SERVICE_UUID = "89D3502B-0F36-433A-8EF4-C502AD55F8DC"
AMS_REMOTE_COMMAND_UUID = "9B3C81D8-57B1-4A8A-B8DF-0E56F7CA51C2"
AMS_ENTITY_UPDATE_UUID = "2F7CABCE-808D-411F-9A0C-BB92BA96C102"
AMS_ENTITY_ATTRIBUTE_UUID = "C6B2F38C-23AB-46D8-A6AB-A3A870BBD5D7"

ANCS_EVENT_IDS = {
    0: "added",
    1: "modified",
    2: "removed",
}

ANCS_EVENT_FLAGS = {
    0: "silent",
    1: "important",
    2: "pre_existing",
    3: "positive_action",
    4: "negative_action",
}

ANCS_CATEGORY_IDS = {
    0: "other",
    1: "incoming_call",
    2: "missed_call",
    3: "voicemail",
    4: "social",
    5: "schedule",
    6: "email",
    7: "news",
    8: "health_and_fitness",
    9: "business_and_finance",
    10: "location",
    11: "entertainment",
}

ANCS_COMMAND_IDS = {
    0: "get_notification_attributes",
    1: "get_app_attributes",
    2: "perform_notification_action",
}

ANCS_NOTIFICATION_ATTRIBUTE_NAMES = {
    0: "app_identifier",
    1: "title",
    2: "subtitle",
    3: "message",
    4: "message_size",
    5: "date",
    6: "positive_action_label",
    7: "negative_action_label",
}

ANCS_NOTIFICATION_ATTRIBUTE_IDS = {
    "app_identifier": 0,
    "title": 1,
    "subtitle": 2,
    "message": 3,
    "message_size": 4,
    "date": 5,
    "positive_action_label": 6,
    "negative_action_label": 7,
}

ANCS_NOTIFICATION_ATTRIBUTES_WITH_LENGTH = {1, 2, 3}

ANCS_APP_ATTRIBUTE_NAMES = {
    0: "display_name",
}

ANCS_APP_ATTRIBUTE_IDS = {
    "display_name": 0,
}

ANCS_ACTION_NAMES = {
    0: "positive",
    1: "negative",
}

ANCS_ACTION_IDS = {
    "positive": 0,
    "negative": 1,
}

AMS_REMOTE_COMMAND_NAMES = {
    0: "play",
    1: "pause",
    2: "toggle_play_pause",
    3: "next_track",
    4: "previous_track",
    5: "volume_up",
    6: "volume_down",
    7: "advance_repeat_mode",
    8: "advance_shuffle_mode",
    9: "skip_forward",
    10: "skip_backward",
    11: "like_track",
    12: "dislike_track",
    13: "bookmark_track",
}

AMS_REMOTE_COMMAND_IDS = {name: command_id for command_id, name in AMS_REMOTE_COMMAND_NAMES.items()}

AMS_ENTITY_NAMES = {
    0: "player",
    1: "queue",
    2: "track",
}

AMS_ENTITY_IDS = {name: entity_id for entity_id, name in AMS_ENTITY_NAMES.items()}

AMS_ENTITY_ATTRIBUTE_NAMES = {
    0: {
        0: "name",
        1: "playback_info",
        2: "volume",
    },
    1: {
        0: "index",
        1: "count",
        2: "shuffle_mode",
        3: "repeat_mode",
    },
    2: {
        0: "artist",
        1: "album",
        2: "title",
        3: "duration",
    },
}

AMS_ENTITY_ATTRIBUTE_IDS = {
    entity_id: {name: attribute_id for attribute_id, name in attribute_names.items()}
    for entity_id, attribute_names in AMS_ENTITY_ATTRIBUTE_NAMES.items()
}

AMS_ENTITY_UPDATE_FLAG_TRUNCATED = 0x01
AMS_PLAYER_PLAYBACK_STATES = {
    0: "paused",
    1: "playing",
    2: "rewinding",
    3: "fast_forwarding",
}
AMS_REPEAT_MODES = {
    0: "off",
    1: "one",
    2: "all",
}
AMS_SHUFFLE_MODES = {
    0: "off",
    1: "one",
    2: "all",
}

DEFAULT_ANCS_NOTIFICATION_ATTRIBUTES = [
    (0, None),
    (1, 64),
    (2, 64),
    (3, 255),
    (4, None),
    (5, None),
    (6, None),
    (7, None),
]

DEFAULT_AMS_ENTITY_SUBSCRIPTIONS = {
    "player": ["name", "playback_info", "volume"],
    "queue": ["index", "count", "shuffle_mode", "repeat_mode"],
    "track": ["artist", "album", "title", "duration"],
}


@dataclass
class AppleCharacteristic:
    """Characteristic metadata captured from discovery."""

    service_uuid: str
    characteristic_uuid: str
    handle: int
    properties: str
    description: str


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


class AppleServices:
    """Session-scoped helper for Apple Notification Center and Media services."""

    def __init__(self, connector: "BLEConnector"):
        self.connector = connector
        self.ancs_characteristics: Dict[str, AppleCharacteristic] = {}
        self.ams_characteristics: Dict[str, AppleCharacteristic] = {}
        self.ancs_handler: Optional[Callable[[str, Dict[str, Any], bytes], Any]] = None
        self.ams_handler: Optional[Callable[[str, Dict[str, Any], bytes], Any]] = None
        self.event_handler: Optional[Callable[[str, str, Dict[str, Any], bytes], Any]] = None
        self.supported_ams_commands: List[int] = []
        self._ancs_request_lock = asyncio.Lock()
        self._ancs_pending_request: Optional[Dict[str, Any]] = None
        self._ancs_pending_future: Optional[asyncio.Future] = None
        self._ancs_response_buffer = bytearray()
        self._ancs_cached_apps: Dict[str, Dict[str, Any]] = {}
        self._last_ams_entity_attribute_request: Optional[Tuple[int, int]] = None
        self.auto_fetch_ancs_details = False
        self.auto_fetch_ancs_app_attributes = False
        self.auto_read_ams_truncated_attributes = True

    @classmethod
    def from_discovery(cls, connector: "BLEConnector") -> "AppleServices":
        instance = cls(connector)
        instance.refresh_from_discovery()
        return instance

    def refresh_from_discovery(self) -> None:
        self.ancs_characteristics = self._collect_service_characteristics(ANCS_SERVICE_UUID)
        self.ams_characteristics = self._collect_service_characteristics(AMS_SERVICE_UUID)
        self.supported_ams_commands = []
        self._ancs_cached_apps = {}
        self._ancs_pending_request = None
        self._ancs_pending_future = None
        self._ancs_response_buffer = bytearray()
        self._last_ams_entity_attribute_request = None

    def has_ancs(self) -> bool:
        return bool(self.ancs_characteristics)

    def has_ams(self) -> bool:
        return bool(self.ams_characteristics)

    def has_any(self) -> bool:
        return self.has_ancs() or self.has_ams()

    def get_supported_ams_command_names(self) -> List[str]:
        return [
            AMS_REMOTE_COMMAND_NAMES.get(command_id, f"reserved_{command_id}")
            for command_id in self.supported_ams_commands
        ]

    def set_handlers(
        self,
        *,
        ancs_handler: Optional[Callable[[str, Dict[str, Any], bytes], Any]] = None,
        ams_handler: Optional[Callable[[str, Dict[str, Any], bytes], Any]] = None,
        event_handler: Optional[Callable[[str, str, Dict[str, Any], bytes], Any]] = None,
    ) -> None:
        self.ancs_handler = ancs_handler
        self.ams_handler = ams_handler
        self.event_handler = event_handler

    def print_status(self) -> None:
        if HAS_RICH and console:
            console.print(self._build_status_table())
            return
        for line in self.status_lines():
            print(line)

    def status_lines(self) -> List[str]:
        lines = []
        if self.has_ancs():
            lines.append("[APPLE] ANCS available")
            lines.extend(self._status_lines_for_service("ANCS", self.ancs_characteristics))
        else:
            lines.append("[APPLE] ANCS not discovered")

        if self.has_ams():
            lines.append("[APPLE] AMS available")
            lines.extend(self._status_lines_for_service("AMS", self.ams_characteristics))
        else:
            lines.append("[APPLE] AMS not discovered")
        return lines

    def _build_status_table(self):
        table = Table(
            title="Apple Services Status",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Service", style="cyan", no_wrap=True)
        table.add_column("Characteristic", style="green")
        table.add_column("Handle", style="yellow", no_wrap=True)
        table.add_column("Properties", style="magenta")

        if not self.has_any():
            table.add_row("-", "No Apple services discovered", "-", "-")
            return table

        for label, characteristics in (("ANCS", self.ancs_characteristics), ("AMS", self.ams_characteristics)):
            if not characteristics:
                table.add_row(label, "Not discovered", "-", "-")
                continue
            for characteristic in characteristics.values():
                table.add_row(
                    label,
                    characteristic.characteristic_uuid,
                    f"0x{characteristic.handle:04X} ({characteristic.handle})",
                    characteristic.properties or "-",
                )

                if self.has_ams():
                    supported = ", ".join(self.get_supported_ams_command_names()) or "waiting for AMS Remote Command notification"
                    table.add_row("AMS", "Supported Commands", "-", supported)

        return table

    async def subscribe_ancs(
        self,
        *,
        auto_fetch_details: bool = True,
        auto_fetch_app_attributes: bool = True,
    ) -> bool:
        if not self.has_ancs():
            print("[ANCS] Service not available. Discover services first.")
            return False

        self.auto_fetch_ancs_details = auto_fetch_details
        self.auto_fetch_ancs_app_attributes = auto_fetch_app_attributes

        data_source = self.ancs_characteristics.get(ANCS_DATA_SOURCE_UUID)
        notification_source = self.ancs_characteristics.get(ANCS_NOTIFICATION_SOURCE_UUID)

        ok = True
        if data_source:
            ok = ok and await self.connector.subscribe_notifications(
                data_source.handle,
                callback=self._handle_ancs_data_source,
                label="ANCS Data Source",
            )
        elif auto_fetch_details:
            print("[ANCS] Data Source characteristic not found, attribute fetches will be unavailable.")

        if notification_source:
            ok = ok and await self.connector.subscribe_notifications(
                notification_source.handle,
                callback=self._handle_ancs_notification_source,
                label="ANCS Notification Source",
            )
        else:
            print("[ANCS] Notification Source characteristic not found.")
            ok = False

        if ok:
            print("[ANCS] Subscribed. Notification Source delivers event summaries; Data Source delivers attribute responses.")
        return ok

    async def subscribe_ams(self, *, register_defaults: bool = True, auto_read_truncated: bool = True) -> bool:
        if not self.has_ams():
            print("[AMS] Service not available. Discover services first.")
            return False

        self.auto_read_ams_truncated_attributes = auto_read_truncated

        ok = True
        remote_command = self.ams_characteristics.get(AMS_REMOTE_COMMAND_UUID)
        entity_update = self.ams_characteristics.get(AMS_ENTITY_UPDATE_UUID)

        if remote_command:
            ok = ok and await self.connector.subscribe_notifications(
                remote_command.handle,
                callback=self._handle_ams_remote_commands,
                label="AMS Remote Command",
            )
        else:
            print("[AMS] Remote Command characteristic not found.")

        if entity_update:
            ok = ok and await self.connector.subscribe_notifications(
                entity_update.handle,
                callback=self._handle_ams_entity_update,
                label="AMS Entity Update",
            )
        else:
            print("[AMS] Entity Update characteristic not found.")
            ok = False

        if ok and register_defaults:
            await self.register_default_ams_updates()

        if ok:
            print("[AMS] Subscribed. Remote Command notifications list supported commands; Entity Update notifications deliver attribute changes.")
        return ok

    async def request_notification_attributes(
        self,
        notification_uid: int,
        attributes: Optional[Sequence[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        control_point = self.ancs_characteristics.get(ANCS_CONTROL_POINT_UUID)
        data_source = self.ancs_characteristics.get(ANCS_DATA_SOURCE_UUID)
        if not control_point or not data_source:
            print("[ANCS] Control Point and Data Source are required for attribute requests.")
            return None

        normalized_attributes = self._normalize_ancs_notification_attribute_specs(
            attributes or DEFAULT_ANCS_NOTIFICATION_ATTRIBUTES
        )
        payload = bytearray([0])
        payload.extend(struct.pack("<I", notification_uid))
        for attribute_id, max_length in normalized_attributes:
            payload.append(attribute_id)
            if attribute_id in ANCS_NOTIFICATION_ATTRIBUTES_WITH_LENGTH:
                payload.extend(struct.pack("<H", max_length or 255))

        pending = {
            "command_id": 0,
            "notification_uid": notification_uid,
            "attributes": normalized_attributes,
        }
        response = await self._perform_ancs_request(bytes(payload), pending)
        if response:
            self._print_ancs_attribute_response(response)
        return response

    async def request_recommended_notification_attributes(self, notification_uid: int) -> Optional[Dict[str, Any]]:
        return await self.request_notification_attributes(notification_uid, DEFAULT_ANCS_NOTIFICATION_ATTRIBUTES)

    async def request_app_attributes(
        self,
        app_identifier: str,
        attributes: Optional[Sequence[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        control_point = self.ancs_characteristics.get(ANCS_CONTROL_POINT_UUID)
        data_source = self.ancs_characteristics.get(ANCS_DATA_SOURCE_UUID)
        if not control_point or not data_source:
            print("[ANCS] Control Point and Data Source are required for app attribute requests.")
            return None

        normalized_attributes = self._normalize_ancs_app_attribute_specs(attributes or [0])
        payload = bytearray([1])
        payload.extend(app_identifier.encode("utf-8"))
        payload.append(0)
        payload.extend(normalized_attributes)

        pending = {
            "command_id": 1,
            "app_identifier": app_identifier,
            "attributes": normalized_attributes,
        }
        response = await self._perform_ancs_request(bytes(payload), pending)
        if response:
            self._ancs_cached_apps[app_identifier] = response.get("attributes", {})
            self._print_ancs_attribute_response(response)
        return response

    async def perform_notification_action(self, notification_uid: int, action: Any) -> bool:
        control_point = self.ancs_characteristics.get(ANCS_CONTROL_POINT_UUID)
        if not control_point:
            print("[ANCS] Control Point characteristic not available.")
            return False

        action_id = self._normalize_ancs_action(action)
        payload = bytes([2]) + struct.pack("<I", notification_uid) + bytes([action_id])
        ok = await self.connector.write_characteristic(control_point.handle, payload)
        if ok:
            print(f"[ANCS] Requested {ANCS_ACTION_NAMES.get(action_id, action_id)} action for notification UID {notification_uid}.")
        return ok

    async def register_ams_entity_updates(self, entity: Any, attributes: Sequence[Any]) -> bool:
        entity_update = self.ams_characteristics.get(AMS_ENTITY_UPDATE_UUID)
        if not entity_update:
            print("[AMS] Entity Update characteristic not available.")
            return False

        entity_id = self._normalize_ams_entity(entity)
        attribute_ids = [self._normalize_ams_attribute(entity_id, attribute) for attribute in attributes]
        payload = bytes([entity_id, *attribute_ids])
        ok = await self.connector.write_characteristic(entity_update.handle, payload)
        if ok:
            names = ", ".join(self._ams_attribute_name(entity_id, attr_id) for attr_id in attribute_ids)
            print(f"[AMS] Registered entity updates for {AMS_ENTITY_NAMES.get(entity_id, entity_id)}: {names}")
        return ok

    async def register_default_ams_updates(self) -> bool:
        overall_ok = True
        for entity_name, attributes in DEFAULT_AMS_ENTITY_SUBSCRIPTIONS.items():
            ok = await self.register_ams_entity_updates(entity_name, attributes)
            overall_ok = overall_ok and ok
        return overall_ok

    async def read_ams_entity_attribute(self, entity: Any, attribute: Any) -> Optional[Dict[str, Any]]:
        entity_attribute = self.ams_characteristics.get(AMS_ENTITY_ATTRIBUTE_UUID)
        if not entity_attribute:
            print("[AMS] Entity Attribute characteristic not available.")
            return None

        entity_id = self._normalize_ams_entity(entity)
        attribute_id = self._normalize_ams_attribute(entity_id, attribute)
        request_payload = bytes([entity_id, attribute_id])
        self._last_ams_entity_attribute_request = (entity_id, attribute_id)

        ok = await self.connector.write_characteristic(entity_attribute.handle, request_payload)
        if not ok:
            return None

        value = await self.connector.read_characteristic(entity_attribute.handle)
        if value is None:
            return None

        parsed = self.parse_ams_entity_attribute_value(entity_id, attribute_id, value)
        self._print_ams_entity_attribute_read(parsed)
        self._emit_ams_event("entity_attribute_read", parsed, value)
        return parsed

    async def send_ams_remote_command(self, command: Any) -> bool:
        remote_command = self.ams_characteristics.get(AMS_REMOTE_COMMAND_UUID)
        if not remote_command:
            print("[AMS] Remote Command characteristic not available.")
            return False

        command_id = self._normalize_ams_command(command)
        if self.supported_ams_commands and command_id not in self.supported_ams_commands:
            supported = ", ".join(self.get_supported_ams_command_names()) or "none"
            print(
                f"[AMS] Remote command {AMS_REMOTE_COMMAND_NAMES.get(command_id, command_id)} is not advertised as supported by the phone. "
                f"Supported commands: {supported}"
            )
            return False

        if not self.supported_ams_commands:
            print(
                "[AMS] No supported-command list received yet. The write can succeed at GATT level even if the phone ignores the command. "
                "Subscribe AMS first and wait for the Remote Command notification to know what is supported."
            )

        ok = await self.connector.write_without_response(remote_command.handle, bytes([command_id]))
        if ok:
            print(f"[AMS] Sent remote command {AMS_REMOTE_COMMAND_NAMES.get(command_id, command_id)}.")
        return ok

    def parse_ancs_notification_source(self, value: bytes) -> Dict[str, Any]:
        if len(value) < 8:
            return {
                "type": "notification_source",
                "error": "payload_too_short",
                "raw_hex": value.hex(),
            }

        event_id = value[0]
        event_flags = value[1]
        category_id = value[2]
        category_count = value[3]
        notification_uid = struct.unpack_from("<I", value, 4)[0]
        return {
            "type": "notification_source",
            "event_id": event_id,
            "event": ANCS_EVENT_IDS.get(event_id, f"reserved_{event_id}"),
            "event_flags": event_flags,
            "event_flag_names": self._decode_ancs_flags(event_flags),
            "category_id": category_id,
            "category": ANCS_CATEGORY_IDS.get(category_id, f"reserved_{category_id}"),
            "category_count": category_count,
            "notification_uid": notification_uid,
            "raw_hex": value.hex(),
        }

    def parse_ams_remote_command_value(self, value: bytes) -> Dict[str, Any]:
        command_ids = list(value)
        return {
            "type": "remote_commands",
            "command_ids": command_ids,
            "commands": [AMS_REMOTE_COMMAND_NAMES.get(command_id, f"reserved_{command_id}") for command_id in command_ids],
            "raw_hex": value.hex(),
        }

    def parse_ams_entity_update_value(self, value: bytes) -> Dict[str, Any]:
        if len(value) < 3:
            return {
                "type": "entity_update",
                "error": "payload_too_short",
                "raw_hex": value.hex(),
            }

        entity_id = value[0]
        attribute_id = value[1]
        flags = value[2]
        raw_value = value[3:]
        parsed_value = self._decode_ams_attribute_value(entity_id, attribute_id, raw_value)
        return {
            "type": "entity_update",
            "entity_id": entity_id,
            "entity": AMS_ENTITY_NAMES.get(entity_id, f"reserved_{entity_id}"),
            "attribute_id": attribute_id,
            "attribute": self._ams_attribute_name(entity_id, attribute_id),
            "flags": flags,
            "truncated": bool(flags & AMS_ENTITY_UPDATE_FLAG_TRUNCATED),
            "raw_value_hex": raw_value.hex(),
            "raw_value": raw_value,
            "value": parsed_value,
            "raw_hex": value.hex(),
        }

    def parse_ams_entity_attribute_value(self, entity_id: int, attribute_id: int, value: bytes) -> Dict[str, Any]:
        return {
            "type": "entity_attribute",
            "entity_id": entity_id,
            "entity": AMS_ENTITY_NAMES.get(entity_id, f"reserved_{entity_id}"),
            "attribute_id": attribute_id,
            "attribute": self._ams_attribute_name(entity_id, attribute_id),
            "raw_value_hex": value.hex(),
            "raw_value": value,
            "value": self._decode_ams_attribute_value(entity_id, attribute_id, value),
        }

    def format_ancs_notification(self, parsed: Dict[str, Any]) -> str:
        if parsed.get("error"):
            return f"[ANCS] Notification Source parse error: {parsed['error']} ({parsed.get('raw_hex', '')})"
        flags = ", ".join(parsed.get("event_flag_names", [])) or "none"
        return (
            "[ANCS] Notification Source: "
            f"event={parsed['event']}, category={parsed['category']}, count={parsed['category_count']}, "
            f"uid={parsed['notification_uid']}, flags={flags}"
        )

    def format_ancs_attribute_response(self, parsed: Dict[str, Any]) -> str:
        if parsed.get("error"):
            return f"[ANCS] Data Source parse error: {parsed['error']}"

        lines = []
        response_type = parsed.get("response_type")
        if response_type == "notification_attributes":
            lines.append(f"[ANCS] Notification Attributes for UID {parsed['notification_uid']}")
        elif response_type == "app_attributes":
            lines.append(f"[ANCS] App Attributes for {parsed['app_identifier']}")
        else:
            lines.append("[ANCS] Data Source response")

        for name, value in parsed.get("attributes", {}).items():
            lines.append(f"  - {name}: {value}")
        return "\n".join(lines)

    def format_ams_remote_commands(self, parsed: Dict[str, Any]) -> str:
        commands = ", ".join(parsed.get("commands", [])) or "none"
        return f"[AMS] Supported remote commands: {commands}"

    def format_ams_entity_update(self, parsed: Dict[str, Any]) -> str:
        if parsed.get("error"):
            return f"[AMS] Entity Update parse error: {parsed['error']} ({parsed.get('raw_hex', '')})"
        suffix = " (truncated)" if parsed.get("truncated") else ""
        return f"[AMS] Entity Update: {parsed['entity']}.{parsed['attribute']} = {parsed['value']}{suffix}"

    def format_ams_entity_attribute_read(self, parsed: Dict[str, Any]) -> str:
        return f"[AMS] Entity Attribute Read: {parsed['entity']}.{parsed['attribute']} = {parsed['value']}"

    def _collect_service_characteristics(self, service_uuid: str) -> Dict[str, AppleCharacteristic]:
        characteristics: Dict[str, AppleCharacteristic] = {}
        target_service = service_uuid.lower()
        for service in self.connector.service_details:
            current_service_uuid = str(service.get("uuid", "")).lower()
            if current_service_uuid != target_service:
                continue

            for characteristic in service.get("characteristics", []):
                handle = characteristic.get("handle")
                characteristic_uuid = str(characteristic.get("uuid", "")).upper()
                if handle is None:
                    continue
                characteristics[characteristic_uuid] = AppleCharacteristic(
                    service_uuid=service_uuid.upper(),
                    characteristic_uuid=characteristic_uuid,
                    handle=handle,
                    properties=characteristic.get("properties") or "",
                    description=characteristic_uuid,
                )
        return characteristics

    def _status_lines_for_service(self, label: str, characteristics: Dict[str, AppleCharacteristic]) -> List[str]:
        lines = []
        for characteristic in characteristics.values():
            lines.append(
                f"  - {label} {characteristic.characteristic_uuid}: handle=0x{characteristic.handle:04X} ({characteristic.handle}), props={characteristic.properties or '-'}"
            )
        return lines

    async def _perform_ancs_request(self, payload: bytes, pending: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        control_point = self.ancs_characteristics.get(ANCS_CONTROL_POINT_UUID)
        if not control_point:
            print("[ANCS] Control Point characteristic not available.")
            return None

        async with self._ancs_request_lock:
            loop = asyncio.get_running_loop()
            self._ancs_response_buffer = bytearray()
            self._ancs_pending_request = pending
            self._ancs_pending_future = loop.create_future()

            try:
                ok = await self.connector.write_characteristic(control_point.handle, payload)
                if not ok:
                    return None
                return await asyncio.wait_for(self._ancs_pending_future, timeout=10.0)
            except asyncio.TimeoutError:
                print("[ANCS] Timed out waiting for Data Source response.")
                return None
            finally:
                self._ancs_response_buffer = bytearray()
                self._ancs_pending_request = None
                self._ancs_pending_future = None

    def _handle_ancs_notification_source(self, value: bytes) -> None:
        parsed = self.parse_ancs_notification_source(value)
        self._print_ancs_notification(parsed)
        self._emit_ancs_event("notification_source", parsed, value)

        should_fetch = (
            parsed.get("event") in {"added", "modified"}
            and self.auto_fetch_ancs_details
            and ANCS_CONTROL_POINT_UUID in self.ancs_characteristics
            and ANCS_DATA_SOURCE_UUID in self.ancs_characteristics
        )
        if not should_fetch:
            return

        notification_uid = parsed.get("notification_uid")
        if notification_uid is None:
            return

        asyncio.create_task(self._auto_fetch_ancs_details(notification_uid))

    def _handle_ancs_data_source(self, value: bytes) -> None:
        if not self._ancs_pending_request:
            parsed = {
                "type": "data_source",
                "warning": "unexpected_response_without_pending_request",
                "raw_hex": value.hex(),
            }
            self._print_warning("ANCS Unexpected Data Source", value.hex())
            self._emit_ancs_event("data_source", parsed, value)
            return

        self._ancs_response_buffer.extend(value)
        parsed = self._try_parse_ancs_response()
        if not parsed:
            logger.debug("[ANCS] Waiting for more Data Source fragments")
            return

        self._emit_ancs_event("data_source", parsed, bytes(self._ancs_response_buffer))
        if self._ancs_pending_future and not self._ancs_pending_future.done():
            self._ancs_pending_future.set_result(parsed)

    def _handle_ams_remote_commands(self, value: bytes) -> None:
        parsed = self.parse_ams_remote_command_value(value)
        self.supported_ams_commands = parsed.get("command_ids", [])
        self._print_ams_remote_commands(parsed)
        self._emit_ams_event("remote_commands", parsed, value)

    def _handle_ams_entity_update(self, value: bytes) -> None:
        parsed = self.parse_ams_entity_update_value(value)
        self._print_ams_entity_update(parsed)
        self._emit_ams_event("entity_update", parsed, value)

        if parsed.get("truncated") and self.auto_read_ams_truncated_attributes:
            entity_id = parsed.get("entity_id")
            attribute_id = parsed.get("attribute_id")
            if entity_id is not None and attribute_id is not None:
                asyncio.create_task(self.read_ams_entity_attribute(entity_id, attribute_id))

    async def _auto_fetch_ancs_details(self, notification_uid: int) -> None:
        response = await self.request_recommended_notification_attributes(notification_uid)
        if not response or not self.auto_fetch_ancs_app_attributes:
            return

        app_identifier = response.get("attributes", {}).get("app_identifier")
        if not app_identifier or app_identifier in self._ancs_cached_apps:
            return

        await self.request_app_attributes(app_identifier)

    def _try_parse_ancs_response(self) -> Optional[Dict[str, Any]]:
        if not self._ancs_pending_request:
            return None

        command_id = self._ancs_pending_request.get("command_id")
        if command_id == 0:
            return self._parse_ancs_notification_attributes_response()
        if command_id == 1:
            return self._parse_ancs_app_attributes_response()
        return None

    def _parse_ancs_notification_attributes_response(self) -> Optional[Dict[str, Any]]:
        buffer = bytes(self._ancs_response_buffer)
        pending = self._ancs_pending_request or {}
        if len(buffer) < 5:
            return None
        if buffer[0] != 0:
            return {
                "type": "data_source",
                "error": f"unexpected_command_id_{buffer[0]}",
                "raw_hex": buffer.hex(),
            }

        notification_uid = struct.unpack_from("<I", buffer, 1)[0]
        offset = 5
        attributes: Dict[str, Any] = {}
        normalized_attributes = pending.get("attributes", [])

        for requested_attribute_id, _ in normalized_attributes:
            if offset + 3 > len(buffer):
                return None

            attribute_id = buffer[offset]
            attribute_length = struct.unpack_from("<H", buffer, offset + 1)[0]
            offset += 3

            if offset + attribute_length > len(buffer):
                return None

            attribute_value = buffer[offset:offset + attribute_length]
            offset += attribute_length
            attribute_name = ANCS_NOTIFICATION_ATTRIBUTE_NAMES.get(attribute_id, f"reserved_{attribute_id}")
            attributes[attribute_name] = self._decode_utf8(attribute_value)

        return {
            "type": "data_source",
            "response_type": "notification_attributes",
            "command": ANCS_COMMAND_IDS[0],
            "notification_uid": notification_uid,
            "attributes": attributes,
            "raw_hex": buffer[:offset].hex(),
        }

    def _parse_ancs_app_attributes_response(self) -> Optional[Dict[str, Any]]:
        buffer = bytes(self._ancs_response_buffer)
        pending = self._ancs_pending_request or {}
        if len(buffer) < 3:
            return None
        if buffer[0] != 1:
            return {
                "type": "data_source",
                "error": f"unexpected_command_id_{buffer[0]}",
                "raw_hex": buffer.hex(),
            }

        try:
            app_identifier_end = buffer.index(0, 1)
        except ValueError:
            return None

        app_identifier = self._decode_utf8(buffer[1:app_identifier_end])
        offset = app_identifier_end + 1
        attributes: Dict[str, Any] = {}

        for requested_attribute_id in pending.get("attributes", []):
            if offset + 3 > len(buffer):
                return None

            attribute_id = buffer[offset]
            attribute_length = struct.unpack_from("<H", buffer, offset + 1)[0]
            offset += 3

            if offset + attribute_length > len(buffer):
                return None

            attribute_value = buffer[offset:offset + attribute_length]
            offset += attribute_length
            attribute_name = ANCS_APP_ATTRIBUTE_NAMES.get(attribute_id, f"reserved_{attribute_id}")
            attributes[attribute_name] = self._decode_utf8(attribute_value)

        return {
            "type": "data_source",
            "response_type": "app_attributes",
            "command": ANCS_COMMAND_IDS[1],
            "app_identifier": app_identifier,
            "attributes": attributes,
            "raw_hex": buffer[:offset].hex(),
        }

    def _emit_ancs_event(self, event_name: str, parsed: Dict[str, Any], raw_data: bytes) -> None:
        if self.ancs_handler:
            self._invoke_handler(self.ancs_handler, event_name, parsed, raw_data)
        if self.event_handler:
            self._invoke_handler(self.event_handler, "ancs", event_name, parsed, raw_data)

    def _emit_ams_event(self, event_name: str, parsed: Dict[str, Any], raw_data: bytes) -> None:
        if self.ams_handler:
            self._invoke_handler(self.ams_handler, event_name, parsed, raw_data)
        if self.event_handler:
            self._invoke_handler(self.event_handler, "ams", event_name, parsed, raw_data)

    def _invoke_handler(self, handler: Callable[..., Any], *args: Any) -> None:
        try:
            result = handler(*args)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        except Exception as exc:
            logger.error(f"Apple service handler failed: {exc}", exc_info=True)

    def _decode_ancs_flags(self, flags: int) -> List[str]:
        names = []
        for bit, name in ANCS_EVENT_FLAGS.items():
            if flags & (1 << bit):
                names.append(name)
        return names

    def _normalize_ancs_notification_attribute_specs(self, attributes: Sequence[Any]) -> List[Tuple[int, Optional[int]]]:
        normalized = []
        for attribute in attributes:
            if isinstance(attribute, tuple):
                attribute_id = self._normalize_ancs_notification_attribute(attribute[0])
                max_length = int(attribute[1]) if attribute[1] is not None else None
            else:
                attribute_id = self._normalize_ancs_notification_attribute(attribute)
                max_length = 255 if attribute_id in ANCS_NOTIFICATION_ATTRIBUTES_WITH_LENGTH else None
            normalized.append((attribute_id, max_length))
        return normalized

    def _normalize_ancs_notification_attribute(self, attribute: Any) -> int:
        if isinstance(attribute, int):
            return attribute
        normalized_name = _normalize_name(str(attribute))
        if normalized_name not in ANCS_NOTIFICATION_ATTRIBUTE_IDS:
            raise ValueError(f"Unknown ANCS notification attribute: {attribute}")
        return ANCS_NOTIFICATION_ATTRIBUTE_IDS[normalized_name]

    def _normalize_ancs_app_attribute_specs(self, attributes: Sequence[Any]) -> List[int]:
        return [self._normalize_ancs_app_attribute(attribute) for attribute in attributes]

    def _normalize_ancs_app_attribute(self, attribute: Any) -> int:
        if isinstance(attribute, int):
            return attribute
        normalized_name = _normalize_name(str(attribute))
        if normalized_name not in ANCS_APP_ATTRIBUTE_IDS:
            raise ValueError(f"Unknown ANCS app attribute: {attribute}")
        return ANCS_APP_ATTRIBUTE_IDS[normalized_name]

    def _normalize_ancs_action(self, action: Any) -> int:
        if isinstance(action, int):
            return action
        normalized_name = _normalize_name(str(action))
        if normalized_name not in ANCS_ACTION_IDS:
            raise ValueError(f"Unknown ANCS action: {action}")
        return ANCS_ACTION_IDS[normalized_name]

    def _normalize_ams_command(self, command: Any) -> int:
        if isinstance(command, int):
            return command
        normalized_name = _normalize_name(str(command))
        if normalized_name not in AMS_REMOTE_COMMAND_IDS:
            raise ValueError(f"Unknown AMS remote command: {command}")
        return AMS_REMOTE_COMMAND_IDS[normalized_name]

    def _normalize_ams_entity(self, entity: Any) -> int:
        if isinstance(entity, int):
            return entity
        normalized_name = _normalize_name(str(entity))
        if normalized_name not in AMS_ENTITY_IDS:
            raise ValueError(f"Unknown AMS entity: {entity}")
        return AMS_ENTITY_IDS[normalized_name]

    def _normalize_ams_attribute(self, entity_id: int, attribute: Any) -> int:
        if isinstance(attribute, int):
            return attribute
        normalized_name = _normalize_name(str(attribute))
        if normalized_name not in AMS_ENTITY_ATTRIBUTE_IDS.get(entity_id, {}):
            raise ValueError(
                f"Unknown AMS attribute '{attribute}' for entity {AMS_ENTITY_NAMES.get(entity_id, entity_id)}"
            )
        return AMS_ENTITY_ATTRIBUTE_IDS[entity_id][normalized_name]

    def _ams_attribute_name(self, entity_id: int, attribute_id: int) -> str:
        return AMS_ENTITY_ATTRIBUTE_NAMES.get(entity_id, {}).get(attribute_id, f"reserved_{attribute_id}")

    def _decode_ams_attribute_value(self, entity_id: int, attribute_id: int, value: bytes) -> Any:
        decoded = self._decode_utf8(value)

        if entity_id == AMS_ENTITY_IDS["player"] and attribute_id == AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["player"]]["playback_info"]:
            return self._parse_ams_playback_info(decoded)

        if entity_id == AMS_ENTITY_IDS["player"] and attribute_id == AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["player"]]["volume"]:
            try:
                return float(decoded)
            except ValueError:
                return decoded

        if entity_id == AMS_ENTITY_IDS["queue"] and attribute_id in (
            AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["queue"]]["index"],
            AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["queue"]]["count"],
        ):
            try:
                return int(decoded)
            except ValueError:
                return decoded

        if entity_id == AMS_ENTITY_IDS["queue"] and attribute_id == AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["queue"]]["shuffle_mode"]:
            try:
                mode = int(decoded)
            except ValueError:
                return decoded
            return AMS_SHUFFLE_MODES.get(mode, mode)

        if entity_id == AMS_ENTITY_IDS["queue"] and attribute_id == AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["queue"]]["repeat_mode"]:
            try:
                mode = int(decoded)
            except ValueError:
                return decoded
            return AMS_REPEAT_MODES.get(mode, mode)

        if entity_id == AMS_ENTITY_IDS["track"] and attribute_id == AMS_ENTITY_ATTRIBUTE_IDS[AMS_ENTITY_IDS["track"]]["duration"]:
            try:
                return float(decoded)
            except ValueError:
                return decoded

        return decoded

    def _parse_ams_playback_info(self, playback_info: str) -> Dict[str, Any]:
        parts = [part.strip() for part in playback_info.split(",")]
        if len(parts) != 3:
            return {"raw": playback_info}

        try:
            state_value = int(parts[0])
        except ValueError:
            state_value = parts[0]

        try:
            playback_rate = float(parts[1])
        except ValueError:
            playback_rate = parts[1]

        try:
            elapsed_time = float(parts[2])
        except ValueError:
            elapsed_time = parts[2]

        return {
            "playback_state": AMS_PLAYER_PLAYBACK_STATES.get(state_value, state_value),
            "playback_rate": playback_rate,
            "elapsed_time_seconds": elapsed_time,
        }

    def _decode_utf8(self, value: bytes) -> str:
        return value.decode("utf-8", errors="replace")

    def _print_warning(self, title: str, message: str) -> None:
        if HAS_RICH and console:
            console.print(Panel(message, title=title, border_style="yellow", expand=False))
            return
        print(f"[{title}] {message}")

    def _print_ancs_notification(self, parsed: Dict[str, Any]) -> None:
        if HAS_RICH and console:
            if parsed.get("error"):
                console.print(
                    Panel(
                        f"{parsed['error']}\n{parsed.get('raw_hex', '')}",
                        title="ANCS Notification Source",
                        border_style="red",
                        expand=False,
                    )
                )
                return

            table = Table(title="ANCS Notification Source", box=box.ROUNDED, show_header=True, header_style="bold cyan")
            table.add_column("Field", style="yellow", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("Event", str(parsed.get("event", "-")))
            table.add_row("Category", str(parsed.get("category", "-")))
            table.add_row("Category Count", str(parsed.get("category_count", "-")))
            table.add_row("Notification UID", str(parsed.get("notification_uid", "-")))
            table.add_row("Flags", ", ".join(parsed.get("event_flag_names", [])) or "none")
            console.print(table)
            return

        print(self.format_ancs_notification(parsed))

    def _print_ancs_attribute_response(self, parsed: Dict[str, Any]) -> None:
        if HAS_RICH and console:
            if parsed.get("error"):
                console.print(
                    Panel(
                        parsed["error"],
                        title="ANCS Data Source",
                        border_style="red",
                        expand=False,
                    )
                )
                return

            title = "ANCS Notification Attributes"
            subject = parsed.get("notification_uid")
            if parsed.get("response_type") == "app_attributes":
                title = "ANCS App Attributes"
                subject = parsed.get("app_identifier")

            table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")
            table.add_column("Attribute", style="yellow", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("subject", str(subject))
            for name, value in parsed.get("attributes", {}).items():
                table.add_row(name, str(value))
            console.print(table)
            return

        print(self.format_ancs_attribute_response(parsed))

    def _print_ams_remote_commands(self, parsed: Dict[str, Any]) -> None:
        if HAS_RICH and console:
            table = Table(title="AMS Supported Remote Commands", box=box.ROUNDED, show_header=True, header_style="bold cyan")
            table.add_column("Command ID", style="yellow", no_wrap=True)
            table.add_column("Command", style="green")
            for command_id, name in zip(parsed.get("command_ids", []), parsed.get("commands", [])):
                table.add_row(str(command_id), name)
            if not parsed.get("command_ids"):
                table.add_row("-", "none")
            console.print(table)
            return

        print(self.format_ams_remote_commands(parsed))

    def _print_ams_entity_update(self, parsed: Dict[str, Any]) -> None:
        if HAS_RICH and console:
            if parsed.get("error"):
                console.print(
                    Panel(
                        f"{parsed['error']}\n{parsed.get('raw_hex', '')}",
                        title="AMS Entity Update",
                        border_style="red",
                        expand=False,
                    )
                )
                return

            table = Table(title="AMS Entity Update", box=box.ROUNDED, show_header=True, header_style="bold cyan")
            table.add_column("Field", style="yellow", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("Entity", str(parsed.get("entity", "-")))
            table.add_row("Attribute", str(parsed.get("attribute", "-")))
            table.add_row("Value", str(parsed.get("value", "-")))
            table.add_row("Truncated", "yes" if parsed.get("truncated") else "no")
            console.print(table)
            return

        print(self.format_ams_entity_update(parsed))

    def _print_ams_entity_attribute_read(self, parsed: Dict[str, Any]) -> None:
        if HAS_RICH and console:
            table = Table(title="AMS Entity Attribute Read", box=box.ROUNDED, show_header=True, header_style="bold cyan")
            table.add_column("Field", style="yellow", no_wrap=True)
            table.add_column("Value", style="green")
            table.add_row("Entity", str(parsed.get("entity", "-")))
            table.add_row("Attribute", str(parsed.get("attribute", "-")))
            table.add_row("Value", str(parsed.get("value", "-")))
            console.print(table)
            return

        print(self.format_ams_entity_attribute_read(parsed))
