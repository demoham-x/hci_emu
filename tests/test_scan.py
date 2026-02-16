#!/usr/bin/env python3
"""Direct scan test - bypasses menu for testing"""

import asyncio
import sys
import logging

# Add src to path
sys.path.insert(0, 'src')

from scanner import BLEScanner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Run scan test"""
    print("\n" + "="*60)
    print("  BLE SCANNER TEST")
    print("="*60 + "\n")
    
    # Create scanner
    scanner = BLEScanner(transport_spec="tcp-client:127.0.0.1:9001")
    
    # Run scan
    print("Starting 10-second scan...\n")
    devices = await scanner.scan(duration=10)
    
    # Display results
    print("\n" + "="*60)
    print(f"SCAN RESULTS: Found {len(devices)} devices")
    print("="*60 + "\n")
    
    for i, device in enumerate(devices, 1):
        print(f"{i}. Address: {device['address']}")
        print(f"   RSSI: {device['rssi']} dBm")
        print(f"   Data: {device['data'][:50]}..." if len(device['data']) > 50 else f"   Data: {device['data']}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
