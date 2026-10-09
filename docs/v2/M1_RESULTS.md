# M1 results — the Glass-box Arena core

Every number here was produced by a run on branch `v2/m1-arena-core`, on the
final M1 build unless a row says otherwise, and each cites its file under
`docs/v2/data/m1/`. Evidence class **MODEL** throughout (the Arena model,
`coco_lab`, the browser) except the recorded runs played in the viewer,
which are **STACK** recordings — played, not re-measured. No physical robot
exists.

**Device and conditions.** The development laptop: Intel Core i5-13420H (12 threads), NVIDIA RTX
4050 laptop GPU, Ubuntu 24.04. The laptop was in its **power-saver**
profile (governor `powersave`) for the M1.10 measurements — recorded in the
cold-start files; M1.5's profile was not recorded, so M1.5 → M1.10 timings
are not a controlled comparison. Browsers: Playwright 1.64.0's Chromium
156.0.8078.4 (headless; GPU through ANGLE with `--use-angle=gl-egl
--ignore-gpu-blocklist --enable-gpu` where it says "GPU", otherwise
SwiftShader), Firefox 157.0, WebKit 27.2; Pyodide 314.0.7 on Node 24.21.0.
The site is served the way GitHub Pages serves it (gzip, `/coco-labs/`,
`lab_web/tools/perf/serve_dist.mjs`). Network profiles are Chromium's
emulation: "Wi-Fi" 30 Mbit/s, 20 ms; "4G" 9 Mbit/s, 170 ms.

## Re-measured in the balanced profile on AC (M1 review, 2026-10-09)

The owner's standard from 2026-10-09 is the **balanced** profile **on AC**
(`docs/STATUS.md`, plan-change log). The independent M1 review re-measured
every M1 budget that way, from a fresh clone at `4b4bef8` (M1 + harness
fixes, no behaviour change), n ≥ 10; every file records the power profile,
AC state, governor and load (`balanced/`, and `docs/RESULTS.md`). The
power-saver rows in the table below are **kept** as the worst case.

| Budget | Balanced, on AC | Power-saver (M1.10, below) |
|---|---|---|
| Laptop fps under the stress load | 60–61 in all 100 samples (10 runs), p95 frame 16.8–17.6 ms | 60–61 |
| Warm goal → its frontier drawn | median **42.9 ms**, p95 61.9, max 63.2, 25/25 < 100 | median 40.4, max 71.5, 25/25 |
| Seek | max **0.7 ms** (70 seeks) | ≤ 0.6 ms |
| First visible computation, desktop / fast-4G* / emulated 4G | **631 / 1,366 / 3,381 ms** | 754 / 1,629 / 3,299 |
| Live model ready (secondary), same | 2,683 / 4,061 / **8,191 ms** | 5,023 / 6,603 / **10,782** |
| Goal right after a planner change (M2.0) | median 138.6, max 1,708.4, 10/25 < 100 | median 293, max 4,029, 7/25 |

\* "fast-4G" is M1's "Wi-Fi" emulation profile (30 Mbit/s, 20 ms), kept so
the rows compare. Files: `balanced/fps/`, `balanced/responsiveness/`,
`balanced/timeline/`, `balanced/coldstart/`.

## Acceptance criteria (M1 B.4)

Measured in **power-saver** (M1.10); the balanced rows are above.

