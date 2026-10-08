# COCO Lab v2 — Master Plan: the Glass-box Arena

> **Authority file for all COCO Lab work from 8 October 2026.**
> Every coding agent reads this file and `docs/STATUS.md` before touching anything.
> Repository: [`GauthamCodes/coco-labs`](https://github.com/GauthamCodes/coco-labs) · Public site: <https://gauthamcodes.github.io/coco-labs/>

---

## 0. How to use this file

**Authority order.** A lower item may never contradict a higher one.

1. **The repository** (code plus committed evidence) is the truth about what COCO Lab *is* today.
2. **This README** is the truth about what COCO Lab *becomes*, in which order, and under which rules.
3. **`docs/STATUS.md`** records where the work stands: current SHA, milestone, checkpoint, open questions, and the plan-change log.
4. **A milestone prompt** carries the instructions for one milestone. It quotes this file; it never extends it.
5. **Agent reports** are claims to verify, never facts. A claim becomes fact only when its evidence is committed and re-checkable.

**Change control.**

- The plan changes only at a milestone boundary, by Gautham, as a dated entry in the plan-change log in `docs/STATUS.md`.
- New ideas go to `docs/IDEAS.md` as one line each, in the form `date | idea | gap it closes | earliest milestone`. They are never implemented mid-milestone.

**COCO Lab is a separate project from the COCO robot project** (the Isaac / P03D line in the robot repo). Never modify the robot repo, its worktrees (for example `~/coco-isaac-21`) or its evidence from COCO Lab work.

---

## 1. What COCO Lab is becoming

**COCO Lab becomes one browser app: a glass-box robot arena.** You drive or dispatch COCO through its world and see everything it computes, live:

- search frontiers and expansion heatmaps
- particles and their weights
- the evolving map
- candidate trajectories and their scores
- beliefs over search regions

You can pause, step, inspect any decision, and replay. Then you compare with what the full ROS 2 stack did in Gazebo, failures included.

- **Tagline:** *See what the robot computes.*
- **The design question every feature answers:** what is the robot computing right now, and how can the user see and understand it?
- **The core moment:** the ISRO Pygame simulator, grown up. The user clicks a goal, watches the planner's search spread as the robot drives, and at the end sees a heatmap of every node the algorithm computed.

### Pillars

| Pillar | Promise | Test a feature must pass |
| --- | --- | --- |
| Glass box | Internal computation is the main view | Does it make some computation visible or understandable? |
| Honest | Model, Stack and hardware results are labelled, never conflated; failures stay on display | Is every on-screen claim traceable to evidence, with its class? |
| Playable | Zero install, instant response | Does it work in a phone browser at first click? |
| Reproducible | Every run is a spec plus a seed anyone can rerun | Can someone reproduce what they see from a link? |

### Who it is for, in priority order

1. Robotics learners (the design target).
2. Instructors.
3. Researchers and practitioners.

### Four modes in one app

| Mode | What it is |
| --- | --- |
| **Learn** | Guided missions organized around the robot's questions |
| **Play** | Challenges scored only with real robotics metrics |
| **Sandbox** | Free play, comparisons, and "Run N seeds" experiments |
| **Case Files** | Recorded full-stack runs and failures, inspectable |

### What COCO Lab is not

- a physics-accurate simulator
- a cloud ROS IDE
- a course website
- a VLM, LLM or RL showcase

---

## 2. Where COCO Lab stands: v1, frozen at tag `coco-lab-v1-final`

**Releases.** Six releases shipped between 29 Sep and 8 Oct 2026:

| Release | Lab |
| --- | --- |
| `lab1-v1.0` | Plan |
| `live-v1.0` | Live |
| `lab2-v1.0` | Localise |
| `lab3-v1.0` | Map |
| `lab4-v1.0` | Search |
| `lab5-v1.0` | Move |

Last known SHAs: `main` = `2b6f8ad`, `lab5` = `3571169`. Verify both before relying on them.

**Architecture today.**

- `lab_web` (Vite, TypeScript, React) on GitHub Pages renders recordings and re-runs `coco_lab` through Pyodide.
- `coco_lab` is a pure-Python algorithm library with no `rclpy`.
- `coco_lab_ros` bridges `coco_lab` to Nav2.
- `platform_server` (in `coco_web`) is the only web-to-ROS bridge, speaking `coco.v1`.
- `cmd_vel_arbiter` is the only wheel publisher.
- The Gazebo Harmonic + ROS 2 Jazzy stack runs locally. Live reaches it through Tailscale Funnel.

**Tests at the last gate.** 3,081 package tests, 308 website tests and 117 build-tool tests, all passing. CI was green.

### Evidence worth keeping forever

Each item is labelled with its evidence class (defined in section 3).

| Result | Class | Caveat |
| --- | --- | --- |
| Smac and `coco_lab` find the same optimal cost on 36/36 pairs | STACK + MODEL | — |
| Sketch LiDAR against Gazebo: 86.7% of beams within 5 cm | MODEL vs STACK | Turns diverge (no wheel slip) |
| Kidnapping, model: 18/20 with injection vs 0/20 without | MODEL | — |
| Kidnapping, Stack: 2/10 vs 0/10 (Fisher p = 0.237) | UNRESOLVED | — |
| Loop closure damaged maps on both real SLAM backends | STACK | Cause unattributed |
| Search: 14/16 complete, 39/39 looks correct | STACK | All 16 replay byte for byte through `coco_lab` |
| Lab 5: 54 runs, 0 void | STACK | DWB 0/5 at the hairpin; nobody swerved head-on |
| Run 15 mechanism reproduced 9/9 | STACK | Exact "0 of 819" not reproduced |
| D\* Lite less work than A\* in 191/200 teaching worlds | MODEL | 2.9× *more* work on one real costmap |
| Latched STOP; drive command p50 4.6 ms; STOP 6.2 ms | STACK | Local network |
| Phone on mobile data drove the robot; RTT about 282–293 ms; disconnect stop about 0.54 s | REMOTE | Robot simulated |

### Corrections every agent must respect

1. **No physical robot exists.** Nothing has run on hardware. "Real" in COCO Lab means the full ROS 2 stack in Gazebo, as opposed to the browser model.
2. **The gripper has two fingers and a magnet, and the magnet does the holding** (it fires before the fingers close). Describe it that way, never as fingers alone and never as a magnet alone.
3. **Live drives the simulated stack** on Gautham's machine. Its name and copy must not imply hardware.
4. **Lab 5, head-on scenario.** The actor walked into an already-stopped robot in all 15 runs. DWB's and MPPI's "reached" exists only because the actor has no collision body.

### Unresolved, and kept labelled as unresolved

- DWB's hairpin stall
- why no controller swerved
- D\* Lite's extra work on the real costmap
- loop-closure damage
- exact Run 15
- recovery from confident AMCL divergence
- the collision-monitor residual
- untested remote behaviours: phone STOP, second spectator, mid-mission preemption, remote mission completion, idle and session caps, the cause of the disconnect, and the stale Nav2 "executing" label

---

## 3. Non-negotiable rules

### Invariants kept from v1

1. `coco_lab` never imports `rclpy`.
2. Browser code never names a ROS topic. It speaks `coco.v1`, which only grows additively unless a major version is declared.
3. `cmd_vel_arbiter` is the sole wheel publisher, in every tier, forever.
4. Ground truth has one authoritative source: the `truth` channel. Nothing fabricates truth elsewhere.
5. Data formats are versioned. A breaking change means a major version plus a converter.
6. Comparisons hold every non-compared variable fixed.
7. Remote control is exclusive and interruptible, and STOP always wins.
8. Gazebo `--fast` stays banned. It produced 531/533 tip-overs.

### The one invariant replaced, and why

**Old:** "No algorithm in TypeScript."

**New:** *Any second implementation of an algorithm (WebAssembly, TypeScript) must be trace-equivalent to the Python reference on the property-test corpus, checked in CI.*

The intent stays the same: no silent divergence. It becomes testable, and it allows performance kernels if measurement ever demands them.

### Evidence classes, used in code, docs and UI

| Class | Meaning |
| --- | --- |
| MODEL | `coco_lab`, the Arena model, the browser |
| STACK | Full ROS 2 stack in Gazebo, recorded |
| REMOTE | Over the public internet, robot simulated |
| HARDWARE | A physical robot. **None exist.** |
| UNRESOLVED | Reproduced but unexplained, statistically unresolved, or untested |
| CONCEPT | Discussed, not built |

The labels shown to learners map onto these: MEASURED, ASSUMPTION, SIMPLIFIED MODEL, SIMULATION RESULT, REAL ROBOT RESULT, INFERENCE.

### Integrity rules

1. **Every learner-facing claim cites committed evidence.** Mission and Case File content without evidence references fails CI (from M2 onward).
2. **Negative results stay visible.** Nothing is removed to make a lesson look cleaner.
3. **Never delete evidence:**
    - recordings in `~/coco_lab_runs/`
    - the contents of `docs/RESULTS.md`, which is append-only
    - release tags
    - GitHub releases
4. **No game mechanic changes robot behaviour or rewards luck.** Scores use real metrics or decision quality in expectation.
5. **Git safety.**
    - No `git clean`, `git reset --hard`, force-push, branch deletion or tag deletion without Gautham's explicit approval.
    - Work happens on `v2/...` branches, merged to `main` only with green CI and Gautham's approval.
6. **The machine is shared with the robot project.** That project's overnight batch runs need an idle machine, so no heavy COCO Lab jobs (Gazebo, long builds, benchmarks) run during an announced robot batch window.

---

## 4. Component verdicts

| Component | Verdict | What happens |
| --- | --- | --- |
| `coco_lab` Python library | Keep, redesign | Stays the reference implementation; emits unified events through a generator API (M1) |
| Pyodide in a Web Worker | Keep, redesign | Streams events incrementally; a kernel moves to WASM only if it misses a measured budget (M1 gate) |
| Per-lab bundle and trace formats | Replace | Common envelope plus typed event families in MCAP; converters keep every old recording playable (M1–M2) |
| Canvas 2D rendering | Replace | Three.js WebGL 2 renderer (M1) |
| React + Vite + TypeScript shell | Keep | Panels and navigation; the renderer lives beside React |
| Six separate lab views | Merge | One Arena app; old views stay live until their content is migrated (end of M2) |
| Sketch 2D model | Keep, redesign | Becomes the deterministic Arena model, generated from the World Spec (M1) |
| GitHub Pages hosting | Keep | Browser tier |
| `coco.v1` | Keep, extend | Additive event channel and session handshake (M5) |
| `platform_server` | Keep, redesign | Gateway inside each cloud Stack container (M4–M5) |
| Live through Tailscale Funnel | Replace (public) | Renamed "Live Stack (simulated)" now; Gautham's private bench; replaced publicly by cloud sessions (M5) |
| Docker image | Keep, redesign | Basis of the cloud worker (M4) |
| Arbiter, latched STOP, caps, kill switch | Keep | Unchanged in every tier |
| `coco_lab_ros` | Keep, extend | ROS-to-event adapter (M3) |
| Predict-then-reveal, paint-and-recompute, map challenge | Keep | Move into Learn, Sandbox and Play |
| Races and comparisons | Merge | Sandbox split-compare |
| Real-run replays, A\* myth exhibit, Run 15, Nav2 overlay | Merge | Case Files (M3) |
| Share links | Keep, redesign | Spec-hash plus input-log links |
| Robot-stack ROS packages inside `coco-labs` | Freeze | Not deleted (Live and the recordings depend on them); no new features; G3 decides long-term |
| Old roadmap "Learn" (RL), "Many Robots", global leaderboard | Defer | See section 6 |
| Old roadmap "Estimate" | Merge | Into the Localise lens |
| Isaac integration inside COCO Lab, VLM layer, browser policy training | Remove | Out of scope permanently |

---

## 5. Target architecture

### 5.1 Two simulation tiers, one world spec

**Tier 1: the Arena model.** A deterministic 2D / 2.5D simulator running beside the algorithms inside a Web Worker (Pyodide + `coco_lab`). It is the main experience, and it costs nothing per user. Deterministic by construction:

- fixed time step
- single-threaded loop
- seeded in-library RNG
- per-tick state hash

**Tier 2: the Stack.** The existing ROS 2 + Gazebo Harmonic system in cloud containers. Batch runs first (M4); interactive sessions only if gated in (M5). It is not bitwise deterministic, so its recordings are its replays.

**World Spec.** One versioned YAML describing geometry, bays, ramp zone, obstacles, actors and the robot (from `coco_config`). Generators produce both the Arena world and the Gazebo SDF.

**Fidelity report.** Each release ships one (LiDAR agreement, odometry in turns, controller tracking), shown in the UI as "model gap" chips.

### 5.2 One trace system

A **family of typed schemas under one envelope**: neither one flat universal event list nor separate per-lab formats.

- **Envelope (manifest):**
    - `run_id` = hash of canonical spec + seed + engine versions
    - the spec, tier, evidence class, library and engine SHAs, schema list, provenance
- **Channels.** Named `coco.<family>.<name>.v<major>`, defined in a new `coco_schemas` package (protobuf) that generates Python and TypeScript:
    - world, robot, truth, `sensor.scan`, estimate
    - `plan.search`, `plan.incremental`
    - `localise.particles`, `localise.ekf`
    - `map.grid`, `map.slam`
    - `control.local`, `decide.search`, `mission.fsm`
    - metrics, annotation, input
- **Visual primitives.** The renderer's whole vocabulary: instanced points, poses, line sets, polygons, scalar grids, graphs, region distributions, sparse labels. Each primitive carries a pick ID back to its semantic event.
- **Lenses.** One per family: event → primitives, inspector templates, default level of detail, captions, aggregates (for example, the end-of-run heatmap). A lens lays out and aggregates; it never computes the algorithm.
- **Three clocks on every event:**
    - `t_world` (simulation seconds)
    - `tick` (control cycle)
    - `seq` (computation step)

    The timeline has a world track and a computation track.
- **Storage.** MCAP container, protobuf messages, zstd-compressed indexed chunks, keyframes every few seconds for seeking. Arena-model replays can be spec + seed + input log, re-simulated.
- **Level of detail.** Producers emit full or summary detail; clients subscribe per channel.
- **Golden traces.** The existing property corpus produces golden traces, diffed in CI.

### 5.3 Rendering

- **Three.js on WebGL 2.** Orthographic 2.5D by default, perspective on demand.
- **Techniques:**
    - instancing for points
    - merged line buffers for fans and rays
    - data textures for grids and heatmaps
    - glTF robot meshes converted from Gazebo's
    - ID picking for the inspector
- **Threads.** The simulation and algorithms run in a worker and post transferable buffers; the renderer owns the main thread; React draws only panels.
- **A visual design system with fixed colour semantics per layer:** frontier, visited, chosen path, rejected candidates, truth (always an outline), uncertainty (always translucent).
- **Rejected:** Canvas 2D (ceiling), pixel streaming (can't be inspected), WebGPU directly (later, through Three.js's WebGPU path, only if budgets fail).

### 5.4 Cloud (from M4 only)

Three things, in order of cost:

1. **CDN:** the app, the replay library, Case Files.
2. **Batch Stack runs:** API, queue, one fresh container per job, MCAP to object storage.
3. **Interactive Stack sessions:** gated (M5).

Rules for the cloud:

- No Kubernetes or microservices until there are several worker hosts.
- Each container gets its own network and localhost-range ROS 2 discovery.
- No user code ever runs server-side.
- Sign-in is required for Stack compute.
- A global daily spend cap.

### 5.5 Latency rules

- Every pedagogical interaction (scrub, inspect, layers, paint, predict, compare) runs in the browser.
- Stack sessions use client-side prediction, interpolation, latest-state-wins delivery, and "pause the view, not the robot".
- Safety stays server-side: STOP latches in the arbiter path, and a disconnect stops the robot.
- Attract mode plays a recorded replay while Pyodide loads, hiding the cold start.

### 5.6 Experiments

- **One spec format** (`spec_version`, world, scenario, robot, sensors, tier, arms, seeds, trials, metrics with one primary, budget), run identically in the browser, the cloud, or locally with `coco run spec.yaml`.
- **Results:**
    - k/n with Wilson 95% intervals
    - median and IQR with bootstrap intervals
    - McNemar or Wilcoxon for paired comparisons
- **Exports:** YAML, CSV, Parquet, MCAP.

### 5.7 Hardware contract (gated, not built)

A future physical robot is a third backend behind the same gateway and event families, with the HARDWARE class, a hardware e-stop, firmware limits, a supervisor and a reservation system. Any participant can press STOP; only the driver drives.

---

## 6. Scope fence

**The drift test.** Before any task, the agent names three things:

- the milestone
- the checkpoint
- the exit criterion the task advances

If it cannot name all three, the task is out of scope.

**Non-goals until further notice** (rejected without discussion):

- Vision-language models, LLM planners, natural-language robot commands
- Multi-robot behaviour
- RL lessons or policy training, until the robot project shows where learning beats classical control
- A third simulator (MuJoCo, Webots, Isaac) inside COCO Lab
- A physical-robot mode before a robot exists
- A global leaderboard before deterministic server-side score verification exists
- Kubernetes, multi-region, microservices
- XP, levels, streaks, loot, or any score that rewards luck
- Package renames or restructures done for aesthetics
- Changes to the COCO robot repo or its worktrees

---

## 7. Roadmap

```
M0 Transition ─▶ M1 Glass-box Arena core ─▶ M2 Whole loop ─▶ M3 Play + Case Files (public v2 launch)
     ─▶ M4 Stack in the cloud: batch + experiments
     ─▶ [gate: cost per slot-hour fits budget AND demand shown] ─▶ M5 Interactive Stack sessions
     ─▶ [gate: a physical robot exists] ─▶ M6 Hardware bridge
```

M0–M3 together form a complete product with no cloud. Effort ranges are rough estimates for part-time, agent-assisted work.

### M0 · Transition: freeze v1, set up v2 (about 1 week)

**Objective:** freeze and measure v1, install this plan as the authority, remove what is marked Remove, fix public honesty issues. **No new features.**

1. **M0.1 Verify.**
    - Locate the repo.
    - Record `main` and `lab5` SHAs, worktree cleanliness, and full test counts (package, web, build tools) on a clean build.
    - If `lab5` is strictly ahead of `main` with documentation-only changes, fast-forward `main`. Otherwise stop and report.
2. **M0.2 Freeze v1.**
    - Tag the last v1 commit `coco-lab-v1-final`.
    - Confirm all six releases and their assets exist.
    - Confirm that recordings cited by checksum in `docs/RESULTS.md` resolve in `~/coco_lab_runs/`. Report any that do not.
3. **M0.3 Baseline measurements, before anything changes.** Write everything to `docs/v2/BASELINE.md` and `docs/RESULTS.md` with evidence labels:
    - Pyodide cold start and warm map edit on the laptop, automated (Playwright or similar)
    - an instruction page plus script so Gautham can repeat the measurement on his phone
    - production bundle sizes
    - frame rate of each current view during playback
    - an inventory of every bundle and trace format, and of duplicated visualization code in `lab_web`
4. **M0.4 Install the plan.**
    - Copy this README to the repo root, after archiving the old one to `docs/archive/v1/README_v1.md`.
    - Create `docs/STATUS.md` and `docs/IDEAS.md`.
    - Archive the old `docs/ROADMAP.md` to `docs/archive/v1/`, and replace it with a short pointer to this section plus the v1 history table.
    - Update `PROJECT_STATE.md`.
    - Update `CLAUDE.md`: keep every engineering rule that still holds; add "README.md is the authority" and the drift test.
5. **M0.5 Remove.**
    - Delete code, config, docs or roadmap entries for Isaac-in-Lab, the VLM layer and browser policy training. List every file in the commit message.
    - Rewrite the old roadmap themes: "Learn" → deferred, "Estimate" → merged into Localise, "Many Robots" → deferred.
    - If none of these exist as code, record that.
6. **M0.6 Honesty fixes** (copy only, no behaviour change):
    - Wherever the site or docs say "real robot" for the Gazebo stack, say "the full ROS 2 stack (simulated)".
    - Gripper → "two fingers and a magnet; the magnet holds the object".
    - Rename Live to "Live Stack (simulated)", and label it a scheduled demo of the simulated stack.
7. **M0.7 Freeze the robot-stack packages** inside `coco-labs` with a `FROZEN.md` note: kept, no new features, decision G3 pending. Nothing is deleted.
8. **M0.8 Deprecation notes.** Mark the Replace items (Canvas renderer, per-lab formats, per-lab views) as deprecated in docs, with the milestone that replaces them. Nothing is deleted yet; every current view keeps working.

**Exit criteria:**

- CI is green.
- Test counts are equal to or higher than M0.1's.
- Every current public view still loads with no console errors.
- The baseline file is committed.
- The README is in place; `STATUS.md`, `ROADMAP.md`, `PROJECT_STATE.md` and `CLAUDE.md` are consistent with it.
- The report is written.
- Gautham approves the merge to `main`.

### M1 · Glass-box Arena core (about 4–6 weeks)

**Objective:** a stranger opens one URL on a phone, clicks a goal, watches the planner compute visibly as the robot drives, and sees the end-of-run heatmap. All of it is deterministic, measured, and on the new engine.

1. **M1.1 `coco_schemas`.**
    - The envelope plus the world, robot, truth, `sensor.scan`, `plan.search`, `plan.incremental`, input, metrics and annotation families.
    - Protobuf with generated Python and TypeScript; CI schema checks.
2. **M1.2 World Spec v1.** The COCO arena and robot parameters, plus a generator for the Arena model. Gazebo SDF generation is designed for, not built.
3. **M1.3 Arena model core in `coco_lab`.**
    - Fixed-step differential-drive kinematics and 2D LiDAR (reuse Sketch; re-confirm the 86.7% fidelity number).
    - Seeded RNG; per-tick state hash; goals and teleop arrive as input events.
4. **M1.4 Planners emit events.** BFS, Dijkstra, A\*, greedy and weighted A\* (D\* Lite optional) through a generator API. Golden traces must match Lab 1's (expansion order and costs) on the 1,000-map corpus.
5. **M1.5 Worker runtime.** Pyodide in a Web Worker streaming transferable event batches; preload during attract mode.
6. **M1.6 Renderer.**
    - Three.js orthographic arena.
    - Layers: occupancy, frontier, closed set, heatmap, path, LiDAR, robot, footprint, truth outline.
    - Picking opens the inspector (g, h, f, parent, expansion order).
    - Visual design system v1.
7. **M1.7 Timeline.** World and computation tracks; play, pause, step, speed, scrub; keyframe seeking.
8. **M1.8 Experience.**
    - attract-mode landing, give-a-goal
    - keyboard and touch-joystick teleop
    - planner choice, side-by-side compare
    - end-of-run heatmap
    - share link (spec hash + input log)
    - the MODEL badge
9. **M1.9 Converters.** Lab 1 bundles and its three real-run replays play in the new viewer. The old Lab 1 view stays live.
10. **M1.10 Measure and decide.** Measure every budget below; record the WebAssembly gate decision. Nothing is ported unless a budget fails.

**Acceptance criteria:**

| Area | Criterion |
| --- | --- |
| Determinism | Identical per-tick hashes in Chrome, Firefox, Safari and Pyodide-in-Node across 100 recorded sessions |
| Correctness | New traces match Lab 1's on all 1,000 corpus maps |
| Laptop performance | 60 fps with about 50,000 points, 20,000 segments and one grid texture |
| Phone performance | 30 fps or better at default detail on Gautham's phone |
| Responsiveness | First frontier node within 100 ms of a goal click (warm); seek under 100 ms |
| Cold start | First visible computation within 10 s of opening the URL on the phone over mobile data |
| Usability | 5 people new to robotics set a goal and explain the heatmap within 2 minutes, unaided |
| Release hygiene | No console errors; phone-width check; schema, golden-trace, determinism and screenshot tests in CI |

**Not in M1:**

- other lenses and local controllers
- the cloud, accounts, a Stack adapter
- leaderboards, the 3D arm
- WebGPU
- WASM ports without a failed budget
- new algorithms

**Stop and escalate if:**

- The phone cannot reach 15 fps at minimum detail.
- Cross-browser hashes differ.
- The schemas cannot express an existing Lab 1 trace without loss.

### M2 · The whole loop (about 5–7 weeks)

**In the arena together:** localization (MCL, EKF, injection), mapping and SLAM (occupancy, EKF-SLAM, FastSLAM, pose graph), local control and search decisions.

**New teaching implementations,** labelled MODEL and compared with Lab 5's Stack runs:

- a DWA-style sampler
- a pure-pursuit tracker
- a small MPPI

**Also in M2:**

- an Arena fetch mission (abstract colour detection, kinematic 2-DOF arm inset)
- the Run 15 mechanism reproduced in the model
- fidelity report v1
- Learn missions 1–6, written as data files with evidence references

**Exit criteria:**

- Every learner-facing claim from Labs 1–5 reappears with its evidence.
- Every old bundle converts and replays.
- The 16 search runs replay byte for byte through the new pipeline.
- The old per-lab views are retired; their release tags remain.

### M3 · Play and Case Files: public v2 launch (about 4–5 weeks)

**Case Files.** Every existing recording, converted through a ROS-to-event adapter in `coco_lab_ros`, with a model-vs-Stack comparison view:

- 16 search runs
- 54 Move runs
- SLAM tours
- Run 15
- the A\* myth

**Play.** The five cheapest challenges first; challenge-a-friend links from input logs; local bests.

**Verification prototype.** Re-simulation under Pyodide in Node.

**Exit criteria:**

- A cold visitor sees computation within 10 s on a mid-range phone.
- Every Case File claim links to its evidence.
- Shared challenge links reproduce exactly.

### M4 · The Stack in the cloud: batch runs and experiments (about 4–6 weeks)

**Built:**

- pinned headless Stack image
- worker and queue
- small API with sign-in and quotas
- object storage
- pre-run replay library
- "Run N seeds"
- the `coco run` command line
- global spend cap

**Measured:**

- Stack real-time factor in cloud containers
- start-up time
- CPU-only (software rendering) against GPU
- cost per run and per slot-hour

### M5 · Interactive Stack sessions (gated, about 4–6 weeks)

**Gate:**

- M4's cost per slot-hour fits the budget (G4).
- M3 shows demand.

**Built:**

- session manager, warm pool, gateway
- additive `coco.v1` event channel
- client-side prediction
- 3D view with Gazebo meshes

**Measured remotely:** STOP, preemption, spectators, caps, disconnect.

**Then:** retire the public Tailscale Live tab.

### M6 · Hardware bridge (gated)

Gated on:

- a physical robot existing (G5)
- the robot project's sim-to-real gate
- M5's remote-safety measurements

---

## 8. Decisions pending, and the defaults agents use until Gautham decides

| ID | Decision | Default until decided |
| --- | --- | --- |
| G1 | Primary audience | Learners first |
| G2 | Priority against the robot project and job hunt | Not an agent decision; agents respect announced robot batch windows |
| G3 | Canonical robot stack | The robot repo is canonical; `coco-labs` robot packages are frozen, not deleted |
| G4 | Monthly cloud budget | Zero; no cloud resources are created before M4 and an explicit budget |
| G5 | Will a physical robot exist within a year? | Assume no; no "real robot" wording anywhere |
| G6 | License and outside contributions | Unchanged from the current repo |

---

## 9. Rules for coding agents

1. **One prompt per milestone.** Work through every checkpoint without pausing, unless a stop condition fires.
2. **Read first:** `README.md`, `docs/STATUS.md`, `CLAUDE.md`, `PROJECT_STATE.md`.
3. **Apply the drift test** before each task. Anything outside the checkpoint list goes to `docs/IDEAS.md`, never into code.
4. **Branch and commits.**
    - Branch `v2/<milestone>` (for example `v2/m1-arena-core`).
    - Commits are prefixed with the checkpoint, for example `[M1.3]`.
    - `docs/STATUS.md` is updated at every checkpoint.
5. **Testing.** Focused tests during work; the full suites (`run_all_package_tests.sh`, web tests, build-tool tests) at each checkpoint's end.
6. **Resources.** RTX 4050 laptop GPU (6 GB VRAM), 16 GB RAM, Ubuntu 24.04, ROS 2 Jazzy. Never run two simulators at once. Respect robot batch windows.
7. **Never:**
    - delete evidence, tags or releases
    - run destructive git commands without approval
    - touch the robot repo
    - invent numbers
    - mark anything MEASURED without committed data
8. **Final report**, in this form:

```
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (with device and conditions):
Files removed (full list) and why:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```

9. **Independent review.** A milestone closes in `STATUS.md` only after a fresh review session, given only the repo, this README and the report, has verified that:
    - the commits exist
    - a sample of the tests pass
    - every evidence file named in the report exists and supports its claim

---

## 10. Where things live

| File | Role |
| --- | --- |
| `README.md` | This plan: the authority |
| `docs/STATUS.md` | Current position, open questions, plan-change log |
| `docs/IDEAS.md` | Parked ideas |
| `docs/ROADMAP.md` | Pointer to section 7, plus the v1 history |
| `docs/RESULTS.md` | Every measured number, append-only |
| `docs/v2/` | Baselines, architecture, schema docs for v2 |
| `docs/archive/v1/` | Archived v1 README, roadmap and other retired docs |
| `CLAUDE.md` | Engineering rules for agents |
| `PROJECT_STATE.md` | Authoritative current state |
| `~/coco_lab_runs/` | Raw evidence recordings (outside git; never delete) |
