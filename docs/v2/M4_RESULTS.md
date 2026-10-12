# M4 results: the 3D Arena

M4 (README §7, "M4 · 3D Arena"; `docs/v2/M4_PROMPT.md`) did ten things:

- checked on a laptop and under emulation that a browser can hold COCO's arena in 3D (the
  feasibility gate; the phone half is Gautham's);
- built an asset pipeline from the recorded world and the robot's own URDF and meshes, with a
  licensed, checksummed manifest and size budgets in CI;
- taught the Arena model **kinematic** terrain following on World Spec v2 (ramps and
  platforms), contacts, the command source and the gated grasp, with every flat-scene hash
  unchanged;
- drew the world in 3D with quality tiers and an automatic top-down fallback;
- gave it cameras and controls: follow by default, a HUD, help, remappable keys, touch;
- put every lens into 3D;
- opened the Case Files in 3D at the stack's recorded truth (and never invented a height
  for a recording that has none);
- added mission cameras and a new challenge, **Race the planner's ghost**;
- drafted the launch;
- measured all of the above.

**Evidence class.** MODEL (the Arena, coco_lab and the browser) unless marked STACK (the full
ROS 2 stack in Gazebo, recorded). The Arena model is planar kinematics plus kinematic terrain
following: no physics engine, no forces, slip or tipping (invariant 10). No physical robot exists.

**Measurement standard:** the balanced profile on AC. Every harness records the profile, AC
state at start and end, governor and load in its JSON; a step during which AC was lost was
run again. Laptop: i5-13420H, 12 threads, RTX 4050 laptop GPU (NVIDIA 580.178.04) and Intel
Raptor Lake-P integrated graphics (Mesa 25.2.8, through ANGLE on Vulkan). Headless Chromium
156 through ANGLE on the RTX unless stated; Firefox 157 and WebKit 27.2 where named. Results
under a phone viewport, CPU throttling or emulated 4G (9 Mbit/s down, 1.5 up, 170 ms) are
**emulated**, never "phone". Measured 2026-10-12 and 13 on `v2/m4-3d-arena`; files under
`docs/v2/data/m4/`.

**Which build.** The M4.10 run measured `dbdea9c` (frame rate, cold start, latency, controls,
quality, lenses, timeline, Case Files), then two fixes it found (below) and the rest on
`62f6338` (the race links, modes, layout, the 30-minute session) and `7e72010` (the replays,
the old URL forms, the console check). The fixes touched the Play page and the replay page's
runs list only; nothing measured on the earlier build reads either.

## Acceptance criteria (README §7, M4)

