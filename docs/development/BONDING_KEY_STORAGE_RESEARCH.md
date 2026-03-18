# Bumble Bonding & Key Storage Implementation Research

## Executive Summary

**YES** - Bumble has built-in key storage and bonding support. You can enable persistent bonding by configuring a `JsonKeyStore`. Without explicit configuration, keys are stored in-memory and are lost on device power off.

---

## 1. Built-in Key Storage in Bumble

### Architecture
Bumble provides a **KeyStore interface** (`bumble/keys.py`) with two implementations:

#### 1.1 JsonKeyStore (Persistent, File-Based)
- **Location**: `~/.local/share/Bumble/Pairing/` (Linux/Mac) or equivalent Windows path
- **Format**: JSON file with hierarchical structure (by namespace and device address)
- **Persistence**: Survives device power-off and application restart
- **Namespacing**: Keys organized by controller address (namespace)
- **Thread-Safe**: Uses atomic file operations (write to temp file, then rename)

#### 1.2 MemoryKeyStore (In-Memory, Default)
- **Storage**: Python dictionary in RAM
- **Persistence**: Lost when device powers off or app closes
- **Default behavior**: If no keystore configured and device.power_on() is called

#### 1.3 Abstract KeyStore Base Class
All keystores inherit from `KeyStore` and implement:
```python
# Core methods
async def delete(name: str) -> None
async def update(name: str, keys: PairingKeys) -> None
async def get(name: str) -> PairingKeys | None
async def get_all() -> list[tuple[str, PairingKeys]]
async def delete_all() -> None
async def get_resolving_keys() -> list[tuple[bytes, hci.Address]]  # For address resolution
async def print(prefix: str = '')  # Display keys
```

---

## 2. Available Keystores

| Keystore Type | Persistence | Storage | Best For |
|---|---|---|---|
| `JsonKeyStore` | ✅ File-based | JSON file | Production, persistent bonding |
| `MemoryKeyStore` | ❌ RAM only | Dictionary | Testing, ephemeral connections |
| Custom | Depends | Depends | Special requirements |

### JsonKeyStore File Structure
```json
{
  "F0:F1:F2:F3:F4:F5": {  // Namespace (controller address)
    "80:E4:BA:42:E9:AF/P": {  // Peer address
      "address_type": 1,        // RANDOM_DEVICE_ADDRESS
      "ltk_central": {
        "value": "d1897ee10016eb1a08e4e037fd54c683",
        "authenticated": true,
        "ediv": 12345,
        "rand": "0102030405060708"
      },
      "ltk_peripheral": { ... },
      "irk": { ... },           // Identity Resolving Key
      "csrk": { ... },          // Connection Signature Resolving Key
      "link_key": { ... },      // Classic mode
      "link_key_type": 5
    }
  }
}
```

---

## 3. How to Enable Persistent Bonding in Bumble

### Step 1: Configure JsonKeyStore
```python
from bumble.keys import JsonKeyStore
from bumble.device import Device

# Method 1: Directly assign keystore after instance creation
device = Device.with_hci(...)
await device.power_on()  # Creates default MemoryKeyStore
device.keystore = JsonKeyStore.from_device(device, filename="my_keys.json")

# Method 2: Via device config (recommended)
device.config.keystore = "JsonKeyStore:/path/to/keystore.json"

# Method 3: Explicit instantiation
keystore = JsonKeyStore(namespace="F0:F1:F2:F3:F4:F5", filename="keys.json")
device.keystore = keystore
```

### Step 2: Enable Bonding in Pairing Configuration
```python
from bumble.pairing import PairingConfig, PairingDelegate

def pairing_config_factory(connection):
    return PairingConfig(
        sc=True,                    # Secure Connections (LE SC)
        mitm=True,                  # Man-in-the-Middle protection
        bonding=True,               # ⭐ ENABLE BONDING - stores keys persistently
        delegate=PairingDelegate(
            io_capability=PairingDelegate.IoCapability.DISPLAY_OUTPUT_AND_KEYBOARD_INPUT,
            local_initiator_key_distribution=(
                PairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY |
                PairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY |
                PairingDelegate.KeyDistribution.DISTRIBUTE_SIGNING_KEY
            ),
            local_responder_key_distribution=(
                PairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY |
                PairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY |
                PairingDelegate.KeyDistribution.DISTRIBUTE_SIGNING_KEY
            ),
        ),
        identity_address_type=PairingConfig.AddressType.RANDOM,
    )

device.pairing_config_factory = pairing_config_factory
```

