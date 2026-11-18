# Development

**English** | [繁體中文](../zh-TW/development.md) | [简体中文](../zh-CN/development.md)

## Firmware layout

All in [`firmware/wheel-controller/main`](../../firmware/wheel-controller/main):

| File | Role |
|---|---|
| `main.c` | Boot, USB host, and the hand-off from the wheel to the driving model |
| `wheel.c` | Parses the wheel base's HID reports (MOZA R5, T300RS) |
| `control.c` | The driving model and every safety rule. The radios only read `control_output()` |
| `radio.c` | Cars, settings in NVS, and the handling every radio goes through |
| `crsf.c` | ExpressLRS (CRSF) sender |
| `multi.c` | MULTI 4-in-1 sender, serial or PPM |
| `remote.c` | Toy remote through the MCP4728 DAC, and the serial console |
| `ffb.c` | Force feedback (USB PID on the MOZA, Thrustmaster's protocol on the T300) |
| `sound.c` | Engine sound synthesis |
| `display_p4.c`, `dash_p4.c`, `ui_p4.h` | Settings screens, instrument clusters, on-screen text in both languages |

`components/usb_host_hid` is a copy of Espressif's usb_host_hid 1.2.1 with two additions, explained under [Force feedback](#force-feedback).

### The signal path

```
wheel.c → control.c (driving model, safety) → radio.c (handling) → crsf.c / multi.c / remote.c
```

A new way of reaching a car only needs a sender that reads `control_output()`, passes it through `radio_steering()` and `radio_throttle()`, and turns the resulting −1…+1 into its own signal. Add it to `radio_kind_t` in `radio.h`, and it gets cars, handling, reverse and the safety rules for free.

### Responsiveness comes first

Nothing may delay the radio. The senders run on core 1 at the highest priorities:

| Task | Core | Priority |
|---|---|---|
| `crsf` | 1 | 10 |
| `multi` | 1 | 9 |
| `sound` | 0 | 6 |
| `ffb` | 0 | 4 |
| `remote` | 1 | 4 |
| `usb_lib` | 0 | 2 |
| `remote_con` (serial console) | 1 | 2 |
| `ui` | 1 | 1 |

The tuning page and the console sit below every sender, so they can't slow the car's response down. A simulated wheel (`w`) is ignored whenever the real wheel has sent data within the last 0.5 s.

### Force feedback

The force feedback reports have to go out on the HID interface's interrupt OUT endpoint (0x03 on the R5). If you send them with SET_REPORT on the control pipe, the R5 answers OK and does nothing. ESP-IDF's usb_host_hid doesn't support OUT endpoints, so `components/usb_host_hid` adds `hid_host_device_send_output_report()`. The effects also need their direction enabled and set to 90° (the X axis); otherwise the spring and damper have no force.

The T300RS follows Linux's hid-thrustmaster and hid-tmff2. When plugged in, it shows up as `044f:b65d`. The firmware reads its model with a vendor request and sends the switch request, which ESP-IDF can't do either, so `components/usb_host_hid` also adds `hid_host_device_vendor_request()`. The base comes back as `044f:b66e`. Its force feedback is output report 0x60 on the same OUT endpoint, in Thrustmaster's own format: open, autocentre off, range 900°, then the three condition effects uploaded, started, and updated.

## Serial console

The console is on the log port ("USB TO UART", 115200), one command per line:

| Command | Does |
|---|---|
| `w <steer> <gas> <brake>` | A simulated wheel sample (−1…1, 0…1, 0…1) through the same driving model as the real wheel. Send it every 50 ms. Ignored while the real wheel has sent data within 0.5 s |
| `k start` / `k up` / `k down` / `k stop` | Ignition, gear up, gear down, emergency stop |
| `d <A> <B>` | Set the two DAC codes directly (0–4095). Goes back to the wheel after 1.5 s without a new one |
| `x` | Go back to the wheel at once |
| `name <text>` | Rename the active car |
| `kind <0–3>` | The active car's radio: 0 ELRS, 1 4-in-1 serial, 2 4-in-1 PPM, 3 toy remote |
| `dead <left> <right> <forward> <reverse>` | The active car's steering and throttle dead bands, in thousandths |
| `scan` | List every address answering on the I2C bus. Normally only the touch panel (0x14 or 0x5D) and the DAC (0x60). Dozens of addresses mean something is dragging the bus, usually a loose or misplaced wire |

## Tuning page

[`tools/remote_tune.html`](../../firmware/wheel-controller/tools/remote_tune.html) is a bench page that talks to the console. Open it in Chrome, which has Web Serial, served from a local server:

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory firmware/wheel-controller/tools
```

Open http://localhost:8765/remote_tune.html and press Connect (連接 P4).

- **Simulated driving** (模擬駕駛): drag the wheel, press the pedals, start the engine and shift. The keyboard works too: A/D steer, W/S throttle and brake, Enter starts the engine, Q/E shift, Space is the emergency stop. It goes through the same path as the real wheel and shows the engine, gear, speed and output.
- **Fine-tune DAC** (精調 DAC): a zoomable axis per DAC channel (⌘ or Ctrl + scroll, or pinch). Each scroll step moves the output by ±1, or ±10 with Shift. You mark each channel's ends and dead band edges on it. See [Converting a toy remote](toy-remote.md#calibration).

When you're done, press Disconnect (斷開). Otherwise the page keeps the serial port and flashing fails.

## Fonts and dashboard images

- **Fonts**: `main/fonts/gen_fonts.sh <font dir>` regenerates the bitmap fonts with `lv_font_conv` (needs Node). The CJK fonts only contain the characters that appear in the sources, so run it after you add on-screen text. The font directory needs Noto Sans SC Medium, plus Saira and Barlow Condensed for the dashboard digits. Download links are at the top of the script.
- **Dashboard images**: the static layers are drawn in `design/render/dash_render.html`. `design/render/build_assets.py` renders them in headless Chrome and writes `main/assets/*.bin`. It needs Google Chrome, Pillow and numpy.

## Protocol notes

- **CRSF**: address `0xEE`, CRC8 polynomial `0xD5`. Channel values 172 / 992 / 1811 are 988 / 1500 / 2012 µs. ELRS only sends channels 1–4 at full resolution.
