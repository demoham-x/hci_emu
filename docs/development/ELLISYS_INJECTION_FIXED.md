# Ellisys HCI Injection Protocol - CORRECTED

## 🎯 Problem Solved

Your HCI packets were reaching Ellisys UDP port 24352, but **Ellisys wasn't decoding them as HCI packets** because the format was wrong!

### ❌ What Was Wrong (Pure BTSnoop format):
```
[BTSnoop Record Header (24 bytes)]
[HCI Packet Type (1 byte)]
[HCI Data (N bytes)]
```

### ✅ What's CORRECT (Ellisys Injection API):
```
[Service ID: 0x0002 (2 bytes, little-endian)]
[Service Version: 0x01 (1 byte)]
[DateTime Object: 0x02 + data (10 bytes)]
[Bitrate Object: 0x80 + data (5 bytes)]
[HCI Packet Type: 0x81 + 1 byte]
[HCI Packet Data: 0x82 + N bytes]
```

## 📋 Format Breakdown

### Service Object (3 bytes)
```python
packet += struct.pack('<H', 0x0002)  # Service ID (HCI Injection)
packet += bytes([0x01])               # Version
```

### DateTime Object (10 bytes)
```python
packet += bytes([0x02])              # Object ID
packet += struct.pack('<H', year)    # Year (2 bytes LE)
packet += bytes([month, day])        # Month, Day (1 byte each)
packet += ns_bytes[:6]               # Nanoseconds (6 bytes)
```

### Bitrate Object (5 bytes)
```python
packet += bytes([0x80])              # Object ID
packet += struct.pack('<I', 12_000_000)  # 12 Mbps (4 bytes LE)
```

### HCI Packet Type (2 bytes)
```python
packet += bytes([0x81])              # Object ID
packet += bytes([hci_type])          # Type byte
```

### HCI Packet Data (1 + N bytes)
```python
packet += bytes([0x82])              # Object ID
packet += hci_data                   # Raw HCI packet
```

## 🔄 HCI Packet Type Mappings

| Direction | Type | Ellisys Byte |
|-----------|------|------|
| Command (Host → Controller) | CMD | 0x01 |
| ACL (Host → Controller) | ACL | 0x02 |
| ACL (Controller → Host) | ACL | 0x82 |
| SCO (Host → Controller) | SCO | 0x03 |
| SCO (Controller → Host) | SCO | 0x83 |
| Event (Controller → Host) | EVT | 0x84 |

## 📝 Usage Example

### Test Single Packet:
```bash
python test_ellisys_udp.py
```

Expected output:
```
Ellisys UDP Injection Test
Using CORRECT Ellisys Injection API (0x0002)

Target: 127.0.0.1:24352

✓ Socket created

Test 1: Sending HCI Reset Command (Ellisys API)...
  ✓ Sent 33 bytes
  Service: 0x0002 (HCI Injection Service)
  HCI Type: 0x01 (CMD)
  HCI Data: 03 0c 00
```

### Enable Live HCI Snoop in Main App:
```bash
python src/main.py

Options:
[D] Enable/Disable HCI snoop logging
```

Select Option D, choose stream (Primary/Secondary/Tertiary), and run BLE operations. HCI packets will now appear in Ellisys Analyzer!

## ✅ Verification Checklist

- [ ] Ellisys Analyzer is running
- [ ] Click "Record" in Ellisys to start capture
- [ ] Enable HCI Injection Services in Ellisys (Tools → Options → Live Import)
- [ ] Run `python test_ellisys_udp.py` (packets should be received)
- [ ] Run `python src/main.py` and select Option D
- [ ] Perform BLE operations (scan, connect, pair)
- [ ] **VERIFY**: HCI packets appear in Ellisys with proper decoding!

## 📊 Packet Structure Example

### HCI Reset Command (Hex Dump):
```
02 00 01 02 18 0B 06 00 00 40 1E 01 00 00 00 00 00 00 80 AE 02 00 00 9E 77 81 01 82 03 03 0C 00
^service^ ^version^ ^datetime_obj^       ^datetime_ns(6bytes)^ ^bitrate_obj^    ^type_obj^ ^hci_data^
```

Breaking it down:
- `02 00` = Service ID 0x0002 (little-endian)
- `01` = Version
- `02` = DateTime object ID
- `18 0B` = Year 2840 (little-endian) - should be current year
- `06 00` = Month 6, Day 0
- `00 00 40 1E 01 00` = Nanoseconds (6 bytes)
- `80` = Bitrate object ID
- `AE 02 00 00` = 12,000,000 bps (little-endian)
- `81` = HCI Packet Type object ID
- `01` = 0x01 (Command)
- `82` = HCI Packet Data object ID
- `03 0C 00` = HCI Reset command bytes

## 🔧 Implementation Files

1. **src/hci_snooper.py** (UPDATED)
   - `_build_ellisys_injection_packet()` - Builds correct packet format
   - `_send_ellisys()` - Sends using correct format
   - Maps Bumble HCI types to Ellisys types

2. **test_ellisys_udp.py** (UPDATED)
   - `build_ellisys_injection_packet()` - Test helper
   - Tests HCI Reset, Event, and multiple packets

3. **src/main.py** (NO CHANGES NEEDED)
   - Already uses HCISnooper class correctly

## 🎓 Reference

Based on: https://github.com/bobwenstudy/bt_ellisys_injection
- Ellisys HCI Injection Service (0x0002) protocol
- Proper object wrapping with type IDs
- Correct HCI packet type mappings

## 🚀 What Changed

**Before:** Particles sent but not recognized
```
[BTSnoop Header] + [0x01] + [03 0C 00] → ❌ Not decoded
```

**After:** Proper Ellisys protocol
```
[0x0002][0x01][0x02...ns...][0x80...bitrate...][0x81][0x01][0x82][03 0C 00] → ✅ Decoded!
```

## 📞 Troubleshooting

### Still not seeing packets in Ellisys?

1. **Check Ellisys Configuration:**
   - Tools → Options → Live Import
   - TCP Injection Service (0x0001) or UDP?
   - HCI Injection Service (0x0002) enabled?

2. **Verify Port Listening:**
   - Ensure Ellisys is listening on 127.0.0.1:24352
   - Check firewall (Windows may block UDP)

3. **Run Diagnostic:**
   ```bash
   python test_ellisys_udp.py
   ```
   - Should show "✓ All tests passed!"

4. **Check BTSnoop File:**
   - HCI snoop generates `.btsnoop` file locally
   - Even if UDP fails, BTSnoop file should be created
   - Can open in Wireshark or Ellisys

## ✨ Next Steps

1. Run `python test_ellisys_udp.py` to verify UDP connectivity
2. Start Python app: `python src/main.py`
3. Click Record in Ellisys
4. Select Option D in menu to enable snoop
5. Perform BLE operations
6. Watch HCI packets appear in Ellisys live! 🎯
