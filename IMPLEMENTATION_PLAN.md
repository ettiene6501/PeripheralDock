# PeripheralDock 實作計畫

## 1. 目標與原則

建立一個不需要管理員權限、常駐 Windows 系統匣的 Python 桌面工具，顯示 Redmi Buds 4 Active、Rapoo E1050、Logitech M235 的可驗證電量。

核心原則：

1. **先探測，後假設。** 沒有實際回應就不顯示百分比。
2. **未知就是 `None`。** 不用 100%、估算值或快取舊值冒充即時電量。
3. **唯讀優先。** 只讀 descriptor/register/feature；不寫入未知 HID 裝置、不改韌體。
4. **使用者範圍。** 開機啟動使用 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，不要求管理員。
5. **可分級顯示。** 已偵測 / 已連線 / 讀取成功 / 讀取失敗 / 不支援，五種狀態分開。
6. **可測試。** 解析與狀態機以假資料單元測試；硬體層以真機 smoke test 驗證。

## 2. 架構

```text
src/peripheraldock/
  models.py                BatteryReading / DeviceSnapshot / 狀態列舉
  adapters/base.py         DeviceAdapter 介面（discover/get_status/read_battery/
                           get_capabilities/close）
  adapters/redmi.py        Windows Bluetooth 電量來源（WinRT 優先）
  adapters/rapoo.py        SetupAPI/HID 探測，標準 HID Battery 頁面
  adapters/logitech.py     HID++ 唯讀查詢（1.0/2.0）
  windows/setupapi.py      SetupDi* / HID 列舉與 report descriptor 解析
  windows/hid.py           HidD_* / HidP_* 唯讀 wrapper
  windows/bluetooth.py     WinRT/登錄檔藍牙探測；無法使用時明確降級
  registry.py              裝置證據收集（不含鍵盤輸入）
  service.py               輪詢、快取過期、低電量狀態機
  notifications.py         Windows 通知（無額外套件時退回 tray 提示）
  tray.py                  系統匣 + 浮窗（tkinter）
  autostart.py             HKCU Run 啟停
  config.py                JSON 設定（%APPDATA%\PeripheralDock）
  cli.py                   probe / once / run 命令
tests/                     單元測試 + 假 HID 回應
tools/probe_hardware.py    可獨立執行的唯讀硬體探測器
```

### 統一介面

```python
class DeviceAdapter(Protocol):
    def discover(self) -> DiscoveryResult: ...
    def get_status(self) -> DeviceStatus: ...
    def read_battery(self) -> BatteryReading: ...
    def get_capabilities(self) -> Capabilities: ...
    def close(self) -> None: ...
```

`BatteryReading` 欄位：

| 欄位 | 型別 | 規則 |
|---|---|---|
| `percentage` | `int \| None` | 0–100；未知必為 `None` |
| `charging` | `bool \| None` | 未知為 `None` |
| `status` | `ok/unsupported/offline/stale/error` | 見狀態機 |
| `source` | `str` | 例如 `windows-gatt:0x2A19` |
| `timestamp` | `datetime \| None` | 最後**成功**讀取時間 |
| `error_message` | `str \| None` | 失敗原因（繁體中文） |
| `components` | `dict[str, ComponentBattery]` | 耳機/左耳/右耳/充電盒，各自可為 `None` |

## 3. 分階段實作

### Phase 0：證據與文件（本次先做）

- 建立 `DEVICE_SUPPORT.md`、`IMPLEMENTATION_PLAN.md`、`TEST_PLAN.md`。
- 以 PowerShell/登錄檔/SetupAPI 收集 VID/PID、BTHENUM、HID interface。
- 保存原始證據到 `docs/evidence/`。
- 驗收：每個設備都有「已確認/待查證/不支援」狀態，沒有未經實測的「可讀」宣稱。

### Phase 1：唯讀探測原型

- `tools/probe_hardware.py`：
  - SetupAPI 列舉 HID device path、VID/PID、usage page/usage、report lengths。
  - 解析 report descriptor，找 Generic Desktop / Battery Strength（Usage Page 0x06, Usage 0x20）。
  - 嘗試 Logitech HID++ 唯讀 feature/register 查詢。
  - 嘗試 Windows Bluetooth 電量/GATT 查詢。
  - 輸出 JSON 證據（不含任何按鍵內容）。
