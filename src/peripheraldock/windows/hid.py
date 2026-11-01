"""Minimal overlapped HID read/write wrapper (no third-party packages)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

if sys.platform != "win32":  # pragma: no cover
    raise RuntimeError("peripheraldock.windows.hid requires Windows")


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CreateEventW.argtypes = [
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.BOOL,
    wintypes.LPCWSTR,
]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.ResetEvent.argtypes = [wintypes.HANDLE]
kernel32.ResetEvent.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetOverlappedResult.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(OVERLAPPED),
    ctypes.POINTER(wintypes.DWORD),
    wintypes.BOOL,
]
kernel32.GetOverlappedResult.restype = wintypes.BOOL
kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
kernel32.CancelIoEx.restype = wintypes.BOOL
kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(OVERLAPPED),
]
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(OVERLAPPED),
]
kernel32.WriteFile.restype = wintypes.BOOL


@dataclass
class HidResult:
    data: bytes | None
    error: str | None = None


class HidHandle:
    """Open a HID collection for read/write HID++ traffic.

    The class intentionally does not expose a generic "send arbitrary bytes"
    helper to the UI.  Adapters own the protocol knowledge.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.handle = kernel32.CreateFileW(
            path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED,
            None,
        )
        if self.handle == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        self.event = kernel32.CreateEventW(None, True, False, None)
        if not self.event:
            kernel32.CloseHandle(self.handle)
            raise ctypes.WinError(ctypes.get_last_error())
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.event:
            kernel32.CloseHandle(self.event)
            self.event = None
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "HidHandle":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def write(self, data: bytes, timeout_ms: int = 1500) -> HidResult:
        if self._closed:
            return HidResult(None, "HID handle 已關閉")
        buffer = ctypes.create_string_buffer(bytes(data), len(data))
        written = wintypes.DWORD(0)
        ov = OVERLAPPED()
        ov.hEvent = self.event
        kernel32.ResetEvent(self.event)
        ok = kernel32.WriteFile(
            self.handle, buffer, len(data), ctypes.byref(written), ctypes.byref(ov)
        )
        if not ok:
            error = ctypes.get_last_error()
            if error != ERROR_IO_PENDING:
                return HidResult(None, f"WriteFile 失敗: WinError {error}")
            if not self._wait(ov, timeout_ms):
                return HidResult(None, "HID 寫入逾時")
            if not kernel32.GetOverlappedResult(
                self.handle, ctypes.byref(ov), ctypes.byref(written), False
            ):
                return HidResult(
                    None, f"GetOverlappedResult 失敗: WinError {ctypes.get_last_error()}"
                )
        return HidResult(b"", None)

    def read(self, size: int, timeout_ms: int = 1500) -> HidResult:
        if self._closed:
            return HidResult(None, "HID handle 已關閉")
        buffer = ctypes.create_string_buffer(size)
        received = wintypes.DWORD(0)
        ov = OVERLAPPED()
        ov.hEvent = self.event
        kernel32.ResetEvent(self.event)
        ok = kernel32.ReadFile(
            self.handle, buffer, size, ctypes.byref(received), ctypes.byref(ov)
        )
        if not ok:
            error = ctypes.get_last_error()
            if error != ERROR_IO_PENDING:
                return HidResult(None, f"ReadFile 失敗: WinError {error}")
            if not self._wait(ov, timeout_ms):
                kernel32.CancelIoEx(self.handle, ctypes.byref(ov))
                kernel32.WaitForSingleObject(self.event, 100)
                return HidResult(None, "HID 讀取逾時")
            if not kernel32.GetOverlappedResult(
                self.handle, ctypes.byref(ov), ctypes.byref(received), False
            ):
                return HidResult(
                    None, f"GetOverlappedResult 失敗: WinError {ctypes.get_last_error()}"
                )
        return HidResult(buffer.raw[: received.value], None)

    def _wait(self, ov: OVERLAPPED, timeout_ms: int) -> bool:
        result = kernel32.WaitForSingleObject(ov.hEvent, timeout_ms)
        return result == WAIT_OBJECT_0
