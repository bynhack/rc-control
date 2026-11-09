# 硬體

[English](../en/hardware.md) | **繁體中文** | [简体中文](../zh-CN/hardware.md)

## 3D 列印件

所有模型都是 [`firmware/wheel-esp32/enclosure`](../../firmware/wheel-esp32/enclosure) 裡的參數化 Python 腳本（manifold3d），STL 在 `enclosure/out/`。`*_viewer.html` 和 `*_assembly.html` 是組裝預覽，用瀏覽器打開。

| 模型 | 內容 |
|---|---|
| `p4_case.py` | P4 板的桌上外殼：螢幕托盤 `p4_tray.stl`；裝在 MOZA 底座上的支架 `p4_stand.stl`，內有 100 × 45 雙單元盒式喇叭的槽位和 ELRS Nano 的位置；以及把四合一掛在支架背板上的蓋板 `p4_multi_cover.stl` |
| `minicar_cage.py` | 1:28 拉力車的測試框：車殼下可用空間的形狀 |
| `minicar_mount.py` | 那台車車殼內的圖傳和接收機支架 |
| `vtx_mount.py` | Walksnail Avatar Ascent Lite+ 圖傳和攝影機的低矮風冷支架 |
| `x2201_cage.py` | 極客者 X2201 駕駛艙的測試框：車殼內可用空間的形狀，放駕駛視角的 Ascent Lite+ 攝影機用 |
| `x2201_fpv_mount.py` | X2201 駕駛艙內的駕駛視角圖傳支架：Ascent Lite+ 攝影機看出擋風玻璃，後面是圖傳和 25 mm 風扇，用 3M 膠黏在底盤中間走線槽兩側 |
| `x2201_liner.py` | 從 3D 掃描（點雲）算出 X2201 黑色內襯的高度圖 `x2201_liner.npz`，支架用它檢查有沒有碰到內襯；也輸出可列印的複製件 `x2201_liner_replica.stl` |
| `x2201_carrier_frame.py` | 以 [X2201 轉接板](#x2201-轉接板)當底座時的圖傳支架列印框架：圖傳柱子、風扇墊片和攝影機側板，鎖在板上的 M2 貼片螺母上 |
| `camera_pod.py` | 美嘉欣 14303 車頂的 WRC 風格 WiFiLink 2 攝影機罩 |
| `wifilink_mount.py` | 夾在 8 mm 圓桿上的 RunCam WiFiLink 2 支架 |

每個腳本開頭的註解說明列印方向和要用的螺絲。標了 `MEASURE` 的參數，列印前要用卡尺量你自己的零件再改。共用的幾何和預覽函式在 `cad.py`。

```bash
cd firmware/wheel-esp32
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/p4_case.py
```

## X2201 轉接板

> 已封存，見 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier`](../../hardware/archive/x2201-carrier) 同時是 X2201 圖傳支架的底座，也負責車上的小電流接線。它取代列印支架的底板，再往後多 10 mm：54 × 52 mm，用 1 mm 的 3M VHB 膠黏在底盤中間走線槽兩側的平面上。零件全部在正面，背面是平的。列印框架（`x2201_carrier_frame.py`）鎖在板上的四個 M2 貼片螺母上：先把圖傳放在板上，再把框架從上面蓋下來。

**往外的接線全部用插座**，集中在板子後端一排，正好在後窗下方。轉接板上不用焊任何線；只有本身沒有插頭的模組（EP2、紅外 LED、風扇）要在模組那端焊一次 ZH 單頭線。

整台車只要電調一個開關：

- **EP2 接收機延時通電**：Q1（AO3401）在電調的 BEC 起來 0.5～1 秒後才給 EP2 供 5V。ZERO-Z 開機時會把 EP2 的 TX 焊盤（GPIO1）拉低，EP2 在這時開機就會卡住；串電阻沒用。
- **圖傳由 BEC 控制**：有 5V 時 Q3（AO3400）打開 Q2（AO3401），圖傳只在電調開著時才接上電池。R2、R3 讓 Q2 的閘極電壓在 3S 以內都不超過 12 V。

| 位號 | 零件 |
|---|---|
| J1 | ZERO-Z 接收機線，ZH1.5 4P（黃 S2、藍 S1、綠 GND、棕 5V） |
| J2 | EP2，ZH1.5 4P：1 RX 焊盤（CH2 油門）、2 TX 焊盤（CH1 轉向）、3 GND、4 5V（延時） |
| Q1、C1、R1、D1 | EP2 延時通電 |
| Q2、Q3、R2–R5 | 圖傳電源開關 |
| J6 | 電池分接，ZH1.5 2P：1 電池正、2 GND。用電池 Y 線從電池到電調的主線分出來 |
| J3 | 圖傳，SH1.0 4P：1 電源、2 GND（3、4 不接）。用雙頭同向的 SH1.0 4P 線直接插圖傳 |
| J4 | 25 mm 風扇，ZH1.5 2P：1 5V、2 GND |
| C2、C3 | 5V 和電池上的 22 µF |
| U2、C4、JP1–JP3、TP11 | 計圈應答器：CH32V003、車號跳線、SWIO 焊盤（只在燒錄時用，WCH-LinkE 的 GND 接在螺母上） |
| Q4、R6–R8、J5 | 應答器的紅外 LED 驅動；J5 是 ZH1.5 2P：1 LED 正、2 LED 負 |
| H1–H4 | 給列印框架用的 M2 貼片螺母（例如 Würth 9774020151R） |

- 舵機插在電調的舵機口上，由電調的陀螺儀控制。
- 應答器的 LED 從車殼的後窗開口朝上照，對著終點線的拱門。
- 原理圖由 `gen_sch.py` 產生，佈局由 `gen_pcb.py` 產生，兩邊網路名稱一致。`x2201-carrier.pdf` 是匯出的原理圖。
- 加上 `FAB=1`，`gen_pcb.py` 會一併輸出 Gerber、`bom.csv` 和 `cpl.csv`，給嘉立創 SMT 貼片用，小零件由工廠焊好。
- 插線前先對照 J1 旁的標示確認線的顏色。
- 板子後端多出來的 10 mm 要確認底盤那裡是平的，試裝測試框時一起看。
- J1 要買兩頭同向（1 腳對 1 腳）的 ZH1.5 4P 線。第一次通電前用電錶量一下，電調的 5V 要落在 J1 第 4 腳。

```bash
cd hardware/archive/x2201-carrier
python3 gen_sch.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
kicad-cli pcb drc --refill-zones x2201-carrier.kicad_pcb
```

腳本裡的 KiCad 路徑是 macOS 的預設安裝位置，其他系統要改 `LIB` 和 `FP`。

## X2201 轉接板 v4（ESP32-S3）

> 已封存，不在目前的迭代路徑上，見 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier-v4`](../../hardware/archive/x2201-carrier-v4) 在轉接板上加了一顆 ESP32-S3，車子有了自己的大腦。這是下一版，還沒做：目前在製作的是上面的 v3。

