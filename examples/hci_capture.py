# Example: HCI Packet Capture
# This script captures HCI packets to file and Ellisys

import asyncio
from hci_snooper import HCISnooper
from connector import BLEConnector

async def example_capture():
    # Initialize HCI snooper
    snooper = HCISnooper(
        ellisys_host="127.0.0.1",
        ellisys_port=24352,
        btsnoop_file="capture.log",
        stream="primary"
    )
    
    # Start capture
    await snooper.start()
    print("✓ HCI capture started")
    print(f"  - Sending to Ellisys (UDP 127.0.0.1:24352)")
    print(f"  - Saving to capture.log")
    
    try:
        # Perform BLE operations (example: connect)
        connector = BLEConnector("tcp-client:127.0.0.1:9001")
        # ... your BLE operations here ...
        
        # Let it run for a bit
        await asyncio.sleep(30)
        
    finally:
        # Stop capture
        await snooper.stop()
        print("\n✓ HCI capture stopped")
        print("  Check capture.log for captured packets")

if __name__ == "__main__":
    asyncio.run(example_capture())
