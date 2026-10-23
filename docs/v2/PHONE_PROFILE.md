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

## M5.6 implementation (provisional until the real heat run)

Play starts automatic quality at medium: drawing-buffer DPR cap 1.5, high 2,
low 1. The existing measured-frame controller selects tiers and can fall back
to top-down; persistent known-visible stalls now participate in that decision.
Phone rendering defaults to 60 submitted frames/s, with an optional 120 setting.
Haptics default on; sound stays off. Fullscreen/orientation requests fail silently
and the portrait rotate card remains usable. Touch travel has a 0.14 dead zone
rescaled continuously to full travel. These are implementation settings, not
measured device performance or heat results. The original self-hosted app icon
and manifest are recorded in DESIGN_ASSETS.json.

M5.6 ADB check: no real phone connected. Phone criterion still pending USB.

## M5.11 closure

[ADB check on 2026-10-19](data/m5/phone/ADB_CHECK_M511_2026-10-19.txt) still lists no device. Real viewport/safe-area/Chrome/network/battery/temperature, real touch latency and real one/ten-minute frame-rate measurements remain pending USB. The agent will measure automatically when available; no manual owner measurements requested.

Default choices remain provisional: 60 fps (optional 120), automatic tier starting medium with DPR cap 1.5; high cap 2 and low cap 1. These are shipped settings, not a conclusion about phone heat. The real ten-minute heat run alone can finalize them. Emulated results and their limitations are linked from M5_RESULTS.md.

## Measured on the real device (G1.13, 2026-10-23)

Nothing Phone (1) A063, Android 15 (Nothing OS V3.2), Chrome 156.0.8078.47, Adreno 642L, over USB
(`lab_web/tools/phone/real_phone.mjs` and the DevTools-free `real_phone_free.mjs`; evidence
`docs/v2/g1/data/g113/README.md` §5, `docs/v2/g1/G1_REVIEW.md`). Gautham's display size is
enlarged (density 478 against the physical 420), which changes the CSS viewport:

| Fact | Assumption above | Measured |
| --- | --- | --- |
| CSS viewport, portrait in a tab | ~412 × 915 | 361 × 654 (screen 362 × 804) |
| CSS viewport, landscape in a tab | ~915 × 412 | 710 × 269 (Chrome's address bar and system bars stay) |
| CSS viewport, landscape full screen | — | 803 × 361 |
| Device pixel ratio | ~2.625 | 2.9875 |
| Cutout and navigation | landscape left edge; bottom gesture bar | landscape safe area left 46 px (the punch hole), others 0; 3-button navigation bar on this phone |
| Browser full screen | requested on game start | granted on a real tap; **while DevTools is attached Chrome keeps its bars** (measure without it) |

Defaults, set from the real 10-minute full-screen run: **tier medium** (drawing pixel ratio 1.25)
and **a 60 fps cap** (60 fps median, frame p95 19.2 ms, 0 context losses; skin 36 → 43 °C while
charging). Uncapped (120 fps) and at *high* the phone ran hotter and slower (73 fps median at high
and 120). Layout must work down to 269 CSS px of height (iPhone Safari and refused full screen):
the HUD scales below 320 px, checked in CI at 710 × 269.
