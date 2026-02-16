#!/usr/bin/env python3
"""
HCI Snoop Logger with Ellisys Injection Support

Captures HCI packets and sends them to:
- Ellisys Bluetooth Analyzer (using CORRECT Ellisys Injection Protocol)
- BTSnoop file format
- Console/file logging

Ellisys Injection API Format (CORRECTED):
- Service ID: 0x0002 (HCI Injection Service)
- Version: 0x01
- Objects: DateTime (0x02), Bitrate (0x80), HciPacketType (0x81), HciPacketData (0x82)
"""

import asyncio
import socket
import struct
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class HCISnooper:
    """
    HCI packet snooper with Ellisys Injection API and BTSnoop output
    
    Implements CORRECT Ellisys HCI Injection Service (0x0002) protocol
    """
    
    # BTSnoop file header
    BTSNOOP_HEADER = b'btsnoop\x00\x00\x00\x00\x01\x00\x00\x03\xea'
    
    # === ELLISYS INJECTION API CONSTANTS ===
    # Service Object
    ELLISYS_HCI_SERVICE_ID = 0x0002  # HCI Injection Service
    ELLISYS_SERVICE_VERSION = 0x01
    
    # Ellisys Object Type IDs
    OBJ_DATETIME_NS = 0x02      # DateTime object
    OBJ_BITRATE = 0x80          # Bitrate object
    OBJ_HCI_PACKET_TYPE = 0x81  # HCI packet type
    OBJ_HCI_PACKET_DATA = 0x82  # HCI packet data
    OBJ_CONTROLLER_INDEX = 0x83 # Controller index (optional)
    
    # Ellisys HCI Packet Type Mappings (different from BTSnoop!)
    ELLISYS_HCI_CMD = 0x01           # Command (Host -> Controller)
    ELLISYS_HCI_ACL_HOST = 0x02      # ACL from Host (Host -> Controller)
    ELLISYS_HCI_ACL_CTRL = 0x82      # ACL from Controller (Controller -> Host)
    ELLISYS_HCI_SCO_HOST = 0x03      # SCO from Host
    ELLISYS_HCI_SCO_CTRL = 0x83      # SCO from Controller
    ELLISYS_HCI_EVT = 0x84           # Event (Controller -> Host)
    
    def __init__(self, 
                 ellisys_host: str = "127.0.0.1",
                 ellisys_port: int = 24352,
                 btsnoop_file: Optional[str] = None,
                 enable_console: bool = False,
                 stream: str = "primary"):
        """
        Initialize HCI snooper
        
        Args:
            ellisys_host: Ellisys analyzer host
            ellisys_port: Ellisys injection port (24352)
            btsnoop_file: Path to BTSnoop output file
            enable_console: Print packets to console
            stream: "primary", "secondary", or "tertiary" stream name
        """
        self.ellisys_host = ellisys_host
        self.ellisys_port = ellisys_port
        self.btsnoop_file = btsnoop_file
        self.enable_console = enable_console
        self.stream_name = stream.lower()
        
        self.udp_socket = None
        self.file_handle = None
        self.packet_count = 0
        self.running = False
        self.udp_send_count = 0
        self.udp_error_count = 0
        self.last_error = None
        self.last_send_time = 0  # Track last send time for spacing
        
    async def start(self):
        """Start snooping"""
        try:
            # Setup Ellisys UDP injection socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.settimeout(1.0)
            
            print(f"\n[HCI SNOOP] ✓ Initialized")
            print(f"[HCI SNOOP] Target: {self.ellisys_host}:{self.ellisys_port}")
            print(f"[HCI SNOOP] Using Ellisys HCI Injection Service (0x0002)")
            print(f"[HCI SNOOP] Stream: {self.stream_name.upper()}")
            logger.info(f"✓ Ellisys UDP injection configured: {self.ellisys_host}:{self.ellisys_port}")
            
            # Send test packet using CORRECT Ellisys protocol
            test_packet = self._build_ellisys_injection_packet(
                self.ELLISYS_HCI_CMD,
                bytes.fromhex("03 0c 00"),  # HCI Reset command
                time.time()  # Current timestamp
            )
            try:
                self.udp_socket.sendto(test_packet, (self.ellisys_host, self.ellisys_port))
                self.last_send_time = time.time()
                print(f"[HCI SNOOP] ✓ Test packet sent (Ellisys Injection API)")
                print(f"[HCI SNOOP] Expected: HCI packets appear in Ellisys Analyzer\n")
                logger.info("Test packet sent to Ellisys using Injection API")
            except (BlockingIOError, socket.error) as e:
                logger.warning(f"Test packet send failed: {e}")
                print(f"[HCI SNOOP] ⚠ Test packet failed: {e}\n")
            
            # Setup BTSnoop file
            if self.btsnoop_file:
                self.file_handle = open(self.btsnoop_file, 'wb')
                self.file_handle.write(self.BTSNOOP_HEADER)
                logger.info(f"✓ BTSnoop file opened: {self.btsnoop_file}")
                print(f"[BTSNOOP FILE] {self.btsnoop_file}\n")
            
            self.running = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to start snooper: {e}", exc_info=True)
            print(f"[ERROR] Failed to start snooper: {e}")
            return False
    
    def _build_ellisys_injection_packet(self, hci_packet_type: int, hci_data: bytes, capture_timestamp: float) -> bytes:
        """
        Build Ellisys HCI Injection packet using CORRECT API protocol
        
        Format:
        [Service ID (2B LE)][Version (1B)][DateTime Obj][Bitrate Obj][HciType Obj][HciData Obj]
        
        Each object starts with type ID (1 byte) followed by data
        """
        packet = b''
        
        # === SERVICE OBJECT ===
        # Service ID (2 bytes, little-endian)
        packet += struct.pack('<H', self.ELLISYS_HCI_SERVICE_ID)  # 0x0002
        # Service Version (1 byte)
        packet += bytes([self.ELLISYS_SERVICE_VERSION])  # 0x01
        
        # === DATETIME OBJECT (0x02) ===
        packet += bytes([self.OBJ_DATETIME_NS])
        dt = datetime.fromtimestamp(capture_timestamp)
        # Year (2 bytes, little-endian)
        packet += struct.pack('<H', dt.year)
        # Month (1 byte)
        packet += bytes([dt.month])
        # Day (1 byte)
        packet += bytes([dt.day])
        # Nanoseconds since midnight (8 bytes, but we'll send 6 as per Ellisys spec)
        dt_midnight = datetime(dt.year, dt.month, dt.day)
        ns_since_midnight = int((dt.timestamp() - dt_midnight.timestamp()) * 1_000_000_000)
        # Pack as 8 bytes then take first 6
        ns_bytes = struct.pack('<Q', ns_since_midnight)[:6]
        packet += ns_bytes
        
        # === BITRATE OBJECT (0x80) ===
        packet += bytes([self.OBJ_BITRATE])
        # Bitrate in bps (4 bytes, little-endian): 12 Mbps for USB Full Speed
        packet += struct.pack('<I', 12_000_000)
        
        # === HCI PACKET TYPE OBJECT (0x81) ===
        packet += bytes([self.OBJ_HCI_PACKET_TYPE])
        packet += bytes([hci_packet_type])
        
        # === HCI PACKET DATA OBJECT (0x82) ===
        packet += bytes([self.OBJ_HCI_PACKET_DATA])
        packet += hci_data
        
        return packet
    
    async def stop(self):
        """Stop snooping"""
        self.running = False
        
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None
            
        print(f"\n[SNOOP SUMMARY]")
        print(f"  Packets captured: {self.packet_count}")
        print(f"  UDP sent: {self.udp_send_count}")
        if self.udp_error_count > 0:
            print(f"  UDP errors: {self.udp_error_count}")
            if self.last_error:
                print(f"  Last error: {self.last_error}")
        if self.btsnoop_file:
            print(f"  BTSnoop file: {self.btsnoop_file}")
        
        logger.info(f"✓ HCI Snooper stopped ({self.packet_count} packets, {self.udp_send_count} UDP sent, {self.udp_error_count} errors)")
    
    def capture_packet(self, packet_type: int, data: bytes, direction: str = "host_to_controller"):
        """
        Capture an HCI packet and send to Ellisys
        
        Args:
            packet_type: HCI packet type (0x01=CMD, 0x02=ACL, 0x03=SCO, 0x04=EVT)
            data: Packet data (without type byte)
            direction: "host_to_controller" or "controller_to_host"
        """
        if not self.running:
            return
        
        try:
            # Capture timestamp IMMEDIATELY to preserve ordering
            timestamp = time.time()
            self.packet_count += 1
            
            # Send to Ellisys via UDP (using CORRECT Ellisys Injection API)
            if self.udp_socket:
                self._send_ellisys(packet_type, data, direction, timestamp)
            
            # Write to BTSnoop file (uses standard BTSnoop format)
            if self.file_handle:
                self._write_btsnoop(packet_type, data, direction, timestamp)
            
            # Console logging
            if self.enable_console:
                self._log_console(packet_type, data, direction)
                
        except Exception as e:
            logger.error(f"Packet capture error: {e}")
    
    def _send_ellisys(self, packet_type: int, data: bytes, direction: str, timestamp: float):
        """
        Send packet to Ellisys via UDP using CORRECT Ellisys Injection Protocol
        
        Maps Bumble HCI types to Ellisys types
        """
        if not self.udp_socket:
            return
        
        try:
            # Map Bumble HCI type to Ellisys HCI type
            # Bumble direction: packet_type from HCI layer
            # Ellisys direction: use 0x01/0x02/0x84 for CMD/ACL/EVT from host
            #                    use 0x82/0x84 for ACL/EVT from controller
            if packet_type == 0x01:  # Command
                ellisys_type = self.ELLISYS_HCI_CMD
            elif packet_type == 0x02:  # ACL
                if direction == "host_to_controller":
                    ellisys_type = self.ELLISYS_HCI_ACL_HOST
                else:
                    ellisys_type = self.ELLISYS_HCI_ACL_CTRL
            elif packet_type == 0x03:  # SCO
                if direction == "host_to_controller":
                    ellisys_type = self.ELLISYS_HCI_SCO_HOST
                else:
                    ellisys_type = self.ELLISYS_HCI_SCO_CTRL
            elif packet_type == 0x04:  # Event
                ellisys_type = self.ELLISYS_HCI_EVT
            else:
                ellisys_type = packet_type
            
            # Build Ellisys Injection packet with captured timestamp
            packet = self._build_ellisys_injection_packet(ellisys_type, data, timestamp)
            
            # Send via UDP
            bytes_sent = self.udp_socket.sendto(packet, (self.ellisys_host, self.ellisys_port))
            self.last_send_time = time.time()
            self.udp_send_count += 1
            
            if self.udp_send_count == 1:
                print(f"[HCI SNOOP] ✓ First HCI packet sent to Ellisys ({bytes_sent} bytes)")
                logger.info(f"First UDP packet sent successfully ({bytes_sent} bytes)")
            
        except (socket.error, OSError) as e:
            self.udp_error_count += 1
            self.last_error = str(e)
            if self.udp_error_count == 1:
                logger.warning(f"UDP send error: {e}")
        except Exception as e:
            self.udp_error_count += 1
            self.last_error = str(e)
            if self.udp_error_count == 1:
                logger.error(f"Ellisys send error: {e}", exc_info=True)
    
    def _write_btsnoop(self, packet_type: int, data: bytes, direction: str, timestamp: float):
        """Write packet to BTSnoop file (standard BTSnoop format)"""
        if not self.file_handle:
            return
            
        try:
            original_length = len(data) + 1
            included_length = original_length
            
            # Flags: 0=sent, 1=received
            flags = 0 if direction == "host_to_controller" else 1
            
            # Drops
            drops = 0
            
            # Timestamp (microseconds since epoch)
            ts_usec = int(timestamp * 1_000_000)
            ts_high = (ts_usec >> 32) & 0xFFFFFFFF
            ts_low = ts_usec & 0xFFFFFFFF
            
            # Write record header
            record_header = struct.pack(
                '>IIII I I',
                original_length,
                included_length,
                flags,
                drops,
                ts_high,
                ts_low
            )
            
            self.file_handle.write(record_header)
            self.file_handle.write(bytes([packet_type]))
            self.file_handle.write(data)
            self.file_handle.flush()
            
        except Exception as e:
            logger.error(f"BTSnoop write error: {e}")
    
    def _log_console(self, packet_type: int, data: bytes, direction: str):
        """Log packet to console"""
        type_names = {
            0x01: "CMD",
            0x02: "ACL",
            0x03: "SCO",
            0x04: "EVT"
        }
        
        type_name = type_names.get(packet_type, f"0x{packet_type:02X}")
        arrow = ">>>" if direction == "host_to_controller" else "<<<"
        
        # Show first 16 bytes
        preview = data[:16].hex(' ')
        if len(data) > 16:
            preview += "..."
        
        print(f"[HCI] {arrow} {type_name:3s} [{len(data):3d} bytes] {preview}")


