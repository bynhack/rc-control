# 电脑端

[English](../en/desktop-app.md) | [繁體中文](../zh-TW/desktop-app.md) | **简体中文**

电脑端用 Rust 写，界面是 egui 原生窗口。它把 CRSF 发给 ExpressLRS 高频头，并用 USB 网卡直接接收 OpenIPC 图传。可以用窗口里的滑条、MOZA R5 或 Thrustmaster T300RS 方向盘操作。用[独立控制器](wheel-controller.md)的话，不需要它。

界面是深色仪表盘：

- **中间**：油门仪表和转向条；有图传时切成画面。
- **左边**：链路状态、图传网卡、30 秒的链路历史。
- **右边**：解锁、速度挡、方向反转，以及正在发送的数值。

![电脑端控制台](../dashboard.png)

## 高频头

| 高频头 | 接法 | 配置 |
|---|---|---|
| Jumper AION Nano（USB 已改成 CRSF 串口） | 直接插 USB | `port = "auto"`，115200 baud，20 ms |
| BETAFPV Micro TX 等外置高频头 | USB 转串口模块的 TXD → 高频头 CRSF 脚（3.3 V 电平） | 写死端口，400000 baud，4 ms |

只接了 TXD、没有 RXD 回传线时，程序收不到高频头的回复，左边会显示 **TX ONLY**。控制照常，只是读不到链路质量。

## 编译和运行

需要 CMake、libusb、libsodium 和 FFmpeg 开发库。macOS 上：

```bash
brew install cmake libusb libsodium ffmpeg
git submodule update --init third_party/aviateur
git -C third_party/aviateur submodule update --init 3rd/devourer
cargo build --release
./target/release/rc-control                # 打开控制窗口
./target/release/rc-control --list-ports   # 列出串口和 USB 编号
```

Aviateur 只需要拉它的 devourer 子模块，不用拉 SDL 等其他部分。

程序动态链接 Homebrew 的 FFmpeg。Homebrew 把 FFmpeg 升到新的大版本后，要重新 `cargo build`。

macOS 上 `cargo build` 报 Xcode 许可证错误时，在终端运行一次 `sudo xcodebuild -license` 同意许可，或改用命令行工具编译：`DEVELOPER_DIR=/Library/Developer/CommandLineTools cargo build --release`。

## 配置

把 [`rc-control.example.toml`](../../rc-control.example.toml) 复制成 `rc-control.toml`，放在当前目录或程序旁边。每个选项在文件里都有说明；不放这个文件就全部用默认值。

串口默认 `auto`，按 CH9102 的 USB 编号（`1a86:55d4`）找 AION Nano。经 USB 转串口模块接的高频头，要在 `[elrs]` 里写明端口和波特率。

## 安全规则

全部集中在 `src/control.rs`，任何后端都绕不过去：

- **解锁**：启动时油门锁定。解锁要求输入心跳正常、油门在中位。
- **输入中断**：输入超过 `heartbeat_timeout_ms`（默认 300 ms）没更新，输出立刻回中、油门锁定。输入恢复后也不会自动解锁，必须重新解锁。窗口每一帧都发心跳，所以窗口最小化或卡住时心跳就会断。
- **油门滑条**：只有按住鼠标拖动时才保持，一松开就回零。
- **急停**：锁定并让方向、油门回中。窗口里按空格键也是急停，而且空格键不会触发任何按钮。
- **退出**：关闭窗口或按 Ctrl+C 时，会先归零、发几帧中位，再关闭串口和图传网卡。

程序被强制结束（kill -9、断电、死机）也是安全的：高频头收不到数据就停止发射，接收机触发失控保护，车会停。

## 图传

程序在 UDP `5600`（配置在 `[video]`）接收 RTP 视频，默认 H.265，也支持 H.264，用 FFmpeg 解码。收到画面时，中间面板切到图传样式：上方是状态条，中间是原比例的画面，下方是油门和转向。超过 1 秒没有画面，就切回仪表盘。

