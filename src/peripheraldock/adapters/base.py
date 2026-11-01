"""Adapter contract and cache/staleness handling.

Adapters implement ``_read_battery``.  The public ``read_battery`` adds the
last-good cache and marks fallback data as ``stale``; it never promotes old
data to ``ok``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from ..models import (
    BatteryReading,
    Capabilities,
    ConnectionState,
    DeviceKind,
    DeviceStatus,
    DiscoveryResult,
)


class DeviceAdapter(ABC):
    key: str = "unknown"
    display_name: str = "未知裝置"
    kind: DeviceKind = DeviceKind.UNKNOWN
    cache_ttl_seconds: int = 180

    def __init__(self) -> None:
        self._last_success: BatteryReading | None = None
        self._discovery: DiscoveryResult | None = None

    @abstractmethod
    def discover(self) -> DiscoveryResult:
        raise NotImplementedError

    @abstractmethod
    def _read_battery(self) -> BatteryReading:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> Capabilities:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    def read_battery(self) -> BatteryReading:
        try:
            result = self._read_battery()
        except Exception as exc:  # noqa: BLE001 - hardware exceptions are diverse
            result = BatteryReading.unknown(
                DeviceStatus.ERROR,
                source="adapter",
                message=f"未預期的讀取錯誤：{type(exc).__name__}: {exc}",
            )

        if result.status is DeviceStatus.OK:
            self._last_success = result
            return result

        if result.status is DeviceStatus.UNSUPPORTED:
            # A capability decision must not be masked by an old value.
            return result

        if self._last_success is not None:
            age = self._last_success.age_seconds()
            if age is not None:
                return BatteryReading(
                    percentage=self._last_success.percentage,
                    charging=self._last_success.charging,
                    status=DeviceStatus.STALE,
                    source=self._last_success.source,
                    timestamp=self._last_success.timestamp,
                    error_message=(
                        f"{result.error_message or '讀取失敗'}；"
                        f"顯示上次成功資料（{int(age)} 秒前），已標示為過期"
                    ),
                    components=self._last_success.components,
                )
        return result

    def get_status(self) -> ConnectionState:
        if self._discovery is None:
            return ConnectionState.UNKNOWN
        if not self._discovery.detected:
            return ConnectionState.DISCONNECTED
        if self._discovery.connected:
            return ConnectionState.CONNECTED
        return ConnectionState.DETECTED

    def last_success(self) -> BatteryReading | None:
        return self._last_success

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc).astimezone()

    def _remember_discovery(self, result: DiscoveryResult) -> DiscoveryResult:
        self._discovery = result
        return result
