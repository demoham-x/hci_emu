#!/usr/bin/env python3
"""
Test bonding persistence by reading the bonds file
"""
import json
import os

bonds_file = "configs/bumble_bonds.json"

if os.path.exists(bonds_file):
    with open(bonds_file, 'r') as f:
        bonds_data = json.load(f)
    
    print("=" * 70)
    print("BONDING STATUS")
    print("=" * 70)
    
    total_devices = 0
    
    # Bumble format: {local_address: {peer_address: {key_data}}}
    for local_addr, peers_dict in bonds_data.items():
        if isinstance(peers_dict, dict):
            device_count = len([p for p in peers_dict if isinstance(peers_dict[p], dict)])
            print(f"\nLocal device: {local_addr}")
            print(f"  Bonded devices: {device_count}")
            
            for peer_addr, keys in peers_dict.items():
                if isinstance(keys, dict):
                    total_devices += 1
                    print(f"\n  {peer_addr}:")
                    
                    # Check for each key type
                    key_types = {
                        "ltk_central": "LTK Central (encryption)",
                        "ltk_peripheral": "LTK Peripheral (encryption)",
                        "irk": "IRK (identity key)",
                        "csrk": "CSRK (signing key)",
                        "address_type": "Address type"
                    }
                    
                    for key_name, description in key_types.items():
                        if key_name in keys:
                            value = keys[key_name]
                            if isinstance(value, dict) and "value" in value:
                                # It's a key object with value property
                                key_value = value.get("value", "?")
                                auth = value.get("authenticated", False)
                                print(f"    ✓ {description}")
                                print(f"      Value: {key_value[:16]}..." if len(str(key_value)) > 16 else f"      Value: {key_value}")
                                if auth:
                                    print(f"      Authenticated: Yes")
                            else:
                                print(f"    ✓ {description}: {value}")
    
    print(f"\n{'=' * 70}")
    print(f"Total bonded devices: {total_devices}")
    print("=" * 70 + "\n")
else:
    print("\n❌ No bonding file found.")
    print("   Device hasn't been bonded yet.\n")

