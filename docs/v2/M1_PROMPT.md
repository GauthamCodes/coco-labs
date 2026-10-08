<!-- Part B of the owner's prompt "COCO Lab: close M0 (review fixes + merge), then Milestone M1", issued 2026-10-08, saved verbatim (B.0) so later sessions can re-read it. Resume a later session with: "Continue COCO Lab M1. Read README.md, docs/STATUS.md and docs/v2/M1_PROMPT.md in ~/coco_labs_ws/src/coco-labs, then carry on from the next step recorded in STATUS.md." Section 0 of that prompt (authority and one-off permissions) is recorded in docs/STATUS.md's plan-change log. -->

# PART B — Milestone M1 · Glass-box Arena core

**The M1 goal:** a stranger opens one URL on a phone, clicks a goal, watches COCO's planner compute visibly as the robot drives, and sees the end-of-run heatmap. All of it is deterministic, measured, and on the new engine.

Read README sections 3, 5, 7 (M1) and 9. Save Part B of this prompt into the repo as `docs/v2/M1_PROMPT.md` so later sessions can re-read it.

## B.1 Canonical checkout and preflight

1. In `~/coco_labs_ws/src/coco-labs`:
    1. Run `git status` and `git log --oneline -5`. Confirm `origin` is `GauthamCodes/coco-labs`.
    2. Check for local commits that aren't on any remote branch: `git log --branches --not --remotes`.
    3. **If it is clean with no unique local commits:** `git fetch origin`, check out `main`, and fast-forward it to `origin/main` (`git merge --ff-only origin/main`).
    4. **If it has uncommitted changes or unique local commits:** do not touch it. Stop and ask Gautham.
2. Confirm `main` contains the PR #19 merge and the tag `coco-lab-v1-final`.
3. Write `docs/v2/CHECKOUTS.md`:
    - this checkout is canonical
    - `~/ros2_ws(personal)` is legacy, holds Labs 2–5 history, and is not used for COCO Lab
    - why
4. Create branch `v2/m1-arena-core`.
5. Rebuild the colcon overlay so this tree is the one that gets built.
6. Pin the toolchain: Node 24 via `.nvmrc` (reuse `~/coco_v2_ws` if needed), the Python venv, and the Pyodide version. Record the versions in `STATUS.md`.
7. Run the three suites once as the M1 baseline.

## B.2 Known facts that shape M1

From the M0 baseline (laptop, n = 5, Chromium), independently re-verified:

| Measurement | Value |
| --- | --- |
| Pyodide cold first edit | Median 12.9 s (range 6.6–42.9 s), dominated by the CDN download |
| Warm edit | Median 1.4 s |
| `dist/` size | 23.0 MB |
| Pyodide from the CDN | 6.4 MB in 6 requests |

**This already misses M1's cold-start target (10 s on a phone over mobile data) before any new work.** Cold start is a first-class M1 workstream, not polish. Expected tools:

- self-host only the Pyodide files and packages actually needed, served from the same origin
- start loading during attract mode
- attract mode plays a precomputed recording, so the user sees motion and computation before Pyodide is ready
- find out why `dist/` is 23 MB and cut what the Arena doesn't need

Measure before and after every change. Do not claim an improvement without numbers.

## B.3 Checkpoints

Prefix commits `[M1.x]`. Update `docs/STATUS.md` at the end of every checkpoint with:

- what was done
- the evidence file
- the exact next step

Continue between checkpoints without asking, unless a stop condition fires.

1. **M1.1 `coco_schemas`.** A new top-level package.
    - Define the envelope (manifest: `run_id` = hash of canonical spec + seed + engine versions; spec; tier; evidence class; library and engine SHAs; schema list; provenance).
    - Define these families: `world`, `robot`, `truth`, `sensor.scan`, `plan.search`, `plan.incremental`, `input`, `metrics`, `annotation`.
    - Naming is `coco.<family>.<name>.v<major>`, and every event carries `t_world`, `tick` and `seq`.
    - Protobuf is the storage schema. Generate Python and TypeScript (prefer `@bufbuild/protobuf` for TypeScript). CI checks that generated code is current and that changes within a major version are compatible.
    - **First, settle how events cross from Python in Pyodide to JavaScript.**
        - Check whether the protobuf runtime exists and is fast in Pyodide.
        - If it isn't, Python emits columnar typed-array batches that TypeScript encodes for storage.
        - Measure both if both are possible, and record the choice in `docs/v2/adr/0001-event-transport.md`.
    - Container: MCAP with zstd. Write a `docs/v2/SCHEMAS.md` reference.
2. **M1.2 World Spec v1.**
    - A versioned YAML schema plus `worlds/coco_arena_v1.yaml`, made from the existing arena geometry and `coco_config` robot parameters (cite the source files).
    - A generator for the Arena model.
    - Gazebo SDF generation is designed for in the schema but not built.
3. **M1.3 Arena model core**, in `coco_lab` (no `rclpy`):
    - fixed-step differential-drive kinematics
    - 2D LiDAR reusing the Sketch ray-caster
    - seeded in-library RNG
    - goals and teleop arrive as `input` events
    - a per-tick state hash over a canonical, quantized byte layout (document the method)

    Then re-run the Sketch-vs-Gazebo LiDAR comparison on the existing 237 recorded poses. The 86.7%-within-5 cm figure must hold or the difference must be explained. Append the result to `docs/RESULTS.md`.
4. **M1.4 Planners emit events.**
    - BFS, Dijkstra, A\*, greedy and weighted A\* stream `plan.search` events through a generator API (D\* Lite with `plan.incremental` is optional).
    - **Golden traces:** on the existing 1,000-map property corpus, the new events must give the same expansion order, the same costs and the same paths as the Lab 1 traces. CI runs this.
