# 專案筆記

開發過程中累積的硬體事實、實測結果和決策原因。目前進度和待辦見 [HANDOFF.md](../HANDOFF.md)，操作說明見 `docs/` 下各語言文件。

## 專案概況

用賽車方向盤遙控 RC 車，不需要電腦。

- **地面端**：ESP32-P4 主機讀方向盤，透過無線模組控制車，並顯示儀表。
- **車端**：X2201 車上的控制板，還有 FPV 圖傳和計圈發射器。

最早的版本跑在 ESP32-S3-N16R8 開發板上（MOZA R5 + 單線 CRSF + GC9A01 圓形螢幕），端到端驗證過，之後依使用者決定只保留 P4（commit a9272ba）。

P4 是預設目標，在 `firmware/wheel-esp32` 直接 `idf.py build`。程式碼授權 GPL-3.0（來自 Aviateur submodule）。

## 地面端（Waveshare ESP32-P4-WIFI6-Touch-LCD-7B）

選它的原因：一塊板就有 USB-A OTG（接方向盤）、獨立 USB-UART（燒錄）、PH2.0 UART 和 1024×600 螢幕。S3 7C 螢幕板沒有空閒 GPIO 給 CRSF，自製 PCB 當時也被否決。

### MOZA R5

- USB ID `346e:0004`。
- 按鍵：Start=36、右撥片 14、左撥片 13、P=32（緊急停止）、N=19（綁定）、20=WIP。
- 踏板：Z（byte 5）油門（右踏板）、Rz（byte 11）煞車。

### 駕駛模型（control.c）

- Start 是點火。撥片是檔位 R N 1 2 3，上限 40/33/67/100%。
- 有滑行；煞車只負責煞車；只有在 R 檔且靜止時才能倒車，並走電調的「煞車－空檔－倒車」流程。

### 力回饋（ffb.c）

- 一開始以為有效，其實回中是底座（Pit House）自己的力。真正要做到兩件事，缺一不可：
  1. 輸出報告要走 HID interrupt OUT 端點 0x03。R5 對 control pipe 的 SET_REPORT 會回 ACK 但不理會，因此 `usb_host_hid` 是 vendored 版本。
  2. Set Effect 要開啟 direction 並設 9000（90°），否則 spring/damper 不動作。
- 用無人手扶的自動測試驗證：回中點 ±0.5 時，方向盤移動到 ±0.50。
- 效果有回中彈簧（隨速度變化）、阻尼、steer_deg 處的端點限位。Pit House 固定 900°，回中彈簧依 900/steer_deg 縮放（上限 2.5）。

### 每台車的設定

- 共 6 台（NVS blob `cars`），包含無線設定、最高時速、音效。
- 操控頁：轉向角度、expo、左右端點、油門起步點、轉向死區、微調。
- 無線類型只負責把 −1..1 轉成訊號；操控處理全部共用，在 radio.c。
- 調校由使用者實際開車給回饋。起步點是為了避免檔位上限把電調死區一起拉伸。

### 儀表、語言、音效

- 兩套圖片式儀表「曜石」「碳纖」，滑動切換。靜態圖層由 `design/render/dash_render.html` 用 headless Chrome 渲染。
- 使用者否決過手繪的 LVGL 儀表，認為沒有設計感：**先用 HTML 設計，再移植**。
- 介面中文，預設簡體，可切繁體。
- 引擎聲（sound.c）由駕駛模型即時合成，不用取樣：普通轎車、拉力賽車、寶馬 M4。轉速要做變化率限制，否則油門變化聽起來像爆音。

## 無線

### ELRS

- 預設單線接 BETAFPV 高頻頭。P4 另有雙線 Nano 選項（NVS `elrs2`）。
- CYCLONE Nano RX2400 當 RX-as-TX，ELRS 3.6.2，target `betafpv.rx_2400.nano`，用 release 的 `flasher.pyz --rx-as-tx internal` 經 WiFi 燒錄。
- 接線：Nano RX → GPIO28、Nano TX → GPIO30、5V 取自 CAN/RS485 第 1 腳。執行時 Nano 的 TX LED 不亮是正常的。
- ESP8285 接收機可從 Mac 連上它的 WiFi，用 curl 對 `10.0.0.1` 設定（`/config`、`/hardware.json`、`/options.json`、`/reboot`）。
- 接收機改 PWM：`hardware.json` 加 `pwm_outputs [1,3]`，TX 焊盤 = CH1 轉向，RX 焊盤 = CH2 油門，50 Hz，失控保護 1500。
- 綁定短語和接收機設定不記錄在此公開文件。

