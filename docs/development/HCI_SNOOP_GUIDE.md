# HCI Snoop Logging with Ellisys Injection

## Overview

The framework now includes live HCI packet capture with multiple output options:
- **Ellisys UDP Injection**: Real-time packet streaming to Ellisys Bluetooth Analyzer
- **BTSnoop File**: Standard BTSnoop format for offline analysis
- **Console Logging**: Real-time packet display in terminal

## Quick Start

### 1. Launch Ellisys Analyzer (Optional)

If you have Ellisys Bluetooth Analyzer:
1. Open Ellisys Bluetooth Analyzer
2. Go to **Tools → Options → Live Import**
3. Enable **Live Import from UDP**
4. Set port to **24352** (default)
5. Click **Start Live Import**

### 2. Enable HCI Snoop in Framework

```bash
python src/main.py
```

From the main menu:
1. Press **D** (HCI Snoop Logging)
2. Configure settings:
   - **Ellisys host**: 127.0.0.1 (localhost) or remote IP
   - **Ellisys port**: 24352 (default)
   - **BTSnoop filename**: hci_capture.btsnoop (default)
   - **Console logging**: y/n (shows packets in real-time)
3. Confirm to enable

### 3. Perform BLE Operations

All HCI packets will now be captured:
- Scan for devices (Option 1)
- Connect (Option 2)
- Pair (Option 8)
- GATT operations (Options 3-7)

### 4. View Captured Packets

**In Ellisys Analyzer:**
- Packets appear in real-time
- Full protocol analysis with timing
- Decode HCI, L2CAP, ATT, SMP layers

**In BTSnoop File:**
Use Wireshark or other tools:
```bash
wireshark hci_capture.btsnoop
```

**In Console:**
```
[HCI] >>> CMD [  4 bytes] 01 0c 20 02 01 00
[HCI] <<< EVT [  6 bytes] 04 0e 04 01 0c 20 00
```

## BTSnoop File Format

The generated `.btsnoop` files are compatible with:
- **Wireshark** (File → Open → hci_capture.btsnoop)
- **Ellisys Bluetooth Analyzer** (File → Open Capture)
- **Android btsnoop_hci.log** viewers
- Any BTSnoop-compatible tool

## HCI Packet Types

| Type | Code | Description |
|------|------|-------------|
| CMD  | 0x01 | HCI Command (Host → Controller) |
| ACL  | 0x02 | ACL Data (Bidirectional) |
| SCO  | 0x03 | SCO Data (Voice) |
| EVT  | 0x04 | HCI Event (Controller → Host) |

## Example Workflow

### Capture Pairing Process

```bash
# 1. Start framework
python src/main.py

# 2. Enable HCI snoop (Option D)
#    - Ellisys: 127.0.0.1:24352
#    - File: pairing_capture.btsnoop
#    - Console: yes

# 3. Scan for device (Option 1)
# 4. Connect to device (Option 2)
# 5. Pair with device (Option 8)
#    (Watch packets flow in real-time!)

# 6. Disable snoop (Option D again)
# 7. Analyze pairing_capture.btsnoop in Wireshark
```

### Analyze in Wireshark

```bash
wireshark hci_capture.btsnoop
```

**Useful Filters:**
- `bthci_evt` - HCI Events only
- `bthci_cmd` - HCI Commands only
- `btl2cap` - L2CAP layer
- `btatt` - ATT (GATT) operations
- `btsmp` - Security Manager Protocol (pairing)

## Troubleshooting

### Ellisys Not Receiving Packets

**Check:**
1. Ellisys "Live Import from UDP" is enabled
2. Port 24352 is correct
3. Firewall allows UDP traffic
4. Host IP is correct (127.0.0.1 for localhost)

**Test with netcat:**
```bash
# Listen on port 24352
nc -ul 24352
```

### BTSnoop File Empty

**Possible causes:**
- No BLE operations performed after enabling snoop
- File permissions issue
- Disk space

**Solution:**
Check file after performing at least one operation (scan, connect, etc.)

### Console Logging Too Verbose

**Options:**
1. Disable console logging when enabling snoop
2. Redirect output to file:
   ```bash
   python src/main.py > output.log 2>&1
   ```

## Technical Details

### UDP Packet Format

Each packet sent to Ellisys via UDP contains:
```
[BTSnoop Record Header (24 bytes)]
  - Original Length (4 bytes)
  - Included Length (4 bytes)
  - Packet Flags (4 bytes)      # 0=sent, 1=received
  - Drops (4 bytes)              # Always 0
  - Timestamp High (4 bytes)     # Microseconds
  - Timestamp Low (4 bytes)
[HCI Packet Type (1 byte)]       # 0x01-0x04
[HCI Packet Data (variable)]
```

### BTSnoop File Format

```
[File Header (16 bytes)]
  "btsnoop\0"                    # Magic bytes
  Version (4 bytes) = 1
  Data Link Type (4 bytes) = 1002 (HCI UART H4)

[Records...]
  [Record Header (24 bytes) + HCI Packet]
```

## Advanced Usage

### Remote Ellisys Analyzer

Capture on one machine, analyze on another:

```python
# On capture machine:
# Press D → Enter remote IP: 192.168.1.100

# On analysis machine (192.168.1.100):
# Run Ellisys with UDP Live Import on port 24352
```

### Dual Mode: File + Live

**Best practice:**
1. Enable HCI snoop with both Ellisys UDP AND BTSnoop file
2. View packets live in Ellisys
3. Save BTSnoop file for later detailed analysis

### Custom Port

If port 24352 is in use:

```python
# Press D
# Ellisys port: 9999 (custom)

# Configure Ellisys to listen on port 9999
```

## References

- **BTSnoop Format**: [RFC 1761 - BTSnoop File Format](https://www.ietf.org/rfc/rfc1761.txt)
- **Ellisys Analyzers**: [https://www.ellisys.com/](https://www.ellisys.com/)
- **Wireshark**: [https://www.wireshark.org/](https://www.wireshark.org/)
- **HCI Specification**: Bluetooth Core Spec v5.3, Vol 4, Part E

## Example Captured Packets

### HCI Reset Command
```
>>> CMD [4 bytes]: 01 03 0c 00
    Opcode: 0x0C03 (Reset)
    Parameters: None

<<< EVT [6 bytes]: 04 0e 04 01 03 0c 00
    Event: Command Complete
    Status: Success (0x00)
```

### LE Set Scan Enable
```
>>> CMD [6 bytes]: 01 0c 20 02 01 00
    Opcode: 0x200C (LE Set Scan Enable)
    Enable: 0x01 (Enabled)
    Filter Duplicates: 0x00 (Disabled)

<<< EVT [6 bytes]: 04 0e 04 01 0c 20 00
    Event: Command Complete
    Status: Success
```

### LE Advertising Report
```
<<< EVT [43 bytes]: 04 3e 29 02 01 00 00 ae cc db 37 60 00 1d ...
    Event: LE Meta Event
    Subevent: Advertising Report
    Address: 00:60:37:DB:CC:AE (Public)
    RSSI: -59 dBm
    Data: [Complete Local Name: "RoadSync_XXXX"]
```
