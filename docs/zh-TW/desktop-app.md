# 電腦版

[English](../en/desktop-app.md) | **繁體中文** | [简体中文](../zh-CN/desktop-app.md)

電腦版用 Rust 寫，介面是 egui 原生視窗。它把 CRSF 發給 ExpressLRS 高頻頭，並用 USB 網卡直接接收 OpenIPC 圖傳。可以用視窗裡的滑條、MOZA R5 或 Thrustmaster T300RS 方向盤操作。用[獨立控制器](wheel-controller.md)的話，不需要它。

介面是深色儀表盤：

- **中間**：油門儀表和轉向條；有圖傳時切成畫面。
- **左邊**：鏈路狀態、圖傳網卡、30 秒的鏈路歷史。
- **右邊**：解鎖、速度檔、方向反轉，以及正在發送的數值。

![電腦版控制台](../dashboard.png)

## 高頻頭

| 高頻頭 | 接法 | 設定 |
|---|---|---|
| Jumper AION Nano（USB 已改成 CRSF 串口） | 直接插 USB | `port = "auto"`，115200 baud，20 ms |
| BETAFPV Micro TX 等外置高頻頭 | USB 轉串口模組的 TXD → 高頻頭 CRSF 腳（3.3 V 電平） | 寫死端口，400000 baud，4 ms |

只接了 TXD、沒有 RXD 回傳線時，程式收不到高頻頭的回覆，左邊會顯示 **TX ONLY**。控制照常，只是讀不到鏈路品質。

## 編譯和執行

需要 CMake、libusb、libsodium 和 FFmpeg 開發庫。macOS 上：

```bash
brew install cmake libusb libsodium ffmpeg
git submodule update --init third_party/aviateur
git -C third_party/aviateur submodule update --init 3rd/devourer
cargo build --release
./target/release/rc-control                # 打開控制視窗
./target/release/rc-control --list-ports   # 列出串口和 USB 編號
```

Aviateur 只需要拉它的 devourer 子模組，不用拉 SDL 等其他部分。

程式動態連結 Homebrew 的 FFmpeg。Homebrew 把 FFmpeg 升到新的大版本後，要重新 `cargo build`。

macOS 上 `cargo build` 報 Xcode 授權錯誤時，在終端機執行一次 `sudo xcodebuild -license` 同意授權，或改用命令列工具編譯：`DEVELOPER_DIR=/Library/Developer/CommandLineTools cargo build --release`。

## 設定

把 [`rc-control.example.toml`](../../rc-control.example.toml) 複製成 `rc-control.toml`，放在目前目錄或程式旁邊。每個選項在檔案裡都有說明；不放這個檔案就全部用預設值。

串口預設 `auto`，按 CH9102 的 USB 編號（`1a86:55d4`）找 AION Nano。經 USB 轉串口模組接的高頻頭，要在 `[elrs]` 裡寫明端口和波特率。

## 安全規則

全部集中在 `src/control.rs`，任何後端都繞不過去：

- **解鎖**：啟動時油門鎖定。解鎖要求輸入心跳正常、油門在中位。
- **輸入中斷**：輸入超過 `heartbeat_timeout_ms`（預設 300 ms）沒更新，輸出立刻回中、油門鎖定。輸入恢復後也不會自動解鎖，必須重新解鎖。視窗每一幀都發心跳，所以視窗最小化或卡住時心跳就會斷。
- **油門滑條**：只有按住滑鼠拖動時才保持，一放開就回零。
- **急停**：鎖定並讓方向、油門回中。視窗裡按空白鍵也是急停，而且空白鍵不會觸發任何按鈕。
- **退出**：關閉視窗或按 Ctrl+C 時，會先歸零、發幾幀中位，再關閉串口和圖傳網卡。

程式被強制結束（kill -9、斷電、當機）也是安全的：高頻頭收不到資料就停止發射，接收機觸發失控保護，車會停。

## 圖傳

程式在 UDP `5600`（設定在 `[video]`）接收 RTP 視訊，預設 H.265，也支援 H.264，用 FFmpeg 解碼。收到畫面時，中間面板切到圖傳樣式：上方是狀態條，中間是原比例的畫面，下方是油門和轉向。超過 1 秒沒有畫面，就切回儀表盤。

