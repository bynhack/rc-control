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

## 3D 列印外殼 v2（目前這版硬體）

模型是參數化的：[enclosure/enclosure.py](enclosure/enclosure.py)。成品在 `enclosure/out/`：

| 檔案 | 列印方向 | 說明 |
|---|---|---|
| `body.stl` | 已經翻轉好，**頂面朝下**貼平台 | 外殼本體：圓屏窗口、後方模組倉、各個開孔 |
| `plate.stl` | 平放 | 底板：ESP32 托架、MB102 墊台、腳墊凹槽 |

兩件都不用支撐。建議 PETG（或 PLA），層高 0.2 mm，3 圈牆，15～20% 填充。外形 88 × 98 × 64 mm（加底板 67 mm）。

組裝模擬：`viewer_export.py` 算出每兩個零件的碰撞體積和螺絲對位，`viewer.html` 用 three.js 顯示（爆炸圖、剖面、紅色標出重疊）。目前 45 組零件零干涉。

### 各零件怎麼裝

| 零件 | 位置 | 固定方式 |
|---|---|---|
| ESP32-S3 開發板 | 左前，長邊前後擺，USB-C 對著前牆開孔 | 托架卡住，熱熔膠點住 |
| 圓屏 | 頂面前方，排針那塊朝左 | **3M 泡棉膠**貼在頂板內側：玻璃落進淺凹槽，圓形 PCB 邊緣和排針那塊貼膠 |
| BETAFPV 1W | 後方模組倉，從後面插入，天線朝上 | 45 × 60 開口加兩側卡扣槽，像遙控器的模組倉一樣插進去 |
| 模組排針（1×5 公排針） | 模組倉前牆的窗口 | **先把高頻頭插好，排針插進它背面的母座，再從殼內點熱熔膠** |
| MB102 電源模組 | 右側，DC 頭和 Mini USB 朝右牆開孔 | **3M 泡棉膠**貼在底板墊台上 |
| USB-A 母座（方向盤） | 左牆 | 熱熔膠 |

列印前用卡尺量這幾個值，跟 `enclosure.py` 裡標 `MEASURE` 的參數對一下，改完重新產生：

1. `TAPE_T`：3M 泡棉膠厚度，目前 1.0 mm。決定玻璃凹槽深度（玻璃 1.5 − 膠厚）。
2. `LATCH_Z`：高頻頭兩側卡扣離模組底邊的高度，目前照照片估 23～37 mm。
3. `PWR_USB_Y` / `PWR_JACK_Y`：MB102 上 Mini USB 和 DC 頭中心離板子前端的距離，目前估 7 / 46 mm。
4. `USBA_HOLE`：USB-A 母座開孔，目前 13.6 × 6.2 mm。

重新產生：

```bash
python3 -m venv .venv && .venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/enclosure.py
.venv/bin/python enclosure/viewer_export.py   # 模擬頁面用的資料
```

### 供電接法

BETAFPV 1W 吃 **5～12V**，MB102 的 5V 穩壓（AMS1117）只適合小電流，所以分兩路：

- **DC 頭接 7～12V 變壓器**（建議 12V 2A）。
  - **高頻頭**：從 MB102 的 DC 輸入端（開關之後）直接拉一條線到模組排針的 5V-12V 腳，**不要接 MB102 的 5V 輸出**。1W 發射時電流大，AMS1117 從 12V 降到 5V 會過熱。
  - **ESP32 + 圓屏 + 方向盤 USB**：接 MB102 的 **5V 輸出** → ESP32 的 5V 腳。
- 全部 GND 接在一起。
- 只用 Mini USB 5V 供電也能動，但高頻頭就只吃 5V，可能開不到滿功率。

模組排針（從上到下照 BETAFPV 標示）：NC、5V-12V、GND、CRSF。CRSF 接 ESP32 的 GPIO17。

### 零件

- M3 自攻螺絲 × 4（長 8～10 mm）
- 1 mm 厚 3M 泡棉雙面膠（圓屏、MB102）
- 1×5 2.54 mm 公排針 × 1
- 直徑 10 mm 的橡膠腳墊 × 4
- USB-A 母座轉接小板 × 1
- 熱熔膠
