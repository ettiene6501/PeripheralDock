"""Rapoo E1050 adapter.

The USB receiver identifies itself only as "Rapoo 2.4G Wireless Device"
(24AE:2010).  Its HID report descriptor exposes keyboard/mouse/consumer
collections but no Generic Device Controls Battery Strength usage and no
feature report.  No public Rapoo SDK or protocol document was found, so the
adapter must not send vendor writes or synthesize a percentage.
"""

from __future__ import annotations

from ..models import BatteryReading, Capabilities, DeviceKind, DeviceStatus, DiscoveryResult
from ..windows.setupapi import HidDevice, enumerate_hid_devices
from .base import DeviceAdapter

RAPOO_VID = 0x24AE
RAPOO_PID = 0x2010


class RapooKeyboardAdapter(DeviceAdapter):
    key = "rapoo-e1050"
    display_name = "Rapoo E1050 無線鍵盤"
    kind = DeviceKind.KEYBOARD

    def __init__(self) -> None:
        super().__init__()
        self.receiver_devices: list[HidDevice] = []
        self.keyboard: HidDevice | None = None

    def _scan(self) -> None:
        devices = [
            d
            for d in enumerate_hid_devices()
            if d.vendor_id == RAPOO_VID and d.product_id == RAPOO_PID
        ]
        self.receiver_devices = devices
        self.keyboard = next(
            (
                d
                for d in devices
                if d.usage_page == 0x01 and d.usage == 0x06
            ),
            None,
        )

    def discover(self) -> DiscoveryResult:
        self._scan()
        if not self.receiver_devices:
            return self._remember_discovery(
                DiscoveryResult(
                    detected=False,
                    connected=False,
                    name=self.display_name,
                    detail="未找到 Rapoo 24AE:2010 接收器。",
                )
            )
        connected = self.keyboard is not None
        return self._remember_discovery(
            DiscoveryResult(
                detected=True,
                connected=connected,
                name="Rapoo 2.4G Wireless Device",
                identifiers={
                    "vid_pid": "24AE:2010",
                    "product": self.receiver_devices[0].product or "",
                    "manufacturer": self.receiver_devices[0].manufacturer or "",
                    "keyboard_interface": self.keyboard.instance_id
                    if self.keyboard
                    else "未找到",
                    "hid_interfaces": str(len(self.receiver_devices)),
                },
                detail=(
                    "接收器與鍵盤 HID 集合存在；裝置字串未包含 E1050 型號，"
                    "因此型號只能標為待實物確認。"
                ),
            )
        )

    def _read_battery(self) -> BatteryReading:
        if not self.receiver_devices:
            self.discover()
        if not self.receiver_devices:
            return BatteryReading.unknown(
                DeviceStatus.OFFLINE,
                source="windows-hid",
                message="Rapoo 24AE:2010 接收器未插入。",
            )
        if self.keyboard is None:
            return BatteryReading.unknown(
                DeviceStatus.OFFLINE,
                source="windows-hid",
                message="接收器存在，但沒有鍵盤 HID 集合（鍵盤可能關機或未配對）。",
            )

        battery_caps = [
            value
            for device in self.receiver_devices
            for value in device.battery_values
        ]
        if battery_caps:
            return BatteryReading.unknown(
                DeviceStatus.ERROR,
                source="windows-hid:battery-strength",
                message=(
                    "HID descriptor 出現 Battery Strength，但此型號的讀取格式尚未實測驗證；"
                    "為避免誤報，暫不顯示百分比。"
                ),
            )
        return BatteryReading.unknown(
            DeviceStatus.UNSUPPORTED,
            source="windows-hid",
            message=(
                "HID report descriptor 沒有 Generic Device Controls Battery Strength"
                "（Usage Page 0x06 / Usage 0x20），也沒有 Feature Report；"
                "Rapoo 未公開此型號的電量協定，因此不可讀取電量。"
            ),
        )

    def get_capabilities(self) -> Capabilities:
        return Capabilities(
            can_read_battery=False,
            can_read_charging=False,
            supports_components=False,
            protocols=("USB HID keyboard",),
            notes=(
                "24AE:2010 的 Product String 只顯示 Rapoo 2.4G Wireless Device；"
                "未找到官方 SDK/協定文件，不發送廠商 HID 寫入命令。"
            ),
        )

    def close(self) -> None:
        self.keyboard = None
        self.receiver_devices = []