| Area | Criterion | Result | Evidence |
|---|---|---|---|
| Frame rate (RTX 4050, balanced, AC) | 60 fps on high tier with the world, robot and fetch-mission default layers; 60 fps on the M2 stress scene at medium tier | **Met.** High tier, the fetch mission with every lens's layers, follow camera, 3 runs × 30 s: **median 61 fps, the slowest second 60** in every run; per-second p95 frame at most 24.1 ms. (A fourth run overlapped a test run and is kept but not counted: also 61 / 60.) M2 stress at medium tier, 3 × 30 s: median **60 / 61 / 61 fps**, slowest second **56 / 59 / 60**; p95 frame at most 25.7 ms. The 56 is one second of 30 in one run | `m410/fps/nvidia_high_m2_{1b,2,3}.json`, `nvidia_high_m2_1.json` (overlapped), `nvidia_medium_stress_{1,2,3}.json` |
| Frame rate (laptop integrated GPU) | 60 fps on medium tier with default layers | **Met.** Intel RPL-P (the renderer string records it), medium tier, the fetch mission's layers, 3 × 30 s: **median 61, slowest second 60** in every run; p95 frame at most 19.5 ms | `m410/fps/intel_medium_m2_{1,2,3}.json` |
| Control latency | Key press to visible motion within one model tick plus one frame (about 50 ms or less), median over 100 presses | **Met.** From the key event's own timestamp to the end of the first frame that draws the robot moved, 100 presses each: follow **median 45.1 ms** (p95 48.8, max 62.4); top-down **median 44.0 ms** (p95 49.2, max 62.4) | `m410/latency/control_latency_{follow,topdown}.json` |
| Camera | No frame over 50 ms during transitions; no long tasks while driving | **Met.** Longest frame during each 0.4 s camera move (follow → orbit → robot-eye → top-down → follow): **16.8 ms** in all four. A 30-minute scripted session (34 rounds of driving, cameras, lenses, goals, grasps): **0 long tasks while driving, 0 in all** (main-thread tasks over 50 ms). The observer was shown to see one: a 120 ms task in the same page was recorded as 120 ms | `m410/controls/controls_check.json`; `m410/soak/soak3d_nvidia.json`; `m410/final/longtask_selfcheck_task.json` |
| Cold start (emulated 4G) | First visible computation 10 s or less; live model ready 10 s or less; 3D world interactive 12 s or less | **Met**, 5 cold runs: first visible computation **3,639–3,694 ms**; the 3D world with the robot in it **3,562–3,605 ms**; live model ready **8,372–8,521 ms**. "Interactive" = the later of the 3D world and the live model (driving needs both): **8,372–8,521 ms** | `m410/fps/cold4g_{1..5}.json` (`marks_ms`) |
| Download | First-scene assets 5 MB or less compressed; robot 1.5 MB or less | **Met (CI).** meshopt-compressed: arena 27,640 B; robot 540,152 B (high), 143,892 B (low). First scene **567,792 B** desktop, **171,532 B** phone | `lab_web/public/assets3d/manifest.json`; `lab_web/tools/test_assets3d.py` |
| Case Files | First frame 2 s or less on emulated 4G for 100 of 100, including 3D geometry | **Met, with one thing to judge.** All 100, cold, emulated 4G: **100 / 100 within 2 s**, median **762 ms**, max **1,773 ms** (`lab2_rl_fidelity_1_tour`); seek max 39.5 ms; 0 console errors. The 2 s frame has the arena in 3D and the robot's **placeholder body** at the recorded pose; the robot's own mesh follows (that file: 2,924 ms). Whether a placeholder body counts as "including 3D geometry" is Gautham's call. Before zstd level 19 (M4.7) the same file took 2,007 ms and 99 / 100 met it | `m410/casefiles/casefile_check_4g.json`; `m47/casefile_check_4g_at_26b6259.json` |
| Determinism | Flat-scene hashes and golden traces byte-identical to M3; terrain sessions identical across Chromium, Firefox, WebKit and Pyodide-in-Node (100 sessions) | **Met (CI).** Every flat golden-trace and hash test passes unedited; CI replays M1's committed sessions every tick. Terrain: 100 recorded World Spec v2 sessions × 700 ticks, **70,000 ticks per engine, 0 mismatched** in Chromium 156, Firefox 157, WebKit 27.2 and Pyodide 314.0.7 in Node 24.21; CI replays 3 of them in all three browsers on every pull request | `m43/determinism/` (M4.3); `.github/workflows/lab.yml` |
| Regressions | Every M3 criterion still met: challenge links, `coco verify`, the 16 replays, every old URL form, the claims check | **Met after two fixes M4.10 found.** (1) The Play page ignored every deflated `z=` link (it asked for `s=` only): fixed, `62f6338`. Then the 18 race links: **18 / 18 reproduced exactly in Chromium, Firefox and WebKit**, `coco verify` **18 / 18**; M3's 100 committed links in CI. (2) Every replay page had lost its runs list (an M4.7 change waited for a mark only Case Files set): fixed, `7e72010`; the replay check **5 / 5** pages; all 16 replays byte for byte (`coco_schemas`). CI now runs the replay check. Old URL forms **22 / 22**, `/v1/` views **6 / 6**. The claims check runs in every build (`build_catalog.py`). Screenshot scenes: **0 differing pixels** against baselines made from the public M3 site | `m410/race/`, `m410/final/replays/`, `m410/final/v1_links/`; `lab_web/test/screenshots/baselines.json` |
| Assets | World Spec ↔ SDF agreement within tolerance; every asset licensed, with checksum, in the manifest | **Met (CI)** (M4.2): v1's 70 boxes and v2's 12 primitives agree with the converted recorded SDF within 1 mm (a 2 mm change is caught); every asset Gautham's own work (Apache-2.0), sources and outputs by sha256 | `lab_web/tools/test_worldspec_sdf.py`, `test_assets3d.py`; `docs/v2/ASSETS.md` |
| Hygiene | 0 console errors; no WebGL context loss in a 30-minute scripted session; phone-width layout checked | **Met.** 0 console and 0 page errors on all **21** views (the four modes, Play and Case File pages, Live, `/v1/`) on the final build. 30-minute session: **0 context losses, 0 errors**, 60.0 fps median (p05 60.0) over 1,797 s. Phone width (**emulated** viewports 390 × 844 and 844 × 390, and 1280 × 800): 7 views each, **no horizontal scroll in 21 / 21**, STOP visible and on screen on every live view on touch, 0 page errors | `m410/final/console/console_check.json`; `m410/soak/`; `m410/layout/layout_check.json` |
| Fallback | A device forced below the low tier gets the top-down renderer automatically, with a notice | **Met (emulated).** SwiftShader at 20× CPU throttling: the low tier drew 20 fps, the page fell to top-down with the notice "3D is too slow on this device (the low tier drew at 20 fps, under 24), so this is the top-down view."; the RTX stays on high | `m410/quality/quality_check.json` |
| Phone frame rate | 30 fps or more on the automatic tier, 10 minutes | **Pending Gautham** ([`PHONE_GATE_M4.md`](PHONE_GATE_M4.md)) | — |
| Phone cold start | First computation 10 s or less on mobile data; 3D world interactive within 15 s | **Pending Gautham** (the `?perf` panel now shows "3D world drawn" and "3D robot in it") | — |
| Phone touch and stability | Joystick about 100 ms or less in `?perf`; no reload, crash or context loss in 10 minutes | **Pending Gautham** (`?perf` now shows "input → motion", median of the last 20, from rest) | — |
| Usability | 5 people new to robotics, unaided (the consolidated test, D5) | **Pending Gautham** ([`USABILITY_TEST_M4.md`](USABILITY_TEST_M4.md)) | — |

