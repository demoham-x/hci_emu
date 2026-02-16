# Ellisys Injection API - Visual Guide

## Packet Structure Diagram

```
ELLISYS HCI INJECTION PACKET
═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│ SERVICE OBJECT HEADER (3 bytes)                             │
├─────────────────────────────────────────────────────────────┤
│ Service ID:  0x0002 (2 bytes, little-endian)               │
│ Version:     0x01 (1 byte)                                 │
├─────────────────────────────────────────────────────────────┤
│ Identifies this as HCI Injection Service (not BTSnoop!)    │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ DATETIME OBJECT (10 bytes)                                  │
├─────────────────────────────────────────────────────────────┤
│ Object ID:   0x02 (1 byte)                                 │
│ Year:        YYYY (2 bytes, little-endian)                 │
│ Month:       MM (1 byte)                                   │
│ Day:         DD (1 byte)                                   │
│ Nanoseconds: NNNNNNNNNNNNNNNN (6 bytes, little-endian)    │
│              Since midnight (00:00:00)                      │
├─────────────────────────────────────────────────────────────┤
│ Provides timestamp for packet                              │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ BITRATE OBJECT (5 bytes)                                    │
├─────────────────────────────────────────────────────────────┤
│ Object ID:   0x80 (1 byte)                                 │
│ Bitrate:     BBBBBBBB (4 bytes, little-endian)            │
│              Usually 12,000,000 bps (12 Mbps) for USB FS  │
├─────────────────────────────────────────────────────────────┤
│ Indicates link speed (for reference)                       │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ HCI PACKET TYPE OBJECT (2 bytes)                            │
├─────────────────────────────────────────────────────────────┤
│ Object ID:   0x81 (1 byte)                                 │
│ Type:        TT (1 byte)                                   │
│                                                             │
│ Type Mappings:                                              │
│   0x01 = CMD (Command from Host to Controller)             │
│   0x02 = ACL_HOST (ACL from Host to Controller)            │
│   0x82 = ACL_CTRL (ACL from Controller to Host)            │
│   0x03 = SCO_HOST (SCO from Host to Controller)            │
│   0x83 = SCO_CTRL (SCO from Controller to Host)            │
│   0x84 = EVT (Event/Response from Controller to Host)      │
├─────────────────────────────────────────────────────────────┤
│ Tells Ellisys what type of HCI packet this is             │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ HCI PACKET DATA OBJECT (1 + N bytes)                        │
├─────────────────────────────────────────────────────────────┤
│ Object ID:   0x82 (1 byte)                                 │
│ Data:        DDDDDDDDDD... (N bytes)                       │
│              Raw HCI packet without type prefix            │
│                                                             │
│ Examples:                                                   │
│   CMD: 03 0C 00 (HCI Reset)                                │
│   EVT: 0E 04 01 03 0C 00 (Command Complete)               │
│   ACL: ... (ACL Data payload)                              │
├─────────────────────────────────────────────────────────────┤
│ Contains the actual HCI packet payload                     │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
Total: ~20-30+ bytes per packet (depending on HCI payload size)
```

---

## Example: HCI Reset Command

```
HCI RESET COMMAND PACKET (Full Breakdown)
══════════════════════════════════════════════════════════════

Hex Dump:
02 00 01 02 18 0B 06 00 00 40 1E 01 00 00 00 00 00 00 80 AE 02 00 00 81 01 82 03 0C 00
│  │  │  │ │  │  │  │  │  │  │  │  │  │  │  │  │  │  │ │      │ │  │ │  │
│  │  │  │ └──────────────────────────┬──────────────────────────┘ │  │ │  │
│  │  │  │                   DateTime (10 bytes)              │ │  │
│  │  │  │ Year: 0x0B18 = 2840 (LE)              │ │  │
│  │  │  │ Month: 06, Day: 00                    │ │  │
│  │  │  │ NS: 6 bytes: 00 40 1E 01 00 00        │ │  │
│  │  │  │                                        │ │  │
│  │  │  └── DateTime Object ID (0x02)          │ │  │
│  │  │                                          │ │  │
│  │  └─────── Service Version (0x01)           │ │  │
│  │                                             │ │  │
│  └────────── Service ID (0x0002 LE)           │ │  │
│                                                │ │  │
├─ Service Header Info ─────────────────────────┤ │  │
│                                                │ │  │
└─ Bitrate Object (0x80) ──────────────────────┘ │  │
   AE 02 00 00 = 12,000,000 bps (LE)            │  │
                                                  │  │
┌─ HCI Packet Type Object (0x81) ───────────────┘  │
   01 = 0x01 (Command)                             │
                                                     │
┌─ HCI Packet Data Object (0x82) ────────────────┘
   03 0C 00 = HCI Reset command
     03 0C = OpCode (0x0C03 = Reset)
     00 = Parameters (0 bytes)

══════════════════════════════════════════════════════════════
```

