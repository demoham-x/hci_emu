# Bumble BLE Testing Framework

> A comprehensive BLE (Bluetooth Low Energy) testing toolkit built on the Bumble Bluetooth stack

**Features:**
- 🔍 Interactive menu-driven interface
- 📡 BLE scanning and device discovery
- 🔗 GATT operations (read/write/notify)
- 🔐 Pairing and persistent bonding
- 📊 Live HCI packet capture (Ellisys + BTSnoop)
- 🐍 Python API for automation

---

## 🚀 Quick Start

### Windows

**1. Run Setup (first time only)**
```powershell
setup.bat
```

**2. Start HCI Bridge (Terminal 1 - as Administrator)**
```powershell
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
```

**3. Run Application (Terminal 2)**
```powershell
run.bat
```

### Linux/macOS

See [SETUP.md](SETUP.md) for detailed platform-specific instructions.

---

## 📖 Documentation

**For Users:**
- **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)** - Complete usage guide, troubleshooting, FAQ

**For Developers:**
- **[docs/TECHNICAL_REFERENCE.md](docs/TECHNICAL_REFERENCE.md)** - Architecture, APIs, protocols

**Setup & Contributing:**
- **[SETUP.md](SETUP.md)** - Platform-specific installation
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute

---

## 📁 Project Structure

```
bumble_hci/
├── 📋 README.md              ← You are here
├── 📋 requirements.txt       ← Python dependencies
├── 📋 setup.py               ← Package configuration
├── 🔧 setup.bat              ← First-time setup (Windows)
├── 🔧 run.bat                ← Run application (Windows)
│
├── 📂 src/                   ← Application source code
│   ├── main.py               ← Main interactive menu
│   ├── connector.py          ← BLE operations
│   ├── scanner.py            ← Device scanning
│   ├── hci_snooper.py        ← HCI packet capture
│   └── utils.py              ← Utilities
│
├── 📂 docs/                  ← Documentation
│   ├── USER_MANUAL.md        ← User guide (START HERE!)
│   ├── TECHNICAL_REFERENCE.md ← Developer guide
│   └── development/          ← Historical dev docs
│
├── 📂 examples/              ← Code examples
│   ├── basic_connection.py
│   ├── scan_devices.py
│   └── hci_capture.py
│
├── 📂 tests/                 ← Test suite
├── 📂 scripts/               ← Utility scripts
├── 📂 configs/               ← Configuration files
│   └── bumble_bonds.json     ← Persistent bonds
├── 📂 logs/                  ← HCI captures & logs
└── 📂 resources/             ← UUID lookups, configs
```

---

---

## 🎯 Key Features

### BLE Operations
- **Scan** - Discover nearby BLE devices with RSSI
- **Connect** - Establish connections to BLE peripherals
- **GATT** - Browse services, read/write characteristics
- **Notify** - Subscribe to characteristic notifications

### Security & Bonding
- **Pairing** - Support for multiple pairing methods
- **Bonding** - Persistent bond storage (survives restart)
- **Encryption** - Manual encryption control

### HCI Packet Capture
- **Live Capture** - Real-time HCI packet streaming
- **Ellisys Integration** - UDP injection for Ellisys Bluetooth Analyzer
- **BTSnoop Format** - Standard .log/.btsnoop file output
- **Protocol Analysis** - Decode and analyze BLE protocol

### Developer Tools
- **Python API** - Programmatic access to all features
- **Examples** - Ready-to-use code samples
- **Rich UI** - Colorful terminal interface with tables

---

## 💡 Usage Examples

### Interactive Menu
```bash
python src/main.py
```

```
═══════════════════════════════════════════════════════
  BUMBLE BLE Testing - Main Menu
═══════════════════════════════════════════════════════

  [1] Scan for BLE Devices
  [2] Connect to Device
  [3] Browse GATT Services
  [4] Read Characteristic
  [5] Write Characteristic
  [6] Subscribe to Notifications
  [7] Pair with Device
  [D] Toggle HCI Capture
  [Q] Quit
```

### Programmatic Usage

See [examples/](examples/) for complete code samples:

```python
from connector import BLEConnector

# Scan for devices
connector = BLEConnector("tcp-client:127.0.0.1:9001")
devices = await connector.scan(duration=10)

# Connect and read
await connector.connect("AA:BB:CC:DD:EE:FF")
value = await connector.read_characteristic(0x0012)
```

---

## 🛠️ Requirements

- **Python 3.8+**
- **Bluetooth USB adapter** (or built-in Bluetooth)
- **USB driver**: WinUSB (Windows - via Zadig)
- **Bumble** - Installed via `pip install bumble`

See [SETUP.md](SETUP.md) for complete requirements and installation.

---

## 📦 Installation

### Quick Install (Windows)

```powershell
# Clone repository
git clone <repository-url>
cd bumble_hci

# Run setup
setup.bat
```

### Manual Install (Any Platform)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt
```

Full instructions: [SETUP.md](SETUP.md)

---

## 🔧 Configuration

### HCI Transport

Default: `tcp-client:127.0.0.1:9001`

Requires `bumble-hci-bridge` running:
```bash
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
```

### Bond Storage

Bonds saved to: `configs/bumble_bonds.json`

### HCI Capture

Files saved to: `logs/hci_capture.log` (BTSnoop format)  
Ellisys: UDP port 24352

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python tests/test_connection.py
python tests/test_ellisys_udp.py

# Check bonding status
python scripts/check_bonding.py
```

---

## 📚 Learn More

**Documentation:**
- [User Manual](docs/USER_MANUAL.md) - How to use the framework
- [Technical Reference](docs/TECHNICAL_REFERENCE.md) - How it works

**Guides:**
- [Setup Guide](SETUP.md) - Installation for Windows/Linux/macOS
- [Contributing](CONTRIBUTING.md) - How to contribute

**Examples:**
- [examples/scan_devices.py](examples/scan_devices.py) - Scan for BLE devices
- [examples/basic_connection.py](examples/basic_connection.py) - Connect and read
- [examples/hci_capture.py](examples/hci_capture.py) - Capture HCI packets

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

Built with [Bumble](https://google.github.io/bumble/) - A Python Bluetooth stack by Google

---

**Questions?** Check the [FAQ](docs/USER_MANUAL.md#faq) or open an issue.