### Step 3: Power On Device
```python
await device.power_on()

# Now the device has:
# 1. JsonKeyStore ready for persistence
# 2. SMP Manager listening for pairing events
# 3. Resolving list loaded with IRK keys from previous bonds
```

---

## 4. Custom vs Built-in Key Storage

| Aspect | Built-in | Custom |
|---|---|---|
| **Do You Need It?** | ✅ In most cases, JsonKeyStore is sufficient | ❌ Only for special requirements |
| **Difficulty** | Easy - configure and use | Medium-Hard - implement KeyStore interface |
| **Common Custom Use Cases** | Database (SQL, NoSQL), encrypted storage, cloud sync, HSM integration | See below |
| **Implementation** | 2-3 lines of code | Implement 6 async methods |

### When to Implement Custom KeyStore
1. **Database Storage** - SQLite, PostgreSQL, Firebase, etc.
2. **Encrypted Storage** - AES-encrypted key files
3. **Cloud Sync** - Sync keys across devices (AWS, Azure)
4. **Hardware Security Modules** - HSM integration
5. **Complex Namespacing** - Application-specific key organization

### Custom KeyStore Example
```python
from bumble.keys import KeyStore, PairingKeys

class CustomKeyStore(KeyStore):
    async def delete(self, name: str) -> None:
        # Delete from database or encrypted storage
        pass

    async def update(self, name: str, keys: PairingKeys) -> None:
        # Save to database or encrypted storage
        pass

    async def get(self, name: str) -> PairingKeys | None:
        # Retrieve from database or encrypted storage
        return None

    async def get_all(self) -> list[tuple[str, PairingKeys]]:
        # Return all bonded devices
        return []

    async def delete_all(self) -> None:
        # Clear all bonded devices
        pass

device.keystore = CustomKeyStore()
```

---

## 5. How Bonding Keys Are Stored and Retrieved

### Storage Flow (During Pairing)
```
1. Pairing initiated via SMP protocol
2. SMP Session completes pairing
3. Session.on_pairing() creates PairingKeys object with:
   - ltk_central: Long-Term Key (initiator/central role)
   - ltk_peripheral: Long-Term Key (responder/peripheral role)
   - irk: Identity Resolving Key (for address resolution)
   - csrk: Connection Signature Resolving Key (for signed writes)
   - link_key: (Classic BLE only)

4. Manager.on_pairing() calls device.update_keys(address, keys)
5. device.update_keys() calls keystore.update(address, keys)
6. JsonKeyStore.update():
   - Loads existing JSON
   - Updates with new keys via to_dict()
   - Atomically saves to file

7. device.refresh_resolving_list() adds IRK to controller's resolving list
8. device emits EVENT_KEY_STORE_UPDATE
```

### Retrieval Flow (After Bonding)
```
1. Device power-on
2. If JsonKeyStore configured:
   - Load keys from JSON file
   - Extract IRK values via get_resolving_keys()
   - Populate controller's resolving list

3. On connection encryption request:
   - Device looks up LTK in keystore via get()
   - Uses stored LTK to complete encryption setup
   - Connection remains encrypted without re-pairing

4. On privacy scenario:
   - Resolvable Private Address (RPA) received from peer
   - Controller uses resolving list to find IRK
   - Resolves RPA to identity address
   - Keystore retrieves full keys for that address
```

### Code Location: `bumble/smp.py` - Session.on_pairing()
```python
async def on_pairing(self) -> None:
    logger.debug('pairing complete')
    # ... validation ...
    
    # Create keys object
    keys = PairingKeys()
    keys.address_type = peer_address.address_type
    authenticated = self.pairing_method != PairingMethod.JUST_WORKS
    
    # Populate key fields
    if self.sc or self.connection.transport == PhysicalTransport.BR_EDR:
        keys.ltk = PairingKeys.Key(value=self.ltk, authenticated=authenticated)
    
    if self.is_initiator:
        keys.ltk_central = peer_ltk_key
        keys.ltk_peripheral = our_ltk_key
    else:
        keys.ltk_central = our_ltk_key
        keys.ltk_peripheral = peer_ltk_key
    
    if self.peer_identity_resolving_key:
        keys.irk = PairingKeys.Key(value=...)
    
    if self.peer_signature_key:
        keys.csrk = PairingKeys.Key(value=...)
    
    # Store via manager
    await self.manager.on_pairing(self, peer_address, keys)
```