class BumbleHCITransportWrapper:
    """
    Wraps Bumble's HCI transport to intercept packets for snooping
    """
    
    def __init__(self, original_source, original_sink, snooper: HCISnooper):
        """
        Wrap transport to capture packets
        
        Args:
            original_source: Original transport source
            original_sink: Original transport sink
            snooper: HCISnooper instance
        """
        self.original_source = original_source
        self.original_sink = original_sink
        self.snooper = snooper
        
        self.sink = self._create_wrapped_sink()
        self.source = self._create_wrapped_source()
    
    def _create_wrapped_sink(self):
        """Create sink wrapper that captures outgoing packets"""
        original_sink = self.original_sink
        snooper = self.snooper
        
        class WrappedSink:
            def on_packet(self, packet: bytes):
                # Capture outgoing packet
                if len(packet) > 0:
                    packet_type = packet[0]
                    data = packet[1:]
                    snooper.capture_packet(packet_type, data, "host_to_controller")
                
                # Forward to original sink
                original_sink.on_packet(packet)
        
        return WrappedSink()
    
    def _create_wrapped_source(self):
        """Create source wrapper that captures incoming packets"""
        original_source = self.original_source
        snooper = self.snooper
        
        class WrappedSource:
            def set_packet_sink(self, sink):
                class InterceptingSink:
                    def on_packet(inner_self, packet: bytes):
                        # Capture incoming packet
                        if len(packet) > 0:
                            packet_type = packet[0]
                            data = packet[1:]
                            snooper.capture_packet(packet_type, data, "controller_to_host")
                        
                        # Forward to actual sink
                        sink.on_packet(packet)
                
                original_source.set_packet_sink(InterceptingSink())
        
        return WrappedSource()


