# PeripheralDock

A Windows tray utility that reports **only battery values it can actually read** from the target peripherals:

- Redmi Buds 4 Active
- Rapoo E1050
- Logitech M235

Unknown values are `None`. Unsupported devices show **“Battery not readable”**. The app never substitutes `100%`, an estimate, or stale data for a live reading.

![PeripheralDock UI](docs/evidence/ui-preview.png)

## Verified status (2026-11-01)

| Device | Status | Result on the test machine |
|---|---|---|
| Redmi Buds 4 Active | Unsupported (this machine) | Classic Bluetooth is connected, but Windows exposes no BLE/GATT object; no `0x180F` battery service |
| Rapoo E1050 | Unsupported (this machine) | No HID Battery Strength usage and no public Rapoo battery protocol; exact E1050 model string not confirmed |
| Logitech M235 | **Verified readable** | HID++ 2.0 `BATTERY_STATUS (0x1000)` → **70%**, not charging |

The test environment is **Windows 10 IoT Enterprise LTSC 2021 (build 19044)**, not Windows 11. See [DEVICE_SUPPORT.md](DEVICE_SUPPORT.md) for the full evidence. Anything not tested on real hardware is marked as pending verification.

## Features

- Three device cards: headset / keyboard / mouse
- Verified battery percentage and progress bar
- Reading states: `ok`, `unsupported`, `offline`, `stale`, `error`
- Low-battery notification (default threshold 20%; only live, online, non-stale readings)
- System tray icon using native `Shell_NotifyIcon` (no `pystray` dependency); falls back to a normal window when no Explorer shell is available
- Manual refresh, automatic polling, persisted settings
- Optional per-user Windows startup via HKCU (off by default, no administrator rights)
- Traditional Chinese UI
- Read-only hardware probing: no keyboard input capture and no firmware changes

## Requirements

- Windows 10 19041+ / Windows 11 (tested on 19044)
- Python 3.10+ (3.11 recommended; tested with 3.12.14)
- Standard library only; `tkinter` must be included with Python
- No administrator rights required

## Install and run

```powershell
cd PeripheralDock
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py run
```

Or:

```powershell
.\run.ps1
```

### CLI

```powershell
# Read-only probe, writes JSON evidence
python main.py probe --json docs/evidence/probe-20261101.json

# Read once and print the result
python main.py once

# Start the UI (optionally hidden to tray)
python main.py run --minimized

# Per-user startup management
python main.py autostart status
python main.py autostart enable
python main.py autostart disable
```

## Configuration

Config file: `%APPDATA%\PeripheralDock\config.json`

| Field | Default | Description |
|---|---|---|
| `low_battery_threshold` | 20 | Notify when the percentage is at or below this value |
| `poll_interval_seconds` | 60 | Automatic refresh interval (15–3600) |
| `notifications_enabled` | true | Enable low-battery notifications |
| `autostart_enabled` | false | Per-user startup; writes only HKCU Run |
| `start_minimized` | true | Start hidden in the system tray |

## Tray and notifications

- Uses Win32 `Shell_NotifyIconW`; no `pystray` dependency.
- Clicking the tray icon opens or restores the main window.
- If the current session has no Explorer shell (for example, a remote service session), `Shell_NotifyIcon` fails. The UI reports “system tray unavailable”, and closing the window exits the app.
- Notifications use a tray balloon first and fall back to a message box.

**Pending verification:** this development session had no Explorer tray, so clicking the icon could not be tested. The native tray code is implemented and needs validation on a normal Windows desktop session.

## Battery data contract

`read_battery()` returns a `BatteryReading`:

| Field | Rule |
|---|---|
| `percentage` | Integer `0–100`, or `None` |
| `charging` | `True`, `False`, or `None` |
| `status` | `ok`, `unsupported`, `offline`, `stale`, or `error` |
| `source` | The protocol actually used, e.g. `logitech-hidpp2:0x1000` |
| `timestamp` | Time of the last successful read |
| `error_message` | Human-readable failure reason |

