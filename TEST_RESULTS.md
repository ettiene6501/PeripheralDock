# PeripheralDock 測試結果

> 執行日期：2026-11-01（Asia/Taipei）
> 環境：Windows 10 IoT Enterprise LTSC 2021 `10.0.19044.7807` x64
> Python：3.12.14
> 權限：一般使用者（非管理員）

## 1. 單元測試（L1）

指令：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

結果：

```text
Ran 43 tests in 0.017s
OK (skipped=1)
```

| 測試檔 | 內容 | 結果 |
|---|---|---|
| `test_models.py` | `None` 規則、0–100 邊界、ok/unsupported 驗證、timestamp | PASS |
| `test_cache.py` | 成功快取、失敗轉 stale、unsupported 不覆蓋舊值、例外轉 error | PASS |
| `test_hidpp.py` | ping 4.5、70%/充電/錯誤 status、0% 視為未知、WPID 4055、名稱、唯讀 trace | PASS |
| `test_notifications.py` | 19% 通知、20% 通知、21% 不通知、unsupported/stale/offline/未連線/停用不通知、回升後再通知 | PASS |
| `test_config.py` | 預設值、clamp、JSON round-trip、損壞檔、未知欄位 | PASS |
| `test_autostart.py` | 路徑引號、frozen/dev 命令；HKCU 實際寫入 | 4 PASS，1 SKIP（沙箱禁止 HKCU 寫入） |

跳過原因：DSH 沙箱在此工作階段拒絕 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 寫入（WinError 5）。這是環境限制，不是程式錯誤；需在一般桌面工作階段重跑 `test_real_hkcu_entry_round_trip` 或 `python main.py autostart enable` 驗證。

## 2. 硬體探測（L2）

指令：

```powershell
python main.py probe --json docs/evidence/probe-20261101.json
```

輸出檔：`docs/evidence/probe-20261101.json`（含 HID descriptor、Bluetooth 服務、HID++ trace、WinRT 結果）。

### 2.1 系統與權限

| 項目 | 結果 |
|---|---|
| Windows build | `10.0.19044` |
| 管理員 | false |
| HID 介面 | 18 個 present HID；目標廠牌 14 個 |
| 藍牙 | `bthserv` Running；Intel `8087:0029` |
| 網路 | 應用程式未發送請求 |

### 2.2 HID 目標裝置

- Logitech `046D:C52B`：鍵盤、滑鼠、consumer、vendor-defined、HID++ short/long。
- Rapoo `24AE:2010`：滑鼠、多媒體、鍵盤；Product String `Rapoo 2.4G Wireless Device`。
- 兩者都**沒有** Generic Device Controls `0x06` / Battery Strength `0x20` value cap。
- Logitech 的 20-byte `0xFF00:0x0002` 介面是實際 HID++ 2.0 通道；32-byte `0xFF00:0x0004` 不適用。

### 2.3 Bluetooth / Redmi

| 檢查 | 結果 |
|---|---|
| BTHENUM 配對 | `Redmi Buds 4 Active` / `48:73:CB:47:62:68` |
| 經典藍牙 WinRT | `Connected` |
| BTHLE 節點 | 無 |
| `BluetoothLEDevice` | `null` |
| BLE 裝置列舉 | 空 |
| GATT `0x180F` / `0x2A19` | 無法執行 |
| Windows battery 屬性 | 無 |
| BTHENUM 服務 | A2DP/AVRCP/HFP/SPP/廠商 |

## 3. Adapter 真機測試（L3）

| 設備 | 已偵測 | 已連線 | 讀取成功 | 讀取失敗 | 不支援 | 結論 |
|---|---|---|---|---|---|---|
| Redmi Buds 4 Active | 是 | 是（WinRT classic） | 否 | 是（無來源） | 是 | `unsupported`，`percentage=None` |
| Rapoo E1050 | 是 | 是（鍵盤 HID） | 否 | 否 | 是 | `unsupported`，`percentage=None` |
| Logitech M235 | 是 | 是（index 1） | **是** | 否 | 否 | **`70%`，未充電** |

Logitech 原始讀值：

```text
TX 11 01 05 0B 00 ...
RX 11 01 05 0B 46 05 00 ...
```

`0x46` = 70%，`0x05` = next level，`0x00` = discharging。WPID 由 `DEVICE_FW_VERSION` 確認為 `4055`（M235）。

重複讀取 3 次（間隔 1 秒）皆為 `70%`、`charging=false`、`status=ok`，時間戳逐次更新，沒有把舊值當新值。

## 4. UI 測試（L4）

- `python main.py run` 可啟動；實測截圖：`docs/evidence/ui-preview.png`。
- 三張卡片完整顯示：
  - Redmi：「已配對／已偵測 · 硬體不支援」「電量不可讀取」
  - Rapoo：「已連線 · 硬體不支援」「電量不可讀取」
  - Logitech：「已連線 · 讀取成功」「70%」「未充電」+ 進度條
- 未知/不支援時不顯示進度條。
- 文字為繁體中文。
- 手動刷新與自動刷新邏輯已接上；UI smoke test 成功。
- **系統匣未實測成功**：目前工作階段沒有 Explorer，`Shell_NotifyIcon(NIM_ADD)` 回傳失敗，UI 正確顯示「系統匣不可用（無 Explorer）」。原生 tray 程式碼已完成，需在一般桌面工作階段驗證點擊/通知。
- 低電量通知邏輯以單元測試覆蓋；因目前沒有低於或等於 20% 的實機讀值，未做真機通知。

## 5. 打包測試（L5）

`build.ps1` 已建立並通過參數檢查，但此環境沒有 PyInstaller：

```text
BUILD_CHECK_FAILED: 找不到 PyInstaller。請先執行：... -m pip install pyinstaller
```

因此**沒有實際產出 `.exe`**。建置流程：

```powershell
python -m pip install pyinstaller
.\build.ps1
# 輸出 dist\PeripheralDock\PeripheralDock.exe
```

待有 PyInstaller 的 Windows 機器執行，並在乾淨資料夾測試啟動、托盘、開機啟動。

## 6. 待驗證清單

- [ ] Windows 11 上重跑 Redmi WinRT/GATT（不同 OS 可能有 BLE 行為）
- [ ] 在一般 Explorer 桌面驗證系統匣點擊、balloon 通知
- [ ] 在非沙箱使用者環境驗證 HKCU 開機啟動
- [ ] 以 PyInstaller 產出 `.exe` 並在無 Python 環境啟動
- [ ] 其他 M235 韌體/接收器、Rapoo 官方協定文件
- [ ] 低電量實機（<20%）通知與回升重置
