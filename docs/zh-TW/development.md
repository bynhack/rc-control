# 開發

[English](../en/development.md) | **繁體中文** | [简体中文](../zh-CN/development.md)

## 韌體結構

都在 [`firmware/wheel-controller/main`](../../firmware/wheel-controller/main)：

| 檔案 | 作用 |
|---|---|
| `main.c` | 開機、USB 主機，把方向盤資料交給駕駛模型 |
| `wheel.c` | 解析方向盤底座的 HID 報告（MOZA R5、T300RS） |
| `control.c` | 駕駛模型和所有安全規則；發射端只讀 `control_output()` |
| `radio.c` | 車輛、NVS 裡的設定，以及所有發射方式都要經過的操控層 |
| `crsf.c` | ExpressLRS（CRSF）發送 |
| `multi.c` | 四合一 MULTI 發送，串口或 PPM |
| `remote.c` | 經 MCP4728 DAC 控制玩具遙控器，以及串口指令 |
| `ffb.c` | 力回饋（MOZA 用 USB PID，T300 用 Thrustmaster 自己的協議） |
| `sound.c` | 引擎聲浪合成 |
| `display_p4.c`、`dash_p4.c`、`ui_p4.h` | 設定頁、儀表盤、兩種語言的介面文字 |

`components/usb_host_hid` 是 Espressif usb_host_hid 1.2.1 的拷貝，多了兩個函式，原因見[力回饋](#力回饋)。

### 訊號路徑

```
wheel.c → control.c（駕駛模型、安全）→ radio.c（操控）→ crsf.c / multi.c / remote.c
```

要加一種新的發射方式，只要寫一個發送端：讀 `control_output()`，經過 `radio_steering()` 和 `radio_throttle()`，再把得到的 −1…+1 換成自己的訊號。把它加進 `radio.h` 的 `radio_kind_t`，車輛、操控、反轉和安全規則就都自動有了。

### 操控的即時響應優先

任何東西都不能拖慢發射。發送任務在 core 1，優先級最高：

| 任務 | Core | 優先級 |
|---|---|---|
| `crsf` | 1 | 10 |
| `multi` | 1 | 9 |
| `sound` | 0 | 6 |
| `ffb` | 0 | 4 |
| `remote` | 1 | 4 |
| `usb_lib` | 0 | 2 |
| `remote_con`（串口指令） | 1 | 2 |
| `ui` | 1 | 1 |

調試頁面和串口指令的優先級都比發送任務低，不會拖慢車的響應。真方向盤在 0.5 秒內有資料時，模擬方向盤（`w`）一律不理。

### 力回饋

力回饋報告要從 HID 介面的中斷 OUT 端點發（R5 是 0x03）。從控制通道用 SET_REPORT 發，R5 會回 OK，但什麼都不做。ESP-IDF 的 usb_host_hid 不支援 OUT 端點，所以 `components/usb_host_hid` 多了 `hid_host_device_send_output_report()`。效果還要打開方向，並設成 90 度（X 軸），否則彈簧和阻尼都沒有力。

T300RS 照 Linux 的 hid-thrustmaster 和 hid-tmff2 做。剛插上時它是 `044f:b65d`，韌體用廠商請求讀它的型號，再發切換請求；ESP-IDF 也做不到這個，所以 `components/usb_host_hid` 還多了 `hid_host_device_vendor_request()`。底座重新連上後變成 `044f:b66e`。它的力回饋是同一個 OUT 端點上的輸出報告 0x60，用 Thrustmaster 自己的格式：開啟、關掉自帶回正、轉角 900°，再上傳、啟動和更新三個條件效果。

## 串口指令

在看 log 的那個口（「USB TO UART」，115200），一行一條：

| 指令 | 作用 |
|---|---|
| `w <方向> <油門> <剎車>` | 模擬一筆方向盤資料（−1…1、0…1、0…1），經過跟真方向盤一樣的駕駛模型。要每 50 ms 送一次。真方向盤在 0.5 秒內有資料時不理 |
| `k start` / `k up` / `k down` / `k stop` | 點火／熄火、升檔、降檔、急停 |
| `d <A> <B>` | 直接設 DAC 兩路的碼（0–4095），1.5 秒沒有新的就交回方向盤 |
| `x` | 馬上交回方向盤 |
| `name <名字>` | 改目前那台車的名字 |
| `kind <0–3>` | 目前那台車的發射方式：0 ELRS、1 四合一串口、2 四合一 PPM、3 遙控器主板 |
| `dead <左> <右> <前進> <倒車>` | 目前那台車的方向和油門死區，千分比 |
| `scan` | 列出 I2C 上所有有回應的位址。正常只有觸控（0x14 或 0x5D）和 DAC（0x60）；出現幾十個位址，表示有東西拖住匯流排，通常是線鬆了或插錯 |

## 調試頁面

[`tools/remote_tune.html`](../../firmware/wheel-controller/tools/remote_tune.html) 是透過串口指令操作的調試頁面。要用支援 Web Serial 的 Chrome，從本機伺服器打開：

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory firmware/wheel-controller/tools
```

打開 http://localhost:8765/remote_tune.html，按「連接 P4」。

- **模擬駕駛**：拖方向盤、踩踏板、點火換檔。也可以用鍵盤：A/D 方向，W/S 油門和剎車，Enter 點火，Q/E 換檔，空白鍵急停。走跟真方向盤一樣的路徑，會顯示引擎、檔位、車速和輸出。
- **精調 DAC**：每路 DAC 一條可以縮放的軸（⌘ 或 Ctrl ＋滾輪，或雙指捏合）。滾輪一格 ±1，按住 Shift 是 ±10，在上面標記每一路的兩端和死區邊。見[改裝玩具遙控器](toy-remote.md#校準)。

用完按「斷開」，不然頁面佔著串口，燒錄會失敗。

## 字型和儀表盤圖片

- **字型**：`main/fonts/gen_fonts.sh <字型目錄>` 用 `lv_font_conv`（需要 Node）重新產生點陣字型。中文字型只收原始碼裡出現的字，所以加了介面文字後要重跑。字型目錄要放 Noto Sans SC Medium，以及儀表數字用的 Saira 和 Barlow Condensed，下載連結在腳本開頭。
- **儀表盤圖片**：靜態圖層畫在 `design/render/dash_render.html`。`design/render/build_assets.py` 用 headless Chrome 渲染，輸出到 `main/assets/*.bin`。需要 Google Chrome、Pillow 和 numpy。

## 協議要點

- **CRSF**：位址 `0xEE`，CRC8 多項式 `0xD5`。通道值 172／992／1811 對應 988／1500／2012 µs。ELRS 只有通道 1–4 是全精度。
