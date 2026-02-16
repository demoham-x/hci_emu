# Utility Scripts

> Helper scripts for bonding management and testing

---

## Scripts

### check_bonding.py

Check the status of bonded devices.

**Usage:**
```bash
python scripts/check_bonding.py
```

**Output:**
- Lists all bonded devices
- Shows bond keys (LTK, IRK, CSRK)
- Displays bond file location

---

### verify_bonding.py

Verify that bonding persistence works correctly.

**Usage:**
```bash
python scripts/verify_bonding.py
```

**What it does:**
- Checks if `configs/bumble_bonds.json` exists
- Validates bond file structure
- Verifies key formats
- Reports any issues

---

## When to Use

**After pairing a device:**
```bash
python scripts/check_bonding.py
```
Confirm the bond was saved correctly.

**Before sharing bonds:**
```bash
python scripts/verify_bonding.py
```
Ensure bond file integrity.

**Troubleshooting connection issues:**
```bash
python scripts/check_bonding.py
```
Check if device is actually bonded.

---

**For more bonding details, see [docs/TECHNICAL_REFERENCE.md](../docs/TECHNICAL_REFERENCE.md#bonding-and-key-storage)**