- **訊號路線**：EP2 → CRSF（UART）→ ESP32-S3 → PWM → 電調。EP2 要改成序列 CRSF 輸出，不再輸出 PWM；失控保護由 ESP32 負責（CRSF 斷掉就把油門歸零）。
- **新增的功能**：電池電壓回傳到方向盤、眼鏡裡的 OSD（透過圖傳線第 3、4 腳的 MSP）、計圈紅外線碼（不用 CH32）、狀態燈，還有前緣的 USB-C，用來燒錄和看序列埠。
- **EP2 開機卡住的問題消失**：電調不再碰 EP2 的腳，所以 v3 的延時供電（Q1、C1、R1、D1）拿掉了。
- **WiFi 只在設定時開**（車號、微調），車子要停著：它和 ELRS 同在 2.4 GHz。
- **插座和線材跟 v3 一樣。** 板子前端加長 4 mm 給模組的天線（58.2 × 52 mm），要確認車殼前方放得下。
- **列印框架兩版都能用**：[`x2201_carrier_frame.py`](../../firmware/wheel-esp32/enclosure/x2201_carrier_frame.py) 在攝影機側板底下多了一個小缺口，讓 v4 的兩顆去耦電容通過。
- **電池電壓**接在 IO17（ADC2），WiFi 關著時才能讀，也就是車子在跑的時候都能讀。
- DRC 和框架的干涉檢查都通過。ESP32 的韌體還沒寫。

```bash
cd hardware/archive/x2201-carrier-v4
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # 原理圖，從板子的網路產生
```

## X2201 轉接板 v5（OpenIPC）

