# wheel-esp32：不用電腦的方向盤遙控器

方向盤透過 USB 主機讀進來，用 CRSF 驅動 ELRS 高頻頭，再發給車上的接收機。全程不用電腦。

## 目前版本（已驗證可用）

硬體：ESP32-S3-N16R8 開發板 + BETAFPV ELRS 高頻頭 + 1.28" GC9A01 圓屏 + MOZA R5。

| 用途 | 接法 |
|---|---|
| 方向盤 | 開發板左邊的 ESP32-OTG 口（需要輸出 5V） |
| 高頻頭 | CRSF 訊號接 GPIO17（單線半雙工，400000 baud，BETAFPV 撥碼 3、4 ON），GND 共地 |
| 圓屏 | RST→8、CS→10、DC→9、SDA→11、SCL→12、VCC→3V3、GND |
| Log | UART0（TX0 = GPIO43），115200 |

MOZA R5 按鍵：

| 按鍵 | 編號 | 功能 |
|---|---|---|
| Start | 36 | 解鎖／上鎖（必須放開兩個踏板才能解鎖） |
| 右撥片 / 左撥片 | 14 / 13 | 限速升檔 / 降檔（L / M / H） |
| P | 32 | 急停 |

踏板：右踏板（Z，byte 5）是油門，左踏板（Rz，byte 11）是剎車／倒車。

安全邏輯照搬電腦版 `src/control.rs`：開機預設鎖定，300 ms 收不到方向盤就自動回中並上鎖，CRSF 每 4 ms 發一幀。

編譯和燒錄：

```bash
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbserial-XXXX flash monitor
```

## 定型的下一版硬體（2026-10-25 決定，採購中）

| 部件 | 型號 | 用途 |
|---|---|---|
| 主控＋儀表屏 | 微雪 ESP32-P4-WIFI6-Touch-LCD-7B | USB-A（OTG 2.0 HS）接方向盤；USB-C（USB TO UART）燒錄和 log；PH2.0 UART 端子接高頻頭；7" 1024×600 觸控儀表盤 |
| 地面發射機 | CYCLONE Nano RX2400 × 2（ESP8285 + SX1281 + AT2401C PA） | 一顆刷 ELRS「RX as TX」當發射機，一顆備用 |
| 車上接收機 | 沿用現有的 5 通道 PWM ELRS 接收機（ESP8285 + SX1281） | 不換，照常接電調、舵機、陀螺儀 |

不採用的方案和原因：
- 自己打板：先用現成的板子。
- 微雪 ESP32-S3-Touch-LCD-7C：RGB 屏佔滿了 GPIO，沒有地方接 CRSF；USB 口又要身兼三職。
- BETAFPV Lite 接收機放車上：只有 CRSF 輸出、沒有 PWM，也沒有 PA/LNA。

新版接法（Nano 走全雙工）：

| P4 板 UART 端子 | Nano RX2400 |
|---|---|
| TXD | RX |
| RXD | TX |
| GND | GND |
| VCC（選 5V） | 5V |

## 硬體到貨後的步驟

1. **車上接收機**：先確認型號，升級到 ELRS 3.5 以上（ESP8285 還支援）。
2. **Nano**：刷同一個大版本的「RX as TX」，綁定短語跟車上一致。
3. **P4 板**：
   1. 看原理圖確認：USB-A 有沒有輸出 5V VBUS；UART 端子用哪兩根 GPIO；5V/3V3 選擇焊盤管哪些端子；12 PIN 端子的 GPIO 編號。
   2. 先跑方向盤測試，確認能認到 MOZA（346e:0004）。
   3. 移植 `wheel.c`、`control.c`、`crsf.c`，`crsf.c` 改成雙線全雙工，同時保留單線模式給 BETAFPV。
   4. 把控車和畫面分開：一個核心跑 CRSF 和安全邏輯，另一個跑 1024×600 儀表盤和觸控設定。
   5. 可選：12 PIN 端子接實體急停按鈕、蜂鳴器。
4. **架空測試**：轉向和油門方向、解鎖、急停、限速檔。
5. **場地實測距離**：ELRS 封包速率可以先設低一點（例如 100 Hz），距離會更遠。
