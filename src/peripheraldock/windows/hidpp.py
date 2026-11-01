"""Minimal read-only Logitech HID++ 2.0 client.

Only these read operations are implemented:
  * Ping
  * ROOT.GetFeature
  * DEVICE_FW_VERSION (ids/model)
  * DEVICE_NAME
  * BATTERY_STATUS / UNIFIED_BATTERY

No configuration, register write, pairing, or firmware command is exposed.
Protocol references: Solaar's hidpp20.py / base.py (GPL-2.0-or-later).
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass
from typing import Protocol

from ..models import BatteryReading, DeviceStatus
from ..windows.hid import HidHandle

SW_ID = 0x0B
SHORT_REPORT = 0x10
LONG_REPORT = 0x11
LONG_SIZE = 20

FEATURE_ROOT = 0x0000
FEATURE_DEVICE_FW_VERSION = 0x0003
FEATURE_DEVICE_NAME = 0x0005
FEATURE_BATTERY_STATUS = 0x1000
FEATURE_BATTERY_VOLTAGE = 0x1001
FEATURE_UNIFIED_BATTERY = 0x1004

HIDPP_ERRORS = {
    0x01: "UNKNOWN",
    0x02: "INVALID_ARGUMENT",
    0x03: "OUT_OF_RANGE",
    0x04: "HARDWARE_ERROR",
    0x05: "LOGITECH_ERROR",
    0x06: "INVALID_FEATURE_INDEX",
    0x07: "INVALID_FUNCTION",
    0x08: "BUSY",
    0x09: "UNSUPPORTED",
}


class HidppError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class HidppUnsupported(HidppError):
    pass


class Transport(Protocol):
    def write(self, data: bytes) -> None: ...
    def read(self, timeout_ms: int) -> bytes | None: ...
    def drain(self) -> None: ...
    def close(self) -> None: ...


class HidppHidTransport:
    def __init__(self, path: str, report_size: int = LONG_SIZE) -> None:
        self._handle = HidHandle(path)
        self.report_size = report_size

    def write(self, data: bytes) -> None:
        result = self._handle.write(data, 1500)
        if result.error:
            raise HidppError(result.error)

    def read(self, timeout_ms: int) -> bytes | None:
        result = self._handle.read(self.report_size, timeout_ms)
        if result.error:
            return None
        return result.data

    def drain(self) -> None:
        while True:
            data = self.read(3)
            if not data:
                return

    def close(self) -> None:
        self._handle.close()


@dataclass(frozen=True)
class DeviceIds:
    unit_id: str
    model_id: str
    transport_bits: int
    wpid: str | None


class HidppClient:
    def __init__(self, transport: Transport, device_index: int = 1) -> None:
        self.transport = transport
        self.device_index = device_index
        self._feature_cache: dict[int, int | None] = {}
        self._name: str | None = None
        self._ids: DeviceIds | None = None
        self.trace: list[dict[str, str]] = []

    # -- low-level -----------------------------------------------------
    def _request(
        self,
        feature: int,
        function: int = 0x00,
        params: bytes = b"",
        timeout: float = 2.5,
    ) -> bytes:
        request_id = (feature << 8) | (function & 0xF0) | SW_ID
        request_bytes = struct.pack("!H", request_id)
        frame = (
            bytes([LONG_REPORT, self.device_index])
            + request_bytes
            + params
        ).ljust(LONG_SIZE, b"\x00")
        if len(frame) != LONG_SIZE:
            raise HidppError("HID++ 長訊息長度錯誤")

        self.transport.drain()
        self.transport.write(frame)
        self.trace.append({"direction": "tx", "data": frame.hex().upper()})

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
            data = self.transport.read(min(remaining_ms, 500))
            if not data:
                continue
            self.trace.append({"direction": "rx", "data": data.hex().upper()})
            if len(data) < 5:
                continue
            # HID++ 2.0 error reply: FF <req_hi> <req_lo> <error>
            if data[2] == 0xFF and data[3:5] == request_bytes:
                code = data[5] if len(data) > 5 else None
                name = HIDPP_ERRORS.get(code or 0, f"0x{code:02X}" if code is not None else "?")
                raise HidppError(f"HID++ 錯誤 {name}", code)
            if data[2:4] == request_bytes:
                return data[4:]
        raise HidppError("HID++ 讀取逾時")

    def ping(self) -> float:
        """Return protocol version (e.g. 4.5) or raise HidppError."""
        request_bytes = struct.pack("!H", 0x0010 | SW_ID)
        mark = 0x5A
        frame = (
            bytes([LONG_REPORT, self.device_index])
            + request_bytes
            + bytes([0x00, 0x00, mark])
        ).ljust(LONG_SIZE, b"\x00")
        self.transport.drain()
        self.transport.write(frame)
        self.trace.append({"direction": "tx", "data": frame.hex().upper()})
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            data = self.transport.read(300)
            if not data:
                continue
            self.trace.append({"direction": "rx", "data": data.hex().upper()})
            if len(data) < 7:
                continue
            if data[2:4] == request_bytes and data[6] == mark:
                return data[4] + data[5] / 10.0
            if data[2] == 0xFF and data[3:5] == request_bytes:
                code = data[5] if len(data) > 5 else 0
                raise HidppError(f"裝置無回應（HID++ 錯誤 0x{code:02X}）", code)
        raise HidppError("ping 逾時")

    # -- features ------------------------------------------------------
    def feature_index(self, feature: int) -> int | None:
        if feature in self._feature_cache:
            return self._feature_cache[feature]
        data = self._request(FEATURE_ROOT, 0x00, struct.pack("!H", feature))
        index = data[0] if data else 0
        if not index:
            self._feature_cache[feature] = None
            return None
        self._feature_cache[feature] = index
        return index

    def device_ids(self) -> DeviceIds:
        if self._ids is not None:
            return self._ids
        index = self.feature_index(FEATURE_DEVICE_FW_VERSION)
        if not index:
            raise HidppUnsupported("裝置不支援 DEVICE_FW_VERSION")
        data = self._request(index, 0x00)
        if len(data) < 13:
            raise HidppError("DEVICE_FW_VERSION 回應過短")
        transport_bits = data[6]
        model_bytes = data[7:13]
        wpid = None
        if transport_bits & 0x04:
            wpid = model_bytes[0:2].hex().upper()
        self._ids = DeviceIds(
            unit_id=data[1:5].hex().upper(),
            model_id=model_bytes.hex().upper(),
            transport_bits=transport_bits,
            wpid=wpid,
        )
        return self._ids

    def device_name(self) -> str | None:
        if self._name is not None:
            return self._name
        index = self.feature_index(FEATURE_DEVICE_NAME)
        if not index:
            return None
        head = self._request(index, 0x00)
        length = head[0] if head else 0
        if not 1 <= length <= 64:
            return None
        name = bytearray()
        offset = 0
        while len(name) < length and offset < length:
            chunk = self._request(index, 0x10, bytes([offset]))
            if not chunk:
                break
            take = min(length - len(name), len(chunk))
            name.extend(chunk[:take])
            offset += take
            if take == 0:
                break
        self._name = bytes(name).decode("utf-8", errors="replace").strip("\x00 ")
        return self._name or None

    # -- battery -------------------------------------------------------
    def _battery_status(self, index: int) -> BatteryReading:
        data = self._request(index, 0x00)
        if len(data) < 3:
            raise HidppError("BATTERY_STATUS 回應過短")
        level, next_level, status = data[0], data[1], data[2] & 0x07
        if level == 0:
            raise HidppError("裝置回報電量 0（HID++ 定義為未知）", 0x03)
        if status in (0x05, 0x06):
            reason = "電池無效" if status == 0x05 else "電池溫度錯誤"
            return BatteryReading.unknown(
                DeviceStatus.ERROR,
                source=f"logitech-hidpp2:0x{FEATURE_BATTERY_STATUS:04X}",
                message=f"{reason}（status=0x{status:02X}），不顯示電量",
            )
        charging = status in (0x01, 0x02, 0x03, 0x04)
        return BatteryReading.ok(
            level,
            charging=charging,
            source=f"logitech-hidpp2:0x{FEATURE_BATTERY_STATUS:04X}",
        )

    def _unified_battery(self, index: int) -> BatteryReading:
        data = self._request(index, 0x10)
        if len(data) < 3:
            raise HidppError("UNIFIED_BATTERY 回應過短")
        discharge, _level, status = data[0], data[1], data[2] & 0x07
        if discharge == 0:
            raise HidppError("裝置回報電量 0（HID++ 定義為未知）", 0x03)
        if status in (0x05, 0x06):
            return BatteryReading.unknown(
                DeviceStatus.ERROR,
                source=f"logitech-hidpp2:0x{FEATURE_UNIFIED_BATTERY:04X}",
                message=f"電池狀態錯誤（status=0x{status:02X}），不顯示電量",
            )
        return BatteryReading.ok(
            discharge,
            charging=status in (0x01, 0x02, 0x03, 0x04),
            source=f"logitech-hidpp2:0x{FEATURE_UNIFIED_BATTERY:04X}",
        )

    def read_battery(self) -> BatteryReading:
        status_index = self.feature_index(FEATURE_BATTERY_STATUS)
        if status_index:
            return self._battery_status(status_index)
        unified_index = self.feature_index(FEATURE_UNIFIED_BATTERY)
        if unified_index:
            return self._unified_battery(unified_index)
        if self.feature_index(FEATURE_BATTERY_VOLTAGE):
            raise HidppUnsupported("僅提供電壓特徵，未經換算驗證，不顯示百分比")
        raise HidppUnsupported("此裝置未提供 HID++ 電池特徵（0x1000/0x1004）")

    def close(self) -> None:
        self.transport.close()