| Area | Criterion | Result | Evidence |
|---|---|---|---|
| Determinism | Identical per-tick hashes, Chromium + Firefox + WebKit + Pyodide-in-Node, 100 recorded sessions with random goals and teleop | **Met.** 100 sessions × 150 ticks = 15,000 ticks per engine; **0 differing** in every engine; every engine's digest of all hashes `0e43a0b5d6b9…`. The sessions: 416 goals, 337 teleop commands, 84 planner switches, 79 stops, from a fixed-seed generator. Each session a fresh model: a new production worker in each browser; in Node, one Pyodide per run with a fresh module (`importlib.reload`) and a fresh Arena per session *(M1 review correction, 2026-10-09: this said "a new Pyodide in Node", which the harness does not do — its own comment says so)*. Re-run by the M1 review: 25 sessions × 4 engines, 0 differing, and 0 against these committed hashes (`review/determinism_rerun/`). | `determinism/determinism.json`, `hashes_*.json.gz`, `sessions.json`; `lab_web/tools/perf/determinism.mjs` |
| Correctness | Golden traces match Lab 1 on all 1,000 corpus maps | **Met.** All 5,000 searches (1,000 maps × 5 algorithms) reproduce Lab 1's traces exactly | `coco_lab/test/test_golden_traces.py` (in the package suite and CI's plain-venv job) |
| Laptop performance | 60 fps with ~50,000 points, 20,000 segments and one grid texture | **Met.** 60–61 fps in each of 10 seconds, p95 frame 17.3–17.9 ms (GPU) | `render/fps_stress_gpu_m110.json` |
| Responsiveness | First frontier node visible within 100 ms of a goal click (warm); seek under 100 ms | **Met.** Real mouse clicks, click → first rendered frame drawing THAT goal's search: median **40.4 ms**, p95 70.8, max 71.5, **25/25** under 100 (first, cold-of-the-live-model goal: 64.8 ms; GPU). Seek: ≤ 0.6 ms in the browser on an 81,593-event search; every seek < 100 ms on a 380k-event search (vitest). | `responsiveness/responsiveness_gpu.json`; `timeline/timeline_check.json`; `lab_web/test/session.test.ts` |
| Laptop cold start | Median and range, n ≥ 10, against the M0 baseline; target under 10 s | **Met for the first visible computation; the live model on emulated 4G is over.** Self-hosted, GPU, n = 10 each — first visible computation (the attract recording's search drawn): **754** (728–999) / **1,629** (1,236–1,703) / **3,299** (3,263–3,518) ms; live model ready: 5,023 (4,683–5,766) / 6,603 (6,311–6,748) / **10,782** (10,491–11,087) ms (unthrottled / Wi-Fi / 4G). M0 baseline: cold first computation 12,857 ms (6,567–42,882), n = 5, Plan view, Pyodide from the CDN, real network (`docs/v2/BASELINE.md` §1). | `coldstart/m110_self_{none,wifi,4g}_gpu.json`; SwiftShader: `m110_self_none.json` |
| Phone performance | 30 fps or better at default detail | **Pending Gautham** (`?perf`, `docs/v2/PHONE_MEASURE.md`) | — |
| Phone cold start | First visible computation within 10 s on mobile data | **Pending Gautham** (the `?perf` panel's "first computation shown") | — |
| Usability | 5 people new to robotics set a goal and explain the heatmap within 2 minutes, unaided | **Pending Gautham** (`docs/v2/USABILITY_TEST.md`) | — |
| Hygiene | 0 console errors in every view; phone-width layout; schema, golden-trace, determinism and screenshot tests in CI; existing suites pass | **Met** (CI result of the new browser job: see `docs/STATUS.md`). 0 console errors in all seven views and in every harness below; Pixel 7 viewport: a tap gives a goal, no horizontal scroll; CI: schema tests (`coco_schemas`) *(M1 review correction, 2026-10-09: false until `[M1-fix]` `b3dc8a0` — CI's `build-and-test` collected 0 `coco_schemas` tests and failed on PR #20, because `setup.py` did not declare pytest; they ran only locally)*, golden traces (`coco_lab`), determinism (vitest: 5 sessions in Pyodide-in-Node against the committed hashes; browser job: 10 sessions in Chromium, Firefox and WebKit), screenshot tests (5 Arena scenes, SwiftShader, with a self-test that two different scenes differ: 3.1 % of pixels). | `console_m110/console_check.json`; `experience/experience_check.json`; `screenshots/check_local.json`; `.github/workflows/lab.yml` |

## Found and fixed in M1.10 (each would have hidden a miss)

- **The goal → frontier timer stopped on the old search.** After a second
  goal the previous search was still on screen, so the timer stopped on the
  next frame. Only first goals had been timed honestly. Fixed: the timer
  counts only a different search; the harness times click → first draw of
  the goal's own search, found by its goal coordinates.
- **A new search stayed hidden until it finished.** `ArenaSession` showed a
  search only once its tick arrived — after the whole search, although its
  events were streaming. Measured with the honest timer: median 414 ms,
  p95 2,690 ms, 7/25 under 100 ms. Fixed (live view shows the search being
  computed for the tick in progress): 40.4 ms, 25/25. Pinned by a vitest.
- **The `?perf` panel named a mark the page no longer recorded** ("first
  frontier node shown" read "—" since M1.8). It now shows "recording ready
  (attract)" and "first computation shown" — the phone cold-start number —
  and the experience check reads them off the screen.

## Measured and reported, not an M1 criterion

- **Goal clicked immediately after a planner change:** median 293 ms, p95
  3,193 ms, max 4,029 ms, 7/25 under 100 ms (`responsiveness/
  responsiveness_gpu_planner_then_goal.json`). A planner change re-plans
  the running goal synchronously (by design, `coco_lab/arena.py`); the
  goal waits behind it. A queueing problem, not a kernel-speed one
  (ADR 0002); parked for M2 (`docs/IDEAS.md`).
- **Attract mode's cost to the live model's load:** with the recording's
  request refused (A/B, same conditions, n = 10 each), live model ready
  4,868 (4,548–5,163) ms against 5,023 (4,683–5,766) ms with it; an earlier
  pair in the same session gave 4,897 against 5,472. Parked for M2.
- **Page weight to Arena ready:** 5,823,366 B (M1.5: 4,944,244 B; the
  difference includes the 688,717 B attract recording).

## Earlier M1 checkpoints (measured then; files committed)

LiDAR fidelity 86.73 % of beams within 5 cm, identical to Lab 2
(`lidar/`); Arena rasterise 780.7 → 9.8 ms (`coldstart/arena_node_*`);
world, computation and replay seeking (`timeline/`); the full experience
— attract, click to take over, arrival totals with heatmap, keyboard and
joystick teleop, compare, share link reproducing the same hash chain,
phone tap (`experience/`, 9/9); Lab 1's eleven bundles converted
losslessly, the three recorded full-stack runs played as STACK
(`replay/`); the trimmed stdlib saved 421 / 1,647 ms on Wi-Fi / 4G
(M1.5, `coldstart/m15_*`).

## Decisions

- [ADR 0001](adr/0001-event-transport.md) — Python emits columnar typed
  arrays; TypeScript encodes protobuf.
- [ADR 0002](adr/0002-wasm-gate.md) — port nothing to WebAssembly: no
  agent-measured budget fails.
- The Arena is the site's landing page (bare URL); every v1 link — a named
  view or a v1 share link — still opens v1 (`landing/landing_check.json`,
  9/9). *(M1 review correction, 2026-10-09: 3 of those 9 cases are Arena
  URLs, and `?view=localise|map|search` and a bare `?v=` were not opened;
  the review's 14-case check covers every v1 form, 14/14:
  `landing/landing_check_review.json`.)*