### MULTI（iRangeX IRX4+）

- 串口必須**不反相**（反相時紅燈閃）。P4 上的 PPM 腳是 GPIO29。
- 撥碼只在上電時讀取，改了要重新上電。
- FlySky FS-GT2E + MXO RXC42-AG（AFHDS 2A）在 PPM 和串口模式都能開。綁定順序：TX 先綁定，再按住 RX 鍵約 2 秒。
- MULTI 不支援：Sanwa FH3/4/5、Futaba T-FHSS/F4G、FlySky AFHDS3、Radiolink、MJX Hyper Go 14303。
- 這塊模組重焊後看起來壞了（上電閃兩下就滅），已擱置。

### 玩具遙控器（JC-02T-2.4G）

- 用 MCP4728 DAC 取代搖桿電位器（VA 轉向、VB 油門）。
- **注意**：P4 的 I2C PH2.0 端子 VCC 是 5V，會把 DAC 板的上拉抬到 5V、卡死匯流排。DAC 的 VCC 要接 12 腳排針的 3V3。
- 輸出要限制在實測範圍內，否則遙控晶片會誤判。JC-02T 的代碼（0..4095 = 0..3.3V）：轉向 L 3320 / 中 2020 / R 660，油門 倒 1720 / 中 1507 / 進 1320。中位值存在 DAC 的 EEPROM，上電不會暴衝。
- 工具：UART0 序列埠指令（`remote.c`）、`tools/remote_tune.html`（Web Serial）。

## 車輛

| 車 | 說明 |
|---|---|
| X2201（極客者） | 1:22、四驅、260 有刷、2S 7.4V 500 mAh。主要開發對象 |
| K989 | 1:28，ELRS |
| 14303 | 1:14，ELRS（換過接收機） |
| XTS-S10 | ELRS |

有一次「油門沒反應、轉向抖動」，查到最後只是車用電池沒電。

### X2201 的電裝

- 電調 ZERO-Z 2S：內建陀螺儀、5V 1A BEC、燈光輸出、開關。接收機口 ZH1.5 4P：黃 S2、藍 S1、綠 GND、棕 5V（已對實物確認）。
- 舵機插在電調上，由電調的陀螺儀控制。BEC 只有 1A，要設好端點避免舵機堵轉。
- 電調要先看到轉向訊號才會解鎖油門。
- 接收機 CYCLONE EP2 2400RX：10×10×6 mm，陶瓷天線，ESP8285，網頁顯示「BETAFPV 2.4GHz Lite RX」，焊盤間距 2.4 mm。
- 圖傳 Walksnail Ascent Lite+：3.0–12.6V。插頭是 **JST1.0（SH）6P**，只有前 4 腳有線：1 紅電源、2 黑 GND、3 白 RX、4 灰 TX。舊文件寫的 4P 是錯的。
- 車殼是合金的，有開窗，天線和 WiFi 距離都要實測。

### EP2 上電卡死

- 現象：接上電調後，上電就卡住（LED 恆亮）。只接電源則正常。
- 原因：電調開機時把 EP2 的 TX 焊盤（ESP8285 GPIO1）拉低，此時開機會失敗。
- 2.7k 串聯電阻**無效**。
- EP2 的 5V 加開關，先開電調再開 EP2：**有效**（2026-11-04 實測）。
- v8 用 RC 延遲做同一件事，電路本身未實測。

## 車載控制板演進

