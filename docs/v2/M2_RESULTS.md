# M2 results — the whole loop

M2 (the M2 prompt, `docs/v2/M2_PROMPT.md`) turned the M1 Arena into the
whole loop — localise, map, move and decide around the planner — added the
lenses that show each computation, converted Labs 2–5 into the loop's
channels, wrote the six Learn missions that carry every v1 claim, measured
the model against the Stack (fidelity report v1), and retired the v1 lab
views to a frozen archive at `/v1/`.

**Evidence class.** Every number here is MODEL (the Arena and the browser)
unless marked STACK (the full ROS 2 stack in Gazebo, recorded). No physical
robot exists. **Measurement standard:** the balanced power profile on AC
(section 0); every harness records profile, AC state, governor and load in
its JSON (`conditions`). Laptop: i5-13420H, 12 threads, RTX 4050 laptop GPU,
Chromium headless through ANGLE unless stated. Measurements taken 2026-10-10
from 05:43 (local) on the final M2 build, files under
`docs/v2/data/m2/m211/`.

## Acceptance criteria (M2 B.3)

| Area | Criterion | Result | Evidence |
|---|---|---|---|
| Determinism | Identical per-tick hashes across Chromium, Firefox, WebKit and Pyodide-in-Node, over 100 sessions with localisation noise, mapping and the fetch mission | **Met.** 100 sessions × 150 ticks = 15,000 ticks per engine, **0 differing** in every engine; each engine's digest of all hashes `6713478e0ec2…` (Chromium 156, Firefox 157, WebKit 27.2, Pyodide 314.0.7 in Node 24.21.0). Every session ran localisation (MCL / EKF / both, range noise 0.01–0.04 m, 50–300 particles, three injection modes, slip in 27), a mapping algorithm (occupancy / EKF-SLAM / FastSLAM / pose graph), a local controller (DWA / RPP / MPPI; a Lab 5 scenario in 68) and a fetch (target moved in 53), plus 376 goals, 339 teleop commands, 55 kidnaps, 47 planner switches and 78 stops from a fixed-seed generator (`--gen-seed 20261011`). WebKit ran with EGL pointed at Mesa (see below); the hashes come from Pyodide, not the renderer | `determinism/determinism.json`, `sessions.json`, `hashes_*.json.gz`; `lab_web/tools/perf/determinism.mjs` |
| Correctness | Golden traces for every algorithm family on its property corpus; the 16 search runs replay byte for byte | **Met.** The package suites run each family's golden and property tests (`coco_lab` 735 / 0 / 0, `coco_schemas` 218 / 0 / 0); the 16 Gazebo searches, converted to coco.v1, replay byte for byte, 16 of 16, and one flipped look is caught (M2.7) | `coco_schemas/test/test_search_replay_v2.py`; `coco_lab/test/` |
| Claims | Every Lab 1–5 learner-facing claim appears in a mission with resolving evidence; the CI evidence check passes | **Met.** 98 of 98 v1 claims carried by the six missions' 61 claims; every reference resolves (a RESULTS.md heading matched exactly once, a committed file, or a test function that exists); `build_catalog.py` refuses to build otherwise (M2.8) | `docs/v2/M2_CLAIMS_COVERAGE.md`; `lab_web/tools/test_missions.py` |
| Laptop performance | 60 fps with all lenses' default layers on the fetch mission, plus 2,000 particles, 1,000 MPPI samples × 56 steps, a full occupancy grid | **Met.** The fetch mission running (MCL, occupancy map from its belief, DWA, a red fetch), every lens's default layers on, plus the stress layers rebuilt at 10 Hz: **60–61 fps in each of 20 seconds**, p95 frame 17.2–20.6 ms. The model step meanwhile: median 34.1 ms per 100 ms tick. M1's stress scene on the same build: 60–61 fps, p95 17.1–17.4 ms | `render/fps_m2_gpu.json` (+ `.png`), `render/fps_m1_gpu.json`; `lab_web/src/arena/stress.ts` |
| Responsiveness | Goal click after a planner change: median ≤ 100 ms, max ≤ 500 ms; seek ≤ 100 ms on a 5-minute fetch-mission recording | **Met.** Goal right after a planner change, real clicks, click → that goal's search drawn: median **43.7 ms**, p95 65.6, max **66.5**, 25 / 25 under 100 (warm goal alone: median 39.5, max 68.3, 25 / 25). Seek on 3,022 ticks of fetch mission (5.0 min; only 1 of its 4 fetches completed, see "Found while measuring"): the slowest of 10 seeks **33.1 ms** to the frame in which every lens has redrawn (the call itself ≤ 0.3 ms) | `responsiveness/responsiveness_gpu_planner_then_goal.json`, `responsiveness_gpu.json`; `seek/seek_check.json` |
| Cold start | First visible computation ≤ 10 s and live model ready ≤ 10 s (Plan lens), emulated 4G; other lenses ready within 3 s of selection, warm cache | **Met.** Emulated 4G (9 Mbit/s, 170 ms), self-hosted Pyodide, n = 10: first visible computation median **3,005 ms** (2,956–3,246); live model ready median **7,870 ms** (7,837–8,158). Unthrottled: 615 ms (386–637) and 2,628 ms (2,153–2,794). Lenses, warm cache: localise 122, map 179, move 205, decide 96 ms (cold: at most 207) | `coldstart/m211_4g_gpu.json`, `m211_none_gpu.json`; `lens/lens_check.json` |
| Links | Every v1 URL form resolves with 0 console errors; the bare URL opens the Arena | **Met.** 22 of 22 forms (`?view=` each lab, deep links, Lab 1 bundle and share links with and without settings or edits, the archive) land where `landing.ts` routes them, 0 console and page errors; the bare URL opens the Arena (M2.10) | `links/v1_links_check.json`; `lab_web/test/landing.test.ts` |
| Hygiene | 0 console errors in all views; phone-width layout checked; all suites and CI green | **Met.** CI green on PR #21 (`lab.yml` run 38015704616 at `0687c4f`, every job, including the v1 archive build and the 22 URL forms in the browser job; its first run caught an archive-path defect, fixed in `0687c4f`). 0 console errors and 0 page errors on all 14 public pages (the Arena and its four lenses, Learn and its six missions, Live, the v1 archive); Live opens no socket on load and recovers to "connected" when a stack appears; phone width (Pixel 7, 390 px): no horizontal scroll on the lens bar, the mission list or a beat. Suites: packages 3,432 / 0 / 0, vitest 343 / 0 / 0, build tools 127 / 0 / 0 | `console/console_check.json`; `lens/lens_check.json`; `learn/learn_check.json`; `docs/STATUS.md` |
| Phone | ≥ 30 fps at default detail on the fetch mission; first visible computation ≤ 10 s on mobile data | **Pending Gautham** (`docs/v2/PHONE_MEASURE.md`, section "M2") | — |
| Usability | 5 people new to robotics complete missions 1, 3 and 5 and explain one computation each, unaided | **Pending Gautham** (`docs/v2/USABILITY_TEST_M2.md`) | — |