---

## Before vs After Comparison

```
BEFORE (WRONG - Pure BTSnoop Format)
╔════════════════════════════════════════════════════════════╗
║ [BTSnoop Record Header: 24 bytes]                          ║
║  - Original Length                                         ║
║  - Included Length                                         ║
║  - Flags (sent/received)                                  ║
║  - Drops counter                                           ║
║  - Timestamp (high 32-bit)                                ║
║  - Timestamp (low 32-bit)                                 ║
║ [HCI Type: 1 byte]                                         ║
║ [HCI Data: N bytes]                                        ║
║                                                            ║
║ Result: ❌ Ellisys doesn't recognize as HCI injection    ║
╚════════════════════════════════════════════════════════════╝


AFTER (CORRECT - Ellisys Injection API)
╔════════════════════════════════════════════════════════════╗
║ [Service ID: 0x0002] (2 bytes)                             ║
║ [Version: 0x01] (1 byte)                                   ║
║   → Identifies as HCI Injection Service                    ║
║                                                            ║
║ [DateTime Object: 0x02] (10 bytes)                         ║
║   → Year, Month, Day, Nanoseconds                          ║
║                                                            ║
║ [Bitrate Object: 0x80] (5 bytes)                           ║
║   → 12 Mbps (or other bitrate)                            ║
║                                                            ║
║ [HCI Type Object: 0x81] (2 bytes)                          ║
║   → 0x01 (CMD), 0x02 (ACL), 0x84 (EVT), etc              ║
║                                                            ║
║ [HCI Data Object: 0x82] (1+N bytes)                        ║
║   → Raw HCI packet                                         ║
║                                                            ║
║ Result: ✅ Ellisys recognizes and decodes HCI packets    ║
╚════════════════════════════════════════════════════════════╝
```

---

## HCI Type Mappings Table

```
┌─────────────┬──────────┬──────────┬────────────────────────┐
│ Direction   │ BTSnoop  │ Ellisys  │ Description            │
├─────────────┼──────────┼──────────┼────────────────────────┤
│ H → C       │   0x01   │   0x01   │ Command                │
│ H → C ACL   │   0x02   │   0x02   │ ACL Data from Host     │
│ C → H ACL   │   0x02   │   0x82   │ ACL Data from Ctrl     │
│ H → C SCO   │   0x03   │   0x03   │ SCO Data from Host     │
│ C → H SCO   │   0x03   │   0x83   │ SCO Data from Ctrl     │
│ C → H       │   0x04   │   0x84   │ Event/Response         │
└─────────────┴──────────┴──────────┴────────────────────────┘

Note: Ellisys distinguishes direction using different bytes for
      ACL/SCO (0x02/0x03 vs 0x82/0x83), while BTSnoop uses the
      same type with flags in the record header.
```

---

## Data Flow Diagram

```
┌──────────────────┐
│  HCI Device      │
│  (Zephyr NRF52)  │
└────────┬─────────┘
         │
         │ HCI (Serial/UART)
         │
         ▼
┌──────────────────┐
│  HCI Bridge      │
│  (TCP Server     │
│   :9001)         │
└────────┬─────────┘
         │
         │ TCP @ 127.0.0.1:9001
         │
         ▼
    ┌─────────┐
    │ Bumble  │
    │ (Python)│
    └────┬────┘
         │
         ├─────────────────┬────────────────┐
         │                 │                │
         │ BTSnoop File    │ Console Log    │ UDP to Ellisys
         │ (Local)         │ (Local)        │ (:24352)
         │                 │                │
         ▼                 ▼                ▼
    ┌─────────┐        ┌─────────┐    ┌──────────────┐
    │ .btsnoop│        │Terminal │    │ Ellisys UDP  │
    │ File    │        │Output   │    │ Inject Port  │
    └─────────┘        └─────────┘    └──────┬───────┘
         │                                    │
         │                                    │ Decodes packets
         │                                    │ using Service 0x0002
         │                                    │
         │                                    ▼
         │                              ┌──────────────────┐
         │                              │ Ellisys Analyzer │
         │                              │ Live View        │
         │                              │                  │
         │                              │ Shows:           │
         │                              │  - Commands (→)  │
         │                              │  - Events (←)    │
         │                              │  - ACL Data (↔)  │
         │                              │  - Timestamps    │
         │                              │  - Decode        │
         │                              └──────────────────┘
         │
         └────────────────────────────────────────┐
                                                   │ Can also import
                                                   │ .btsnoop file
                                                   ▼
                                              ┌──────────────┐
                                              │  Wireshark   │
                                              │  (offline)   │
                                              └──────────────┘
```

