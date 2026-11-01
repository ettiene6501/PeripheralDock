"""Native Windows notification-area icon (no pystray dependency).

A message-only Win32 window owns the tray icon.  Clicking it calls a callback
which the Tk UI marshals back to its own thread with ``after``.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes

if sys.platform != "win32":  # pragma: no cover
    raise RuntimeError("peripheraldock.tray requires Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_APP = 0x8000
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001
IDI_APPLICATION = 32512


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", ctypes.c_wchar * 256),
        ("uTimeout", wintypes.UINT),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wintypes.WORD
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadIconW.restype = wintypes.HICON
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class TrayUnavailable(RuntimeError):
    pass


class TrayIcon:
    def __init__(self, on_activate, tooltip: str = "PeripheralDock — 周邊電量") -> None:
        self.on_activate = on_activate
        self.tooltip = tooltip
        self.hwnd = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: str | None = None
        self._wndproc = WNDPROC(self._window_proc)
        self._callback_message = WM_APP + 42
        self._class_name = f"PeripheralDockTray_{id(self)}"
        self._hicon = None
        self._nid: NOTIFYICONDATAW | None = None
        self._running = False

    def start(self, timeout: float = 3.0) -> None:
        if self._running:
            return
        self._thread = threading.Thread(target=self._run, name="PeripheralDockTray", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise TrayUnavailable("系統匣執行緒啟動逾時")
        if self._error:
            raise TrayUnavailable(self._error)

    def stop(self) -> None:
        if not self._running:
            return
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
        self._running = False

    def notify(self, title: str, message: str) -> bool:
        if not self._running or not self.hwnd:
            return False
        nid = self._base_nid()
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = title[:63]
        nid.szInfo = message[:255]
        nid.dwInfoFlags = NIIF_INFO
        nid.uTimeout = 5000
        return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))

    def _run(self) -> None:
        try:
            instance = kernel32.GetModuleHandleW(None)
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = self._wndproc
            wc.hInstance = instance
            wc.lpszClassName = self._class_name
            wc.hIcon = user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
            if not user32.RegisterClassExW(ctypes.byref(wc)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd = user32.CreateWindowExW(
                0,
                self._class_name,
                "PeripheralDock",
                0,
                0,
                0,
                0,
                0,
                None,
                None,
                instance,
                None,
            )
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hicon = wc.hIcon
            nid = self._base_nid()
            nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
            nid.uCallbackMessage = self._callback_message
            nid.hIcon = self._hicon
            nid.szTip = self.tooltip[:127]
            if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
                raise TrayUnavailable("Shell_NotifyIcon(NIM_ADD) 失敗（可能沒有 Explorer 系統匣）")
            self._nid = nid
            self._running = True
            self._ready.set()

            msg = wintypes.MSG()
            while True:
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._ready.set()
        finally:
            if self._nid is not None and self.hwnd:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            self._nid = None
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
                self.hwnd = None
            self._running = False

    def _base_nid(self) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        return nid

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == self._callback_message:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_RBUTTONUP):
                try:
                    self.on_activate()
                except Exception:
                    pass
            return 0
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