| 版本 | 內容 | 結果 |
|---|---|---|
| v3 `x2201-carrier` | 被動接線板，全插座，EP2 延遲上電 | 封存 |
| v4 | S3-MINI-1，EP2 → CRSF → S3 → PWM | 封存 |
| v5 | 自製 ELRS（C3 + SX1280 + AT2401C）+ C3 主控 | 封存 |
| v6 | S3 裸晶片 + 板載天線、陀螺儀、雙面貼片 | 放棄。一次整合太多，初版風險過高；另有 25 個過孔在焊盤上 |
| v7 | S3-Zero + EP2 手焊 | 被 v8 取代，圖傳插座是錯的 4P |
| **v8** | S3-MINI-1 貼片，EP2 手焊，EP2 直接接電調 | 暫緩，下一版的基礎 |

後續路徑見 [hardware/ROADMAP.md](../hardware/ROADMAP.md)，v3～v7 已移到 `hardware/archive/`。

使用者對 v8 的要求：第一版盡量精簡，冗餘留待後續版本。車燈、溫度偵測、風扇調速、陀螺儀都已拿掉。

選擇 EP2 直接接電調（方案 A）的原因：這條控制鏈路已經跑通，S3 當機也不影響開車。代價是 EP2 在 PWM 模式下沒有回傳路徑，電量只能走圖傳 OSD。

## FPV 支架與外殼（`firmware/wheel-esp32/enclosure`）

- 駕駛視角：Walksnail 攝影機 + 圖傳 + 25 mm 風扇。
- 座艙實測：底部 84 長 × 68 寬，腰線 12，車頂最高 24（mm）。
- `x2201_liner.py` 把內襯掃描點雲轉成高度圖。第一次掃描有破洞，車頂邊緣下方缺資料，要噴顯像劑重掃。
- 待定：內襯開整片擋風玻璃還是鏡頭孔，天線從合金殼哪裡出來。
- repo 裡沒有 CAD 虛擬環境，要自己建，見 HANDOFF.md。

## 計圈

四台車同場。先做車端，終點拱門之後做。

- 發射器 CH32V003J4M6 + AO3400 + 940 nm LED，38 kHz（`firmware/transponder`，`hardware/transponder`），還沒上機驗證。
- 幀格式：4T 訊號、2T 間隔的起始，8 位元 LSB 先傳（1T 訊號，1T 或 2T 間隔），ID 加反碼，1T 停止位，T = 400 µs。幀間隨機 4–12 ms。
- 車號在燒錄時指定：`make flash CAR=n`，跳線為備用。
- 編譯用 ESP-IDF 的 riscv32 GCC，`make build PREFIX=riscv32-esp-elf`；需要 ch32fun、minichlink、WCH-LinkE。
- v8 改由 S3 的 GPIO15 驅動 IR。

## 電路板流程

- 產生器：`hardware/pcbgen.py`、`schgen.py`，各板的 `gen_pcb.py`、`gen_sch.py`，用 KiCad 內建的 Python 執行。
- 佈線用 Freerouting 1.9.0（`-mt 1`），同樣輸入結果相同，因此可重用 `.ses`。
- KiCad 匯入 SES 時會停在螺絲孔的 placement 區塊，之後的網路全部遺失，要先去掉該區塊。
- 用 `rules()` 設定網路類別要在匯出 DSN 之前，否則線寬全部變成 0.2 mm，DRC 也查不出來。
- 4 層板上，要把內層標成 power，Freerouting 才不會走訊號；每個 GND 焊盤先放過孔再佈線。
- 懸空走線要用 uuid 刪除；用座標比對會誤刪相鄰走線。
- **DRC 通過不等於電路正確**：要核對網路（曾把 IR 打成兩個網路）、線寬，以及 SMD 焊盤上有沒有過孔。
- 嘉立創規則：線寬、間距 0.15 mm，過孔最小 0.45 mm。
- 嘉立創的零件模型方向常和 KiCad 不同，修正寫在各板的 `CPL_TURN`，每次都要看貼片預覽。

## 協作偏好

- 回覆一律使用繁體中文；程式碼、註解和 commit 訊息維持英文。
- 硬體方案改動要先討論，不要自己換掉已驗證的流程。
- 使用 brew 安裝前先詢問，不改全域 git 設定，commit 和 push 要使用者明確要求。
- 重新燒錄前說明原因。
