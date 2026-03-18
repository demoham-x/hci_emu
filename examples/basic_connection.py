# Example: Basic BLE Connection
# This script demonstrates connecting to a BLE device

import asyncio
from connector import BLEConnector

async def example_connection():
    # Initialize connector with HCI bridge
    connector = BLEConnector("tcp-client:127.0.0.1:9001")
    
    # Target device address
    device_address = "00:60:37:DB:CC:AE/P"
    
    try:
        # Connect to device
        print(f"Connecting to {device_address}...")
        connection = await connector.connect(device_address)
        print("✓ Connected!")
        
        # Discover services
        print("Discovering services...")
        services = await connector.discover_services()
        print(f"Found {len(services)} services")
        
        # Read a characteristic (example handle)
        handle = 0x0054
        value = await connector.read_characteristic(handle)
        print(f"Read value: {value.hex()}")
        
        # Disconnect
        await connector.disconnect()
        print("✓ Disconnected")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(example_connection())
