# Setup Guide

## Windows Setup

### 1. Install Python
Download and install Python 3.8+ from [python.org](https://www.python.org/downloads/)

### 2. Setup Project
```powershell
# Navigate to project directory
cd bumble_hci

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get execution policy error:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt
```

### 3. USB Bluetooth Adapter
- Plug in USB Bluetooth adapter
- Verify it's detected in Device Manager

### 4. Run Application

**Terminal 1 - HCI Bridge:**
```powershell
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
```

**Terminal 2 - Main App:**
```powershell
python src\main.py
```

## Linux Setup

### 1. Install Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv libusb-1.0-0-dev

# Fedora
sudo dnf install python3 python3-pip libusb-devel

# Arch
sudo pacman -S python python-pip libusb
```

### 2. Setup Project
```bash
cd bumble_hci
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. USB Permissions
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Or create udev rule for your adapter
sudo nano /etc/udev/rules.d/99-bluetooth.rules

# Add (replace XXXX:YYYY with your vendor:product ID):
SUBSYSTEM=="usb", ATTRS{idVendor}=="XXXX", ATTRS{idProduct}=="YYYY", MODE="0666"

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logout and login for group changes
```

### 4. Run Application
```bash
# Terminal 1
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001

# Terminal 2
python src/main.py
```

## macOS Setup

### 1. Install Homebrew (if not installed)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Dependencies
```bash
brew install python@3.11 libusb
```

### 3. Setup Project
```bash
cd bumble_hci
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Run Application
```bash
# Terminal 1
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001

# Terminal 2
python src/main.py
```

## Ellisys Setup (Optional - for HCI Capture)

### 1. Install Ellisys Bluetooth Analyzer
Download from [Ellisys website](https://www.ellisys.com/products/bta/download.php)

### 2. Configure UDP Listener
- Open Ellisys Analyzer
- Go to: **Tools → Options → UDP Listener**
- Enable UDP Listener
- Set port to **24352** (or your chosen port)
- Select data stream (Primary/Secondary/Tertiary)

### 3. Enable in Application
- Run the BLE testing app
- Choose **Option D: HCI Snoop Logging**
- Configure Ellisys host/port
- Enable capture

### 4. Verify Capture
- Perform BLE operations
- Check Ellisys Analyzer for incoming packets
- Check capture file (e.g., `hci_capture.log`)

## Troubleshooting

### "USB device not found"
- Check adapter is plugged in
- Try different USB port
- Check permissions (Linux)
- Try `bumble-hci-bridge usb:1` or `usb:2` for different adapters

### "Module not found" errors
```bash
# Ensure virtual environment is activated
# Windows
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### "Cannot connect to tcp-server"
- Ensure HCI bridge is running in separate terminal
- Check port 9001 is not in use
- Try different port in both bridge and app

### Rich formatting not working
```bash
# Install/reinstall Rich
pip install --upgrade rich
```

### Permission denied (Linux)
```bash
# Check USB permissions
lsusb
ls -la /dev/bus/usb/001/*  # Adjust based on lsusb output

# Run with sudo temporarily to test
sudo -E python src/main.py  # -E preserves environment
```

## Verification

Test your setup:

```bash
# Check Bumble installation
bumble-hci-bridge --help

# List available USB adapters
python -c "import usb.core; print([f'USB {d.idVendor:04x}:{d.idProduct:04x}' for d in usb.core.find(find_all=True)])"

# Check Python version
python --version  # Should be 3.8+

# Test Rich library
python -c "from rich.console import Console; Console().print('[green]✓ Rich working[/green]')"
```

All checks passing? You're ready to go! 🎉

Run the application:
```bash
# Terminal 1
bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001

# Terminal 2
python src/main.py
```
