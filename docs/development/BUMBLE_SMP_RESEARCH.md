# Bumble SMP (Security Manager Protocol) Pairing Implementation Research

## Overview
Bumble is a full-featured Python Bluetooth Stack that supports both BLE and Bluetooth Classic. The SMP implementation handles generic pairing without device-specific knowledge, making it highly flexible and reusable.

---

## 1. How Bumble Handles Generic BLE Pairing

### Key Architecture Components

Bumble's SMP pairing system is organized into three main components:

1. **`Device`** - The main entry point that ties together all BLE functionality
2. **`smp.Manager`** - Manages SMP sessions for each connection
3. **`smp.Session`** - Handles individual pairing sessions (initiator or responder)
4. **`PairingDelegate`** - Abstract interface for handling user interactions
5. **`PairingConfig`** - Configuration object for each pairing session

### Generic Pairing Flow

Bumble implements a **stateful, connection-based** pairing model:

```
Connection Established
    ↓
Pairing Request (from initiator or responder)
    ↓
SMP Manager creates Session (or reuses existing)
    ↓
PairingDelegate handles user interactions (accept, passkey, confirm, etc.)
    ↓
Phase 1: Exchange pairing parameters
    ↓
Phase 2: Authentication exchange (depends on pairing method)
    ↓
Phase 3: Key generation and distribution
    ↓
Pairing Complete → Keys stored and connection is encrypted
```

### Generic Approach (Device-Agnostic)

The key to Bumble's generic design is the **`pairing_config_factory`** - a callable that creates `PairingConfig` for each connection:

```python
device.pairing_config_factory = lambda connection: PairingConfig(
    sc=True,           # Secure Connections (LE SC)
    mitm=True,         # Man-in-the-Middle protection
    bonding=True,      # Store keys for future reconnections
    delegate=my_delegate,
    identity_address_type=PairingConfig.AddressType.RANDOM
)
```

This factory is called for **every connection**, making it device-agnostic. The delegate handles all user interactions regardless of peer characteristics.

---

## 2. Supported SMP Methods

Bumble supports **5 pairing methods** defined in `bumble/smp.py`:

```python
class PairingMethod(enum.IntEnum):
    JUST_WORKS = 0              # No MITM, automatic confirmation
    NUMERIC_COMPARISON = 1      # Display 6-digit number, user confirms
    PASSKEY = 2                 # Display or input passkey (6 digits)
    OOB = 3                     # Out-of-Band (pre-shared data)
    CTKD_OVER_CLASSIC = 4       # Cross-Transport Key Derivation
```

### Method Selection Matrix

The pairing method is automatically selected based on:
- **I/O Capabilities** (from delegate)
- **MITM requirement** (auth_req flags)
- **Secure Connections support** (SC vs Legacy)

**Decision Logic** (from `Session.decide_pairing_method()`):

| Initiator I/O | Responder I/O | Method |
|---|---|---|
| DISPLAY_ONLY + DISPLAY_ONLY | → | JUST_WORKS |
| KEYBOARD_ONLY + DISPLAY_KEYBOARD | → | PASSKEY (init: input, resp: display) |
| DISPLAY_KEYBOARD + DISPLAY_KEYBOARD | → | NUMERIC_COMPARISON (SC) or PASSKEY (Legacy) |
| *_WITH_KEYBOARD + *_WITH_YES_NO | → | NUMERIC_COMPARISON (SC) or PASSKEY (Legacy) |
| NO_INPUT_NO_OUTPUT (both) | → | JUST_WORKS |

---

## 3. Generic Pairing Handler Implementation

### Entry Point: Create Custom PairingDelegate

The core of generic pairing is extending `PairingDelegate`:

```python
from bumble.pairing import PairingDelegate, PairingConfig
from bumble.device import Device

class GenericPairingDelegate(PairingDelegate):
    """Generic pairing handler that works with any BLE peripheral"""
    
    def __init__(self, io_capability=None):
        # NO_OUTPUT_NO_INPUT: Auto-accepts Just Works pairing
        # DISPLAY_OUTPUT_ONLY: Shows passkeys
        # DISPLAY_OUTPUT_AND_KEYBOARD_INPUT: Full interactive pairing
        io_cap = io_capability or PairingDelegate.IoCapability.DISPLAY_OUTPUT_ONLY
        
        super().__init__(
            io_capability=io_cap,
            local_initiator_key_distribution=PairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY 
                                             | PairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY,
            local_responder_key_distribution=PairingDelegate.KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY 
                                             | PairingDelegate.KeyDistribution.DISTRIBUTE_IDENTITY_KEY,
        )
    
    async def accept(self) -> bool:
        """Called when a pairing request is received from peer"""
        print("✓ Accepting pairing request...")
        return True
    
    async def confirm(self, auto: bool = False) -> bool:
        """Called for Just Works confirmation"""
        print("✓ Auto-confirming Just Works pairing")
        return True
    
    async def compare_numbers(self, number: int, digits: int) -> bool:
        """Called for Numeric Comparison (Secure Connections only)"""
        print(f"🔐 Numeric Comparison: Display '{number:0{digits}}' on both devices")
        # In real implementation: wait for user confirmation
        return await self._wait_user_confirmation()
    
    async def get_number(self) -> int | None:
        """Called for Passkey Entry (initiator input or responder display)"""
        print("📱 Enter passkey (6 digits): ")
        # In real implementation: get from user input or external source
        passkey_str = input().strip()
        try:
            return int(passkey_str)
        except ValueError:
            return None
    
    async def display_number(self, number: int, digits: int) -> None:
        """Called for Passkey Display"""
        print(f"🔑 Passkey to display: {number:0{digits}}")
    
    async def get_string(self, max_length: int) -> str | None:
        """Called for PIN entry (Classic pairing)"""
        print(f"Enter PIN (up to {max_length} chars): ")
        return input().strip() or None
    
    async def generate_passkey(self) -> int:
        """Override to use fixed passkey instead of random"""
        # Default: random passkey between 0-999999
        return super().generate_passkey()
```

### Setup on Device

```python
from bumble.transport import open_transport

async def setup_generic_pairing(device_config_path, hci_transport_spec):
    """Generic initialization for any BLE peripheral"""
    
    # Connect to HCI
    async with await open_transport(hci_transport_spec) as hci_transport:
        # Create device
        device = Device.from_config_file_with_hci(
            device_config_path,
            hci_transport.source,
            hci_transport.sink
        )
        
        # Set up generic pairing on device
        device.pairing_config_factory = lambda connection: PairingConfig(
            sc=True,                    # Secure Connections
            mitm=True,                  # MITM protection
            bonding=True,               # Store keys
            delegate=GenericPairingDelegate(
                io_capability=PairingDelegate.IoCapability.DISPLAY_OUTPUT_ONLY
            ),
            identity_address_type=PairingConfig.AddressType.RANDOM
        )
        
        # Listen for pairing events
        device.on('pairing', lambda connection, keys: on_pairing_complete(connection, keys))
        device.on('pairing_failure', lambda connection, reason: on_pairing_failure(connection, reason))
        
        await device.power_on()
        # ... rest of device setup
```

---

## 4. Code Examples

### Example 1: SecurityManager Setup

```python
# In Device.__init__():
from bumble.smp import Manager as SMPManager
from bumble import pairing

self.smp_manager = SMPManager(
    self,
    pairing_config_factory=lambda connection: pairing.PairingConfig(
        identity_address_type=(
            pairing.PairingConfig.AddressType(self.config.identity_address_type)
            if self.config.identity_address_type
            else None
        ),
        delegate=pairing.PairingDelegate(
            io_capability=pairing.PairingDelegate.IoCapability(
                self.config.io_capability
            )
        ),
    ),
)
```

### Example 2: Handling Pairing Requests from Devices

```python
from bumble.device import Device, Connection
from bumble.pairing import PairingConfig, PairingDelegate

async def handle_pairing_request(device: Device, peer_address: str):
    """Generic pairing handler for any peer"""
    
    # Get or create connection
    connection = await device.connect(peer_address)
    
    # Initiate pairing
    try:
        await device.pair(connection)
        print(f"✓ Pairing successful with {peer_address}")
    except Exception as e:
        print(f"✗ Pairing failed: {e}")
        await connection.disconnect()

# Alternative: Request pairing without initiating
device.request_pairing(connection)
```

