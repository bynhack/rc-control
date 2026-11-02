# Desktop app

**English** | [繁體中文](../zh-TW/desktop-app.md) | [简体中文](../zh-CN/desktop-app.md)

The desktop app is the PC version, written in Rust with an egui window. It sends CRSF to an ExpressLRS module and shows OpenIPC FPV video, received directly from a USB Wi-Fi adapter. You can drive with the window's sliders, a MOZA R5 or a Thrustmaster T300RS wheel. You don't need it for the [standalone controller](wheel-controller.md).

The window is a dark dashboard:

- **Centre**: the throttle gauge and the steering bar. When video arrives, this panel shows the video instead.
- **Left**: link status, the FPV adapter, and a 30-second link history.
- **Right**: arming, speed range, steering reverse, and the values going out.

![Desktop app dashboard](../dashboard.png)

## Transmitters

| Module | Wiring | Config |
|---|---|---|
| Jumper AION Nano, its USB rewired as a CRSF serial port | Plug in over USB | `port = "auto"`, 115200 baud, 20 ms |
| An external module such as the BETAFPV Micro TX | A USB-serial adapter's TXD → the module's CRSF pin (3.3 V levels) | Set the port by name, 400000 baud, 4 ms |

If only TXD is wired, with no RXD line back, the app can't hear the module and the left panel shows **TX ONLY**. Driving works as usual; only the link quality is missing.

## Build and run

You need CMake, libusb, libsodium and the FFmpeg development libraries. On macOS:

```bash
brew install cmake libusb libsodium ffmpeg
git submodule update --init third_party/aviateur
git -C third_party/aviateur submodule update --init 3rd/devourer
cargo build --release
./target/release/rc-control                # open the window
./target/release/rc-control --list-ports   # list serial ports and USB IDs
```

Only Aviateur's devourer submodule is needed, not SDL and the rest.

The app links Homebrew's FFmpeg dynamically. After Homebrew upgrades FFmpeg to a new major version, run `cargo build` again.

If `cargo build` on macOS stops with an Xcode license error, run `sudo xcodebuild -license` once, or build with the command line tools: `DEVELOPER_DIR=/Library/Developer/CommandLineTools cargo build --release`.

## Configuration

Copy [`rc-control.example.toml`](../../rc-control.example.toml) to `rc-control.toml`, either in the current directory or next to the program. Every option is explained in the file. Without it, the defaults apply.

The port defaults to `auto`, which finds the AION Nano by its CH9102 USB ID (`1a86:55d4`). A module behind a USB-serial adapter needs its port and baud rate set in `[elrs]`.

## Safety

All safety rules are in `src/control.rs`, and no backend can bypass them:

- **Arming.** The throttle is locked at start. To unlock it, the input heartbeat must be healthy and the throttle at neutral.
- **Lost input.** If the input doesn't update for `heartbeat_timeout_ms` (default 300 ms), the output centres at once and the throttle locks. It stays locked when the input returns; you have to unlock it again. The window sends a heartbeat every frame, so the heartbeat stops if the window is minimised or hangs.
- **Throttle slider.** It only holds while you drag it with the mouse. When you let go, it snaps back to zero.
- **Emergency stop.** It locks the throttle and centres steering and throttle. Space in the window is also an emergency stop, and Space never presses a button.
- **Quitting.** Closing the window or Ctrl+C first zeroes the output and sends a few neutral frames, then closes the serial port and the FPV adapter.

If the app is killed (kill -9, power loss, a crash), the module stops transmitting and the receiver's failsafe stops the car.

## FPV video

The app receives RTP video on UDP `5600` (`[video]`), H.265 by default or H.264, and decodes it with FFmpeg. While video arrives, the centre panel shows it: a status bar on top, the picture at its own aspect ratio, and throttle and steering below. After 1 s without video it goes back to the dashboard.

**The built-in receiver** (`[radio]`) drives an RTL8812AU-class USB Wi-Fi adapter itself to receive OpenIPC video, so you don't need Aviateur running. The receive code is Aviateur's (the devourer user-space driver plus wfb-ng). It is a submodule in `third_party/aviateur`, built unchanged, with only its GUI interface replaced by `native/gui_interface.h`. "FPV RADIO" in the left panel shows the adapter, the channel and the link quality.

- The defaults are channel 161 (5805 MHz), 20 MHz and the OpenIPC default key. They must match the camera.
- It can't run alongside a separate Aviateur, because both would claim the same adapter and UDP 8001.
- If the adapter locks up and several starts fail in a row, the window asks you to replug it.

To use a separate Aviateur instead, set `[radio] enabled = false`, enable Forward RTP in Aviateur, and set its port to 5600.

To test without a camera, send a test picture with FFmpeg:

```bash
ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=60 -c:v libx265 -preset ultrafast -tune zerolatency -x265-params keyint=30:repeat-headers=1 -f rtp -pkt_size 1400 rtp://127.0.0.1:5600
```

## Wheel

With a MOZA R5 / R5 Pro (base `346e:0004`) or a Thrustmaster T300RS (base `044f:b66e`) plugged in, the wheel takes over steering and throttle. If both are plugged in, the MOZA is used. The throttle is the gas pedal minus the brake pedal. The app reads the HID reports directly. After 250 ms without new data (unplugged), control goes back to the window's sliders and the throttle returns to zero. Settings are in `[wheel]`.

## Diagnostic commands

```bash
./target/release/rc-control --probe-wheel   # record wheel and pedal HID reports into wheel-trace.csv
./target/release/rc-control --probe-video   # receive video for 10 s, print bitrate, frame rate, decode time
./target/release/rc-control --probe-elrs    # send 250 neutral CRSF frames and print the replies
```

## Windows

Build with the MSYS2 UCRT64 toolchain.

1. Install MSYS2 to `C:\msys64` and install the dependencies once:
   ```
   C:\msys64\usr\bin\pacman.exe -S --noconfirm mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-clang mingw-w64-ucrt-x86_64-llvm mingw-w64-ucrt-x86_64-libusb mingw-w64-ucrt-x86_64-libsodium mingw-w64-ucrt-x86_64-ffmpeg mingw-w64-ucrt-x86_64-rust
   ```
2. Build:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 --release
   ```
   This produces `target\release\rc-control.exe`. The script sets up the UCRT64 PATH, pkg-config, CMake (Ninja) and libclang.
3. Before you ship it, copy the FFmpeg, libusb and libsodium DLLs next to the exe, so it no longer needs MSYS2:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\deploy-dlls.ps1
   ```

The release build starts without a console window and shows Chinese in Microsoft YaHei.

- If the CH9102 (the AION Nano) doesn't show up as a COM port in Device Manager, install WCH's CH343SER driver. You can also set the port by name, such as `COM5`.
- The RTL8812AU adapter must use the WinUSB or libusbK driver; Realtek's Wi-Fi driver (RtlWlanu) can't open it over USB. Switch it with Zadig, or with the script in the repository, which asks for UAC:
  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\bind-8812au-winusb.ps1
  ```
  Afterwards the adapter no longer appears as a Wi-Fi adapter, which is expected. The script first saves the old registry entries to `scripts\rtl8812au-before-winusb-<time>.reg`. To go back to the Realtek driver, double-click that file and replug the adapter. To check: `Get-PnpDevice | ? InstanceId -match 'VID_0BDA'` should show the service as `WinUSB`.

The Windows-specific changes in this repository are listed in [Development](development.md#desktop-app-build-notes).
