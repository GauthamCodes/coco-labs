# COCO Lab v2 — Master Plan: the 3D Glass-box Arena

> **Authority file for all COCO Lab work. Revision 2, 11 October 2026: 3D becomes the default experience.**
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

**COCO Lab is one browser app: a 3D glass-box robot arena.**

You enter COCO's own arena in 3D, the world the full ROS 2 stack was recorded in, rendered in the browser. You can:

- drive COCO yourself with keyboard, mouse or touch
- hand it over to autonomy
- follow it, orbit it, or ride on its camera

All the while you see everything it computes, live and anchored in the world:

- search frontiers and expansion heatmaps
- LiDAR rays at the sensor's real height
- particles and their weights
- the evolving map
- candidate trajectories and their scores
- beliefs over search regions

You can pause, step, inspect any decision, drop to the top-down analytic view, and replay. Then you compare with what the full ROS 2 stack did in Gazebo, failures included.

- **Tagline:** *See what the robot computes.*
- **The design question every feature answers:** what is the robot computing right now, and how can the user see and understand it?
- **The core moment:** the ISRO Pygame simulator, grown into a 3D game. The user drives or sends COCO to a goal, watches the planner's search spread across the floor as the robot moves, and at the end sees a heatmap of every node the algorithm computed.

### Pillars

| Pillar | Promise | Test a feature must pass |
| --- | --- | --- |
| Glass box | Internal computation is the main view, in 3D and top-down | Does it make some computation visible or understandable? |
| Honest | Model, Stack and hardware results are labelled, never conflated; 3D looks never imply physics the model doesn't have; failures stay on display | Is every on-screen claim traceable to evidence, with its class? |
| Playable | Zero install, instant response, game-like feel | Does it work in a phone browser at first click, and does driving feel immediate? |
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
| **Sandbox** | Free driving and autonomy in the 3D arena, comparisons, and "Run N seeds" experiments |
| **Case Files** | Recorded full-stack runs and failures, inspectable in the same 3D world |

### What COCO Lab is not

- a physics-accurate simulator (physics comes from Gazebo, through Case Files and later cloud runs)
- a cloud ROS IDE
- a course website
- a VLM, LLM or RL showcase

---

## 2. Where COCO Lab stands

### v1, frozen at tag `coco-lab-v1-final`

Six releases shipped between 29 Sep and 8 Oct 2026: `lab1-v1.0` (Plan), `live-v1.0` (Live), `lab2-v1.0` (Localise), `lab3-v1.0` (Map), `lab4-v1.0` (Search) and `lab5-v1.0` (Move).

The v1 site is served frozen at `/v1/` from the orphan branch `v1-site`. Every old v1 URL still resolves.

### v2 progress