- After a failed read, a last-good value is returned as `stale` with its original timestamp; the UI marks it as expired.
- `unsupported` is never overwritten by cached data.
- Low-battery notifications require `status=ok` and `connection=connected`.

## Project layout

```text
PeripheralDock/
  DEVICE_SUPPORT.md       Hardware test report
  IMPLEMENTATION_PLAN.md  Implementation plan
  TEST_PLAN.md            Test plan
  TEST_RESULTS.md         Actual test results
  README.md
  main.py                 Development entry point
  run.ps1 / build.ps1
  src/peripheraldock/
    adapters/             redmi / rapoo / logitech
    windows/              setupapi / hid / hidpp / bluetooth
    service.py            Polling and snapshots
    notifications.py      Low-battery policy
    tray.py               Native system tray
    ui.py                 Tkinter UI
    autostart.py          HKCU Run entry
    config.py             JSON settings
    cli.py                probe / once / run
  tools/
    probe_hardware.py     Standalone read-only probe
    winrt_probe.ps1       WinRT classic / BLE / GATT evidence
  tests/                  unittest, 43 tests
  docs/evidence/          JSON evidence and screenshot
```

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

See [TEST_RESULTS.md](TEST_RESULTS.md). Current result: **42 passed, 1 skipped**. The skipped test writes a real HKCU startup entry; the development sandbox denied registry writes.

## Build a Windows executable

PyInstaller is needed only for building:

```powershell
python -m pip install pyinstaller
.\build.ps1
```

Output:

```text
dist\PeripheralDock\PeripheralDock.exe
```

`build.ps1` uses `--windowed --name PeripheralDock --paths src main.py` and requires no administrator rights. For a single-file build:

```powershell
.\build.ps1 -OneFile
```

> PyInstaller was not available in this development environment, so no `.exe` was produced here. The build flow and arguments are in `build.ps1`; run it on a Windows machine where build tools can be installed.

## Safety and privacy

- Does not read keyboard input; only HID descriptors and HID++ replies.
- Does not send HID writes to unknown devices; Logitech receives read-only feature requests only.
- Does not modify firmware, pair/unpair devices, or change device settings.
- Does not require administrator rights; startup is written only to the current user's HKCU.
- The application makes no network requests.
- Third-party reference: Solaar (GPL-2.0-or-later) was used for protocol research only; no code was copied. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Data sources and acknowledgements

This project was possible thanks to the following public documentation, protocol references, and community work. Thanks to all authors and maintainers. All trademarks and copyrights belong to their respective owners.

