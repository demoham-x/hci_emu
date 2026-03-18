#!/usr/bin/env python3
"""
Verify that bonding is working and keys are persisted in the Bumble HCI project.

Usage:
    python verify_bonding.py [--check-only] [--keystore-file FILE]

Options:
    --check-only        Only check existing keystore file, don't test persistence
    --keystore-file FILE  Custom keystore filename (default: configs/bumble_bonds.json)
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Optional

def check_existing_keystore(keystore_file: str = "configs/bumble_bonds.json") -> bool:
    """Check if keystore file exists and contains bonded devices"""
    
    if not os.path.exists(keystore_file):
        print(f"✗ Keystore file not found: {keystore_file}")
        return False
    
    print(f"✓ Found keystore: {keystore_file}\n")
    
    try:
        with open(keystore_file, 'r') as f:
            data = json.load(f)
        
        print("📋 Bonded Devices:")
        total_bonds = 0
        
        for namespace, peers in data.items():
            print(f"\n  Namespace (Local Device): {namespace}")
            for addr, keys in peers.items():
                total_bonds += 1
                
                # Check key types
                has_ltk = 'ltk' in keys or 'ltk_central' in keys or 'ltk_peripheral' in keys
                has_irk = 'irk' in keys
                has_csrk = 'csrk' in keys
                has_link_key = 'link_key' in keys
                
                auth_status = ""
                if has_ltk and 'ltk' in keys and isinstance(keys['ltk'], dict):
                    if keys['ltk'].get('authenticated'):
                        auth_status = " (Authenticated)"
                
                print(f"    📱 {addr}{auth_status}")
                print(f"       └─ LTK:  {'✓' if has_ltk else '✗'} | " +
                      f"IRK:  {'✓' if has_irk else '✗'} | " +
                      f"CSRK: {'✓' if has_csrk else '✗'}")
                
                if has_link_key:
                    print(f"       └─ Link Key: ✓ (Classic Bluetooth)")
                
                # Print key details
                if has_ltk and 'ltk' in keys and isinstance(keys['ltk'], dict):
                    ltk_val = keys['ltk'].get('value', '')
                    ediv = keys['ltk'].get('ediv')
                    rand = keys['ltk'].get('rand', '')
                    
                    if isinstance(ltk_val, str) and len(ltk_val) >= 8:
                        print(f"       └─ LTK Value: {ltk_val[:16]}... (ediv={ediv})")
        
        print(f"\n✅ Total Bonded Devices: {total_bonds}")
        return True
        
    except json.JSONDecodeError as e:
        print(f"✗ Error parsing JSON: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

async def test_keystore_functionality(keystore_file: str = "configs/bumble_bonds.json") -> bool:
    """
    Test that bonding keys can be stored and retrieved.
    This is a functional test that doesn't require actual BLE hardware.
    """
    
    print_header("Testing Bonding Functionality")
    
    try:
        from bumble.keys import JsonKeyStore, PairingKeys
        from bumble.device import Device
    except ImportError as e:
        print(f"✗ Cannot import Bumble: {e}")
        print("  Make sure Bumble is installed: pip install bumble")
        return False
    
    test_address = "80:E4:BA:42:E9:AF"
    test_namespace = "F0:F1:F2:F3:F4:F5"
    
    try:
        # Test 1: Create and use keystore
        print("\n1️⃣  Testing keystore creation and key storage...")
        
        keystore = JsonKeyStore(test_namespace, keystore_file)
        
        # Create test bonding keys
        test_keys = PairingKeys(
            address_type=1,  # RANDOM_ADDRESS
            ltk=PairingKeys.Key(
                value=b'\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF\x00',
                authenticated=True,
                ediv=0x1234,
                rand=b'\x01\x02\x03\x04\x05\x06\x07\x08'
            ),
            irk=PairingKeys.Key(
                value=b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xAA\xBB\xCC\xDD\xEE\xFF',
                authenticated=True
            ),
            csrk=PairingKeys.Key(
                value=b'\xAA\xBB\xCC\xDD\xEE\xFF\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99',
                authenticated=True,
                counter=42
            )
        )
        
        # Store keys
        await keystore.update(test_address, test_keys)
        print(f"  ✓ Test bonding keys stored: {test_address}")
        
        # Test 2: Verify file created and contains data
        print("\n2️⃣  Verifying file persistence...")
        if not os.path.exists(keystore_file):
            print(f"  ✗ File not created: {keystore_file}")
            return False
        
        file_size = os.path.getsize(keystore_file)
        print(f"  ✓ File created: {keystore_file}")
        print(f"  ✓ File size: {file_size} bytes")
        
        # Verify content
        with open(keystore_file, 'r') as f:
            data = json.load(f)
        
        if test_namespace not in data:
            print(f"  ✗ Namespace not in file")
            return False
        
        if test_address not in data[test_namespace]:
            print(f"  ✗ Test address not in namespace")
            return False
        
        print(f"  ✓ Data structure valid")
        
        # Test 3: Retrieve keys
        print("\n3️⃣  Testing key retrieval...")
        retrieved_keys = await keystore.get(test_address)
        
        if retrieved_keys is None:
            print(f"  ✗ Keys not retrieved")
            return False
        
        print(f"  ✓ Keys successfully retrieved!")
        
        # Verify key content
        if retrieved_keys.ltk:
            ltk_match = retrieved_keys.ltk.value == test_keys.ltk.value
            auth_match = retrieved_keys.ltk.authenticated == test_keys.ltk.authenticated
            ediv_match = retrieved_keys.ltk.ediv == test_keys.ltk.ediv
            
            if ltk_match and auth_match and ediv_match:
                print(f"    ✓ LTK preserved correctly")
            else:
                print(f"    ✗ LTK data mismatch")
                return False
        
        if retrieved_keys.irk:
            irk_match = retrieved_keys.irk.value == test_keys.irk.value
            if irk_match:
                print(f"    ✓ IRK preserved correctly")
            else:
                print(f"    ✗ IRK data mismatch")
                return False
        
        if retrieved_keys.csrk:
            csrk_match = retrieved_keys.csrk.value == test_keys.csrk.value
            counter_match = retrieved_keys.csrk.counter == test_keys.csrk.counter
            
            if csrk_match and counter_match:
                print(f"    ✓ CSRK preserved correctly")
            else:
                print(f"    ✗ CSRK data mismatch")
                return False
        
        # Test 4: Test deletion
        print("\n4️⃣  Testing key deletion...")
        await keystore.delete(test_address)
        
        deleted_keys = await keystore.get(test_address)
        if deleted_keys is None:
            print(f"  ✓ Keys successfully deleted")
        else:
            print(f"  ✗ Keys still present after deletion")
            return False
        
        # Test 5: Verify lifecycle
        print("\n5️⃣  Testing complete lifecycle (store → reload → retrieve)...")
        
        # Store keys
        await keystore.update(test_address, test_keys)
        
        # Create new keystore instance (simulates app restart)
        keystore2 = JsonKeyStore(test_namespace, keystore_file)
        
        # Retrieve from "restarted" keystore
        reloaded_keys = await keystore2.get(test_address)
        
        if reloaded_keys is None:
            print(f"  ✗ Keys lost after simulated restart")
            return False
        
        if reloaded_keys.ltk and reloaded_keys.ltk.value == test_keys.ltk.value:
            print(f"  ✓ Keys successfully survived app restart")
        else:
            print(f"  ✗ Keys corrupted after restart")
            return False
        
        print("\n✅ All functionality tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify Bumble bonding and persistent key storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python verify_bonding.py                          # Full test
    python verify_bonding.py --check-only             # Check existing keys only
    python verify_bonding.py --keystore-file custom.json  # Use custom file
        """.strip()
    )
    
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check existing keystore, don't test functionality"
    )
    
    parser.add_argument(
        "--keystore-file",
        default="configs/bumble_bonds.json",
        help="Path to keystore file (default: configs/bumble_bonds.json)"
    )
    
    args = parser.parse_args()
    
    print_header("BUMBLE BONDING VERIFICATION TOOL")
    
    # Check current state
    print("\n📊 Checking existing keystore...")
    keystore_exists = check_existing_keystore(args.keystore_file)
    
    if args.check_only:
        print_header("Check Complete")
        sys.exit(0 if keystore_exists else 1)
    
    # Run functionality tests
    print("\n\n🔧 Running functionality tests...")
    
    try:
        test_passed = asyncio.run(test_keystore_functionality(args.keystore_file))
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Summary
    print_header("TEST SUMMARY")
    
    if keystore_exists:
        print("\n✅ Keystore file found with bonded devices")
    else:
        print("\n⚠️  No existing keystore file (normal for first run)")
    
    if test_passed:
        print("✅ Functionality tests passed")
        print("\n🎉 BONDING IS WORKING CORRECTLY!")
        print("\nNext steps:")
        print("  1. Pair with a real BLE device")
        print("  2. Disconnect and wait a few seconds")
        print("  3. Reconnect - should establish encrypted link automatically")
        print("  4. Run this script again to confirm keys are persisted")
        sys.exit(0)
    else:
        print("❌ Functionality tests failed")
        print("\nTroubleshooting:")
        print("  • Check that Bumble is installed: pip install bumble")
        print("  • Check file permissions on keystore file")
        print("  • Check available disk space")
        print("  • Review error messages above")
        sys.exit(1)

if __name__ == "__main__":
    main()
