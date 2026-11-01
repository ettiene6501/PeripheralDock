from __future__ import annotations

import struct
import unittest

from peripheraldock.models import DeviceStatus
from peripheraldock.windows.hidpp import (
    HidppClient,
    HidppError,
    HidppUnsupported,
)


def response(dev: int, request_id: int, payload: bytes = b"") -> bytes:
    data = bytes([0x11, dev]) + struct.pack("!H", request_id) + payload
    return data.ljust(20, b"\x00")


def error_response(dev: int, request_id: int, code: int) -> bytes:
    data = bytes([0x11, dev, 0xFF]) + struct.pack("!H", request_id) + bytes([code])
    return data.ljust(20, b"\x00")


class FakeTransport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read(self, timeout_ms: int) -> bytes | None:
        return self.replies.pop(0) if self.replies else None

    def drain(self) -> None:
        pass

    def close(self) -> None:
        pass


class HidppTests(unittest.TestCase):
    def test_ping(self):
        transport = FakeTransport([response(1, 0x001B, b"\x04\x05\x5A")])
        client = HidppClient(transport, 1)
        self.assertAlmostEqual(client.ping(), 4.5, places=1)

    def test_battery_status_70_discharging(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x05\x00\x00"),
                response(1, 0x050B, b"\x46\x05\x00"),
            ]
        )
        reading = HidppClient(transport, 1).read_battery()
        self.assertEqual(reading.status, DeviceStatus.OK)
        self.assertEqual(reading.percentage, 70)
        self.assertFalse(reading.charging)
        self.assertIn("0x1000", reading.source)
        self.assertGreaterEqual(len(transport.writes), 2)
        for frame in transport.writes:
            self.assertEqual(len(frame), 20)
            self.assertEqual(frame[0], 0x11)
            self.assertEqual(frame[1], 1)
            # Only function 0 (read) / 1 (read) are used; no write opcodes.
            self.assertIn(frame[3] & 0xF0, (0x00, 0x10))

    def test_battery_status_charging(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x05\x00\x00"),
                response(1, 0x050B, b"\x32\x00\x01"),
            ]
        )
        reading = HidppClient(transport, 1).read_battery()
        self.assertEqual(reading.percentage, 50)
        self.assertTrue(reading.charging)

    def test_invalid_battery_status_is_error_not_percentage(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x05\x00\x00"),
                response(1, 0x050B, b"\x32\x00\x05"),
            ]
        )
        reading = HidppClient(transport, 1).read_battery()
        self.assertEqual(reading.status, DeviceStatus.ERROR)
        self.assertIsNone(reading.percentage)

    def test_zero_level_is_not_reported_as_0_percent(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x05\x00\x00"),
                response(1, 0x050B, b"\x00\x00\x00"),
            ]
        )
        with self.assertRaises(HidppError):
            HidppClient(transport, 1).read_battery()

    def test_no_battery_feature_is_unsupported(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x00\x00\x00"),
                response(1, 0x000B, b"\x00\x00\x00"),
                response(1, 0x000B, b"\x00\x00\x00"),
            ]
        )
        with self.assertRaises(HidppUnsupported):
            HidppClient(transport, 1).read_battery()

    def test_protocol_error_raises_with_code(self):
        transport = FakeTransport([error_response(1, 0x000B, 0x09)])
        with self.assertRaises(HidppError) as caught:
            HidppClient(transport, 1).feature_index(0x1000)
        self.assertEqual(caught.exception.code, 0x09)

    def test_ids_include_wpid(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x02\x00\x00"),
                response(
                    1,
                    0x020B,
                    b"\x01\xA1\xEA\x4D\xA9\x00\x04\x40\x55\x00\x00\x00\x00",
                ),
            ]
        )
        ids = HidppClient(transport, 1).device_ids()
        self.assertEqual(ids.wpid, "4055")
        self.assertEqual(ids.unit_id, "A1EA4DA9")

    def test_name(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x03\x00\x00"),
                response(1, 0x030B, b"\x0e"),
                response(1, 0x031B, b"Wireless Mouse"),
            ]
        )
        name = HidppClient(transport, 1).device_name()
        self.assertEqual(name, "Wireless Mouse")

    def test_trace_records_read_only_traffic(self):
        transport = FakeTransport(
            [
                response(1, 0x000B, b"\x05\x00\x00"),
                response(1, 0x050B, b"\x46\x05\x00"),
            ]
        )
        client = HidppClient(transport, 1)
        client.read_battery()
        self.assertGreaterEqual(len(client.trace), 4)
        self.assertEqual(client.trace[0]["direction"], "tx")


if __name__ == "__main__":
    unittest.main()
