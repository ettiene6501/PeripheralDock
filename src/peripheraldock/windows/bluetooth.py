"""Read-only Bluetooth evidence from the Windows registry.

The registry holds pairing and service information, not live battery values.
This module never claims that a paired device is currently connected.
"""

from __future__ import annotations

import winreg
from dataclasses import dataclass, field

BTHENUM_ROOT = r"SYSTEM\CurrentControlSet\Enum\BTHENUM"
BTHLE_ROOT = r"SYSTEM\CurrentControlSet\Enum\BTHLE"
BTHPORT_DEVICES = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"


@dataclass(frozen=True)
class BluetoothDeviceRecord:
    name: str
    address: str
    instance_id: str
    services: tuple[str, ...] = field(default_factory=tuple)
    has_le_node: bool = False

    @property
    def looks_like_headphones(self) -> bool:
        lowered = self.name.lower()
        return any(word in lowered for word in ("buds", "headphone", "headset", "earbud"))

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "address": self.address,
            "instance_id": self.instance_id,
            "services": list(self.services),
            "has_le_node": self.has_le_node,
        }


def _format_address(key_name: str) -> str:
    raw = key_name.removeprefix("Dev_").upper()
    return ":".join(raw[i : i + 2] for i in range(0, len(raw), 2))


def _read_default(handle: int, name: str) -> str:
    try:
        value, _ = winreg.QueryValueEx(handle, name)
    except OSError:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00")
    return str(value).rstrip("\x00")


def _decode_name(value: bytes | str) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\x00 ")
    return str(value).rstrip("\x00 ")


def _bthport_name(address: str) -> str:
    key_name = address.replace(":", "").lower()
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            f"{BTHPORT_DEVICES}\\{key_name}",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            for value_name in ("Name", "LEName"):
                try:
                    value, _ = winreg.QueryValueEx(key, value_name)
                except OSError:
                    continue
                name = _decode_name(value)
                if name:
                    return name
    except OSError:
        pass
    return ""


def _child_friendly_name(dev_key: int) -> str:
    try:
        index = 0
        while True:
            try:
                child_name = winreg.EnumKey(dev_key, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(dev_key, child_name, 0, winreg.KEY_READ) as child:
                    name = _read_default(child, "FriendlyName")
            except OSError:
                continue
            if not name:
                continue
            # Some service names are "@driver.inf,...;%1 Human Name".
            if ";" in name:
                tail = name.rsplit(";", 1)[-1].strip()
                if tail:
                    name = tail
            if name and not name.startswith("@"):
                return name
    except OSError:
        pass
    return ""


def _services_for_address(root: int, address: str) -> tuple[str, ...]:
    raw_address = address.replace(":", "").upper()
    services: set[str] = set()
    index = 0
    while True:
        try:
            subkey_name = winreg.EnumKey(root, index)
        except OSError:
            break
        index += 1
        if not subkey_name.startswith("{"):
            continue
        guid = subkey_name.split("_", 1)[0].strip("{}").lower()
        try:
            with winreg.OpenKey(root, subkey_name, 0, winreg.KEY_READ) as service_key:
                child_index = 0
                while True:
                    try:
                        child = winreg.EnumKey(service_key, child_index)
                    except OSError:
                        break
                    child_index += 1
                    if raw_address in child.upper():
                        services.add(guid)
        except OSError:
            continue
    return tuple(sorted(services))


def _service_names(handle: int) -> tuple[str, ...]:
    services: list[str] = []
    try:
        with winreg.OpenKey(handle, "", 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    subkey = winreg.EnumKey(key, index)
                except OSError:
                    break
                index += 1
                # Service subkeys are GUIDs such as {0000110b-...}.
                if subkey.startswith("{"):
                    services.append(subkey.strip("{}").lower())
    except OSError:
        pass
    return tuple(sorted(set(services)))


def enumerate_bluetooth_devices() -> list[BluetoothDeviceRecord]:
    devices: list[BluetoothDeviceRecord] = []
    try:
        root = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            BTHENUM_ROOT,
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
    except OSError:
        return devices

    with root:
        index = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            if not subkey_name.startswith("Dev_"):
                continue
            address = _format_address(subkey_name)
            try:
                with winreg.OpenKey(root, subkey_name, 0, winreg.KEY_READ) as dev_key:
                    name = (
                        _bthport_name(address)
                        or _child_friendly_name(dev_key)
                        or _read_default(dev_key, "FriendlyName")
                        or _read_default(dev_key, "DeviceDesc")
                    )
                    services = _service_names(dev_key) or _services_for_address(root, address)
            except OSError:
                continue
            instance_id = f"BTHENUM\\{subkey_name}"
            has_le = False
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    f"{BTHLE_ROOT}\\{subkey_name}",
                    0,
                    winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                ):
                    has_le = True
            except OSError:
                pass
            devices.append(
                BluetoothDeviceRecord(
                    name=name,
                    address=address,
                    instance_id=instance_id,
                    services=services,
                    has_le_node=has_le,
                )
            )
    return devices


def find_headset(name_contains: str = "Redmi Buds 4 Active") -> BluetoothDeviceRecord | None:
    for device in enumerate_bluetooth_devices():
        if name_contains.lower() in device.name.lower():
            return device
    return None


def find_by_address(address: str) -> BluetoothDeviceRecord | None:
    normalized = address.replace(":", "").lower()
    for device in enumerate_bluetooth_devices():
        if device.address.replace(":", "").lower() == normalized:
            return device
    return None
