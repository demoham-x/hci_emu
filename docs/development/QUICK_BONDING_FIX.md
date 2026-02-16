# Quick Implementation - Minimal Code Changes

This file shows the **exact code changes** needed to enable persistent bonding in your project.

## ✅ MIN 3-Line Fix

**Location**: `src/connector.py` - In `BLEConnector.__init__()` or after `power_on()`

```python
# Add this import at top of file
from bumble.keys import JsonKeyStore

# After device.power_on(), add:
device.keystore = JsonKeyStore.from_device(device, "bumble_bonds.json")
```

**That's it.** Bonding is now persistent.

---

## Detailed Implementation Steps

### Step 1: Add Import

**File**: `src/connector.py`

Find the imports section and add:
```python
from bumble.keys import JsonKeyStore
```

### Step 2: Setup Keystore After Power-On

**File**: `src/connector.py`

In the `BLEConnector` class, find the `power_on()` method or `__init__()` method.

**Option A: Add method to BLEConnector class**

```python
class BLEConnector:
    # ... existing code ...
    
    async def setup_bonding_persistence(self):
        """Enable persistent bonding with JsonKeyStore"""
        if self.device is None:
            logger.error("Device not initialized")
            return False
        
        try:
            self.device.keystore = JsonKeyStore.from_device(
                self.device, 
                filename="bumble_bonds.json"
            )
            logger.info("✓ Persistent bonding enabled")
            return True
        except Exception as e:
            logger.error(f"✗ Failed to setup bonding: {e}")
            return False
```

**Option B: Add directly in power_on() method**

```python
async def power_on(self):
    """Turn on Bluetooth"""
    try:
        # ... existing power-on code ...
        await self.device.power_on()
        
        # ✅ ADD THIS LINE:
        self.device.keystore = JsonKeyStore.from_device(self.device, "bumble_bonds.json")
        
        logger.info("Bluetooth is on")
        return True
    except Exception as e:
        logger.error(f"Power on failed: {e}")
        return False
```

### Step 3: Call Setup From main.py

**File**: `src/main.py`

In `BLETestingMenu.power_on()` or wherever you call `connector.power_on()`:

```python
async def power_on(self):
    """Turn on Bluetooth"""
    if self.connector.device is not None:
        if self.connector.device.is_powered_on:
            print("✗ Already powered on")
            return
    
    try:
        await self.connector.power_on()
        print("✓ Bluetooth is ON")
        
        # ✅ ADD THIS LINE:
        await self.connector.setup_bonding_persistence()
        
    except Exception as e:
        print(f"✗ Error: {e}")
```

---

## Verify It Works

After making changes:

### Test 1: Check File Created After Pairing
```bash
# In your menu:
# A - Power On
# 1 - Scan
# 2 - Connect to a device
# 8 - Pair with device
# Complete pairing

# Then check:
ls -la bumble_bonds.json
# Should show file created with size > 100 bytes

# View contents:
cat bumble_bonds.json
# Should show JSON with bonded device keys
```

### Test 2: Verify Persistence
```bash
# Kill your app (Ctrl+C)
# Wait a few seconds
# Start app again
# Power on
# In menu: 10 - Show Bonded Devices
# Should list previously bonded device

# Try connecting to the same device
# Should reconnect and establish encrypted link automatically
```

### Test 3: Run Verification Script
```bash
python verify_bonding.py
```

---

## What You Get

| Before | After |
|--------|-------|
| ❌ Bonding lost on app restart | ✅ Bonding persists in JSON file |
| ❌ Must re-pair every time | ✅ Auto-reconnect with encryption |
| ❌ Keys only in RAM | ✅ Keys saved to disk |
| ❌ No bonding list | ✅ Can list bonded devices |

---

## File Locations

After first pairing, look for:
- **Windows**: `bumble_bonds.json` (current directory or in app folder)
- **Linux**: `~/.local/share/Bumble/Pairing/bonds.json`
- **Mac**: `~/Library/Application Support/Bumble/Pairing/bonds.json`

You can specify custom location:
```python
device.keystore = JsonKeyStore.from_device(device, "/custom/path/bonds.json")
```

---

## Troubleshooting

**Q: File not created**
- A: Make sure `setup_bonding_persistence()` is actually called AFTER `power_on()`

**Q: "Device not initialized" error**
- A: Call setup after device is powered on, not before

**Q: File created but no bonded devices after restart**
- A: File created successfully, but pairing never completed. Check pairing logs.

**Q: Permission denied**
- A: Check file permissions on `bumble_bonds.json`. Delete it and restart.

**Q: KeyError when trying to get bonded devices**
- A: No devices bonded yet. Pair a device first using menu option 8.

---

## Code Reference

| Operation | Code |
|-----------|------|
| **Enable bonding** | `device.keystore = JsonKeyStore.from_device(device, "file.json")` |
| **Get all bonded** | `await device.keystore.get_all()` |
| **Get one device** | `await device.keystore.get("address")` |
| **Remove bonding** | `await device.keystore.delete("address")` |
| **Check bonding** | `if await device.keystore.get(address):` |

---

## Example: Complete Setup Function

```python
from bumble.keys import JsonKeyStore
import logging

logger = logging.getLogger(__name__)

class BLEConnector:
    def __init__(self, ...):
        # ... existing init ...
        self.keystore_file = "bumble_bonds.json"
    
    async def power_on(self):
        """Power on device and setup persistence"""
        try:
            await self.device.power_on()
            
            # Setup persistent bonding
            self.device.keystore = JsonKeyStore.from_device(
                self.device,
                self.keystore_file
            )
            
            # List any existing bonded devices
            bonded = await self.device.keystore.get_all()
            if bonded:
                logger.info(f"Found {len(bonded)} bonded devices:")
                for addr, keys in bonded:
                    logger.info(f"  - {addr}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to power on: {e}")
            return False
```

---

## Advanced: Custom Keystore Path

If you want keys stored in a custom location:

```python
import os
from pathlib import Path

# Option 1: Specific directory
bonds_dir = Path.home() / ".bumble_bonds"
bonds_dir.mkdir(exist_ok=True)
device.keystore = JsonKeyStore.from_device(device, str(bonds_dir / "bonds.json"))

# Option 2: Project-local directory
bonds_file = Path(__file__).parent / "data" / "bonds.json"
bonds_file.parent.mkdir(exist_ok=True)
device.keystore = JsonKeyStore.from_device(device, str(bonds_file))

# Option 3: Environment variable
import os
bonds_file = os.getenv("BUMBLE_BONDS", "bumble_bonds.json")
device.keystore = JsonKeyStore.from_device(device, bonds_file)
```

---

## Next Steps After Implementation

1. ✅ Add the 3 lines of code above
2. ✅ Test pairing and verify file created
3. ✅ Run verification script: `python verify_bonding.py`
4. ✅ Test power-off/on cycle persistence
5. ✅ (Optional) Add menu options for managing bonded devices

See `BONDING_IMPLEMENTATION_GUIDE.md` for full menu integration examples.
