# G1 · Game Look — the laptop and phone review (2026-10-23)

Gautham asked for a thorough pass on the laptop and the real Nothing Phone (1), a thorough
report, and suggestions — keeping in mind that the game look feels like it has lost some of the
resemblance COCO Lab should keep to ROS 2, Gazebo and RViz. This file is that report. Every
number links to committed evidence under [`data/g113/`](data/g113/); measured on Gautham's
laptop (i5-13420H, RTX 4050 driver 580.178.04, Intel Raptor Lake-P Mesa 25.2.8, balanced, on AC)
and his phone (Nothing Phone (1) A063, Android 15, Chrome 156, Adreno 642L). Nothing was merged,
deployed or released.

## 1. In one page

- **G1 works on the real phone.** In true full screen, at the shipped defaults (medium, 60 fps),
  10 minutes of driving held **60 fps median** (frame p95 19.2 ms), with **0 WebGL context
  losses and 0 errors**; touch-to-motion **150 ms median** on deliberate swipes. The laptop holds
  the 60 fps ceiling on both GPUs in title, Play and Compare. Determinism is exact across four
  engines; every suite is green.
- **The real phone found six defects the cloud and emulation could not.** Five are fixed and
  re-measured; one is open:

  | # | Defect (found on the real device) | Status |
  |---|---|---|
  | 1 | PLAY never asked for full screen: Play ran under Chrome's address bar (710 × 269 CSS px) | **fixed** — full screen |
  | 2 | No phone frame cap in G1's game: full screen drew 120 fps and ran hotter (skin 41 °C, GPU 59 °C, charging) | **fixed** — M5's 60 fps cap; 60 fps median over 10 min |
  | 3 | At short heights the HUD overlapped: **STOP covered the "MODEL · kinematic" badge** (an honesty invariant) and the minimap covered the joystick label | **fixed** — HUD scales below 320 px; a CI check now catches it (fails 20/20 on the old build) |
  | 4 | Portrait: the rotate card covered PLAY, so nothing could ask for full screen / landscape | **fixed** — "PLAY IN LANDSCAPE" on the card (one tap: full screen, landscape, game starts) |
  | 5 | **Robot vision froze the model**: every 4 s costmap refresh stalled the clock ~0.9 s on the laptop and **3.5–4.1 s on the phone** (18 ticks in 20 s — the game nearly stopped) | **fixed** — cached static costmap + only changed cells sent (byte-identical, tested): laptop no gap over 162 ms; phone 168 ticks in 20 s after the first step of the fix (the final build's phone check is pending — the phone was in use) |
  | 6 | The landscape lock outlived Play | **fixed** — released on leaving Play |
  | — | AUTO tick-gap target (none over 100 ms) | **not met** — 269 → 119–141 ms after one fix (§3) |

- **On the robotics resemblance: you are right, and the plan already says how to fix it.**
  Compare and Research still read as robotics software (costmaps with inflation, expansions,
  clearance, STACK recordings from Gazebo). Play — the first thing people see — reads as a
  warehouse game: stars, a timer, a speed gauge, a hero camera; the ROS-shaped vocabulary is
  hidden behind a small ⓘ chip and a "Robot vision" eye. README §1 ("What ROS 2 at its core means") promises a **ROS graph panel**
  (`/scan`, `/odom`, `/map`, `/plan`, `/cmd_vel`), **every level a real Gazebo world**, a **real
  ROS 2 ghost** racing you, and (§5.1) **model-gap chips** — none of these is in Play yet. §5 proposes how
  to bring them in without turning the game back into a dashboard.

## 2. What was measured (laptop and phone)

### The phone (real device)

| Measurement | Result | Evidence |
|---|---|---|
| Play, 10 min, **true full screen**, defaults (medium, 60 fps cap), no DevTools attached | **60 fps median**, min 44, p05 59; frame median 16.7 ms, p95 19.2 ms, p99 22.6 ms; 4 of 35,931 frames > 50 ms; **0 context losses, 0 errors**; viewport 803 × 361 CSS px, pixel ratio 1.25 | [`phone_free_defaults_10min/`](data/g113/phone_free_defaults_10min/) |
| Heat over that run (charging, started after a 20-min rest at battery 37 °C) | battery 37 → 41 °C; skin 36.0 → 43.0 °C; GPU 39.7 → 62.1 °C; CPU ~42 → 69 °C | same |
| Touch-to-motion (15 deliberate swipes, open floor) | **150 ms median**, p90 193 ms | same (`touch_to_motion.samples[0:15]`) |
| Your saved settings (quality *high*, 120 fps) — 1 min | 73 fps median, frame p95 20.2 ms, touch 197 ms, GPU 45 → 69 °C in one minute: **too heavy for this phone** | [`phone_free_user_prefs_1min/`](data/g113/phone_free_user_prefs_1min/) |
| Cold start ×3 (cache + storage cleared; served by the laptop over USB, **not mobile data**) | first paint 120–132 ms; title 0.66–0.70 s; PLAY ready 8.1–8.7 s (Pyodide ready 4.5 s, the model 7.7 s) | [`phone/`](data/g113/phone/) |
| Viewport vs PHONE_PROFILE.md | assumed 412 × 915 / 915 × 412 at DPR 2.625 → **measured 361 × 654 portrait tab, 710 × 269 landscape tab, 803 × 361 landscape full screen, DPR 2.9875** (your display size is enlarged: density 478 vs 420); landscape safe area **left 46 px** (the punch hole), as assumed | §5 of [`data/g113/README.md`](data/g113/README.md) |
| Robot vision stall | before: 18 ticks / 20 s, gaps 3.5–4.1 s, banner ~14 s; after step 1: 168 ticks, worst gap 880 ms | [`vision_stall/`](data/g113/vision_stall/) |

**Method notes (important for anyone measuring again).** Chrome on Android keeps its status bar,
address bar and navigation bar while DevTools is attached, even when the page is full screen —
every DevTools-driven run measured a 269-px-tall window. `tools/phone/real_phone_free.mjs`
measures as a player: it installs a recorder, detaches, plays with Android's own taps and swipes,
and re-attaches only to read the results. Use it for the next phone gate.

### The laptop

| Measurement | Result | Evidence |
|---|---|---|
| Frame rate, NVIDIA and Intel: title, Play (Fetch Rush, 10 min, medium and high), four-pane Compare | 59.6–60.3 fps median everywhere (headless Chromium ceiling), frame p95 16.9–19.1 ms, **0 context losses**, 0 errors | [`data/g113/README.md`](data/g113/README.md) §4, [`gpu/`](data/g113/gpu/) |
| AUTO press → motion, largest model-tick gap | before 269 ms → after 162/132 ms → after one fix **119/141 ms**: **target (≤ 100 ms) not met** | [`data/g113/README.md`](data/g113/README.md) §3 |
| Determinism | v2 corpus 100 sessions × 4 engines: **0 mismatches**; v3 native-vs-Pyodide gate exact | [`data/g113/README.md`](data/g113/README.md) §6 |
| ROS packages, gz tests | 12/12 packages; gz 2 passed, 0 skipped | [`suites.txt`](data/g113/suites.txt) |
| Gazebo + Nav2 on the Depot (STACK) | independent legs 5/8; the phone-round ghost fails its 2nd leg twice; AMCL ~0.5 m south drift unresolved | [`../m6/RESULTS_M6_FOUNDATIONS.md`](../m6/RESULTS_M6_FOUNDATIONS.md) |

## 3. What is still open (ranked)

1. **AUTO tick gaps** (target ≤ 100 ms): 119–141 ms after the one allowed fix. The rest is step-time
   variance in the worker (28–88 ms). Options: accept (gaps are now presented on a schedule; p95
   107 ms), restate the target as ≤ 150 ms, or a second fix (a longer lead, or shaving the
   worker's slow steps).
2. **Robot vision's first view on the phone** sends ~63,000 cells at once (step 1 measured a 0.88 s
   gap on the phone). The bulk emitter (`Batch.add_many`) should cut it a lot; the phone check of
   the final build is pending (one minute when the phone is free).
3. **Gazebo + Nav2 on the Depot** (M6F.8): Nav2 meets occupied cost where the model's lane-free route
   to Dock 1 passes (twice), and AMCL drifts ~0.5 m south after the dock legs. Until this is
   understood, the "real ROS 2 ghost" of a Fetch Rush round cannot be recorded complete.
4. **Phone round variety**: by the rule as written, one round for every shift (22 m, 4:33.5).
5. **M6F.4**: Pyodide is over the 300 ms planning budget for BFS/Dijkstra/A* on long Depot routes
   (16 of 35) — matters the day a live planner runs during play.
6. Your phone has **quality = high and 120 fps** saved for `localhost:4174`; at those settings the
   phone ran 73 fps and hot. Consider whether the settings sheet should warn, or auto-quality should
   be allowed to step down from a saved *high*.
7. Smaller: the Research cards say "the lab's final phase was succeeded" (grammar); in the tactical
   camera the zone labels sit under the speed gauge; the "clock waits" banner says "planner is
   computing" whatever is computing.

## 4. The robotics resemblance — an honest assessment

**Where COCO Lab still looks like robotics software**

- **Compare**: occupancy grid, inflation radius, cost scaling, robot radius, expansions, path
  cost, minimum clearance, ms per search — the vocabulary of Nav2 and a planning course.
- **Research › Recordings**: 165 recordings, STACK badges, "simulations in Gazebo", failures
  kept, "claims and evidence" per recording.
- **Robot vision** in Play: LiDAR fan, the model's own costmap (lethal / inscribed / inflation) and
  the plan — the most RViz-like thing in the game, but off by default and behind an eye icon.
- **Honesty plumbing**: MODEL · kinematic everywhere, "No physical robot exists", STACK vs MODEL.

**Where it was lost (Play, the first impression)**

- The title says "See what the robot computes" but shows a hero render; nothing on screen is a
  computation until you press V.
- The HUD is a racing HUD: a speed gauge, a timer, stars. A robotics person looks for frames,
  topics, a costmap legend, `cmd_vel`, an odometry pose — none is visible.
- Fetch Rush's results screen scores like an arcade (stars, time) and only links to Compare;
  it does not show what the planner computed for the same task, or what Nav2 did in Gazebo.
- The world looks like a game level (night lighting, bloom). Gazebo's and RViz's visual cues — a
  metric grid, coordinate axes, frames, topic names, a fixed-frame selector — are absent.
- M5's Arena (`?view=arena`) still has a more "engineering tool" feel (KNOWN MAP panel, a plain
  MODEL badge, a 0.30 m/s readout); G1 replaced it as the first thing Play shows.

