"""Shared data types for PeripheralDock.

The central rule: an unknown battery value is ``None``.  No adapter is allowed
to substitute 0, 100, or an estimate when the hardware did not answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DeviceStatus(str, Enum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    OFFLINE = "offline"
    STALE = "stale"
    ERROR = "error"


class DeviceKind(str, Enum):
    HEADPHONES = "headphones"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    UNKNOWN = "unknown"


class ConnectionState(str, Enum):
    DETECTED = "detected"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ComponentBattery:
    """One independently readable battery, e.g. left earbud or charging case."""

    label: str
    percentage: int | None = None
    charging: bool | None = None
    available: bool = False

    def __post_init__(self) -> None:
        if self.percentage is not None and not 0 <= self.percentage <= 100:
            raise ValueError(f"percentage out of range: {self.percentage}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "percentage": self.percentage,
            "charging": self.charging,
            "available": self.available,
        }


@dataclass(frozen=True)
class BatteryReading:
    """Result of one read_battery() call.

    ``timestamp`` is the last *successful* read, not the time of this call.
    A failed call keeps the old timestamp so the UI can judge staleness.
    """

    percentage: int | None
    charging: bool | None
    status: DeviceStatus
    source: str
    timestamp: datetime | None = None
    error_message: str | None = None
    components: dict[str, ComponentBattery] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.percentage is not None:
            if not isinstance(self.percentage, int) or isinstance(self.percentage, bool):
                raise ValueError("percentage must be int or None")
            if not 0 <= self.percentage <= 100:
                raise ValueError(f"percentage out of range: {self.percentage}")
        if self.status is DeviceStatus.OK and self.percentage is None:
            raise ValueError("status=ok requires a percentage")
        if self.status is DeviceStatus.UNSUPPORTED and self.percentage is not None:
            raise ValueError("status=unsupported cannot carry a percentage")

    @classmethod
    def ok(
        cls,
        percentage: int,
        *,
        source: str,
        charging: bool | None = None,
        timestamp: datetime | None = None,
        components: dict[str, ComponentBattery] | None = None,
    ) -> "BatteryReading":
        return cls(
            percentage=percentage,
            charging=charging,
            status=DeviceStatus.OK,
            source=source,
            timestamp=timestamp or datetime.now(timezone.utc).astimezone(),
            components=components or {},
        )

    @classmethod
    def unknown(
        cls,
        status: DeviceStatus,
        *,
        source: str,
        message: str,
        timestamp: datetime | None = None,
        components: dict[str, ComponentBattery] | None = None,
    ) -> "BatteryReading":
        return cls(
            percentage=None,
            charging=None,
            status=status,
            source=source,
            timestamp=timestamp,
            error_message=message,
            components=components or {},
        )

    @property
    def is_live_percentage(self) -> bool:
        return self.status is DeviceStatus.OK and self.percentage is not None

    def age_seconds(self, now: datetime | None = None) -> float | None:
        if self.timestamp is None:
            return None
        current = now or datetime.now(timezone.utc).astimezone()
        if self.timestamp.tzinfo is None:
            current = current.replace(tzinfo=None)
        return max(0.0, (current - self.timestamp).total_seconds())

    def to_dict(self) -> dict[str, Any]:
        return {
            "percentage": self.percentage,
            "charging": self.charging,
            "status": self.status.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(timespec="seconds")
            if self.timestamp
            else None,
            "age_seconds": round(self.age_seconds(), 1)
            if self.age_seconds() is not None
            else None,
            "error_message": self.error_message,
            "components": {key: value.to_dict() for key, value in self.components.items()},
        }


@dataclass(frozen=True)
class DiscoveryResult:
    detected: bool
    connected: bool
    name: str | None = None
    identifiers: dict[str, str] = field(default_factory=dict)
    detail: str = ""
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "connected": self.connected,
            "name": self.name,
            "identifiers": self.identifiers,
            "detail": self.detail,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class Capabilities:
    can_read_battery: bool
    can_read_charging: bool
    supports_components: bool
    protocols: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_read_battery": self.can_read_battery,
            "can_read_charging": self.can_read_charging,
            "supports_components": self.supports_components,
            "protocols": list(self.protocols),
            "notes": self.notes,
        }
