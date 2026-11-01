"""Logitech M235 adapter (HID++ 2.0, read-only).

Verified on this machine:
  receiver 046D:C52B, paired device index 1, WPID 4055 (M235),
  BATTERY_STATUS feature 0x05, response 46 05 00 => 70%, discharging.

Only feature reads are sent.  No HID++ write/register-set/pairing command is
implemented.
"""

from __future__ import annotations

import time

from ..models import BatteryReading, Capabilities, DeviceKind, DeviceStatus, DiscoveryResult
from ..windows.hidpp import (
    FEATURE_BATTERY_STATUS,
    FEATURE_BATTERY_VOLTAGE,
    FEATURE_UNIFIED_BATTERY,
    HidppClient,
    HidppError,
    HidppHidTransport,
    HidppUnsupported,
)
from ..windows.setupapi import HidDevice, enumerate_hid_devices
from .base import DeviceAdapter

LOGITECH_VID = 0x046D
RECEIVER_PID = 0xC52B
M235_WPID = "4055"


class LogitechMouseAdapter(DeviceAdapter):
    key = "logitech-m235"
    display_name = "Logitech M235 無線滑鼠"
    kind = DeviceKind.MOUSE

    def __init__(self) -> None:
        super().__init__()
        self.client: HidppClient | None = None
        self.interface: HidDevice | None = None
        self.wpid: str | None = None
        self.model_name: str | None = None
        self.device_index: int | None = None

    def _candidates(self) -> list[HidDevice]:
        return [
            d
            for d in enumerate_hid_devices()
            if d.vendor_id == LOGITECH_VID
            and d.product_id == RECEIVER_PID
            and d.usage_page == 0xFF00
            and d.usage == 0x0002
            and d.input_report_bytes == 20
        ]

    def _open_client(self, interface: HidDevice) -> HidppClient | None:
        try:
            transport = HidppHidTransport(interface.path)
        except OSError as exc:
            self._last_error = f"無法開啟 HID++ 介面：{exc}"
            return None
        try:
            # Probe only paired-device slots.  A missing slot normally returns
            # quickly; timeouts are bounded so discovery stays responsive.
            for index in range(1, 7):
                client = HidppClient(transport, device_index=index)
                try:
                    protocol = client.ping()
                except HidppError:
                    continue
                if protocol < 2.0:
                    raise HidppUnsupported(
                        f"裝置 index {index} 只支援 HID++ {protocol:.1f}，此 adapter 需要 2.0"
                    )
                self.device_index = index
                return client
            transport.close()
            self._last_error = "接收器存在，但 1–6 號配對槽都沒有 HID++ 2.0 裝置回應。"
            return None
        except Exception:
            transport.close()
            raise

    def discover(self) -> DiscoveryResult:
        self._last_error = None
        candidates = self._candidates()
        if not candidates:
            return self._remember_discovery(
                DiscoveryResult(
                    detected=False,
                    connected=False,
                    name=self.display_name,
                    detail="未找到 Logitech 046D:C52B 的 HID++ 介面。",
                )
            )

        if self.client is not None:
            try:
                self.client.ping()
                return self._discovery or self._remember_discovery(
                    DiscoveryResult(
                        detected=True,
                        connected=True,
                        name=self.model_name or self.display_name,
                        detail="HID++ 裝置仍在線。",
                    )
                )
            except HidppError:
                self.close()

        self.interface = candidates[0]
        self.client = self._open_client(self.interface)
        if self.client is None:
            return self._remember_discovery(
                DiscoveryResult(
                    detected=True,
                    connected=False,
                    name="Logitech 無線接收器",
                    identifiers={
                        "vid_pid": "046D:C52B",
                        "product": self.interface.product or "",
                        "interface": self.interface.instance_id,
                    },
                    detail=self._last_error or "接收器存在，但沒有可回應的裝置。",
                    error_message=self._last_error,
                )
            )

        try:
            ids = self.client.device_ids()
            self.wpid = ids.wpid
            name = self.client.device_name()
            self.model_name = name
        except HidppError as exc:
            self.close()
            return self._remember_discovery(
                DiscoveryResult(
                    detected=True,
                    connected=False,
                    name="Logitech 無線裝置",
                    detail=f"有 HID++ 回應，但讀取裝置識別失敗：{exc}",
                    error_message=str(exc),
                )
            )

        display = self._friendly_name()
        return self._remember_discovery(
            DiscoveryResult(
                detected=True,
                connected=True,
                name=display,
                identifiers={
                    "vid_pid": "046D:C52B",
                    "receiver_product": self.interface.product or "",
                    "hidpp_interface": self.interface.instance_id,
                    "device_index": str(self.device_index),
                    "wpid": self.wpid or "未知",
                    "unit_id": ids.unit_id,
                    "model_id": ids.model_id,
                },
                detail=(
                    f"WPID {self.wpid or '未知'}；HID++ 2.0 裝置 "
                    f"index {self.device_index}；名稱：{display}"
                ),
            )
        )

    def _friendly_name(self) -> str:
        if self.wpid == M235_WPID:
            return "Logitech M235 無線滑鼠"
        if self.model_name:
            return f"Logitech {self.model_name}（WPID {self.wpid or '未知'}）"
        return f"Logitech 無線滑鼠（WPID {self.wpid or '未知'}）"

    def _read_battery(self) -> BatteryReading:
        if self.client is None:
            self.discover()
        if self.client is None:
            return BatteryReading.unknown(
                DeviceStatus.OFFLINE,
                source="logitech-hidpp2",
                message=self._last_error or "Logitech HID++ 裝置離線。",
            )
        try:
            return self.client.read_battery()
        except HidppUnsupported as exc:
            return BatteryReading.unknown(
                DeviceStatus.UNSUPPORTED,
                source="logitech-hidpp2",
                message=str(exc),
            )
        except HidppError as exc:
            # A stale handle or a sleeping mouse is an offline condition, not
            # a fabricated 0%.  The next refresh will rediscover it.
            self.close()
            return BatteryReading.unknown(
                DeviceStatus.OFFLINE,
                source="logitech-hidpp2",
                message=f"HID++ 讀取失敗，裝置可能休眠或離開接收器：{exc}",
            )

    def get_capabilities(self) -> Capabilities:
        protocols = ["Logitech HID++ 2.0"]
        if self.client is not None:
            try:
                if self.client.feature_index(FEATURE_BATTERY_STATUS):
                    protocols.append("BATTERY_STATUS 0x1000")
                elif self.client.feature_index(FEATURE_UNIFIED_BATTERY):
                    protocols.append("UNIFIED_BATTERY 0x1004")
                elif self.client.feature_index(FEATURE_BATTERY_VOLTAGE):
                    protocols.append("BATTERY_VOLTAGE 0x1001（僅電壓）")
            except HidppError:
                pass
        return Capabilities(
            can_read_battery=self.client is not None,
            can_read_charging=True,
            supports_components=False,
            protocols=tuple(protocols),
            notes=(
                "只發送 ROOT.GetFeature、DEVICE_FW_VERSION、DEVICE_NAME、"
                "BATTERY_STATUS/UNIFIED_BATTERY 的唯讀查詢。"
            ),
        )

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None
        self.interface = None
        self.device_index = None
        self._last_error = None