## 5. Suggestions — robotics identity, without losing the game

These keep README §3's boundary (invariant 2): the model never pretends to be ROS; ROS names are *shown* as
teaching labels ("in the STACK this is `/scan`"), as that invariant explicitly allows.

**A. An "RViz view" in Play (one tap, persistent).** A camera + overlay preset that turns the
same game into what a ROS user expects:
1. a **Displays panel** (collapsible, left): `Grid`, `TF`, `LaserScan`, `Map`, `Costmap
   (global)`, `Path (plan)`, `RobotModel`, `Footprint`, each a checkbox — exactly RViz's names;
2. **TF frames** drawn as small RGB axes at `map`, `odom`, `base_link`, `lidar_link` (the model
   has them: M6F.7 checked the frames and static transforms against the Stack);
3. a **metric grid** on the floor (1 m major, 0.1 m minor) and a scale bar;
4. **LaserScan as points** coloured by range (RViz's default), not only the glow fan;
5. the costmap in **RViz's costmap palette** as an option (the cyan hologram stays the game look);
6. a **Fixed frame: map** chip, and the MODEL · kinematic badge next to it.

**B. A ROS graph panel** (README §1, planned for M6): `/scan → /amcl… → /plan → /cmd_vel` as the model's
equivalent dataflow, with live rates (Hz) from the model's own ticks, each labelled "model
equivalent of the STACK topic". Tap a node → what it computes in coco_lab (glass box).

**C. A telemetry strip (rqt-like)** under the speed gauge, monospace: `cmd_vel v 0.21 ω -0.30`,
`odom x 42.3 y 8.4 θ 337°`, `tick 1462 · t 146.2 s`. Small, optional, on by default in RViz view.

**D. The STACK ghost and model-gap chips in the game.** Once M6F.8's Dock-1 failure is understood,
record the round's Nav2 ghost and race it (translucent, labelled STACK). Until then, the results
screen can show the **planner's own run of the same task** (expansions, path length, clearance —
the Compare metrics) and link to the **matching Gazebo recording** in Research.