---

## 6. What Happens to Bonding Keys After Device Power Off

| Scenario | Result | Recovery |
|---|---|---|
| **JsonKeyStore + Power Off** | ✅ Keys persisted to disk | Automatically loaded on next power_on() |
| **MemoryKeyStore + Power Off** | ❌ Keys lost (RAM cleared) | Must pair again |
| **JsonKeyStore + File Deleted** | ❌ Keys lost | Must pair again |
| **JsonKeyStore + Corrupted File** | ⚠️ Depends on corruption type | May lose all or some pairings |

### Timeline
```
T0: Device paired, bonding=True, JsonKeyStore configured
    ✅ Keys written to disk: ~/.local/share/Bumble/Pairing/<address>.json

T1: Device powered off
    ✅ JSON file remains on disk

T2: Application/system restarted

T3: Device powered on again
    1. device.power_on() called
    2. KeyStore.create_for_device() checks config.keystore
    3. JsonKeyStore instantiated, loads JSON file
    4. Called device.refresh_resolving_list()
    5. IRKs from all bonded devices loaded into controller
    ✅ Ready to reconnect without re-pairing

T4: Previously bonded peer connects
    1. Peer may advertise with Resolvable Private Address (RPA)
    2. Controller's resolving list resolves RPA to identity address
    3. device.lookup_connection() finds stored LTK
    4. Encryption completed using stored LTK
    ✅ Connection encrypted without re-pairing!
```

---

## 7. Code Examples for Proper Bonding Configuration

### Example 1: Basic Bonding with JsonKeyStore
```python
import asyncio
from bumble.device import Device
from bumble.keys import JsonKeyStore
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.transport import open_transport

async def setup_bonding():
    # Open HCI transport
    async with await open_transport("usb:0") as (hci_source, hci_sink):
        # Create device
        device = Device.with_hci(
            name="BondingDevice",
            address="F0:F1:F2:F3:F4:F5",
            hci_source=hci_source,
            hci_sink=hci_sink,
        )
        
        # Power on (creates default MemoryKeyStore)
        await device.power_on()
        
        # Switch to persistent JsonKeyStore
        device.keystore = JsonKeyStore.from_device(
            device, 
            filename="bonded_devices.json"
        )
        
        # Configure pairing
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True,
            mitm=True,
            bonding=True,  # ⭐ KEY: Enable bonding
            delegate=PairingDelegate(
                io_capability=PairingDelegate.IoCapability.NO_OUTPUT_NO_INPUT,
                local_initiator_key_distribution=(
                    PairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY |
                    PairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY
                ),
            ),
        )
        
        # Listen for bonding events
        device.on("key_store_update", lambda: print("✓ Keys stored!"))
        
        # Start advertising
        await device.start_advertising()
        
        # Keep running
        await asyncio.sleep(300)

asyncio.run(setup_bonding())
```

### Example 2: Load Previously Bonded Devices
```python
async def list_bonded_devices():
    """Show all previously bonded devices"""
    device = Device.with_hci(...)
    await device.power_on()
    
    device.keystore = JsonKeyStore.from_device(device, "bonded_devices.json")
    
    # Get all bonded addresses
    bonded = await device.keystore.get_all()
    
    print("Previously bonded devices:")
    for address, keys in bonded:
        authenticated = "Yes" if keys.ltk and keys.ltk.authenticated else "No"
        print(f"  {address} - LTK: {keys.ltk is not None}, IRK: {keys.irk is not None}")
        if keys.ltk:
            print(f"    Authenticated: {authenticated}")

asyncio.run(list_bonded_devices())
```