- 驗收：三款設備各有一份實際 JSON 結果；失敗要有 Win32 錯誤碼/原因。

### Phase 2：Adapters

- `RedmiAdapter`：Windows 電量屬性 → GATT 0x180F/0x2A19 → 廣播被動觀察；全部失敗回 `unsupported`/`offline`，保留介面。
- `RapooAdapter`：SetupAPI 找鍵盤/接收器；HID Battery Strength；沒有就 `unsupported`。不執行廠商寫入。
- `LogitechAdapter`：先確認 HID++ 通道，再唯讀查詢；成功才解析百分比；失敗回具體原因。
- 每個 adapter 完成後先跑單元測試，再跑真機探測。

### Phase 3：服務與狀態機

- 輪詢間隔預設 60 秒；快取超過 3 分鐘標 `stale`。
- 低電量門檻預設 20%；只在 `ok` + 在線 + 未過期 + 電量 ≤ 門檻時觸發，且同一電量只通知一次。
- 裝置 `unsupported` 絕不觸發通知。
- 支援手動刷新與 last-good 顯示（標示「資料過期」）。

### Phase 4：UI / 系統匣

- tkinter 浮窗：三張設備卡、進度條、狀態文字、重新整理、設定。
- 系統匣：使用 `pystray` 若可用；否則以 `--window` 模式仍可完整操作（不假裝有 tray）。
- 設定：低電量門檻、輪詢間隔、開機啟動、通知開關。
- 繁體中文文案；不支援時顯示「電量不可讀取」。

### Phase 5：打包與交付

- `build.ps1`：PyInstaller one-folder/one-file，`--windowed`，圖示可選。
- 文件：安裝、執行、限制、測試結果、建置流程。
- 驗收：`python -m pytest` 全綠；`probe_hardware.py --json` 可重現；UI 可啟動。

## 4. 風險與對策

| 風險 | 對策 |
|---|---|
| OS 是 Windows 10 而非 11 | 文件標明；WinRT API 以可用性探測，不硬假設 |
| Python 3.12 而非 3.11 | 型別語法維持 3.10+；文件註明 |
| 沒有 WinRT Python 套件 | 以 PowerShell 5.1/WinRT 或 C# 小工具探測；Adapter 找不到時明確 `unsupported` |
| 接收器有多個 HID collection | 用 usage page/usage + report descriptor 選取，不靠猜測 |
| Logitech 是 HID++ 1.0 而非 2.0 | 兩種唯讀路徑都實作；以實際回應決定 |
| Rapoo 無標準 battery page | 直接 `unsupported`，不做估算 |
| 通知 API 不可用 | 退回 tray balloon/視窗提示，不影響核心資料 |

## 5. 完成定義（Definition of Done）

- [x] 三個 adapter 都實作五個介面方法。
- [x] 未知電量永遠 `None`，且有測試覆蓋。
- [x] 五種設備狀態都有 UI 文案與測試。
- [x] 低電量通知只對有效、在線、未過期資料觸發。
- [x] 開機啟動預設關閉，只寫 HKCU；程式與命令組裝完成（沙箱內無法實寫 HKCU，待一般桌面驗證）。
- [x] 真機結果如實寫入 `DEVICE_SUPPORT.md`。
- [x] 測試報告與建置流程可照做重現。
- [ ] 以 PyInstaller 產出 `.exe` 並在無 Python 環境啟動（此環境沒有 PyInstaller）。
- [ ] 一般 Explorer 桌面工作階段的系統匣點擊/通知實測。

## 6. 實作進度（2026-11-01）

| 階段 | 狀態 | 備註 |
|---|---|---|
| Phase 0 文件與證據 | 完成 | 三份文件 + JSON + UI 截圖 |
| Phase 1 唯讀探測 | 完成 | SetupAPI/HID/WinRT/HID++ |
| Phase 2 Adapters | 完成 | Logitech 實測 70%；Redmi/Rapoo unsupported |
| Phase 3 服務與通知 | 完成 | 快取 stale、通知政策、43 測試 |
| Phase 4 UI / 系統匣 | 完成（托盘待桌面驗證） | Tkinter UI 截圖；無 Explorer 時退回視窗 |
| Phase 5 打包 | 流程完成，未產出 exe | 缺 PyInstaller |
