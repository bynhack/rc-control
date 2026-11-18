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
| `camera_pod.py` | 美嘉欣 14303 車頂的 WRC 風格 WiFiLink 2 攝影機罩 |
| `wifilink_mount.py` | 夾在 8 mm 圓桿上的 RunCam WiFiLink 2 支架 |

每個腳本開頭的註解說明列印方向和要用的螺絲。標了 `MEASURE` 的參數，列印前要用卡尺量你自己的零件再改。共用的幾何和預覽函式在 `cad.py`。

```bash
cd firmware/wheel-esp32
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/p4_case.py
```

## X2201 主板

X2201 已確認的硬體方案（元件和接線）在 [hardware/PLAN.md](../../hardware/PLAN.md)。照這份方案畫好的板子是 [`hardware/x2201-mainboard`](../../hardware/x2201-mainboard)，40 × 40 mm，用一顆 M2 螺絲固定在底盤凸台上、定位柱定位，在底盤 40 × 60 mm 的可用範圍內。

- **只有一個電源入口**：2S 電池焊在主板上，經過防反接 Q1。
- **電調在主板上**：TI DRV8874 H 橋，經 ZH2.0 插座驅動 260 馬達，限流約 4.9A。
- **5V BEC 在主板上**：LMR51430 降壓，約 2–2.5A，供 ESP32、EP2、舵機、風扇、IR LED。
- **控制器**：ESP32-S3 SuperMini，用排針墊高後手焊，USB-C 伸出板外。
- **插座**：全部是側插的 ZH1.5（EP2、圖傳、舵機、風扇、電源按鈕），插口朝外，板子上方沒有東西立起來。
- **電源按鈕**：不自鎖。按一下開機，S3 開機後用 TX 腳保持電源；再按一下關機。

板子外形可以照車內空間調整，元件和接線以 PLAN.md 為準。v3～v9 的舊板子已在 2026-11-16 刪除，需要時可以從 git 找回（commit `56bd000` 之前）。

## 計圈應答器

每台車裝一個應答器，用 940 nm 紅外 LED 閃自己的車號，讓終點線的拱門分辨是哪台車（最多 8 台）。X2201 的應答器做在主板上（IR LED 直接焊在主板車尾）；其他車用 [`hardware/transponder`](../../hardware/transponder) 的小板（15 × 22 mm）。

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