| Source | Used for | License / note |
|---|---|---|
| [pwr-Solaar/Solaar](https://github.com/pwr-Solaar/Solaar) | Cross-checking Logitech HID++ 2.0 framing, `BATTERY_STATUS(0x1000)` / `UNIFIED_BATTERY(0x1004)` fields, and M235 WPID `4055` | GPL-2.0-or-later; this project **does not copy or link its code**, only reimplements the observed protocol behavior |
| [Solaar devices.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/devices.md) | M235 WPID and HID++ generation | Same as above |
| [Solaar hidpp20.py](https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/hidpp20.py) | HID++ feature request and battery response format reference | Same as above |
| [Microsoft Learn: BluetoothLEDevice](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.bluetoothledevice) | Windows Bluetooth LE object and GATT queries | Microsoft documentation |
| [Microsoft Learn: GATT Battery Service](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattdeviceservice) | Standard `0x180F` / `0x2A19` battery service | Microsoft documentation |
| [USB-IF HID Usage Tables 1.12](https://usb.org/document-library/hid-usage-tables-112) | Generic Device Controls `0x06` and Battery Strength `0x20` detection | USB-IF specification |
| [SgZincanya/ChargeDock](https://github.com/SgZincanya/ChargeDock) | Product reference for a tray-first utility, per-user startup, and hardware state separation | Reference project; no code copied |
| [Redmi Buds 4 Active FAQ](https://www.mi.com/de/support/faq/details/KA-50604/) | Redmi headset features and connection background | Xiaomi official FAQ |
| [Rapoo E1050 product page](https://www.rapoo.com/ru/product/E1050) | Rapoo E1050 specifications and model background | Rapoo official product page |
| [SpartanX1/bluetooth_classic_battery_windows](https://github.com/SpartanX1/bluetooth_classic_battery_windows) | Research on RFCOMM / `AT+IPHONEACCEV` battery reporting for classic Bluetooth headsets | Background only; not used, to avoid taking over the audio channel |
| [Microsoft Q&A: Bluetooth battery level](https://learn.microsoft.com/en-us/answers/questions/32945/is-there-any-way-can-get-the-bluetooth-battery-lev) | Confirming Windows has no public classic-Bluetooth headset battery query API | Microsoft Q&A discussion |

Special thanks:

- **The pwr-Solaar community** for public HID++ implementation and device data, which allowed M235 WPID, feature index, and battery fields to be cross-checked.
- **Microsoft Learn / Windows developer documentation** for official WinRT, GATT, HID, and SetupAPI behavior.
- **USB-IF** for maintaining the HID Usage Tables, giving Battery Strength a standards-based definition.
- **SgZincanya/ChargeDock** as a product reference for a tray-first peripheral battery tool, especially the principles of “show only verifiable data” and “handle each device separately”.
- The hardware vendors **Redmi / Rapoo / Logitech** for product documentation, and all open-source contributors who documented protocol observations.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the full third-party attribution.

## License

Original project code is released under the MIT License. Third-party components and references are described in `THIRD_PARTY_NOTICES.md`.

---

# 繁體中文

## 專案簡介

PeripheralDock 是常駐 Windows 系統匣的周邊電量工具，目標硬體為 Redmi Buds 4 Active、Rapoo E1050 與 Logitech M235。

核心原則：**只顯示實際讀取到的電量。** 未知就是 `None`；不支援就顯示「電量不可讀取」；不用 `100%`、估算值或過期資料冒充即時電量。

![PeripheralDock UI](docs/evidence/ui-preview.png)

## 目前實測狀態（2026-11-01）

| 設備 | 狀態 | 本機結果 |
|---|---|---|
| Redmi Buds 4 Active | 不支援（本機） | 經典藍牙已連線，但 Windows 未建立 BLE/GATT 物件；沒有可讀的 `0x180F` |
| Rapoo E1050 | 不支援（本機） | HID descriptor 無 Battery Strength；沒有公開的 Rapoo 電量協定；裝置字串未確認為 E1050 |
| Logitech M235 | **已驗證可讀取** | HID++ 2.0 `BATTERY_STATUS (0x1000)` → **70%**，未充電 |

實測環境是 **Windows 10 IoT Enterprise LTSC 2021（19044）**，不是 Windows 11。完整證據見 [DEVICE_SUPPORT.md](DEVICE_SUPPORT.md)。沒有真機測試的欄位都標為待驗證。

## 功能

- 三張設備卡：耳機 / 鍵盤 / 滑鼠
- 可驗證的電量百分比與進度條
- 讀取狀態：`ok` / `unsupported` / `offline` / `stale` / `error`
- 低電量通知（預設 20%，只在實際有效、在線、未過期時觸發）
- 原生 `Shell_NotifyIcon` 系統匣圖示；沒有 Explorer 時退回視窗模式
- 手動刷新、自動輪詢、設定保存
- 可選的目前使用者開機啟動（HKCU，預設關閉，免管理員）
- 繁體中文介面
- 全程唯讀硬體探測；不擷取鍵盤輸入、不修改韌體

## 系統需求

- Windows 10 19041+ / Windows 11（實測 19044）
- Python 3.10+（建議 3.11；實測 3.12.14）
- 標準函式庫即可執行；`tkinter` 需隨 Python 安裝
- 不需要管理員權限

## 安裝與執行

```powershell
cd PeripheralDock
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py run
```

或：

```powershell
.\run.ps1
```

### CLI

```powershell
# 唯讀探測，輸出 JSON 證據
python main.py probe --json docs/evidence/probe-20261101.json

# 讀取一次並顯示
python main.py once

# 啟動 UI（可加 --minimized）
python main.py run --minimized

# 開機啟動管理
python main.py autostart status
python main.py autostart enable
python main.py autostart disable
```

## 設定

設定檔：`%APPDATA%\PeripheralDock\config.json`

| 欄位 | 預設 | 說明 |
|---|---|---|
| `low_battery_threshold` | 20 | 電量等於或低於此值時通知 |
| `poll_interval_seconds` | 60 | 自動刷新間隔（15–3600） |
| `notifications_enabled` | true | 低電量通知開關 |
| `autostart_enabled` | false | 開機啟動；只寫 HKCU Run |
| `start_minimized` | true | 啟動時隱藏到系統匣 |

## 系統匣與通知

- 使用 Win32 `Shell_NotifyIconW`，不需要 `pystray`。
- 點擊圖示會開啟/喚回主視窗。
- 若目前工作階段沒有 Explorer（例如遠端服務工作階段），`Shell_NotifyIcon` 會失敗；UI 會標示「系統匣不可用」，關閉視窗即結束。
- 通知優先用系統匣 balloon；沒有系統匣時退回對話框。

**待驗證：** 本開發工作階段沒有 Explorer 系統匣，無法實際點擊圖示；程式碼已完成，需在一般 Windows 桌面工作階段驗證。

## 電量資料規則

`read_battery()` 回傳 `BatteryReading`：

| 欄位 | 規則 |
|---|---|
| `percentage` | 0–100 整數或 `None` |
| `charging` | `True` / `False` / `None` |
| `status` | `ok` / `unsupported` / `offline` / `stale` / `error` |
| `source` | 實際協定，例如 `logitech-hidpp2:0x1000` |
| `timestamp` | 最後成功讀取時間 |
| `error_message` | 失敗原因 |

- 讀取失敗後若有 last-good，會回 `stale` 並保留時間戳，UI 標示「過期」。
- `unsupported` 不會被舊資料覆蓋。
- 低電量通知只接受 `status=ok` 且 `connection=connected`。

## 專案結構

```text
PeripheralDock/
  DEVICE_SUPPORT.md       硬體實測報告
  IMPLEMENTATION_PLAN.md  實作計畫
  TEST_PLAN.md            測試計畫
  TEST_RESULTS.md         實測結果
  README.md
  main.py                 開發入口
  run.ps1 / build.ps1
  src/peripheraldock/
    adapters/             redmi / rapoo / logitech
    windows/              setupapi / hid / hidpp / bluetooth
    service.py            輪詢與快照
    notifications.py      低電量政策
    tray.py               原生系統匣
    ui.py                 Tkinter UI
    autostart.py          HKCU Run
    config.py             JSON 設定
    cli.py                probe / once / run
  tools/
    probe_hardware.py     獨立唯讀探測
    winrt_probe.ps1       WinRT 經典藍牙 / BLE / GATT 證據
  tests/                  unittest，43 個測試
  docs/evidence/          JSON 與截圖
```

## 測試

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

結果見 [TEST_RESULTS.md](TEST_RESULTS.md)。目前 **42 個測試通過，1 個跳過**；跳過的是 HKCU 開機啟動實際寫入測試，因開發沙箱拒絕登錄檔寫入。

## 建置 Windows 可執行檔

需要 PyInstaller（僅建置時需要）：

```powershell
python -m pip install pyinstaller
.\build.ps1
```

輸出：

```text
dist\PeripheralDock\PeripheralDock.exe
```

`build.ps1` 使用 `--windowed --name PeripheralDock --paths src main.py`，不需要管理員權限。若要單檔：

```powershell
.\build.ps1 -OneFile
```

> 本開發環境沒有安裝 PyInstaller，因此未實際產出 `.exe`；流程與參數已寫入 `build.ps1`，需在可安裝建置工具的 Windows 機器執行。

## 安全與隱私

- 不讀取鍵盤按鍵內容；只讀 HID descriptor 與 HID++ 回應。
- 不對未知裝置發送 HID 寫入；Logitech 只發送唯讀 feature request。
- 不修改韌體、不配對/解除配對、不改裝置設定。
- 不要求管理員權限；開機啟動只寫目前使用者 HKCU。
- 應用程式不發送網路請求。
- 第三方參考：Solaar（GPL-2.0-or-later）只用於協定研究，未複製程式碼；詳見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 資料來源與致謝

本專案能完成，主要來自以下公開資料、協定文件與社群實作。感謝各專案作者與維護者；所有商標與著作權屬於各自所有者。

| 資料來源 | 用途 | 授權／備註 |
|---|---|---|
| [pwr-Solaar/Solaar](https://github.com/pwr-Solaar/Solaar) | 交叉驗證 Logitech HID++ 2.0 訊息框架、`BATTERY_STATUS(0x1000)` / `UNIFIED_BATTERY(0x1004)` 欄位、M235 WPID `4055` | GPL-2.0-or-later；本專案**沒有複製或連結其程式碼**，只依協定行為重新實作 |
| [Solaar devices.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/devices.md) | M235 的 WPID 與 HID++ 世代對照 | 同上 |
| [Solaar hidpp20.py](https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/hidpp20.py) | HID++ feature request 與電池回應格式參考 | 同上 |
| [Microsoft Learn: BluetoothLEDevice](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.bluetoothledevice) | Windows 藍牙 LE 物件與 GATT 查詢 | Microsoft 文件 |
| [Microsoft Learn: GATT Battery Service](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattdeviceservice) | `0x180F` / `0x2A19` 標準 Battery Service | Microsoft 文件 |
| [USB-IF HID Usage Tables 1.12](https://usb.org/document-library/hid-usage-tables-112) | Generic Device Controls `0x06`、Battery Strength `0x20` 的判定 | USB-IF 文件 |
| [SgZincanya/ChargeDock](https://github.com/SgZincanya/ChargeDock) | 系統匣優先、使用者範圍開機啟動、硬體狀態分級的產品參考 | 參考專案；未複製程式碼 |
| [Redmi Buds 4 Active FAQ](https://www.mi.com/de/support/faq/details/KA-50604/) | Redmi 耳機功能與連線方式背景 | 小米官方 FAQ |
| [Rapoo E1050 產品頁](https://www.rapoo.com/ru/product/E1050) | Rapoo E1050 規格與型號背景 | Rapoo 官方產品頁 |
| [SpartanX1/bluetooth_classic_battery_windows](https://github.com/SpartanX1/bluetooth_classic_battery_windows) | 經典藍牙耳機以 RFCOMM / `AT+IPHONEACCEV` 取得電量的研究 | 僅作背景參考；未採用，避免搶占音訊通道 |
| [Microsoft Q&A: Bluetooth battery level](https://learn.microsoft.com/en-us/answers/questions/32945/is-there-any-way-can-get-the-bluetooth-battery-lev) | 確認 Windows 沒有公開的經典藍牙耳機電量查詢 API | Microsoft Q&A 討論 |

特別感謝：

- **pwr-Solaar 社群**公開 HID++ 實作與裝置資料，讓 M235 的 WPID、feature index 與電池欄位可以交叉驗證。
- **Microsoft Learn / Windows 開發文件**提供 WinRT、GATT、HID 與 SetupAPI 的官方行為說明。
- **USB-IF** 維護 HID Usage Tables，讓 Battery Strength 的判定有標準依據。
- **SgZincanya/ChargeDock** 作為系統匣周邊電量工具的產品參考，特別是「只顯示可驗證資料」與「依設備分開處理」的方向。
- 硬體供應商 **Redmi / Rapoo / Logitech** 的產品文件，以及所有在文件中留下協定觀察的開源社群貢獻者。

更完整的第三方授權與引用說明見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 授權

本專案原創程式碼採用 MIT License；第三方元件與參考資料另見 `THIRD_PARTY_NOTICES.md`。
