"""JSON configuration in %APPDATA%\\PeripheralDock."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

APP_DIR_NAME = "PeripheralDock"
CONFIG_NAME = "config.json"


@dataclass
class AppConfig:
    low_battery_threshold: int = 20
    poll_interval_seconds: int = 60
    notifications_enabled: bool = True
    autostart_enabled: bool = False
    start_minimized: bool = True

    def __post_init__(self) -> None:
        self.low_battery_threshold = max(1, min(99, int(self.low_battery_threshold)))
        self.poll_interval_seconds = max(15, min(3600, int(self.poll_interval_seconds)))
        self.notifications_enabled = bool(self.notifications_enabled)
        self.autostart_enabled = bool(self.autostart_enabled)
        self.start_minimized = bool(self.start_minimized)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


def default_config_path() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_DIR_NAME / CONFIG_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}" / CONFIG_NAME


def load_config(path: Path | None = None) -> tuple[AppConfig, Path]:
    target = path or default_config_path()
    if not target.exists():
        return AppConfig(), target
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root must be an object")
        return AppConfig.from_dict(data), target
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # A corrupt file must not prevent the app from starting.
        return AppConfig(), target


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, target)
    return target