---

## State Transition Diagram

```
START
  │
  ├─ user selects Option D
  │
  ▼
HCI Snooper.start()
  ├─ UDP socket created
  ├─ BTSnoop file opened
  ├─ Transport wrapper installed
  │
  └─ RUNNING STATE
       │
       ├─ Each HCI packet captured:
       │  ├─ _build_ellisys_injection_packet()
       │  │  └─ Returns proper API format
       │  │
       │  ├─ _send_ellisys()
       │  │  └─ Sends via UDP → Ellisys port 24352
       │  │     (Ellisys decodes and shows in live view)
       │  │
       │  ├─ _write_btsnoop()
       │  │  └─ Writes to local .btsnoop file
       │  │
       │  └─ _log_console()
       │     └─ Prints to terminal
       │
       ├─ Statistics updated:
       │  ├─ packet_count++
       │  ├─ udp_send_count++
       │  └─ udp_error_count (if errors)
       │
       └─ user selects Option D again to stop
          │
          ▼
       HCI Snooper.stop()
          └─ Socket closed
          └─ BTSnoop file closed
          └─ Summary printed
             └─ END
```

---

## Object Type Summary

```
ELLISYS OBJECT TYPES
═══════════════════════════════════════════════════════════

0x02 - DateTime Object
       ┌─ Year (2B LE)
       ├─ Month (1B)
       ├─ Day (1B)
       └─ Nanoseconds (6B LE)
       Purpose: Timestamp the packet

0x80 - Bitrate Object
       └─ Bitrate (4B LE)
       Purpose: Indicate link speed

0x81 - HCI Packet Type Object
       └─ Type (1B)
          0x01 = CMD
          0x02 = ACL (Host→Ctrl)
          0x82 = ACL (Ctrl→Host)
          0x03 = SCO (Host→Ctrl)
          0x83 = SCO (Ctrl→Host)
          0x84 = Event
       Purpose: Identify packet type

0x82 - HCI Packet Data Object
       └─ Raw HCI bytes (NB)
       Purpose: Contains the actual packet payload

═══════════════════════════════════════════════════════════
```

---

## Packet Build Example (Python)

```python
def build_packet(hci_type, hci_data):
    p = b''
    
    # Service header (3B)
    p += struct.pack('<H', 0x0002)  # Service ID
    p += bytes([0x01])               # Version
    
    # DateTime (10B)
    p += bytes([0x02])               # Object ID
    dt = datetime.now()
    p += struct.pack('<H', dt.year)
    p += bytes([dt.month, dt.day])
    ns = int((dt.timestamp() % 86400) * 1e9)
    p += struct.pack('<Q', ns)[:6]
    
    # Bitrate (5B)
    p += bytes([0x80])
    p += struct.pack('<I', 12_000_000)
    
    # HCI Type (2B)
    p += bytes([0x81, hci_type])
    
    # HCI Data (1+N B)
    p += bytes([0x82]) + hci_data
    
    return p

# Usage:
reset_cmd = build_packet(0x01, b'\x03\x0c\x00')
# → 25-30 bytes ready for UDP
```

---

## Summary

The corrected Ellisys HCI Injection protocol is an **object-based** format that wraps HCI packets with metadata:

1. **Service header** identifies this as HCI Injection (0x0002)
2. **DateTime object** provides timestamp
3. **Bitrate object** indicates link speed
4. **Type object** tells Ellisys the packet direction
5. **Data object** contains the raw HCI packet

This is fundamentally different from BTSnoop format and THAT'S why it now works! 🎯
