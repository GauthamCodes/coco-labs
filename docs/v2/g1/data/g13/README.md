# G1.3 — Play HUD inputs and touch-to-motion latency

Harness: `lab_web/tools/g1/input_check.mjs` (raw results: [`input/checks.json`](input/checks.json),
screenshot `input/touch.png`). Evidence class **TESTED** for the controls; the latency rows
are an **emulated** profile on the **cloud container's software renderer** (Chromium
SwiftShader, Xeon 2.1 GHz × 4, no GPU): not a phone, not the laptop.

## Controls, checked against what the model reports

| Case | Result |
| --- | --- |
| 1 one-finger drive | pass |
| 2 second finger on STOP while driving: STOP wins | pass |
| 2b a hold on STOP releases it | pass |
| 3 joystick nudge: the base follows past the ring | pass |
| 4 minimap goal set (tap minimap, tap map, GO) | pass |
| 1-4 no console or page errors | pass |
| 5 gamepad: stick drives, B is STOP | pass |
| 6 keyboard-only playthrough | pass |

Each case reads the model's own tick (command source, speed, mode) through
`window.__cocoGame.tick`: e.g. a second finger on STOP while the first thumb is still on
the stick leaves the model at v = 0 (STOP wins), and only a hold on STOP releases it.

## Touch-to-motion (M4.10's definition, the one M5 reported)

`perf.inputToMotion`: a drive input with the robot at rest → the end of the first frame that
draws the robot somewhere else. Same machine, same emulated Nothing Phone (1) landscape
profile (viewport, touch, **4× CPU throttle**), same harness, 20 trials each:

| Play | Samples | Median (ms) | All samples (ms) |
| --- | --- | --- | --- |
| G1 (`?view=play&game=fetch_rush`, medium tier) | 18 | 127.8 | 98, 102, 105, 107, 111, 116, 118, 122, 123, 128, 132, 133, 134, 136, 273, 312, 326, 330 |
| M5 (`?view=arena`) | 19 | 320.2 | 190, 238, 267, 273, 287, 299, 304, 304, 311, 320, 327, 328, 330, 335, 336, 361, 374, 382, 392 |

**G1 is not worse than M5 here.** Samples are fewer than trials when a trial began before the
robot was at rest for three frames (the definition refuses such a reading).

How it got there (all measured on this machine, recorded in the session): the first G1 build
measured 557 ms against M5's 364 ms (2 trials each), then 349 vs 297.5 ms (20 trials) after
moving the model's pacing off the frame loop and dropping MSAA below high. A breakdown showed
the touch waiting for 200–370 ms frames (SwiftShader + 4× throttle); the cost was per-pixel
shading. Below the high tier G1 now shades with Lambert (no specular), keeps the headlight as a
floor light pool (the spot light is high-tier only) and caps medium at 1.25× pixels.

M5's own committed figure (82.9 ms median, laptop GPU, `docs/v2/data/m5/close/phone-ten-minutes-visible/`)
is not comparable with these cloud numbers; the laptop rerun is pending.
