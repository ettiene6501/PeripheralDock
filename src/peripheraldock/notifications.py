"""Low-battery notification policy.

The policy is intentionally strict: only a live ``ok`` reading from a
connected device can trigger.  Unsupported, stale, offline, error, and
unknown values are ignored.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .models import ConnectionState, DeviceStatus
from .service import DeviceSnapshot


class LowBatteryNotifier:
    def __init__(
        self,
        threshold: int = 20,
        enabled: bool = True,
        notify: Callable[[str, str], None] | None = None,
    ) -> None:
        self.threshold = max(1, min(99, int(threshold)))
        self.enabled = enabled
        self.notify = notify or (lambda _title, _message: None)
        self._last_notified: dict[str, int] = {}
        self._last_message: tuple[str, str] | None = None

    def process(self, snapshots: Iterable[DeviceSnapshot]) -> list[tuple[str, str]]:
        emitted: list[tuple[str, str]] = []
        if not self.enabled:
            return emitted
        seen: set[str] = set()
        for snapshot in snapshots:
            reading = snapshot.reading
            if reading is None or reading.percentage is None:
                continue
            if reading.status is not DeviceStatus.OK:
                continue
            if snapshot.connection is not ConnectionState.CONNECTED:
                continue
            if reading.percentage > self.threshold:
                self._last_notified.pop(snapshot.key, None)
                continue
            seen.add(snapshot.key)
            if self._last_notified.get(snapshot.key) == reading.percentage:
                continue
            self._last_notified[snapshot.key] = reading.percentage
            title = f"{snapshot.name} 電量偏低"
            message = f"目前電量 {reading.percentage}%，已達 {self.threshold}% 提醒門檻。請準備充電或更換電池。"
            self._last_message = (title, message)
            if self.enabled:
                self.notify(title, message)
                emitted.append((title, message))
        for key in list(self._last_notified):
            if key not in seen:
                self._last_notified.pop(key, None)
        return emitted

    @property
    def last_message(self) -> tuple[str, str] | None:
        return self._last_message
