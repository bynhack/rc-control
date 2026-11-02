# 硬件

## x2201-carrier

极客者 X2201（1:22 四驱攀爬车）改装用的无源转接板：不放芯片，只把电池、电源开关、ZERO-Z 电调、电机、ELRS 接收机（Lite RX 当 2 路 PWM）、舵机、车灯和图传供电接到一块板上，减少飞线。

- 原理图由 `gen_sch.py` 生成（KiCad 10），改连线就改脚本再运行；`x2201-carrier.pdf` 是导出的原理图。
- 目前只有连线，PCB 布局等零件实测尺寸后再画。
- 电机大电流走电调自己的线，1oz 铜厚就够。

```bash
python3 hardware/x2201-carrier/gen_sch.py
kicad-cli sch erc hardware/x2201-carrier/x2201-carrier.kicad_sch
kicad-cli sch export pdf -o hardware/x2201-carrier/x2201-carrier.pdf hardware/x2201-carrier/x2201-carrier.kicad_sch
```

`gen_sch.py` 里的 KiCad 符号库路径是 macOS 的默认安装位置，其他系统要改 `LIB`。
