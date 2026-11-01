# PeripheralDock 測試計畫

> 執行結果與原始證據已記錄於 `TEST_RESULTS.md`；本文件保留測試設計與驗收條件。

## 1. 測試層級

| 層級 | 目的 | 執行方式 |
|---|---|---|
| L1 單元測試 | 狀態機、解析器、快取過期、通知條件 | `python -m pytest`，不需要硬體 |
| L2 唯讀硬體探測 | 確認 SetupAPI/HID/Bluetooth 在真機可用 | `python tools/probe_hardware.py --json` |
| L3 Adapter 真機測試 | 每個 adapter 的 discover/read_battery | `python -m peripheraldock.cli probe` |
| L4 UI/系統匣測試 | 顯示、手動刷新、設定保存 | 手動 + 螢幕截圖 |
| L5 打包測試 | 無 Python 環境可啟動 | 乾淨資料夾執行 `.exe` |

## 2. L1 必測案例

### 2.1 資料模型

- [ ] `percentage=None` 時不得變成 0 或 100。
- [ ] `percentage` 超出 0–100 時拒絕，回 `error`。
- [ ] `charging=None` 與 `False` 可區分。
- [ ] `status=unsupported` 時不得有有效百分比。
- [ ] `datetime` 使用本地時區，JSON 輸出含 offset。

### 2.2 快取/過期

- [ ] 讀取成功後快取 timestamp。
- [ ] 超過 TTL 後 `get_status()` 回 `stale`，但保留 last-good 與過期標記。
- [ ] 裝置離線時回 `offline`，不把舊值當即時值。
- [ ] 讀取失敗時不清除 last-good，但標 `error`。

### 2.3 低電量通知

- [ ] 19% + 在線 + `ok` → 觸發一次。
- [ ] 20% + 在線 + `ok` → 觸發（門檻是「等於或低於」20）。
- [ ] `unsupported` + 0% → 不觸發。
- [ ] `stale` → 不觸發。
- [ ] `offline` → 不觸發。
- [ ] 同一裝置同一電量只通知一次；回升後可再次通知。
- [ ] 通知關閉時不觸發。

### 2.4 HID report descriptor 解析

- [ ] 認得 Usage Page 0x06 / Usage 0x20（Battery Strength）。
- [ ] 認得 Feature report 與 Input report 的差異。
- [ ] 不把滑鼠/鍵盤輸入 report 當成電量。
- [ ] 截斷/惡意 descriptor 不崩潰。
- [ ] 只保存 descriptor 結構，不保存按鍵內容。

### 2.5 Logitech HID++

- [ ] 短訊息/長訊息 framing 正確。
- [ ] feature index 查詢失敗 → `unsupported`，不是 0%。
- [ ] 電池回應電壓/百分比邊界（0、100、255）正確。
- [ ] 無回應/timeout → `error` 或 `offline`。
- [ ] 不送出 write/register set 命令（測試用 fake transport 斷言）。

### 2.6 開機啟動

- [ ] 預設關閉。
- [ ] 啟用只寫 `HKCU\...\Run`，值名稱固定。
- [ ] 停用只刪自己的值，不動其他程式。
- [ ] 路徑含空白/引號時正確 quote。

## 3. L2 真機探測清單

執行：

```powershell
python tools/probe_hardware.py --json docs/evidence/probe-YYYYMMDD.json
```

需記錄：

- [ ] OS build、Python 版本、是否管理員。
- [ ] 每個 HID device path、VID/PID、product string、usage page/usage、report ID、input/output/feature byte lengths。
- [ ] report descriptor 是否含 Battery Strength。
- [ ] Logitech HID++ 查詢的 request/response hex（唯讀）。
- [ ] Bluetooth 位址、名稱、BTHENUM 服務、BTHLE 是否存在。
- [ ] GATT 0x180F/0x2A19 查詢結果或錯誤碼。
- [ ] 每個設備的最終狀態與理由。

**禁止：** 不記錄鍵盤按鍵、不送出 HID write、不配對/解除配對、不改裝置設定。

## 4. L3 真機驗收矩陣

| 設備 | 已偵測 | 已連線 | 讀取成功 | 讀取失敗 | 不支援 |
|---|---|---|---|---|---|
| Redmi Buds 4 Active | 是 | 是（WinRT classic） | 否 | 是（無可用來源） | 是 |
| Rapoo E1050 | 是 | 是（鍵盤 HID） | 否 | 否 | 是 |
| Logitech M235 | 是 | 是（HID++ index 1） | **是（70%）** | 否 | 否 |

判定規則：

- 讀取成功：回應可重現、百分比在 0–100、`source` 明確、timestamp 新鮮。
- 讀取失敗：有硬體但 API/協定錯誤；保留錯誤碼。
- 不支援：硬體/接收器明確沒有該能力，或 descriptor 無 battery 且無公開協定。
- 沒有真機的欄位一律標「待驗證」，不得用推測填滿。

## 5. L4 UI 驗收

- [ ] 三分類清單（耳機/鍵盤/滑鼠）都可見。
- [ ] 進度條只在有效百分比時顯示；未知顯示「—」。
- [ ] 狀態文字正確：已偵測/已連線/讀取成功/讀取失敗/不支援。
- [ ] 「電量不可讀取」不出現進度條、不觸發通知。
- [ ] 手動刷新有 loading 與最後更新時間。
- [ ] 設定關閉再開仍保留。
- [ ] 繁體中文無簡體字。
- [ ] 系統匣圖示可開啟/關閉浮窗、結束程式。
- [ ] 120% DPI 與 100% DPI 都可讀。

## 6. L5 打包驗收

- [ ] `build.ps1` 在乾淨環境成功。
- [ ] `dist\PeripheralDock\PeripheralDock.exe` 可啟動。
- [ ] 不需要管理員權限。
- [ ] 不建立網路連線。
- [ ] 設定寫在 `%APPDATA%\PeripheralDock\config.json`。
- [ ] 解除安裝只移除程式資料夾與可選的使用者設定。

## 7. 測試結果記錄格式

每次執行記錄：

```text
日期：
OS：
Python：
指令：
結果：PASS/FAIL
失敗原因：
證據檔案：
```

最終 `TEST_RESULTS.md` 需包含 L1 指令輸出摘要、L2 JSON 證據連結、L3 每設備結論、L4 截圖、L5 建置輸出。
