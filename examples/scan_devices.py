# Example: Scanning for BLE Devices
# This script shows how to scan and display discovered devices

import asyncio
from scanner import BLEScanner

async def example_scan():
    # Initialize scanner
    scanner = BLEScanner("tcp-client:127.0.0.1:9001")
    
    try:
        # Scan for 10 seconds
        print("Scanning for BLE devices...")
        devices = await scanner.scan(duration=10)
        
        print(f"\nFound {len(devices)} devices:\n")
        
        for addr, info in devices.items():
            name = info.get('name', 'Unknown')
            rssi = info.get('rssi', 'N/A')
            print(f"  {addr:<20} RSSI: {rssi:>4} dBm  Name: {name}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(example_scan())
