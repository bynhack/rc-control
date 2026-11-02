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

[`hardware/x2201-carrier`](../../hardware/x2201-carrier) 是改裝極客者 X2201（1:22 四驅攀爬車）用的無源轉接板。板上沒有晶片，只有接頭和焊盤，把電池、電源開關、ZERO-Z 電調、馬達、ELRS 接收機（Lite RX 當 2 路 PWM 接收機）、舵機、車燈和圖傳供電接在同一塊板上，減少飛線。固定在底盤中間的孔上。

| 位號 | 零件 |
|---|---|
| J1 | 電調，ZH1.5 4P（S2、S1、GND、5V） |
| J2 | Lite RX 焊盤 |
| C1、C2 | 5V 上的 220 µF（7343）和 100 nF |
| J3、J4 | 舵機輸出和電調的舵機線（ZH 3P） |
| J5–J7、R1、R2 | 車燈，0 Ω 電阻先佔位 |
| JP1、J9 | 圖傳供電選擇和輸出 |
| J8、J10 | 電池和電源開關（PH2.0 2P） |
| J11–J13 | 電調電源、電調馬達線、馬達（PH2.0 2P） |
| H1、H2 | M2 固定孔 |

- 原理圖由 `gen_sch.py` 產生（KiCad 10）。要改連線就改腳本再執行一次；`x2201-carrier.pdf` 是匯出的原理圖。
- 目前只有原理圖。PCB 佈局要等零件實際量好尺寸再畫。
- 馬達的大電流走電調自己的線，1 oz 銅厚就夠了。

```bash
python3 hardware/x2201-carrier/gen_sch.py
kicad-cli sch erc hardware/x2201-carrier/x2201-carrier.kicad_sch
kicad-cli sch export pdf -o hardware/x2201-carrier/x2201-carrier.pdf hardware/x2201-carrier/x2201-carrier.kicad_sch
```

`gen_sch.py` 裡的 KiCad 符號庫路徑是 macOS 的預設安裝位置，其他系統要改 `LIB`。
