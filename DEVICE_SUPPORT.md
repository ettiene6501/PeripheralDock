# PeripheralDock 硬體實測報告

> 本文件只記錄「實際在這台機器上觀測到」的結果。沒有真機讀取成功之前，任何設備都不會標記為「已驗證可讀取電量」。
>
> 首次觀測：2026-11-01（Asia/Taipei）
> 最後更新：2026-11-01 16:18
> 證據檔：`docs/evidence/probe-20261101.json`
> UI 截圖：`docs/evidence/ui-preview.png`

## 1. 實測環境與限制

| 項目 | 實測值 | 備註 |
|---|---|---|
| 作業系統 | Windows 10 IoT Enterprise LTSC 2021 | `10.0.19044.7807`，**不是任務指定的 Windows 11** |
| 架構 | x64 | |
| Python | 3.12.14 | 任務優先建議 3.11；程式碼維持 3.10+ 相容 |
| 藍牙服務 | `bthserv` Running | Intel Wireless Bluetooth (USB `8087:0029`) |
| 測試帳號權限 | 一般使用者（非管理員） | 未使用管理員權限 |
| 網路 | 應用程式未發送任何網路請求 | 開發階段查文件不在此限 |

**重要限制：** 實測 OS 與指定環境不同。Windows 10 19044 與 Windows 11 的 Bluetooth WinRT / 通知 / 系統匣行為可能不同；因此本報告的「已確認」只代表本機可重現，不自動代表所有 Windows 11 機器。

### 狀態定義

| 狀態 | 定義 |
|---|---|
| 已確認 | 在本機以指定方法成功取得可驗證資料，且已保存原始回應 |
| 待查證 | 已偵測到硬體或協定線索，但尚未成功讀取，或缺少關鍵識別 |
| 不支援 | 已用可重現的方法確認硬體/接收器不提供該資料，或協定明確拒絕 |
| 未偵測 | 本次執行沒有找到對應硬體 |

「已偵測」不等於「已連線」；「已連線」不等於「可讀取電量」。本文件與程式都分開記錄。

---

## 2. 總覽

| 目標設備 | 本機偵測 | 連線 | 電量讀取 | 目前狀態 | 顯示欄位 |
|---|---|---|---|---|---|
| Redmi Buds 4 Active | 是（BTHENUM，已配對） | 是（WinRT 經典藍牙 `Connected`） | 失敗（無可用來源） | **不支援（本機）** | 「電量不可讀取」 |
| Rapoo E1050 | 是（Rapoo `24AE:2010` 複合接收器 + 鍵盤 HID） | 是（鍵盤 HID 存在） | 失敗（descriptor 無 battery） | **不支援（本機）** | 「電量不可讀取」 |
| Logitech M235 | 是（`046D:C52B` Unifying 接收器 + HID++ 2.0） | 是（device index 1） | **成功：70%** | **已驗證可讀取電量** | `70%`、未充電、進度條 |

> 上表是 2026-11-01 16:14 的實測結果。Logitech 的 70% 是當次讀值，不是固定值。

---

## 3. Redmi Buds 4 Active

### 3.1 識別資料

| 欄位 | 實測值 | 來源 |
|---|---|---|
| 完整裝置名稱 | `Redmi Buds 4 Active` | BTHPORT `Devices\4873cb476268\Name`；BTHENUM 子節點 `FriendlyName` |
| Bluetooth 位址 | `48:73:CB:47:62:68` | BTHPORT `Devices\4873cb476268` |
| 位址類型 | 經典藍牙 Public；`LEAddressType=0` | BTHPORT |
| LMP Version | 12 | BTHPORT；**不得以此推論 GATT** |
| Manufacturer ID | 1602（`0x0642`） | BTHPORT |
| 配對狀態 | 已配對 | `BTHENUM\Dev_4873CB476268` |
| 即時連線 | `Connected` | WinRT `BluetoothDevice.ConnectionStatus`（`tools/winrt_probe.ps1`） |
| 接收器 | 不適用（耳機本體） | |

### 3.2 實際連線方式與 Windows 服務

