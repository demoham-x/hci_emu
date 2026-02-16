# 🚀 QUICK START - ELLISYS LIVE HCI SNOOP

## ⚡ 30-Second Setup

1. **Start Ellisys Analyzer**
   - Open application
   - Navigate to your device (e.g., RoadSync_XXXX)

2. **Click "Record"** to start capture

3. **Run Python app in another terminal:**
   ```bash
   python src/main.py
   ```

4. **Select Option D** (HCI Snoop Logging)
   ```
   [D] Enable/Disable HCI snoop logging
   Select stream (primary/secondary/tertiary): primary
   ```

5. **Perform BLE operations:**
   - Option 1 (Scan)
   - Option 2 (Connect)
   - Option 3 (Browse GATT)
   - Option 7 (Pair)

6. **Watch Ellisys** - HCI packets appear in real-time! ✅

---

## 📋 Complete Workflow

### Terminal 1 - Analyzer
```
Start Ellisys Bluetooth Analyzer
→ Select device or connection
→ Click "Record" (red button)
→ WAIT for Python to connect
```

### Terminal 2 - Python App
```bash
$ python src/main.py

Connecting to HCI bridge at 127.0.0.1:9001...
✓ Connected
✓ Got device info

[HCI SNOOP] ✓ Initialized
[HCI SNOOP] Target: 127.0.0.1:24352
[HCI SNOOP] Using Ellisys HCI Injection Service (0x0002)
[HCI SNOOP] Stream: PRIMARY
[HCI SNOOP] ✓ Test packet sent (Ellisys Injection API)
[BTSNOOP FILE] hci_snoop_2024-01-15_14-30-45.btsnoop

Menu:
  [1] Scan for BLE devices
  [2] Connect to device
  ...
  [D] Enable/Disable HCI snoop logging
  [Q] Quit
```

### Live in Ellisys
```
Record starts...
↓
HCI packets appear in real-time:
  - Commands (→)
  - Events (←)
  - ACL Data (↔)
  - Full packet decode
↓
Stop recording when done
Export as PCAP if needed
```

---

## 🎯 What You'll See

In Ellisys Analyzer window:

```
│ Time     │ Src │ Dst │ Type │ Data                          │
├──────────┼─────┼─────┼──────┼───────────────────────────────┤
│ 12:30:45 │ Cmd │ Evt │ CMD  │ 1E-20: LE Set Scan Parameters │
│ 12:30:45 │ Evt │     │ EVT  │ 04-0E: Command Complete       │
│ 12:30:46 │ Cmd │ Evt │ CMD  │ 0C-20: LE Set Scan Enable     │
│ 12:30:46 │ Evt │     │ EVT  │ 04-0E: Command Complete       │
│ 12:30:47 │ Cmd │ Evt │ CMD  │ 01-03: LE Create Connection   │
│ 12:30:47 │ Evt │     │ EVT  │ 13-05: LE Meta Event          │
└──────────┴─────┴─────┴──────┴───────────────────────────────┘
```

---

## 🔧 Troubleshooting Checklist

### Problem: "No packets in Ellisys"

**Step 1: Test UDP connectivity**
```bash
python test_ellisys_udp.py
```
Should show: `✓ All tests passed!`

**Step 2: Check Ellisys config**
- Tools → Options → Live Import
- Ensure UDP Injection (0x0002) is **ENABLED**
- Verify port: **24352**

**Step 3: Check firewall**
- Windows may block UDP from Python
- Add exception: Settings → Firewall → Allow app

**Step 4: Check BTSnoop file**
- Local file still created: `hci_snoop_*.btsnoop`
- Can open in Wireshark even if UDP fails

### Problem: "Packets appear but no decode"

**Cause:** Ellisys plugin not installed or wrong version

**Solution:**
1. Check Ellisys for decode errors
2. Verify packet format using: `hexdump hci_snoop_*.btsnoop`
3. Packets should start with correct Service ID bytes

### Problem: "Connection refused"

**Cause:** Ellisys not listening on port 24352

**Solution:**
1. Verify Ellisys is running
2. Check Admin privileges
3. Try different port in options (though 24352 is standard)

---

## 📊 Packet Format (Reference)

Each packet contains:

```
┌─────────────────────────────────┐
│ Service ID (2B)     │ 0x0002    │
├─────────────────────────────────┤
│ Version (1B)        │ 0x01      │
├─────────────────────────────────┤
│ DateTime Object     │ 10 bytes  │
│  - Type ID (0x02)               │
│  - Year (2B)                    │
│  - Month/Day (1B each)          │
│  - Nanoseconds (6B)             │
├─────────────────────────────────┤
│ Bitrate Object      │ 5 bytes   │
│  - Type ID (0x80)               │
│  - 12,000,000 bps (4B)          │
├─────────────────────────────────┤
│ HCI Packet Type     │ 2 bytes   │
│  - Type ID (0x81)               │
│  - Type (0x01/0x02/0x84/...)    │
├─────────────────────────────────┤
│ HCI Packet Data     │ 1+N bytes │
│  - Type ID (0x82)               │
│  - Raw HCI packet               │
└─────────────────────────────────┘
```

---

## 💾 Output Files

When you enable snoop, you get:

1. **UDP Stream (Live):**
   - Sent to Ellisys port 24352
   - Real-time decode in Ellisys window

2. **BTSnoop File:**
   - Location: `hci_snoop_YYYY-MM-DD_HH-MM-SS.btsnoop`
   - Standard format, can open with:
     - Ellisys Analyzer
     - Wireshark
     - Any BTSnoop-compatible tool

3. **Console Output:**
   ```
   [HCI] >>> CMD [3 bytes] 03 0c 00
   [HCI] <<< EVT [4 bytes] 0e 04 01
   ```

---

## 🎯 Typical Session

```bash
# Terminal 1: Start app
$ python src/main.py
✓ Connected to HCI bridge

# Terminal 1: Enable snoop
Enter option: d
Select stream: primary
[HCI SNOOP] ✓ Initialized
[BTSNOOP FILE] hci_snoop_2024-01-15_14-30-45.btsnoop

# Terminal 1: Run BLE operations
Enter option: 1
[SCAN] Starting BLE scan...
[HCI] >>> CMD [3 bytes] 0c 20 02 01 00
[HCI] <<< EVT [6 bytes] 0e 04 01 0c 20 00
✓ Found device: RoadSync_XXXX (00:60:37:DB:CC:AE)

# Terminal 1: Connect
Enter option: 2
Select device: 1
[CONNECT] Connecting to RoadSync_XXXX...
[HCI] >>> CMD [15 bytes] 0d 20 0d 4c 00 00 00 00 00 00 00 00 00 00 00
[HCI] <<< EVT [4 bytes] 0e 04 01 0d 20 00

# Ellisys shows all packets in real-time! ✅
```

---

## 🚨 Know Issues & Limitations

| Issue | Status | Workaround |
|-------|--------|-----------|
| Packets not in Ellisys | Rare | Run test_ellisys_udp.py |
| BTSnoop file not created | Check permissions | Use writable directory |
| Ellisys shows raw data | Plugin issue | Verify packet format |
| UDP timeout | Firewall | Add Windows Firewall exception |

---

## 📞 Support

1. **Test connectivity:**
   ```bash
   python test_ellisys_udp.py
   ```

2. **Check local file:**
   ```bash
   ls hci_snoop_*.btsnoop
   # Open in Wireshark or Ellisys
   ```

3. **Enable console logging:**
   - Option D detects socket errors
   - Check printed output for issues

4. **Reference documentation:**
   - [ELLISYS_FIX_SUMMARY.md](ELLISYS_FIX_SUMMARY.md) - Full technical details
   - [ELLISYS_INJECTION_FIXED.md](ELLISYS_INJECTION_FIXED.md) - Protocol details

---

## ✅ Success Indicators

You'll know it's working when:

- [ ] `test_ellisys_udp.py` shows "✓ All tests passed!"
- [ ] Option D in menu shows: `[HCI SNOOP] ✓ Test packet sent`
- [ ] BTSnoop file is created: `hci_snoop_*.btsnoop`
- [ ] Packets appear in Ellisys in real-time
- [ ] Packets have proper HCI decode (not raw data)
- [ ] Operation types visible: CMD, EVT, ACL

---

## 🎉 You're Ready!

```bash
python src/main.py
```

Select Option D and enjoy real-time HCI snoop logging in Ellisys! 🚀
