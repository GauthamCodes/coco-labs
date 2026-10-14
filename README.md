# COCO Lab v2 — Master Plan: Play, Compare, Research

> **Authority file for all COCO Lab work. Revision 3, 14 October 2026: three purposes, three modes.**
> Every coding agent (Claude Code, Codex or any other) reads this file, `AGENTS.md` and `docs/STATUS.md` before touching anything.
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

**COCO Lab is one browser app with three purposes, and one mode for each.**

| Mode | Purpose | Who it's for | First thing a visitor does |
| --- | --- | --- | --- |
| **Play** | A fun robot game anyone can play, anywhere, anytime, with ROS 2 at its core | Everyone | Picks a mini-game card, gets a 20-second tutorial, plays |
| **Compare** | See how algorithms differ, through the costmaps they actually work on | Learners, instructors | Picks two algorithms and a goal, watches both search the same costmap side by side |
| **Research** | Reproducible experiments and real ROS 2 recordings | Students, researchers | Builds an experiment, runs many seeds, exports results, or opens a recorded ROS 2 run |

The first screen is a **title screen**: COCO idling in its world at night under a work light, the logo, and three large cards, Play · Compare · Research. Everything else is behind one of those doors or on a quiet About page.

- **Tagline:** *See what the robot computes.*
- **The design question every feature answers:** what is the robot computing right now, and how can the user see and understand it?
- **The core moment:** the ISRO Pygame simulator grown into a 3D game. You drive COCO, or send it, through a warehouse; its planner's search spreads across the floor; it finds, picks up and delivers objects with its arm; and at the end you see the heatmap of everything it computed.

### What "ROS 2 at its core" means

A full ROS 2 stack cannot run inside a phone's browser, and cloud ROS sessions for every player would cost money per player. So ROS 2 is at the core in these five ways, in order of cost:

| Layer | What it means | When |
| --- | --- | --- |
| **ROS-shaped model** | The browser robot speaks ROS 2 message shapes internally (`LaserScan`, `OccupancyGrid`, `Twist`, `Path`, TF frames). A "ROS graph" panel shows the topics flowing between nodes (`/scan`, `/odom`, `/map`, `/plan`, `/cmd_vel`) | M6 |
| **Every level is a real Gazebo world** | One level file compiles to the browser world *and* a Gazebo SDF world with a Nav2 map and params, validated by launching it in Gazebo | M6 |
| **The real ROS 2 ghost** | For each level and objective, the real stack (Nav2, MoveIt, Gazebo) is recorded doing it on Gautham's laptop. In the game, that recording races you as a translucent ghost labelled STACK | M6 |
| **Connect your own ROS 2** | Researchers connect their own ROS 2 nodes to the browser robot over a local WebSocket bridge | M7 |
| **Cloud ROS 2 sessions** | Live Gazebo and Nav2 in the cloud | M9, gated |

The first three make the claim true for every player, at no running cost.

### Pillars

| Pillar | Promise | Test a feature must pass |
| --- | --- | --- |
| Glass box | The robot's computation is visible and inspectable | Does it make some computation visible or understandable? |
| Honest | Model, Stack and hardware results are labelled, never conflated; good looks never imply physics the model doesn't have; failures stay on display | Is every on-screen claim traceable to evidence, with its class? |
| Playable | Zero install, instant response, game-like feel, good-looking | Would a non-roboticist enjoy the first two minutes on a phone? |
| Focused | Every screen serves Play, Compare or Research; nothing else is on screen | Can a newcomer tell what to do first? |
| Reproducible | Every run is a spec plus a seed anyone can rerun | Can someone reproduce what they see from a link? |

### Who it is for, in priority order

1. Robotics learners (the design target).
2. Instructors.
3. Researchers and practitioners.

Everyone else comes for the game.

### What COCO Lab is not