觀測到的 BTHENUM 服務：

| UUID | 用途 |
|---|---|
| `0000110b` | A2DP Audio Sink |
| `0000110c` | AVRCP Target |
| `0000110e` | AVRCP Controller |
| `0000111e` | Hands-Free（HFP） |
| `00001101` | Serial Port（COM3 / COM4） |
| `0000fd2d` | 廠商/未知服務 |
| `df21fe2c-2515-4fdb-8886-f12c4d67927c` | 廠商/未知服務 |

- **沒有 `BTHLE` 裝置節點。**
- WinRT `BluetoothLEDevice.FromBluetoothAddressAsync(0x4873CB476268)` 回傳 `null`；BLE 裝置列舉結果為空。
- 因此 **Windows 沒有建立可查詢 GATT 的 LE 物件**；`0x180F/0x2A19` 無從讀取。

### 3.3 可用 API 與實測

| API | 用途 | 實測結果 |
|---|---|---|
| WinRT `BluetoothDevice.FromBluetoothAddressAsync` | 經典藍牙物件 | 成功；名稱正確、`ConnectionStatus=Connected` |
| WinRT `BluetoothLEDevice.FromBluetoothAddressAsync` | LE 物件 | **回傳 null** |
| WinRT `GattDeviceService` / `0x180F` | 標準 Battery Service | **無法執行**（沒有 LE 物件） |
| WinRT `0x2A19` ReadValue | Battery Level | **無法執行** |
| WinRT `BluetoothLEAdvertisementWatcher` | 被動廣播 | 未執行（沒有 LE 物件；不影響結論） |
| Windows PnP `System.Devices.BatteryLife` | 系統電量 | AEP 裝置存在，但沒有 battery 屬性 |
| HFP（`0000111e`） | 通話音訊 | 服務存在；Windows 沒有公開應用程式 API 可查詢耳機電量 |
| 廠商協定 | 小米/Redmi 私有 | 未找到公開、可驗證文件 |

### 3.4 標準/廠商協定

- 標準 GATT Battery Service：`0x180F`；Battery Level：`0x2A19`。**本機無法建立 LE 物件，因此沒有讀到。**
- HFP 的 `AT+IPHONEACCEV` 是 Apple 擴充；部分耳機會主動送出，但 Windows 沒有公開 API 讓桌面程式查詢。被動監聽 RFCOMM 可能干擾音訊，且不是可重現的查詢機制，本專案不採用。
- Bluetooth 5.3 / LMP 12 只代表控制器版本，**不是** GATT 電量證據。
- 未找到小米/Redmi 針對此型號的公開 SDK 或 GATT 文件。

### 3.5 官方 SDK / 文件

