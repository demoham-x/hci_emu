# Implementation Guide: Enable Persistent Bonding in Your Project

This guide shows exactly how to modify your existing Bumble HCI Testing Project to enable **persistent bonding with real key storage**.

---

## TL;DR - Quick Start

Replace your device initialization with this:

```python
from bumble.keys import JsonKeyStore

# After creating device
await device.power_on()

# Add this ONE line:
device.keystore = JsonKeyStore.from_device(device, "bumble_bonds.json")

# That's it! Bonding is now persistent.
```

---

## Full Implementation for Your Project

### File 1: Modify `src/connector.py`

Add this import at the top:
```python
from bumble.keys import JsonKeyStore
```

Then modify `BLEConnector.__init__()`:
```python
class BLEConnector:
    """BLE Device Connection Manager"""
    
    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001", interactive: bool = True):
        self.transport_spec = transport_spec
        self.device = None
        self.connected_device = None
        self.services = {}
        self.characteristics = {}
        self.interactive = interactive
        self.pairing_delegate = None
        
        # ✅ NEW: Store keystore file path
        self.keystore_file = "bumble_bonds.json"
    
    async def setup_keystore(self):
        """Enable persistent bonding with JsonKeyStore"""
        if self.device is None or not hasattr(self.device, 'keystore'):
            logger.error("Device not initialized")
            return False
        
        try:
            # Replace default MemoryKeyStore with persistent JsonKeyStore
            self.device.keystore = JsonKeyStore.from_device(
                self.device,
                filename=self.keystore_file
            )
            
            logger.info(f"✓ Persistent bonding enabled: {self.keystore_file}")
            
            # List previously bonded devices
            bonded = await self.device.keystore.get_all()
            if bonded:
                logger.info(f"  Found {len(bonded)} previously bonded device(s):")
                for addr, keys in bonded:
                    has_ltk = keys.ltk is not None or keys.ltk_central is not None
                    print(f"    - {addr}: LTK={'✓' if has_ltk else '✗'}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to setup keystore: {e}")
            return False
    
    async def get_bonded_devices(self) -> Dict:
        """Get list of bonded devices"""
        if self.device is None or self.device.keystore is None:
            return {}
        
        try:
            bonded_list = await self.device.keystore.get_all()
            bonded_dict = {}
            
            for addr, keys in bonded_list:
                bonded_dict[addr] = {
                    'address': addr,
                    'ltk': keys.ltk is not None or keys.ltk_central is not None,
                    'irk': keys.irk is not None,
                    'csrk': keys.csrk is not None,
                    'authenticated': (
                        (keys.ltk and keys.ltk.authenticated) or
                        (keys.ltk_central and keys.ltk_central.authenticated) or
                        False
                    )
                }
            
            return bonded_dict
        except Exception as e:
            logger.error(f"Error getting bonded devices: {e}")
            return {}
    
    async def unbond_device(self, address: str) -> bool:
        """Remove bonding for a device"""
        if self.device is None or self.device.keystore is None:
            logger.error("Keystore not available")
            return False
        
        try:
            await self.device.keystore.delete(address)
            logger.info(f"✓ Unbonded: {address}")
            return True
        except KeyError:
            logger.warning(f"Device not bonded: {address}")
            return False
        except Exception as e:
            logger.error(f"Error unbonding device: {e}")
            return False
```

---

### File 2: Modify `src/main.py`

Add import:
```python
from bumble.keys import JsonKeyStore
```

Modify `BLETestingMenu` class:

