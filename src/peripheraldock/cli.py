"""Command line: probe / once / run / autostart."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__, autostart
from .adapters.logitech import LogitechMouseAdapter
from .adapters.rapoo import RapooKeyboardAdapter
from .adapters.redmi import RedmiBudsAdapter
from .config import load_config
from .models import DeviceStatus
from .service import DeviceService
from .windows import bluetooth
from .windows.setupapi import enumerate_hid_devices

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _environment() -> dict[str, Any]:
    version = sys.getwindowsversion()
    return {
        "captured_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "os": platform.platform(),
        "windows_build": f"{version.major}.{version.minor}.{version.build}",
        "python": sys.version,
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
        "administrator": _is_admin(),
    }


def _is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_winrt_probe() -> dict[str, Any] | None:
    script = PROJECT_ROOT / "tools" / "winrt_probe.ps1"
    if not script.exists():
        return None
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Address",
                "4873CB476268",
                "-Scan",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        return {
            "exit_code": completed.returncode,
            "stderr": completed.stderr.strip(),
            "stdout": completed.stdout.strip(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def build_probe_report() -> dict[str, Any]:
    devices = [
        device
        for device in enumerate_hid_devices()
        if device.vendor_id in (0x046D, 0x24AE)
    ]
    bt_devices = [
        device
        for device in bluetooth.enumerate_bluetooth_devices()
        if "Redmi" in device.name or "Buds" in device.name
    ]

    adapters = [RedmiBudsAdapter(), RapooKeyboardAdapter(), LogitechMouseAdapter()]
    adapter_rows: list[dict[str, Any]] = []
    for adapter in adapters:
        discovery = adapter.discover()
        reading = adapter.read_battery()
        row = {
            "key": adapter.key,
            "name": adapter.display_name,
            "discovery": discovery.to_dict(),
            "battery": reading.to_dict(),
            "capabilities": adapter.get_capabilities().to_dict(),
        }
        client = getattr(adapter, "client", None)
        if client is not None:
            row["hidpp_trace"] = client.trace
        adapter.close()
        adapter_rows.append(row)

    return {
        "environment": _environment(),
        "hid_devices": [device.to_dict() for device in devices],
        "bluetooth_devices": [device.to_dict() for device in bt_devices],
        "adapters": adapter_rows,
        "winrt_redmi_probe": _run_winrt_probe(),
    }


def cmd_probe(args: argparse.Namespace) -> int:
    report = build_probe_report()
    text = json.dumps(report, ensure_ascii=False, indent=2, default=_json_default)
    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"已寫入 {target}")
    else:
        print(text)
    return 0


def _format_reading(reading) -> str:
    if reading.status is DeviceStatus.OK:
        charging = {True: "充電中", False: "未充電", None: "充電狀態未知"}[reading.charging]
        return f"{reading.percentage}% ({charging})"
    if reading.status is DeviceStatus.STALE:
        return f"{reading.percentage}% (過期)"
    if reading.status is DeviceStatus.UNSUPPORTED:
        return "不可讀取"
    return f"{reading.status.value}: {reading.error_message or ''}"


def cmd_once(args: argparse.Namespace) -> int:
    service = DeviceService()
    try:
        snapshots = service.refresh()
        for snapshot in snapshots:
            reading = snapshot.reading
            print(f"[{snapshot.kind.value}] {snapshot.name}")
            print(f"  連線：{snapshot.connection.value} / 狀態：{snapshot.ui_state}")
            if reading:
                print(f"  電量：{_format_reading(reading)}")
                print(f"  來源：{reading.source}")
                if reading.error_message:
                    print(f"  說明：{reading.error_message}")
            print()
    finally:
        service.close()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from .ui import run_ui

    config, path = load_config()
    run_ui(
        config,
        path,
        start_minimized=args.minimized or config.start_minimized,
    )
    return 0


def cmd_autostart(args: argparse.Namespace) -> int:
    if args.action == "status":
        print(f"開機啟動：{autostart.autostart_status()}")
    elif args.action == "enable":
        autostart.set_enabled(True)
        print("已啟用開機啟動（HKCU，目前使用者）。")
    elif args.action == "disable":
        autostart.set_enabled(False)
        print("已停用開機啟動。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peripheraldock", description="周邊電量監控")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    probe = sub.add_parser("probe", help="唯讀硬體探測並輸出 JSON")
    probe.add_argument("--json", metavar="PATH", help="寫入 JSON 證據檔")
    probe.set_defaults(func=cmd_probe)

    once = sub.add_parser("once", help="讀取一次並顯示結果")
    once.set_defaults(func=cmd_once)

    run = sub.add_parser("run", help="啟動系統匣 UI")
    run.add_argument("--minimized", action="store_true", help="啟動時隱藏到系統匣")
    run.set_defaults(func=cmd_run)

    startup = sub.add_parser("autostart", help="管理目前使用者的開機啟動")
    startup.add_argument("action", choices=("status", "enable", "disable"))
    startup.set_defaults(func=cmd_autostart)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