**内置图传接收**（`[radio]`）直接驱动 RTL8812AU 这类 USB 网卡接收 OpenIPC 图传，不用再开 Aviateur。收包部分就是 Aviateur 的代码（devourer 用户态驱动加 wfb-ng），以子模块放在 `third_party/aviateur`，原样编译，只把它的界面接口换成 `native/gui_interface.h`。左边面板的“图传 RADIO”显示网卡、信道和链路质量。

- 默认信道 161（5805 MHz）、20 MHz、OpenIPC 默认密钥，要和摄像头一致。
- 不能和外部的 Aviateur 同时用，两边会抢同一块网卡和 UDP 8001。
- 网卡卡死、连续几次启动失败时，界面会提示拔插网卡。

想继续用外部 Aviateur：把 `[radio] enabled` 设成 `false`，在 Aviateur 里打开 Forward RTP，端口设成 5600。

没有摄像头时，可以用 FFmpeg 推测试画面：

```bash
ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=60 -c:v libx265 -preset ultrafast -tune zerolatency -x265-params keyint=30:repeat-headers=1 -f rtp -pkt_size 1400 rtp://127.0.0.1:5600
```

## 方向盘

接上 MOZA R5／R5 Pro（底座 `346e:0004`）或 Thrustmaster T300RS（底座 `044f:b66e`）就自动接管方向和油门：油门踏板减刹车踏板就是油门量。程序直接读 HID 报告。两台都插着时用 MOZA。250 ms 没有新数据（拔线）时，控制回到窗口的滑条，油门照常回零。配置在 `[wheel]`。

## 排查命令

```bash
./target/release/rc-control --probe-wheel   # 记录方向盘和踏板的 HID 报告，生成 wheel-trace.csv
./target/release/rc-control --probe-video   # 只收图传 10 秒，打印码率、帧率、解码耗时
./target/release/rc-control --probe-elrs    # 发 250 帧中位 CRSF，并打印收到的回复
```

## Windows

用 MSYS2 UCRT64 工具链编译。

1. 把 MSYS2 装到 `C:\msys64`，再一次装好依赖：
   ```
   C:\msys64\usr\bin\pacman.exe -S --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-llvm mingw-w64-ucrt-x86_64-libusb mingw-w64-ucrt-x86_64-libsodium mingw-w64-ucrt-x86_64-ffmpeg mingw-w64-ucrt-x86_64-rust
   ```
2. 编译：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 --release
   ```
   得到 `target\release\rc-control.exe`。脚本负责设置 UCRT64 的 PATH、pkg-config、CMake（Ninja）和 libclang。国内网络建议把 `%USERPROFILE%\.cargo\config.toml` 的 crates.io 源换成国内镜像。
3. 发布前，把 FFmpeg、libusb、libsodium 的 DLL 复制到 exe 旁边，就不再需要 MSYS2：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy-dlls.ps1
   ```

Release 版双击运行不会弹出命令行窗口，中文用微软雅黑显示。

- CH9102（AION Nano）在设备管理器里没有出现 COM 口时，要装 WCH 的 CH343SER 驱动。端口也可以写死成 `COM5` 这样的名字。
- RTL8812AU 网卡必须绑定 WinUSB 或 libusbK 驱动，Realtek 的 Wi-Fi 驱动（RtlWlanu）打不开 USB。可以用 Zadig 替换，或用仓库里的脚本（会弹出 UAC 确认）：
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\bind-8812au-winusb.ps1
  ```
  绑定后系统里就没有这块 Wi-Fi 网卡了，这是预期的。脚本执行前会把原来的注册表导出到 `scripts\rtl8812au-before-winusb-<时间>.reg`；想换回 Realtek 驱动时双击它，再拔插网卡。检查方法：`Get-PnpDevice | ? InstanceId -match 'VID_0BDA'` 的 Service 应该是 `WinUSB`。

本仓库为 Windows 做的改动，见[开发](development.md#电脑端编译备注)。
