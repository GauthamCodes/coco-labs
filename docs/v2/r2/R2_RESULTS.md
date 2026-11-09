# R2 · Bring Your Own Algorithm — results

Prompt: [`R2_PROMPT.md`](R2_PROMPT.md). Progress log: [`R2_STATUS.md`](R2_STATUS.md). Branch `v2/r2-byoa` from main
`4894c76` (R1 merged); worktree `~/coco_labs_ws/worktrees/r2`. Evidence per checkpoint in [`data/`](data/).
Evidence classes as in AGENTS.md: **MODEL** (COCO Lab's Python reference, natively or in the browser), **STACK**
(full ROS 2 in Gazebo; simulation, never hardware), TESTED, MEASURED, INFERENCE, UNRESOLVED.

## Checkpoints done

| Checkpoint | Result | Evidence |
| --- | --- | --- |
| R2.0 Baseline | main's tree = R1's final tree byte for byte; R1.9's results are the baseline | [`data/r20/`](data/r20/README.md) |
| R2.1 API and security design | `coco_lab.api` (`coco.algorithm.v1`), the guard, built-ins wrapped; ADR 0012, ADR 0013 | [`data/r21/`](data/r21/README.md) |
| R2.2 Sandboxed worker | user code only in its own locked-down Pyodide worker; escape tests pass in 3 browsers | [`data/r22/`](data/r22/README.md) |
| R2.3 Algorithm Studio | editor, templates, runs drawn as they think, Compare, validation, ROS 2 export | [`data/r23/`](data/r23/README.md) |
| R2.4 Compare, experiments, native | `coco experiment run --algorithm`; "Benchmark it"; parity in CI | [`data/r24/`](data/r24/README.md) |
| R2.5 Share links | code links with explicit "Run this code"; .py download/upload | [`data/r25/`](data/r25/README.md) |
| R2.6 Leaderboard | sandboxed verifier + trusted writer; Gautham's submission PR #31 verified in CI | [`data/r26/`](data/r26/README.md) |
| R2.7 Run in ROS 2 | package exporter; planner, controller and localiser validated in Gazebo + Nav2 | [`data/r27/`](data/r27/README.md) |
| R2.8 Phone and Learn | emulated phone pass; "Try it yourself" on Learn; [`API.md`](API.md) | [`data/r28/`](data/r28/README.md) |
| R2.9 Close | every suite, determinism v1/v2/v3, reference sample, security tests, fps, screenshots | [`data/r29/`](data/r29/README.md), [`BEFORE_AFTER.md`](BEFORE_AFTER.md) |

## API — MODEL / TESTED

Three contracts in ROS 2 message shapes ([ADR 0013](../adr/0013-algorithm-api-v1.md), [`API.md`](API.md)):
`plan(costmap: Costmap, start: Pose2D, goal: Pose2D, ctx) -> list[Pose2D] | None` (the costmap is
`nav2_msgs/Costmap`, raw costs 0–255); `control(state: RobotState, scan: LaserScan, path, ctx) -> Twist`;
`localise(odom: Odometry, scan: LaserScan, map: OccupancyGrid, ctx) -> PoseWithCovariance`. `ctx`: a seeded RNG, the robot (from the World Spec), params,
the time budget, `ctx.emit` thinking events (expand, push, frontier, path, candidate, lookahead, particles, estimate,
marker, note). Every output validated (contract errors end the run with a named status; Twist clamped and logged,
never silently).

**Built-ins wrapped byte-identical?** Yes, with one bounded, recorded exception:
- BFS, Dijkstra, A*, greedy, weighted A*, DWA, RPP, MPPI, MCL, MCL + injection, EKF through the API: **identical**
  (status, every metric, expansions in order, paths cell for cell, every tick's truth pose) ([`data/r21/`](data/r21/README.md)).
- **D\* Lite**: identical except path length and cost, ≤ 3 × 10⁻¹⁵ relative — its native adapter sums with Python
  3.12's compensated `sum()`. No native result, hash or golden changed (question 1 below).
  **Resolved 2026-11-06:** the measurement now adds in each built-in's native order; D\* Lite is
  identical too (see "Gautham's answers" below).
- The 10% sample of the 1,970 COCO-Bench v0 reference runs re-run with the final code: **197/197 match**; every
  v1/v2/v3 golden unchanged; native gate exact.

## Security — TESTED

**Escape tests** (`lab_web/tools/r2/escape_check.mjs`, the built site, final tree) — **pass in Chromium, Firefox and
WebKit**: 19/19 hostile files failed safely, 68/68 lockdown probes blocked, 0 external requests:

| Hostile file | Result (each browser) |
| --- | --- |
| network: `import js` + fetch · `pyodide.http` · `urllib` | refused by the guard (imports outside the allow-list) |
| escape: object graph to `sys` (`__subclasses__`) · `__import__("js")` · `import js` · `pyodide.ffi` · generator frame (`gi_frame`, `f_globals`) | refused by the guard |
| escape: `getattr` with a dunder name | error at run time (guarded `getattr`) |
| DOM: `document` · `js.document` | error (no such name) · refused by the guard |
| storage: open a file | error (`open` is not a builtin) |
| infinite loop in a controller | stopped: time_limit (worker terminated and rebooted) |
| memory: one huge allocation · a huge list · a growing list | error: the 1 GiB WebAssembly growth ceiling |
| huge output: print · events · path | console capped · events capped (or time limit) · invalid_output |

The lockdown's probes (fetch, XHR, WebSocket, WebTransport, workers, BroadcastChannel, IndexedDB, caches, storage
managers, devices, `navigator.*`, `eval`, `Function`, `import()` of remote and `data:` code): all blocked. The page
CSP is a `<meta>` (GitHub Pages sends no headers); the worker starts from `blob:` so it inherits it.

**CI sandbox** (`.github/workflows/leaderboard-verify.yml`): `pull_request` only (never `pull_request_target`),
`permissions: contents: read`, no secrets; the **base branch's** verifier and coco_lab judge the PR; a PR touching
anything but its submission files is refused; `docker run --network none --read-only --cap-drop ALL
--security-opt no-new-privileges --user 65534 --cpus 2 --memory 4g --pids-limit 256`, 140 min timeout. Results are
written only by `leaderboard-results.yml` (`workflow_run`, default branch), which validates the artifact as data,
re-checks the PR's head and files through the API, and regenerates the comment from the numbers (mentions, links,
markup made inert). Probe of the container: no route out (ENETUNREACH), no DNS, uid 65534, read-only image.

