#!/usr/bin/env python3
"""
Test script for BLE connection with reused device
"""

import asyncio
import logging
from src.main import BLETestingMenu

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test connection to a device from scan"""
    menu = BLETestingMenu()
    
    try:
        # Power on Bluetooth
        print("1. Powering on Bluetooth...")
        await menu.menu_bluetooth_on()
        
        # Scan for devices
        print("\n2. Scanning for devices...")
        await menu._do_scan(duration=15, filter_duplicates=True, active_scan=True)
        
        if not menu.discovered_devices:
            print("No devices discovered!")
            return
        
        # Get first device or RoadSync
        target_device = None
        for addr, info in menu.discovered_devices.items():
            name = info.get('name', '')
            if 'RoadSync' in name or 'Honda' in name:
                target_device = addr
                print(f"\n3. Found target device: {addr} ({name})")
                break
        
        if not target_device:
            # Just use first device
            target_device = list(menu.discovered_devices.keys())[0]
            name = menu.discovered_devices[target_device].get('name', 'Unknown')
            print(f"\n3. Using first device: {target_device} ({name})")
        
        # Try to connect
        print(f"\n4. Connecting to {target_device}...")
        from bumble.hci import Address
        
        device = await menu._get_scan_device()
        
        # Stop scanning
        if getattr(device, "scanning", False):
            print("   Stopping scan first...")
            await device.stop_scanning()
        
        # Connect
        target_address = Address(target_device)
        print("   Initiating connection...")
        connected_device = await device.connect(target_address)
        menu.connector.connected_device = connected_device
        menu.connector.device = device
        menu.connected = True
        menu.current_device = target_device
        
        print(f"✓ Successfully connected to {target_device}!")
        
        # Keep connection alive for a bit
        print("\n5. Connection active for 10 seconds...")
        await asyncio.sleep(10)
        
        # Disconnect
        print("\n6. Disconnecting...")
        await connected_device.disconnect()
        print("✓ Disconnected")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await menu._close_scan_device()
        print("\nTest complete!")

if __name__ == "__main__":
    asyncio.run(test_connection())
