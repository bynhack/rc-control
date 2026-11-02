# Driving and handling

**English** | [繁體中文](../zh-TW/driving.md) | [简体中文](../zh-CN/driving.md)

## Controls (MOZA R5)

| Button | HID number | Function |
|---|---|---|
| Start | 36 | Start or stop the engine. It only starts in N with both pedals released |
| Right / left paddle | 14 / 13 | Gear up / down: R N 1 2 3 |
| P | 32 | Emergency stop |
| N | 19 | Bind, in 4-in-1 serial mode |

The right pedal (Z axis) is the throttle and the left pedal (Rz) is the brake.

## The driving model

The model lives in `control.c` and drives like a real car:

- Gears 1, 2 and 3 give 33, 67 and 100 % of full power. R gives 40 %.
- The car only reverses with the throttle pressed in R. To change direction, stop the car first.
- Releasing the throttle lets the car coast and slow down gradually. The brake only brakes.
- Set the ESC to forward / brake / reverse mode. When you shift into R, the firmware sends brake, then neutral, then reverse, so the ESC actually reverses.
- The speed on the dashboard is estimated from the model. There is no speed sensor on the car.

### Safety

The safety rules are in `control.c`, and no radio can bypass them:

- The engine is off at power-up.
- If no wheel data arrives for 300 ms, the car is centred and the engine stops. When the wheel comes back, you have to start the engine again.
- An emergency stop always centres steering and throttle.

## Cars

The first settings tab, **Cars** (车辆), holds six cars. Tap one to switch to it. Each car keeps its own:

- radio and the radio's settings
- top speed (used to show km/h)
- engine sound
- everything on the **Handling** (操控) tab

Language, volume, force feedback strength, screen flip and the ELRS wiring belong to the controller and apply to every car.

## Handling

Handling sits between the driving model and the radio, and **it is the same for every radio**. Each radio only turns the final −1…+1 into its own signal: CRSF channels, PPM, MULTI channels or DAC voltages. A new radio added later goes through the same settings.

```
Steering: wheel → range → expo → dead band → trim → end points → reverse → radio
Throttle: driving model → dead band → reverse → radio
```

| Setting | Range | What it does |
|---|---|---|
| **Wheel range** (方向盘转角) | 90–900°, default 900° | How far you turn the wheel for full lock. Past it, force feedback holds the wheel with a soft stop, and the centring spring gets stronger by 900 / range, up to 2.5×. Larger is calmer, smaller is quicker |
| **Expo** (中心柔和) | 0–80 % | Softer steering around the centre, for steadier straights |
| **Steering dead band** (方向死区) | left and right, up to 50 % | For steering that doesn't move until the wheel is turned a little. Once set, the wheels move as soon as the wheel does |
| **Trim** (方向回正) | up to 30 % of full lock | Like the trim knob on a stock radio, for a car that doesn't run straight |
| **End points** (舵量) | left and right, 30–100 % of full lock | Where full lock is, so the servo doesn't stall at its stop, and so left and right match |
| **Throttle dead band** (油门死区) | forward and reverse, up to 80 % | The span around the ESC's neutral where the car doesn't move. Output = dead band + throttle × (1 − dead band), so the car moves as soon as you press the pedal; the gear only limits top speed. The brake isn't affected |
| **Reverse** (反转) | per radio, on the Radio tab | Reverses steering or throttle |

### Setting them on the car

Each setting is set with the wheel or the pedals while the car is running:

- **Steering dead band**: press **Set with wheel** (用方向盘调). Turn slowly left from centre and press **Save left** (存左) when the wheels start to move. Do the same to the right with **Save right** (存右).
- **Trim**: press **Set with wheel**, hold the wheel where the car runs straight and press **Save** (保存). Force feedback then pulls the wheel back to the centre.
- **End points**: press **Set with wheel**, turn until the wheels just reach their stop and press **Save left** / **Save right**.
- **Throttle dead band**: press **Set with throttle** (用油门调). In gear 1, press the pedal slowly and press **Save** when the car starts to move. Then do it again in R for reverse. While you set it, the pedal goes straight to the output, up to 90 %.

While you set one of them, that setting itself is left out. What you see is the position before it is applied.

## Force feedback

The MOZA R5 gets standard USB PID effects:

- a spring that centres the wheel and gets stronger with speed
- a damper
- a third spring with a dead band, which acts as the soft stop at the wheel range

The strength is on the **Drive** (驾驶设置) tab, default 40 %. How the reports reach the base is in [Development](development.md#force-feedback).

## Dashboard and engine sound

- Two instrument clusters, Obsidian and Carbon. Swipe left or right to switch.
- The engine sound is synthesised live from the driving model, with no recordings. There are three voices: a road car, a rally car and a BMW M4. Each car picks its own.
- The screen text is in Simplified or Traditional Chinese. Switch with the 简体 / 繁體 buttons at the top right of the settings screen.