| 項目 | 結果 |
|---|---|
| 小米官方 SDK | 未找到公開 SDK |
| 官方 GATT 文件 | 未找到 |
| 官方 FAQ | [Redmi Buds 4 Active FAQ（Xiaomi）](https://www.mi.com/de/support/faq/details/KA-50604/) 僅供產品功能參考 |
| 微軟 API | [BluetoothLEDevice](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.bluetoothledevice)、[GATT](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattdeviceservice) |

### 3.6 電量讀取實測

| 嘗試 | 結果 | 原始證據 |
|---|---|---|
| Windows 經典藍牙電量屬性 | 無 `System.Devices.BatteryLife` | 探測 JSON `bluetooth_devices` |
| 建立 LE 物件 | `null` | `winrt_redmi_probe.stdout` |
| 查詢 GATT `0x180F` | 無法執行 | 同上 |
| 讀取 `0x2A19` | 無法執行 | 同上 |
| HFP 電量查詢 | 無公開 API；未主動搶占 RFCOMM | 設計決策，見安全限制 |

**結論：不支援（本機）。** Windows 10 19044 沒有提供這款經典藍牙耳機的可讀取電量來源。Adapter 保留完整介面，回傳 `percentage=None`、`status=unsupported`；**耳機、左耳、右耳、充電盒四個欄位都沒有取得，`components={}`**。UI 顯示「電量不可讀取」，不觸發低電量通知。

> 待查證：Windows 11 較新版本、或耳機韌體在配對後另外開啟 BLE 廣播時，是否會出現 `0x180F`。本專案不會用推測補值；需要另一台機器重跑 `probe` 才能升級狀態。

### 3.7 狀態判定

| 分類 | 內容 |
|---|---|
| 已確認 | 經典藍牙已配對且 `Connected`；BTHENUM 有 A2DP/AVRCP/HFP/SPP；WinRT 沒有 LE 物件；沒有 `System.Devices.BatteryLife` |
| 待查證 | Windows 11 或不同韌體是否會建立 BLE 物件並公開 `0x180F`；HFP 是否會主動送電量事件 |
| 不支援 | 本機目前沒有可查詢的電量來源；Adapter 回 `unsupported` |

> UI 對 Redmi 顯示「已配對／已偵測」，因為 adapter 不把靜態配對/服務紀錄當成即時連線；WinRT 的 `Connected` 是 `probe` 的另行查詢結果，兩者分開記錄。

---

## 4. Rapoo E1050

### 4.1 識別資料

| 欄位 | 實測值 | 來源 |
|---|---|---|
| 完整裝置名稱 | `Rapoo 2.4G Wireless Device` | HID `HidD_GetProductString` |
| USB VID/PID | `24AE:2010` | SetupAPI / 登錄檔 |
| 接收器型號/硬體版本 | 未由裝置字串取得；HID `bcdDevice=0110` | HID attributes |
| 實際連線方式 | 2.4 GHz USB 複合接收器 | HID 介面 |
| 鍵盤 HID | `MI_02` → Usage Page `0x01` / Usage `0x06` | SetupAPI |
| 滑鼠 HID | `MI_00` → Usage Page `0x01` / Usage `0x02` | SetupAPI |
| 多媒體 HID | `MI_01` → `0xFF00:0x000E`、`0x0001:0x0080`、`0x000C:0x0001` | SetupAPI |

> **型號確認限制：** 裝置字串只有 `Rapoo 2.4G Wireless Device`，沒有 `E1050`。因此「E1050」是使用者指定的目標型號，硬體字串只能確認 Rapoo 接收器與鍵盤集合。文件與 UI 不把 product string 冒充成 E1050。

### 4.2 HID 介面與報告長度

| Interface | Usage Page / Usage | Input | Output | Feature | Battery Strength |
|---|---|---|---|---|---|
| `MI_00`（滑鼠） | `0x0001` / `0x0002` | 7 | 0 | 0 | 無 |
| `MI_01&Col01` | `0xFF00` / `0x000E` | 32 | 32 | 0 | 無 |
| `MI_01&Col02` | `0x0001` / `0x0080` | 2 | 0 | 0 | 無 |
| `MI_01&Col03` | `0x000C` / `0x0001` | 3 | 0 | 0 | 無 |
| `MI_02`（鍵盤） | `0x0001` / `0x0006` | 9 | 2 | 0 | 無 |

- 所有集合的 `battery_values` 都是空陣列。
- 沒有 Feature Report；沒有 Generic Device Controls（Usage Page `0x06`）/ Battery Strength（Usage `0x20`）。
- 因此不存在標準 HID 電量報告可讀。

實際鍵盤 DevicePath（節錄）：

```text
\\?\hid#vid_24ae&pid_2010&mi_02#8&62dcf43&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}\kbd
```

完整路徑與所有集合見 `docs/evidence/probe-20261101.json` 的 `hid_devices`。

### 4.3 官方 SDK / 文件

| 項目 | 結果 |
|---|---|
| Rapoo 官方 SDK | 未找到 |
| Rapoo 官方協定文件 | 未找到 |
| 官方產品頁 | [Rapoo E1050 產品頁](https://www.rapoo.com/ru/product/E1050)（僅規格，無電量 API） |

### 4.4 電量讀取實測

| 嘗試 | 結果 | 原始證據 |
|---|---|---|
| SetupAPI 列舉鍵盤/接收器 | 成功 | 探測 JSON `hid_devices` |
| HID report descriptor / value caps 掃描 Battery Strength | 無 | `battery_values: []` |
| 讀取 Feature Report | 無 Feature Report，未執行 | `feature_report_bytes=0` |
| 廠商命令 | **不執行**（無公開協定，避免任意寫入） | 安全限制 |

**結論：不支援（本機）。** 若日後取得 Rapoo 官方協定文件，才可能在獨立 adapter 中新增唯讀查詢；目前不生成假電量、不把按鍵活動或裝置在線狀態當成電量。

### 4.5 狀態判定

| 分類 | 內容 |
|---|---|
| 已確認 | `24AE:2010` 接收器存在；鍵盤 HID `0x01:0x06` 存在；所有 collection 無 Battery Strength；無 Feature Report |
| 待查證 | Product String 未含 `E1050`，型號需實物標籤確認；Rapoo 是否有未公開的廠商協定 |
| 不支援 | 本機沒有標準 HID 電量報告；未取得官方協定，因此 `unsupported` |

---

## 5. Logitech M235

### 5.1 識別資料

| 欄位 | 實測值 | 來源 |
|---|---|---|
| 完整裝置名稱 | `Wireless Mouse`（HID++ DEVICE_NAME） | HID++ feature `0x0005` |
| 目標型號 | **Logitech M235**（WPID `4055`） | HID++ DEVICE_FW_VERSION `0x0003` |
| USB VID/PID | `046D:C52B`（Unifying 接收器） | SetupAPI |
| 接收器 | `USB Receiver`，`bcdDevice=1211` | HID attributes |
| HID++ 介面 | `MI_02&Col02`，Usage Page `0xFF00` / Usage `0x0002`，20-byte | SetupAPI |
| 實際 HID++ DevicePath | `\\?\hid#vid_046d&pid_c52b&mi_02&col02#8&18be37b8&0&0001#{4d1e55b2-f16f-11cf-88cb-001111000030}` | SetupAPI |
| 配對裝置 index | `1` | HID++ ping |
| HID++ 協定 | `4.5` | ping 回應 |
| Unit ID | `A1EA4DA9` | DEVICE_FW_VERSION |
| Model ID | `405500000000` | DEVICE_FW_VERSION；transport bit `0x04` = WPID |
| 實際連線方式 | 2.4 GHz Unifying 接收器 | HID++ |

### 5.2 協定與實作

- 使用 HID++ 2.0 長訊息（report ID `0x11`，20 bytes）。
- 只發送以下唯讀查詢：
  - `ROOT.GetFeature(0x0000)`：取得 feature index。
  - `DEVICE_FW_VERSION(0x0003)`：取得 Unit ID / Model ID / WPID。
  - `DEVICE_NAME(0x0005)`：取得名稱。
  - `BATTERY_STATUS(0x1000)`：讀取電量/充電狀態。
  - 若沒有 `0x1000`，才嘗試 `UNIFIED_BATTERY(0x1004)`；仍沒有才回報 unsupported。
- 沒有實作 register write、pairing、firmware update、LED/DPI 設定。

### 5.3 原始 HID++ 證據

```text
TX 11 01 00 1B 00 00 5A 00 ...   (ping index 1)
RX 11 01 00 1B 04 05 5A 00 ...   -> HID++ 4.5

TX 11 01 00 0B 00 03 00 ...      (ROOT.GetFeature 0x0003)
RX 11 01 00 0B 02 00 01 ...      -> feature index 2

TX 11 01 02 0B 00 ...            (DEVICE_FW_VERSION)
RX 11 01 02 0B 01 A1 EA 4D A9 00 04 40 55 00 ...
                                  -> Unit A1EA4DA9, transport 0x04, WPID 4055

TX 11 01 00 0B 00 05 00 ...      (ROOT.GetFeature 0x0005)
RX 11 01 00 0B 03 00 00 ...      -> feature index 3

TX 11 01 03 0B 00 ...            (DEVICE_NAME length)
RX 11 01 03 0B 0E ...            -> 14 bytes

TX 11 01 03 1B 00 ...            (DEVICE_NAME offset 0)
RX 11 01 03 1B 57 69 72 65 6C 65 73 73 20 4D 6F 75 73 65
                                  -> "Wireless Mouse"

TX 11 01 00 0B 10 00 ...         (ROOT.GetFeature 0x1000)
RX 11 01 00 0B 05 00 00 ...      -> feature index 5

TX 11 01 05 0B 00 ...            (BATTERY_STATUS)
RX 11 01 05 0B 46 05 00 ...      -> 0x46=70%, next=5, status=0x00 (discharging)
```

### 5.4 電量解析與範圍

- `BATTERY_STATUS` 回應：`level`, `next_level`, `status`。
- `level == 0` 依 HID++ 定義視為「未知」，不回傳 0%。
- `status` 有意義值：`0x00` discharging、`0x01` recharging、`0x02` almost full、`0x03` full、`0x04` slow recharge。
- `status` `0x05`（invalid battery）/ `0x06`（thermal error）→ `error`，不顯示百分比。
- 實測：`0x46` → **70%**，`status=0x00` → 未充電。
- 時間戳：最後成功讀取時間；失敗時保留 last-good 並標 `stale`，不當成即時值。

### 5.5 官方 SDK / 文件

| 項目 | 結果 |
|---|---|
| Logitech 官方 HID++ 文件 | 未找到公開完整文件；Solaar 社群文件可用 |
| Solaar 裝置表 | [devices.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/devices.md)：M235 WPID `4055`，HID++ 2.0 |
| Solaar 實作 | [hidpp20.py](https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/hidpp20.py)、[base.py](https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/base.py) |
| 授權 | Solaar 為 GPL-2.0-or-later；本專案只參考協定格式，未複製其程式碼 |

**結論：已驗證可讀取電量（本機）。** WPID `4055` 對應 M235；讀值 70%；命令與解析已整合到 `LogitechMouseAdapter`。仍待驗證：其他 M235 韌體、不同 Unifying 接收器、Windows 11。

### 5.6 狀態判定

| 分類 | 內容 |
|---|---|
| 已確認 | HID++ 2.0 ping 4.5；WPID `4055`；`BATTERY_STATUS` feature index 5；回應 `46 05 00` = 70% |
| 待查證 | 其他 M235 韌體/接收器、Windows 11、休眠喚醒後的回應 |
| 不支援 | 無（本機路徑成功）；若未來特徵消失，會回 `unsupported` 而非假值 |

---

## 6. 跨設備共通結論

1. **只有 Logitech M235 在本機達到「已驗證可讀取電量」**（70%，HID++ `0x1000`）。
2. Redmi 與 Rapoo 都保留 adapter 介面，但回傳 `unsupported`，不生成假電量。
3. 已偵測到的匯流排/協定存在，只能證明裝置存在，不能證明電量可讀。
4. 未知值一律 `percentage=None`；不得以 100% 或估算值代替。
5. 低電量通知只在 `status=ok`、`percentage` 有效、裝置在線且資料未過期時觸發。
6. 系統匣在此執行環境不可用（沒有 Explorer shell）；原生 `Shell_NotifyIcon` 實作已完成，但需在一般桌面工作階段驗證。

## 7. 參考資料

- [Microsoft Windows.Devices.Bluetooth](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth)
- [Microsoft GATT Battery Service](https://learn.microsoft.com/uwp/api/windows.devices.bluetooth.genericattributeprofile.gattdeviceservice)
- [USB HID Usage Tables](https://usb.org/document-library/hid-usage-tables-112)
- [Solaar](https://github.com/pwr-Solaar/Solaar)
- [Solaar devices.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/devices.md)
- [Rapoo E1050 產品頁](https://www.rapoo.com/ru/product/E1050)
- [Redmi Buds 4 Active FAQ](https://www.mi.com/de/support/faq/details/KA-50604/)
- [Windows 10 Bluetooth Classic Battery Level（RFCOMM 參考）](https://github.com/SpartanX1/bluetooth_classic_battery_windows)
