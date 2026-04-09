#!/usr/bin/env python3
"""Unit tests for Apple ANCS and AMS parsing helpers."""

import sys
import unittest

sys.path.insert(0, "src")

from hciemu.app import BLETestingApp
from hciemu.apple_services import AppleServices


class FakeConnector:
    def __init__(self, service_details=None):
        self.service_details = service_details or []


def _build_ancs_service_details():
    return [
        {
            "uuid": "7905F431-B5CE-4E99-A40F-4B1E122D00D0",
            "characteristics": [
                {
                    "uuid": "9FBF120D-6301-42D9-8C58-25E699A21DBD",
                    "handle": 0x002A,
                    "properties": "notify",
                },
                {
                    "uuid": "22EAC6E9-24D6-4BB5-BE44-B36ACE7C7BFB",
                    "handle": 0x002B,
                    "properties": "notify",
                },
                {
                    "uuid": "69D1D8F3-45E1-49A8-9821-9BBDFDAAD9D9",
                    "handle": 0x002C,
                    "properties": "write",
                },
            ],
        }
    ]


class AppleServicesParsingTests(unittest.TestCase):
    def setUp(self):
        self.apple_services = AppleServices(FakeConnector())

    def test_parse_ancs_notification_source(self):
        payload = bytes.fromhex("00 18 06 03 78 56 34 12")

        parsed = self.apple_services.parse_ancs_notification_source(payload)

        self.assertEqual(parsed["event"], "added")
        self.assertEqual(parsed["category"], "email")
        self.assertEqual(parsed["category_count"], 3)
        self.assertEqual(parsed["notification_uid"], 0x12345678)
        self.assertEqual(parsed["event_flag_names"], ["positive_action", "negative_action"])

    def test_parse_ams_entity_update_playback_info(self):
        payload = bytes([0, 1, 0]) + b"1,1.0,42.5"

        parsed = self.apple_services.parse_ams_entity_update_value(payload)

        self.assertEqual(parsed["entity"], "player")
        self.assertEqual(parsed["attribute"], "playback_info")
        self.assertEqual(parsed["value"]["playback_state"], "playing")
        self.assertEqual(parsed["value"]["playback_rate"], 1.0)
        self.assertEqual(parsed["value"]["elapsed_time_seconds"], 42.5)

    def test_parse_ams_entity_attribute_read(self):
        parsed = self.apple_services.parse_ams_entity_attribute_value(2, 2, b"Track Title")

        self.assertEqual(parsed["entity"], "track")
        self.assertEqual(parsed["attribute"], "title")
        self.assertEqual(parsed["value"], "Track Title")

    def test_app_refresh_reuses_existing_apple_service_instance(self):
        fake_app = BLETestingApp.__new__(BLETestingApp)
        fake_app.connector = FakeConnector(_build_ancs_service_details())
        fake_app.apple_services = None

        first = BLETestingApp._refresh_apple_services(fake_app)
        second = BLETestingApp._refresh_apple_services(fake_app)

        self.assertIsNotNone(first)
        self.assertIs(first, second)
        self.assertTrue(second.has_ancs())


if __name__ == "__main__":
    unittest.main()