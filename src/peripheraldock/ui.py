"""Tkinter UI and tray integration (Traditional Chinese)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from . import autostart
from .config import AppConfig, save_config
from .models import DeviceKind, DeviceStatus
from .notifications import LowBatteryNotifier
from .service import DeviceService, DeviceSnapshot
from .tray import TrayIcon, TrayUnavailable

BG = "#0f1115"
CARD = "#191c23"
CARD_ALT = "#20242d"
TEXT = "#f2f4f8"
MUTED = "#9aa3b2"
ACCENT = "#6f9cff"
GOOD = "#54d18c"
WARN = "#f5b84b"
BAD = "#ff6b6b"
BORDER = "#2a303b"

STATE_LABELS = {
    DeviceStatus.OK.value: "讀取成功",
    DeviceStatus.UNSUPPORTED.value: "硬體不支援",
    DeviceStatus.OFFLINE.value: "裝置離線",
    DeviceStatus.STALE.value: "資料過期",
    DeviceStatus.ERROR.value: "讀取失敗",
    "detected": "已偵測",
    "missing": "未偵測",
}

CONNECTION_LABELS = {
    "connected": "已連線",
    "detected": "已配對／已偵測",
    "disconnected": "未連線",
    "unknown": "狀態未知",
}

KIND_ICONS = {
    DeviceKind.HEADPHONES: "🎧",
    DeviceKind.KEYBOARD: "⌨",
    DeviceKind.MOUSE: "🖱",
    DeviceKind.UNKNOWN: "◈",
}


def shorten(text: str | None, limit: int = 150) -> str:
    if not text:
        return ""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class DeviceCard:
    def __init__(self, parent: tk.Widget, snapshot: DeviceSnapshot) -> None:
        self.key = snapshot.key
        self.frame = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
        )
        self.frame.pack(fill="x", padx=18, pady=4)
        self.frame.grid_columnconfigure(1, weight=1)

        icon = KIND_ICONS.get(snapshot.kind, "◈")
        self.icon = tk.Label(
            self.frame,
            text=icon,
            font=("Segoe UI Emoji", 20),
            bg=CARD,
            fg=TEXT,
            width=2,
        )
        self.icon.grid(row=0, column=0, rowspan=2, padx=(12, 4), pady=(8, 0), sticky="n")

        self.name = tk.Label(
            self.frame,
            text=snapshot.name,
            font=("Microsoft JhengHei UI", 11, "bold"),
            bg=CARD,
            fg=TEXT,
            anchor="w",
        )
        self.name.grid(row=0, column=1, sticky="w", pady=(8, 0))

        self.state = tk.Label(
            self.frame,
            text="尚未讀取",
            font=("Microsoft JhengHei UI", 9),
            bg=CARD,
            fg=MUTED,
            anchor="e",
        )
        self.state.grid(row=0, column=2, sticky="e", padx=(8, 12), pady=(8, 0))

        self.percentage = tk.Label(
            self.frame,
            text="—",
            font=("Segoe UI", 21, "bold"),
            bg=CARD,
            fg=MUTED,
            anchor="w",
            width=5,
        )
        self.percentage.grid(row=1, column=1, sticky="w")

        self.detail = tk.Label(
            self.frame,
            text="",
            font=("Microsoft JhengHei UI", 9),
            bg=CARD,
            fg=MUTED,
            anchor="w",
            justify="left",
            wraplength=580,
        )
        self.detail.grid(row=2, column=0, columnspan=3, sticky="w", padx=14, pady=(0, 0))

        self.progress = ttk.Progressbar(
            self.frame,
            style="Battery.Horizontal.TProgressbar",
            maximum=100,
            value=0,
            length=560,
        )
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", padx=14, pady=(3, 0))

        self.meta = tk.Label(
            self.frame,
            text="",
            font=("Microsoft JhengHei UI", 8),
            bg=CARD,
            fg="#7f8796",
            anchor="w",
            justify="left",
            wraplength=640,
        )
        self.meta.grid(row=4, column=0, columnspan=3, sticky="w", padx=14, pady=(2, 6))
        self.progress.grid_remove()

    def update(self, snapshot: DeviceSnapshot) -> None:
        reading = snapshot.reading
        connection = CONNECTION_LABELS.get(snapshot.connection.value, snapshot.connection.value)
        self.name.config(text=snapshot.name)

        if reading is None:
            self.state.config(text=connection, fg=MUTED)
            self.percentage.config(text="—", fg=MUTED)
            self.detail.config(text="尚未執行硬體探測。")
            self.progress.grid_remove()
            self.meta.config(text="")
            return

        label = STATE_LABELS.get(reading.status.value, reading.status.value)
        color = {
            DeviceStatus.OK: GOOD,
            DeviceStatus.UNSUPPORTED: MUTED,
            DeviceStatus.OFFLINE: WARN,
            DeviceStatus.STALE: WARN,
            DeviceStatus.ERROR: BAD,
        }.get(reading.status, MUTED)
        self.state.config(text=f"{connection} · {label}", fg=color)

        if reading.percentage is not None:
            suffix = "%"
            if reading.status is DeviceStatus.STALE:
                suffix = "%（過期）"
            self.percentage.config(text=f"{reading.percentage}{suffix}", fg=color)
            self.progress.grid()
            self.progress.config(value=reading.percentage)
        else:
            self.percentage.config(text="—", fg=color)
            self.progress.grid_remove()

        if reading.status is DeviceStatus.UNSUPPORTED:
            self.detail.config(
                text=f"電量不可讀取 — {shorten(reading.error_message, 130)}",
                fg=TEXT,
            )
        elif reading.status is DeviceStatus.OK:
            charging = "充電中" if reading.charging else "未充電"
            self.detail.config(text=f"{charging} · 來源：{reading.source}", fg=MUTED)
        else:
            self.detail.config(
                text=shorten(reading.error_message or label, 150),
                fg=WARN if reading.status in (DeviceStatus.STALE, DeviceStatus.OFFLINE) else BAD,
            )

        bits: list[str] = []
        if reading.timestamp is not None:
            bits.append(f"最後成功：{reading.timestamp.astimezone().strftime('%H:%M:%S')}")
        if reading.status is DeviceStatus.UNSUPPORTED:
            self.meta.grid_remove()
        else:
            self.meta.grid()
            self.meta.config(text="  ·  ".join(bits))


class PeripheralDockApp:
    def __init__(
        self,
        root: tk.Tk,
        config: AppConfig,
        config_path: Path,
        *,
        start_minimized: bool = False,
    ) -> None:
        self.root = root
        self.config = config
        self.config_path = config_path
        self.service = DeviceService()
        self.notifier = LowBatteryNotifier(
            threshold=config.low_battery_threshold,
            enabled=config.notifications_enabled,
            notify=self._notify,
        )
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._refreshing = False
        self._after_id: str | None = None
        self._tray: TrayIcon | None = None
        self._tray_available = False
        self._closing = False

        self.root.title("PeripheralDock — 周邊電量")
        self.root.configure(bg=BG)
        self.root.geometry("760x570")
        self.root.minsize(680, 520)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_style()
        self._build()
        self._start_tray()
        self.root.after(150, self._poll_queue)
        self.refresh_async()
        if start_minimized and self._tray_available:
            self.root.withdraw()

    # -- construction -------------------------------------------------
    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Battery.Horizontal.TProgressbar",
            troughcolor="#2a303b",
            background=ACCENT,
            bordercolor="#2a303b",
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
        )

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(10, 4))
        tk.Label(
            header,
            text="PeripheralDock",
            font=("Microsoft JhengHei UI", 18, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(side="left")
        tk.Label(
            header,
            text="周邊電量監控",
            font=("Microsoft JhengHei UI", 10),
            bg=BG,
            fg=MUTED,
        ).pack(side="left", padx=(10, 0), pady=(7, 0))

        self.updated_label = tk.Label(
            header,
            text="尚未更新",
            font=("Microsoft JhengHei UI", 9),
            bg=BG,
            fg=MUTED,
        )
        self.updated_label.pack(side="right", pady=(7, 0))

        toolbar = tk.Frame(self.root, bg=BG)
        toolbar.pack(fill="x", padx=20, pady=(2, 2))
        self.refresh_button = tk.Button(
            toolbar,
            text="重新整理",
            command=self.refresh_async,
            font=("Microsoft JhengHei UI", 9, "bold"),
            bg=ACCENT,
            fg="#0b1020",
            activebackground="#8bb0ff",
            activeforeground="#0b1020",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
        )
        self.refresh_button.pack(side="left")
        tk.Button(
            toolbar,
            text="設定",
            command=self._open_settings,
            font=("Microsoft JhengHei UI", 9),
            bg=CARD_ALT,
            fg=TEXT,
            activebackground="#2b3240",
            activeforeground=TEXT,
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        self.tray_hint = tk.Label(
            toolbar,
            text="",
            font=("Microsoft JhengHei UI", 8),
            bg=BG,
            fg=MUTED,
        )
        self.tray_hint.pack(side="right")

        container = tk.Frame(self.root, bg=BG)
        container.pack(fill="both", expand=True)
        self.cards: dict[str, DeviceCard] = {}
        for snapshot in self.service.snapshots:
            card = DeviceCard(container, snapshot)
            self.cards[snapshot.key] = card

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=20, pady=(0, 8))
        self.footer = tk.Label(
            footer,
            text="",
            font=("Microsoft JhengHei UI", 8),
            bg=BG,
            fg=MUTED,
            justify="left",
            anchor="w",
        )
        self.footer.pack(fill="x")

    # -- refresh ------------------------------------------------------
    def refresh_async(self) -> None:
        if self._refreshing or self._closing:
            return
        self._refreshing = True
        self.refresh_button.config(state="disabled", text="讀取中…")
        threading.Thread(target=self._refresh_worker, name="PeripheralDockRefresh", daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            snapshots = self.service.refresh()
            self._queue.put(("refreshed", snapshots))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("failed", f"{type(exc).__name__}: {exc}"))

    def _on_refreshed(self, snapshots: list[DeviceSnapshot]) -> None:
        self._refreshing = False
        self.refresh_button.config(state="normal", text="重新整理")
        for snapshot in snapshots:
            card = self.cards.get(snapshot.key)
            if card:
                card.update(snapshot)
        self.updated_label.config(text=f"更新於 {datetime.now().strftime('%H:%M:%S')}")
        self.notifier.threshold = self.config.low_battery_threshold
        self.notifier.enabled = self.config.notifications_enabled
        self.notifier.process(snapshots)
        self._update_footer()
        self._schedule_refresh()

    def _on_refresh_failed(self, message: str) -> None:
        self._refreshing = False
        self.refresh_button.config(state="normal", text="重新整理")
        self.updated_label.config(text="更新失敗")
        messagebox.showerror("刷新失敗", message, parent=self.root)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._closing:
            return
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(
            self.config.poll_interval_seconds * 1000, self.refresh_async
        )

    def _update_footer(self) -> None:
        threshold = self.config.low_battery_threshold
        interval = self.config.poll_interval_seconds
        startup = autostart.autostart_status()
        tray = "系統匣可用" if self._tray_available else "系統匣不可用，關閉視窗即結束"
        self.footer.config(
            text=(
                f"低電量 {threshold}% · 每 {interval} 秒更新 · "
                f"開機啟動：{startup} · {tray}　（未知或過期資料不通知）"
            )
        )

    # -- tray / notifications ----------------------------------------
    def _start_tray(self) -> None:
        try:
            self._tray = TrayIcon(lambda: self._queue.put(("show", None)))
            self._tray.start()
            self._tray_available = True
            self.tray_hint.config(text="點擊系統匣圖示可開啟視窗")
        except TrayUnavailable:
            self._tray_available = False
            self.tray_hint.config(text="系統匣不可用（無 Explorer）")
        except Exception:
            self._tray_available = False
            self.tray_hint.config(text="系統匣初始化失敗")

    def _notify(self, title: str, message: str) -> None:
        if self._tray_available and self._tray and self._tray.notify(title, message):
            return
        messagebox.showinfo(title, message, parent=self.root)

    def _poll_queue(self) -> None:
        try:
            while True:
                command, payload = self._queue.get_nowait()
                if command == "show":
                    self.show_window()
                elif command == "refreshed":
                    self._on_refreshed(payload)  # type: ignore[arg-type]
                elif command == "failed":
                    self._on_refresh_failed(str(payload))
        except queue.Empty:
            pass
        if not self._closing:
            self.root.after(150, self._poll_queue)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    # -- settings -----------------------------------------------------
    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("設定")
        dialog.configure(bg=BG)
        dialog.geometry("420x360")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="PeripheralDock 設定",
            font=("Microsoft JhengHei UI", 14, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(anchor="w", padx=20, pady=(18, 12))

        form = tk.Frame(dialog, bg=BG)
        form.pack(fill="x", padx=20)

        tk.Label(form, text="低電量門檻（%）", bg=BG, fg=TEXT, font=("Microsoft JhengHei UI", 9)).grid(
            row=0, column=0, sticky="w", pady=8
        )
        threshold = tk.IntVar(value=self.config.low_battery_threshold)
        ttk.Spinbox(form, from_=1, to=99, textvariable=threshold, width=8).grid(
            row=0, column=1, sticky="w", padx=(16, 0)
        )

        tk.Label(form, text="更新間隔（秒）", bg=BG, fg=TEXT, font=("Microsoft JhengHei UI", 9)).grid(
            row=1, column=0, sticky="w", pady=8
        )
        interval = tk.IntVar(value=self.config.poll_interval_seconds)
        ttk.Spinbox(form, from_=15, to=3600, increment=15, textvariable=interval, width=8).grid(
            row=1, column=1, sticky="w", padx=(16, 0)
        )

        notifications = tk.BooleanVar(value=self.config.notifications_enabled)
        tk.Checkbutton(
            form,
            text="啟用低電量通知",
            variable=notifications,
            bg=BG,
            fg=TEXT,
            selectcolor=CARD,
            activebackground=BG,
            activeforeground=TEXT,
            font=("Microsoft JhengHei UI", 9),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 2))

        launch = tk.BooleanVar(value=autostart.is_enabled())
        tk.Checkbutton(
            form,
            text="Windows 開機時自動啟動（目前使用者，免管理員）",
            variable=launch,
            bg=BG,
            fg=TEXT,
            selectcolor=CARD,
            activebackground=BG,
            activeforeground=TEXT,
            font=("Microsoft JhengHei UI", 9),
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 2))

        note = tk.Label(
            dialog,
            text="開機啟動預設關閉，只寫入 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。",
            font=("Microsoft JhengHei UI", 8),
            bg=BG,
            fg=MUTED,
            wraplength=380,
            justify="left",
        )
        note.pack(anchor="w", padx=20, pady=(12, 0))

        buttons = tk.Frame(dialog, bg=BG)
        buttons.pack(fill="x", padx=20, pady=18, side="bottom")

        def save() -> None:
            try:
                new_config = AppConfig(
                    low_battery_threshold=int(threshold.get()),
                    poll_interval_seconds=int(interval.get()),
                    notifications_enabled=bool(notifications.get()),
                    autostart_enabled=bool(launch.get()),
                    start_minimized=self.config.start_minimized,
                )
                autostart.set_enabled(new_config.autostart_enabled)
                save_config(new_config, self.config_path)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("設定儲存失敗", str(exc), parent=dialog)
                return
            self.config = new_config
            self.notifier.threshold = new_config.low_battery_threshold
            self.notifier.enabled = new_config.notifications_enabled
            self._schedule_refresh()
            self._update_footer()
            dialog.destroy()

        tk.Button(
            buttons,
            text="取消",
            command=dialog.destroy,
            font=("Microsoft JhengHei UI", 9),
            bg=CARD_ALT,
            fg=TEXT,
            relief="flat",
            padx=14,
            pady=6,
        ).pack(side="right")
        tk.Button(
            buttons,
            text="儲存",
            command=save,
            font=("Microsoft JhengHei UI", 9, "bold"),
            bg=ACCENT,
            fg="#0b1020",
            relief="flat",
            padx=14,
            pady=6,
        ).pack(side="right", padx=(0, 8))

    # -- shutdown -----------------------------------------------------
    def _on_close(self) -> None:
        if self._tray_available and self._tray:
            self.root.withdraw()
            return
        if messagebox.askyesno(
            "結束 PeripheralDock",
            "此環境沒有可用的系統匣圖示。關閉視窗會結束程式，要繼續嗎？",
            parent=self.root,
        ):
            self.quit()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
        if self._tray is not None:
            self._tray.stop()
        self.service.close()
        self.root.destroy()


def run_ui(config: AppConfig, config_path: Path, start_minimized: bool = False) -> None:
    root = tk.Tk()
    PeripheralDockApp(root, config, config_path, start_minimized=start_minimized)
    root.mainloop()
