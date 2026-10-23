# G1.9 — Performance (cloud: emulated phone and desktop on a software GPU)

Evidence class MODEL in the browser, **emulated**. Cloud container: Intel Xeon 2.1 GHz × 4,
no GPU, so Chromium (Playwright) renders with **SwiftShader** (Vulkan on the CPU; renderer
string in every JSON). Build: the final G1.8 build (`c7d1ce0` source), served by
`lab_web/tools/perf/serve_dist.mjs` (gzip, as Pages). Harness:
`lab_web/tools/g1/perf_play.mjs` (Play → Free Drive → Depot, medium tier, driven by keys
for the whole run: forward, turns, reverse, Robot vision toggled every ~45 s).
Emulated Nothing Phone (1) = `lab_web/tools/phone/nothing-phone-1.mjs` (915 × 412,
DPR 2.625, touch, Android UA, 4× CPU throttle). **No real phone was measured; this is
not a phone result.**

## What each number is

- **Frames drawn per second**: frames that reached the WebGL context (first clear per
  animation frame), per one-second window. On SwiftShader the rasteriser runs on this
  container's CPU: these numbers describe software rendering here, **not** a phone GPU.
- **JavaScript per frame**: main-thread time of the page's animation-frame callbacks
  (the game loop, renderer submission, HUD). This is the CPU-side share that the 4×
  throttle models; the 60 fps budget is 16.7 ms.

## Results

| Run | Duration | Drawn fps median / min (SwiftShader) | Drawn frame time p95 | JS per frame median / p95 / max | Errors | WebGL context lost |
| --- | --- | --- | --- | --- | --- | --- |
| Emulated phone, medium ([json](phone-medium-10min.json)) | 10 min (515 windows) | 4.7 / 1.8 | 344 ms | 7.9 / 16.0 / 514 ms | 0 | 0 |
| Desktop 1440 × 900, medium ([json](desktop-medium-10min.json)) | 10 min (472 windows) | 3.8 / 0.7 | 508 ms | 1.8 / 5.5 / 782 ms | 0 | 0 |
| Emulated phone soak, medium ([json](phone-medium-soak-30min.json)) | 30 min (1,556 windows, 7,974 model ticks) | 4.9 / 1.5 | — | 7.4 / 15.1 / 961 ms | 0 | **0** |

**The 60 fps criterion is not met and cannot be evaluated here**: the drawn rate is
software rendering's. CPU-side, the emulated phone's median frame JS (7.9 ms) and p95
(16.0 ms) fit inside the 16.7 ms budget; the long maxima are single frames (world build,
Vision toggles). Whether the Depot holds 60 fps at medium on a phone is **pending: the
laptop (emulated profile on a real GPU) and the real Nothing Phone (1) over USB/CDP.**

## Title and loading

| | Emulated phone | Desktop |
| --- | --- | --- |
| First paint | 388 ms | 120 ms |
| First contentful paint | 2,672 ms | 696 ms |
| Title visible | 3,061 ms | 790 ms |
| JS transferred by then | 274,752 B | 274,752 B |
| Mode select → PLAY enabled (model ready) | 8,346 ms | 4,886 ms |
| PLAY → first model tick | 2,287 ms | 1,478 ms |

Local server, no network emulation (warm cache-free loads from 127.0.0.1); the worker's
own load marks are in each JSON (`loading.perf_marks`).

## Budgets

- Title-critical JS: **284,510 B gzip** (`node tools/check_dist.mjs`), limit 350 kB.
- World budgets per tier ([`budgets.json`](budgets.json), `tools/g1/budgets.mjs`, max over
  chase / wide orbit / tactical): Depot low 278,534 B / 14,399 tris / 57 draws; high
  674,794 B / 29,999 / 98; Proving Ground low 186,603 B / 6,319 / 23; high 582,863 B /
  21,907 / 55 — all within (low ≤ 1.2 MB / 150k / 120; high ≤ 3 MB / 400k / 250).
- Console and page errors: 0 in all three runs. WebGL context losses: 0, including the
  30-minute soak.

## Pending: laptop and phone

Real GPU fps on both laptop GPUs (balanced profile, on AC, driver recorded); the real
Nothing Phone (1) over USB/CDP when `adb devices` lists it, with a 10-minute heat run;
choosing the default tier from those numbers.
