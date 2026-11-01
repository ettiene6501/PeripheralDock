"""Device orchestration: one refresh produces one UI-ready snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .adapters.base import DeviceAdapter
from .adapters.logitech import LogitechMouseAdapter
from .adapters.rapoo import RapooKeyboardAdapter
from .adapters.redmi import RedmiBudsAdapter
from .models import BatteryReading, ConnectionState, DeviceKind, DeviceStatus, DiscoveryResult


@dataclass
class DeviceSnapshot:
    adapter: DeviceAdapter
    discovery: DiscoveryResult | None
    reading: BatteryReading | None
    refreshed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).astimezone())

    @property
    def key(self) -> str:
        return self.adapter.key

    @property
    def name(self) -> str:
        if self.discovery and self.discovery.name:
            return self.discovery.name
        return self.adapter.display_name

    @property
    def kind(self) -> DeviceKind:
        return self.adapter.kind

    @property
    def connection(self) -> ConnectionState:
        return self.adapter.get_status()

    @property
    def ui_state(self) -> str:
        if self.reading is None:
            if self.discovery and self.discovery.detected:
                return "detected"
            return "missing"
        return self.reading.status.value

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "name": self.name,
            "kind": self.kind.value,
            "connection": self.connection.value,
            "ui_state": self.ui_state,
            "discovery": self.discovery.to_dict() if self.discovery else None,
            "battery": self.reading.to_dict() if self.reading else None,
            "refreshed_at": self.refreshed_at.isoformat(timespec="seconds"),
        }


def default_adapters() -> list[DeviceAdapter]:
    return [RedmiBudsAdapter(), RapooKeyboardAdapter(), LogitechMouseAdapter()]


class DeviceService:
    def __init__(self, adapters: Iterable[DeviceAdapter] | None = None) -> None:
        self.adapters = list(adapters) if adapters is not None else default_adapters()
        self.snapshots: list[DeviceSnapshot] = [
            DeviceSnapshot(adapter=adapter, discovery=None, reading=None)
            for adapter in self.adapters
        ]
        self._discovered = False

    def refresh(self) -> list[DeviceSnapshot]:
        snapshots: list[DeviceSnapshot] = []
        for adapter in self.adapters:
            discovery = None
            try:
                discovery = adapter.discover()
            except Exception as exc:  # noqa: BLE001
                discovery = DiscoveryResult(
                    detected=False,
                    connected=False,
                    error_message=f"discover 失敗：{type(exc).__name__}: {exc}",
                )
            try:
                reading = adapter.read_battery()
            except Exception as exc:  # noqa: BLE001
                reading = BatteryReading.unknown(
                    DeviceStatus.ERROR,
                    source=getattr(adapter, "key", "unknown"),
                    message=f"read_battery 失敗：{type(exc).__name__}: {exc}",
                )
            snapshots.append(
                DeviceSnapshot(adapter=adapter, discovery=discovery, reading=reading)
            )
        self.snapshots = snapshots
        self._discovered = True
        return snapshots

    def low_battery(self, threshold: int) -> list[DeviceSnapshot]:
        result: list[DeviceSnapshot] = []
        for snapshot in self.snapshots:
            reading = snapshot.reading
            if reading is None or reading.percentage is None:
                continue
            if reading.status is not DeviceStatus.OK:
                continue
            if snapshot.connection is not ConnectionState.CONNECTED:
                continue
            if reading.percentage <= threshold:
                result.append(snapshot)
        return result

    def close(self) -> None:
        for adapter in self.adapters:
            try:
                adapter.close()
            except Exception:
                pass
