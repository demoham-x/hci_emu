# Generic SMP Pairing Implementation

## Overview

Implemented **generic SMP (Security Manager Protocol) pairing** for Bumble that automatically handles any BLE peripheral pairing without device-specific code.

## What Was Added

### 1. GenericPairingDelegate (in connector.py)

A flexible pairing handler that supports all SMP pairing methods:

- **Just Works**: Auto-confirms with zero-effort bonding
- **Passkey Entry**: Display or input 6-digit passkey
- **Numeric Comparison**: Display matching codes on both devices (Secure Connections)
- **Out-of-Band (OOB)**: For future extension
- **CTKD**: Cross-transport key derivation

**Constructor Parameters:**
- `interactive=True` → Prompts user for pairing decisions
- `interactive=False` → Auto-accepts all pairing requests

**Key Methods:**
- `accept()` - Accept or reject pairing request
- `confirm()` - Confirm Just Works pairing
- `compare_numbers()` - Handle numeric comparison codes
- `get_number()` - Input passkey from user
- `display_number()` - Show passkey to user
- `get_string()` - Get PIN for Classic pairing

### 2. Connected Device Pairing Setup (in main.py)

When Bluetooth is powered on, the device is configured for pairing:

```python
# Automatically set up generic SMP on scan device
self.connector.setup_pairing_on_device(self._scan_device)
```

Configuration includes:
- ✅ Secure Connections (LE SC) enabled
- ✅ MITM protection enabled
- ✅ Bonding enabled (keys stored for future reconnects)
- ✅ Random address type for privacy
- ✅ Full key distribution (encryption, identity, signing)

### 3. Pairing Initiation (in connector.py)

The `pair()` method now actually initiates SMP pairing:

```python
await self.device.pair(self.connected_device)
```

This triggers the pairing flow with automatic delegate callbacks.

### 4. Enhanced Menu Interface (in main.py)

- Connection success message shows next steps
- Menu option 8 now initiates actual SMP pairing
- Better status messages during pairing process

## How to Test

### Basic Test Sequence

```
1. Press A → Bluetooth On
   "✓ Bluetooth is ON"

2. Press 1 → Scan for devices (10-15 seconds)
   Find your target device: "RoadSync_XXXX"

3. Press 2 → Connect to Device
   Select: 1 (or any device number)
   Wait for connection...

4. Should see: "✓ Successfully connected to XX:XX:XX:XX:XX:XX"
   Shows next steps:
     - Option 3: Discover GATT Services
     - Option 8: Pair with device (if needed)
     - Option 9: Disconnect

5. Press 3 → Try to discover services
   If encrypted connection required, Bumble will auto-request pairing

6. If pairing is required, you'll see:
   
   FOR JUST WORKS:
   "✓ Just Works pairing confirmed"
   
   FOR PASSKEY:
   "📱 PASSKEY REQUIRED"
   "Enter 6-digit passkey: "
   (Get passkey from device or user manual)
   
   FOR NUMERIC COMPARISON:
   "🔐 NUMERIC COMPARISON CODE: 123456"
   "Verify this code appears on the peer device and matches!"
   "Do the codes match? (y/n): "

7. After successful pairing:
   "✓ Pairing completed successfully"
   Connection will be encrypted and bonded
```

### Pairing Flow Variations

**Scenario 1: Device requires Just Works pairing**
- Device initiates pairing after connection
- Menu shows pairing confirmation
- Press Y to accept
- Connection becomes encrypted

**Scenario 2: Device requires passkey**
1. Enter passkey shown on device (e.g., 123456)
2. Both devices confirm pairing
3. Connection becomes encrypted and bonded

**Scenario 3: Device supports Numeric Comparison (Secure Connections)**
1. 6-digit code displays on both devices
2. Verify codes match (different codes = possible attack!)
3. Press Y to confirm match
4. Connection becomes encrypted

## Technical Details

### SMP Method Selection

Bumble automatically selects the pairing method based on:
- Device I/O capabilities
- MITM requirement setting
- Secure Connections support

Decision tree:
```
Both NO_INPUT_NO_OUTPUT? → JUST_WORKS
Both DISPLAY_ONLY? → JUST_WORKS
One is KEYBOARD, other is DISPLAY? → PASSKEY_ENTRY
Both DISPLAY_AND_KEYBOARD (SC)? → NUMERIC_COMPARISON
Both DISPLAY_AND_KEYBOARD (Legacy)? → PASSKEY_ENTRY
Has OOB data? → OUT_OF_BAND
```

### Security Configuration

```python
PairingConfig(
    sc=True,                    # Secure Connections (LE SC)
    mitm=True,                  # Man-in-the-Middle protection
    bonding=True,               # Store keys for future connections
    delegate=GenericPairingDelegate(),
    identity_address_type=PairingConfig.AddressType.RANDOM
)
```

**Rationale:**
- **SC=True**: More secure than Legacy pairing
- **MITM=True**: Requires authentication method (passkey/numeric comparison)
- **Bonding=True**: Bonds automatically after successful pairing
- **RANDOM address**: Privacy protection

### Device-Agnostic Design

The implementation works with ANY BLE peripheral because:
1. **No hardcoded responses** - Delegate methods handle all scenarios
2. **Flexible I/O capabilities** - Support display, keyboard, yes/no button, or combinations
3. **Automatic method selection** - Based on peer device's capabilities
4. **Standard SMP flow** - Follows Bluetooth SIG specification

## Next Steps

After successful connection and pairing:

1. **Discover Services** (Option 3)
   - Enumerate GATT services on peripheral
   - List characteristics and descriptors

2. **Read/Write Characteristics** (Options 4-6)
   - Read attribute values
   - Write with and without response

3. **Subscribe to Notifications** (Option 7)
   - Enable client characteristic configuration (CCC)
   - Receive notification callbacks

## Troubleshooting

### "Connection timeout"
- Device may not accept connections
- Try scanning again to refresh device state
- Check if device is powered on and in range

### "Pairing failed"
- Device may require specific authentication
- Check device's supported pairing methods
- Try option B (Bluetooth Off) then A (On) to reset

### "No passkey prompt"
- Device may use Just Works pairing (no prompt needed)
- Watch for "Just Works pairing confirmed" message
- Or numeric comparison code will appear

### "Numeric Comparison code mismatch"
- ⚠️ SECURITY WARNING: Possible attack!
- DO NOT press Y if codes don't match
- Abort pairing and restart

## References

- Bumble SMP Implementation: `bumble/smp.py`
- Bumble Pairing: `bumble/pairing.py`
- Bluetooth SIG SMP Specification: Core v5.3
