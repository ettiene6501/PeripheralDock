"""Per-user Windows startup entry (HKCU Run, no administrator rights)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PeripheralDock"


def quote_windows_argument(value: str) -> str:
    """Quote one Windows command-line argument.

    Backslashes are only special before a closing quote; keep paths intact.
    """
    if '"' in value:
        raise ValueError("path contains an embedded quote")
    return f'"{value}"'


def build_autostart_command(
    *,
    frozen: bool | None = None,
    executable: str | None = None,
    script: str | None = None,
) -> str:
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if frozen:
        exe = executable or sys.executable
        return f"{quote_windows_argument(str(Path(exe).resolve()))} --minimized"
    python = executable or sys.executable
    launcher = script or str(Path(__file__).resolve().parents[2] / "main.py")
    return (
        f"{quote_windows_argument(str(Path(python).resolve()))} "
        f"{quote_windows_argument(str(Path(launcher).resolve()))} --minimized"
    )


def _open_run_key(write: bool = False):
    import winreg

    access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE if write else winreg.KEY_QUERY_VALUE
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access | winreg.KEY_WOW64_64KEY)


def is_enabled(value_name: str = VALUE_NAME) -> bool:
    import winreg

    try:
        with _open_run_key() as key:
            value, _ = winreg.QueryValueEx(key, value_name)
        return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool, value_name: str = VALUE_NAME) -> None:
    import winreg

    with _open_run_key(write=True) as key:
        if enabled:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, build_autostart_command())
        else:
            try:
                winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass


def autostart_status() -> str:
    return "已啟用" if is_enabled() else "未啟用"
