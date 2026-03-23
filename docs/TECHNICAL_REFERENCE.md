# Technical Reference

> Advanced documentation for developers and technical users

---

## Table of Contents

1. [Architecture](#architecture)
2. [Bluetooth Protocol Stack](#bluetooth-protocol-stack)
3. [HCI Packet Format](#hci-packet-format)
4. [Ellisys Injection Protocol](#ellisys-injection-protocol)
5. [Bonding and Key Storage](#bonding-and-key-storage)
6. [GATT Operations](#gatt-operations)
7. [API Reference](#api-reference)

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────┐
│  User Application (src/main.py, your scripts)         │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────┐
│  BLE Operations Layer (connector.py, scanner.py)       │
│  - Connection management                                │
│  - GATT operations                                      │
│  - Pairing/bonding                                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────┐
│  Bumble Device Layer                                    │
│  - Device abstraction                                   │
│  - SMP (pairing) handling                               │
│  - L2CAP, ATT, GATT                                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────┐
│  Transport Layer (HCI over TCP)                         │
│  - HCI command/event exchange                           │
│  - Packet capture (optional)                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓ TCP Socket
                 │
┌─────────────────────────────────────────────────────────┐
│  HCI Bridge (bumble-hci-bridge)                         │
│  - TCP server (port 9001)                               │
│  - USB HCI adapter interface                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ↓ USB
                 │
┌─────────────────────────────────────────────────────────┐
│  Bluetooth USB Adapter                                  │
│  - Bluetooth 4.0+ controller                            │
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**src/main.py** - Interactive menu interface
- User interaction
- Menu rendering
- Operation orchestration

**src/connector.py** - BLE connection and GATT operations
- Device connection/disconnection
- Service discovery
- Characteristic read/write
- Notification subscriptions
- Pairing and encryption

**src/scanner.py** - BLE device scanning
- Advertisement monitoring
- Device filtering
- RSSI tracking

**src/hci_snooper.py** - HCI packet capture
- Packet interception
- Ellisys UDP injection
- BTSnoop file writing

**src/utils.py** - Shared utilities
- Address formatting
- UUID lookups
- Logging helpers

---

## Bluetooth Protocol Stack

### Protocol Layers

```
Application Layer
═══════════════════════
   GATT Profile
───────────────────────
   ATT Protocol
───────────────────────
   L2CAP
───────────────────────
   HCI
───────────────────────
   Link Layer (Radio)
```

### HCI Commands Used

| Command | Opcode | Purpose |
|---------|--------|---------|
| HCI_Reset | 0x0C03 | Reset controller |
| LE_Set_Scan_Parameters | 0x200B | Configure scan settings |
| LE_Set_Scan_Enable | 0x200C | Start/stop scanning |
| LE_Create_Connection | 0x200D | Initiate connection |
| Disconnect | 0x0406 | Terminate connection |
| LE_Read_Remote_Features | 0x2016 | Read peer features |
| LE_Start_Encryption | 0x2019 | Begin encryption |

### HCI Events Received

| Event | Code | Description |
|-------|------|-------------|
| Command_Complete | 0x0E | Command finished |
| Command_Status | 0x0F | Command status |
| Disconnection_Complete | 0x05 | Connection ended |
| LE_Meta_Event | 0x3E | LE-specific events |
| └─ LE_Advertising_Report | 0x02 | Advertisement packet |
| └─ LE_Connection_Complete | 0x01 | Connection established |
| └─ LE_Long_Term_Key_Request | 0x05 | LTK needed for encryption |

---

## HCI Packet Format

### Packet Types

```
 HCI COMMAND (Host → Controller)
 ┌────┬───────┬───────┬──────────────┐
 │ 01 │ OpCd  │ Len   │ Parameters   │
 │ 1B │ 2B LE │ 1B    │ 0-255 bytes  │
 └────┴───────┴───────┴──────────────┘

 HCI EVENT (Controller → Host)
 ┌────┬───────┬───────┬──────────────┐
 │ 04 │ EvtCd │ Len   │ Parameters   │
 │ 1B │ 1B    │ 1B    │ 0-255 bytes  │
 └────┴───────┴───────┴──────────────┘

 HCI ACL DATA (Bidirectional)
 ┌────┬───────┬───────┬──────────────┐
 │ 02 │ Handle│ Len   │ Data         │
 │ 1B │ 2B LE │ 2B LE │ 0-65535 bytes│
 └────┴───────┴───────┴──────────────┘
```

### Example: LE Create Connection

```
Command:
01 0D 20 19    → OpCode: 0x200D (LE_Create_Connection)
               → Parameter Length: 0x19 (25 bytes)
60 00          → Scan Interval: 0x0060 (96 * 0.625ms = 60ms)
30 00          → Scan Window: 0x0030 (48 * 0.625ms = 30ms)
00             → Initiator Filter Policy: 0 (peer address)
01             → Peer Address Type: 1 (Random)
AE CC DB 37 60 00 → Peer Address: 00:60:37:DB:CC:AE
00             → Own Address Type: 0 (Public)
...

Event (Command Status):
04 0F 04       → Event Code: 0x0F (Command_Status)
               → Parameter Length: 4
00             → Status: 0 (Success)
01             → Num HCI Command Packets: 1
0D 20          → Command OpCode: 0x200D

Event (Connection Complete):
04 3E 13       → Event Code: 0x3E (LE Meta Event)
               → Parameter Length: 19
01             → Subevent: 0x01 (LE_Connection_Complete)
00             → Status: 0 (Success)
40 00          → Connection Handle: 0x0040
01             → Role: 1 (Peripheral)
...
```

---

## Ellisys Injection Protocol

### UDP Packet Structure

Ellisys expects HCI packets wrapped in a specific format:

```
Ellisys UDP Packet Format (for HCI Injection Service 0x0002)
═══════════════════════════════════════════════════════════

┌────────────────────────────────────────────────┐
│ Service Object Header (3 bytes)                │
├────────────────────────────────────────────────┤
│ 0x02 0x00    Service ID: 0x0002 (HCI Inject)  │
│ 0x01         Version: 1                        │
└────────────────────────────────────────────────┘
┌────────────────────────────────────────────────┐
│ DateTime Object (10 bytes, Object ID 0x02)     │
├────────────────────────────────────────────────┤
│ 0x02         Object ID                         │
│ YYYY (2B LE) Year                              │
│ MM (1B)      Month                             │
│ DD (1B)      Day                               │
│ NNNNNN (6B LE) Nanos since midnight           │
└────────────────────────────────────────────────┘
┌────────────────────────────────────────────────┐
│ Bitrate Object (5 bytes, Object ID 0x80)      │
├────────────────────────────────────────────────┤
│ 0x80         Object ID                         │
│ BBBBBBBB (4B LE) Bitrate (e.g., 12000000)    │
└────────────────────────────────────────────────┘
┌────────────────────────────────────────────────┐
│ Packet Type Object (2 bytes, Object ID 0x81)  │
├────────────────────────────────────────────────┤
│ 0x81         Object ID                         │
│ TT           Type (0x01=CMD, 0x02=ACL_HOST... │
│              0x04=EVT, 0x82=ACL_CTRL)          │
└────────────────────────────────────────────────┘
┌────────────────────────────────────────────────┐
│ HCI Payload Object (2+ bytes, Object ID 0x83) │
├────────────────────────────────────────────────┤
│ 0x83         Object ID                         │
│ LL (1B)      Payload Length                    │
│ HCI Packet   Actual HCI packet bytes           │
└────────────────────────────────────────────────┘
```

### Packet Type Mappings

| HCI Type | Bumble Name | Ellisys Type | Direction |
|----------|-------------|--------------|-----------|
| 0x01 | CMD | 0x01 | Host → Controller |
| 0x02 | ACL | 0x02 | Host → Controller |
| 0x02 | ACL | 0x82 | Controller → Host |
| 0x04 | EVT | 0x04 | Controller → Host |

### Python Implementation

```python
def encode_ellisys_packet(hci_packet: bytes, packet_type: int, 
                         direction: str) -> bytes:
    """Encode HCI packet for Ellisys injection"""
    
    # Service header
    service_header = struct.pack('<HB', 0x0002, 0x01)
    
    # Timestamp
    now = datetime.now()
    nanos_since_midnight = (
        now.hour * 3600 + now.minute * 60 + now.second
    ) * 1_000_000_000 + now.microsecond * 1000
    
    datetime_obj = struct.pack(
        '<BHBBQ',
        0x02,  # Object ID
        now.year,
        now.month,
        now.day,
        nanos_since_midnight
    )
    
    # Bitrate
    bitrate_obj = struct.pack('<BI', 0x80, 12_000_000)
    
    # Packet type
    ellisys_type = packet_type
    if packet_type == 0x02:  # ACL
        ellisys_type = 0x82 if direction == 'controller_to_host' else 0x02
    
    type_obj = struct.pack('<BB', 0x81, ellisys_type)
    
    # Payload
    payload_obj = struct.pack('<BB', 0x83, len(hci_packet)) + hci_packet
    
    return service_header + datetime_obj + bitrate_obj + type_obj + payload_obj
```

---

## Bonding and Key Storage

### Bond Storage Format

Keys stored in `configs/bumble_bonds.json`:

```json
{
  "bonds": {
    "00:60:37:DB:CC:AE": {
      "ltk": "0102030405060708090a0b0c0d0e0f10",
      "ediv": 1234,
      "rand": "1122334455667788",
      "irk": "a1a2a3a4a5a6a7a8a9aaabacadaeafb0",
      "csrk": "b1b2b3b4b5b6b7b8b9babbbcbdbebfc0",
      "peer_irk": null,
      "peer_csrk": null
    }
  }
}
```

### Persistent CCCD Subscription Storage

The app stores persistent CCCD subscription preferences in the same bond file,
alongside peer key material, under an internal key:

```json
{
    "<local_address>": {
        "<peer_address>": {
            "ltk": { "value": "..." },
            "irk": { "value": "..." },
            "_hciemu_cccd": {
                "88": "notify",
                "93": "indicate"
            }
        }
    }
}
```

Restore behavior is controlled by `auto_restore_cccd_on_reconnect` in
`ui_config.json`:

- `true`: after bonded reconnect and successful encryption, the app discovers services and restores saved CCCD subscriptions.
- `false`: no automatic restore; user subscribes manually.

### Key Types

| Key | Purpose | Size |
|-----|---------|------|
| **LTK** (Long Term Key) | Link encryption | 128-bit |
| **EDIV** (Encrypted Diversifier) | LTK identifier | 16-bit |
| **RAND** (Random) | LTK identifier | 64-bit |
| **IRK** (Identity Resolving Key) | Address resolution | 128-bit |
| **CSRK** (Connection Signature Resolving Key) | Signed writes | 128-bit |

### Pairing Process

```
Central (Us)              Peripheral (Device)
     │                            │
     │  Pairing Request           │
     ├──────────────────────────→ │
     │                            │
     │  Pairing Response          │
     │ ←──────────────────────────┤
     │                            │
     │  Exchange capabilities     │
     │  Determine pairing method  │
     │                            │
     │  [Authentication]          │
     │  (Passkey, Just Works, etc)│
     │                            │
     │  Key Exchange              │
     │ ←─────────────────────────→│
     │  (LTK, IRK, CSRK)          │
     │                            │
     │  Pairing Complete          │
     │                            │
     [Keys saved to configs/bumble_bonds.json]
```

### Security Levels

| Level | Encryption | Authentication | MITM Protection |
|-------|------------|----------------|-----------------|
| 1 | No | No | No |
| 2 | Yes | No | No |
| 3 | Yes | Yes | No |
| 4 | Yes | Yes | Yes |

---

## GATT Operations

### ATT Protocol Methods

| Method | Request | Response | Use Case |
|--------|---------|----------|----------|
| **Read** | Read Request | Read Response | Read characteristic value |
| **Write** | Write Request | Write Response | Write with confirmation |
| **Write Cmd** | Write Command | (none) | Write without confirmation |
| **Notify** | (none) | Handle Value Notification | Server-initiated update |
| **Indicate** | (none) | Handle Value Indication | Server-initiated update with ACK |

### Handle Management

```
GATT Database Handle Layout:
╔═══════════════════════════════════════╗
║ Handle │ Type       │ UUID           ║
╠═══════════════════════════════════════╣
║ 0x0001 │ Service    │ 0x1800 (GAP)   ║
║ 0x0002 │ Include    │ ...            ║
║ 0x0003 │ Char Decl  │ 0x2A00 (Name)  ║
║ 0x0004 │ Char Value │ 0x2A00         ║
║ 0x0005 │ Descriptor │ 0x2901         ║
║ ...    │ ...        │ ...            ║
╚═══════════════════════════════════════╝

Important:
- Service starts at declaration handle
- Characteristic uses TWO handles: declaration + value
- Descriptors follow characteristic value
- CCC descriptor (0x2902) enables notifications
```

### Notification Subscription

To enable notifications:

```python
# 1. Find characteristic handle (e.g., 0x0012)
# 2. Find CCC descriptor (usually handle + 1, e.g., 0x0013)
# 3. Write 0x0001 to CCC descriptor

ccc_value = struct.pack('<H', 0x0001)  # Enable notifications
await connection.write_value(ccc_handle, ccc_value)

# For indications:
ccc_value = struct.pack('<H', 0x0002)  # Enable indications

# To disable:
ccc_value = struct.pack('<H', 0x0000)  # Disable
```

---

## API Reference

### BLEConnector Class

```python
from connector import BLEConnector

connector = BLEConnector(transport_spec="tcp-client:127.0.0.1:9001")
```

#### Methods

**connect(address: str) → Connection**
```python
connection = await connector.connect("00:60:37:DB:CC:AE")
```
Connect to BLE device at specified address.

**discover_services(force_fresh: bool = False) → Dict**
```python
services = await connector.discover_services()
# Returns: {service_uuid: [characteristics], ...}
```
Discover all GATT services and characteristics.

**read_characteristic(handle: int) → bytes**
```python
value = await connector.read_characteristic(0x0012)
```
Read value from characteristic handle.

**write_characteristic(handle: int, value: bytes) → bool**
```python
success = await connector.write_characteristic(0x0020, b'\x01\x02\x03')
```
Write value to characteristic with response.

**write_without_response(handle: int, value: bytes) → bool**
```python
success = await connector.write_without_response(0x0020, b'\x01\x02\x03')
```
Write value without waiting for response.

**subscribe_notifications(handle: int) → bool**
```python
success = await connector.subscribe_notifications(0x0012)
```
Subscribe to notifications from characteristic.

**pair() → bool**
```python
success = await connector.pair()
```
Initiate pairing with connected device.

**disconnect() → None**
```python
await connector.disconnect()
```
Disconnect from device.

### BLEScanner Class

```python
from scanner import BLEScanner

scanner = BLEScanner(transport_spec="tcp-client:127.0.0.1:9001")
```

#### Methods

**scan(duration: int, active: bool = True, filter_duplicates: bool = True) → Dict**
```python
devices = await scanner.scan(duration=10, active=True)
# Returns: {address: {name, rssi, data}, ...}
```
Scan for BLE devices.

### HCISnooper Class

```python
from hci_snooper import HCISnooper

snooper = HCISnooper(
    ellisys_host="127.0.0.1",
    ellisys_port=24352,
    btsnoop_file="capture.log",
    stream="primary"
)
```

#### Methods

**start() → None**
```python
await snooper.start()
```
Begin packet capture.

**stop() → None**
```python
await snooper.stop()
```
End packet capture.

---

## Performance Considerations

### Connection Parameters

| Parameter | Typical Value | Impact |
|-----------|---------------|--------|
| Connection Interval | 7.5ms - 4s | Latency vs power |
| Slave Latency | 0-499 | Power savings |
| Supervision Timeout | 100ms - 32s | Connection reliability |

### Throughput Limits

- **BLE 4.2**: ~250 kbps practical throughput
- **BLE 5.0**: ~800 kbps (with 2M PHY)
- **BLE 5.1+**: ~1.4 Mbps (with Coded PHY + DLE)

### Memory Usage

- **Bonds**: ~200 bytes per device
- **Service cache**: ~1-5 KB per device
- **HCI capture**: ~100 bytes per packet

---

## Security Best Practices

1. **Always validate UUIDs** before reading/writing
2. **Use encryption** for sensitive data
3. **Implement timeouts** for all operations
4. **Sanitize user input** for hex values
5. **Store bonds securely** (encrypt configs/bumble_bonds.json if needed)
6. **Clear sensitive data** from memory after use
7. **Use MITM protection** when pairing
8. **Verify peer identity** when reconnecting

---

## Development Tips

### Debugging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Bumble debug logs
logging.getLogger('bumble').setLevel(logging.DEBUG)
```

### Testing

```bash
# Test scan
python examples/scan_devices.py

# Test connection
python examples/basic_connection.py

# Test capture
python examples/hci_capture.py
```

### Common Patterns

**Retry logic:**
```python
async def retry_operation(func, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(1)
```

**Timeout wrapper:**
```python
async def with_timeout(coro, timeout=10.0):
    return await asyncio.wait_for(coro, timeout)
```

---

## Further Reading

- [Bumble Documentation](https://google.github.io/bumble/)
- [Bluetooth Core Specification](https://www.bluetooth.com/specifications/specs/)
- [GATT Specification](https://www.bluetooth.com/specifications/specs/gatt-specification-supplement/)
- [HCI Specification](https://www.bluetooth.com/specifications/specs/core-specification/)

---

**For general usage, see [USER_MANUAL.md](USER_MANUAL.md)**
