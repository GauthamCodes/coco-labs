# COCO Lab — roadmap

> **Status, 2026-10-01: Lab 1 complete and released.**
> - The Lab 1.1 open items (§5) were delivered on 2026-10-01, and
>   `lab1-v1.0` is published with the demo video:
>   <https://github.com/GauthamCodes/coco-labs/releases/tag/lab1-v1.0>.
> - COCO Lab now lives in its own repository, `GauthamCodes/coco-labs`,
>   served at <https://gauthamcodes.github.io/coco-labs/>.
> - Phases 0 and 1 are closed. 1G (optional) was not run. Lab 1.2 is
>   deferred (§5).
> - **Phase 2 (Live), 2026-10-04: Parts A–C done, Part D (ship) in progress.**
>   The Live tab is on the public site; a phone on mobile data drove the robot
>   through Tailscale Funnel. Status against §6's "done when" is in
>   [`docs/live/LIVE.md`](live/LIVE.md) and the report
>   [`docs/live/PART_C_REPORT.md`](live/PART_C_REPORT.md).
>
> - **Phase 3 (Localise, Lab 2), 2026-10-04: implemented, tested,
>   measured and deployed.** `main` was fast-forwarded to `4405065` with
>   `CI` and `Lab` green, and Lab 2 is live at
>   <https://gauthamcodes.github.io/coco-labs/?view=localise> (verified on
>   the public site, headless Firefox). Its demo video was re-recorded from
>   the public site. The `live-v1.0` (Phase 2) and `lab2-v1.0` (Phase 3)
>   tags and releases are **published** (2026-10-04, owner-approved):
>   <https://github.com/GauthamCodes/coco-labs/releases/tag/live-v1.0>,
>   <https://github.com/GauthamCodes/coco-labs/releases/tag/lab2-v1.0>
>   (with the video). Status against §6's "done when" and the remaining
>   items: [`docs/labs/LAB2_LOCALISE.md`](labs/LAB2_LOCALISE.md).
>   *(Until 2026-10-04 this line read "implemented, tested and measured on
>   branch `lab2`; not yet deployed".)*
> - **Phase 4 (Map, Lab 3), 2026-10-05: implemented, tested, measured
>   and deployed.** `main` was fast-forwarded to `ee9bd65` after CI and Lab
>   were green on the PR, and the site was verified on the public URL
>   (0 console errors, headless Firefox). The demo video was recorded from
>   the public site. `lab3-v1.0` is **published** (2026-10-06,
>   owner-approved): <https://github.com/GauthamCodes/coco-labs/releases/tag/lab3-v1.0>
>   (with the video). *(Until 2026-10-06: "tagged LOCALLY with a DRAFT
>   release; publishing it is the owner's call".)* Status, numbers and limitations:
>   [`docs/labs/LAB3_MAP.md`](labs/LAB3_MAP.md).
>   *(Until 2026-10-05 16:30 UTC this line read "implemented, tested,
>   measured on branch `lab3`".)*
>
> - **Phase 5 (Search, Lab 4), 2026-10-06/07: implemented, tested,
>   measured and deployed** (`main` fast-forwarded to `0cb5588`,
>   owner-approved; verified on the public site with 0 console errors;
>   video recorded from it). `lab4-v1.0` is **published** (2026-10-07,
>   owner-approved): <https://github.com/GauthamCodes/coco-labs/releases/tag/lab4-v1.0>
>   (with the video). *(Until 2026-10-07: "tagged LOCALLY with a DRAFT
>   release — publishing is the owner's call".)* *(Until 2026-10-07: "implemented, tested
>   and measured on branch `lab4`".)* The autonomous mission now DISCOVERS the
>   target (told only the colour; `coco_lab.regionsearch` chooses the bays),
>   and the Live label follows what the running mission reports. Gazebo
>   matrix (measured, 16 runs, fresh simulator each): 14 COMPLETE, 2 ABORT
>   (one localisation failure on the return after a correct find; one the
>   deliberate stop-after-the-first-bay order); every recorded search
>   replays byte for byte through coco_lab. Write-up
>   [`docs/labs/LAB4_SEARCH.md`](labs/LAB4_SEARCH.md).
>
> - **Phase 6 (Move, Lab 5), 2026-10-07: implemented, tested, measured and
>   deployed** (`main` fast-forwarded to `0fef157` on green CI; verified on
>   the public site with 0 console errors; video recorded from it;
>   release record on `main` = `2b6f8ad`). `lab5-v1.0` is **published**
>   (2026-10-08, owner-approved):
>   <https://github.com/GauthamCodes/coco-labs/releases/tag/lab5-v1.0>
>   (with the video). *(Until 2026-10-08: "tagged LOCALLY with a DRAFT
>   release — publishing is the owner's call".)* *(Until deployment:
>   "implemented, tested and measured on branch `lab5`".)* DWB, MPPI and Regulated Pure Pursuit on the same
>   frozen global paths (54 Gazebo runs, fresh simulator each, 0 void),
>   apron-only kinematic actors, run 15's mechanism reproduced (its exact
>   symptom not), D\* Lite in coco_lab with the Lab 5 view
>   (`?view=move`). Write-up [`docs/labs/LAB5_MOVE.md`](labs/LAB5_MOVE.md).
>
> *(The status line of 2026-09-30 read: "plan revised (Phase 2 · Live
> added) … Phase 1 closed by decision with open items … Phase 2 not
> started.")*
> This roadmap supersedes the priority order in the COCO 2.0 master context
> (§45). Everything else in that document — its invariants, protected files
> and git rules — still holds. The previous roadmap is archived at
> [`docs/history/ROADMAP_COCO2.md`](history/ROADMAP_COCO2.md), and this
> plan as first installed (before Phase 2 · Live) at
> [`docs/history/ROADMAP_LAB_2026-09-28.md`](history/ROADMAP_LAB_2026-09-28.md).
>
> Session prompts: [`docs/LAB_PHASES.md`](LAB_PHASES.md) ·
> Current state: [`docs/SESSION_LOG.md`](SESSION_LOG.md) ·
> Measured results: [`docs/RESULTS.md`](RESULTS.md)

Numbers in this document are **targets** unless marked **(measured)** with a
pointer to `RESULTS.md`. Week counts are part-time estimates, not
measurements. "COCO Lab" is a working title; Phase 0 picks a name people can
actually search for.

---

## 1. What COCO Lab is

**An interactive, browser-based robotics curriculum that runs on a real ROS 2
robot — and lets you drive that robot live: by joystick, by Nav2 goal, or by
handing it the whole mission.**

The well-known algorithm visualisers stop at the grid. PathFinding.js and Red
Blob Games show search spreading over cells. PythonRobotics animates filters
and SLAM as recordings you can't interact with. RViz and Foxglove show
whatever a robot publishes, and Nav2's planners don't expose their search as
something a learner can step through. COCO Lab sits in that gap, and it can
show two things none of them can:

- **The textbook-to-robot gap.** The grid path solves the textbook problem.
  Then a robot with a real footprint, an inflated costmap, a local controller
  and imperfect localisation has to drive it. The difference between the line
  and what the robot actually does is where most of robotics lives.
- **The belief-to-truth gap.** What the robot thinks versus where it really
  is. Only a simulator knows the truth, and EpisodeSpec already enforces the
  boundary in code: the manifest is privileged, and `task_view` is all the
  robot gets. The platform turns that anti-cheat invariant into a "show
  truth" toggle.

The mental model is a cutaway engine in a museum: you watch the pistons move,
and it actually runs.

**One principle holds it together: same inputs, different algorithm, measured
outputs.** Every comparison fixes the map, start, goal, recorded drive and
seed — the discipline of the 1,080-episode baseline matrix, applied to
teaching. Every scenario is an EpisodeSpec, so every scenario is a
reproducible, shareable link.

### What it is not

- **Not a game-engine imitation of a robot.** The robot runs the real ROS 2 /
  Nav2 stack. The browser displays and asks; it never decides.
- **Not a replacement for the stack.** Every lab ties back to something the
  real robot did, recorded with provenance.
- **Not, yet, an always-on hosted robot.** The public site is static. The
  live robot runs on the Docker stack: locally for anyone who runs it, and on
  the public site during scheduled live sessions (§3.5).

---

## 2. Why the direction changed

The master context's priority order — P0.4, then cross-simulator generation
and Isaac, then dynamic obstacles, then learning, then a multi-user browser
platform — was sequenced for an **autonomy research platform**. For a
**learning platform**, the value comes from different places: access without
installing anything, algorithm internals made visible, and comparisons that
are honest because their inputs are fixed. The existing work maps onto that
almost entirely. It needs reordering, not replacing.

The project also already owns its best teaching material, in the form of
measured, documented failures:

| Documented result | Concept it teaches | Lab |
|---|---|---|
| AMCL `recovery_alpha_fast/slow` = 0.0, so it cannot escape a confident wrong mode | Particle injection | 2 |
| Global relocalisation converged inside the ramp footprint on a self-similar map | Perceptual aliasing | 2 |
| AMCL covariance moved the wrong way at divergence | Filter overconfidence; covariance is not health | 2 |
| Coulomb friction not identifiable: τ spans 0.0003 across a μ span of 0.35 | Observability | Later (Estimate) |
| SmacPlanner2D path 6.2% shorter than NavFn's (M3) | Implementation vs algorithm | 1 |
| Run 15: after AMCL drifted, DWB scored 0 of 819 trajectories | Local planning under bad localisation | 5 |
| B2, a gain-scheduled PD with privileged terrain, at 98% on Route A | When learning isn't needed | Later (Learn) |

### Disposition of the previous priority order

| Previous item | Now | Reason |
|---|---|---|
| P03C consolidation | Done; lands on `main` in Phase 0 | Not yet on the remote |
| P0.4 autonomous discovery | **Phase 5**, as Lab 4 (Search) | Search under uncertainty is a belief problem and teaches better after Localise and Map. The master context's design (§17–25) is unchanged; it is built visualisation-first |
| Cross-simulator scene generation; full Isaac backend | **Deferred** (§9) | 6 GB VRAM limits already hit (LLVM, OOM); little learner value from a second renderer; cross-engine rigour already shown — 0.242 mm MuJoCo–Gazebo parity (measured) |
| Dynamic obstacles | **Phase 6**, in Lab 5 (Move) | Apron only, per the M7_DESIGN §2.6 spec |
| Advanced learning / RL | **Later lab** (Learn) | Phase 3 and C2-M2 measured that RL isn't justified on this task; that finding is the lesson |
| Browser control of the real robot, including remote sessions | **Phase 2** (Live) | The three modes already exist in coco.v1; scheduled sessions through a tunnel make them public without running costs |
| Always-on hosting; concurrent multi-user sessions; cloud | **Deferred** (§9) | It needs a host that can render Gazebo's sensors, and it costs money and operations before there's a measured audience |

---

## 3. Architecture

```mermaid
flowchart TB
  subgraph PUB["Public tier: static site, no install"]
    APP["Web app<br/>Replay and Sketch modes"]
    PYO["Pyodide web worker<br/>runs coco_lab"]
  end
  subgraph CORE["coco_lab: pure Python, no rclpy"]
    ALG["Algorithms<br/>emit versioned traces"]
    BUN["Scenario bundles<br/>arrays plus provenance"]
  end
  subgraph LIVE["Live tier: Docker stack, local"]
    NODE["coco_lab_ros planner node"]
    NAV["Nav2 FollowPath<br/>existing command chain"]
    ARB["cmd_vel_arbiter<br/>sole wheel publisher"]
    REC["rosbag2 recorder<br/>and exporter"]
    PS["platform_server<br/>coco.v1"]
  end
  CI["CI property tests<br/>no ROS needed"]

  ALG --> PYO --> APP
  ALG --> NODE --> NAV --> ARB
  ALG --> CI
  REC --> BUN --> APP
  APP -.->|live mode, Phase 2| PS
```

### 3.1 `coco_lab` — the core

Pure Python, **no `rclpy`**, with a standard-library-only runtime in Phase 1
(numpy may be added later if a lab measurably needs it). It builds with colcon
**and** installs with pip in a ROS-free venv; CI proves the second.

Algorithms operate on a generic graph interface — neighbours, edge cost,
heuristic — and the grid is one implementation. That is what lets a
*(cell, heading)* state space, and later Hybrid A\*, reuse the same code.

The same code runs in three places: CI, where property tests prove it; the
browser, via Pyodide in a Web Worker; and a ROS node, where it plans for the
real robot.

### 3.2 Traces and scenario bundles

- **Trace.** Every algorithm emits a versioned, columnar event stream (push,
  expand, relax, path) carrying cell, g, h and parent, plus a summary:
  expansions, path cost, path length, status. Later labs add event types —
  particle sets, pose-graph iterations — under the same versioning rule.
- **Bundle.** `manifest.json` plus little-endian typed arrays, optionally
  gzipped. The manifest carries provenance: source kind (`glass-box`,
  `recorded-run`, `sketch`), `coco_lab` version, git commit and dirty flag,
  seed, EpisodeSpec hash where applicable, creation time, and for recorded
  runs the rosbag2 file hash and sim-time range. Every replay can say which
  run produced it.
- **Versioning.** Additive changes within a major version; anything that
  changes meaning bumps it. This is the same rule coco.v1 uses.

### 3.3 The public tier

A static site on GitHub Pages: free to host, no install, no analytics, no
cookies, and it opens on a phone, which is where most people will first click
the link. Two modes, **always labelled on screen**, plus Live during scheduled
sessions (§3.5):

- **Replay** — real runs recorded from the Docker stack and exported to
  bundles, with provenance shown.
- **Sketch** (from Phase 3) — a 2D differential-drive and ray-cast LiDAR model
  in the browser, so anyone can drive, kidnap and map without Gazebo.

Sketch is the one place the project's no-fake-simulation rule bends, so it
bends the way MuJoCo did: Sketch and Gazebo are compared at identical poses,
and the fidelity number is published beside the mode label. The remaining gap
(Sketch wheels never slip) is itself a lesson.

Editing — painting a map, changing settings — recomputes traces with
`coco_lab` running under Pyodide in a Web Worker, lazy-loaded only when a
user edits.

### 3.4 The real-stack hook

`coco_lab_ros` hosts a planner node that reads the real global costmap, plans
from the robot's AMCL belief, publishes its trace, and hands the path to
Nav2's `FollowPath` action. The controller server tracks it, and commands
still flow through the existing chain into `cmd_vel_arbiter`. The algorithm a
learner watched really drives the robot, and **nothing new publishes to the
wheels**. Lab runs use a lab-only Nav2 parameter overlay, so the mission's
configuration is untouched.

### 3.5 The live robot (Phase 2)

The flagship view: the real robot, moving, controllable from the page in
three modes. The capability already exists — coco.v1 has the intents and
`cmd_vel_arbiter` already mediates the modes — so Phase 2 carries it into
COCO Lab rather than building it.

| Mode | What you do | coco.v1 intents (exist today) | What drives the wheels |
|---|---|---|---|
| Teleop | Joystick or keyboard | `set_mode: teleop`, `drive` | You, through the arbiter's teleop input |
| Nav2 | Click a goal on the map | `set_mode: auto`, `nav_goal` | Nav2, through the relay and the arbiter |
| Autonomous | Pick a colour, press start | `select_target`, `mission: start / abort` | The mission executive, handing the wheels between Nav2, the RL policy and the approach controller |

`stop` works in every mode, and the arbiter already lets teleop preempt any
autonomous source. The live panel makes that visible rather than hiding it.

**What the page shows:**

- the arena map with the robot's pose live — its belief, with the truth
  toggle, since the server already subscribes to the ground-truth
  `/model/coco/odometry`
- the camera stream, which the server already serves as MJPEG
- the active mode, who holds control, and which source the arbiter is
  forwarding
- the global plan and local trajectory in Nav2 mode, and the mission's state,
  step by step, in autonomous mode

A 3D view of the robot rendered in the browser from its own URDF and STL
meshes, driven by live telemetry rather than video, is the should-have. It
looks like the real thing, and spectators cost almost no bandwidth.

**New work beyond carrying the panel over:**

- **Driver and spectators.** The platform is single-session by design
  (P0.1). Remote sessions need one driver holding a control code, everyone
  else watching, an idle timeout and a session time cap.
- **Scheduled public sessions.** The Docker stack on this machine, reachable
  through a tunnel (Cloudflare Tunnel or Tailscale Funnel, for example) so no
  router ports open, exposing only the coco.v1 endpoint. The public site
  shows "live now" or the next session time. Hand an interviewer the control
  code and let them drive.
- **Lab hooks.** In Nav2 mode, choose the planner: Nav2's SmacPlanner2D, or
  any Lab 1 planner through the `FollowPath` hook from 1C.
- **Small additive intent changes**, such as an optional heading on
  `nav_goal`, which takes only x and y today. All of it goes through
  `safety.PUBLISH_ALLOWLIST`; the browser still never names a topic and never
  owns robotics logic.

**Honest labels.** Until Lab 4 (P0.4) landed, the autonomous mode was told
which lane the colour is in — `resolve_lane()` handed the mission the
answer, from the episode's region map or, with none, exactly
`lane_for_colour()` — and the page said so. Since Phase 5 (2026-10-06) it
discovers the target (`mission.launch.py search:=true`, the default), and
the label is chosen from what the RUNNING mission reports on
`/mission/search`: "discovers" only for `mode=discover`, told for a stack
launched `search:=false`, no claim for one that reports nothing.

Outside a live session, the public site shows Replay and Sketch, plus a short
Docker quickstart for running the whole stack and driving it locally.
Always-on hosting stays deferred (§9).

**As built (2026-10-04).** Three modes, driver and spectators, scheduled
sessions through **Tailscale Funnel** (`/ws` and `/healthz` only), the
public "live now" status, and the Docker remote configuration are built
and measured (`docs/live/`). **Not built:** the planner choice in Nav2
mode (lab hook), the optional `nav_goal` heading, and the 3D view. They,
and the phone test's production findings (remote stability, telemetry
rate, mobile layout, visualisation), are the prioritised backlog in
`docs/live/LIVE.md` §9.

---

## 4. Platform invariants

These join `CLAUDE.md` in Phase 0. The master context's invariants — protected
files, forbidden git commands, a fresh simulator per run, never `--fast`,
killing by process name — all still apply.

1. **`coco_lab` never imports `rclpy`.** A test enforces it, as it does for
   `protocol.py` and `mujoco_env.py`.
2. **The browser never names a topic**, and never commands the robot except
   through coco.v1 intents added additively.
3. **No new wheel publisher.** Lab planners move the robot only via
   `FollowPath`, through the existing command chain into `cmd_vel_arbiter`.
4. **Every mode is labelled on screen:** Replay (recorded real run, provenance
   shown), Sketch (browser model, measured fidelity shown), Live (local
   stack).
5. **Every claim shown to a learner is backed** by a property test or a
   (measured) result, and the exhibit cites it. Theorems are tested, not
   asserted.
6. **Comparisons hold inputs fixed:** map, start, goal, recording, seed.
7. **Trace and bundle schemas are versioned.** Breaking changes bump the major
   version.
8. **The TypeScript UI never re-implements an algorithm.** It renders traces
   and asks `coco_lab`.
9. **Live control is exclusive and interruptible.** One driver holds control
   at a time; teleop preempts autonomy, as the arbiter already guarantees;
   `stop` is always one tap away; remote sessions expose only the coco.v1
   endpoint.

---

## 5. The labs

Build order and curriculum order are the same: each lab needs the concepts of
the one before. Labs also plug into the live robot (§3.5) where they can:
Lab 1's planners become choices in Nav2 mode, and Lab 4 turns the autonomous
mode from told to discovering.

| Lab | What learners play with | Where the real robot comes in |
|---|---|---|
| 1 · Plan | BFS, Dijkstra, A\*, greedy best-first, weighted A\*; paint obstacles, race, predict-then-reveal | Paths driven via `FollowPath`; SmacPlanner2D conformance; the A\* exhibit |
| 2 · Localise | Particle filter vs EKF; kidnap the robot; particle and injection sliders; truth toggle | AMCL failures replayed; `recovery_alpha` and `robot_localization` A/Bs |
| 3 · Map | Occupancy mapping → EKF-SLAM → FastSLAM → pose graph; "map the arena" | slam_toolbox vs Cartographer on identical drives; trajectory error and map score |
| 4 · Search | The robot knows only "red": belief over bays, negative search, your order vs the policy | P0.4, built visualisation-first; the live autonomous mode starts discovering instead of being told |
| 5 · Move | DWB vs MPPI vs Regulated Pure Pursuit; moving actors; D\* Lite | Nav2 trajectory debug topics; run 15's "0 of 819" explained |

### Lab 1 — Plan (v1 scope)

- **Algorithms, capped at five:** BFS, Dijkstra, A\*, greedy best-first,
  weighted A\*.
- **Controls:**
  - a heuristic picker (zero, Manhattan, Euclidean, octile) with an
    admissibility and consistency badge computed by the core
  - 4- vs 8-connectivity and a tie-breaking toggle
  - a weighted-A\* slider: w = 0 is Dijkstra, w = 1 is A\*, and large w drifts
    toward greedy, with the suboptimality bound shown live
- **Maps, escalating:** a 20×20 teaching grid → the arena's occupancy map →
  the inflated costmap with the robot's footprint swept along the path.
- **Games:** predict-then-reveal; race mode; paint and recompute; one
  break-the-planner challenge ("greedy at least 2× optimal", verified
  automatically); share links that reproduce the exact trace.
- **Real robot:** three recorded runs (A\*, Dijkstra and greedy on the same
  start and goal) with ground truth, belief and plan overlaid;
  SmacPlanner2D conformance reported.
- **Exhibit, "The A\* myth, twice":** with admissible heuristics and identical
  costs, A\* and Dijkstra return equal-cost paths. The algorithm changes the
  work, not the answer.
  - (a) Live proof on the same map.
  - (b) COCO's 6.2% SmacPlanner2D-vs-NavFn gap, explained by NavFn's
    `calcPath` gradient-descent path extraction.
  - (c) The ISRO simulator's "A\* 4% longer" result, tested against two
    hypotheses: a cell-only search state under a heading-dependent turn
    penalty, and an octile heuristic that overestimates for the move costs
    used. It is labelled a diagnosis only if the ISRO source is examined;
    otherwise it is a reconstruction.
- **Later increments (Lab 1.2+):** JPS, Theta\*, RRT / RRT\* / PRM, Hybrid A\*;
  and the games listed under Lab 1.2 below.

#### Lab 1.1 — Lab 1 must-haves not delivered when Phase 1 closed (2026-09-30) — all delivered 2026-10-01

Phase 1 was closed by decision after 1D and a partial 1F; 1E was never run
as a session (`docs/SESSION_LOG.md`, "PHASE 1 — COMPLETE" and the plan
revision entry). What exists on the public site is 1D's trace player: ten
catalog bundles, recorded-run overlays, mode badges, and a one-cell edit
recomputed by `coco_lab` in Pyodide. Still owed, from `LAB_PHASES.md` 1E
and 1F:

- **1E.1 Settings panel:** the five algorithms; the heuristic picker with
  the admissibility and consistency badge from `coco_lab`;
  4/8-connectivity; a tie-breaking toggle; the weighted-A\* slider (0–5)
  with the suboptimality bound shown live. **Done in Lab 1.1 Part A
  (2026-10-01).** The badge and the bound are looked up in a table
  `coco_lab` computes at site build time (`search.suboptimality_bound`,
  checked on 1,000 maps by `test_the_reported_suboptimality_bound_holds`);
  the slider moves in 0.25 steps so every bound shown is one it computed.
- **1E.2 Map ladder:** teaching grid → arena occupancy → inflated costmap
  with the footprint (from `coco_config`) swept along the path. **Done in
  Lab 1.1 Part A.** The third rung is Nav2's own global costmap from the 1C
  A\* run, downsampled x2 by `coco_lab`; the footprint, 0.297 m x 0.314 m,
  is *derived* from `coco_config` (chassis and wheels) and drawn only on a
  map with geo.
- **1E.3 Race mode:** two to four algorithms on identical inputs, a
  synchronised step counter, and the final table. **Done in Lab 1.1 Part
  A.** The shared counter counts expansions; the optimum is `coco_lab`'s
  Dijkstra on the same inputs.
- **1E.4 Predict-then-reveal.** **Done in Lab 1.1 Part B (2026-10-01):**
  before a race ("which will expand the fewest cells?") and before a
  settings run ("will the path cost more, less, or the same?"); the reveal
  reads the trace summaries coco_lab wrote.
- **1E.5 Paint obstacles and recompute:** **Done in Lab 1.1 Part A.** A
  1, 3 or 5 cell brush paints or erases; a drag is one stroke, applied and
  searched by `coco_lab` in Pyodide. A stroke over the start or the goal is
  refused with a message, by the page and again by the worker.
- **1E.6 Share links** encoding seed, edits and settings, with a tested
  round trip. **Done in Lab 1.1 Part B.** Format v1 names the catalog
  bundle, the settings and the map edits (run-length), plus the trace's
  digest; opening a link reruns coco_lab and says whether the trace came
  out identical. CI tests the round trip in both languages
  (`test/share.test.ts`, `tools/test_glue.py::test_share_vectors_reproduce_their_trace_digests`).
  There is no seed to encode: no Lab 1 input is random (the daily seed is
  Lab 1.2).
- **1E.8 "Driven by COCO":** **Done in Lab 1.1 Part B.** The tracking-error
  plot is 1C's definition, recomputed at site build by 1C's own code and
  refused unless it reproduces the recorded n / mean / p95 / max exactly;
  the provenance line shows the commit, the seed (none: a real run is not
  seeded), the bundle hash and the rosbag hash.
- **1E.9 The exhibit, "The A\* myth, twice"** (a)–(c), every claim cited.
  **Done in Lab 1.1 Part B.** (a) runs live; (b) reports 1C's measured
  analogue — M3's 6.2 % itself stays *neither reproduced nor refuted*, and
  the analogue's paths are not drawn because 1C recorded their lengths, not
  their coordinates; (c) is labelled a reconstruction, as 1B recorded it.
  A test checks that every test the page cites exists.
- **1F.1 `docs/labs/LAB1_PLAN.md`.** **Done (Lab 1.1 Part C, 2026-10-01).**
- **1F.2 README:** the "Try it" link to the public URL at the top, a short
  Lab 1 section, and the planner claim linked to the exhibit. **Done (Part C).**
  (the planner claim itself was corrected in Phase 0).
- **1F.3 Demo video,** 60–90 s, of the web app. **Done (Part C):** 65.3 s,
  recorded from the public site, viewport only; one cut, the Pyodide
  warm-up (6.6 s), before recording.
- **1F.4 Tag `lab1-v1.0` and a draft release** with the video and notes.
  **Done, and published with the owner's approval (2026-10-01)**, on
  `GauthamCodes/coco-labs`.
- **1F.5 Final checks:** CI green on `main`, per-package counts, and the
  page at phone width (headless Firefox, 390 × 844) are *done*. A real
  phone, and a share-link round trip, are *not*. **Done (Part C):** a
  share link round-trips in CI (both languages), in headless Firefox on
  the public site, and — owner-reported — on a Nothing Phone (1) in Chrome,
  where the page loaded, the trace played and a share link showed "This
  link reproduced the exact trace".

#### Lab 1.2 — deferred from Lab 1.1 by the owner (2026-10-01)

Not part of Lab 1.1; each stays a Lab 1 increment, and none adds an
algorithm:

- **Break-the-planner challenge** (was 1E.7): "paint a map where greedy
  best-first's path costs at least twice the optimum", verified
  automatically.
- **Beat-the-planner:** draw your own path and compare it with the search.
- **Stars:** one to three, per exercise.
- **Daily seed.**

### Lab 2 — Localise

- **What learners do:** compare a particle filter and an EKF on identical
  inputs, kidnap the robot, and adjust particle count, motion noise and
  injection. A belief-vs-truth toggle and an error plot show the gap.
- **Exhibits:** the three localisation limitations in §2, replayed from real
  runs.
- **Real-stack work that is also an engineering fix:** a kidnap-recovery A/B
  with non-zero `recovery_alpha_*`, and a `robot_localization` EKF fusing
  wheel odometry and IMU (motivated by run 15).
- **Sketch mode lands here**, with its fidelity measured against Gazebo.

**As built (2026-10-04, branch `lab2`).** Sketch (coco_lab: 2D diff drive
+ ray-cast LiDAR, seeded) with its fidelity shown beside the mode
(measured: 86.7 % of beams within 5 cm at 237 identical poses; odometry
exact on straights, wrong on turns); MCL (nav2_amcl's likelihood field,
score and injection) and EKF localisation, traced in loc bundle 1.0; the
Lab 2 view with every listed control, belief vs truth, error plot, race and
predict-then-reveal; the four exhibits, each cited. Real stack: the
kidnap A/B (shipped 0 / 10, injection 2 / 10 — unresolved, p = 0.237);
robot_localization (wheel pose + gyro) cut a 120 m tour's worst odometry
error from 21.6 m to 0.21 m on identical recorded drives (an upper bound:
noiseless sim gyro), observe-only, the mission untouched. Numbers:
`docs/RESULTS.md` "COCO Lab Phase 3"; write-up `docs/labs/LAB2_LOCALISE.md`.
Deployed 2026-10-04 from `main` = `4405065` and verified on the public
site (measured: `docs/RESULTS.md` "COCO Lab Phase 3" > "On the public
site").

### Lab 3 — Map

- **Progression:** occupancy-grid mapping with known poses → EKF-SLAM with an
  idealised landmark sensor (labelled as idealised) → FastSLAM, the
  Rao-Blackwellised particle filter behind GMapping → pose-graph SLAM with
  loop closure.
- **Real backends:** slam_toolbox (already in the stack) and Cartographer
  (its ROS 2 port is released for Jazzy; upstream is dormant), run on
  **identical recorded drives**. GMapping and Hector are ROS 1-era and not
  officially released for Jazzy (verified 2026-10-05: no `ros-jazzy-`
  gmapping or hector package in apt; Cartographer, slam_toolbox, RTAB-Map
  and MRPT are), so their ideas live in `coco_lab` rather than in
  unofficial ports.
- **Metrics:** absolute trajectory error against ground truth, and a map
  score against a ground-truth occupancy map rasterised from the world
  generator.
- **Challenge:** "map the arena" in Sketch mode, scored. Learners discover
  that loop closures help and featureless corridors hurt.

**As built (2026-10-05, branch `lab3`; deployed from `main` = `ee9bd65`).** coco_lab: log-odds occupancy
mapping, EKF-SLAM on an IDEALISED landmark sensor (labelled), grid FastSLAM
(Rao-Blackwellised), pose-graph SLAM (MAP point-to-line ICP, loop closure
on well-constrained matches, Gauss-Newton with a chain-preconditioned CG),
the metrics (ATE after a rigid alignment; map precision / recall / F1 at
0.10 m against visible truth walls; coverage), map bundle 1.0. The Lab 3 view
(`?view=map`): Sketch scenes (loop room, featureless corridor, landmarks
room), the "map the arena" challenge scored round(100 x F1), and a Replay of
a recorded tour. Real backends on two identical recorded 121 m tours, three
rounds (measured): slam_toolbox (project config) 0.103 / 0.793 m online ATE,
map F1 0.933 / 0.400; Cartographer (released config) F1 0.19 / 0.17 with
global SLAM on, 0.88 / 0.92 off — loop closure hurt on these drives,
reproduced, not attributed. coco_lab on the same drives: pose graph 0.267 /
0.758 m, FastSLAM 0.12–0.24 / 0.09–0.53 m (5 seeds). Numbers:
`docs/RESULTS.md` "COCO Lab Phase 4"; write-up `docs/labs/LAB3_MAP.md`.

### Lab 4 — Search (P0.4)

- **What learners see:** the robot knows only "red". Belief over bays,
  searched-region bookkeeping, negative search, the robot's deterministic
  policy against the learner's chosen order, and expected search cost.
- **Build:** to the master context's P0.4 design, visualisation-first,
  including its anti-cheat tests.
- **Mission theatre:** the live panel's autonomous mode, with the search
  visualised as it happens — belief/truth overlays and the FSM timeline. From
  here on the autonomous mode discovers the target instead of being told,
  and its label changes to say so.

**As built (2026-10-06/07, branch `lab4`).** The master context's P0.4 text
is not in the repository; this section and the Phase 5 brief were the spec.
coco_lab: `regionsearch` (belief over COCO's four bays, Bayes on a miss,
the exact expected-cost order over every remaining order, d = 0.9 ASSUMED,
uniform prior, teaching policies nearest-first / most-likely-first /
the learner's order, a seeded Sketch, `replay_search` of recorded looks)
and search bundle 1.0 (`docs/labs/SEARCH_FORMAT.md`). The mission:
SELECT_SEARCH_REGION, SURVEY_REGION, MARK_REGION_SEARCHED, LEAVE_REGION
(`/ramp/retreat`: back down the ramp it climbed) around the proven fetch;
told only `task_view()`'s colour (anti-cheat tests in coco_sim,
coco_mission, coco_lab). The Lab 4 view (`?view=search`): your order,
predict, reveal coco_lab's plans, place the target and watch both search;
Replay of the Gazebo runs with their FSM timeline and an evaluator-only
truth toggle; every claim with its test. Gazebo (measured, 16 runs):
14 COMPLETE, 2 ABORT; numbers `docs/RESULTS.md` "COCO Lab Phase 5"; write-up
`docs/labs/LAB4_SEARCH.md`.

### Lab 5 — Move

- DWB vs MPPI vs Regulated Pure Pursuit on identical paths, with rollouts
  taken from Nav2's own debug topics.
- Run 15's "0 of 819 trajectories" explained.
- Moving actors on the apron only (M7_DESIGN §2.6). Gazebo actors are
  ray-cast-visible but produce no physics contacts, so account for that.
- D\* Lite replanning when the world changes.

**As built (2026-10-07, branch `lab5`).** A lab-only controller overlay
(`coco_lab_ros/config/nav2_move_overlay.yaml`) loads MPPI and RPP beside the
mission's untouched DWB, every robot limit equal; `lab_planner path_file:=`
sends one frozen SmacPlanner2D path to any of them. Rollouts are Nav2's own:
DWB `/evaluation`, MPPI `/trajectories`, RPP's lookahead and arc. Actors
(`lab_actors`): visual-only grey cylinders, no collision geometry, poses
driven through Gazebo, robot-triggered, validated to the apron; contacts are
measured from ground truth. Metrics fixed before measuring
(`coco_lab.movemetrics`: tracking error, travel time, RMS commanded
accelerations, minimum footprint clearance). Gazebo (measured, 54 runs):
static room DWB 0/5, MPPI 5/5, RPP 5/5; crossing 15/15; oncoming — nobody
swerved, the person reached a stopped robot in 15/15; mislocalised by run
15's 3.4 m — all three controllers refused the path in their first cycle
(`INVALID_PATH`, 0 candidates scored), the mechanism of run 15 but not its
"0 of 819". D\* Lite (`coco_lab.dstarlite`, `coco_lab.replan`): optimal after
every change (1,000-map properties); less total work than A\* from scratch in
191 of 200 Sketch worlds, but 2.9x MORE on Nav2's real costmap change
(Experiment C). Numbers: `docs/RESULTS.md` "COCO Lab Phase 6"; write-up
`docs/labs/LAB5_MOVE.md`.

### Later labs

- **Learn** — when a tuned controller is enough: the Phase 3 ablation (1,080
  episodes, B2 at 98%) and the observer finding.
- **Estimate** — observability, through the friction non-identifiability
  result.
- **Many robots** — multi-agent pathfinding. The ISRO simulator's reservation
  tables and the AMR fleet's trajectory layer are the two starting points.

---

## 6. Phases

| Phase | ≈ weeks | Ships | Done when |
|---|---|---|---|
| **0 · Make the repo tell the truth** | 1 | Consolidated `main`; honest README and PROJECT_STATE; this roadmap installed | Consolidation on `main` with per-package test counts (measured); collision-monitor loop measured, fixed and re-measured with a comparability statement; branches archived as `archive/*` tags; name decided |
| **1 · Plan** | 3 | Public URL, demo video, `docs/labs/LAB1_PLAN.md` | Property tests green on ≥1,000 random maps with exact oracle agreement; three real runs replayable; SmacPlanner2D conformance reported; the A\* exhibit live; works on a phone |
| **2 · Live** | 2 | The live robot on the site: teleop, Nav2 and autonomous modes; scheduled public sessions | All three modes working from the Lab page against the local stack, with command-to-wheel latency (measured); driver and spectator control tested; a remote session driven from a phone on mobile data; the tunnel verified to expose only the coco.v1 endpoint |
| **3 · Localise** | 2–3 | Lab 2; Sketch mode | Sketch fidelity vs Gazebo measured and shown; MCL vs EKF on identical inputs; kidnap-recovery A/B with non-zero `recovery_alpha` (measured) |
| **4 · Map** | 3–4 | Lab 3 | slam_toolbox, Cartographer and three `coco_lab` SLAMs on identical recorded drives; trajectory error and map score published |
| **5 · Search** | 3 | Lab 4 (P0.4); the autonomous mode discovers | The master context's P0.4 matrix (≥16 runs, including negative-first-region) passing and replayable; the live autonomous mode switched to discovery and its label updated |
| **6 · Move** | 2–3 | Lab 5; dynamic obstacles | DWB, MPPI and RPP on identical paths with rollouts shown; moving actors on the apron; D\* Lite replanning |

Phase numbers and lab numbers diverge from Phase 3 on, because Live is a
phase but not a lab.

**Rule 9 against this table (owner's reading, 2026-09-30).** Rule 9 of
the CLAUDE.md addendum, which is §7 scope rule 1 here (not §4 invariant 9,
the live-control rule), says no new *lab* starts until the previous one has
a public URL, a video and a write-up. Live is a phase, not a lab, so
**Phase 2 is not blocked**. **Lab 2 (Phase 3) is blocked** until Lab 1 has
its demo video and its write-up (`docs/labs/LAB1_PLAN.md`); on 2026-09-30
Lab 1 had only its public URL. **Satisfied 2026-10-01:** Lab 1 has its
public URL, its video (release `lab1-v1.0`) and its write-up, so rule 9 no
longer blocks Lab 2.

**Minimum signature release: Phases 0 and 1, about four weeks.** It stands on
its own: a public URL, a video, a write-up and a measured, tested lab.
Everything after it adds to a working product rather than building toward
one.

**Phase 2 adds the live robot, about six weeks in total.** It comes after
Lab 1 rather than before, because it reuses Lab 1's web app, deploy pipeline
and map renderer.

Prompts for Phase 0 and Phase 1 (split into sessions 1A–1F) are in
`docs/LAB_PHASES.md`. Prompts for later phases get written from this document
when their turn comes, not before.

---

## 7. Scope rules

Three rules, because this project's history shows what happens without them:

1. **No new lab starts** until the previous one has a public URL, a video and a
   write-up.
2. **A lab's first version ships at most five algorithms.**
3. **The protected list stands:** `cmd_vel_arbiter.py`, `target_finder.py`,
   `protocol.py` (extended additively only), `mujoco_env.py` and the policy
   weights, and the Isaac backend. The collision-monitor loop (known
   limitation 0) is the one pre-approved exception, because it is a measured
   defect.

---

## 8. Correctness plan

The education-specific failure mode is **teaching something wrong**. A
visualiser with a closed-set bug installs a misconception in everyone who
uses it. Correctness therefore gets the same status as the anti-cheat
invariants.

**Theorems as property tests** — seeded random maps, at least 1,000 per
property, using hypothesis:

| Property | Condition |
|---|---|
| A\* cost = Dijkstra cost | Admissible heuristic |
| A\*'s expanded set ⊆ Dijkstra's, up to ties | Consistent heuristic |
| Weighted-A\* cost ≤ w × optimal | w ≥ 1, admissible heuristic |
| w = 0 reproduces Dijkstra | — |
| BFS is optimal | Unit edge costs |
| Greedy best-first cost ≥ optimal, and strictly worse on a committed counterexample | — |
| All algorithms agree on "no path" | — |

**Oracles.** networkx shortest-path costs (a test-only dependency). From
Phase 3, PythonRobotics (MIT) as a cross-check for filters and SLAM.

**Conformance.** `coco_lab` A\* vs SmacPlanner2D on identical costmap
snapshots; SLAM variants vs slam_toolbox and Cartographer on identical
drives; Sketch vs Gazebo at identical poses. Gaps are reported, never tuned
away.

**Cross-language.** The TypeScript UI never re-implements an algorithm.
Bundle decoding is pinned by golden files written by the Python encoder —
the pattern `coco_web` already uses for its binary frames.

**Evidence on screen.** Every exhibit cites its evidence: a test name or a
`RESULTS.md` anchor.

---

## 9. Deferred, and what would bring each back

| Deferred | Revisit when |
|---|---|
| Full Isaac backend; cross-simulator scene equivalence | More VRAM or cloud credits, **and** a lab that needs what Isaac adds (e.g., photoreal perception) |
| Always-on hosted live robot; concurrent drivers | Scheduled sessions show sustained demand, and a host that can render Gazebo's camera and LiDAR is funded (a GPU instance, or accepting slow software rendering) |
| Global leaderboard | Share links are in real use; it needs a small backend |
| VLM task layer (M7_DESIGN §2.7) | A lab teaches it |
| M7 Phase 4 policy training | A lab needs a trained policy as teaching material |

Branches for deferred work are archived as `archive/*` tags in Phase 0, not
deleted.

---

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| Teaching something wrong | §8 |
| Pyodide too slow for interactive editing | A Web Worker; budgets measured in 1D; a coarser edit resolution; a TypeScript hot loop only as a last resort, decided with numbers |
| Core and UI drifting apart | Invariant 8; golden-file decoding |
| Sketch mistaken for the real robot | Always labelled; fidelity measured and shown |
| A large conformance gap vs SmacPlanner2D | A finding, not a failure: smoothing and cost models differ. Report and explain |
| Recordings too large for the static site | Measure bundle sizes (1B); downsample; host large recordings as release assets |
| Remote live sessions: security, abuse, bandwidth | The closed coco.v1 vocabulary (the reason rosbridge was removed); a control code; rate limits and a session time cap; a tunnel, so no open router ports; a containerised stack; telemetry-driven rendering for spectators instead of video; a kill switch on the host |
| Scope creep | §7 |

---

## 11. Measures of success

- The public URL loads and replays on a phone (Phase 1).
- The live robot: command-to-wheel latency measured locally and through the
  tunnel, and one remote session driven end to end in each of the three
  modes (Phase 2).
- Property tests reported with their count, maps per property and exact
  oracle agreement, marked (measured) in `RESULTS.md`.
- Conformance, fidelity and performance numbers published with reproduction
  commands, whatever they turn out to be.
- **Optional learning check** (after Phase 1): Lab 1 put in front of about ten
  classmates with a short before-and-after quiz, no personal data collected,
  reported with small-sample caveats. A measured learning result is rare for
  a student project.

---

## 12. History

- Previous roadmap (COCO 2.0 tracks, M0–M7): `docs/history/ROADMAP_COCO2.md`
- COCO 2.0 master context — still authoritative, except for §45's priority
  order
- `PROJECT_STATE.md`, `docs/RESULTS.md`, `docs/DESIGN_DECISIONS.md`
