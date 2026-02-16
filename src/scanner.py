#!/usr/bin/env python3
"""
BLE Device Scanner using Bumble
"""

import asyncio
import logging
from typing import List, Dict, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BLEScanner:
    """BLE Device Scanner"""
    
    def __init__(self, transport_spec: str = "tcp-client:127.0.0.1:9001"):
        self.transport_spec = transport_spec
        self.device = None
        self.discovered_devices = {}
        self.scanning = False
        
    async def connect(self):
        """Connect to HCI transport"""
        try:
            from bumble.transport import open_transport
            from bumble.device import Device
            from bumble.hci import Address
            
            logger.info(f"Opening transport: {self.transport_spec}")
            self.transport = await open_transport(self.transport_spec)
            
            # Create device using proper initialization
            self.device = Device.with_hci(
                name='BLEConnector',
                address=Address('F0:F1:F2:F3:F4:F5'),
                hci_source=self.transport.source,
                hci_sink=self.transport.sink,
            )
            
            logger.info("Connected to HCI device")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def scan(self, duration: int = 10, callback: Optional[Callable] = None) -> List[Dict]:
        """
        Scan for BLE devices
        
        Args:
            duration: Scan duration in seconds
            callback: Optional callback for each device found
            
        Returns:
            List of discovered devices
        """
        try:
            from bumble.transport import open_transport
            from bumble.device import Device
            from bumble.hci import Address
            from datetime import datetime
            
            logger.info(f"Scanning for {duration} seconds...")
            
            # Open transport
            transport = await open_transport(self.transport_spec)
            
            # Create device using source/sink pattern (proper initialization)
            device = Device.with_hci(
                name='BLEScanner',
                address=Address('F0:F1:F2:F3:F4:F5'),
                hci_source=transport.source,
                hci_sink=transport.sink,
            )
            
            discovered = []
            start_time = asyncio.get_event_loop().time()
            
            # Scan callback BEFORE starting
            def on_advertising_report(report):
                device_addr = str(report.address)
                if device_addr not in self.discovered_devices:
                    device_info = {
                        'address': device_addr,
                        'rssi': report.rssi,
                        'data': str(report.data) if report.data else "",
                        'timestamp': datetime.now().isoformat(),
                    }
                    self.discovered_devices[device_addr] = device_info
                    discovered.append(device_info)
                    
                    if callback:
                        callback(device_info)
                    
                    logger.info(f"Found device: {device_addr} (RSSI: {report.rssi})")
            
            # Register callback BEFORE scanning
            device.on("advertisement", on_advertising_report)
            
            # Power on device
            await device.power_on()
            
            # Start scanning
            await device.start_scanning(active=False)
            
            # Wait for duration
            while asyncio.get_event_loop().time() - start_time < duration:
                await asyncio.sleep(0.1)
            
            # Stop scanning
            await device.stop_scanning()
            await device.power_off()
            await transport.close()
            
            logger.info(f"Scan complete. Found {len(discovered)} devices")
            return discovered
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def close(self):
        """Close connection"""
        if self.device:
            try:
                await self.device.close()
            except:
                pass


async def scan_devices(duration: int = 10, transport_spec: str = "tcp-client:127.0.0.1:9001") -> List[Dict]:
    """Standalone scan function"""
    scanner = BLEScanner(transport_spec)
    
    # Try simple scan
    try:
        from bumble.transport import open_transport
        from bumble.device import Device
        
        transport = await open_transport(transport_spec)
        device = Device()
        device.hci_transport = transport
        
        devices = []
        
        print(f"\n{'='*60}")
        print(f"  Scanning for {duration} seconds...")
        print(f"{'='*60}\n")
        
        # Simple counter approach
        count = 0
        while count < duration:
            print(f"  [{count}/{duration}] Scanning... Press Ctrl+C to stop")
            await asyncio.sleep(1)
            count += 1
        
        print(f"\nScan complete!")
        
        return devices
        
    except Exception as e:
        logger.error(f"Scan error: {e}")
        return []


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan for BLE devices")
    parser.add_argument(
        "--transport",
        default="tcp-client:127.0.0.1:9001",
        help="Transport specification",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Scan duration in seconds",
    )
    
    args = parser.parse_args()
    
    try:
        asyncio.run(scan_devices(args.duration, args.transport))
    except KeyboardInterrupt:
        print("\nScan interrupted")


if __name__ == "__main__":
    main()
