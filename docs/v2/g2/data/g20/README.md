# G2.0 Baseline — evidence

Tree: `origin/main` `7475896` (PR #27 merged), branch `v2/g2-sim-identity`; only the G2 paperwork
and new `tools/g2` / `lab_web/tools/g2` files uncommitted when measured. Laptop: i5-13420H,
RTX 4050 driver 580.178.04, **balanced, on AC**; no simulator running.

## Suites — [`suites.txt`](suites.txt) (`tools/g2/suites.sh`, G1.13's runner kept in the repo)

| Suite | Result |
| --- | --- |
| coco_lab, CI venv route (`-m "not gz"`) | 1077 passed |
| coco_lab gz tests | 2 passed |
| `pytest lab_web/tools` | 232 passed |
| vitest | 539 passed (66 files) |
| typecheck, schemas check, catalog, arena assets, build twice (same dist hash), check_dist | pass |
| native gate (CPython vs Pyodide, hash v3) | planners 818,951 / 818,951 exact; fetch_rush 1,436 / 1,436 exact |
| coco verify + play references | 18 of 18 references earn their stars |
| determinism, 10 M1 sessions, Chromium / Firefox / WebKit / Pyodide-Node | 1500 ticks each, 0 mismatches |
| determinism, 3 M4 terrain sessions, same four | 2100 ticks each, 0 mismatches |
| screenshots, replays, v1 links (50 forms), update isolation | pass |
| chase HUD check (20 poses × phone landscape, desktop, real-phone tab 710 × 269) | 0 failed |
| ROS packages (`scripts/run_all_package_tests.sh`, overlay `~/coco_lab_g2_ws`) | 12 / 12 packages |

The runner serves `dist` on port **4184**: a G1-era `serve_dist.mjs` (from the g1 worktree,
started before this session) still holds 4174. It was left alone, and every G2 check names its
own site (`determinism.mjs` defaults to 4174, so G2 passes `--site`).

## Before screenshots — [`../../screens/before/`](../../screens/before/)

- `screens/`: `lab_web/tools/g1/screens.mjs` on the **NVIDIA** GPU (`G1_GPU=nvidia`): title, Play
  (Fetch Rush seed 1, PLAY pressed), Compare, Recordings, at 1440 × 900 and on the **emulated**
  Nothing Phone (1) in landscape and portrait. Phone-portrait Play is the rotate card by design
  (PLAY is under it, so the tool's "press PLAY" step times out there; recorded in `shots.json`).
- `review/`: `lab_web/tools/g1/review_shots.mjs` (NVIDIA, 1440 × 900): title, modes, Play chase,
  Robot vision on, tactical, the "what is real here" sheet, Compare, Research, M5's Arena.
- `real_phone/`: the **real** Nothing Phone (1) (A063, Android 15, Chrome 156.0.8078.47), Fetch
  Rush seed 1, full screen, shipped defaults, 1 minute, `lab_web/tools/phone/real_phone_free.mjs`
  (no DevTools attached while playing), served by the laptop over USB.

### Real phone, 1 minute (baseline for G2's budgets) — [`phone_free.json`](../../screens/before/real_phone/phone_free.json)

| Measure | Value |
| --- | --- |
| End state | full screen, landscape, viewport 803 × 361 CSS px, tier medium, pixel ratio 1.25 |
| fps (1 s windows) | median 60, min 59, p05 60 |
| frame time | median 16.7 ms, p95 18.2 ms, p99 19.9 ms, max 26.8 ms; 0 frames over 50 ms |
| WebGL context losses / page errors | 0 / 0 |
| temperatures (start → end, °C) | skin 30.4 → 35.2; GPU 36.6 → 57.9; battery 31 → 33 (charging, 100 %) |
| touch-to-motion | 10 samples, median 127 ms; the p90 sample is 4,865 ms — **unexplained** (10 samples, a 1-minute run; not investigated at G2.0) |

**Phone privacy.** Status bars are blacked out with `lab_web/tools/g2/redact_statusbar.mjs`
(portrait top 150 px; landscape top 108 px unless a shot was looked at and has none). Two of the
four screencaps were **not committed**: the portrait rotate card and the shot just after entering
full screen both showed a heads-up alarm notification (and the latter the status bar, which
Android shows for a moment on entering full screen). The two committed shots (1 minute, end)
were looked at: no status bar, no notification. The phone's rotation settings were restored
(0 / 0, as found); its saved COCO settings live on `localhost:4174`, an origin G2's runs on
4184 never touch.
