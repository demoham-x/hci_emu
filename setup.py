#!/usr/bin/env python3
"""
Setup script to configure Bumble HCI testing environment
"""

import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and report status"""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        print(f"\n✓ {description} - Success")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {description} - Failed")
        return False


def main():
    """Main setup"""
    print("\n" + "="*60)
    print("  Bumble HCI Testing Environment Setup")
    print("="*60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("\n✗ Python 3.8+ required")
        return False
    
    print(f"\n✓ Python {sys.version.split()[0]} detected")
    
    # Create virtual environment
    if not os.path.exists("venv"):
        run_command("python -m venv venv", "Creating virtual environment")
    else:
        print("\n✓ Virtual environment already exists")
    
    # Activate and install
    activate_cmd = ".\\venv\\Scripts\\activate" if sys.platform == "win32" else "source venv/bin/activate"
    install_cmd = f"{activate_cmd} && pip install -r requirements.txt"
    
    run_command(install_cmd, "Installing dependencies")
    
    print("\n" + "="*60)
    print("  Setup Complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Activate virtual environment:")
    print(f"     {activate_cmd}")
    print("\n  2. Start HCI Bridge (Terminal 1):")
    print("     bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001")
    print("\n  3. Run testing menu (Terminal 2):")
    print("     python src/main.py")
    print()


if __name__ == "__main__":
    main()
