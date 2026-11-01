from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from peripheraldock.models import (
    BatteryReading,
    Capabilities,
    ConnectionState,
    DeviceKind,
    DeviceStatus,
    DiscoveryResult,
)


class FakeAdapter:
    key = "fake"
    display_name = "Fake"
    kind = DeviceKind.MOUSE

    def __init__(self, detected=True, connected=True):
        self._discovery = DiscoveryResult(detected=detected, connected=connected)
        self._last_success = None

    def get_status(self):
        if not self._discovery.detected:
            return ConnectionState.DISCONNECTED
        return ConnectionState.CONNECTED if self._discovery.connected else ConnectionState.DETECTED

    def last_success(self):
        return self._last_success


class BatteryReadingTests(unittest.TestCase):
    def test_unknown_is_none_never_100(self):
        reading = BatteryReading.unknown(
            DeviceStatus.UNSUPPORTED, source="test", message="no battery page"
        )
        self.assertIsNone(reading.percentage)
        self.assertIsNone(reading.charging)
        self.assertEqual(reading.to_dict()["percentage"], None)

    def test_ok_requires_percentage(self):
        with self.assertRaises(ValueError):
            BatteryReading(
                percentage=None,
                charging=None,
                status=DeviceStatus.OK,
                source="test",
            )

    def test_unsupported_cannot_carry_percentage(self):
        with self.assertRaises(ValueError):
            BatteryReading(
                percentage=55,
                charging=False,
                status=DeviceStatus.UNSUPPORTED,
                source="test",
            )

    def test_percentage_bounds(self):
        for bad in (-1, 101):
            with self.assertRaises(ValueError):
                BatteryReading.ok(bad, source="test")

    def test_stale_can_carry_last_good(self):
        reading = BatteryReading(
            percentage=42,
            charging=False,
            status=DeviceStatus.STALE,
            source="test",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        self.assertFalse(reading.is_live_percentage)
        self.assertEqual(reading.percentage, 42)

    def test_age_seconds(self):
        old = datetime.now(timezone.utc) - timedelta(seconds=30)
        reading = BatteryReading.ok(50, source="test", timestamp=old)
        self.assertGreaterEqual(reading.age_seconds(), 29)
        self.assertLess(reading.age_seconds(), 35)


if __name__ == "__main__":
    unittest.main()
