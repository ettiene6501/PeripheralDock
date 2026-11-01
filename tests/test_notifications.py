from __future__ import annotations

import unittest

from peripheraldock.models import (
    BatteryReading,
    ConnectionState,
    DeviceKind,
    DeviceStatus,
    DiscoveryResult,
)
from peripheraldock.notifications import LowBatteryNotifier
from peripheraldock.service import DeviceSnapshot


class SnapshotAdapter:
    key = "mouse"
    display_name = "Mouse"
    kind = DeviceKind.MOUSE

    def __init__(self, connected=True):
        self._discovery = DiscoveryResult(detected=True, connected=connected)

    def get_status(self):
        return ConnectionState.CONNECTED if self._discovery.connected else ConnectionState.DETECTED


def snapshot(percentage, status=DeviceStatus.OK, connected=True, charging=False):
    if status is DeviceStatus.UNSUPPORTED:
        percentage = None
    reading = BatteryReading(
        percentage=percentage,
        charging=charging,
        status=status,
        source="test",
    )
    return DeviceSnapshot(
        adapter=SnapshotAdapter(connected),
        discovery=DiscoveryResult(detected=True, connected=connected),
        reading=reading,
    )


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.messages: list[tuple[str, str]] = []
        self.notifier = LowBatteryNotifier(
            threshold=20,
            enabled=True,
            notify=lambda title, message: self.messages.append((title, message)),
        )

    def test_below_threshold_notifies_once(self):
        emitted = self.notifier.process([snapshot(19)])
        self.assertEqual(len(emitted), 1)
        self.assertEqual(len(self.messages), 1)
        self.assertIn("19%", self.messages[0][1])
        self.notifier.process([snapshot(19)])
        self.assertEqual(len(self.messages), 1)

    def test_exactly_threshold_notifies(self):
        self.notifier.process([snapshot(20)])
        self.assertEqual(len(self.messages), 1)

    def test_above_threshold_does_not_notify(self):
        self.notifier.process([snapshot(21)])
        self.assertEqual(self.messages, [])

    def test_unsupported_never_notifies(self):
        self.notifier.process(
            [snapshot(0, status=DeviceStatus.UNSUPPORTED)]
        )
        self.assertEqual(self.messages, [])

    def test_stale_never_notifies(self):
        self.notifier.process([snapshot(10, status=DeviceStatus.STALE)])
        self.assertEqual(self.messages, [])

    def test_offline_never_notifies(self):
        self.notifier.process([snapshot(10, status=DeviceStatus.OFFLINE, connected=False)])
        self.assertEqual(self.messages, [])

    def test_not_connected_never_notifies(self):
        self.notifier.process([snapshot(10, connected=False)])
        self.assertEqual(self.messages, [])

    def test_disabled_never_notifies(self):
        self.notifier.enabled = False
        self.notifier.process([snapshot(10)])
        self.assertEqual(self.messages, [])

    def test_recovers_then_notifies_again(self):
        self.notifier.process([snapshot(10)])
        self.notifier.process([snapshot(30)])
        self.notifier.process([snapshot(10)])
        self.assertEqual(len(self.messages), 2)

    def test_different_percentage_notifies_again(self):
        self.notifier.process([snapshot(19)])
        self.notifier.process([snapshot(18)])
        self.assertEqual(len(self.messages), 2)


if __name__ == "__main__":
    unittest.main()