### Example 3: Responding to Passkey Requests

```python
class InteractivePairingDelegate(PairingDelegate):
    """Delegate that prompts for passkey/confirmation interactively"""
    
    async def compare_numbers(self, number: int, digits: int) -> bool:
        """Numeric Comparison - user confirms numbers match"""
        print(f"\n{'='*40}")
        print(f"NUMERIC COMPARISON")
        print(f"Display on both devices: {number:0{digits}}")
        print(f"{'='*40}")
        
        response = input("Do numbers match? (yes/no): ").strip().lower()
        return response in ('yes', 'y')
    
    async def get_number(self) -> int | None:
        """Handle passkey entry"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                passkey = int(input("Enter 6-digit passkey: ").strip())
                if 0 <= passkey <= 999999:
                    return passkey
                print("Passkey must be between 0 and 999999")
            except ValueError:
                print("Invalid input. Enter 6 digits.")
        
        return None  # Reject after max attempts
    
    async def accept(self) -> bool:
        """Accept/reject pairing from peer"""
        response = input("Accept pairing request? (yes/no): ").strip().lower()
        return response in ('yes', 'y')
```

### Example 4: Handling Different Pairing Methods Automatically

```python
class AutoPairingDelegate(PairingDelegate):
    """Automatically handles all pairing methods with sensible defaults"""
    
    def __init__(self, device_name="MyDevice", fixed_passkey=None):
        # Use DISPLAY_OUTPUT_ONLY to enable most pairing methods
        super().__init__(
            io_capability=PairingDelegate.IoCapability.DISPLAY_OUTPUT_AND_YES_NO_INPUT,
        )
        self.device_name = device_name
        self.fixed_passkey = fixed_passkey
    
    async def accept(self) -> bool:
        """Auto-accept all pairing requests"""
        print(f"{self.device_name}: Accepting pairing...")
        return True
    
    async def confirm(self, auto: bool = False) -> bool:
        """Auto-confirm Just Works (least secure, but generic)"""
        print(f"{self.device_name}: Confirming Just Works pairing")
        return True
    
    async def compare_numbers(self, number: int, digits: int) -> bool:
        """Auto-confirm numeric comparison (demonstrates security)"""
        print(f"{self.device_name}: Numeric code: {number:0{digits}}")
        # For testing: automatically confirm
        # In production: wait for user
        return True
    
    async def get_number(self) -> int | None:
        """Return fixed passkey if configured, else generate"""
        if self.fixed_passkey is not None:
            print(f"{self.device_name}: Using fixed passkey: {self.fixed_passkey:06}")
            return self.fixed_passkey
        # Otherwise use default random generation
        passkey = await super().generate_passkey()
        print(f"{self.device_name}: Generated passkey: {passkey:06}")
        return passkey
    
    async def display_number(self, number: int, digits: int) -> None:
        """Display passkey"""
        print(f"{self.device_name}: 🔑 Passkey: {number:0{digits}}")
    
    async def generate_passkey(self) -> int:
        """Generate random or return fixed passkey"""
        if self.fixed_passkey is not None:
            return self.fixed_passkey
        return await super().generate_passkey()
```

### Example 5: Generic GATT Server with Pairing