```python
class BLETestingMenu:
    """Interactive BLE Testing Menu"""
    
    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001"):
        # ... existing code ...
        
        # ✅ NEW: Store for bonding operations
        self.bonded_devices = {}
    
    async def power_on(self):
        """Turn on Bluetooth and setup bonding"""
        if self.connector.device is not None:
            if self.connector.device.is_powered_on:
                print("✗ Already powered on")
                return
        
        try:
            await self.connector.power_on()
            print("✓ Bluetooth is ON")
            
            # ✅ NEW: Setup persistent bonding AFTER power on
            if await self.connector.setup_keystore():
                print("✓ Bonding persistence enabled")
                
                # Refresh bonded devices list
                self.bonded_devices = await self.connector.get_bonded_devices()
            
        except Exception as e:
            print(f"✗ Error powering on: {e}")
    
    def print_main_menu(self):
        """Print main menu"""
        print_section("BUMBLE BLE Testing - Main Menu")
        print("A. Bluetooth On")
        print("B. Bluetooth Off")
        print("C. Set Device Filters")
        print("1. Scan for BLE Devices")
        print("2. Connect to Device")
        print("3. Discover GATT Services")
        print("4. Read Characteristic")
        print("5. Write Characteristic")
        print("6. Write Without Response")
        print("7. Subscribe to Notifications")
        print("8. Pair with Device")
        print("9. Unpair / Delete Bonding")
        print("10. Show Bonded Devices")  # ✅ NEW
        print("11. Disconnect")
        print("0. Exit")
        
        # Show bonding status
        if self.bonded_devices:
            print(f"\n[Bonded Devices: {len(self.bonded_devices)}]")
        print()
    
    async def show_bonded_devices(self):
        """Display all bonded devices"""
        if not self.bonded_devices:
            print("\n✗ No bonded devices")
            return
        
        print_section("Bonded Devices")
        
        if HAS_RICH:
            from rich.table import Table
            table = Table(title="Bonded Devices", show_header=True, header_style="bold cyan")
            table.add_column("Address", style="green", width=20)
            table.add_column("LTK", style="yellow", width=4)
            table.add_column("IRK", style="yellow", width=4)
            table.add_column("Auth", style="cyan", width=6)
            
            for addr, info in self.bonded_devices.items():
                table.add_row(
                    addr,
                    "✓" if info['ltk'] else "✗",
                    "✓" if info['irk'] else "✗",
                    "✓" if info['authenticated'] else "✗",
                )
            
            console.print(table)
        else:
            for addr, info in self.bonded_devices.items():
                print(f"  {addr}")
                print(f"    LTK: {'✓' if info['ltk'] else '✗'}, " +
                      f"IRK: {'✓' if info['irk'] else '✗'}, " +
                      f"Auth: {'✓' if info['authenticated'] else '✗'}")
    
    async def unpair_device(self):
        """Unpair a bonded device"""
        if not self.bonded_devices:
            print("✗ No bonded devices")
            return
        
        print("\nBonded devices:")
        for i, addr in enumerate(self.bonded_devices.keys(), 1):
            print(f"  {i}. {addr}")
        
        try:
            choice = input("Select device to unpair (number or address): ").strip()
            
            if choice.isdigit():
                idx = int(choice) - 1
                address = list(self.bonded_devices.keys())[idx]
            else:
                address = choice
            
            if await self.connector.unbond_device(address):
                del self.bonded_devices[address]
                print(f"✓ Unpaired: {address}")
                
                # Refresh from device
                self.bonded_devices = await self.connector.get_bonded_devices()
            
        except (ValueError, IndexError):
            print("✗ Invalid selection")
    
    async def run_menu(self):
        """Main menu loop"""
        while True:
            self.print_main_menu()
            choice = input("Enter choice: ").strip().upper()
            
            try:
                if choice == "A":
                    await self.power_on()
                
                elif choice == "B":
                    # ... existing power off code ...
                    pass
                
                elif choice == "1":
                    # ... existing scan code ...
                    pass
                
                elif choice == "8":
                    # Pair with device
                    # ... existing pairing code ...
                    # After successful pairing, update bonded list:
                    self.bonded_devices = await self.connector.get_bonded_devices()
                    print("✓ Bonding keys saved!")
                
                elif choice == "9":
                    # ✅ NEW: Unpair device
                    await self.unpair_device()
                
                elif choice == "10":
                    # ✅ NEW: Show bonded devices
                    await self.show_bonded_devices()
                
                elif choice == "11":
                    # Disconnect
                    # ... existing code ...
                    pass
                
                elif choice == "0":
                    print("Exiting...")
                    break
                
                else:
                    print("✗ Invalid choice")
            
            except Exception as e:
                print(f"✗ Error: {e}")
```

---

### File 3: Update setup_pairing_on_device() (Verify existing code)

Your current code in `src/connector.py` already has `bonding=True`:

```python
# ✅ GOOD - Already correct
def setup_pairing_on_device(self, device):
    config = PairingConfig(
        sc=True,
        mitm=True,
        bonding=True,  # ✅ This enables bonding!
        delegate=delegate,
        identity_address_type=PairingConfig.AddressType.RANDOM
    )
```

**No changes needed here!** Your pairing config is already correct.

---

### File 4: Create Verification Script

Create `verify_bonding.py`:

```python
#!/usr/bin/env python3
"""Verify that bonding is working and keys are persisted"""

import json
import os
import asyncio
from pathlib import Path

def verify_keystore_file():
    """Check if keystore file exists and contains bonded devices"""
    
    # Check default location
    default_paths = [
        "bumble_bonds.json",
        os.path.expanduser("~/.local/share/Bumble/Pairing/keys.json"),
        os.path.expanduser("~/Library/Application Support/Bumble/Pairing/keys.json"),
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            print(f"✓ Found keystore: {path}\n")
            
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                
                print("Bonded Devices:")
                total_bonds = 0
                
                for namespace, peers in data.items():
                    print(f"\n  Namespace: {namespace}")
                    for addr, keys in peers.items():
                        total_bonds += 1
                        
                        # Check key types
                        has_ltk = 'ltk' in keys or 'ltk_central' in keys or 'ltk_peripheral' in keys
                        has_irk = 'irk' in keys
                        has_csrk = 'csrk' in keys
                        has_link_key = 'link_key' in keys
                        
                        print(f"    {addr}:")
                        print(f"      LTK:  {'✓' if has_ltk else '✗'}")
                        print(f"      IRK:  {'✓' if has_irk else '✗'}")
                        print(f"      CSRK: {'✓' if has_csrk else '✗'}")
                        if has_link_key:
                            print(f"      Link Key: ✓ (Classic)")
                
                print(f"\n✓ Total Bonded Devices: {total_bonds}")
                return True
                
            except json.JSONDecodeError as e:
                print(f"✗ Error parsing JSON: {e}")
                return False
    
    print("✗ No keystore file found")
    print(f"  Expected locations:")
    for path in default_paths:
        print(f"    - {path}")
    return False

async def test_keystore_persistence():
    """Test that bonding keys persist"""
    from bumble.device import Device
    from bumble.keys import JsonKeyStore, PairingKeys
    
    print("\n" + "="*60)
    print("Testing Bonding Persistence")
    print("="*60)
    
    test_file = "test_bonding.json"
    test_address = "80:E4:BA:42:E9:AF"
    
    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # Step 1: Create keystore and add bonding
    print("\n1️⃣  Simulating pairing and bonding...")
    device = Device.from_config_file_with_hci(
        "configs/pytest.device",
        None, None  # Don't need HCI for this test
    )
    await device.power_on()
    device.keystore = JsonKeyStore.from_device(device, test_file)
    
    # Simulate bonding by adding test keys
    test_keys = PairingKeys(
        address_type=1,  # RANDOM
        ltk=PairingKeys.Key(
            value=b'\x00' * 16,
            authenticated=True,
            ediv=12345,
            rand=b'\x01' * 8
        ),
        irk=PairingKeys.Key(
            value=b'\x02' * 16,
            authenticated=True
        ),
    )
    
    await device.keystore.update(test_address, test_keys)
    print(f"  ✓ Bonding keys stored: {test_address}")
    
    # Step 2: Verify file created
    print("\n2️⃣  Verifying file persistence...")
    if os.path.exists(test_file):
        with open(test_file, 'r') as f:
            data = json.load(f)
        print(f"  ✓ File created: {test_file}")
        print(f"  ✓ File size: {os.path.getsize(test_file)} bytes")
    else:
        print(f"  ✗ File not created")
        return False
    
    # Step 3: Simulate power-off and reload
    print("\n3️⃣  Simulating power-off and reload...")
    del device  # "Power off"
    
    # "Power on" new device
    device2 = Device.from_config_file_with_hci(
        "configs/pytest.device",
        None, None
    )
    await device2.power_on()
    device2.keystore = JsonKeyStore.from_device(device2, test_file)
    
    # Step 4: Verify keys restored
    print("\n4️⃣  Verifying bonding persistence...")
    restored_keys = await device2.keystore.get(test_address)
    
    if restored_keys is None:
        print(f"  ✗ Keys not restored")
        return False
    
    print(f"  ✓ Keys successfully restored!")
    
    if restored_keys.ltk:
        print(f"    LTK: {restored_keys.ltk.value.hex()[:16]}...")
        print(f"    Authenticated: {restored_keys.ltk.authenticated}")
    
    if restored_keys.irk:
        print(f"    IRK: {restored_keys.irk.value.hex()[:16]}...")
    
    print("\n✅ BONDING WORKS! Keys persist across power cycles")
    
    # Cleanup
    os.remove(test_file)
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("BUMBLE BONDING VERIFICATION")
    print("="*60)
    
    # Check for existing keystore
    print("\n1. Checking for existing bonded devices...")
    verify_keystore_file()
    
    # Test persistence
    print("\n2. Testing bonding persistence...")
    try:
        result = asyncio.run(test_keystore_persistence())
        if result:
            print("\n" + "="*60)
            print("✅ ALL TESTS PASSED - BONDING WORKING!")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("❌ TESTS FAILED")
            print("="*60)
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
```