> 已封存，不在目前的迭代路徑上，見 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier-v5`](../../hardware/archive/x2201-carrier-v5) 是 v4 把 Walksnail 圖傳換成 OpenIPC 數位圖傳，車上只要接攝影機。**目前只畫了電路。** 排板要等實物到了量過尺寸再做。

- **影像**：買現成的 OpenIPC Thinker Base（SSC338Q，25 × 25 mm，M2 孔距 20 × 20），用銅柱疊在板子上面。IMX335 攝影機插在它上面。電腦版本來就能用 RTL8812AU 網卡收 OpenIPC。
- **WiFi**：BL-M8812EU2（RTL8812EU）模組。它最大要 5 V 2 A 以上，電調的 1 A BEC 不夠，所以由 U4（LMR51430，5 V 3 A）從電池另外降壓供電。最大佔空比 98%，2S 沒電時也撐得住 5 V。要加散熱片和風扇，室內發射功率調低。
- **主板內建 ELRS 接收機**：ESP32-C3 + SX1280 + AT2401C，照 ExpressLRS 官方「Generic C3 2400 PA」的腳位接，可以直接刷官方韌體。天線用 U.FL（J10），車殼是金屬的，要從車窗拉出去。ESP32-S3 控制 C3 的 EN 和 GPIO9，所以 Mac 插 USB-C 就能刷 ELRS。EP2 插座（J2）保留當備案：讓 C3 停在重置狀態，再插上 EP2。C3 自己的 WiFi（ELRS 設定頁）另外接一個 U.FL（J11）。外圍電路照 Espressif 的參考電路（40 MHz 晶振）和 AnyLeaf 的開源接收機設計（MIT 授權）。匹配電路的數值只是起始值，要再調。
- **插座**：
  - J3，SH1.0 6P：Thinker 的電源/UART2，照它的腳序。1–2 腳是開關後的電池，3 腳是它的 RX，4 腳是它的 TX，5–6 腳是 GND。
  - J7，SH1.0 4P：Thinker 的 USB，Vd 腳不接。
  - J8，ZH1.5 8P：WiFi 模組，照它的腳序。ESP32 可以重置它（IO12）。
  - J6 電池插座改成 PH2.0（約 2 A）。
  - 風扇改吃 WiFi 那路 5 V。
- **ESP32** 透過 MSP 接 Thinker 的 UART2（msposd 畫 OSD），兩邊各串 1k，誰都不會反向供電給對方。
- **電源**：Thinker 和 WiFi 跟著電調開關，和 v3 的圖傳一樣。
- **實物到了要量**：模組的厚度、固定孔、散熱片，Thinker 加散熱片的高度，以及插座型號。量完再排板、重畫列印框架。
- ERC：0 個錯誤。

```bash
cd hardware/archive/x2201-carrier-v5
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # 只放零件，沒走線
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # 原理圖，從板子的網路產生
```

## 計圈應答器

每台車裝一個應答器，用 940 nm 紅外 LED 閃自己的車號，讓終點線的拱門分辨是哪台車（最多 8 台）。X2201 的應答器做在轉接板上；其他車用 [`hardware/transponder`](../../hardware/transponder) 的小板（15 × 22 mm）。

- **電路**：CH32V003J4M6 在 PC4（TIM1_CH4）產生 38 kHz 脈衝，AO3400 經 33 Ω 推動 LED，脈衝時約 110 mA，平均約 10 mA。
- **車號**：燒錄時設定，`make flash CAR=3`（1–15）。不帶 `CAR` 燒錄時，改讀焊上的跳線：1 加上焊上的跳線（+1、+2、+4）。
- **J1**：5V、GND、SWIO（2.54 mm）。接到接收機任一個舵機口的正負極；燒錄時 WCH-LinkE 也接這三腳。
- **LED**：3 mm 940 nm，可以直接焊在板上，也可以用兩根線拉出去。要能從窗口或薄塑膠車殼朝上照出去。
- **訊號格式**：開頭脈衝 4T、間隔 2T，接著 8 位元、低位先送（脈衝 1T，間隔 1T = 0、2T = 1）：車號和它的反碼，最後一個 1T 的結束脈衝。T = 400 µs。每幀之間隨機隔 4～12 ms。
- **韌體**：[`firmware/transponder`](../../firmware/transponder)，用 [ch32fun](https://github.com/cnlohr/ch32fun) 編譯（`make`、`make flash CAR=n`）。

```bash
cd hardware/transponder
python3 gen_sch.py
FAB=1 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
```

兩塊板子的腳本共用 `hardware/pcbgen.py`（佈局）和 `hardware/schgen.py`（原理圖）。
