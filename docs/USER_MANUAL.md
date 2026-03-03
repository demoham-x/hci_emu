# Bumble BLE Testing Framework - User Manual

> **Version 1.0** | Complete guide for testing BLE devices

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Basic Operations](#basic-operations)
4. [Advanced Features](#advanced-features)
5. [Legacy LE Mode](#legacy-le-mode)
6. [HCI Packet Capture](#hci-packet-capture)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Quick Start

### What You Need

- Windows, Linux, or macOS computer
- Bluetooth adapter (built-in or USB dongle)
- Python 3.8 or higher
- 10 minutes to set up

### 3-Step Setup

#### 1. Start HCI Bridge (Terminal 1)

```bash
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
```

Wait for:
```
>>> connecting to HCI...
>>> connected
```

#### 2. Run Application (Terminal 2)

```bash
python src/main.py
```

#### 3. Start Testing!

```
+--------------------------------+
| BUMBLE BLE Testing - Main Menu |
+--------------------------------+

A. Bluetooth On
1. Scan for BLE Devices
2. Connect to Device
3. Discover GATT Services
...

Select option:
```

---

## Installation

See [SETUP.md](../SETUP.md) for detailed platform-specific instructions.

### Quick Install (All Platforms)

```bash
# Clone repository
git clone <repository-url>
cd bumble_hci

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Check Bumble is installed
bumble-hci-bridge --help

# Check Python version
python --version  # Should be 3.8+
```

---

## Basic Operations

### 1. Scanning for Devices

**Steps:**
1. Select **Option A** - Bluetooth On
2. Select **Option 1** - Scan for BLE Devices
3. Enter scan duration (default: 10 seconds)
4. Choose duplicate filtering (Y/n)
5. Choose active or passive scan (Y/n)

**What you'll see:**
```
Starting LE active scan for 10 seconds (duplicate filtering: on)...

  [1] ADV 00:60:37:DB:CC:AE/P  RSSI:  -57 dBm Name: RoadSync_XXXX
╭────────────────────────────────────────────╮
│ Type                    Value              │
│ Adv type                legacy, connectable│
│ Flags                   LE General         │
│ Complete Local Name     "RoadSync_XXXX"    │
╰────────────────────────────────────────────╯

✓ Scan complete. Found 1 total devices
```

**Tips:**
- **Active scan**: Requests additional info from devices (scan response)
- **Passive scan**: Only listens to advertisements
- **Duplicate filtering ON**: Shows each device once
- **Duplicate filtering OFF**: Shows every advertisement packet

### 2. Device Filtering

Use filters to find specific devices quickly.

**Steps:**
1. Select **Option C** - Set Device Filters
2. Enter partial device name (e.g., "road")
3. Enter partial address (e.g., "1E:59")

**Example:**
```
Device name (partial, case-insensitive): road
Device address (partial, e.g., '1E:59:DD'): 

✓ Filters updated:
  - Name contains: 'road'

[Filters Active: Name: 'road']
```

Only devices matching filters will be shown in scans.

### 3. Connecting to a Device

**Steps:**
1. Scan for devices (Option 1)
2. Select **Option 2** - Connect to Device
3. Enter device number from list

**What happens:**
```
Enter device number from list (or address manually): 1

Connecting to 00:60:37:DB:CC:AE/P...
(This may take a few seconds... press Ctrl+C to cancel)

✓ Successfully connected to 00:60:37:DB:CC:AE/P
✓ Device is already bonded - no pairing needed

Connection ready.

Next steps:
  - Option 9: Encrypt connection (if bonded)
  - Option 3: Discover GATT Services
  - Option 11: Disconnect
```

**Connection States:**
- **Not Bonded**: May initiate pairing automatically
- **Already Bonded**: Uses saved keys, no pairing needed
- **Timeout**: Device not responding (check range/power)

### 4. Discovering Services

After connecting, discover what the device offers.

**Steps:**
1. Select **Option 3** - Discover GATT Services
2. View services, characteristics, and descriptors

**Example Output:**
```
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Type     ┃ UUID          ┃ Handle    ┃ Properties┃ Description  ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ SERVICE  │ 0x1800        │ 0x0001-.. │ -         │ Generic Access│
│   └─CHAR │ 0x2A00        │ 0x0003    │ READ      │ Device Name  │
│ SERVICE  │ 0x180F        │ 0x0010-.. │ -         │ Battery Service│
│   └─CHAR │ 0x2A19        │ 0x0012    │ READ,NOTF │ Battery Level│
└──────────┴───────────────┴───────────┴───────────┴──────────────┘
```

**Properties Legend:**
- **READ**: Can read value
- **WRITE**: Can write with response
- **WRITE_WITHOUT_RESPONSE**: Can write without response
- **NOTIFY**: Can subscribe to notifications
- **INDICATE**: Can subscribe to indications

### 5. Reading a Characteristic

**Steps:**
1. Note the handle from service discovery (e.g., 0x0012)
2. Select **Option 4** - Read Characteristic
3. Enter handle (hex `0x0012` or decimal `18`)

**Example:**
```
Enter characteristic handle (hex 0x0054 or decimal 84): 0x12

╭────────────────────────────────────────────╮
│ Read Result - Handle 0x0012                │
├────────────────────────────────────────────┤
│ Handle      │ 0x0012 (decimal: 18)         │
│ Length      │ 1 bytes                       │
│ Hex         │ 64                            │
│ ASCII       │ d                             │
│ Uint8       │ 100                           │
╰────────────────────────────────────────────╯
```

### 6. Writing to a Characteristic

**Steps:**
1. Select **Option 5** (with response) or **Option 6** (without response)
2. Enter handle
3. Enter hex value (e.g., `01020304`)

**Example:**
```
Enter characteristic handle: 0x20
Enter value (hex, space-separated or continuous): 01 02 03 04

✓ Successfully wrote to handle 0x0020 (32)
```

**When to use each:**
- **Write (Option 5)**: Confirmation needed, more reliable
- **Write Without Response (Option 6)**: Faster, no confirmation

### 7. Subscribing to Notifications

**Steps:**
1. Find characteristic with NOTIFY property
2. Select **Option 7** - Subscribe to Notifications
3. Enter handle

**What happens:**
```
Enter characteristic handle: 0x12

✓ Subscribed to notifications on handle 0x0012 (18)
Notifications will be printed when received.
```

**Receiving notifications:**
```
[NOTIFICATION] Handle: 0x0012 (18), Value: 65
[NOTIFICATION] Handle: 0x0012 (18), Value: 66
```

**To stop receiving**: Disconnect or unsubscribe (write 0x0000 to CCC descriptor)

### 8. Pairing and Bonding

**Steps:**
1. Connect to device (Option 2)
2. If not bonded, pairing may start automatically
3. Or manually select **Option 9** - Pair / Encrypt Connection

**Pairing Methods:**
- **Just Works**: No user interaction needed
- **Passkey Entry**: Enter 6-digit code shown on device
- **Numeric Comparison**: Confirm same code on both devices

**After pairing:**
- Keys stored in `configs/bumble_bonds.json`
- Next connection uses saved keys
- No need to pair again

**Managing Bonds:**
- View bonded devices: Option A (Bluetooth On)
- Delete bond: Option 10 (Unpair / Delete Bonding)

### 9. Disconnecting

**Steps:**
1. Select **Option 11** - Disconnect
2. Confirmation shown

```
✓ Disconnected
```

---

## Advanced Features

### Burst Write Operations

Send multiple writes in rapid succession for stress testing.

**Steps:**
1. Connect to device
2. Select **Option 12** (with response) or **Option 13** (without response)
3. Enter handle, value, count, and interval

**Example:**
```
Enter characteristic handle: 0x20
Enter value (hex): 01 02 03 04
Count (0 = infinite, default 0): 100
Interval ms (default 100): 50

Burst write started in background.
```

**Monitoring:**
- Check console for write confirmations
- Use Option 14 to stop

**Use cases:**
- Throughput testing
- Stress testing device firmware
- Connection stability testing

### Burst Read Operations

Continuously read from a characteristic.

**Steps:**
1. Select **Option 15** - Burst Read
2. Enter handle, count, interval
3. Choose console printing (y/n)

**Example:**
```
Enter characteristic handle: 0x12
Count (0 = infinite): 50
Interval ms: 100
Print each read to console? (y/N): y

Burst read started in background.

╭────────────────────────────────────────────╮
│ Burst Read #1 - Handle 0x0012             │
├────────────────────────────────────────────┤
│ Value: 64 (100)                            │
╰────────────────────────────────────────────╯
```

**Stop**: Option 16

### CSV Logging

Log all notifications to CSV file for analysis.

**Steps:**
1. Select **Option 17** - Start CSV Logging
2. Enter filename (optional)
3. Subscribe to characteristics
4. Notifications logged automatically

**Example:**
```
CSV filename (default: notifications_20260211_150432.csv): my_data.csv

CSV logging started.
```

**CSV Format:**
```
timestamp,handle,value_hex,value_ascii
2026-02-11 15:04:32.123456,18,64,d
2026-02-11 15:04:33.234567,18,65,e
```

**Stop**: Option 18

---

## Legacy LE Mode

Some Bluetooth controllers, or setups where you need to sniff with a legacy
analyser, require that only the original non-extended LE HCI commands are used
for scanning, advertising, and connection initiation.

By default Bumble uses **extended** commands when the controller reports it
supports them (Bluetooth 5.0+).  The **Legacy LE mode** flag tells the
framework to strip those capability bits so that Bumble always sends the
classic opcodes:

| Operation | Legacy opcode(s) used |
|-----------|----------------------|
| Scan parameters | `LE_Set_Scan_Parameters` (0x200B) |
| Scan enable/disable | `LE_Set_Scan_Enable` (0x200C) |
| Create connection | `LE_Create_Connection` (0x200D) |
| Advertising parameters | `LE_Set_Advertising_Parameters` (0x2006) |
| Advertising data | `LE_Set_Advertising_Data` (0x2008) |
| Scan response data | `LE_Set_Scan_Response_Data` (0x2009) |
| Advertising enable | `LE_Set_Advertise_Enable` (0x200A) |

### Enabling Legacy LE Mode

**Option 1 – Command-line flag:**

```bash
python src/main.py --legacy-le
```

**Option 2 – Environment variable:**

```bash
# Linux / macOS
USE_LEGACY_LE=1 python src/main.py

# Windows PowerShell
$env:USE_LEGACY_LE=1; python src/main.py

# Windows Command Prompt
set USE_LEGACY_LE=1 && python src/main.py
```

When active the main menu shows a reminder line:

```
E. Debug Logging (NONE)
   [Legacy LE mode: ON  -- using legacy scan/adv/connect opcodes]
1. Scan for BLE Devices
```

and a confirmation is printed once Bluetooth powers on:

```
[Legacy LE] ✓ Legacy-only LE procedures enforced (opcodes 0x200B/C, 0x200D)
```

### Verifying with HCI Snoop

1. Enable HCI Snoop (Option D) to record a `logs/hci_capture.log` file.
2. Start scanning.
3. Open `hci_capture.log` in Wireshark or the Ellisys Analyzer.
4. Filter for opcode `0x200b` — you should see `LE Set Scan Parameters`
   packets rather than the extended equivalent (`0x2041`).

### When to use Legacy LE Mode

- The target peripheral does not support extended advertising.
- A hardware HCI sniffer only decodes legacy LE packets.
- Debugging interoperability with Bluetooth 4.x-only equipment.
- Reproducing issues observed on legacy-only stacks.

---

## HCI Packet Capture

Capture raw Bluetooth HCI packets for deep analysis.

### What is HCI Snoop?

HCI (Host Controller Interface) is the layer between your app and the Bluetooth controller. Capturing HCI packets shows:
- Commands sent to controller
- Events received from controller
- ACL data (actual Bluetooth data)
- Connection parameters
- Pairing/encryption details

### Setting Up Capture

**Steps:**
1. Select **Option D** - HCI Snoop Logging
2. Configure settings:

```
Ellisys host (default 127.0.0.1): [Enter for default]
Ellisys port (default 24352): [Enter for default]

Ellisys Data Stream:
  1. Primary
  2. Secondary
  3. Tertiary
Select stream (1-3): 1

Capture file format (.log or .btsnoop - both work with Ellisys/analyzers)
Filename (default logs/hci_capture.log): capture.log

Enable console packet logging? (y/n): n

Enable HCI snoop logging with these settings? (y/n): y
```

**What's captured:**
- ✅ Commands to controller
- ✅ Events from controller
- ✅ ACL data packets
- ✅ Timestamps (nanosecond precision)
- ✅ Packet direction (Host→Controller, Controller→Host)

### Analyzing Captures

#### Option 1: Wireshark

```bash
wireshark capture.log
```

Filter for Bluetooth HCI:
- `bluetooth.hci` - All HCI traffic
- `bthci_cmd` - HCI commands
- `bthci_evt` - HCI events
- `bthci_acl` - ACL data

#### Option 2: Ellisys Analyzer

1. Open Ellisys Bluetooth Analyzer
2. **File → Open Capture**
3. Select `capture.log`
4. View decoded packets with protocol analysis

#### Option 3: Real-time Ellisys

1. Open Ellisys Analyzer
2. **Tools → Options → Live Import**
3. Enable **Live Import from UDP**
4. Set port to **24352**
5. Start Live Import
6. Enable HCI Snoop in application
7. Packets appear in real-time!

### Example Captures

**Connection Sequence:**
1. `HCI_LE_Create_Connection` command
2. `Command_Status` event
3. `LE_Connection_Complete` event
4. ACL data exchange begins

**Pairing Sequence:**
1. L2CAP SMP packets
2. Pairing Request/Response
3. Key exchange
4. `Encryption_Change` event

### Tips

- **File size**: ~1KB per 100 packets
- **Performance**: Minimal impact on operations
- **Console logging**: Useful for debugging, slows down capture
- **Multiple streams**: Use different Ellisys streams for different captures

---

## Troubleshooting

### Connection Issues

#### "Connection timeout - device not responding"

**Causes:**
- Device out of range
- Device not advertising
- Interference

**Solutions:**
1. Move closer to device
2. Check device is powered on
3. Scan again to verify advertising
4. Try different Bluetooth channel

#### "Device not initialized. Run 'A' (Bluetooth On) first"

**Solution:**
1. Select **Option A** - Bluetooth On
2. Wait for "Bluetooth is ON"
3. Then retry operation

#### "Failed to stop scan cleanly"

**Solution:**
- Wait a few seconds
- Try again
- If persists, restart HCI bridge

### Pairing Issues

#### "Pairing timeout"

**Causes:**
- Device requires user interaction
- Device already paired to another host
- Security mismatch

**Solutions:**
1. Check device for pairing prompts
2. Reset device pairing state
3. Delete existing bonds (Option 10)
4. Try connecting again

#### "Device is bonded but connection fails"

**Solution:**
1. Delete bond (Option 10)
2. Reconnect (Option 2)
3. Pair fresh

### Read/Write Errors

#### "Failed to read handle"

**Causes:**
- Handle doesn't support READ
- Need pairing/encryption first
- Invalid handle

**Solutions:**
1. Check service discovery for properties
2. Pair with device (Option 9)
3. Verify handle number

#### "Failed to write"

**Causes:**
- Handle doesn't support WRITE
- Value too long
- Need higher security level

**Solutions:**
1. Check max write length
2. Enable encryption (Option 9)
3. Try write WITHOUT response (Option 6)

### HCI Bridge Issues

#### "Cannot connect to tcp-server"

**Solutions:**
1. Ensure HCI bridge is running
2. Check port 9001 not in use
3. Try different port:
   ```bash
   bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9002
   ```
4. Update transport in code

#### "USB device not found"

**Solutions:**
1. Check Bluetooth adapter plugged in
2. Try different USB port
3. Try `usb:1` or `usb:2`:
   ```bash
   bumble-hci-bridge usb:1 tcp-server:127.0.0.1:9001
   ```

### Performance Issues

#### "Scan finds no devices"

**Solutions:**
1. Increase scan duration (30+ seconds)
2. Try active scan
3. Remove filters (Option C → Clear)
4. Check Bluetooth adapter working

#### "Notifications arrive slowly"

**Causes:**
- Connection interval too long
- Interference
- Device limiting rate

**Solutions:**
- Normal: Notifications every 100-1000ms
- Cannot change from central side
- Check device configuration

---

## FAQ

### General

**Q: Do I need special hardware?**  
A: Any Bluetooth adapter works - built-in laptop Bluetooth or USB dongles.

**Q: Does this work on Linux/Mac?**  
A: Yes! See [SETUP.md](../SETUP.md) for platform-specific instructions.

**Q: Can I use this with my BLE device?**  
A: Yes! Works with any standards-compliant BLE device.

### Technical

**Q: What's the difference between GATT and HCI?**  
A: GATT is the high-level profile (services, characteristics). HCI is low-level (raw Bluetooth commands).

**Q: Why use Bumble instead of BlueZ/Windows Bluetooth API?**  
A: Bumble provides:
- Cross-platform consistency
- Direct HCI access
- Better debugging/capture capabilities
- Python-friendly API

**Q: Can I automate tests?**  
A: Yes! Import modules from `src/` and write Python scripts. See `examples/` directory.

### Bonding

**Q: Where are bonds stored?**  
A: In `configs/bumble_bonds.json` in the project directory.

**Q: Can I share bonds between computers?**  
A: Yes, but keys are tied to Bluetooth address. Copy `configs/bumble_bonds.json` to new machine.

**Q: How do I reset all bonding?**  
A: Delete `configs/bumble_bonds.json` or use Option 10 to remove specific bonds.

### Capture

**Q: Can I open .log files in Wireshark?**  
A: Yes! Both `.log` and `.btsnoop` files contain BTSnoop format.

**Q: Does capture affect performance?**  
A: Minimal impact. File writing is efficient, UDP streaming is fast.

**Q: Can I capture without Ellisys?**  
A: Yes! Just use file capture. Ellisys is optional for analysis.

### Troubleshooting

**Q: "Module not found" errors**  
A: Ensure virtual environment is activated and dependencies installed:
```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Q: HCI bridge won't start**  
A: Check:
1. USB permissions (Linux: `sudo usermod -a -G dialout $USER`)
2. Bluetooth adapter detected (`lsusb` on Linux)
3. Try different USB port/adapter

---

## Next Steps

- **For developers**: See [CONTRIBUTING.md](../CONTRIBUTING.md)
- **For technical details**: See [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)
- **For setup help**: See [SETUP.md](../SETUP.md)

---

**Need more help?**
- Check [GitHub Issues](repository-url/issues)
- Read [Bumble documentation](https://google.github.io/bumble/)
- Review examples in `examples/` directory

**Happy BLE Testing! 🔵📡**
