# Nothing Phone (1) — M5 target profile

Owner decision 2026-10-14. No pre-design observations exist; the gate is
waived. The committed blank usability template stays unchanged.

## Assumptions until measured on the real device

| Fact | Assumption supplied by Gautham |
| --- | --- |
| Screen | 6.55-inch OLED, 1080 × 2400 physical pixels, up to 120 Hz |
| Chip / GPU | Snapdragon 778G+ / Adreno 642L |
| Browser | Chrome on Android |
| CSS portrait / landscape | About 412 × 915 / 915 × 412; Android display-size settings can change this |
| Device pixel ratio | About 2.625 |
| Cutout and navigation | Portrait top-left punch hole, landscape left edge; bottom gesture bar |

These are assumptions, not measured device facts. Responsive layout uses
available viewport and safe-area env values, never a model-specific width.

## Measurement status

At M5.1 preflight system `adb` was unavailable. A local adb and its Android
libraries were unpacked under `~/coco_labs_ws/m5-tools/adb/` without sudo
or changing system packages. `adb devices -l` reports an empty device list.
Real phone: **not connected / not measured**. Phone acceptance stays pending: connect phone over USB with USB
debugging enabled (adb access is now available). Emulation cannot satisfy it.

The shared emulation profile will record 4× CPU throttling as a chip proxy,
not Adreno GPU emulation, and emulated 4G. All reports use the label
“emulated Nothing Phone (1)”. Real CDP measurements record innerWidth,
innerHeight, devicePixelRatio, screen dimensions/orientation, computed
safe-area values, Chrome version, network, battery and temperature when
available. No inferred physical measurements are marked measured.

Provisional phone defaults (subject to M5.11 measurements): 60 fps cap,
optional 120 fps; automatic quality from measured frame time, tier pixel
ratio cap; haptics on where supported, sound off. These are choices, not
verified heat/performance results.
