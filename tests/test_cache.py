from __future__ import annotations

import unittest

from peripheraldock.adapters.base import DeviceAdapter
from peripheraldock.models import (
    BatteryReading,
    Capabilities,
    ConnectionState,
    DeviceKind,
    DeviceStatus,
    DiscoveryResult,
)


class ScriptedAdapter(DeviceAdapter):
    key = "scripted"
    display_name = "Scripted"
    kind = DeviceKind.MOUSE

    def __init__(self, readings):
        super().__init__()
        self._readings = list(readings)
        self.discover_calls = 0

    def discover(self):
        self.discover_calls += 1
        return self._remember_discovery(DiscoveryResult(detected=True, connected=True))

    def _read_battery(self):
        return self._readings.pop(0)

    def get_capabilities(self):
        return Capabilities(True, True, False)

    def close(self):
        pass


class CacheTests(unittest.TestCase):
    def test_success_is_cached(self):
        adapter = ScriptedAdapter([BatteryReading.ok(77, source="test")])
        result = adapter.read_battery()
        self.assertEqual(result.status, DeviceStatus.OK)
        self.assertEqual(adapter.last_success().percentage, 77)

    def test_failure_after_success_becomes_stale_not_ok(self):
        ok = BatteryReading.ok(77, source="test")
        adapter = ScriptedAdapter(
            [ok, BatteryReading.unknown(DeviceStatus.ERROR, source="test", message="timeout")]
        )
        adapter.read_battery()
        result = adapter.read_battery()
        self.assertEqual(result.status, DeviceStatus.STALE)
        self.assertEqual(result.percentage, 77)
        self.assertFalse(result.is_live_percentage)
        self.assertIn("過期", result.error_message)

    def test_unsupported_does_not_fall_back_to_cache(self):
        adapter = ScriptedAdapter(
            [
                BatteryReading.ok(77, source="test"),
                BatteryReading.unknown(
                    DeviceStatus.UNSUPPORTED, source="test", message="not supported"
                ),
            ]
        )
        adapter.read_battery()
        result = adapter.read_battery()
        self.assertEqual(result.status, DeviceStatus.UNSUPPORTED)
        self.assertIsNone(result.percentage)

    def test_no_cache_returns_original_failure(self):
        adapter = ScriptedAdapter(
            [BatteryReading.unknown(DeviceStatus.OFFLINE, source="test", message="gone")]
        )
        result = adapter.read_battery()
        self.assertEqual(result.status, DeviceStatus.OFFLINE)
        self.assertIsNone(result.percentage)

    def test_unexpected_exception_is_error(self):
        class Broken(ScriptedAdapter):
            def _read_battery(self):
                raise RuntimeError("boom")

        adapter = Broken([])
        result = adapter.read_battery()
        self.assertEqual(result.status, DeviceStatus.ERROR)
        self.assertIn("boom", result.error_message)

    def test_connection_state(self):
        adapter = ScriptedAdapter([])
        self.assertEqual(adapter.get_status(), ConnectionState.UNKNOWN)
        adapter.discover()
        self.assertEqual(adapter.get_status(), ConnectionState.CONNECTED)


if __name__ == "__main__":
    unittest.main()
