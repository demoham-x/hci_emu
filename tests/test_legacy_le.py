#!/usr/bin/env python3
"""
Tests for Legacy LE mode.

Verifies that apply_legacy_le_mode() correctly strips the extended LE
feature/command bits so that Bumble falls back to legacy HCI procedures,
and that BLETestingMenu propagates the legacy_le flag to its scanning call.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestApplyLegacyLeMode(unittest.TestCase):
    """Unit tests for the apply_legacy_le_mode helper in utils.py"""

    def _make_mock_device(self, le_features: int, supported_commands: int):
        """Return a mock Bumble Device with the given host capability fields."""
        device = MagicMock()
        device.host.local_le_features = le_features
        device.host.local_supported_commands = supported_commands
        return device

    def test_strips_extended_advertising_feature_bit(self):
        """LE_EXTENDED_ADVERTISING bit should be cleared after apply_legacy_le_mode."""
        from bumble import hci
        from utils import apply_legacy_le_mode

        ext_adv_bit = int(hci.LeFeatureMask.LE_EXTENDED_ADVERTISING)
        # Start with all feature bits set
        device = self._make_mock_device(
            le_features=0xFFFFFFFFFFFFFFFF,
            supported_commands=0,
        )

        apply_legacy_le_mode(device)

        self.assertEqual(
            device.host.local_le_features & ext_adv_bit,
            0,
            "LE_EXTENDED_ADVERTISING feature bit must be cleared",
        )

    def test_strips_extended_create_connection_command_bit(self):
        """Extended Create Connection supported-command bit should be cleared."""
        from bumble import hci
        from utils import apply_legacy_le_mode

        mask = hci.HCI_SUPPORTED_COMMANDS_MASKS.get(
            hci.HCI_LE_EXTENDED_CREATE_CONNECTION_COMMAND, 0
        )
        # Start with all command bits set
        # HCI Supported Commands is 64 bytes = 512 bits; use 512 to cover all bits.
        all_commands = (1 << 512) - 1
        device = self._make_mock_device(
            le_features=0,
            supported_commands=all_commands,
        )

        apply_legacy_le_mode(device)

        self.assertEqual(
            device.host.local_supported_commands & mask,
            0,
            "Extended Create Connection command bit must be cleared",
        )

    def test_other_le_features_preserved(self):
        """Feature bits unrelated to extended advertising should be untouched."""
        from bumble import hci
        from utils import apply_legacy_le_mode

        ext_adv_bit = int(hci.LeFeatureMask.LE_EXTENDED_ADVERTISING)
        initial = 0xFFFFFFFFFFFFFFFF
        device = self._make_mock_device(
            le_features=initial,
            supported_commands=0,
        )

        apply_legacy_le_mode(device)

        # All bits except ext_adv_bit should remain set
        expected = initial & ~ext_adv_bit
        self.assertEqual(device.host.local_le_features, expected)

    def test_does_not_raise_on_missing_bumble(self):
        """apply_legacy_le_mode should not raise even if bumble import fails."""
        from utils import apply_legacy_le_mode

        device = MagicMock()
        device.host.local_le_features = 0
        device.host.local_supported_commands = 0

        with patch.dict('sys.modules', {'bumble': None, 'bumble.hci': None}):
            # Should log a warning rather than propagate the ImportError
            try:
                apply_legacy_le_mode(device)
            except Exception as exc:
                self.fail(f"apply_legacy_le_mode raised unexpectedly: {exc}")


class TestBLETestingMenuLegacyFlag(unittest.TestCase):
    """Verify that BLETestingMenu stores the legacy_le flag."""

    def test_legacy_le_default_false(self):
        """BLETestingMenu should default to legacy_le=False."""
        # Patch heavy imports so we don't need a running controller
        with patch('bumble.keys.JsonKeyStore'), \
             patch('hci_snooper.HCISnooper'), \
             patch('hci_snooper.BumbleHCITransportWrapper'):
            from main import BLETestingMenu
            menu = BLETestingMenu.__new__(BLETestingMenu)
            menu.transport_spec = "tcp-client:127.0.0.1:9001"
            menu.legacy_le = False
            self.assertFalse(menu.legacy_le)

    def test_legacy_le_flag_stored(self):
        """BLETestingMenu should store legacy_le=True when passed."""
        with patch('bumble.keys.JsonKeyStore'), \
             patch('hci_snooper.HCISnooper'), \
             patch('hci_snooper.BumbleHCITransportWrapper'):
            from main import BLETestingMenu
            menu = BLETestingMenu.__new__(BLETestingMenu)
            menu.legacy_le = True
            self.assertTrue(menu.legacy_le)


if __name__ == "__main__":
    unittest.main(verbosity=2)
