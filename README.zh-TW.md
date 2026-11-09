# rc-control

[English](README.md) | **繁體中文** | [简体中文](README.zh-CN.md)

用模擬賽車的方向盤和踏板開遙控車。方向盤插在一塊 7 吋 ESP32-P4 觸控螢幕上：它用 USB 讀方向盤，跑一套有點火、檔位、滑行和真實剎車的駕駛模型，再用那台車的發射方式發出去。全程不用電腦。

![電腦版控制台](docs/dashboard.png)

## 功能

- **獨立的方向盤控制器**：ESP32-P4 7 吋觸控板加 MOZA R5 或 Thrustmaster T300RS 方向盤底座，在螢幕上選。
- **三種發射方式**，每台車各自選：
  - ExpressLRS（CRSF）
  - 四合一 MULTI 高頻頭，走串口協議或 PPM
  - 玩具車原裝遙控器，用 DAC 取代它的電位器
- **每台車各自的操控設定**，所有發射方式都要經過它：轉角、中心柔和、方向和油門死區、方向回正、舵量、反轉，都直接用方向盤設定。
- **照真車駕駛**：點火、R N 1 2 3 檔、滑行、真實剎車；進倒檔時會自動替電調送「剎車 → 倒車」。
- **力回饋**：兩種底座都有（MOZA 用 USB PID，T300 用 Thrustmaster 的協議），回正力隨車速加強，打到轉角極限時有軟性頂點。
- **儀表盤**：兩款儀表、簡繁中文介面、6 台車的設定檔，板子的喇叭即時合成引擎聲浪。
- **電腦版**（Rust，可選）：從電腦控制 ELRS 高頻頭，並用 USB 網卡直接收 OpenIPC 圖傳。
- **3D 列印件和車上轉接板**：MOZA 底座上的支架、車上的固定件、KiCad 原理圖。

## 文件

| | |
|---|---|
| [方向盤控制器](docs/zh-TW/wheel-controller.md) | 硬體、接線、編譯和燒錄韌體 |
| [駕駛和操控](docs/zh-TW/driving.md) | 按鍵、駕駛模型、車輛、操控設定、力回饋 |
| [發射方式](docs/zh-TW/radios.md) | ExpressLRS、四合一 MULTI、玩具遙控器 |
| [改裝玩具遙控器](docs/zh-TW/toy-remote.md) | 用 MCP4728 DAC 控制玩具車的原裝遙控器 |
| [硬體](docs/zh-TW/hardware.md) | 3D 列印件和 X2201 轉接板 |
| [電腦版](docs/zh-TW/desktop-app.md) | 電腦控制 ELRS、圖傳、Windows 編譯 |
| [開發](docs/zh-TW/development.md) | 程式結構、串口指令、調試頁面、重新產生字型和圖片 |

## 快速開始

```bash
git clone https://github.com/bynhack/rc-control.git
cd rc-control/firmware/wheel-esp32
. ~/esp/esp-idf/export.sh          # ESP-IDF v5.5
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

然後接好發射方式（見[發射方式](docs/zh-TW/radios.md)），把方向盤插到板子的 USB-A 口，按方向盤的 Start 點火。

## 倉庫結構

```
firmware/wheel-esp32/   獨立控制器（ESP-IDF，C）
  main/                 韌體原始碼
  tools/                remote_tune.html，Web Serial 調試頁面
  enclosure/            3D 列印件（Python，manifold3d）
  design/               儀表盤的美術稿
hardware/               電路板（KiCad）
src/, native/           電腦版（Rust，圖傳部分是 C++）
docs/                   三種語言的文件
```

## 參與貢獻

歡迎提 issue 和 pull request。送 pull request 前，先用 `idf.py build` 編譯韌體；改了電腦版的話，也要跑 `cargo test`。新的文件要寫進 `docs/` 下的三種語言；只會寫一種的話，在 pull request 裡說一聲，會有人幫忙翻譯。

## 授權

本專案以 **GPL-3.0-only** 發布（[LICENSE](LICENSE)），範圍包括電腦版、韌體、3D 模型和硬體設計。發布修改後的版本（包括燒進設備的韌體）時，要以同樣的授權提供原始碼。

用到的第三方程式碼和資源各自保留原本的授權：

| 部分 | 位置 | 授權 |
|---|---|---|
| [Aviateur](https://github.com/OpenIPC/aviateur)（圖傳收包：devourer + wfb-ng） | `third_party/aviateur`（子模組） | GPL-3.0 |
| ffmpeg-sys-next 9.0.1（加了 Windows 空 stub） | `vendor/ffmpeg-sys-next-9.0.1` | WTFPL（FFmpeg 本身是 LGPL/GPL） |
| ESP-IDF usb_host_hid（加了中斷 OUT 報告） | `firmware/wheel-esp32/components/usb_host_hid` | Apache-2.0 |
| ESP-IDF、LVGL、微雪 BSP 等元件 | 由 ESP-IDF 元件管理器下載 | Apache-2.0 / MIT 等 |
| Noto Sans SC、Saira、Barlow Condensed（產生的點陣字形） | `firmware/wheel-esp32/main/fonts` | SIL Open Font License 1.1 |

MOZA、Thrustmaster、ExpressLRS、OpenIPC、微雪等名稱只用來說明相容的硬體，跟本專案沒有關係。

**免責聲明：** 遙控車有速度、有重量，改裝涉及電池和無線電發射。照本專案操作造成的損壞或傷害，請自行負責；無線電發射請遵守當地法規。
