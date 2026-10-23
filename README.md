# rc-control

电脑端遥控车控制程序。同一套控制逻辑，可以切换两种发送方案：

| 方案 | 硬件 | 方式 |
|---|---|---|
| `elrs` | Jumper AION Nano 高频头（USB 已改为 CRSF 串口）→ ELRS PWM 接收机 | 每 20 ms 发一帧 16 通道 CRSF，115200 |
| `rc2` | MR-RC2 控制器（CH340） | 请求/应答协议，只在值变化时写，460800 |

界面是原生窗口（egui），深色仪表盘风格：中间是油门仪表和转向条，左边是链路状态和 30 秒链路历史，右边是解锁、速度档、灯光和线上发送的值。方向盘（T300）以后作为另一个输入源，接到同一个控制层。

![控制台](docs/dashboard.png)

## 运行

```bash
cargo build --release
./target/release/rc-control              # 打开控制窗口
./target/release/rc-control --backend rc2
./target/release/rc-control --list-ports # 看串口和 USB 编号
```

配置：复制 `rc-control.example.toml` 为 `rc-control.toml`，放在当前目录或程序旁边。不放就用默认值。串口默认 `auto`，按 USB 芯片编号自动找：

- 高频头 CH9102 `1a86:55d4`
- RC2 控制器 CH340 `1a86:7523`

**macOS 上 `cargo build` 报 Xcode 许可证错误时：** 在终端运行一次 `sudo xcodebuild -license` 同意许可，或者临时改用命令行工具编译：`DEVELOPER_DIR=/Library/Developer/CommandLineTools cargo build --release`。

## Windows

在 Windows 上装好 Rust（https://rustup.rs ），在项目目录运行 `cargo build --release`，得到 `target\release\rc-control.exe`。分发时把 exe 和 `rc-control.toml` 放在同一个文件夹即可，不需要别的运行环境。Release 版双击运行不会弹出黑色命令行窗口。界面用系统自带的微软雅黑显示中文。

- CH340（RC2）的驱动一般由 Windows 更新自动安装。
- CH9102（高频头）如果设备管理器里没有出现 COM 口，要装 WCH 的 CH343SER 驱动。
- 配置里也可以把端口写死成 `COM5` 这样的名字。

## 图传

程序在 UDP `5600`（配置 `[video]`）接收 RTP 视频（默认 H.265，也支持 H.264），用 FFmpeg 解码。收到画面时，中间面板切到图传样式：上方状态条，中间是原比例画面，下方是油门和转向；超过 1 秒没有画面，就自动切回仪表盘。

**内置图传接收（`[radio]`）：** 程序直接驱动 RTL8812AU 这类 USB 网卡收 OpenIPC 图传，不需要再开 Aviateur。收包部分就是 Aviateur 的代码（devourer 用户态驱动 + wfb-ng），以子模块形式放在 `third_party/aviateur`，原样编译，只把它的界面接口换成 `native/gui_interface.h`。左边面板的「图传 RADIO」显示网卡、信道和链路质量。

- 默认信道 161（5805 MHz）、20 MHz、OpenIPC 默认密钥，要和摄像头一致。
- 和外部 Aviateur 不能同时用：两边会抢同一块网卡和 UDP 8001。
- 网卡卡死、连续几次启动失败时，界面会提示拔插网卡。
- 对上游的一处修正：Aviateur 停止链路后不会关闭 UDP 8001，同一进程里再次启动会直接崩溃。构建时会给复制出来的 `tx_frame.cpp` 补上关闭代码（见 `native/CMakeLists.txt`），子模块里的源码保持不动。

也可以继续用外部 Aviateur：把 `[radio] enabled` 设成 `false`，在 Aviateur 里打开 Forward RTP，端口设成 5600。

```bash
./target/release/rc-control --probe-video   # 只收图传 10 秒，打印码率、帧率、解码耗时
```

没有摄像头时，可以用 FFmpeg 推测试画面：

```bash
ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=60 -c:v libx265 -preset ultrafast -tune zerolatency -x265-params keyint=30:repeat-headers=1 -f rtp -pkt_size 1400 rtp://127.0.0.1:5600
```

**获取源码：** 克隆后要拉取 Aviateur 子模块（只需要它的 devourer，不用拉 SDL 等）：

```bash
git submodule update --init third_party/aviateur
git -C third_party/aviateur submodule update --init 3rd/devourer
```

