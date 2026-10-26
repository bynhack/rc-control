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

## 3D 列印外殼（目前這版硬體）

模型是參數化的：[enclosure/enclosure.py](enclosure/enclosure.py)。成品檔案在 `enclosure/out/`：

| 檔案 | 列印方向 | 說明 |
|---|---|---|
| `body.stl` | 已經翻轉好，**頂面朝下**貼平台 | 外殼本體，含圓屏窗口和後方模組倉側牆 |
| `plate.stl` | 平放 | 底板，含 ESP32 托架、模組倉前擋、腳墊凹槽 |

兩件都**不用支撐**。建議 PLA 或 PETG，層高 0.2 mm，3 圈牆，15～20% 填充。

外形 75 × 102 × 38 mm（模組倉加上高頻頭後，總高約 64 mm 再加天線）。

**列印前請用卡尺量這幾個值**，跟 `enclosure.py` 開頭標了 `MEASURE` 的參數對一下，改完重新執行就會重新產生：

1. ~~`MOD_T`~~：BETAFPV 模組厚度，已實測 20 mm（模組倉內深 20.8 mm）。
2. ~~圓屏模組~~：已照規格書做。玻璃是 Ø35.6 的圓形，加上排線側凸出共 38.1 mm；凹槽是圓形加排線口袋，窗口 Ø32.4 跟可視區同心。排針那塊朝左、排線朝前（靠使用者這側）。
3. `USBA_HOLE`：USB-A 母座開孔，目前 13.6 × 6.2 mm。

重新產生：

```bash
python3 -m venv .venv && .venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/enclosure.py
```

### 零件

- M3 自攻螺絲 × 6（長 8～10 mm）：底板鎖本體 4 顆，模組倉 2 顆
- 直徑 10 mm 的橡膠腳墊 × 4
- USB-A 母座轉接小板 × 1
- 熱熔膠

### 組裝和接線改動

1. **方向盤改走 USB-A 母座**，不再用 OTG 口和 OTG 線。母座小板用熱熔膠固定在右側開孔後面，焊 4 根線：

   | USB-A 母座 | ESP32-S3 |
   |---|---|
   | VBUS | 5V |
   | D− | GPIO19 |
   | D+ | GPIO20 |
   | GND | GND |

   改完後 **CH340C（右邊 USB-C）專門負責供電、燒錄和看 log**，方向盤插著也能燒錄，FT232 不用了。韌體不用改。**OTG 口不要再插任何東西**（它和 GPIO19/20 是同一組 USB 線）。
2. **ESP32 板**：元件面朝上，USB-C 那頭頂著左牆，放進四個托架，用熱熔膠點住。排針朝下，托架下面留了 12 mm 給杜邦頭；直接焊線更省空間。
3. **圓屏**：玻璃從內側放進頂部的方形凹槽，對正圓窗，背面用熱熔膠固定。
4. **BETAFPV**：從上往下插進後方模組倉，背面針腳朝著外殼。CRSF、5V、GND 的線從後牆缺口穿進去。
5. 底板蓋上，6 顆 M3 自攻螺絲鎖緊，貼上腳墊。

**供電提醒**：BETAFPV 1W 是從 ESP32 板的 5V 取電，全部電流都經過 CH340C 那個 USB-C。請用 **5V 2A 以上的充電頭**。如果高頻頭在高功率時重啟，就給它單獨供電。
