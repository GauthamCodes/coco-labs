# R1.8 Performance

Evidence class: MEASURED on this laptop (13th Gen Intel Core i5-13420H, 12 threads, 16 GB; NVIDIA GeForce RTX
4050 Laptop GPU, driver 580.178.04; Chromium (Playwright) on ANGLE/NVIDIA), power profile **balanced, on AC**
(battery full); the original profile (power-saver) was restored afterwards. Counts are device-independent;
every timing below is wall time under these conditions. Each JSON holds its start and end conditions.

## Experiments in the browser (`lab_web/tools/r1/perf_experiment.mjs`)

| Case | Runs | Workers | Wall time, Run → digest shown (statistics included) | Digest (browser = native) |
| --- | --- | --- | --- | --- |
| Laptop: A*, Dijkstra, greedy, weighted A* × `depot-nav-100` ([`laptop_4x100.json`](laptop_4x100.json)) | 400 | 6 (cores − 1, capped) | **54.3 s** | `6060a0d2bf3896a9…` = native ([`native_4x100/`](native_4x100/), 6 processes: 30.3 s) |
| Phone, **emulated** Nothing Phone (1) (viewport, touch, 4× CPU throttle on this laptop): A*, Dijkstra × 20 seeded Proving Ground pairs ([`phone_2x20_emulated.json`](phone_2x20_emulated.json)) | 40 | 2 (the phone cap) | **18.0 s** | `223e483497128464…` = native ([`native_2x20/`](native_2x20/)) |

The browser's time includes booting each worker's interpreter and the statistics; the native time is the CLI's
own. **Real phone: not measured** — no device was connected (adb: no device); pending: connect the Nothing
Phone (1) over USB with debugging on. Emulation never meets the Phone criterion.

## Play is unaffected (`lab_web/tools/g1/perf_play.mjs`, Fetch Rush, 2 min each, [`play_fps/`](play_fps/))

The baseline build (main `7bbb430` + R1.0 paperwork) and the R1 build, served side by side, same conditions:

| Run | Drawn fps median | min | Frame interval median / p99 / max (ms) | > 50 ms | Frame JS median (ms) |
| --- | --- | --- | --- | --- | --- |
| baseline, desktop high | 60.07 | 59.17 | 16.5 / 20.7 / 25.7 | 0 | 3.5 |
| **R1, desktop high** | **60.07** | **59.18** | 16.6 / 20.6 / 24.7 | 0 | 2.8 |
| baseline, emulated phone medium | 60.02 | 58.12 | 16.6 / 19.8 / 43.4 | 0 | 6.9 |
| **R1, emulated phone medium** | **60.02** | **58.21** | 16.6 / 19.8 / 33.7 | 0 | 6.7 |

No regression (the stop condition did not fire). Title JavaScript transferred at the title: 292,148 → 294,256 bytes
(the worker's experiment entry points; the Workbench is a lazy chunk).