### Example 3: Verify Bonding Actually Works
```python
async def test_bonding():
    """Test that bonding persists across power cycles"""
    import json
    import os
    
    device = Device.with_hci(...)
    await device.power_on()
    
    keystore_file = "test_bonding.json"
    device.keystore = JsonKeyStore.from_device(device, keystore_file)
    
    # Pair with device (simulated)
    print("Simulating pairing...")
    from bumble.keys import PairingKeys
    test_keys = PairingKeys(
        address_type=1,
        ltk=PairingKeys.Key(value=b'\x00' * 16, authenticated=True),
        irk=PairingKeys.Key(value=b'\x01' * 16, authenticated=True),
    )
    
    await device.keystore.update("80:E4:BA:42:E9:AF", test_keys)
    
    # Verify file created
    if os.path.exists(keystore_file):
        print(f"✓ Keystore file created: {keystore_file}")
        
        with open(keystore_file, 'r') as f:
            data = json.load(f)
            print(f"✓ Keys persisted to disk:")
            print(f"  Namespaces: {list(data.keys())}")
            for ns, peers in data.items():
                print(f"  Peers in {ns}: {list(peers.keys())}")
    
    # Simulate power-off and power-on
    print("\nSimulating power-off...")
    device_copy = Device.with_hci(...)
    await device_copy.power_on()
    device_copy.keystore = JsonKeyStore.from_device(device_copy, keystore_file)
    
    # Verify keys still available
    loaded_keys = await device_copy.keystore.get("80:E4:BA:42:E9:AF")
    if loaded_keys and loaded_keys.ltk:
        print("✓ Bonding WORKS! Keys persist after power-off")
        print(f"  Loaded LTK: {loaded_keys.ltk.value.hex()}")
    else:
        print("✗ Bonding FAILED - keys not restored")

asyncio.run(test_bonding())
```

---

## 8. PairingConfig Bonding Flag - What It Actually Does

### Flag: `bonding: bool = True`

The `bonding` flag tells the SMP (Security Manager Protocol) whether to save bonding keys:

```python
class PairingConfig:
    def __init__(
        self,
        sc: bool = True,                    # Use Secure Connections
        mitm: bool = True,                  # Require authentication
        bonding: bool = True,               # ⭐ THIS FLAG
        delegate: PairingDelegate | None = None,
        ...
    ):
        self.bonding = bonding
```

### What `bonding=True` Does
1. **During SMP Pairing**: Sets BONDING flag in Auth Req byte (Bluetooth spec Vol 3, Part H)
2. **After Successful Pairing**: 
   - Triggers `Manager.on_pairing()` 
   - Calls `device.update_keys()`
   - Stores keys in keystore via `keystore.update()`
3. **On Device Reconnection**:
   - Restored keys used for encryption
   - No need to re-pair
   - Fast re-connection

### What `bonding=False` Does
1. **During SMP Pairing**: No BONDING flag set
2. **After Successful Pairing**:
   - Keys generated locally but NOT stored
   - `keystore.update()` not called
   - Keys discarded on disconnection
3. **On Device Reconnection**:
   - No stored keys available
   - Must pair again for encryption
   - Full pairing flow every connection

### SMP Wire-Level: `Auth Req` Byte

| Bit | Flag | `bonding=True` | `bonding=False` |
|---|---|---|---|
| 0 | Bonding | **1** | **0** |
| 1 | MITM | Depends on `mitm` flag | Depends on `mitm` flag |
| 2 | SC | Depends on `sc` flag | Depends on `sc` flag |
| 3 | Keypress | 0 (usually) | 0 (usually) |

---

## 9. Where Key Storage Is Implemented in Bumble Source Code

### File Hierarchy
```
bumble/
├── keys.py              ⭐ Core key storage (KeyStore, JsonKeyStore, MemoryKeyStore, PairingKeys)
├── device.py            ⭐ Device class with keystore integration (update_keys, refresh_resolving_list)
├── smp.py               ⭐ SMP pairing (Session.on_pairing, Manager.on_pairing)
├── pairing.py           ⭐ PairingConfig and PairingDelegate
└── ...
```

### Key Functions

#### 1. **bumble/keys.py** - Core Implementation
`KeyStore` base class and implementations:
- `KeyStore.create_for_device()` - Factory method
- `JsonKeyStore.__init__()` - Initialize JSON storage
- `JsonKeyStore.load()` - Load JSON file
- `JsonKeyStore.save()` - Save to file (atomic write)
- `JsonKeyStore.update()` - Store keys
- `JsonKeyStore.get()` - Retrieve keys
- `MemoryKeyStore.update()` / `MemoryKeyStore.get()`