**依赖：** 编译需要 CMake、libusb、libsodium 和 FFmpeg 开发库（macOS 上 `brew install cmake libusb libsodium ffmpeg`）。现在程序动态链接 Homebrew 的 FFmpeg；Homebrew 升级 FFmpeg 大版本后，要重新 `cargo build`。正式分发前要把 FFmpeg 库一起打包。

## 安全规则

全部集中在 `src/control.rs`，两种方案共用，后端绕不过去：

- 启动时油门锁定。解锁要求输入心跳正常、油门在中位。
- 输入超过 `heartbeat_timeout_ms`（默认 300 ms）没更新：输出立即回中，油门锁定。之后输入恢复了也不会自动解锁，必须重新解锁。窗口每一帧都发心跳，最小化或卡住时心跳就会断。
- 油门滑条只有按住鼠标拖动时才保持，松开立即回零。
- 急停：锁定并让转向、油门回中。窗口里按空格键也是急停，而且空格不会触发任何按钮。
- 切换方案时自动锁定。
- 关闭窗口或 Ctrl+C 退出时，都会先归零再关串口。RC2 会一直保持最后写入的值，所以这一步对它尤其重要。
- RC2 油门回零时不带速率限制，立即生效；其他油门变化带 `throttle_rate`。

**已知限制：** 程序被强制结束（kill -9、断电、蓝屏）时：

- ELRS：高频头收不到数据就停止发射，接收机触发失控保护，车会停。
- RC2：设备端有没有超时保护还不清楚，可能保持最后的油门值。

## 结构

```
src/
  control.rs        与方案无关的控制状态和全部安全规则
  config.rs         配置文件
  protocol/crsf.rs  CRSF 组帧、解析（链路质量、设备名、模块复位）
  protocol/rc2.rs   RC2 协议，每次 2 个字符流水线发送，含模拟设备测试
  backend/elrs.rs   定时发送线程
  backend/rc2.rs    变化写入 + 逐个读取遥测
  gui/mod.rs        窗口布局和交互
  gui/widgets.rs    自绘组件：仪表、转向条、滑条、信号条、链路历史
  gui/theme.rs      配色、深色主题、字体（中文用苹方/微软雅黑，数字用 DIN/Bahnschrift）
  gui/dev.rs        开发用：自动截图、演示输入
  video/rtp.rs      RTP 重组成 H.264/H.265 帧（丢包时丢弃残缺分片）
  video/decoder.rs  FFmpeg 低延迟解码，转 RGBA
  video/mod.rs      收流线程、统计
  radio/mod.rs      内置图传：网卡选择、启动、断线重连、状态
native/             C++ 层：编译 Aviateur 的收包代码，提供 C 接口（rcwfb.h）
third_party/aviateur  子模块，GPL-3.0
```

`cargo test` 运行协议、映射、安全规则的单元测试。不需要接硬件，RC2 用软件模拟设备测试。

### 调界面用的两个环境变量

- `RC_CONTROL_SNAPSHOT=out.bmp`：启动约 1.5 秒后把窗口画面存成图片，程序自己截，不需要系统录屏权限。
- `RC_CONTROL_DEMO=转向,油门[,low|mid|high]`：用假输入看仪表效果，数值范围 -1 到 1。**只要有设备连着就自动失效**，配合不存在的串口使用：

```bash
printf '[elrs]\nport = "/dev/none"\n[rc2]\nport = "/dev/none"\n' > /tmp/demo.toml
RC_CONTROL_DEMO="0.45,0.85,high" RC_CONTROL_SNAPSHOT=/tmp/ui.bmp ./target/release/rc-control --config /tmp/demo.toml
```

## 协议要点

- **CRSF**：地址 `0xEE`，CRC8 多项式 `0xD5`；通道 172 / 992 / 1811 对应 988 / 1500 / 2012 µs。ELRS 只有通道 1 到 4 是全精度，转向和油门不要放到 5 以上。
- **RC2**：每个字节拆成两个半字节字符，每个字符都要等设备回确认。实测设备最多能接住连续 2 个字符，所以每次发 2 个。写一次约 40 ms，比逐字符快约 40%。

## 许可证

GPL-3.0，见 [LICENSE](LICENSE)。图传收包部分来自 [Aviateur](https://github.com/OpenIPC/aviateur)（同为 GPL-3.0）。