**E. Words and type.** Keep "Fetch Rush", but frame orders as missions in robotics terms
("goal: `obj_dock` pre-grasp → `dock_1`", "Nav2-style global plan: A*"). Use a monospace face
(e.g. JetBrains Mono, OFL) for every number that comes from the model, so data looks like data.

**F. The title.** Under "See what the robot computes", show the robot computing: the LiDAR and
costmap layers animating over the hero (the attract demo already exists in M5), and a line
"Built with ROS 2 Jazzy · Nav2 · Gazebo Harmonic recordings".

**G. A "Gazebo view" of the Depot** (Research): the generated SDF's view — plain grey, the
grid, the model tree — next to the game render, so visitors see that the game world *is* a
Gazebo world (M6F.2 already compiles it).

**Order I would do them in:** C and A.1–A.3 (cheap, high signal), then D (results screen with the
planner's run), then B (graph panel), then A.4–A.6 and F, then G; the STACK ghost when M6F.8 is
solved.

## 6. Other suggestions

- **Phone gate:** adopt `real_phone_free.mjs` as the phone procedure (DevTools-free); add the
  real-phone viewport (710 × 269) to every layout check (done for the chase HUD check).
- **Defaults:** keep medium + 60 fps for phones (measured); consider auto-quality that can step
  down from a saved *high* when frame time says so.
- **Robot vision cost:** the costmap view is now incremental; the LiDAR fan could be made more
  visible (it is hard to see in the review screenshots, `data/g113/review_shots/04-…`, NVIDIA).
- **AUTO gaps:** if the target matters, profile the worker's slow steps (28 → 88 ms) — likely
  Grasp Assist or LiDAR casting on some ticks.
- **Copy:** fix "was succeeded"; rename the busy banner to what is computing.
- **Testing:** the cloud could not see any of the phone defects; schedule a real-phone run at every
  look-changing checkpoint (it now takes ~15 minutes, unattended, with the phone plugged in).

## 7. What changed in this pass (G1.13, laptop + phone)

`lab_web/src/game/PlayGame.tsx` (full screen on PLAY, the phone frame cap, PLAY IN LANDSCAPE,
the lock released, delta costmap requests), `lab_web/src/game/game.css` (short-height HUD),
`lab_web/src/game/session.ts` (ticks shown on a schedule), `coco_lab/coco_lab/costmap.py`
(`StaticLayers`, `emit_cells`), `coco_lab/coco_lab/columns.py` (`Batch.add_many`),
`lab_web/src/arena/arena_glue.py` + worker/client/protocol (delta costmap view), tests
(`test_costmap_static_layers.py`, glue, session pacing, the chase/HUD check), and the phone tools
(`tools/phone/real_phone.mjs`, `real_phone_free.mjs`), `tools/g1/vision_stall.mjs`,
`tools/g1/review_shots.mjs`. Screenshots for this review: [`data/g113/review_shots/`](data/g113/review_shots/).

**Privacy note:** some phone screenshots pushed earlier (commit `2ee5f63`) showed the phone's
status bar (notification icons). The committed copies are now redacted; the earlier versions
remain in git history (history is never rewritten here). A screenshot that caught your
WhatsApp list during this pass was deleted and never committed.
