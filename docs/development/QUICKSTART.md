# Quick Start Guide

## Step 1: Ensure Driver is Changed
**Already done** - Your Intel Bluetooth is now using WinUSB driver

## Step 2: Start HCI Bridge (Terminal 1)

Run PowerShell **as Administrator**:

```powershell
cd C:\workspace\misc\bumble_hci
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
```

You should see:
```
>>> connecting to HCI...
>>> connected
```

**Keep this terminal open!**

---

## Step 3: Start Bumble Console (Terminal 2)

Open a new PowerShell (as Administrator):

```powershell
bumble-console tcp-client:127.0.0.1:9001
```

---

## Step 4: Use Console Commands

Inside bumble-console, you can now run:

### Scan for Devices
```
scan on
```
Wait a few seconds to see advertising devices...

```
scan off
```

### Connect to Device
Replace with actual device address you want to connect to:
```
connect 80:E4:BA:42:E9:AF
```

### Pair (if needed)
```
pair
```

### Discover GATT Services
```
discover
```

### Read a Characteristic
```
read <handle>
```
(Replace `<handle>` with actual handle from discover output, e.g., `read 15`)

### Write to Characteristic
```
write <handle> <hex_value>
```
Example:
```
write 20 0102030405
```

### Write Without Response
```
write-without-response <handle> <hex_value>
```

### Subscribe to Notifications (CCC)
```
subscribe <handle>
```

### View All Commands
```
help
```

### Disconnect
```
disconnect
```

---

## Example Workflow

```
# 1. Scan for devices
scan on
[wait a few seconds - look for your device]
scan off

# 2. Connect to a device
connect A0:B1:C2:D3:E4:F5

# 3. Discover services
discover

# 4. Read a characteristic (example handle 20)
read 20

# 5. Write to characteristic (example handle 25 with value 0x01)
write 25 01

# 6. Subscribe to notifications on characteristic (example handle 30)
subscribe 30

# 7. The device will now send notifications to handle 30
[notifications appear on screen]

# 8. Disconnect when done
disconnect
```

---

## Common Issues

### "LIBUSB_ERROR_ACCESS"
- Make sure you run **as Administrator**

### "Connection refused" when starting console
- **HCI Bridge terminal is not running!**
- Go back to Terminal 1 and start: `bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001`

### No devices appearing in scan
- Check that scan is actually on: `scan on`
- Make sure target device is advertising
- Wait 5+ seconds before turning scan off

### Can't connect to device
- Verify address format (case-insensitive)
- Device may be out of range
- Try scanning again to confirm it's still advertising

---

## Next Steps

1. Identify a BLE device to test with
2. Run scan to find its address
3. Connect and explore services
4. Test read/write operations
5. Set up subscriptions for notifications