5. **M1.5 Worker runtime.**
    - Pyodide plus `coco_lab` in a Web Worker, streaming event batches as transferable buffers.
    - Do the cold-start work from B.2 here.
    - Add a `?perf` overlay showing fps, load timings and event throughput, so Gautham can measure on his phone.
6. **M1.6 Renderer.**
    - Three.js on WebGL 2, orthographic 2.5D camera, pan and zoom (touch included).
    - Layers: occupancy, frontier, closed set, expansion heatmap, path, LiDAR fan, robot, footprint, truth outline.
    - Use instancing, merged line buffers and data textures. Picking opens an inspector showing g, h, f, parent and expansion order.
    - Add a visual design system v1 in `docs/v2/VISUAL_SYSTEM.md`: fixed colour per layer, truth always drawn as an outline, light and dark themes. Use the frontend-design guidance if available.
    - The renderer lives beside React. React draws panels only.
    - Load the robot sprite or mesh from existing assets. Converting Gazebo meshes to glTF is optional in M1.
7. **M1.7 Timeline.**
    - A world track (ticks) and a computation track (`seq` within the selected tick).
    - Play, pause, step, speed, scrub.
    - Keyframes for seeking.
8. **M1.8 Experience**, as a new view `?view=arena`:
    - attract mode
    - give-a-goal by click or tap
    - keyboard and on-screen-joystick teleop
    - planner choice
    - side-by-side compare of two planners on the same start, goal and seed
    - end-of-run heatmap with the totals (expansions, path cost, path length)
    - a share link carrying spec hash, seed and input log, which reproduces the run exactly
    - an always-visible MODEL evidence badge

    Keep the old views working. Make `?view=arena` the default landing page **only after** every agent-measurable acceptance criterion passes. Keep a visible link to the v1 labs.
9. **M1.9 Converters.** Lab 1 bundles and its three recorded full-stack replays play in the new viewer, labelled STACK. The old Lab 1 view stays.
10. **M1.10 Measure and decide.**
    - Measure every budget in B.4.
    - Write the WebAssembly gate decision in `docs/v2/adr/0002-wasm-gate.md`. **Port nothing unless a budget fails, and then only the failing kernel, under trace-equivalence tests.**
    - Write `docs/v2/M1_RESULTS.md` and append all numbers to `docs/RESULTS.md`, each with evidence class, device and conditions.
    - Prepare two things for Gautham:
        - `docs/v2/USABILITY_TEST.md`: a 2-minute script for 5 people new to robotics, plus a results table
        - the phone measurement steps using `?perf`

## B.4 Acceptance criteria

| Area | Criterion | Who measures |
| --- | --- | --- |
| Determinism | Identical per-tick hashes across Chromium, Firefox and WebKit (Playwright) and Pyodide-in-Node, over 100 recorded sessions with random goals and teleop | Agent |
| Correctness | Golden traces match Lab 1 on all 1,000 corpus maps | Agent (CI) |
| Laptop performance | 60 fps with about 50,000 points, 20,000 segments and one grid texture on screen | Agent |
| Responsiveness | First frontier node visible within 100 ms of a goal click (warm); seek under 100 ms | Agent |
| Laptop cold start | Median and range, n ≥ 10, against the M0 baseline; target under 10 s | Agent |
| Phone performance | 30 fps or better at default detail | Gautham, using `?perf` |
| Phone cold start | First visible computation within 10 s on mobile data | Gautham |
| Usability | 5 people new to robotics set a goal and explain the heatmap within 2 minutes, unaided | Gautham |
| Hygiene | 0 console errors in every view; phone-width layout checked; schema, golden-trace, determinism and screenshot tests in CI; existing suites still pass | Agent |

The agent closes every criterion it can measure. The three marked Gautham stay listed as *pending Gautham* in `STATUS.md`. Never mark them done yourself.

## B.5 Scope fence for M1

**Not in M1:**

- localization, mapping, local control or search lenses (those are M2)
- new algorithms
- the cloud, accounts, a ROS-to-event adapter
- leaderboards, challenges
- the 3D arm
- WebGPU
- any WebAssembly port without a failed budget
- multi-robot, RL, VLM
- changes to the frozen robot-stack packages or the robot repo

**Anything else worth doing** goes to `docs/IDEAS.md` as one line.

**Git:**

- Work only on `v2/m1-arena-core`. Push it regularly.
- Open a pull request into `main` when all agent-measurable criteria pass. **Do not merge it.** The section 0 merge permission covers PR #19 only.
- Do not deploy Pages or edit releases.

## B.6 Stop and ask Gautham if

- The phone cannot plausibly reach 15 fps at minimum detail: an early WebAssembly decision is needed.
- Cross-browser hashes differ and the cause isn't found within one checkpoint.
- The schemas cannot express an existing Lab 1 trace without loss.
- Cold start cannot get under 10 s on the laptop with self-hosted assets.
- Any step would require deleting evidence, a release or a working public view.

## Final report (end of every session)

Fill in this report and update `docs/STATUS.md` to match:

```
Part A (first session only): each fix → done / not done | evidence file | PR #19 merge SHA | public-site check result
Release texts edited: tag → before/after files
Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements taken (with device and conditions), against the M0 baseline:
Acceptance criteria: each → met / not met / pending Gautham, with evidence:
Files removed (full list) and why:
Decisions recorded (ADRs):
Plan-change log entries added:
Deviations from the plan, and why:
Ideas parked in docs/IDEAS.md:
Stop condition hit? which one:
Questions for Gautham:
Next step according to README.md:
```