---

## Testing Your Implementation

### Test 1: Enable Bonding
```bash
cd c:\workspace\misc\bumble_hci

# Start HCI bridge (Terminal 1)
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001

# Run your application (Terminal 2)
python src/main.py

# Menu sequence:
# A - Power On        → Should show setup_keystore messages
# 1 - Scan            → Find a device
# 2 - Connect         → Connect
# 8 - Pair            → Complete pairing (bonding=True)
#     Should see: "✓ Bonding keys saved!"
# 10 - Show Bonded    → Should list the just-bonded device
```

### Test 2: Verify File Created
```bash
# Check JSON file created
cat bumble_bonds.json

# Should show structure like:
# {
#   "F0:F1:F2:F3:F4:F5": {
#     "80:E4:BA:42:E9:AF": {
#       "ltk_central": {...},
#       "ltk_peripheral": {...},
#       "irk": {...}
#     }
#   }
# }
```

### Test 3: Verify Persistence
```python
# Run verification script
python verify_bonding.py

# Should output:
# ✓ Found keystore: bumble_bonds.json
# Bonded Devices:
#   Namespace: F0:F1:F2:F3:F4:F5
#     80:E4:BA:42:E9:AF:
#       LTK:  ✓
#       IRK:  ✓
#       CSRK: ✓
# ✓ Total Bonded Devices: 1
```

### Test 4: Power-Off/On Cycle
```bash
# Kill application (simulates power-off)
# Check that bumble_bonds.json still exists
# Restart application
# Menu: A (Power On)
# Should see: "Found X previously bonded device(s)"
# This proves bonding persisted!
```

---

## Summary of Changes

| Component | Change | Impact |
|---|---|---|
| `connector.py` | Add `JsonKeyStore` setup | Enables persistent storage |
| `connector.py` | Add `get_bonded_devices()` | Can list bonded devices |
| `connector.py` | Add `unbond_device()` | Can remove bonds |
| `main.py` | Call `setup_keystore()` after power on | Activates persistence |
| `main.py` | Add menu options 10, 11 | UI for bonding mgmt |
| `pairing_config` | Already has `bonding=True` | No changes needed |

---

## What Happens Now

### Before Implementation
- ❌ Bonding data stored only in RAM (MemoryKeyStore)
- ❌ Keys lost on power-off
- ❌ Must re-pair every connection

### After Implementation
- ✅ Bonding data persisted to `bumble_bonds.json`
- ✅ Keys survive power-off/restart
- ✅ Previous devices auto-encrypt on reconnection
- ✅ Bonded list visible in command menu

---

## Troubleshooting

### "No bonded devices after restart"
1. Check `bumble_bonds.json` exists
2. Verify `setup_keystore()` is called
3. Ensure pairing actually completed (check logs)

### "KeyError when trying to unpair"
- Device not actually bonded (doesn't exist in keystore)
- Check with `show_bonded_devices()` first

### "File not found: bumble_bonds.json"
- Either never paired, or file in different directory
- Check with `verify_bonding.py` script

### "Keystore locked/permission denied"
- File locked by another instance
- Close all Bumble applications
- Delete `bumble_bonds.json` and start fresh