- a physics-accurate simulator (physics comes from Gazebo, through recordings and later cloud runs)
- a cloud ROS IDE
- a course website or a dashboard
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
| M3 Play and Case Files | Merged quietly (PR #22, `bf7443f`); independently reviewed |
| M4 3D Arena | Merged (PR #23, `6c286b7`) and live; reviewed at merge; Gautham's rows pending |
| Gautham's phone and usability rows | Not run since M1. The phone measurement and a 3-person test are due before M5's design work |

**Architecture today.**

- `lab_web` (Vite, TypeScript, React) on GitHub Pages: a Three.js WebGL 2 renderer, 3D by default with a top-down analytic camera.
- `coco_lab` (pure Python, no `rclpy`) runs in a Pyodide worker as the Arena model and every algorithm.
- `coco_schemas` defines the event families, stored in MCAP.
- `coco_lab_ros` converts ROS recordings into Case Files.
- `platform_server` (in `coco_web`) is the only web-to-ROS bridge for Live, speaking `coco.v1`.
- `cmd_vel_arbiter` is the only wheel publisher.

`docs/STATUS.md` holds the current SHAs and test counts.

### What the October 13 assessment found

- **The core is strong:** deterministic simulation, glass-box algorithms, a working 3D pipeline, honest evidence, about 4,100 passing tests.
- **The surface is a dashboard, not a game.** The Arena page is 1,817 px tall, with 13 rows of controls and about 70 run links under the 3D view.
- **The 3D view is unflattering.** It has heavy LiDAR moiré, and the low camera turns the walls into grey slabs.
- **Phones get a 250-pixel strip.**
- **Play, Learn and Case Files are lists of links.**
- **Defects remain from M4:** an unbounded race-link input, a state-hash gap, race controls left enabled, a placeholder robot in Case Files, and a failing v1 workflow.
- **Agent overhead is high:** `CLAUDE.md`, `STATUS.md` and `PROJECT_STATE.md` total about 4,800 lines, read at the start of every session.

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
| The 44 mm band: `robot_radius` 0.20 → 0.25 closed a gap between the local costmap and the collision monitor | STACK | Mechanism not exercised in the 12/12 re-run |
| Latched STOP; drive command p50 4.6 ms; STOP 6.2 ms | STACK | Local network |
| Phone on mobile data drove the robot; RTT about 282–293 ms; disconnect stop about 0.54 s | REMOTE | Robot simulated |

### Corrections every agent must respect

1. **No physical robot exists.** Nothing has run on hardware. "Real" in COCO Lab means the full ROS 2 stack in Gazebo, as opposed to the browser model.
2. **The gripper has two fingers and a magnet, and the magnet does the holding** (it fires before the fingers close). Describe it that way, never as fingers alone and never as a magnet alone.
3. **Live drives the simulated stack** on Gautham's machine. Its name and copy must not imply hardware.
4. **Lab 5, head-on scenario.** The actor walked into an already-stopped robot in all 15 runs. DWB's and MPPI's "reached" exists only because the actor has no collision body.
5. **The Arena model is kinematic.** In 3D it can climb a ramp visibly, but it never simulates tipping, slip, friction or contact forces.
6. **COCO is a 4-wheel skid-steer base modelled as differential drive.** It turns in place and never strafes.

### Unresolved, and kept labelled as unresolved

- DWB's hairpin stall
- why no controller swerved
- D\* Lite's extra work on the real costmap
- loop-closure damage
- exact Run 15
- recovery from confident AMCL divergence
- the collision-monitor residual
- the Arena pose graph's poor score on a long tour (F1 0.316 against 0.580)
- the terrain LiDAR, never compared with Gazebo
- untested remote behaviours: phone STOP, second spectator, mid-mission preemption, remote mission completion, idle and session caps, the cause of the disconnect, and the stale Nav2 "executing" label

---

## 3. Non-negotiable rules

### Invariants

1. `coco_lab` never imports `rclpy`.
2. **The control boundary.** Browser code that controls COCO's Stack (Live, cloud sessions) never names a ROS topic; it speaks `coco.v1`, which only grows additively unless a major version is declared. Two things are outside this boundary:
    - The ROS-shaped model and the ROS graph panel may *show* ROS names, because they teach.
    - The "Connect your ROS 2" bridge (M7) talks only to the visitor's own local ROS 2, never to COCO's Stack, and its runs carry the EXTERNAL evidence class.
3. `cmd_vel_arbiter` is the sole wheel publisher, in every tier, forever. In the browser the same priority rule holds: STOP > the person driving > assists and autonomy.
4. Ground truth has one authoritative source: the `truth` channel. Nothing fabricates truth elsewhere. Height, roll and pitch are never invented for a Stack recording that didn't record them.
5. Data formats are versioned. A breaking change means a major version plus a converter. **State hashes are versioned too:** a new hash version never invalidates links made under an older one.
6. Comparisons hold every non-compared variable fixed.
7. Remote control is exclusive and interruptible, and STOP always wins.
8. Gazebo `--fast` stays banned. It produced 531/533 tip-overs.
9. Any second implementation of an algorithm (WebAssembly, TypeScript) must be trace-equivalent to the Python reference on the property-test corpus, checked in CI.
10. **No physics engine in the browser.** The Arena model is planar kinematics plus kinematic terrain following. Adding rigid-body physics requires a new decision by Gautham.
11. **Rendering never changes the model.** Cameras, lighting, interpolation, wall display height and visual effects are outside the per-tick state hash.
12. **Every world is a real Gazebo world** (from M6). A level is authored once as a World Spec and compiled to the browser world, a Gazebo SDF and a Nav2 map. The original COCO arena remains the reference for every existing recording.
13. **Game rules are not physics.** A rule such as "fragile cargo" is a scoring rule about how the player drives, measured and labelled as a rule. It never claims the model simulates breakage, damage or forces.

### Evidence classes, used in code, docs and UI

| Class | Meaning |
| --- | --- |
| MODEL | `coco_lab`, the Arena model, the browser |
| STACK | Full ROS 2 stack in Gazebo, recorded |
| REMOTE | Over the public internet, robot simulated |
| EXTERNAL | Driven by a visitor's own ROS 2 through the bridge (M7) |
| HARDWARE | A physical robot. **None exist.** |
| UNRESOLVED | Reproduced but unexplained, statistically unresolved, or untested |
| CONCEPT | Discussed, not built |

The labels shown to learners map onto these: MEASURED, TESTED (a property or unit test proves it), ASSUMPTION, SIMPLIFIED MODEL, SIMULATION RESULT, REAL ROBOT RESULT, INFERENCE, UNRESOLVED.

Whenever the Arena model drives the robot, a small "MODEL · kinematic" badge is visible in the HUD corner. Grasp Assist shows "MODEL · MoveIt-style".

### Integrity rules

1. **Every learner-facing claim cites committed evidence.** Missions, tours and Case File text without evidence references fail CI.
2. **Negative results stay visible.** Nothing is removed to make a lesson look cleaner.
3. **Never delete evidence:**
    - recordings in `~/coco_lab_runs/`
    - the contents of `docs/RESULTS.md`, which is append-only
    - release tags
    - GitHub releases

    Moving documentation into archives is allowed; deleting it is not.
4. **No game mechanic changes robot behaviour or rewards luck.**
    - Scores use real metrics or decision quality in expectation.
    - Controls map to what COCO can physically do: it turns in place but never strafes, and never exceeds its real speed or acceleration limits.
5. **Git safety.**
    - No `git clean`, `git reset --hard`, force-push, branch deletion or tag deletion without Gautham's explicit approval.
    - Work happens on `v2/...` branches, merged to `main` only with green CI and Gautham's approval.
6. **The machine is shared with the robot project.** No heavy COCO Lab jobs (Gazebo, long builds, benchmarks) run during an announced robot batch window.
7. **Browser storage and telemetry.**
    - Per-viewer preferences and progress live in `localStorage`, through one preferences module, every access inside `try`. The page works without it.
    - A **service-worker cache** may hold static assets only (the app, Pyodide, the `coco_lab` wheel, 3D assets, recordings), versioned by content hash, never personal data.
    - **One cookieless, aggregate-only visit counter** may run when Gautham switches it on in the site config. No personal data, no fingerprinting, no per-user tracking.
    - No cookies, no `sessionStorage`, no IndexedDB for personal data, no other analytics.
8. **Every asset has a recorded licence.** Third-party textures, environment maps, props, fonts and icons must be CC0, OFL or an equivalent permissive licence, listed in the asset manifest with source and checksum. COCO's own CAD meshes are Gautham's own work.

---

## 4. Component verdicts

| Component | Verdict | What happens |
| --- | --- | --- |
| `coco_lab` and the Arena model | Keep, extend | Nav2-style costmap layers (M5); World Spec v3 worlds, Grasp Assist, mini-game rules (M6–M7) |
| Pyodide in a Web Worker | Keep | WebAssembly only for a kernel that misses a measured budget, trace-equivalent |
| `coco_schemas`, MCAP, keyframes | Keep, extend | Versioned state hash v2 (M5); `manip.grasp` and game families (M6) |
| Three.js renderer | Keep, restyle | "Night Shift" look; LiDAR as a scan area; three-quarter camera; dollhouse walls in Play; multi-pane rendering for Compare |
| `ArenaApp.tsx` (1,097 lines) | Split | A shared scene core plus three thin shells: Play, Compare, Research (M5) |
| Mode navigation (Learn, Play, Sandbox, Case Files) | Replace | Title screen plus Play, Compare, Research (M5) |
| Learn missions 1–7 | Move | Guided tours inside Compare, claims and evidence intact (M5) |
| Sandbox | Move | Play › Free roam (M5) |
| Case Files and the run list | Move | Research › Recordings library; Play's "real ROS 2 ghost" (M5–M6) |
| Five challenges and Race the ghost | Keep, restyle | Game cards and a scorecard in Play (M5) |
| Lens bar, levels, layer checkboxes, planner buttons | Move | Compare's side panel or the Settings drawer; Play gets one "Robot vision" toggle |
| Live Stack (simulated), v1 archive links | Move | About page |
| World Spec | Extend | v3: a modular level kit compiled to browser, Gazebo SDF and Nav2 map (M6) |
| COCO arena | Keep | The "Proving Ground" level and the home of existing recordings |
| COCO Depot | New | The game world, about 48 × 32 m (M6) |
| Grasp Assist | New | A glass-box, MoveIt-style pick pipeline in the model (M6) |
| Research mode | New | Recordings library (M5); experiments, exports, "Run it in ROS 2", the ROS 2 bridge (M7) |
| `CLAUDE.md` (935 lines) | Replace | `AGENTS.md`, about 200 lines, read by every agent; `CLAUDE.md` points to it; robot-stack lore archived (M5) |
| `docs/STATUS.md` (1,887 lines), `PROJECT_STATE.md` (1,990 lines) | Slim | Current state only; history moved to archive files (M5) |
| RL-era scripts at the repo root | Move | Under `coco_rl/` (frozen) (M5) |
| `coco.v1`, `platform_server`, Docker image | Keep | Live and future cloud (M8–M9) |
| Arbiter, latched STOP, caps, kill switch | Keep | Unchanged in every tier |
| Robot-stack ROS packages inside `coco-labs` | Freeze | Not deleted; no new features |
| Isaac inside COCO Lab, VLM layer, browser policy training, browser physics engine, engine switch | Remove | Out of scope |

---

## 5. Target architecture

### 5.1 Two simulation tiers, real worlds

**Tier 1: the Arena model.** A deterministic simulator running beside the algorithms in a Web Worker (Pyodide + `coco_lab`). It costs nothing per user.

It is deterministic by construction:

- fixed time step
- single-threaded loop
- seeded in-library RNG
- versioned per-tick state hash

What it simulates:

- **Planar differential-drive kinematics** with the real speed and acceleration limits.
- **2D LiDAR** at the sensor's real mounting height.
- **Kinematic terrain following:** height and pitch from the world's elevation data. No tipping, slip or forces.
- **Contact:** the robot stops on contact and the contact is recorded as an event.
- **Grasping:** the gated grasp, extended in M6 into Grasp Assist.

**Tier 2: the Stack.** The ROS 2 Jazzy + Gazebo Harmonic system. It is the source of everything physical (tipping, slip, friction, contact, MoveIt, camera perception). Its recordings are its replays.

- Today it reaches users as recordings.
- From M6, as real ROS 2 ghosts for every Depot level.
- From M8, as cloud batch runs; from M9, gated interactive sessions.

**Worlds.**

- **World Spec v3** (M6) is a modular level kit: walls, doors, racks, benches, pallets, ramps, docks, drop zones, object spawns and actor lanes.
- Each level compiles to:
    - the browser world and its glTF scene
    - a Gazebo SDF world (moving actors as models *with* collision bodies)
    - a Nav2 map (PGM + YAML) and parameters
- **CI checks schema and geometry.** Gazebo and Nav2 validation runs on the laptop and is recorded as STACK evidence.
- The original COCO arena (SDF-derived, World Spec v2) stays as the Proving Ground.

**Fidelity report.** Each release ships one, shown in the UI as "model gap" chips. It covers LiDAR against Gazebo, odometry in turns, controller tracking and terrain, and from M6, Grasp Assist against recorded MoveIt picks.

### 5.2 One trace system

A **family of typed schemas under one envelope**.

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
    - `costmap.layers` (M5)
    - `manip.grasp` and `game` (M6)
- **3D fields:** optional z, roll and pitch on poses; wheel speeds; command source.
- **Visual primitives.** Instanced points, poses, line sets, ribbons, polygons, scalar grids, graphs, region distributions, sparse labels. Each carries a pick ID back to its semantic event.
- **Lenses.** One per family. A lens maps events to primitives and defines inspector templates, level of detail, captions and aggregates; it never computes the algorithm.
- **Three clocks on every event:** `t_world`, `tick`, `seq`.
- **State hash, versioned.** v1 (through M4) and v2 (M5: adds the planner's hand-back goal and every other input that can change behaviour). Every link records its hash version and verifies under it.
- **Storage.** MCAP with zstd-compressed indexed chunks and keyframes. Case Files load their first frame and the robot model before scan data.
- **Golden traces.** The property corpus produces golden traces, diffed in CI.

### 5.3 The product shell

- **Title screen.** It is the attract mode: a light 3D scene that loads first while Pyodide warms up behind it, with three mode cards and an About link.
- **Play.**
    - The 3D world fills the screen, with a HUD in the corners.
    - Contents: game cards, a first-run tutorial, the mini-games, free roam, a scorecard and a 10-second instant replay.
    - In landscape on phones, a full-screen layout; in portrait, a "rotate your phone" card.
- **Compare.** Synced panes, the layered costmap, the side panel with algorithms and parameters, a lockstep timeline, a difference view, a results strip and guided tours. It works in portrait with stacked top-down panes.
- **Research.** The Recordings library (M5), then the experiment builder, runner, results, exports and "Run it in ROS 2" (M7).
- **About.** What COCO Lab is, the evidence classes, Live Stack (simulated), the v1 archive, credits and licences.
- **Settings drawer** (gear icon, in every mode): quality tier, wall height, sound, key bindings, theme, reduced motion.
- **Code shape.**
    - One scene core: renderer, cameras, controls, session, and the worker client.
    - Three shells: Play, Compare, Research, each lazy-loaded.
    - three.js in its own long-cached chunk.

### 5.4 Rendering and look ("Night Shift")

- **Engine:** Three.js on WebGL 2. Compare's panes render as scissored viewports in **one** WebGL context, never one context per pane.
- **Art direction:** a dark, calm robot warehouse after hours, with graphite floors, matte racks and warm work lights. **The robot's computation is the only thing that glows.**
    - The computation colours keep fixed meanings (frontier, visited, chosen path, rejected candidates, uncertainty, truth always as an outline), tuned for a dark background and checked against colour-blindness simulations.
    - A light theme remains for classrooms and projectors.
- **Design tokens** live in one file: colours, type, spacing, radius, motion. Restyling is one change.
    - One display face and one UI face, self-hosted and licensed.
    - One icon set.
    - Motion: 150–250 ms eased, a single pulse on decisions, reduced motion honoured.
- **Cameras:**
    - **Follow (default):** a three-quarter view, about 4–6 m back and pitched down 35–45°, sprung and collision-aware.
    - **Orbit.**
    - **Robot-eye:** labelled as rendered presentation.
    - **Top-down:** the analytic view.

    Transitions take about 0.4 s.
- **LiDAR** is drawn as a filled, translucent "what COCO can see" area with bright hit points. Individual rays appear only at Compare's Inspect level, thinned.
- **Walls** have lighter top caps, darker sides and edge lines. In Play they display at half height ("dollhouse") by default. This is a display choice that changes nothing the model uses.
- **Computation in 3D:**
    - grids, costmaps, frontiers and heatmaps are floor decals following terrain
    - paths and trajectories are ribbons
    - particles are instanced floor arrows
    - beliefs are translucent columns over regions
- **Quality tiers** (high, medium, low) are chosen automatically from frame time, with a manual override. A device that can't hold the low tier, or lacks WebGL 2, falls back to the top-down renderer with a notice.
- **Rejected:** switching engines, pixel streaming, WebGPU directly (later through Three.js only if budgets fail), photorealism.

### 5.5 Assets

- **Robot:** the URDF meshes converted to glTF, with the joint hierarchy kept (wheels, arm joints, fingers, magnet indicator) and two levels of detail. **The low-detail robot (about 144 kB) always loads first.**
- **Worlds:** generated from World Spec, built from a modular kit of CC0 or own-made pieces (instanced). The kit and textures live in an asset manifest with licences, sources and checksums.
- **Compression:** meshopt geometry and KTX2 textures.
- **Budget:** the first scene is 5 MB or less compressed. Larger detail, and other Depot zones, stream in afterwards.
- **Service-worker cache:** static assets only, content-hashed (integrity rule 7).

### 5.6 Controls and game feel

**Desktop:**

| Key | Action |
| --- | --- |
| W / S | Forward or reverse velocity, with the real acceleration limits |
| A / D | Yaw rate (turns in place at rest) |
| Shift | Precision mode: half speed, never above the real maximum |
| Space | Latched STOP |
| R | Release STOP; hold to reset home |
| G | Grasp Assist (from M6) |
| E | The gated grasp or release (today), then an alias of G |
| Tab | Switch between driving yourself and autonomy |
| C / V | Cycle camera / back to follow |
| X | Robot vision: cycle Play's overlays |
| P, [ , ] | Pause, step back, step forward |
| H | Help |

The mouse orbits and zooms, and a click on the floor sets an autonomous goal. Every binding is remappable and stored through the preferences module.

**Phone and tablet:**

- landscape, full screen
- a left virtual joystick
- right-hand buttons: STOP, Grasp, Autonomy, Camera
- tap the floor for a goal; two fingers orbit and zoom
- an optional tank mode

**The arbiter is a game mechanic.** Manual input takes over from autonomy. The HUD always shows the command source: YOU, PLANNER, ASSIST or STOP.

**Feel from truth:**

- instant local input
- real acceleration limits, felt through the sprung camera
- wheels turning at the true wheel speed
- an optional motor sound and soft UI sounds, off by default

**Never:** strafing, boost beyond the real maximum, fake suspension, camera shake or bob.

### 5.7 Compare

- **Panes:** 2 or 4, synced camera (top-down by default, 3D toggle), each running one algorithm on the same map, start, goal and seed.
- **Costmap layers, Nav2-style:**
    - static
    - inflation: a gradient with the lethal and inscribed bands outlined; sliders for inflation radius, cost-scaling factor and robot radius
    - obstacle (live LiDAR)
    - combined
    - hover shows any cell's cost

    The inflation formula follows Nav2's documented one and is tested against it.
- **Families:**
    - global planning: BFS, Dijkstra, A\*, greedy, weighted A\*, D\* Lite
    - local control: DWA-style sampler, pure pursuit, MPPI
    - localization: MCL with and without injection, EKF
    - mapping: occupancy, EKF-SLAM, FastSLAM, pose graph
- **Difference view:** cells only A expanded, only B, or both; both paths drawn.
- **Lockstep timeline:** one scrubber steps every pane together.
- **Results strip:** expansions, path length, path cost, minimum clearance, compute time (with the device named), success.
- **Guided tours:**
    - Learn's missions 1–7, claims and evidence intact
    - real-story tours: the 44 mm band, the A\* myth, D\* Lite's 2.9×, the Lab 5 hairpin, Run 15

### 5.8 Grasp Assist (M6)

One button (G) runs a visible, MoveIt-style pipeline in the model, badged "MODEL · MoveIt-style", emitting `manip.grasp` events.

1. **Detect** objects in sensor range (camera view plus a short radius) and outline them.
2. **Check** each object as graspable or not, with the reason:
    - too wide for the fingers
    - out of the arm's reach envelope
    - not magnetic
    - blocked

    The reach envelope is drawn on the floor.
3. **Choose** the best candidate (reachable, cheapest approach). The ranking shows on hover.
4. **Approach:** the global planner to the pre-grasp pose, then the local controller into the approach window, which is the Stack's proximity gate.
5. **Reach:** the arm's IK solution as a ghost arm, then the joint trajectory.
6. **Grip and verify:** the fingers close, the magnet holds, the object attaches; on failure, the reason is shown.

The real MoveIt doing real picks appears through STACK recordings and ghosts. The Depot's object catalog holds graspable items within COCO's gripper envelope plus deliberately ungraspable ones that teach the reasons.

### 5.9 Play: the COCO Depot and the mini-games (M6–M7)

**COCO Depot:** a night-shift warehouse of about 48 × 32 m.

- Its zones:
    - loading dock
    - high-bay aisles
    - mezzanine with a ramp
    - office block
    - workshop maze
    - forklift lanes with moving forklifts and walkers that have collision bodies
- **Planning resolution:** 0.1 m in the game (480 × 320 cells, close to today's arena at 0.05 m). Research may choose 0.05 m.

**Mini-games.** Every one uses both the wheels and the arm, is scored only on real metrics, and races the planner ghost and the real ROS 2 ghost where one is recorded.

| Game | Milestone | Player does | Score | Teaches |
| --- | --- | --- | --- | --- |
| Fetch Rush | M6 | Fill pick-and-deliver orders for three minutes, driving or dispatching, using Grasp Assist | Deliveries, then time and path efficiency against the ghosts; contacts subtract | Planning, docking, the pick pipeline |
| Rush Hour | M6 | Carry a canister across the forklift lanes, with a chosen driving assist (DWA, pure pursuit, MPPI) or none | Time, minimum clearance, contacts; jerk under the "fragile cargo" rule; the assist used is on the scorecard | Local planners, the local costmap |
| Fog Scout | M7 | The map starts dark (only what COCO's LiDAR has seen); find a requested item in an office and bring it back | Time, map F1, search-decision quality in expectation | Mapping, frontiers, Bayesian search |
| Lost & Found | M7 | COCO wakes up somewhere unknown; localize, then pick up and deliver a parcel | Time to localize, pose error at pickup, delivery time | Localization, kidnapping |

Free roam, the five existing challenges and Race the ghost stay in Play. Progress (best scores, stars) is stored locally.

### 5.10 Research (M5, M7)

- **Recordings library (M5).** Every Case File and later Depot recordings, searchable by level, algorithm and outcome, with failures easy to find.
- **Experiment builder (M7).** Pick a level, arms, parameters, seeds and one primary metric. Saved as a spec with a hash ID.
- **Runner (M7).** Every arm × seed runs in the browser, in background workers if the device allows (measured first).
- **Results (M7):**
    - k/n with Wilson 95% intervals
    - median and IQR with bootstrap intervals
    - paired tests on shared seeds
    - every row opens its replay
- **Reproduce (M7).** Identical numbers from the link, and from `coco run spec.yaml` in Python.
- **Export (M7).** Spec (YAML), results (CSV and JSON), runs (MCAP), and a citation snippet.
- **Run it in ROS 2 (M7).** Download the level's SDF, Nav2 map and params, the spec, and the exact command for a local ROS 2 Jazzy.
- **Connect your ROS 2 (M7).** The browser robot publishes and subscribes ROS-shaped messages through a bridge to the visitor's own local ROS 2 (rosbridge or a Foxglove WebSocket bridge). EXTERNAL evidence class; never connected to COCO's Stack.

### 5.11 Cloud (from M8 only)

Unchanged in content from revision 2:

- CDN first
- then batch Stack runs (API, queue, one fresh container per job, MCAP to object storage, recordings with full 3D pose)
- then gated interactive sessions with the same 3D client

**Rules:**

- no Kubernetes or microservices until there are several worker hosts
- per-container networks and localhost-range ROS 2 discovery
- no user code server-side
- sign-in for Stack compute
- a global daily spend cap

### 5.12 Latency rules

- **Everything in the browser:** every pedagogical interaction and all driving of the Arena model.
- **Control latency:** key press to visible motion within one model tick plus one frame.
- **Stack sessions:** client-side prediction, interpolation, latest-state-wins delivery, and "pause the view, not the robot". Safety stays server-side.
- **Cold start:** the title screen draws first; Pyodide and assets load behind it; returning visitors load from the service-worker cache.

### 5.13 Hardware contract (gated, not built)

A future physical robot is a third backend behind the same gateway and event families, with:

- the HARDWARE class
- a hardware e-stop
- firmware limits
- a supervisor
- a reservation system

---

## 6. Scope fence

**The drift test.** Before any task, the agent names three things:

- the milestone
- the checkpoint
- the exit criterion the task advances

If it cannot name all three, the task is out of scope.

**Non-goals until further notice** (rejected without discussion):

- Vision-language models, LLM planners, natural-language robot commands
- Multi-robot behaviour, multiplayer, accounts, global leaderboards
- RL lessons or policy training, until the robot project shows where learning beats classical control
- A third simulator inside COCO Lab, or a physics engine in the browser
- Switching rendering engines; photoreal or ray-traced rendering; a level editor UI
- Perception on rendered pixels in the browser
- Gamepad, VR or AR
- A physical-robot mode before a robot exists
- Kubernetes, multi-region, microservices
- XP, levels, streaks, loot, or any score that rewards luck
- Package renames or restructures done for aesthetics
- Changes to the COCO robot repo or its worktrees

---

## 7. Roadmap

```
M0 ─▶ M1 ─▶ M2 ─▶ M3 ─▶ M4 (done)
   ─▶ [Gautham: 3-person test + phone measurement]
   ─▶ M5 Focus and polish ─▶ [gate: 5-person test + phone pass] ─▶ public v2.0
   ─▶ M6 COCO Depot: world, Grasp Assist, Fetch Rush, Rush Hour, ROS 2 ghosts ─▶ v2.1 game launch
   ─▶ M7 Fog Scout, Lost & Found, Research mode, Connect your ROS 2
   ─▶ M8 Stack in the cloud: batch and experiments
   ─▶ [gate: cost fits budget AND demand shown] ─▶ M9 Interactive cloud ROS 2 sessions
   ─▶ [gate: a physical robot exists] ─▶ M10 Hardware bridge
```

Effort ranges are rough estimates for part-time, agent-assisted work.

### Completed milestones

Details live in `docs/v2/M*_PROMPT.md`, `docs/v2/M*_RESULTS.md` and `docs/v2/reviews/`.

| Milestone | What it delivered |
| --- | --- |
| M0 Transition | v1 frozen and tagged; baseline; plan installed; honesty fixes; robot-stack packages frozen |
| M1 Glass-box Arena core | `coco_schemas`, World Spec v1, Arena model, planner events, Pyodide worker, renderer, timeline, share links, 4-engine determinism |
| M2 The whole loop | Localise, Map, Move and Decide lenses; teaching controllers; fetch mission; Run 15 in the model; fidelity report; Learn missions; claims check; v1 at `/v1/` |
| M3 Play and Case Files | ROS-to-event adapter; 100 Case Files; mission 7; five challenges; `coco verify`; four modes |
| M4 3D Arena | Asset pipeline (URDF and SDF to glTF); World Spec v2 with elevation; kinematic terrain; 3D renderer, cameras, controls, quality tiers; every lens in 3D; Case Files in 3D; Race the ghost |

### M5 · Focus and polish: the public v2.0 launch (about 4–5 weeks)

**Objective:** turn what exists into a focused, good-looking product with three doors (Play, Compare, Research), fix the known defects, cut the agents' overhead, and launch. No new world and no new mini-games yet.

**Checkpoints:**

1. **M5.0 Setup.** Branch and README install; plan-change log entries for E1–E8; Gautham's test and phone notes read and committed.
2. **M5.1 Defects:**
    - every share-link field bounded and validated (ticks, inputs, size), in the browser and in `coco verify`
    - state hash v2, versioned so v1 links still verify
    - race runs either lock planner, grasp and autonomy, or score as "assisted"
    - Case Files load the low-detail robot first, cached
    - goal picking in the perspective camera tested
    - the "v1 site reproducible" workflow fixed, or documented and disabled
3. **M5.2 Agent overhead.**
    - `AGENTS.md` becomes the canonical agent rules file, about 200 lines or fewer, for Claude Code and Codex alike.
    - `CLAUDE.md` points to it.
    - Robot-stack lore moves to `docs/archive/robot_stack/`.
    - `docs/STATUS.md` keeps current state only (200 lines or fewer), with history moved to `docs/v2/STATUS_HISTORY.md`.
    - `PROJECT_STATE.md` becomes a short pointer page; its old content is archived.
    - RL-era root scripts move under `coco_rl/`, with references updated.
    - The committed `node_modules/` cache is removed and ignored.
    - Nothing is deleted except that cache.
4. **M5.3 Code shape.**
    - The scene core plus three shells.
    - Bundle splitting: three.js in its own chunk; modes lazy-loaded.
    - Behaviour is unchanged, proven by the existing suites.
5. **M5.4 Design system.**
    - Night Shift tokens; dark and light themes; fonts and icons licensed and self-hosted.
    - **Three reference mock screenshots** (title, Play HUD, Compare), committed for Gautham's review. This is a soft gate: carry on, and apply his recorded feedback at the next checkpoint.
6. **M5.5 App shell.**
    - The title screen (attract), the three modes, About and the Settings drawer.
    - Route migration: every old URL form redirects to its new home; Learn missions open as Compare tours; Case Files open in Research; Sandbox opens Play's Free roam; Live is reachable from About.
7. **M5.6 Play.**
    - The full-screen 3D HUD:
        - objective and timer
        - minimap (COCO's own occupancy map)
        - speed, wheel bars and command source
        - action buttons
        - the badge
        - toasts
    - The three-quarter follow camera, dollhouse walls, LiDAR as a scan area, the Robot vision toggle (X).
    - Game cards for the five challenges and Race the ghost; a scorecard; a 10-second instant replay; a first-run tutorial; Free roam.
    - Phone landscape full-screen, and a portrait "rotate" card.
8. **M5.7 Compare.**
    - Panes in one WebGL context.
    - Nav2-style costmap layers with sliders and hover values; the inflation formula tested against Nav2's documented formula.
    - Global planning, local control and localization comparisons; mapping if it fits the time box, otherwise parked in `IDEAS.md`.
    - The difference view, the lockstep timeline and the results strip.
    - Guided tours: missions 1–7 plus the five real-story tours, all passing the claims check.
9. **M5.8 Research, first piece.** The Recordings library replacing the run-link list: search, filters, a failure filter, open in the viewer.
10. **M5.9 Caching and counter.**
    - A service-worker asset cache (content-hashed, versioned, safe to clear).
    - The cookieless aggregate counter, wired but **off** until Gautham adds his counter ID in the site config.
11. **M5.10 Launch preparation** (drafts only):
    - v2.0 release notes, every number traced to `docs/RESULTS.md`
    - a 60–90 s demo script: title → Play → Compare → Research
    - `docs/v2/USABILITY_TEST_M5.md`
    - an updated phone guide
12. **M5.11 Measure and close.** Every budget measured; `docs/v2/M5_RESULTS.md`; a pull request.

**Acceptance criteria:**

| Area | Criterion | Who measures |
| --- | --- | --- |
| Focus | In Play at 1440 × 900 and at 844 × 390 landscape: no page scroll, and at most 8 always-visible on-screen controls (HUD buttons included; keyboard excluded) | Agent |
| Title screen | Visible 3 s or less on emulated 4G (cold) | Agent |
| Cold start | Live model ready 10 s or less, 3D world interactive 12 s or less, on emulated 4G (cold) | Agent |
| Warm start | Live model ready 3 s or less on emulated 4G with the service-worker cache warm | Agent |
| JavaScript | Title-screen JavaScript 350 kB or less gzipped, with three.js in its own chunk | Agent (CI) |
| Frame rate | Play at 60 fps on the RTX 4050 (high tier) and the Intel integrated GPU (medium tier); Compare with 4 panes at 30 fps or more top-down on the integrated GPU | Agent |
| Determinism | Every flat-scene v1 hash and golden trace unchanged; v2 hash defined and tested across all four engines; every committed link verifies under its own hash version | Agent (CI) |
| Defects | Each M5.1 defect has a regression test | Agent (CI) |
| Links | Every old URL form resolves to its new home with 0 console errors; the `/v1/` archive works | Agent (CI) |
| Claims | Every mission, tour and Case File claim resolves to evidence (CI check) | Agent (CI) |
| Agent files | `AGENTS.md` 250 lines or fewer; `docs/STATUS.md` 200 lines or fewer; nothing deleted except the cache | Agent |
| Accessibility | Every control keyboard-reachable; text contrast WCAG AA; computation colours distinguishable under deuteranopia and protanopia simulation; reduced motion honoured | Agent |
| Hygiene | 0 console errors; no WebGL context loss in a 30-minute scripted session | Agent |
| Phone | Play in landscape at 30 fps or more on the automatic tier; first visible computation 10 s or less on mobile data | Gautham |
| Usability | 5 people new to robotics, unaided. At least 4 of 5 each: start a game within 30 s; in Compare, say why A\* expanded fewer cells than Dijkstra; find a recorded ROS 2 run in Research. Median 4/5 or more on "looks good" and on "easy to understand" | Gautham |

**Not in M5:**

- the Depot
- Grasp Assist
- new mini-games
- the experiment builder
- the ROS 2 bridge
- cloud work, accounts
- new algorithms (apart from the costmap inflation layer)

**Stop and escalate if:**

- A v1 hash or golden trace changes.
- An old URL can't be given a new home.
- A claim loses its evidence in the move.
- The Focus criterion can't be met without removing a capability (rather than moving it).

**Launch.** The public v2.0 release and announcement happen after M5 merges and the two Gautham rows pass. Gautham publishes them.

### M6 · COCO Depot: the game world (about 6–7 weeks)

**Objective:** the Depot exists in the browser *and* as a real Gazebo world. COCO can find and pick up objects with one button. Two mini-games (Fetch Rush, Rush Hour) are playable against the planner ghost and a recorded real ROS 2 ghost.

**Contents:**

- World Spec v3 and the modular level kit, with generators for the browser world and glTF, the Gazebo SDF, and the Nav2 map and params.
- The Depot level (about 48 × 32 m, six zones) and its zone streaming.
- The object catalog with grasp affordances; moving forklifts and walkers with collision bodies in both tiers.
- Grasp Assist (section 5.8) and `manip.grasp` events.
- The ROS-shaped message model and the ROS graph panel.
- Fetch Rush and Rush Hour, with scoring, stars from reference results, reproducible links and `coco verify` support.
- On the laptop, respecting batch windows:
    - each generated world launched in Gazebo with Nav2
    - a planning smoke test
    - recorded real ROS 2 runs of each game objective (Nav2 + MoveIt), converted into ghosts and Research recordings
- Deterministic sessions for the Depot and both games.
- v2.1 release notes and demo (drafts).

**Acceptance (summary):**

| Area | Criterion | Who measures |
| --- | --- | --- |
| Download | Depot first scene 5 MB or less compressed | Agent |
| Frame rate | 60 fps on the RTX 4050, 60 on the integrated GPU at medium | Agent |
| Planning | Depot planning time at 0.1 m measured; any planner over its budget goes through the WebAssembly gate | Agent |
| Gazebo | Every generated world launches in Gazebo and Nav2 plans on its map (STACK evidence) | Agent |
| Ghosts | A recorded ROS 2 ghost exists for each Fetch Rush and Rush Hour level | Agent |
| Grasp Assist | Gives a reason for every refusal, and its picks pass the Stack's proximity gate | Agent |
| Reproducibility | Game links reproduce in all four engines and in `coco verify` | Agent (CI) |
| People | Phone and 5-person usability: start and finish a Fetch Rush run unaided; "fun" median 4/5 or more | Gautham |

### M7 · Two more games, and Research (about 5–6 weeks)

**Objective:** complete the game with Fog Scout and Lost & Found, and make Research a real tool.

**Contents:**

- Fog Scout and Lost & Found
- the experiment builder, runner and statistics
- exports and "Run it in ROS 2"
- `coco run` parity
- the "Connect your ROS 2" bridge (EXTERNAL class; tested against a local ROS 2 Jazzy with rosbridge or a Foxglove bridge)
- mapping in Compare, if it was parked in M5

**Acceptance (summary):**

| Area | Criterion |
| --- | --- |
| Experiments | A 30-seed, two-arm experiment runs in the browser and gives identical numbers to `coco run` |
| Exports | Load in Python and Foxglove |
| ROS 2 bundle | A level's ROS 2 bundle launches in Gazebo and Nav2 on the laptop |
| Bridge | Drives the browser robot from a local ROS 2 node with STOP precedence intact |
| Games | Both new games have reproducible links and ghosts |
| People | Usability for one Research task and both games |

### M8 · Stack in the cloud: batch and experiments (about 4–6 weeks)

**Built:**

- a pinned headless Stack image
- worker and queue
- an API with sign-in and quotas
- object storage
- Research specs run on real ROS 2
- a global spend cap

**Measured:** real-time factor, start-up time, CPU against GPU, cost per run.

### M9 · Interactive cloud ROS 2 sessions (gated, about 4–6 weeks)

**Gate:** M8's cost fits the budget (G4), and demand is shown.

**Built:** session manager, gateway, the additive `coco.v1` event channel, the 3D client with prediction. Remote STOP, preemption, spectators, caps and disconnect are measured.

**Then:** the public Live tab retires.

### M10 · Hardware bridge (gated)

Gated on:

- a physical robot existing (G5)
- the robot project's sim-to-real gate
- M9's remote-safety measurements

---

## 8. Decisions

### Recorded decisions

| ID | Date | Decision |
| --- | --- | --- |
| D1 | 11 Oct | 3D is the default experience; top-down is a camera mode and the automatic fallback |
| D2 | 11 Oct | The 3D Arena came before cloud work (done as M4) |
| D3 | 11 Oct | The first 3D world is COCO's Gazebo arena converted from its SDF (extended by E2) |
| D4 | 11 Oct | No physics engine in the browser |
| D5 | 11 Oct | M3 merged quietly; one consolidated usability test replaces the M1–M3 tests |
| D6 | 11 Oct | Case File scans load after the first frame; one preferences module |
| E1 | 14 Oct | Three modes (Play, Compare, Research), the title screen and About replace Learn, Play, Sandbox and Case Files |
| E2 | 14 Oct | COCO Depot from World Spec v3; every world compiles to browser, Gazebo SDF and Nav2 map; the arena stays as the Proving Ground |
| E3 | 14 Oct | "ROS 2 at its core": a ROS-shaped model and graph panel, real Gazebo worlds, real ROS 2 ghosts; the "Connect your ROS 2" bridge in M7, with invariant 2 narrowed to the control boundary |
| E4 | 14 Oct | Grasp Assist is a glass-box, MoveIt-style pipeline in the model, badged as such |
| E5 | 14 Oct | Public v2.0 after M5; the Depot games launch as v2.1 |
| E6 | 14 Oct | A service-worker cache for static assets is allowed |
| E7 | 14 Oct | One cookieless, aggregate-only visit counter is allowed, off until Gautham configures it |
| E8 | 14 Oct | Slim and archive the agent files; `AGENTS.md` becomes canonical; nothing deleted |

### Pending decisions, and the defaults agents use until Gautham decides

| ID | Decision | Default until decided |
| --- | --- | --- |
| G1 | Primary audience | Learners first; everyone for the game |
| G2 | Priority against the robot project and job hunt | Not an agent decision; agents respect announced robot batch windows |
| G3 | Canonical robot stack | The robot repo is canonical; `coco-labs` robot packages are frozen, not deleted |
| G4 | Monthly cloud budget | Zero; no cloud resources before M8 and an explicit budget |
| G5 | Will a physical robot exist within a year? | Assume no; no "real robot" wording anywhere |
| G6 | License and outside contributions | Unchanged from the current repo |

---

## 9. Rules for coding agents

These apply to every agent: Claude Code, Codex or any other.

1. **One prompt per milestone.** Work through every checkpoint without pausing, unless a stop condition fires. Commit at every checkpoint, so any session can resume from `docs/STATUS.md`.
2. **Read first:** `README.md`, `AGENTS.md` (or `CLAUDE.md` until M5.2 creates `AGENTS.md`), `docs/STATUS.md`.
3. **Apply the drift test** before each task. Anything outside the checkpoint list goes to `docs/IDEAS.md`, never into code.
4. **Branch and commits.**
    - Branch `v2/<milestone>` (for example `v2/m5-focus`).
    - Commits are prefixed with the checkpoint, for example `[M5.3]`.
    - `docs/STATUS.md` is updated at every checkpoint, in its short form: current state and next step. History is appended to `docs/v2/STATUS_HISTORY.md`.
5. **Testing.** Focused tests during work; the full suites (package tests, `lab_web` vitest, build-tool tests) at each checkpoint's end.
6. **Resources and measurement.**
    - Hardware: RTX 4050 laptop GPU (6 GB VRAM), Intel integrated GPU, 16 GB RAM, Ubuntu 24.04, ROS 2 Jazzy.
    - Never two simulators at once. Respect robot batch windows.
    - Measure on the balanced power profile, on AC. Switch the profile if needed and restore it.
    - Record power state and GPU driver version.
    - Emulated results are labelled "emulated", never "phone".
7. **Sandboxed agents.** An agent without access to the laptop's GPU, `~/coco_lab_runs/`, Gazebo or the network records the affected measurements as *pending, needs the laptop*. It never estimates them.
8. **Visual review.** Agents cannot judge looks reliably; screenshot tests catch regressions only.
    - At each checkpoint that changes the look, commit screenshots to `docs/v2/data/<milestone>/screens/` and list them in `STATUS.md`.
    - Carry on without waiting, and apply Gautham's recorded feedback at the next checkpoint.
9. **Never:**
    - delete evidence, tags or releases
    - create or edit releases
    - run destructive git commands without approval
    - touch the robot repo
    - invent numbers
    - mark anything MEASURED without committed data
    - mark a Gautham-owned row as done
    - merge a milestone pull request without Gautham's explicit permission
10. **Final report**, in this form:

```
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (device or emulation, power profile, driver, conditions):
Acceptance criteria: each → met / not met / pending Gautham / pending laptop, with evidence:
Screenshots awaiting Gautham's review:
Files moved or removed (full list) and why:
Decisions recorded (ADRs) and plan-change log entries:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```

11. **Independent review.** A milestone closes in `STATUS.md` only after a fresh review session, given only the repo, this README and the report, has verified that:
    - the commits exist
    - a sample of the tests pass
    - every evidence file named in the report exists and supports its claim

---

## 10. Where things live

| File | Role |
| --- | --- |
| `README.md` | This plan: the authority |
| `AGENTS.md` | Canonical rules for every coding agent (from M5.2) |
| `CLAUDE.md` | Points to `AGENTS.md` (from M5.2) |
| `docs/STATUS.md` | Current position, open questions, plan-change log (short) |
| `docs/v2/STATUS_HISTORY.md` | Checkpoint history (append-only) |
| `docs/IDEAS.md` | Parked ideas |
| `docs/ROADMAP.md` | Pointer to section 7, plus the v1 history |
| `docs/RESULTS.md` | Every measured number, append-only |
| `docs/v2/` | Prompts, results, reviews, ADRs, schemas, fidelity reports, asset manifest, usability notes |
| `docs/archive/` | Archived v1 docs and the robot-stack record |
| `PROJECT_STATE.md` | Short pointer to the current state (from M5.2) |
| `~/coco_lab_runs/` | Raw evidence recordings (outside git; never delete) |