| Milestone | State as of this revision |
| --- | --- |
| M0 Transition | Merged (PR #19); independently reviewed |
| M1 Glass-box Arena core | Merged (PR #20); independently reviewed |
| M2 The whole loop | Merged (PR #21); independently reviewed |
| M3 Play and Case Files | Built (PR #22); review, one fix and part of the measurement outstanding; closes before M4 starts |
| Gautham's phone and usability rows, M1–M3 | Not run. Phone baseline due now; usability consolidated into M4 (decision D5) |

**Architecture today.**

- `lab_web` (Vite, TypeScript, React) on GitHub Pages, with a Three.js WebGL 2 renderer and an orthographic 2.5D camera.
- `coco_lab` (pure Python, no `rclpy`) runs in a Pyodide worker as the Arena model and every algorithm.
- `coco_schemas` defines the event families, stored in MCAP.
- `coco_lab_ros` converts ROS recordings into Case Files.
- `platform_server` (in `coco_web`) is the only web-to-ROS bridge, speaking `coco.v1`.
- `cmd_vel_arbiter` is the only wheel publisher.
- The Gazebo Harmonic + ROS 2 Jazzy stack runs locally. Live reaches it through Tailscale Funnel.

`docs/STATUS.md` holds the current SHAs and test counts.

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
5. **The Arena model is kinematic.** In 3D it can climb a ramp visibly, but it never simulates tipping, slip, friction or contact forces. Those lessons come from Gazebo.

### Unresolved, and kept labelled as unresolved

- DWB's hairpin stall
- why no controller swerved
- D\* Lite's extra work on the real costmap
- loop-closure damage
- exact Run 15
- recovery from confident AMCL divergence
- the collision-monitor residual
- the Arena pose graph's poor score on a long tour (F1 0.316 against 0.580), reported in M3 and not investigated
- untested remote behaviours: phone STOP, second spectator, mid-mission preemption, remote mission completion, idle and session caps, the cause of the disconnect, and the stale Nav2 "executing" label

---

## 3. Non-negotiable rules

### Invariants

1. `coco_lab` never imports `rclpy`.
2. Browser code never names a ROS topic. It speaks `coco.v1`, which only grows additively unless a major version is declared.
3. `cmd_vel_arbiter` is the sole wheel publisher, in every tier, forever. In the browser, the same priority rule holds: manual input overrides autonomy, and STOP overrides everything.
4. Ground truth has one authoritative source: the `truth` channel. Nothing fabricates truth elsewhere. Height, roll and pitch are never invented for a Stack recording that didn't record them.
5. Data formats are versioned. A breaking change means a major version plus a converter.
6. Comparisons hold every non-compared variable fixed.
7. Remote control is exclusive and interruptible, and STOP always wins.
8. Gazebo `--fast` stays banned. It produced 531/533 tip-overs.
9. **Any second implementation of an algorithm** (WebAssembly, TypeScript) must be trace-equivalent to the Python reference on the property-test corpus, checked in CI.
10. **No physics engine in the browser.** The Arena model is planar kinematics plus kinematic terrain following. Adding rigid-body physics requires a new decision by Gautham.
11. **Rendering never changes the model.** Cameras, lighting, interpolation and visual effects are outside the per-tick state hash. Flat-scene hashes stay byte-identical across renderer changes.

### Evidence classes, used in code, docs and UI

| Class | Meaning |
| --- | --- |
| MODEL | `coco_lab`, the Arena model, the browser |
| STACK | Full ROS 2 stack in Gazebo, recorded |
| REMOTE | Over the public internet, robot simulated |
| HARDWARE | A physical robot. **None exist.** |
| UNRESOLVED | Reproduced but unexplained, statistically unresolved, or untested |
| CONCEPT | Discussed, not built |

The labels shown to learners map onto these: MEASURED, TESTED (a property or unit test proves it), ASSUMPTION, SIMPLIFIED MODEL, SIMULATION RESULT, REAL ROBOT RESULT, INFERENCE, UNRESOLVED.

Whenever the Arena model drives the robot, a **"MODEL · kinematic"** badge is on screen.

### Integrity rules

1. **Every learner-facing claim cites committed evidence.** Mission and Case File content without evidence references fails CI.
2. **Negative results stay visible.** Nothing is removed to make a lesson look cleaner.
3. **Never delete evidence:**
    - recordings in `~/coco_lab_runs/`
    - the contents of `docs/RESULTS.md`, which is append-only
    - release tags
    - GitHub releases
4. **No game mechanic changes robot behaviour or rewards luck.** Scores use real metrics or decision quality in expectation. Controls map to what COCO can physically do: it turns in place but never strafes, and never exceeds its real speed or acceleration limits.
5. **Git safety.**
    - No `git clean`, `git reset --hard`, force-push, branch deletion or tag deletion without Gautham's explicit approval.
    - Work happens on `v2/...` branches, merged to `main` only with green CI and Gautham's approval.
6. **The machine is shared with the robot project.** That project's overnight batch runs need an idle machine, so no heavy COCO Lab jobs (Gazebo, long builds, benchmarks) run during an announced robot batch window.
7. **Browser storage is per-viewer convenience only:**
    - `localStorage` only, through one preferences module, every access inside `try`
    - the page works without it
    - no cookies, `sessionStorage`, IndexedDB or analytics
8. **Every asset has a recorded licence.** Third-party textures, environment maps and props must be CC0 or equivalent, listed in the asset manifest with source and checksum.

---

## 4. Component verdicts

| Component | Verdict | What happens |
| --- | --- | --- |
| `coco_lab` Python library and Arena model | Keep, extend | Gains kinematic terrain following, teleop preemption, the gated grasp action (M4) |
| Pyodide in a Web Worker | Keep | A kernel moves to WebAssembly only if it misses a measured budget |
| `coco_schemas`, MCAP, keyframes | Keep, extend | Additive: optional z, roll and pitch; wheel speeds; command source (M4) |
| Three.js WebGL 2 renderer | Keep, adapt | Becomes a 3D renderer: perspective camera rig, lighting, overlay pass, cutaways, quality tiers (M4) |
| Orthographic 2.5D view | Keep, repurpose | Becomes the top-down analytic camera *and* the automatic low-end fallback |
| React + Vite + TypeScript shell | Keep, redesign layout | Full-bleed world with HUD and slide-in panels |
| Robot sprite | Replace | Articulated glTF robot converted from the URDF meshes |
| World Spec | Keep, extend | Gains elevation data; checked against COCO's Gazebo SDF world in CI |
| Asset pipeline (SDF and URDF to glTF) | New | Offline conversion, meshopt and KTX2 compression, levels of detail, licence manifest (M4) |
| Camera and controls module | New | Follow, orbit, robot-eye, top-down; keyboard, mouse, touch, tank mode (M4) |
| GitHub Pages hosting; `/v1/` from `v1-site` | Keep | Browser tier |
| Learn missions, challenges, `coco verify`, Case Files | Keep, extend | Camera presets per mission step; one new challenge; adapter carries 3D pose where recorded |
| `coco.v1` | Keep, extend | Additive event channel and session handshake (M6) |
| `platform_server` | Keep, redesign | Gateway inside each cloud Stack container (M5–M6) |
| Live through Tailscale Funnel | Replace (public) | "Live Stack (simulated)"; Gautham's private bench; replaced publicly by cloud sessions (M6) |
| Docker image | Keep, redesign | Basis of the cloud worker (M5) |
| Arbiter, latched STOP, caps, kill switch | Keep | Unchanged in every tier |
| Robot-stack ROS packages inside `coco-labs` | Freeze | Not deleted; no new features; G3 decides long-term |
| Old roadmap "Learn" (RL), "Many Robots", global leaderboard | Defer | See section 6 |
| Isaac integration inside COCO Lab, VLM layer, browser policy training, browser physics engine, engine switch | Remove | Out of scope |

---

## 5. Target architecture

### 5.1 Two simulation tiers, one world

**Tier 1: the Arena model.** A deterministic simulator running beside the algorithms in a Web Worker (Pyodide + `coco_lab`). It is the main experience and costs nothing per user.

It is deterministic by construction:

- fixed time step
- single-threaded loop
- seeded in-library RNG
- per-tick state hash

What it simulates:

- **Planar differential-drive kinematics** with the real speed and acceleration limits from `coco_config`.
- **2D LiDAR** cast in the plane at the sensor's real mounting height.
- **Kinematic terrain following:** height and pitch read from the World Spec's elevation data, so the robot visibly climbs the ramp onto the platform. No tipping, slip, friction or contact forces.
- **Contact:** the robot stops on contact with a wall or actor, and the contact is recorded as an event. Nothing bounces.
- **The grasp:** a gated kinematic action using the same proximity gate as the Stack.

**Tier 2: the Stack.** The existing ROS 2 + Gazebo Harmonic system. It is the source of everything physical:

- tipping and the PPO ramp policy
- slip and skid-steer yaw response
- friction and contact
- camera perception on rendered images

Today it reaches users as recorded Case Files. From M5 it adds cloud batch runs; from M6, gated interactive sessions. It is not bitwise deterministic, so its recordings are its replays.

**One world.** The 3D world is COCO's actual Gazebo arena, converted offline from its SDF file, so Arena runs and Stack recordings share one scene. The World Spec (YAML) must agree with the converted SDF geometry within a stated tolerance, checked in CI. Lab dressing sits only *outside* the robot's operating area.

**Fidelity report.** Each release ships one, shown in the UI as "model gap" chips. It covers:

- LiDAR agreement against Gazebo
- odometry in turns
- controller tracking
- from M4, terrain following

### 5.2 One trace system

A **family of typed schemas under one envelope**: neither one flat universal event list nor separate per-lab formats.

- **Envelope (manifest):**
    - `run_id` = hash of canonical spec + seed + engine versions
    - the spec, tier, evidence class, library and engine SHAs, schema list, provenance
- **Channels.** Named `coco.<family>.<name>.v<major>`, defined in `coco_schemas` (protobuf), which generates Python and TypeScript. Families:
    - world, robot, truth, `sensor.scan`, `sensor.detect`, estimate, arm
    - `plan.search`, `plan.incremental`
    - `localise.particles`, `localise.ekf`
    - `map.grid`, `map.slam`
    - `control.local`, `decide.search`, `mission.fsm`
    - metrics, annotation, input
- **3D fields (from M4):** optional z, roll and pitch on robot and truth poses, wheel speeds, and the command source (TELEOP, PLANNER, MISSION, STOP). All additive.
- **Visual primitives.** The renderer's whole vocabulary: instanced points, poses, line sets, ribbons, polygons, scalar grids, graphs, region distributions, sparse labels. Each primitive carries a pick ID back to its semantic event.
- **Lenses.** One per family. A lens maps events to primitives and defines inspector templates, default level of detail, captions and aggregates. It lays out and aggregates; it never computes the algorithm.
- **Three clocks on every event:**
    - `t_world` (simulation seconds)
    - `tick` (control cycle)
    - `seq` (computation step)

    The timeline has a world track and a computation track.
- **Storage.** MCAP container, protobuf messages, zstd-compressed indexed chunks, and keyframes every few seconds for seeking. Arena-model replays can be spec + seed + input log, re-simulated. Case Files load their first frame before their bulky scan data.
- **Golden traces.** The property corpus produces golden traces, diffed in CI.

### 5.3 Rendering

**Three.js on WebGL 2, 3D by default.** Cameras:

- **follow:** the default; sprung, with look-ahead, collision-aware
- **orbit**
- **robot-eye:** from the URDF camera link, labelled as rendered presentation; perception stays abstract
- **top-down:** the orthographic analytic view

Transitions take about 0.4 s, with a reduced-motion setting.

**Look.** A clean, muted lab style:

- matte physically based materials
- hemisphere light plus one directional light whose shadow follows the robot
- baked ambient occlusion and a small environment map
- tone mapping and adaptive anti-aliasing

**The computation layers are the brightest thing on screen.** No bloom everywhere, screen-space reflections, ray tracing or photorealism.

**Computation in 3D:**

- grids, costmaps, frontiers and heatmaps are floor decals following the terrain
- paths and candidate trajectories are ribbons slightly above the floor
- particles are instanced floor arrows
- search beliefs are translucent columns over the bays
- the mission state and command source sit in the head-up display (HUD)
- computation layers draw unlit in an overlay pass
- cutaway walls and a low-walls mode keep layers visible
- picking uses a floor ray for grids and GPU IDs for instances

**Quality tiers:** high, medium and low, chosen automatically from measured frame time, with a manual override. A device that can't hold the low tier, or lacks WebGL 2, falls back automatically to the top-down renderer, with a notice.

**Threads:** the simulation and algorithms run in a worker and post transferable buffers. The renderer owns the main thread; React draws only panels and the HUD.

**Rejected:**

- switching engines (Unity, Unreal, Godot, Babylon.js, PlayCanvas)
- pixel streaming, which can't be inspected
- WebGPU directly; later, through Three.js's WebGPU path, only if budgets fail

### 5.4 Assets

- **Robot:** the URDF meshes, which come from the Fusion 360 CAD, converted to glTF. The joint hierarchy is kept: wheels, both arm joints, both fingers, and a magnet indicator.
    - Every joint moves from events.
    - Two levels of detail: about 20k triangles near the camera, and well under 5k for phones and distant views.
- **World:** COCO's Gazebo arena from its SDF, converted to glTF, plus a small set of CC0 props outside the operating area.
- **Compression:** meshopt geometry and KTX2 textures.
- **Budget:** 5 MB or less compressed for the first scene, of which the robot is 1.5 MB or less. Larger detail streams in afterwards.
- **Asset manifest:** every file's source, licence, checksum and size. Size budgets are checked in CI.

### 5.5 Controls and game feel

- **Desktop keys:**

    | Key | Action |
    | --- | --- |
    | W / S | Forward or reverse velocity, ramped by the real acceleration limits |
    | A / D | Yaw rate (turns in place at rest) |
    | Shift | Precision mode: half speed, never above the real maximum |
    | Space | Latched STOP |
    | R | Release STOP; hold to reset home |
    | E | Context action: grasp or release through the proximity gate, otherwise inspect |
    | Tab | Switch between driving yourself and autonomy |
    | C / V | Cycle camera / back to follow |
    | 1–5 | Lenses |
    | P, [ , ] | Pause, step back, step forward |
    | H | Help |

    The mouse orbits and zooms, and a click on the floor sets an autonomous goal. Every binding is remappable and stored through the preferences module.
- **Phone and tablet:**
    - landscape, full screen
    - a left virtual joystick for velocity and yaw rate
    - buttons for STOP, E, camera and autonomy
    - tap the floor to set a goal; two fingers orbit and zoom
    - an optional tank mode: left and right wheel sliders
- **The arbiter as a game mechanic.** Manual input during autonomy takes control, and the HUD always shows the command source.
- **Feel from truth:**
    - instant local input
    - the real acceleration limits, felt through the sprung camera
    - wheels turning at the true wheel speed
    - optional wheel-speed bars
    - an optional motor sound, off by default, pitched to the wheel speed
- **Never:** strafing, a boost beyond the real maximum, fake suspension, camera shake or bob.

### 5.6 Cloud (from M5 only)

Three things, in order of cost:

1. **CDN:** the app, assets, the replay library, Case Files.
2. **Batch Stack runs:** API, queue, one fresh container per job, MCAP to object storage. Recordings include full 3D pose from the first run.
3. **Interactive Stack sessions:** gated (M6). They use the same 3D client with client-side prediction.

Rules for the cloud:

- No Kubernetes or microservices until there are several worker hosts.
- Each container gets its own network and localhost-range ROS 2 discovery.
- No user code ever runs server-side.
- Sign-in is required for Stack compute.
- A global daily spend cap.

### 5.7 Latency rules

- **In the browser:** every pedagogical interaction (scrub, inspect, layers, paint, predict, compare) and all driving of the Arena model.
- **Control latency:** key press to visible motion within one model tick plus one frame.
- **Stack sessions:** client-side prediction, interpolation, latest-state-wins delivery, and "pause the view, not the robot".
- **Safety stays server-side:** STOP latches in the arbiter path, and a disconnect stops the robot.
- **Cold start:** attract mode plays a light recorded scene while Pyodide and the 3D assets load.

### 5.8 Experiments

- **One spec format** (`spec_version`, world, scenario, robot, sensors, tier, arms, seeds, trials, metrics with one primary, budget), run identically in the browser, the cloud, or locally with `coco run spec.yaml`.
- **Results:**
    - k/n with Wilson 95% intervals
    - median and IQR with bootstrap intervals
    - McNemar or Wilcoxon for paired comparisons
- **Exports:** YAML, CSV, Parquet, MCAP.

### 5.9 Hardware contract (gated, not built)

A future physical robot is a third backend behind the same gateway and event families, with:

- the HARDWARE class
- a hardware e-stop
- firmware limits
- a supervisor
- a reservation system

Any participant can press STOP; only the driver drives.

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
- A third simulator (MuJoCo, Webots, Isaac) inside COCO Lab, or a physics engine in the browser
- Switching rendering engines
- Photoreal or ray-traced rendering; a world or level editor; a second world before the first is excellent
- Perception on rendered pixels in the browser
- Gamepad, VR or AR, multiplayer
- A physical-robot mode before a robot exists
- A global leaderboard before deterministic server-side score verification exists
- Kubernetes, multi-region, microservices
- XP, levels, streaks, loot, or any score that rewards luck
- Package renames or restructures done for aesthetics
- Changes to the COCO robot repo or its worktrees

---

## 7. Roadmap

```
M0 ─▶ M1 ─▶ M2 ─▶ M3 (done or closing)
   ─▶ M4 3D Arena  ── first checkpoint: feasibility gate on Gautham's phone ──  public v2.0 launch
   ─▶ M5 Stack in the cloud: batch + experiments
   ─▶ [gate: cost per slot-hour fits budget AND demand shown] ─▶ M6 Interactive Stack sessions
   ─▶ [gate: a physical robot exists] ─▶ M7 Hardware bridge
```

Effort ranges are rough estimates for part-time, agent-assisted work.

### Completed milestones

Details live in their prompts (`docs/v2/M*_PROMPT.md`), results (`docs/v2/M*_RESULTS.md`) and reviews (`docs/v2/reviews/`).

| Milestone | What it delivered |
| --- | --- |
| M0 Transition | v1 frozen and tagged; baseline measured; plan installed; honesty fixes; robot-stack packages frozen |
| M1 Glass-box Arena core | `coco_schemas`, World Spec v1, Arena model, planners emitting events, Pyodide worker, Three.js renderer (2.5D), timeline, share links, 4-engine determinism |
| M2 The whole loop | Localise, Map, Move and Decide lenses; the teaching controllers; the Arena fetch mission; Run 15 in the model; fidelity report v1; Learn missions 1–6; the CI claims check; v1 retired to `/v1/` |
| M3 Play and Case Files | ROS-to-event adapter; 100 Case Files; mission 7; five challenges; `coco verify`; the four-mode app; v2.0 drafts. Closes with: a review, scans loaded after the first frame, the outstanding re-measurement, and a quiet merge (no announcement) |

### M4 · 3D Arena: the public v2.0 launch (about 5–7 weeks)

**Objective:** a visitor opens the site and is inside COCO's arena in 3D. They drive the robot with keys or touch, hand it to autonomy, watch every algorithm compute in the world, drop to top-down to inspect, race the planner's ghost, and open a Case File in the same world. Everything stays deterministic, measured, honest about being kinematic, and fast on a phone.

**Checkpoints:**

1. **M4.1 Feasibility gate.**
    - A first conversion of the robot (URDF) and the world (SDF) to glTF.
    - A perspective scene with the follow camera, driving on the flat floor, and the Plan lens on the floor.
    - Measured on the laptop and under emulated weak-device conditions.
    - A preview Gautham can open on his phone over mobile data, plus a measurement guide.
    - Three reference screenshots that fix the visual target.

    The gate decides only the phone default (3D or top-down). The milestone continues either way, and the agent does not wait for the result.
2. **M4.2 Asset pipeline.**
    - SDF and URDF to glTF, meshopt, KTX2, levels of detail.
    - The asset manifest with licences and checksums.
    - Size budgets in CI.
    - World Spec v2 with elevation, and the World Spec ↔ SDF agreement check in CI.
3. **M4.3 Arena model.**
    - Kinematic terrain following.
    - Contact stop and contact events.
    - Teleop preempting autonomy, with the command source as an event.
    - The gated grasp action; reset home.
    - Additive schema fields.
    - Flat-scene golden traces and hashes byte-identical to M3; new terrain sessions deterministic across all four engines.
    - A terrain section in the fidelity report.
4. **M4.4 3D renderer.**
    - Lighting, materials, shadows, environment map, tone mapping, anti-aliasing.
    - The overlay pass, cutaway walls and low-walls mode.
    - Floor decals that follow the terrain; 3D picking.
    - Quality tiers and the automatic top-down fallback.
5. **M4.5 Cameras and controls.**
    - The four cameras and their transitions, with reduced motion.
    - The remappable key map and the generalised preferences module.
    - Touch joystick and tank mode.
    - The HUD: command source, wheel-speed bars, the MODEL · kinematic badge.
    - The optional motor sound and the help overlay.
6. **M4.6 Every lens in 3D.**
    - Plan, Localise, Map, Move, Decide, at the Watch, Explain and Inspect levels.
    - LiDAR at the sensor's height; belief columns.
    - The timeline in every camera, including the follow camera during replay.
7. **M4.7 Case Files in 3D.**
    - The adapter carries full 3D pose wherever recordings contain it, and a "planar recording" chip otherwise.
    - Case Files reconverted within budget, citing their source checksums.
    - Model-vs-Stack side by side in 3D.
8. **M4.8 Learn and Play in 3D.**
    - Camera presets per mission step.
    - Precision challenges open in top-down.
    - **Race the planner's ghost:** time, path length and contacts against a ghost following the planner's path under the same limits. Thresholds come from a reference; the links reproduce; `coco verify` supports it.
9. **M4.9 Launch preparation** (drafts only; Gautham publishes):
    - the landing page becomes 3D attract mode
    - updated v2.0 release notes and a demo-recording script shot in 3D
    - `docs/v2/USABILITY_TEST_M4.md`, the consolidated test
    - the phone guide
10. **M4.10 Measure and close.** Every budget measured; `docs/v2/M4_RESULTS.md`; a pull request.

**Acceptance criteria:**

| Area | Criterion | Who measures |
| --- | --- | --- |
| Frame rate (RTX 4050, balanced, AC) | 60 fps on high tier with the world, robot and fetch-mission default layers; 60 fps on the M2 stress scene at medium tier | Agent |
| Frame rate (laptop integrated GPU) | 60 fps on medium tier with default layers | Agent |
| Control latency | Key press to visible motion within one model tick plus one frame (about 50 ms or less), median over 100 presses | Agent |
| Camera | No frame over 50 ms during transitions; no long tasks while driving | Agent |
| Cold start (emulated 4G) | First visible computation 10 s or less; live model ready 10 s or less; 3D world interactive 12 s or less | Agent |
| Download | First-scene assets 5 MB or less compressed; robot 1.5 MB or less | Agent (CI) |
| Case Files | First frame 2 s or less on emulated 4G for 100 of 100, including 3D geometry | Agent |
| Determinism | Flat-scene hashes and golden traces byte-identical to M3; terrain sessions identical across Chromium, Firefox, WebKit and Pyodide-in-Node (100 sessions) | Agent (CI) |
| Regressions | Every M3 criterion still met: challenge links, `coco verify`, the 16 replays, every old URL form, the claims check | Agent (CI) |
| Assets | World Spec ↔ SDF agreement within tolerance; every asset licensed, with checksum, in the manifest | Agent (CI) |
| Hygiene | 0 console errors; no WebGL context loss in a 30-minute scripted session; phone-width layout checked | Agent |
| Fallback | A device forced below the low tier gets the top-down renderer automatically, with a notice | Agent (emulated) |
| Phone frame rate | 30 fps or more on the automatic tier with world and default layers, across a 10-minute session | Gautham |
| Phone cold start | First visible computation 10 s or less on mobile data; 3D world interactive within 15 s | Gautham |
| Phone touch and stability | Joystick response feels immediate (about 100 ms or less in `?perf`); no reload, crash or context loss in 10 minutes | Gautham |
| Usability | 5 people new to robotics, unaided: at least 4 of 5 drive to a marked spot within 60 s, point at the planner's search in 3D, explain the top-down heatmap, and say why they won or lost against the ghost. "Felt like a game" and "I could see what the robot was computing" both median 4/5 or more. Nobody reports motion discomfort | Gautham |

**Not in M4:**

- a physics engine
- a second world
- perception on pixels
- gamepad, VR, multiplayer
- WebGPU
- photorealism, a world editor
- any cloud, server or account
- the four later challenges
- RL, multi-robot, VLM

**Stop and escalate if:**

- Flat-scene hashes change.
- The first-scene download can't fit 5 MB.
- The converted world can't be made to agree with the World Spec.
- A Stack recording would need invented 3D pose.
- Any step would require deleting evidence or breaking a public URL.

**Launch.** The public v2.0 release and announcement happen after M4 is merged, the Gautham rows pass, and Gautham publishes them.

### M5 · The Stack in the cloud: batch runs and experiments (about 4–6 weeks)

**Built:**

- pinned headless Stack image
- worker and queue
- small API with sign-in and quotas
- object storage
- pre-run replay library (recordings with full 3D pose)
- "Run N seeds"
- the `coco run` command line
- global spend cap

**Measured:**

- Stack real-time factor in cloud containers
- start-up time
- CPU-only (software rendering) against GPU
- cost per run and per slot-hour

### M6 · Interactive Stack sessions (gated, about 4–6 weeks)

**Gate:**

- M5's cost per slot-hour fits the budget (G4).
- Demand shown after the v2.0 launch.

**Built:**

- session manager, warm pool, gateway
- additive `coco.v1` event channel
- the 3D client with client-side prediction and interpolation

**Measured remotely:** STOP, preemption, spectators, caps, disconnect.

**Then:** retire the public Tailscale Live tab.

### M7 · Hardware bridge (gated)

Gated on:

- a physical robot existing (G5)
- the robot project's sim-to-real gate
- M6's remote-safety measurements

---

## 8. Decisions

### Recorded decisions (11 October 2026)

| ID | Decision |
| --- | --- |
| D1 | 3D is the default experience. Top-down is a camera mode and the automatic fallback. If the phone fails the M4 feasibility gate, phones default to top-down and desktops to 3D |
| D2 | "M4 · 3D Arena" comes before cloud work. Cloud batch is M5, interactive sessions M6, hardware M7 |
| D3 | The first world is COCO's Gazebo arena converted from its SDF, with dressing outside the operating area |
| D4 | The Arena stays planar kinematics plus kinematic terrain following; no physics engine in the browser |
| D5 | M3 merges quietly; the public v2.0 launch waits for M4; the phone baseline is measured now; one consolidated five-person usability test at the end of M4 replaces the M1–M3 tests |
| D6 | Case File scans load after the first frame (ADR 0005 amended); the narrowed storage guard is accepted and generalised into one preferences module |

### Pending decisions, and the defaults agents use until Gautham decides

| ID | Decision | Default until decided |
| --- | --- | --- |
| G1 | Primary audience | Learners first |
| G2 | Priority against the robot project and job hunt | Not an agent decision; agents respect announced robot batch windows |
| G3 | Canonical robot stack | The robot repo is canonical; `coco-labs` robot packages are frozen, not deleted |
| G4 | Monthly cloud budget | Zero; no cloud resources are created before M5 and an explicit budget |
| G5 | Will a physical robot exist within a year? | Assume no; no "real robot" wording anywhere |
| G6 | License and outside contributions | Unchanged from the current repo |

---

## 9. Rules for coding agents

1. **One prompt per milestone.** Work through every checkpoint without pausing, unless a stop condition fires.
2. **Read first:** `README.md`, `docs/STATUS.md`, `CLAUDE.md`, `PROJECT_STATE.md`.
3. **Apply the drift test** before each task. Anything outside the checkpoint list goes to `docs/IDEAS.md`, never into code.
4. **Branch and commits.**
    - Branch `v2/<milestone>` (for example `v2/m4-3d-arena`).
    - Commits are prefixed with the checkpoint, for example `[M4.3]`.
    - `docs/STATUS.md` is updated at every checkpoint.
5. **Testing.** Focused tests during work; the full suites (`run_all_package_tests.sh`, web tests, build-tool tests) at each checkpoint's end.
6. **Resources and measurement.**
    - Hardware: RTX 4050 laptop GPU (6 GB VRAM), Intel integrated GPU, 16 GB RAM, Ubuntu 24.04, ROS 2 Jazzy.
    - Never run two simulators at once. Respect robot batch windows.
    - Measure on the balanced power profile, on AC. You may switch the profile and must restore it.
    - Every harness records power state and GPU driver version.
7. **Visual review.** Agents cannot judge looks reliably. Screenshot tests catch regressions only.
    - At each M4 checkpoint that changes the look, commit screenshots to `docs/v2/data/m4/screens/` and list them in `STATUS.md` for Gautham's review.
    - Carry on without waiting. Apply Gautham's recorded feedback at the next checkpoint.
8. **Never:**
    - delete evidence, tags or releases
    - create or edit releases
    - run destructive git commands without approval
    - touch the robot repo
    - invent numbers
    - mark anything MEASURED without committed data
    - mark a Gautham-owned row as done
9. **Final report**, in this form:

```
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (device, power profile, driver, conditions):
Acceptance criteria: each → met / not met / pending Gautham, with evidence:
Screenshots awaiting Gautham's review:
Files removed (full list) and why:
Decisions recorded (ADRs) and plan-change log entries:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```

10. **Independent review.** A milestone closes in `STATUS.md` only after a fresh review session, given only the repo, this README and the report, has verified that:
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
| `docs/v2/` | Prompts, results, reviews, ADRs, schemas, fidelity reports, asset manifest |
| `docs/archive/v1/` | Archived v1 README, roadmap and other retired docs |
| `CLAUDE.md` | Engineering rules for agents |
| `PROJECT_STATE.md` | Authoritative current state |
| `~/coco_lab_runs/` | Raw evidence recordings (outside git; never delete) |
