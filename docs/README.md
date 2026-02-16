# Documentation

> All documentation for the Bumble BLE Testing Framework

---

## 📚 Start Here

### For Users (Getting Started)

**[USER_MANUAL.md](USER_MANUAL.md)** - Complete user guide  
Everything you need to install, configure, and use the framework. Includes:
- Quick start guide
- Installation instructions (Windows/Linux/macOS)
- Basic operations (scan, connect, read/write)
- Advanced features (bonding, pairing, notifications)
- HCI packet capture setup
- Troubleshooting and FAQ

**Start here if you want to use the tool.**

---

### For Developers (Technical Details)

**[TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)** - Advanced technical documentation  
Deep dive into implementation details, protocols, and APIs:
- Architecture overview
- Bluetooth protocol stack
- HCI packet format and commands
- Ellisys injection protocol
- Bonding and key storage internals
- GATT operations and handles
- API reference for programmatic usage
- Performance considerations
- Security best practices

**Start here if you want to understand or extend the code.**

---

## 📖 Additional Documentation

The following documents are archived in the [`development/`](development/) folder. They contain historical development notes, research, and implementation details that may be useful for understanding design decisions or troubleshooting specific issues:

### Implementation Guides
- [`development/BONDING_IMPLEMENTATION_GUIDE.md`](development/BONDING_IMPLEMENTATION_GUIDE.md) - Detailed bonding implementation notes
- [`development/PAIRING_IMPLEMENTATION.md`](development/PAIRING_IMPLEMENTATION.md) - Pairing process documentation
- [`development/PERSISTENT_BONDING_GUIDE.md`](development/PERSISTENT_BONDING_GUIDE.md) - Persistent bond storage details
- [`development/PACKET_STRUCTURE_GUIDE.md`](development/PACKET_STRUCTURE_GUIDE.md) - HCI packet structure reference

### Research & Analysis
- [`development/BUMBLE_SMP_RESEARCH.md`](development/BUMBLE_SMP_RESEARCH.md) - Security Manager Protocol research
- [`development/BONDING_KEY_STORAGE_RESEARCH.md`](development/BONDING_KEY_STORAGE_RESEARCH.md) - Key storage investigation
- [`development/HCI_SNOOP_GUIDE.md`](development/HCI_SNOOP_GUIDE.md) - HCI capture technical details

### Quick References
- [`development/QUICK_REF.md`](development/QUICK_REF.md) - Command and operation quick reference
- [`development/QUICKSTART.md`](development/QUICKSTART.md) - Original quick start guide
- [`development/QUICKSTART_SNOOP.md`](development/QUICKSTART_SNOOP.md) - Quick HCI capture guide
- [`development/GUIDE.md`](development/GUIDE.md) - Original comprehensive guide

### Development History
- [`development/IMPLEMENTATION_STATUS.md`](development/IMPLEMENTATION_STATUS.md) - Implementation progress tracking
- [`development/SUCCESS_REPORT.md`](development/SUCCESS_REPORT.md) - Project success summary
- [`development/QUICK_BONDING_FIX.md`](development/QUICK_BONDING_FIX.md) - Bonding issue fix notes
- [`development/ELLISYS_FIX_SUMMARY.md`](development/ELLISYS_FIX_SUMMARY.md) - Ellisys integration fix summary
- [`development/ELLISYS_INJECTION_FIXED.md`](development/ELLISYS_INJECTION_FIXED.md) - Ellisys UDP injection fix details
- [`development/README_ELLISYS_SOLUTION.md`](development/README_ELLISYS_SOLUTION.md) - Ellisys solution overview

> **Note:** Most content from these documents has been consolidated into USER_MANUAL.md and TECHNICAL_REFERENCE.md. These archived files remain available for reference and historical context.

---

## 🗺️ Navigation Guide

**I want to...** | **Go to...**
---|---
Use the tool | [USER_MANUAL.md](USER_MANUAL.md)
Install it | [USER_MANUAL.md#installation](USER_MANUAL.md#installation)
Scan for devices | [USER_MANUAL.md#scanning-for-devices](USER_MANUAL.md#scanning-for-devices)
Connect and read/write | [USER_MANUAL.md#connecting-to-devices](USER_MANUAL.md#connecting-to-devices)
Capture HCI packets | [USER_MANUAL.md#hci-packet-capture](USER_MANUAL.md#hci-packet-capture)
Troubleshoot issues | [USER_MANUAL.md#troubleshooting](USER_MANUAL.md#troubleshooting)
Understand the code | [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md)
Extend functionality | [TECHNICAL_REFERENCE.md#api-reference](TECHNICAL_REFERENCE.md#api-reference)
Learn about pairing | [TECHNICAL_REFERENCE.md#bonding-and-key-storage](TECHNICAL_REFERENCE.md#bonding-and-key-storage)
Understand HCI packets | [TECHNICAL_REFERENCE.md#hci-packet-format](TECHNICAL_REFERENCE.md#hci-packet-format)

---

## 🔄 Quick Links

- **[Project README](../README.md)** - Main project page
- **[Setup Guide](../SETUP.md)** - Platform-specific setup
- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute
- **[Examples](../examples/)** - Code examples

---

**Need help?** Check the [FAQ section](USER_MANUAL.md#faq) or open an issue on GitHub.