async def test_snooper():
    """Test HCI snooper with CORRECT Ellisys Injection API"""
    print("=" * 60)
    print("HCI SNOOPER TEST - Ellisys Injection API (0x0002)")
    print("=" * 60)
    print()
    
    snooper = HCISnooper(
        ellisys_host="127.0.0.1",
        ellisys_port=24352,
        btsnoop_file="test_hci_capture.btsnoop",
        enable_console=True
    )
    
    await snooper.start()
    
    print("Simulating HCI packets...\n")
    
    # HCI Reset command
    snooper.capture_packet(0x01, bytes.fromhex("03 0c 00"), "host_to_controller")
    await asyncio.sleep(0.1)
    
    # HCI Reset response
    snooper.capture_packet(0x04, bytes.fromhex("0e 04 01 03 0c 00"), "controller_to_host")
    await asyncio.sleep(0.1)
    
    # LE Set Scan Enable
    snooper.capture_packet(0x01, bytes.fromhex("0c 20 02 01 00"), "host_to_controller")
    await asyncio.sleep(0.1)
    
    print(f"\n✓ Captured {snooper.packet_count} test packets\n")
    
    await snooper.stop()
    
    print("\nVerify:")
    print("  ✓ Check Ellisys Analyzer for HCI packets")
    print("  ✓ Check test_hci_capture.btsnoop file")


if __name__ == "__main__":
    asyncio.run(test_snooper())