**內建圖傳接收**（`[radio]`）直接驅動 RTL8812AU 這類 USB 網卡接收 OpenIPC 圖傳，不用再開 Aviateur。收包部分就是 Aviateur 的程式碼（devourer 使用者態驅動加 wfb-ng），以子模組放在 `third_party/aviateur`，原樣編譯，只把它的介面接口換成 `native/gui_interface.h`。左邊面板的「圖傳 RADIO」顯示網卡、信道和鏈路品質。

- 預設信道 161（5805 MHz）、20 MHz、OpenIPC 預設密鑰，要和攝影機一致。
- 不能和外部的 Aviateur 同時用，兩邊會搶同一塊網卡和 UDP 8001。
- 網卡卡死、連續幾次啟動失敗時，介面會提示拔插網卡。

想繼續用外部 Aviateur：把 `[radio] enabled` 設成 `false`，在 Aviateur 裡打開 Forward RTP，端口設成 5600。

沒有攝影機時，可以用 FFmpeg 推測試畫面：

```bash
ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=60 -c:v libx265 -preset ultrafast -tune zerolatency -x265-params keyint=30:repeat-headers=1 -f rtp -pkt_size 1400 rtp://127.0.0.1:5600
```

## 方向盤

接上 MOZA R5／R5 Pro（底座 `346e:0004`）或 Thrustmaster T300RS（底座 `044f:b66e`）就自動接管方向和油門：油門踏板減剎車踏板就是油門量。程式直接讀 HID 報告。兩台都插著時用 MOZA。250 ms 沒有新資料（拔線）時，控制回到視窗的滑條，油門照常回零。設定在 `[wheel]`。

## 排查指令

```bash
./target/release/rc-control --probe-wheel   # 記錄方向盤和踏板的 HID 報告，產生 wheel-trace.csv
./target/release/rc-control --probe-video   # 只收圖傳 10 秒，印出碼率、幀率、解碼耗時
./target/release/rc-control --probe-elrs    # 發 250 幀中位 CRSF，並印出收到的回覆
```

## Windows

用 MSYS2 UCRT64 工具鏈編譯。

1. 把 MSYS2 裝到 `C:\msys64`，再一次裝好依賴：
   ```
   C:\msys64\usr\bin\pacman.exe -S --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-llvm mingw-w64-ucrt-x86_64-libusb mingw-w64-ucrt-x86_64-libsodium mingw-w64-ucrt-x86_64-ffmpeg mingw-w64-ucrt-x86_64-rust
   ```
2. 編譯：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 --release
   ```
   得到 `target\release\rc-control.exe`。腳本負責設定 UCRT64 的 PATH、pkg-config、CMake（Ninja）和 libclang。
3. 發布前，把 FFmpeg、libusb、libsodium 的 DLL 複製到 exe 旁邊，就不再需要 MSYS2：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy-dlls.ps1
   ```

Release 版雙擊執行不會跳出命令列視窗，中文用微軟雅黑顯示。

- CH9102（AION Nano）在裝置管理員裡沒有出現 COM 口時，要裝 WCH 的 CH343SER 驅動。端口也可以寫死成 `COM5` 這樣的名字。
- RTL8812AU 網卡必須綁定 WinUSB 或 libusbK 驅動，Realtek 的 Wi-Fi 驅動（RtlWlanu）打不開 USB。可以用 Zadig 替換，或用倉庫裡的腳本（會跳出 UAC 確認）：
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\bind-8812au-winusb.ps1
  ```
  綁定後系統裡就沒有這塊 Wi-Fi 網卡了，這是預期的。腳本執行前會把原本的登錄檔匯出到 `scripts\rtl8812au-before-winusb-<時間>.reg`；想換回 Realtek 驅動時雙擊它，再拔插網卡。檢查方法：`Get-PnpDevice | ? InstanceId -match 'VID_0BDA'` 的 Service 應該是 `WinUSB`。

本倉庫為 Windows 做的改動，見[開發](development.md#電腦版編譯備註)。