## What M4 built, checkpoint by checkpoint

Details, numbers and the evidence of each are in `docs/STATUS.md`'s "M4 checkpoint log".

- **M4.1 feasibility gate.** 60 fps in every run on the RTX, the integrated GPU and an
  emulated phone at 4× and 6× CPU (`docs/RESULTS.md` "M4.1"). The phone half is Gautham's.
- **M4.2 asset pipeline** (ADR 0006): the world from the recorded SDF, the robot from its URDF
  and meshes; meshopt; a manifest with sources, licence and checksums; World Spec v2 (ADR 0007).
- **M4.3 the Arena model:** terrain following, contacts, command source, the gated grasp;
  flat hashes unchanged; terrain fidelity against Lab 4's 17 Gazebo fetches (height |e| p95
  7.4 mm on slopes, pitch max 1.37°; `FIDELITY_v1.md` §4).
- **M4.4 renderer:** tiers, two passes (the world lit; the computation exact on top), cutaway
  and low walls, draped decals.
- **M4.5 cameras and controls:** follow by default (D1), the HUD with "MODEL · kinematic",
  latched STOP, help and remapping, touch, tank mode; one preferences module (integrity rule 7).
- **M4.6 lenses in 3D:** all 15 lens × level combinations, Watch at most two layers.
- **M4.7 Case Files in 3D:** truth z, roll and pitch from the stack's recording (float32), all
  100 re-converted; the planar chip on recordings without them.
- **M4.8:** mission cameras; Race the planner's ghost (three levels, 18 generated submissions).
- **M4.9 launch drafts:** a light landing, the 3D demo script, the usability test, the phone guide.
- **M4.10:** this document; the two fixes above; the screenshot harness now reads the canvas.

## What M4.10 found and fixed

1. **Deflated challenge links were ignored by the Play page.** M4.8 made links carry their
   inputs deflated (`z=`), because a long race drive made a 17.9 KB link the server refused
   (HTTP 431). The decoder, `coco verify` and the unit tests read `z=`; the page asked
   `params.has('s')` first and showed the level's intro instead. A test now pins that the page
   sees both forms.
2. **Replay pages had lost their runs list.** M4.7 deferred the runs index on recording pages
   until `recording_ready`, which only Case Files mark. Now only a Case File waits. CI now runs
   `replay_check.mjs`, which found it.
3. **The screenshot test failed on a one-pixel layout shift.** The planar-recording chip moved
   the canvas to a different fraction of a pixel; nothing drawn changed. The harness now reads
   the canvas's own pixels; baselines were remade from the public M3 site, and this build
   matches them with 0 differing pixels.
4. `test_play_levels.py` had no valid input for the race (it counted 16 levels).

## Deviations and open items

- No baked ambient occlusion (M4.4); picking uses the floor ray, not GPU ids; without WebGL 2
  the page shows its panels and a notice (a Canvas 2D view is parked in `IDEAS.md`).
- The Arena's LiDAR on terrain is not compared with Gazebo's scans (UNRESOLVED).
- The demo video is scripted (`tools/demo_record.mjs`), not recorded: its look waits for
  Gautham's review of the screenshots.
- `reference_shots.mjs` sets the camera on the renderer directly, so the HUD chip in
  `screens/m410/reference/orbit_wide.png` and `robot_eye.png` still says "follow"; the page's
  own chip follows real camera changes (`controls_check`).

## Screenshots awaiting Gautham's review (agent rule 7)

`docs/v2/data/m4/screens/`: `m43/` (terrain), `m44/` (cutaway, low walls, phone landscape),
`m46/` (every lens and level), `m410/terrain/`, `m410/reference/`, `m410/layout_*` (phone
widths). Known look issues: the LiDAR fan's sheet and moiré are heavy in 3D; cut walls read as
large grey slabs with dark inner faces; on a phone in portrait the 3D view is short and the
joystick sits below the timeline.
