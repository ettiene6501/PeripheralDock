# 實測證據

| 檔案 | 說明 |
|---|---|
| `probe-20261101.json` | 2026-11-01 的唯讀探測 JSON：環境、HID descriptor、Bluetooth 服務、HID++ trace、WinRT 結果 |
| `ui-preview.png` | PeripheralDock UI 實際畫面（三台設備） |

重現：

```powershell
python main.py probe --json docs/evidence/probe-YYYYMMDD.json
```

`probe` 不會送出 HID 寫入、不會讀取鍵盤輸入、不會修改裝置設定。
