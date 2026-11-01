"""Redmi Buds 4 Active adapter.

This adapter deliberately does not invent a battery value.  On the tested
Windows 10 machine the headset is a paired *classic* Bluetooth audio device:
Windows exposes A2DP/HFP/AVRCP but no public battery property, no BTHLE node,
and no GATT Battery Service.  HFP does not provide a standard host-side query
for headset battery.  The adapter therefore keeps the interface and reports a
specific unsupported reason until a verifiable source exists.
"""

from __future__ import annotations

from ..models import BatteryReading, Capabilities, DeviceKind, DeviceStatus, DiscoveryResult
from ..windows import bluetooth
from .base import DeviceAdapter


class RedmiBudsAdapter(DeviceAdapter):
    key = "redmi-buds-4-active"
    display_name = "Redmi Buds 4 Active"
    kind = DeviceKind.HEADPHONES

    def __init__(self) -> None:
        super().__init__()
        self.record = None

    def discover(self) -> DiscoveryResult:
        record = bluetooth.find_headset("Redmi Buds 4 Active")
        self.record = record
        if record is None:
            return self._remember_discovery(
                DiscoveryResult(
                    detected=False,
                    connected=False,
                    name=self.display_name,
                    detail="登錄檔中沒有 Redmi Buds 4 Active 的 BTHENUM 配對節點。",
                )
            )

        identifiers = {
            "bluetooth_address": record.address,
            "bth_enum": record.instance_id,
            "services": ", ".join(record.services),
            "ble_node": "yes" if record.has_le_node else "no",
        }
        return self._remember_discovery(
            DiscoveryResult(
                detected=True,
                # Pairing/service records do not prove a live connection.
                connected=False,
                name=record.name,
                identifiers=identifiers,
                detail=(
                    "已配對的經典藍牙音訊裝置；Windows 未建立 BTHLE/GATT 物件。"
                    "即時連線狀態需由 WinRT BluetoothDevice 另行查詢。"
                ),
            )
        )

    def _read_battery(self) -> BatteryReading:
        if self.record is None:
            self.discover()
        if self.record is None:
            return BatteryReading.unknown(
                DeviceStatus.OFFLINE,
                source="windows-classic-bluetooth",
                message="找不到已配對的 Redmi Buds 4 Active。",
            )
        services = ", ".join(self.record.services) or "無服務記錄"
        return BatteryReading.unknown(
            DeviceStatus.UNSUPPORTED,
            source="windows-classic-bluetooth",
            message=(
                "Windows 未提供可讀取的經典藍牙耳機電量："
                "沒有 BTHLE/GATT Battery Service（0x180F/0x2A19），"
                "也沒有公開的 HFP 電量查詢 API。"
                f"已觀測服務：{services}。不顯示任何百分比。"
            ),
        )

    def get_capabilities(self) -> Capabilities:
        return Capabilities(
            can_read_battery=False,
            can_read_charging=False,
            supports_components=False,
            protocols=("Classic Bluetooth A2DP/HFP/AVRCP",),
            notes=(
                "未取得標準 GATT Battery Service；HFP 電量僅能由耳機主動送出，"
                "Windows 沒有公開 API 可查詢。不得以藍牙版本或音訊連線推論電量。"
            ),
        )

    def close(self) -> None:
        self.record = None