## Found while measuring

- **The NVIDIA userspace libraries were upgraded mid-run.** Unattended
  upgrades moved them from 580.173.02 to 580.178.04 at 06:18; the loaded
  kernel module stayed 580.173.02, so NVIDIA EGL fails (`EGL_BAD_ALLOC`;
  NVML: "Driver/library version mismatch") **until the machine is
  rebooted**. Every timing above was written by 05:58, before it. Only the
  WebKit determinism run came after, and it was re-run with EGL pointed at
  Mesa for that process (the hashes come from Pyodide, not the renderer).
- **In the seek recording only the first of four fetches completed.** The
  next fetches, each started where the robot stood when the last ended, failed
  `NAVIGATION_FAILED: no_valid_control` (DWA). Reproduced in the Python Arena
  (seed 1): the first fetch itself stalls near (1.7, 5.7) and every later fetch
  starts from that pose and stalls again. This is M2.6's measured DWA
  weakness (MCL + DWA fetched 4 of 8), not a restart defect; a new fetch from
  a stuck pose inherits it. Parked in `docs/IDEAS.md`.
- A label bug fixed: the mission state read "Go To_bay" (one underscore
  replaced); it reads "Go To Bay" in the committed screenshot.

## The milestone, checkpoint by checkpoint

Each checkpoint's full record — what changed, what was measured, its tests —
is in `docs/STATUS.md` "M2 checkpoint log". The headline of each:

| Checkpoint | Headline | Evidence |
|---|---|---|
| M2.0 Carry-overs | cancellable planning (a goal after a planner change no longer waits for the re-plan), the attract recording deferred, lazy lens packs | `v2/data/m2/m20/` |
| M2.1 Schemas | ten channel families added within coco.v1, TypeScript and Python byte-identical | `coco_schemas/` |
| M2.2 Lens framework | five lenses, three disclosure levels, Watch shows at most two computation layers (tested) | `lab_web/src/arena/lens/` |
| M2.3 Localise | MCL and EKF step by step in the Arena, kidnap and config inputs; a closed-loop kidnap recovered 0 of 20 (Lab 2's 18 of 20 was open loop) | `v2/data/m2/m23/` |
| M2.4 Map | occupancy, EKF-SLAM, FastSLAM, pose graph on the Arena; one drive: pose graph F1 0.642 and 0.12 m ATE against Lab 3's engine 0.218 and 1.72 m | `v2/data/m2/m24/` |
| M2.5 Move | DWA, RPP, MPPI as teaching implementations; against the Lab 5 recordings 9 of 9 controller-scenario cells agree on hairpin, crossing and run 15; head-on differs by construction | `v2/M2_MOVE_COMPARISON.md`, `v2/data/m2/m25/` |
| M2.6 Decide | the fetch mission in the Arena (Bayesian bay search, arm inset); plain 6/8, MCL 8/8, MCL+MPPI 7/8, MCL+RPP 4/8, MCL+DWA 4/8, mislocalised 1/4 | `v2/data/m2/m26/` |
| M2.7 Converters | Labs 2–5 convert losslessly; the 16 Gazebo searches replay byte for byte; 54 Lab 5 drives play as STACK | `v2/SCHEMAS.md`, `v2/data/m2/m27/` |
| M2.8 Learn | six missions as data, 61 claims, 98 of 98 v1 claims covered, a CI evidence check | `v2/M2_CLAIMS_COVERAGE.md`, `v2/data/m2/m28/` |
| M2.9 Fidelity | the Arena's LiDAR casts beam for beam as Lab 2's Sketch on the Nav2 map (agreement with the map, not with Gazebo's sensor); against Gazebo's recorded scans |e| median 2.2 mm, 86.7 % of beams within 5 cm; wheel-odometry turn over-count against Gazebo's own ground truth 1.22–1.27×, the model's slip option 1.29× (fitted on a tour; no physical robot measured); model gap chips | `v2/FIDELITY_v1.md`, `v2/data/m2/m29/` |
| M2.10 Retire v1 | `/v1/` built from the tag at deploy time; routing; 69 v1 view files removed | `v2/adr/0003-v1-archive.md`, `v2/data/m2/m210/` |
| M2.11 Measure | this document; ADR 0004: no WebAssembly port | `v2/adr/0004-wasm-gate-m2.md`, `v2/data/m2/m211/` |

## Decisions

- **No WebAssembly port** (ADR 0004): no budget fails.
- **The v1 archive is built from its tag at deploy time** (ADR 0003).
- **Learner labels:** README's set plus UNRESOLVED and TESTED — a deviation
  for Gautham to rule on (`docs/IDEAS.md`). **Ruled 2026-10-10: both kept;
  README §3 lists them** (plan-change log).

## Reproduce

```
~/coco_lab_m2_ws/bin/m211_measure.sh      # (not in the repo) builds, serves, sets balanced, runs:
node tools/perf/render_fps.mjs --scene m2 --gl gpu --seconds 20
node tools/perf/responsiveness.mjs --n 25 --gpu 1 [--immediate 1]
node tools/perf/seek_check.mjs --gpu 1
node tools/perf/coldstart.mjs --runs 10 --pyodide self --throttle none|4g --gl gpu
node tools/perf/lens_check.mjs --gpu 1
node tools/perf/console_check.mjs --recovery-port 8089
node tools/perf/v1_links_check.mjs ; node tools/perf/learn_check.mjs ; node tools/perf/mission_check.mjs --gpu 1
node tools/perf/determinism.mjs make --n 100 --ticks 150 --loop 1 --map 1 --move 1 --mission 1 --gen-seed 20261011
node tools/perf/determinism.mjs node|chromium|firefox|webkit ; node tools/perf/determinism.mjs compare
```

(each with `--site http://127.0.0.1:4194/coco-labs/ --out DIR`, the site
built by `npm run build` and served by `tools/perf/serve_dist.mjs` with the
v1 archive at `dist/v1/`).

## After the independent review: re-measured on the new NVIDIA driver (2026-10-10)

The M2 review session (`docs/v2/reviews/M2_REVIEW.md`) re-measured the
agent budgets after the reboot.

**Conditions:**
- NVIDIA kernel module and userspace both **580.178.04**
- balanced, on AC
- headless Chromium 156 on `ANGLE (NVIDIA … RTX 4050 Laptop GPU …)`
- n ≥ 10 each
- the review clone's production build of `330df44`

Evidence: `docs/v2/data/m2/review/remeasure/`; the full table is in
`docs/RESULTS.md`, "COCO Lab v2 · M2 independent review".

| Budget | Re-measured | Verdict |
|---|---|---|
| 60 fps, fetch mission + stress layers | 58–62 fps in every one of 200 s (10 runs); p95 frame median 18.6 ms, 16.9–33.0 | met |
| M1 stress scene | 60–61 fps in every one of 100 s (10 runs) | met |
| Goal after a planner change | median 40.3 ms, max 66.8, 25 / 25 under 100 | met |
| Seek | max 35.4 ms over 30 seeks (3 recordings) | met |
| First visible computation, 4G | median 3,201 ms (2,969–3,222) | met |
| Live model ready, 4G | median 8,062 ms (7,836–8,129) | met |

**Two corrections from the review:**
- **The seek recording's fetch outcomes vary from run to run.** Each next
  fetch starts at the tick the page saw the previous one end (1688 or
  1689), and DWA's stall is sensitive to it. Completed fetches were red
  and green, red and green, and red and blue in the three review
  recordings, against red only in M2.11's.
- **`/v1/` is built from `9f58b83`**, because the tag's build undid M0's
  public fixes.
