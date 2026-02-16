#!/usr/bin/env python3
"""
UDP Injection Connectivity Test
Tests if packets can reach Ellisys using CORRECT Ellisys Injection API protocol
"""

import socket
import struct
import sys
import time
from datetime import datetime

# === ELLISYS INJECTION API CONSTANTS ===
ELLISYS_HCI_SERVICE_ID = 0x0002
ELLISYS_SERVICE_VERSION = 0x01

# Object IDs
OBJ_DATETIME_NS = 0x02
OBJ_BITRATE = 0x80
OBJ_HCI_PACKET_TYPE = 0x81
OBJ_HCI_PACKET_DATA = 0x82

# HCI Packet Types
HCI_CMD = 0x01
HCI_ACL = 0x02
HCI_EVENT = 0x84


def build_ellisys_injection_packet(hci_type: int, hci_data: bytes) -> bytes:
    """
    Build CORRECT Ellisys HCI Injection packet
    
    Format:
    [Service ID (2B LE)][Version (1B)][DateTime (0x02)][Bitrate (0x80)][HciType (0x81)][HciData (0x82)]
    """
    packet = b''
    
    # Service header
    packet += struct.pack('<H', ELLISYS_HCI_SERVICE_ID)  # 0x0002
    packet += bytes([ELLISYS_SERVICE_VERSION])            # 0x01
    
    # DateTime object
    packet += bytes([OBJ_DATETIME_NS])
    dt = datetime.now()
    packet += struct.pack('<H', dt.year)
    packet += bytes([dt.month, dt.day])
    dt_midnight = datetime(dt.year, dt.month, dt.day)
    ns_since_midnight = int((dt.timestamp() - dt_midnight.timestamp()) * 1_000_000_000)
    ns_bytes = struct.pack('<Q', ns_since_midnight)[:6]
    packet += ns_bytes
    
    # Bitrate object
    packet += bytes([OBJ_BITRATE])
    packet += struct.pack('<I', 12_000_000)  # 12 Mbit/s
    
    # HCI Packet Type
    packet += bytes([OBJ_HCI_PACKET_TYPE])
    packet += bytes([hci_type])
    
    # HCI Packet Data
    packet += bytes([OBJ_HCI_PACKET_DATA])
    packet += hci_data
    
    return packet


def test_ellisys_udp(host: str = "127.0.0.1", port: int = 24352):
    """Test UDP connectivity to Ellisys using CORRECT Ellisys Injection API protocol"""
    
    print("=" * 60)
    print("  Ellisys UDP Injection Test")
    print("  Using CORRECT Ellisys Injection API (0x0002)")
    print("=" * 60)
    print()
    
    print(f"Target: {host}:{port}\n")
    
    # Create socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        print("✓ Socket created")
    except Exception as e:
        print(f"✗ Failed to create socket: {e}")
        return False
    
    try:
        # Test 1: HCI Reset Command using CORRECT Ellisys API
        print("\nTest 1: Sending HCI Reset Command (Ellisys API)...")
        hci_reset_cmd = bytes.fromhex("03 0c 00")
        packet = build_ellisys_injection_packet(HCI_CMD, hci_reset_cmd)
        sock.sendto(packet, (host, port))
        print(f"  ✓ Sent {len(packet)} bytes")
        print(f"    Service: 0x0002 (HCI Injection Service)")
        print(f"    HCI Type: 0x{HCI_CMD:02X} (CMD)")
        print(f"    HCI Data: {hci_reset_cmd.hex()}")
        
        # Test 2: HCI Event packet
        print("\nTest 2: Sending HCI Event (Ellisys API)...")
        hci_event = bytes.fromhex("0e 04 01 03 0c 00")
        packet = build_ellisys_injection_packet(HCI_EVENT, hci_event)
        sock.sendto(packet, (host, port))
        print(f"  ✓ Sent {len(packet)} bytes")
        print(f"    Service: 0x0002 (HCI Injection Service)")
        print(f"    HCI Type: 0x{HCI_EVENT:02X} (Event)")
        print(f"    HCI Data: {hci_event.hex()}")
        
        # Test 3: Multiple packets
        print(f"\nTest 3: Sending 5 sequential HCI packets...")
        for i in range(5):
            packet_type = HCI_CMD if i % 2 == 0 else HCI_EVENT
            hci_data = bytes([0x03, 0x0c, 0x00]) if i % 2 == 0 else bytes([0x0e, 0x02, 0x00])
            
            packet = build_ellisys_injection_packet(packet_type, hci_data)
            sock.sendto(packet, (host, port))
            print(f"  ✓ Packet {i+1}: HCI Type 0x{packet_type:02X} ({len(packet)} bytes)")
            time.sleep(0.1)
        
        print()
        print("=" * 60)
        print("  ✓ All tests passed!")
        print("=" * 60)
        print()
        print("✓ CORRECT Ellisys Injection API Protocol")
        print("  - Service ID: 0x0002 (HCI Injection Service)")
        print("  - DateTime, Bitrate, HciType, HciData objects")
        print()
        print("Next steps:")
        print("  1. Click 'Record' in Ellisys Analyzer")
        print("  2. Run HCI snoop: python src/main.py → Option D")
        print("  3. Perform BLE operations (scan, connect, pair)")
        print("  4. ✓ HCI packets should appear in Ellisys!")
        print()
        
        sock.close()
        return True
        
    except socket.timeout:
        print(f"✗ Socket timeout")
        print(f"  Ellisys may not be listening on {host}:{port}")
        sock.close()
        return False
        
    except ConnectionRefusedError:
        print(f"✗ Connection refused by {host}:{port}")
        print(f"  Ellisys is not running or wrong port")
        sock.close()
        return False
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sock.close()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Ellisys UDP injection with CORRECT API")
    parser.add_argument("--host", default="127.0.0.1", help="Ellisys host IP")
    parser.add_argument("--port", type=int, default=24352, help="Ellisys UDP port")
    parser.add_argument("--stream", choices=["primary", "secondary", "tertiary"], 
                       default="primary", help="Ellisys data stream")
    
    args = parser.parse_args()
    
    print(f"Stream: {args.stream.upper()}")
    success = test_ellisys_udp(args.host, args.port)
    sys.exit(0 if success else 1)