#### 2. **bumble/device.py** - Device Integration
```python
# Line ~4100: Device.__init__() sets up keystore
if self.keystore is None:
    self.keystore = KeyStore.create_for_device(self)

# Line ~4947: update_keys() stores keys
async def update_keys(self, address: str, keys: PairingKeys) -> None:
    if self.keystore is None:
        return
    await self.keystore.update(address, keys)
    await self.refresh_resolving_list()
    self.emit(self.EVENT_KEY_STORE_UPDATE)

# Line ~4840+: get_long_term_key() retrieves for encryption
async def get_long_term_key(self, ...):
    keys = await self.keystore.get(str(address))
    if keys and keys.ltk:
        return keys.ltk.value
```

#### 3. **bumble/smp.py** - Pairing & Key Generation
```python
# Line ~1329-1390: Session.on_pairing() - Creates PairingKeys
async def on_pairing(self):
    keys = PairingKeys()
    keys.ltk = PairingKeys.Key(value=self.ltk, ...)
    keys.irk = PairingKeys.Key(value=self.peer_identity_resolving_key, ...)
    keys.csrk = PairingKeys.Key(value=self.peer_signature_key, ...)
    await self.manager.on_pairing(self, peer_address, keys)

# Line ~2015-2025: Manager.on_pairing() - Calls device.update_keys()
async def on_pairing(self, session, identity_address, keys):
    if self.device.keystore and identity_address is not None:
        await self.device.update_keys(str(identity_address), keys)
    self.device.on_pairing(...)
```

#### 4. **bumble/pairing.py** - Configuration
```python
# Line ~232-260: PairingConfig class
class PairingConfig:
    def __init__(self, sc=True, mitm=True, bonding=True, ...):
        self.bonding = bonding
        # When bonding=True:
        # - Auth Req byte includes BONDING flag (0x01)
        # - SMP sends Auth Req with bonding bit set
        # - After pairing, keys stored (no validation, just stored)
```

---

## 10. Verifying Bonding Actually Works

### Method 1: Check Keystore File
```python
import json
import os

def verify_bonding():
    keystore_path = os.path.expanduser("~/.local/share/Bumble/Pairing/keys.json")
    
    if os.path.exists(keystore_path):
        with open(keystore_path, 'r') as f:
            data = json.load(f)
            
        print("Bonding Verification:")
        print(f"  File exists: ✓")
        print(f"  Namespaces: {len(data)}")
        
        total_bonds = 0
        for ns, peers in data.items():
            total_bonds += len(peers)
            print(f"    {ns}: {len(peers)} bonded device(s)")
            for addr, keys in peers.items():
                has_ltk = 'ltk_central' in keys or 'ltk_peripheral' in keys or 'ltk' in keys
                has_irk = 'irk' in keys
                print(f"      {addr}: LTK={'✓' if has_ltk else '✗'}, IRK={'✓' if has_irk else '✗'}")
        
        return total_bonds > 0
    else:
        print("✗ No keystore file found")
        return False

verify_bonding()
```

### Method 2: Monitor KEY_STORE_UPDATE Event
```python
async def monitor_bonding(device):
    async def on_key_store_update():
        print("⭐ Bonding keys were just stored!")
        all_bonds = await device.keystore.get_all()
        print(f"   Total bonded devices: {len(all_bonds)}")
    
    device.on("key_store_update", on_key_store_update)
    
    # Now trigger pairing...
    await device.pair(connection)  # This will trigger EVENT_KEY_STORE_UPDATE
```

### Method 3: Load Keys After "Power Off"
```python
async def test_persistence():
    # Create device and pair
    device1 = Device.with_hci(...)
    await device1.power_on()
    device1.keystore = JsonKeyStore.from_device(device1, "bonds.json")
    # ... pair with peer ...
    
    # "Power off" and on (simulate)
    device2 = Device.with_hci(...)
    await device2.power_on()
    device2.keystore = JsonKeyStore.from_device(device2, "bonds.json")
    
    # Check if bonding persisted
    restored_keys = await device2.keystore.get("80:E4:BA:42:E9:AF")
    if restored_keys and restored_keys.ltk:
        print("✓✓✓ BONDING CONFIRMED - Keys persisted!")
        return True
    else:
        print("✗ Bonding failed - keys not restored")
        return False
```