**ADR 0012** ([link](../adr/0012-running-strangers-code.md)) in brief: the guard runs everywhere but is not a boundary
on its own (CPython was never built to contain hostile code); the boundary is named per place — in the browser the
dedicated, locked-down worker (no network, DOM or storage; time and memory limits; CSP; nothing runs from a link
without consent); in CI the network-less, unprivileged, read-only container with no secrets and a separate trusted
writer; on a researcher's own machine (native CLI, ROS 2 package) it is their code on their machine, and the guard is
for portability and honest measurement. Determinism is checked (every run twice, hash chains compared) and
non-deterministic code is labelled and cannot be submitted.

## Studio — TESTED

- **Templates** (9): planners `planner_astar`, `planner_greedy`, `planner_empty`; controllers `controller_pure_pursuit`,
  `controller_empty`; localisers `localiser_particle_filter`, `localiser_empty`; teaching `teach_heuristic` (write A*'s
  heuristic), `teach_tune_dwa` (tune DWA's critics).
- **Thinking visualised**, in GAME and SIM, as it streams: expansions and pushes, the frontier, candidate trajectories
  and the lookahead, the particle cloud and the estimate, markers; truth and belief; MODEL · kinematic on every view.
- **Determinism check**: each run twice, hash chains compared, shown in Results and Validation; the A* starter on
  depot-nav-100 s001: found, 3,059 expansions, identical chains.
- **Validation**: contract problems, clamped outputs, per-call time with the device, dropped events; tracebacks
  mapped to editor lines; console capped.
- **Phone usability** (emulated only): the page states that the editor is basic on a phone (read, run and compare
  fully; upload a .py for long edits); Run reachable (48 px), no sideways scroll, the A* starter runs. Real phone not
  connected.

## Parity — browser vs native, per template (MODEL)

`lab_web/tools/r2/parity.mjs` (CI step in `lab.yml`), CPython vs Pyodide, final tree: **850 values, 0 differences**.

| Template | Runs | Differences | Non-deterministic |
| --- | --- | --- | --- |
| planner_astar | 8 | 0 | 0 |
| planner_greedy | 8 | 0 | 0 |
| planner_empty | 6 | 0 | 0 |
| teach_heuristic | 6 | 0 | 0 |
| controller_pure_pursuit | 4 | 0 | 0 |
| controller_empty | 4 | 0 | 0 |
| teach_tune_dwa | 2 | 0 | 0 |
| localiser_particle_filter | 2 | 0 | 0 |
| localiser_empty | 2 | 0 | 0 |

## Leaderboard — MODEL / TESTED

- **Suites/boards**: arena-nav-50, depot-nav-100, depot-narrow-30 (planning; one board per suite and family).
  **Entries**: 18 reference entries (the six built-in planners × three suites). Controller and localiser reference
  entries were **not generated** (MPPI and MCL take hours per board here); those boards rank submissions only until
  they are.
- **Held-out scheme**: each suite's own generator, seed `sha256(salt | suite | merge-base)`. **Stated limitation**
  (CONTRIBUTING, ADR 0012): the salt is committed — no secret is possible in a fork-safe `pull_request` job — so anyone
  who knows a PR's merge-base can compute its held-out set; it catches overfitting by habit or chance, not a
  determined cheat. Review and the no-hard-coding rule cover the rest.
- **Gautham's submission**: [PR #31](https://github.com/GauthamCodes/coco-labs/pull/31), Lazy Theta* on
  depot-nav-100 (into `v2/r2-byoa`, three files only). **Verified in CI** (sandboxed run
  [41905826181](https://github.com/GauthamCodes/coco-labs/actions/runs/41905826181)): public 100/100 (Wilson 95%
  0.963–1.000), path 0.978 × grid-optimal, held-out 20/20, deterministic, claim matches; public results byte-identical
  natively, in the laptop's container and in CI. The `verified` label and the committed result come from the trusted
  writer, which runs only from main — once R2 is merged (then re-run #31's checks, retargeted to main).

## Run in ROS 2 — STACK (Gazebo Harmonic + Nav2 Jazzy, simulation; no physical robot)

Exported with "Export ROS 2" / `python -m coco_lab.ros2_export`: an `ament_python` package `coco_user_<name>` with the
file unchanged and the same guard. **No change to COCO's robot repository** (the bring-up is this repository's
`gazebo_models` and `custom_teleop`). 29 fresh headless sessions, one at a time, never `--fast`
([`data/r27/`](data/r27/README.md)):

| Component | STACK success | vs stock Nav2 | MODEL vs STACK |
| --- | --- | --- | --- |
| A* starter as the planner (ComputePathToPose), 20 depot-nav-100 scenarios × 3 sessions | **60/60** plans; drives 4/5 | stock Smac 42/60 (the same 6 every session: Nav2 refuses a start/goal in inflated cost, COCO Lab snaps them — a convention, not a better planner); +0.551 m paired; drives 3/5 | MODEL 20/20; path +0.232 m (+0.8 %) paired median |
| Lazy Theta* as the planner | **57/60** plans (3 = session 1's 120 s wait; 20/20 in the others and on balanced); **drives 0/5** with Nav2's RPP (104 FollowPath; RPP's "collision ahead" — its paths hug corners; mechanism INFERENCE) | −0.742 m paired (shorter) | MODEL 20/20; path −0.086 m paired |
| pure-pursuit starter as the controller (FollowPath, through `cmd_vel_arbiter`) | **20/20** colour rounds, 40/40 legs; `controller_server` got no goals | — | time per leg +0.145 s paired median (n=8 legs) |
| particle-filter starter in place of AMCL | 2/2 legs (one round: a smoke run, not a rate) | — | error at leg ends 0.063 / 0.258 m (MODEL 0.097 / 0.110 m) |

All sessions ran on the power-saver profile (a deviation, found afterwards); a balanced re-run of the planning
comparison and the Theta* drive gave **the same counts and path lengths**, planning 2.4–3× faster in wall time. The
"Browser vs ROS 2" panel shows these rows beside the exact file (keyed by sha256), negative results included.

## Tests and determinism

| Suite | R1.9 baseline | R2 final |
| --- | --- | --- |
| coco_lab (installed, plain venv) | 1192 | **1303 passed** |
| coco_lab gz | 2 | 2 |
| lab_web/tools pytest | 248 | **263** |
| vitest | 631 (83 files) | **640 (84 files)** |
| ROS packages (12) | all pass | **all pass** (coco_lab 1308 with lint) |
| native gate (hash v3) | exact | **exact** (818,951 + 1,436 values) |
| determinism v1 / terrain / v2 (4 engines) | 0 diff | **0 diff** (1,500 / 2,100 / 1,500 ticks each; same chains as R1.9) |
| R1 parity / R2 parity | 4,269 / — | **4,269 / 850, 0 diff** |
| R1 reference sample | 197/197 | **197/197** |
| link e2e ×4, Compare, export = native, coco verify 18/18, build twice, update isolation, v1 links, replays, screenshots, chase HUD, saved view | pass | **pass** |
| accessibility | 16 pages | **24 pages** (+ Studio, Leaderboard), 0 failures |
| escape tests | — | **pass × 3 browsers** |

The close-out found and fixed five defects (evidence kept in [`data/r29/failures/`](data/r29/failures/)): R2's
tests lacked a `COCO_WORLDS` fixture (29 failures against an installed coco_lab, as CI runs it); a test required PR
#31's files; the Studio's light-theme syntax colours (92 contrast failures); ament lint on `ros2_export.py` and the
starter files (R2.7); and — found by the R2 PR's own CI — `check_dist.mjs` failing on external URLs. That last one
was **already failing on main since the R1 merge** (`4894c76`: the Datasets tab's hyperlinks and its Colab link; main's
lab run 41897972116, "Build twice") and R2 added one (the lockdown's `https://example.invalid/x.mjs` probe). The
local suites runner piped `check_dist` into `tail`, which hid its exit code, so "build twice: pass" above did not
include it. Fixed: the three are hyperlinks or a probe, never fetched, and are allow-listed narrowly with reasons;
the runner uses `pipefail`; build twice + `check_dist` re-run: identical trees, 0 failures.

## Performance — MEASURED (balanced, AC; RTX 4050, i5-13420H)

| | Baseline (main) | R2 final |
| --- | --- | --- |
| Play fps, desktop high (median / min) | 60.05 / 59.18 | **60.10 / 59.17** |
| Play fps, **emulated** phone medium | 59.99 / 56.29 | **60.01 / 56.48** |
| frames over 50 ms | 0 / 0 | 0 / 0 |

**Play's frame rate is unchanged.** Studio (wall time, named device): one A* starter run 5.7 s incl. the sandbox's
first boot (planning call 1.71 s); "Benchmark it" (starter + built-in A*, all 50 arena-nav-50 scenarios, 100 runs,
each of the starter's twice) **29.1 s** on the laptop (4 sandboxes), 95.9 s on the **emulated** phone (1 sandbox).
Real phone: **not measured — not connected**.

## Screenshots

[`BEFORE_AFTER.md`](BEFORE_AFTER.md): before = R1.9's after set; after = [`screens/r29/`](screens/r29/) (desktop and
both emulated phone orientations). Visual review is Gautham's.

## Stop conditions

None fired. No built-in result or hash changed through the API (D\* Lite's last-ulp summation difference exists only
through the API's measurement, recorded; native unchanged). No escape test succeeded. The verifier needs neither
secrets nor `pull_request_target`. Gazebo + Nav2 ran every user node without changing COCO's robot repository.
Play's frame rate did not get worse.

## Deviations

- R2.7's Gazebo sessions ran on **power-saver** (the laptop's setting; the prompt asks for balanced): found in
  `meta.json` afterwards; the planning comparison and the Theta* drive were re-run on balanced — same counts and
  lengths; the balanced planning times are the ones quoted.
- R2.8 was committed before R2.7 (R2.7's Gazebo runs took hours).
- The close-out ran three times (attempt 1 stopped on the fixture defect; attempt 2's three fixes re-checked on the
  final tree); the laptop suspended for 30 h mid-run (lid closed) and resumed; no measurement ran on battery.
- One tool file was briefly written into the tree during attempt 1's first suite (about a minute, while only the
  installed-copy coco_lab suite ran) and moved out at once; that run was then abandoned anyway.
- "Run in Live ROS 2" (Docker) stays R5; only the export is built here, as the plan says.

## Questions for Gautham

1. **D\* Lite through the API**: accept the ≤ 3e-15 summation difference as recorded; make the API's measurement
   compensated (then the five search planners differ by an ulp); or give D\* Lite's adapter sequential addition under
   a new experiment version?
2. **PR #31**: after R2 merges, retarget it to main and re-run its checks so the trusted writer labels it and commits
   its result. Merge is yours.
3. **Theta\* drives 0/5 under Nav2's RPP**: keep this as the visible negative STACK row (current), or also validate
   it with a controller tolerant of corner-hugging plans? (The leaderboard ranks MODEL; STACK is shown, not ranked.)
4. **Stock Nav2's start/goal convention**: the 205/208 failures come from Nav2 not snapping start and goal into free
   space. Keep the comparison as it is (with the explanation), or also snap for Nav2 to compare planners only?
5. **The Studio on a phone in landscape**: editor and view side by side, the drawing one scroll below. Put the view
   first?
6. **A 3D view of user runs** (the Studio draws 2D GAME/SIM): wanted in R3/R4?
7. **Controller and localiser reference entries** for the leaderboard: generate them (hours of MPPI/MCL) in R3?
8. **The real phone**: plug the Nothing Phone (1) in over USB (debugging on) when convenient; the Studio, its timings
   and Play are then measured on the device.

## Gautham's answers and the decisions taken (2026-11-06)

Recorded at R3 Part A ("land R2"). Principles for the ones left to the agent: exact reproducibility
first, no hidden failures, honest labels, the smallest change that serves learners and researchers.

| # | Question | Answer / decision | Applied |
| --- | --- | --- | --- |
| 1 | D\* Lite's ≤ 3e-15 | **Gautham:** byte-identical; the adapter adds up the path in native order, a 1e-12 tolerance for derived floats only if impossible. | Done without a tolerance: `Builtin.summation` + `measure_path(..., summation)`; exact-equality test on 6 scenarios (ADR 0013 update). No native result, hash or golden changed. |
| 2 | PR #31 | **Gautham:** retarget to main once R2 merges; the verifier labels it; merged under the standing gate. | R3 Part A3. |
| 3 | Theta\* drives 0/5 | **Gautham:** keep the visible negative row; re-run the 5 drives recording the costmap cost along each Theta\* path to confirm or reject "hugs corners". | Row unchanged. **Re-run 2026-11-07 (STACK, balanced, AC): still 0/5**; on every drivable scenario 29–77 % of the plans RPP received from Theta\* had a pose at cost ≥ 253 in the local costmap, against 0–10 % for stock Nav2 (3/5) and the A\* starter (4/5) on the same drives: **the explanation is supported** (the cost is MEASURED; that RPP's check stops each drive remains INFERENCE). [`docs/v2/r3/data/a1/`](../r3/data/a1/README.md) |
| 4 | Stock Nav2's start/goal | **Gautham:** report both, stock (unchanged) and "snapped" (start and goal moved to the nearest free cell, as COCO Lab does), clearly labelled. | Stock rows stay as measured. **Measured 2026-11-07 (STACK, 3 sessions × 20 scenarios):** stock as given 42/60 (the same six scenarios, 205/208); **snapped 60/60**; A\* starter 60/60; snapped Nav2 paired median −0.610 m vs the starter. Snapping moves start or goal by more than a cell only on those six scenarios (0.78–7.38 m); s086's goal is 7.38 m from free space in the live costmap though the model drew it with clearance: UNRESOLVED. [`docs/v2/r3/data/a1/`](../r3/data/a1/README.md) |
| 5 | Studio on a phone in landscape | **Gautham:** view first. | The drawing heads the right column and the Workbench header is compact on the Studio in phone landscape; `studio_check.mjs` asserts the view starts above Run and inside the first screen (emulated: view y = 323 of 412 px, Run y = 678). |
| 6 | A 3D view of user runs | **Decision: not now.** The 2D GAME/SIM drawing already shows every thinking event exactly; a 3D view adds rendering work and no measurement. Parked in `docs/IDEAS.md` for R4 (Learn course), where it may serve learners. | Parked. |
| 7 | Controller/localiser reference entries | **Decision: yes, in R3** (B3: Leaderboard v1 boards for controllers and localisers), generated with resumable runs; until then those boards stay labelled "submissions only". | R3. |
| 8 | The real phone | Not connected at R3 start (`adb devices` empty); stays pending, measured automatically when it is. | Pending. |

## Next step (R3 · COCO-Bench v1 and the paper)

README §7 names R3 · COCO-Bench and the paper as the next milestone; its scope is set by Gautham's R3 prompt, not here.
What R2 hands it: the API and leaderboard for submissions with held-out sets, the MODEL ↔ STACK tooling of R2.7
(`tools/r2/ros2_*`) for more pairs, and the open questions above. Before it: R2 reviewed and merged, then PR #31
labelled by the trusted writer.
