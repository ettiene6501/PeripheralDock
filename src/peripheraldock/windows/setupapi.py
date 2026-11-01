"""Read-only Windows SetupAPI / HID enumeration.

Only descriptors and metadata are read.  No keyboard input is captured and no
output/feature report is written.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import POINTER, byref, c_ubyte, c_ulong, c_ushort, c_void_p, c_wchar
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

if sys.platform != "win32":  # pragma: no cover - the app is Windows-only
    raise RuntimeError("peripheraldock.windows.setupapi requires Windows")

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)

HID_GUID = UUID("4d1e55b2-f16f-11cf-88cb-001111000030")

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010
SPDRP_DEVICEDESC = 0x00000000
SPDRP_HARDWAREID = 0x00000001
SPDRP_COMPATIBLEIDS = 0x00000002
SPDRP_SERVICE = 0x00000004
SPDRP_MFG = 0x0000000B
SPDRP_FRIENDLYNAME = 0x0000000C
SPDRP_LOCATION_INFORMATION = 0x0000000D
SPDRP_PHYSICAL_DEVICE_OBJECT_NAME = 0x0000000E

DIF_PROPERTYCHANGE = 0x12

ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

HIDP_STATUS_SUCCESS = 0x00110000
HIDP_REPORT_TYPE_INPUT = 0
HIDP_REPORT_TYPE_OUTPUT = 1
HIDP_REPORT_TYPE_FEATURE = 2

HID_USAGE_PAGE_GENERIC_DEVICE_CONTROLS = 0x06
HID_USAGE_BATTERY_STRENGTH = 0x20


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value: UUID) -> "GUID":
        return cls(
            value.time_low,
            value.time_mid,
            value.time_hi_version,
            (c_ubyte * 8).from_buffer_copy(value.bytes[8:]),
        )


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", c_wchar * 1),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", c_ushort),
        ("ProductID", c_ushort),
        ("VersionNumber", c_ushort),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", c_ushort),
        ("UsagePage", c_ushort),
        ("InputReportByteLength", c_ushort),
        ("OutputReportByteLength", c_ushort),
        ("FeatureReportByteLength", c_ushort),
        ("Reserved", c_ushort * 17),
        ("NumberLinkCollectionNodes", c_ushort),
        ("NumberInputButtonCaps", c_ushort),
        ("NumberInputValueCaps", c_ushort),
        ("NumberInputDataIndices", c_ushort),
        ("NumberOutputButtonCaps", c_ushort),
        ("NumberOutputValueCaps", c_ushort),
        ("NumberOutputDataIndices", c_ushort),
        ("NumberFeatureButtonCaps", c_ushort),
        ("NumberFeatureValueCaps", c_ushort),
        ("NumberFeatureDataIndices", c_ushort),
    ]


class _ValueCapsRange(ctypes.Structure):
    _fields_ = [
        ("UsageMin", c_ushort),
        ("UsageMax", c_ushort),
        ("StringMin", c_ushort),
        ("StringMax", c_ushort),
        ("DesignatorMin", c_ushort),
        ("DesignatorMax", c_ushort),
        ("DataIndexMin", c_ushort),
        ("DataIndexMax", c_ushort),
    ]


class _ValueCapsNotRange(ctypes.Structure):
    _fields_ = [
        ("Usage", c_ushort),
        ("Reserved1", c_ushort),
        ("StringIndex", c_ushort),
        ("Reserved2", c_ushort),
        ("DesignatorIndex", c_ushort),
        ("Reserved3", c_ushort),
        ("DataIndex", c_ushort),
        ("Reserved4", c_ushort),
    ]


class _ValueCapsUnion(ctypes.Union):
    _fields_ = [("Range", _ValueCapsRange), ("NotRange", _ValueCapsNotRange)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [
        ("UsagePage", c_ushort),
        ("ReportID", c_ubyte),
        ("IsAlias", c_ubyte),
        ("BitField", c_ushort),
        ("LinkCollection", c_ushort),
        ("LinkUsage", c_ushort),
        ("LinkUsagePage", c_ushort),
        ("IsRange", c_ubyte),
        ("IsStringRange", c_ubyte),
        ("IsDesignatorRange", c_ubyte),
        ("IsAbsolute", c_ubyte),
        ("HasNull", c_ubyte),
        ("Reserved", c_ubyte),
        ("BitSize", c_ushort),
        ("ReportCount", c_ushort),
        ("Reserved2", c_ushort * 5),
        ("UnitsExp", ctypes.c_ulong),
        ("Units", ctypes.c_ulong),
        ("LogicalMin", ctypes.c_long),
        ("LogicalMax", ctypes.c_long),
        ("PhysicalMin", ctypes.c_long),
        ("PhysicalMax", ctypes.c_long),
        ("Value", _ValueCapsUnion),
    ]


setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiGetClassDevsW.argtypes = [
    POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE,
    c_void_p,
    POINTER(GUID),
    wintypes.DWORD,
    POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE,
    POINTER(SP_DEVICE_INTERFACE_DATA),
    c_void_p,
    wintypes.DWORD,
    POINTER(wintypes.DWORD),
    POINTER(SP_DEVINFO_DATA),
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    wintypes.HANDLE,
    POINTER(SP_DEVINFO_DATA),
    wintypes.LPWSTR,
    wintypes.DWORD,
    POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
    wintypes.HANDLE,
    POINTER(SP_DEVINFO_DATA),
    wintypes.DWORD,
    POINTER(wintypes.DWORD),
    c_void_p,
    wintypes.DWORD,
    POINTER(wintypes.DWORD),
]
setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

hid.HidD_GetHidGuid.argtypes = [POINTER(GUID)]
hid.HidD_GetHidGuid.restype = None
hid.HidD_GetAttributes.argtypes = [wintypes.HANDLE, POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
hid.HidD_GetProductString.argtypes = [wintypes.HANDLE, c_void_p, wintypes.ULONG]
hid.HidD_GetProductString.restype = wintypes.BOOLEAN
hid.HidD_GetManufacturerString.argtypes = [wintypes.HANDLE, c_void_p, wintypes.ULONG]
hid.HidD_GetManufacturerString.restype = wintypes.BOOLEAN
hid.HidD_GetSerialNumberString.argtypes = [wintypes.HANDLE, c_void_p, wintypes.ULONG]
hid.HidD_GetSerialNumberString.restype = wintypes.BOOLEAN
hid.HidD_GetPreparsedData.argtypes = [wintypes.HANDLE, POINTER(c_void_p)]
hid.HidD_GetPreparsedData.restype = wintypes.BOOLEAN
hid.HidD_FreePreparsedData.argtypes = [c_void_p]
hid.HidD_FreePreparsedData.restype = wintypes.BOOLEAN
hid.HidP_GetCaps.argtypes = [c_void_p, POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = wintypes.LONG
hid.HidP_GetValueCaps.argtypes = [
    ctypes.c_int,
    POINTER(HIDP_VALUE_CAPS),
    POINTER(c_ushort),
    c_void_p,
]
hid.HidP_GetValueCaps.restype = wintypes.LONG

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


@dataclass
class HidDevice:
    path: str
    instance_id: str
    vendor_id: int
    product_id: int
    version_number: int
    product: str | None
    manufacturer: str | None
    serial_number: str | None
    usage_page: int
    usage: int
    input_report_bytes: int
    output_report_bytes: int
    feature_report_bytes: int
    battery_values: list[dict[str, Any]] = field(default_factory=list)
    open_error: str | None = None
    parent_instance_id: str | None = None

    @property
    def vid_pid(self) -> str:
        return f"{self.vendor_id:04X}:{self.product_id:04X}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "instance_id": self.instance_id,
            "parent_instance_id": self.parent_instance_id,
            "vid_pid": self.vid_pid,
            "version_number": f"{self.version_number:04X}",
            "product": self.product,
            "manufacturer": self.manufacturer,
            "serial_number": self.serial_number,
            "usage_page": f"0x{self.usage_page:04X}",
            "usage": f"0x{self.usage:04X}",
            "input_report_bytes": self.input_report_bytes,
            "output_report_bytes": self.output_report_bytes,
            "feature_report_bytes": self.feature_report_bytes,
            "battery_values": self.battery_values,
            "open_error": self.open_error,
        }


def _enum_hid_interfaces() -> list[tuple[str, str, str | None]]:
    """Return (device_path, instance_id, parent_instance_id) for present HID."""

    guid = GUID.from_uuid(HID_GUID)
    flags = DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    info_set = setupapi.SetupDiGetClassDevsW(byref(guid), None, None, flags)
    if info_set == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())

    results: list[tuple[str, str, str | None]] = []
    try:
        index = 0
        while True:
            interface = SP_DEVICE_INTERFACE_DATA()
            interface.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(
                info_set, None, byref(guid), index, byref(interface)
            ):
                error = ctypes.get_last_error()
                if error == ERROR_NO_MORE_ITEMS:
                    break
                raise ctypes.WinError(error)

            required = wintypes.DWORD(0)
            setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set, byref(interface), None, 0, byref(required), None
            )

            buffer = ctypes.create_string_buffer(max(required.value, 16))
            # cbSize is 8 on 64-bit Windows and 6 on 32-bit Windows.  The path
            # starts immediately after it.  Reading it with wstring_at avoids
            # ctypes' single-character c_wchar[1] field semantics.
            ctypes.c_uint32.from_buffer(buffer).value = (
                8 if ctypes.sizeof(c_void_p) == 8 else 6
            )
            devinfo = SP_DEVINFO_DATA()
            devinfo.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(
                info_set,
                byref(interface),
                ctypes.cast(buffer, c_void_p),
                required.value,
                byref(required),
                byref(devinfo),
            ):
                raise ctypes.WinError(ctypes.get_last_error())

            path = ctypes.wstring_at(ctypes.addressof(buffer) + 4)
            instance_id = _device_instance_id(info_set, devinfo) or ""
            parent = _registry_property(
                info_set, devinfo, SPDRP_PHYSICAL_DEVICE_OBJECT_NAME
            )
            results.append((path, instance_id, parent))
            index += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(info_set)
    return results


def _device_instance_id(handle: wintypes.HANDLE, devinfo: SP_DEVINFO_DATA) -> str | None:
    buffer = ctypes.create_unicode_buffer(1024)
    required = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDeviceInstanceIdW(
        handle, byref(devinfo), buffer, len(buffer), byref(required)
    )
    return buffer.value if ok else None


def _registry_property(
    handle: wintypes.HANDLE, devinfo: SP_DEVINFO_DATA, prop: int
) -> str | None:
    buffer = ctypes.create_string_buffer(4096)
    required = wintypes.DWORD(0)
    reg_type = wintypes.DWORD(0)
    ok = setupapi.SetupDiGetDeviceRegistryPropertyW(
        handle,
        byref(devinfo),
        prop,
        byref(reg_type),
        buffer,
        len(buffer),
        byref(required),
    )
    if not ok:
        return None
    if reg_type.value in (7,):  # REG_MULTI_SZ
        return buffer.raw[: required.value].decode("utf-16-le", errors="replace").rstrip(
            "\x00"
        )
    if reg_type.value in (1, 2):  # REG_SZ / REG_EXPAND_SZ
        return buffer.raw[: required.value].decode("utf-16-le", errors="replace").rstrip(
            "\x00"
        )
    return buffer.raw[: required.value].decode("utf-16-le", errors="replace").rstrip(
        "\x00"
    )


def _open_hid(path: str, access: int = 0) -> wintypes.HANDLE:
    handle = kernel32.CreateFileW(
        path,
        access,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    return handle


def _string_descriptor(handle: wintypes.HANDLE, getter: Any) -> str | None:
    buffer = ctypes.create_unicode_buffer(256)
    if getter(handle, ctypes.cast(buffer, c_void_p), ctypes.sizeof(buffer)):
        value = buffer.value.strip()
        return value or None
    return None


def _value_caps(
    preparsed: c_void_p, report_type: int, count: int
) -> list[HIDP_VALUE_CAPS]:
    if count <= 0:
        return []
    array = (HIDP_VALUE_CAPS * count)()
    length = c_ushort(count)
    status = hid.HidP_GetValueCaps(report_type, array, byref(length), preparsed)
    if status != HIDP_STATUS_SUCCESS:
        return []
    return list(array[: length.value])


def _battery_values(caps: list[HIDP_VALUE_CAPS], kind: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for cap in caps:
        usages: list[int] = []
        if cap.IsRange:
            usages.extend(range(cap.Value.Range.UsageMin, cap.Value.Range.UsageMax + 1))
        else:
            usages.append(cap.Value.NotRange.Usage)
        if cap.UsagePage != HID_USAGE_PAGE_GENERIC_DEVICE_CONTROLS:
            continue
        if HID_USAGE_BATTERY_STRENGTH not in usages:
            continue
        found.append(
            {
                "report_type": kind,
                "report_id": cap.ReportID,
                "usage_page": f"0x{cap.UsagePage:04X}",
                "usage": "0x0020",
                "bit_size": cap.BitSize,
                "report_count": cap.ReportCount,
                "logical_min": cap.LogicalMin,
                "logical_max": cap.LogicalMax,
                "is_absolute": bool(cap.IsAbsolute),
            }
        )
    return found


def enumerate_hid_devices() -> list[HidDevice]:
    devices: list[HidDevice] = []
    for path, instance_id, parent in _enum_hid_interfaces():
        handle = _open_hid(path)
        open_error: str | None = None
        if handle == INVALID_HANDLE_VALUE:
            open_error = f"CreateFileW: {ctypes.WinError(ctypes.get_last_error())}"
            devices.append(
                HidDevice(
                    path=path,
                    instance_id=instance_id,
                    vendor_id=0,
                    product_id=0,
                    version_number=0,
                    product=None,
                    manufacturer=None,
                    serial_number=None,
                    usage_page=0,
                    usage=0,
                    input_report_bytes=0,
                    output_report_bytes=0,
                    feature_report_bytes=0,
                    open_error=open_error,
                    parent_instance_id=parent,
                )
            )
            continue
        try:
            attributes = HIDD_ATTRIBUTES()
            attributes.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
            if not hid.HidD_GetAttributes(handle, byref(attributes)):
                open_error = f"HidD_GetAttributes: {ctypes.WinError(ctypes.get_last_error())}"

            preparsed = c_void_p()
            caps = HIDP_CAPS()
            battery_values: list[dict[str, Any]] = []
            if hid.HidD_GetPreparsedData(handle, byref(preparsed)):
                try:
                    if hid.HidP_GetCaps(preparsed, byref(caps)) == HIDP_STATUS_SUCCESS:
                        for report_type, kind, count in (
                            (HIDP_REPORT_TYPE_FEATURE, "feature", caps.NumberFeatureValueCaps),
                            (HIDP_REPORT_TYPE_INPUT, "input", caps.NumberInputValueCaps),
                        ):
                            battery_values.extend(
                                _battery_values(
                                    _value_caps(preparsed, report_type, count), kind
                                )
                            )
                finally:
                    hid.HidD_FreePreparsedData(preparsed)
            else:
                open_error = open_error or (
                    f"HidD_GetPreparsedData: {ctypes.WinError(ctypes.get_last_error())}"
                )

            devices.append(
                HidDevice(
                    path=path,
                    instance_id=instance_id,
                    vendor_id=attributes.VendorID,
                    product_id=attributes.ProductID,
                    version_number=attributes.VersionNumber,
                    product=_string_descriptor(handle, hid.HidD_GetProductString),
                    manufacturer=_string_descriptor(handle, hid.HidD_GetManufacturerString),
                    serial_number=_string_descriptor(handle, hid.HidD_GetSerialNumberString),
                    usage_page=caps.UsagePage,
                    usage=caps.Usage,
                    input_report_bytes=caps.InputReportByteLength,
                    output_report_bytes=caps.OutputReportByteLength,
                    feature_report_bytes=caps.FeatureReportByteLength,
                    battery_values=battery_values,
                    open_error=open_error,
                    parent_instance_id=parent,
                )
            )
        finally:
            kernel32.CloseHandle(handle)
    return devices


def find_parent_usb(instance_id: str) -> str | None:
    """Extract the USB parent pattern from a HID instance id, if present."""

    marker = "VID_"
    if marker not in instance_id:
        return None
    segment = instance_id.split("\\", 1)[1] if "\\" in instance_id else instance_id
    # HID\VID_046D&PID_C52B&MI_02&Col01\...
    parts = segment.split("&")
    if len(parts) >= 2 and parts[0].startswith("VID_"):
        return f"USB\\{parts[0]}&{parts[1]}"
    return None
