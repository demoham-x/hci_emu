#!/bin/bash
# Test bonding persistence workflow

echo "================================"
echo "Testing Bonding Persistence"
echo "================================"
echo ""

# Clean up old bonds file for fresh test
if [ -f "bumble_bonds.json" ]; then
    echo "Backing up existing bonds..."
    mv bumble_bonds.json bumble_bonds.json.bak
fi

echo "Test Steps:"
echo "1. Run: A (Bluetooth On)"
echo "2. Run: 1 (Scan for devices)"
echo "3. Run: 2 (Connect to RoadSync_XXXX)"
echo "4. Enter passkey when prompted"
echo "5. Wait for 'Pairing completed!'"
echo "6. Run: 10 (Disconnect)"
echo "7. Run: 1 (Scan again)"
echo "8. Run: 2 (Connect to same device)"
echo ""
echo "Expected Result on Step 8:"
echo "  ✓ NO passkey prompt"
echo "  ✓ Shows 'Device is already bonded - skipping pairing'"
echo "  ✓ bumble_bonds.json file exists with bonded device"
echo ""
echo "Start the app with:"
echo "  python src/main.py"