```python
from bumble.device import Device
from bumble.gatt import Characteristic, Service
from bumble.pairing import PairingConfig, PairingDelegate

async def create_gatt_server_with_pairing(hci_transport_spec, device_config):
    """Create a generic GATT server that accepts pairing"""
    
    async with await open_transport(hci_transport_spec) as hci_transport:
        device = Device.from_config_file_with_hci(
            device_config,
            hci_transport.source,
            hci_transport.sink
        )
        
        # Add a simple GATT service
        heart_rate_service = Service(
            '180d',  # Heart Rate Service UUID
            [
                Characteristic(
                    '2a37',  # Heart Rate Measurement
                    Characteristic.Properties.NOTIFY,
                    Characteristic.READABLE
                )
            ],
        )
        device.add_services([heart_rate_service])
        
        # Configure generic pairing
        device.pairing_config_factory = lambda connection: PairingConfig(
            sc=True,
            mitm=True,
            bonding=True,
            delegate=AutoPairingDelegate("HeartRate_Device"),
        )
        
        # Listen for pairing events
        def on_pairing(connection, keys):
            print(f"✓ Paired with {connection.peer_address}")
            print(f"  LTK: {keys.ltk.value.hex() if keys.ltk else 'N/A'}")
        
        def on_pairing_failure(connection, reason):
            print(f"✗ Pairing failed: {reason}")
        
        device.on('pairing', on_pairing)
        device.on('pairing_failure', on_pairing_failure)
        
        await device.power_on()
        await device.start_advertising(auto_restart=True)
        
        # Keep running
        await hci_transport.source.terminated
```

---

## 5. Key Classes and Methods

### smp.Manager
**File**: `bumble/smp.py`

`Manager` handles SMP for all connections on a device.

```python
class Manager(EventEmitter):
    def __init__(
        self,
        device: Device,
        pairing_config_factory: Callable[[Connection], PairingConfig],
    )
    
    async def pair(self, connection: Connection) -> None
        """Initiate pairing as central (initiator)"""
    
    def request_pairing(self, connection: Connection) -> None
        """Request pairing from peripheral (via Security Request)"""
    
    def on_smp_pdu(self, connection: Connection, pdu: bytes) -> None
        """Handle incoming SMP commands"""
    
    @property
    def ecc_key(self) -> crypto.EccKey
        """Get or generate elliptic curve key for SC (async generation)"""
```

### smp.Session
**File**: `bumble/smp.py` (lines 575-1918)

`Session` manages individual pairing sessions (one per connection).

```python
class Session:
    def __init__(
        self,
        manager: Manager,
        connection: Connection,
        pairing_config: PairingConfig,
        is_initiator: bool,
    )
    
    async def pair(self) -> None
        """Main pairing coroutine (initiator only)"""
    
    def decide_pairing_method(
        self,
        auth_req: int,
        initiator_io_capability: int,
        responder_io_capability: int,
    ) -> None
        """Select pairing method based on I/O capabilities"""
    
    # Phase handlers
    def send_pairing_request_command(self) -> None
    def send_pairing_response_command(self) -> None
    
    # User interaction methods
    async def display_passkey(self) -> None
    def prompt_user_for_number(self, next_steps: Callable) -> None
    def prompt_user_for_confirmation(self, next_steps: Callable) -> None
    def prompt_user_for_numeric_comparison(self, code: int, next_steps: Callable) -> None
    
    # SMP command handlers
    def on_smp_pairing_request_command(command: SMP_Pairing_Request_Command) -> None
    def on_smp_pairing_response_command(command: SMP_Pairing_Response_Command) -> None
    def on_smp_pairing_confirm_command(command: SMP_Pairing_Confirm_Command) -> None
    def on_smp_pairing_random_command(command: SMP_Pairing_Random_Command) -> None
    def on_smp_pairing_public_key_command(command: SMP_Pairing_Public_Key_Command) -> None
    def on_smp_pairing_dhkey_check_command(command: SMP_Pairing_DHKey_Check_Command) -> None
```

### PairingDelegate (Abstract Base)
**File**: `bumble/pairing.py` (lines 94-226)

Abstract interface for handling user interactions during pairing.

