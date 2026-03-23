# BLETestingApp API Reference

This is a script-first reference for `BLETestingApp` in `src/app.py`.

It uses collapsible sections so you can scan signatures quickly and expand only what you need.

## Contents

- [Quick Start](#quick-start)
- [Reference Style Notes](#reference-style-notes)
- [Class State Variables](#class-state-variables)
- [Lifecycle and Connection](#lifecycle-and-connection)
- [Scanning and Filters](#scanning-and-filters)
- [HCI Snoop and Debug Logging](#hci-snoop-and-debug-logging)
- [GATT Operations](#gatt-operations)
- [Burst Operations](#burst-operations)
- [CSV Logging](#csv-logging)
- [SMP and Bonding](#smp-and-bonding)
- [Optional Menu Runner](#optional-menu-runner)
- [Internal Helpers](#internal-helpers)

## Quick Start

```python
import asyncio
from src.app import BLETestingApp


async def main():
    app = BLETestingApp("tcp-client:127.0.0.1:9001")

    await app.app_bluetooth_on()
    await app.app_scan_devices(duration=5, filter_duplicates=True, active_scan=True)

    # Replace with a real address found during scan
    await app.connect("AA:BB:CC:DD:EE:FF", timeout=30.0)

    await app.app_discover_services()
    await app.app_read_characteristic("0x0012")

    await app.app_disconnect()
    await app.app_bluetooth_off()


if __name__ == "__main__":
    asyncio.run(main())
```

## Reference Style Notes

- Handles can be decimal strings (`"84"`) or hex strings (`"0x0054"`).
- Hex payload supports spaced or compact text (`"01 02 A0"` or `"0102A0"`).
- Async methods should be called with `await`.

## Class State Variables

These are class instance attributes (not module-level globals). Access them via your app instance, for example `app.discovered_devices`.

<details>
<summary><code>Connection and Scan State</code></summary>

| Attribute | Type | Typical Use |
|---|---|---|
| `transport_spec` | `str` | Current transport string used to create HCI transport. |
| `discovered_devices` | `dict` | Last scan result map keyed by address. |
| `connected` | `bool` | Connection status flag for current session. |
| `current_device` | `Optional[str]` | Connected peer address (if connected). |
| `filter_name` | `Optional[str]` | Name substring filter used during scanning. |
| `filter_address` | `Optional[str]` | Address substring filter used during scanning. |

Recommended pattern:
- Read these directly for status dashboards.
- Prefer calling `app_set_filters(...)` and `app_scan_devices(...)` instead of manual mutation.

</details>

<details>
<summary><code>Snoop and Debug Configuration</code></summary>

| Attribute | Type | Typical Use |
|---|---|---|
| `debug_mode` | `str` | Current debug output mode (`none`, `console`, `file`, `both`). |
| `snoop_enabled` | `bool` | Runtime flag indicating snoop is currently active. |
| `ellisys_host` | `str` | UDP destination host for Ellisys output. |
| `ellisys_port` | `int` | UDP destination port for Ellisys output. |
| `btsnoop_filename` | `str` | Capture output file path. |
| `ellisys_stream` | `str` | Stream selection (`primary`, `secondary`, `tertiary`). |
| `snoop_console_logging` | `bool` | Whether packet logs are echoed in console. |
| `snoop_auto_enable` | `bool` | Whether startup auto-enable is requested via config. |
| `snoop_ellisys_enabled` | `bool` | Whether UDP Ellisys sink is enabled. |
| `snoop_file_enabled` | `bool` | Whether capture file sink is enabled. |
| `auto_restore_cccd_on_reconnect` | `bool` | Whether bonded reconnect should auto-discover services and restore persisted CCCD subscriptions. |

Recommended pattern:
- Use `app_toggle_hci_snoop(...)` and `app_debug_logging(...)` to update these consistently.

</details>

<details>
<summary><code>Advanced/Internal Runtime Flags</code></summary>

| Attribute | Type | Notes |
|---|---|---|
| `_scan_transport` | object | Active Bumble transport instance. |
| `_scan_device` | object | Active Bumble device wrapper for scan/connect. |
| `_scan_ready` | `bool` | Internal readiness flag for scan device lifecycle. |
| `_scan_adv_handler` | callable | Current registered advertisement callback. |
| `_suppress_adv_printing` | `bool` | Temporarily suppresses advertisement logging. |
| `_connect_in_progress` | `bool` | Connection-attempt flag used by timeout/callback logic. |
| `_connect_target_address` | `Optional[str]` | Address currently being connected. |
| `_post_connect_task` | `Optional[asyncio.Task]` | Post-connect setup task handle. |
| `_connect_auto_encrypt_if_bonded` | `bool` | Connection-time bonded-encryption policy snapshot. |
| `_security_request_task` | `Optional[asyncio.Task]` | Task handling peer security request. |
| `_pairing_task` | `Optional[asyncio.Task]` | Active pairing task handle. |
| `_pairing_in_progress` | `bool` | Pairing status flag. |

Recommended pattern:
- Avoid writing these directly unless extending internals.
- If you need behavior changes, use public APIs first.

</details>

### Using State in Scripts

```python
# Read state
print(app.connected)
print(len(app.discovered_devices))

# Update state using public methods (preferred)
await app.app_set_filters(name_filter="RoadSync")
await app.app_scan_devices(duration=3)

# Direct reads are fine for telemetry/reporting
for addr, info in app.discovered_devices.items():
    print(addr, info.get("rssi"), info.get("name"))
```

### Dictionary Structures

This section describes the expected shape for dict-based state and data.

<details>
<summary><code>discovered_devices</code> (after <code>app_scan_devices(...)</code>)</summary>

Type:
- `dict[str, dict]`

Top-level key:
- Advertiser address string, for example `"00:60:37:08:F5:D7/P"`.

Per-device value fields:

| Key | Type | Description |
|---|---|---|
| `address` | `str` | Advertiser address (same value as top-level key). |
| `rssi` | `int` | Last observed RSSI for that address. |
| `data` | `str` | String form of advertisement data (if available). |
| `data_hex` | `str` | Hex-encoded raw advertisement payload bytes. |
| `name` | `str` or `None` | Decoded local name if present. |
| `last_printed_data_hex` | `str` | Last payload printed in detail output. |
| `details_printed` | `bool` | Internal print-control flag. |

Example:

```json
{
    "00:60:37:08:F5:D7/P": {
        "address": "00:60:37:08:F5:D7/P",
        "rssi": -57,
        "data": "AdvertisingData(...)",
        "data_hex": "0201060c09426c756554657374",
        "name": "BlueTest",
        "last_printed_data_hex": "0201060c09426c756554657374",
        "details_printed": true
    }
}
```

</details>

<details>
<summary><code>uuid_name_map</code> and <code>ad_type_name_map</code> (resource maps)</summary>

Type:
- `uuid_name_map`: `dict[str, str]`
- `ad_type_name_map`: `dict[int, str]`

Purpose:
- `uuid_name_map` maps UUID aliases to friendly names.
- `ad_type_name_map` maps AD type numeric values to names.

Example:

```json
{
    "uuid_name_map": {
        "180f": "Battery Service",
        "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service"
    },
    "ad_type_name_map": {
        "9": "Complete Local Name",
        "255": "Manufacturer Specific Data"
    }
}
```

Note:
- In JSON, integer keys are shown as strings. In Python, `ad_type_name_map` keys are integers.

</details>

<details>
<summary><code>ui_config.json</code> structure (persisted runtime config)</summary>

Type:
- `dict[str, Any]`

Schema:

```json
{
    "filter_name": "BLE",
    "filter_address": "00:60:37",
    "debug_mode": "none",
    "auto_restore_cccd_on_reconnect": true,
    "hci_snoop": {
        "enabled": false,
        "enable_ellisys": true,
        "enable_file": true,
        "ellisys_host": "127.0.0.1",
        "ellisys_port": 24352,
        "btsnoop_filename": "logs/hci_capture.log",
        "ellisys_stream": "primary",
        "snoop_console_logging": false
    }
}
```

Used by:
- `_load_ui_config()` and `_save_ui_config()`.

Behavior:
- `auto_restore_cccd_on_reconnect`: If `true`, bonded reconnect flow performs encrypted reconnect recovery by discovering services and restoring persisted Notify/Indicate subscriptions.

</details>

<details>
<summary><code>smp_config.json</code> structure (persisted SMP config)</summary>

Type:
- `dict[str, Any]`

Schema:

```json
{
    "io_capability": "DISPLAY_OUTPUT_AND_KEYBOARD_INPUT",
    "mitm_required": true,
    "le_secure_connections": true,
    "min_enc_key_size": 7,
    "max_enc_key_size": 16,
    "bonding_enabled": true,
    "auto_pair_encrypt_on_security_request": true,
    "auto_encrypt_if_bonded": true
}
```

Behavior:
- `auto_pair_encrypt_on_security_request`: Controls automatic pairing/encryption handling when a peer sends an SMP security request.
- `auto_encrypt_if_bonded`: Controls automatic encryption attempt after connection when the peer is already bonded.

Note:
- CCCD subscription state is stored with bond data in `bumble_bonds.json` under internal key `_hciemu_cccd` for each peer entry.

</details>

## Lifecycle and Connection

<details>
<summary><code>BLETestingApp(transport_spec: str = "tcp-client:127.0.0.1:9001")</code></summary>

Creates the application object.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `transport_spec` | `str` | No | Bumble transport string. |

</details>

<details>
<summary><code>connect(address: str, timeout: float = 30.0, auto_encrypt_if_bonded: Optional[bool] = None)</code></summary>

Connects to a BLE peripheral.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `address` | `str` | Yes | Peer address, for example `AA:BB:CC:DD:EE:FF`. |
| `timeout` | `float` | No | Timeout in seconds. |
| `auto_encrypt_if_bonded` | `Optional[bool]` | No | If `True`, auto-encrypt when peer is already bonded. If `None`, uses SMP config. |

</details>

<details>
<summary><code>app_disconnect()</code></summary>

Disconnects current link if connected.

</details>

## Scanning and Filters

<details>
<summary><code>app_bluetooth_on()</code></summary>

Initializes transport, creates scanner device, and powers on controller.

</details>

<details>
<summary><code>app_bluetooth_off()</code></summary>

Stops scanning if needed and powers off controller.

</details>

<details>
<summary><code>app_set_filters(clear: bool = False, name_filter: Optional[str] = None, address_filter: Optional[str] = None)</code></summary>

Configures scan filters.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `clear` | `bool` | No | Clear both filters when `True`. |
| `name_filter` | `Optional[str]` | No | Case-insensitive name substring. |
| `address_filter` | `Optional[str]` | No | Case-insensitive address substring. |

</details>

<details>
<summary><code>app_scan_devices(duration: int = 10, filter_duplicates: bool = True, active_scan: bool = True)</code></summary>

Performs a BLE scan and updates `discovered_devices`.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `duration` | `int` | No | Scan duration in seconds. |
| `filter_duplicates` | `bool` | No | Suppress duplicate advertiser reports. |
| `active_scan` | `bool` | No | Request scan responses when `True`. |

</details>

<details>
<summary><code>print_scan_menu()</code></summary>

Prints the currently discovered devices table.

</details>

## HCI Snoop and Debug Logging

<details>
<summary><code>app_toggle_hci_snoop(enable: Optional[bool] = None, ellisys_host: Optional[str] = None, ellisys_port: Optional[int] = None, ellisys_stream: Optional[str] = None, btsnoop_filename: Optional[str] = None, enable_ellisys: Optional[bool] = None, enable_file: Optional[bool] = None, enable_console: Optional[bool] = None)</code></summary>

Enables/disables HCI snoop outputs.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `enable` | `Optional[bool]` | Yes | `True` to enable, `False` to disable. |
| `ellisys_host` | `Optional[str]` | No | UDP host for Ellisys output. |
| `ellisys_port` | `Optional[int]` | No | UDP port (0-65535). |
| `ellisys_stream` | `Optional[str]` | No | `primary`, `secondary`, or `tertiary`. |
| `btsnoop_filename` | `Optional[str]` | No | Capture file path (`.log` or `.btsnoop`). |
| `enable_ellisys` | `Optional[bool]` | No | Enable/disable UDP sink. |
| `enable_file` | `Optional[bool]` | No | Enable/disable file sink. |
| `enable_console` | `Optional[bool]` | No | Enable/disable packet console output. |

</details>

<details>
<summary><code>app_debug_logging(mode: str)</code></summary>

Sets debug logging mode.

Valid `mode` values:
- `none`
- `console`
- `file`
- `both`

</details>

## GATT Operations

<details>
<summary><code>app_discover_services()</code></summary>

Discovers and prints services, characteristics, and descriptors.

</details>

<details>
<summary><code>app_read_characteristic(handle: str, show_table: bool = False)</code></summary>

Reads a characteristic value by handle.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `handle` | `str` | Yes | Decimal or hex handle string. |
| `show_table` | `bool` | No | Print filtered characteristics table before read. |

</details>

<details>
<summary><code>app_write_characteristic(handle: str, hex_value: str, show_table: bool = False)</code></summary>

Writes a characteristic with response.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `handle` | `str` | Yes | Decimal or hex handle string. |
| `hex_value` | `str` | Yes | Hex payload (spaced or compact). |
| `show_table` | `bool` | No | Print filtered characteristics table before write. |

</details>

<details>
<summary><code>app_write_without_response(handle: str, hex_value: str, show_table: bool = False)</code></summary>

Writes a characteristic without response.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `handle` | `str` | Yes | Decimal or hex handle string. |
| `hex_value` | `str` | Yes | Hex payload (spaced or compact). |
| `show_table` | `bool` | No | Print filtered characteristics table before write. |

</details>

<details>
<summary><code>app_subscribe(handle: str, show_table: bool = False)</code></summary>

Subscribes to notifications.

</details>

<details>
<summary><code>app_subscribe_indications(handle: str, show_table: bool = False)</code></summary>

Subscribes to indications.

</details>

## Burst Operations

<details>
<summary><code>app_burst_write(handle: str, hex_value: str, count: int = 0, interval_ms: int = 100, show_table: bool = False)</code></summary>

Starts repeated write with response.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `handle` | `str` | Yes | Decimal or hex handle string. |
| `hex_value` | `str` | Yes | Hex payload. |
| `count` | `int` | No | Number of writes; `0` means infinite. |
| `interval_ms` | `int` | No | Delay between writes in ms. |
| `show_table` | `bool` | No | Print table before start. |

</details>

<details>
<summary><code>app_burst_write_without_response(handle: str, hex_value: str, count: int = 0, interval_ms: int = 100, show_table: bool = False)</code></summary>

Starts repeated write without response.

</details>

<details>
<summary><code>app_stop_burst_write()</code></summary>

Stops active burst write task.

</details>

<details>
<summary><code>app_burst_read(handle: str, count: int = 0, interval_ms: int = 100, print_each_read: bool = False, show_table: bool = False)</code></summary>

Starts repeated read operation.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `handle` | `str` | Yes | Decimal or hex handle string. |
| `count` | `int` | No | Number of reads; `0` means infinite. |
| `interval_ms` | `int` | No | Delay between reads in ms. |
| `print_each_read` | `bool` | No | Print each sampled value. |
| `show_table` | `bool` | No | Print table before start. |

</details>

<details>
<summary><code>app_stop_burst_read()</code></summary>

Stops active burst read task.

</details>

## CSV Logging

<details>
<summary><code>app_start_csv_logging(filename: Optional[str] = None)</code></summary>

Starts CSV logging for notification/indication values.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `filename` | `Optional[str]` | No | Output path. If omitted, timestamp naming is used. |

</details>

<details>
<summary><code>app_stop_csv_logging()</code></summary>

Stops CSV logging.

</details>

## SMP and Bonding

<details>
<summary><code>app_smp_settings()</code></summary>

Prints current SMP configuration values.

</details>

<details>
<summary><code>app_smp_auto_pair_encrypt(enabled: bool)</code></summary>

Enables/disables auto pair or encrypt behavior on security request.

</details>

<details>
<summary><code>app_smp_auto_encrypt_if_bonded(enabled: bool)</code></summary>

Enables/disables automatic encryption when connecting to an already bonded device.

</details>

<details>
<summary><code>app_auto_restore_cccd_on_reconnect(enabled: bool)</code></summary>

Enables/disables automatic CCCD restore after bonded reconnect.

When enabled:
- reconnect to bonded peer
- establish encryption
- discover services
- restore persisted notification/indication subscriptions from bond data

</details>

<details>
<summary><code>app_smp_io_capability(io_capability: str)</code></summary>

Sets SMP IO capability.

Valid values:
- `DISPLAY_ONLY`
- `KEYBOARD_ONLY`
- `NO_INPUT_NO_OUTPUT`
- `KEYBOARD_DISPLAY`
- `DISPLAY_OUTPUT_AND_KEYBOARD_INPUT`

</details>

<details>
<summary><code>app_smp_mitm_required(required: bool)</code></summary>

Sets MITM requirement.

</details>

<details>
<summary><code>app_smp_secure_connections(enabled: bool)</code></summary>

Enables/disables LE Secure Connections.

</details>

<details>
<summary><code>app_smp_encryption_key_size(min_size: int = 7, max_size: int = 16)</code></summary>

Sets encryption key size range.

Constraints:
- `7 <= min_size <= 16`
- `7 <= max_size <= 16`
- `min_size <= max_size`

</details>

<details>
<summary><code>app_smp_bonding(enabled: bool)</code></summary>

Enables/disables bond persistence.

</details>

<details>
<summary><code>app_pair()</code></summary>

If bonded, verifies/enables encryption. If unbonded, starts pairing.

</details>

<details>
<summary><code>app_unpair(index: Optional[int] = None, address: Optional[str] = None)</code></summary>

Removes a bonded device by either list index or exact address.

</details>

## Optional Menu Runner

<details>
<summary><code>run(choices)</code></summary>

Runs legacy menu flow from a provided iterable of options.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `choices` | iterable | Yes | Sequence like `["a", "1", "0"]`. |

Direct app method calls are preferred for automation.

</details>

## Internal Helpers

The following methods are internal lifecycle/helpers and usually should not be called directly from scripts:

- `_load_ui_config`, `_save_ui_config`
- `_event_names_from_emitter`, `_register_device_events`, `_register_connection_events`
- `_on_pairing_start`, `_on_connection_encryption_change`, `_on_connection_encryption_failure`
- `_on_connection_encryption_key_refresh`, `_on_connection_parameters_update`
- `_on_pairing_complete`, `_on_pairing_failure`, `_on_security_request`
- `_start_pairing_non_blocking`, `_handle_security_request_async`
- `_cancel_connect_on_timeout`, `_handle_connection_ready`
- `_load_resource_maps`, `_parse_simple_yaml_list`, `_uuid_aliases`
- `_lookup_uuid_name`, `_format_uuid_with_name`, `_parse_handle`
- `_format_advertisement_details`, `_print_advertisement_details`, `_matches_filters`
- `_auto_enable_hci_snoop_on_startup`, `_enable_hci_snoop`, `_disable_hci_snoop`
- `_configure_debug_logging`, `_get_scan_device`, `_close_scan_device`, `_do_scan`
- `_maybe_show_discovery_table`, `_show_characteristics_table`, `_print_read_value`