---

## 11. Changes Needed to Enable Real Bonding with Persistence

### Current State (Your Code)
Your current implementation has:
- ✅ Generic SMP pairing working
- ✅ Pairing configuration with `bonding=True`
- ❌ No persistent keystore configured
- ❌ Keys stored only in memory (MemoryKeyStore)

### Required Changes

#### Change 1: Add JsonKeyStore Setup (in main.py or connector.py)
```python
from bumble.keys import JsonKeyStore

class BLETestingMenu:
    def __init__(self, transport_spec):
        # ... existing code ...
        self.keystore_file = "bumble_bonds.json"
    
    async def setup_bonding(self):
        """Enable persistent bonding"""
        # Create device's default keystore
        await self._scan_device.power_on()  # Creates MemoryKeyStore
        
        # Replace with JsonKeyStore
        self._scan_device.keystore = JsonKeyStore.from_device(
            self._scan_device,
            filename=self.keystore_file
        )
        
        print(f"✓ Persistent bonding enabled: {self.keystore_file}")
```

#### Change 2: Call Setup on Connection
```python
async def on_connection(self):
    """After successful connection, setup bonding"""
    await self.setup_bonding()
    print("✓ Bonding configured, keys will be saved")
```

#### Change 3: Verify on Startup
```python
async def on_startup(self):
    """Check for previously bonded devices"""
    await self._scan_device.power_on()
    self._scan_device.keystore = JsonKeyStore.from_device(
        self._scan_device,
        filename=self.keystore_file
    )
    
    bonded = await self._scan_device.keystore.get_all()
    if bonded:
        print(f"\n✓ Found {len(bonded)} previously bonded device(s):")
        for addr, keys in bonded:
            print(f"  - {addr} (LTK: {'✓' if keys.ltk else '✗'})")
```

#### Change 4: Add Unbond Function
```python
async def unpair_device(self, address_str):
    """Remove bonding for a specific device"""
    try:
        await self._scan_device.keystore.delete(address_str)
        print(f"✓ Unbonded: {address_str}")
    except KeyError:
        print(f"✗ Device not bonded: {address_str}")
```

#### Change 5: Update `PairingConfig` in connector.py
Ensure your `setup_pairing_on_device()` has `bonding=True`:
```python
def setup_pairing_on_device(self, device):
    def pairing_config_factory(connection):
        config = PairingConfig(
            sc=True,
            mitm=True,
            bonding=True,  ⭐ Already have this
            delegate=delegate,
            identity_address_type=PairingConfig.AddressType.RANDOM
        )
        return config
    
    device.pairing_config_factory = pairing_config_factory
```

---

## Summary: What to Do Now

### Minimal Implementation (3 Lines)
```python
# After device.power_on():
from bumble.keys import JsonKeyStore
device.keystore = JsonKeyStore.from_device(device, "bonds.json")
print("✓ Bonding enabled with persistent storage")
```

### Full Implementation
1. ✅ Keep your existing `PairingConfig(bonding=True)` 
2. ✅ Add `JsonKeyStore` setup in device initialization
3. ✅ Add event listener for `EVENT_KEY_STORE_UPDATE`
4. ✅ Load bonded devices on startup
5. ✅ Provide unbond function in menu

###Result After Implementation
- ✅ Bonding will be **PERSISTENT** across power cycles
- ✅ Previously bonded devices auto-encrypt without re-pairing
- ✅ Keys visible in `~/.local/share/Bumble/Pairing/<address>.json`
- ✅ Full Bluetooth bonding compliance

---

## References

- Bumble Source: [github.com/google/bumble](https://github.com/google/bumble)
- `bumble/keys.py` - KeyStore implementations
- `bumble/device.py` - Device keystore integration (lines 4100, 4947)
- `bumble/smp.py` - SMP pairing & key generation (lines 1329, 2015)
- `bumble/pairing.py` - PairingConfig class
- Bluetooth SIG Spec: Vol 3, Part H (SMP), Vol 3, Part C (GAP)