```python
class PairingDelegate:
    class IoCapability(enum.IntEnum):
        NO_OUTPUT_NO_INPUT = 3
        KEYBOARD_INPUT_ONLY = 2
        DISPLAY_OUTPUT_ONLY = 1
        DISPLAY_OUTPUT_AND_YES_NO_INPUT = 4
        DISPLAY_OUTPUT_AND_KEYBOARD_INPUT = 0
    
    class KeyDistribution(enum.IntFlag):
        DISTRIBUTE_ENCRYPTION_KEY = 1
        DISTRIBUTE_IDENTITY_KEY = 2
        DISTRIBUTE_SIGNING_KEY = 4
        DISTRIBUTE_LINK_KEY = 8
    
    io_capability: IoCapability
    local_initiator_key_distribution: KeyDistribution
    local_responder_key_distribution: KeyDistribution
    maximum_encryption_key_size: int  # Default: 16
    
    # Methods to override
    async def accept(self) -> bool
        """Accept/reject pairing request"""
    
    async def confirm(self, auto: bool = False) -> bool
        """Confirm Just Works pairing"""
    
    async def compare_numbers(self, number: int, digits: int) -> bool
        """Confirm Numeric Comparison code"""
    
    async def get_number(self) -> int | None
        """Get passkey (0-999999)"""
    
    async def display_number(self, number: int, digits: int) -> None
        """Display passkey"""
    
    async def get_string(self, max_length: int) -> str | None
        """Get PIN string (Classic pairing)"""
    
    async def generate_passkey(self) -> int
        """Generate passkey (override to return fixed value)"""
    
    async def key_distribution_response(
        self, 
        peer_initiator_key_distribution: int,
        peer_responder_key_distribution: int
    ) -> tuple[int, int]
        """Return negotiated key distribution flags"""
```

### PairingConfig
**File**: `bumble/pairing.py` (lines 232-268)

Configuration for pairing on a per-connection basis.

```python
class PairingConfig:
    class AddressType(enum.IntEnum):
        PUBLIC = 0
        RANDOM = 1
    
    @dataclass
    class OobConfig:
        """Out-of-Band configuration"""
        our_context: OobContext | None
        peer_data: OobSharedData | None
        legacy_context: OobLegacyContext | None
    
    def __init__(
        self,
        sc: bool = True,                      # Secure Connections
        mitm: bool = True,                    # MITM protection
        bonding: bool = True,                 # Store keys
        delegate: PairingDelegate | None = None,
        identity_address_type: AddressType | None = None,
        oob: OobConfig | None = None,
    )
```

### Device
**File**: `bumble/device.py` (lines 2547-2570, 4795-4818)

Main entry point for BLE functionality, includes SMP integration.

```python
class Device(CompositeEventEmitter):
    smp_manager: smp.Manager
    
    @property
    def pairing_config_factory(self) -> Callable[[Connection], PairingConfig]
        """Get factory for creating PairingConfig per connection"""
    
    @pairing_config_factory.setter
    def pairing_config_factory(
        self, 
        pairing_config_factory: Callable[[Connection], PairingConfig]
    ) -> None
        """Set factory for creating PairingConfig per connection"""
    
    async def pair(self, connection: Connection)
        """Initiate pairing as central"""
    
    def request_pairing(self, connection: Connection)
        """Request pairing from peripheral"""
    
    # SMP events
    def on_pairing_start(self, connection: Connection) -> None
    def on_pairing(
        self, 
        connection: Connection,
        identity_address: Address | None,
        keys: PairingKeys,
        sc: bool
    ) -> None
    def on_pairing_failure(self, connection: Connection, reason: int) -> None
```

---

## 6. SMP Command Classes

All SMP commands inherit from `SMP_Command` and are defined in `bumble/smp.py` (lines 173-510).

Key commands:

```python
# Phase 1: Pairing parameters exchange
SMP_Pairing_Request_Command()
SMP_Pairing_Response_Command()

# Phase 2: Authentication (varies by method)
SMP_Pairing_Confirm_Command()        # LE Legacy only
SMP_Pairing_Random_Command()         # LE Legacy only
SMP_Pairing_Public_Key_Command()     # Secure Connections
SMP_Pairing_DHKey_Check_Command()    # Secure Connections

# Key distribution
SMP_Encryption_Information_Command()
SMP_Master_Identification_Command()
SMP_Identity_Information_Command()
SMP_Identity_Address_Information_Command()
SMP_Signing_Information_Command()

# Security & Control
SMP_Security_Request_Command()
SMP_Pairing_Failed_Command()
```

---

## 7. Error Codes

SMP defines error codes in `bumble/smp.py` (lines 103-171):

