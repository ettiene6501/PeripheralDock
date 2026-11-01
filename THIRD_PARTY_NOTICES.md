# 第三方元件與參考資料

## 執行期依賴

本專案只使用 Python 標準函式庫（`ctypes`、`winreg`、`tkinter`、`json`、`unittest`），
未打包第三方執行期套件。

## 協定研究參考

### Solaar

- 專案：https://github.com/pwr-Solaar/Solaar
- 授權：GPL-2.0-or-later
- 用途：確認 Logitech HID++ 2.0 的訊息框架、feature `0x1000` / `0x1004` 欄位與
  `BATTERY_STATUS` 回應格式；確認 M235 WPID `4055`。
- 遵循方式：本專案**沒有複製或連結 Solaar 程式碼**；`windows/hidpp.py` 是依協定行為
  重新實作的獨立唯讀 client。Solaar 的授權與著作權仍屬其作者。
- 相關檔案：`lib/logitech_receiver/base.py`、`hidpp20.py`、`hidpp20_constants.py`。

### Windows API 文件

- Microsoft Learn：`Windows.Devices.Bluetooth`、`Windows.Devices.Bluetooth.GenericAttributeProfile`
- USB-IF HID Usage Tables 1.12（Usage Page `0x06` / Usage `0x20`）

### 其他參考

- `SpartanX1/bluetooth_classic_battery_windows`：經典藍牙耳機以 RFCOMM 監聽
  `AT+IPHONEACCEV` 的實驗；本專案**未採用**，以避免搶占音訊通道與依賴耳機主動事件。
- Rapoo E1050 官方產品頁：僅規格，無 SDK/電量協定。

## 圖片與字型

UI 使用系統內建字型（Microsoft JhengHei UI、Segoe UI Emoji），未打包字型檔。
截圖 `docs/evidence/ui-preview.png` 為本專案執行畫面。