```python
SMP_PASSKEY_ENTRY_FAILED_ERROR = 0x01
SMP_CONFIRM_VALUE_FAILED_ERROR = 0x02
SMP_PAIRING_NOT_SUPPORTED_ERROR = 0x05
SMP_OOB_NOT_AVAILABLE_ERROR = 0x0F
SMP_CONFIRM_VALUE_FAILED_ERROR = 0x02
SMP_INVALID_PARAMETERS_ERROR = 0x03
SMP_UNSPECIFIED_REASON_ERROR = 0x08
```

---

## 8. Key Distribution

By default, Bumble distributes:

```python
DEFAULT_KEY_DISTRIBUTION = (
    KeyDistribution.DISTRIBUTE_ENCRYPTION_KEY   # LTK
    | KeyDistribution.DISTRIBUTE_IDENTITY_KEY   # IRK + IA
)
```

This provides:
- **LTK** (Long Term Key) - for connection encryption
- **IRK** (Identity Resolving Key) - for address resolution
- **IA** (Identity Address) - the identity address for future connections

Optional:
- **SIGNING_KEY** - for GATT signed writes
- **LINK_KEY** - for BR/EDR cross-transport derivation

---

### 9. Complete Generic Pairing Example

```python
"""Generic BLE Pairing Handler - Works with ANY peripheral"""

import asyncio
from bumble.device import Device
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.transport import open_transport

class GenericBLEPairingDelegate(PairingDelegate):
    """Handles all pairing methods generically"""
    
    def __init__(self, device_name="BLEDevice", interactive=False):
        super().__init__(
            io_capability=PairingDelegate.IoCapability.DISPLAY_OUTPUT_AND_YES_NO_INPUT
        )
        self.device_name = device_name
        self.interactive = interactive
    
    async def accept(self) -> bool:
        print(f"[{self.device_name}] Pairing request accepted")
        return True
    
    async def confirm(self, auto: bool = False) -> bool:
        print(f"[{self.device_name}] Just Works confirmed")
        return True
    
    async def compare_numbers(self, number: int, digits: int) -> bool:
        print(f"[{self.device_name}] Numeric comparison: {number:0{digits}}")
        if self.interactive:
            response = input("Match? (y/n): ").strip().lower()
            return response == 'y'
        return True  # Auto-confirm for testing
    
    async def get_number(self) -> int | None:
        if self.interactive:
            user_input = input("Enter passkey: ").strip()
            try:
                return int(user_input)
            except ValueError:
                return None
        return 123456  # Default for testing
    
    async def display_number(self, number: int, digits: int) -> None:
        print(f"[{self.device_name}] Display passkey: {number:0{digits}}")

async def main():
    # Connect to HCI device
    transport_spec = "usb:0"  # or "uart:/dev/ttyUSB0" etc.
    hci_transport = await open_transport(transport_spec)
    
    async with hci_transport:
        # Create device
        device = Device(
            name="TestDevice",
            address="00:11:22:33:44:55"
        )
        
        # Set up generic pairing
        device.pairing_config_factory = lambda conn: PairingConfig(
            sc=True,
            mitm=True,
            bonding=True,
            delegate=GenericBLEPairingDelegate("TestDevice", interactive=False),
        )
        
        # Track pairing
        device.on('pairing', lambda conn, keys: 
            print(f"✓ Paired: {conn.peer_address}"))
        device.on('pairing_failure', lambda conn, reason: 
            print(f"✗ Failed: {reason}"))
        
        await device.power_on()
        print("Ready for pairing...")
        
        # Pair with a peer (as central/initiator)
        # or wait for peripheral to initiate
        await asyncio.sleep(3600)  # Run for 1 hour

if __name__ == '__main__':
    asyncio.run(main())
```

---

## Summary

**Key Takeaways for Generic Pairing:**

1. **One Pattern, All Devices**: Use the same `pairing_config_factory` and `PairingDelegate` for any peripheral
2. **Automatic Method Selection**: Bumble chooses pairing method based on I/O capabilities
3. **Extensible Architecture**: Override only what you need in `PairingDelegate`
4. **No Device Knowledge Required**: Works generically without device-specific implementations
5. **Secure by Default**: SC enabled, MITM protection, and key bonding all configurable
6. **Manual or Automatic**: Support both interactive prompts and automatic confirmation

The design allows building tools that pair with ANY BLE device while maintaining security and flexibility.
