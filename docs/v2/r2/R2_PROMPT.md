# R2 · Bring Your Own Algorithm — prompt (saved verbatim, 2026-11-04)

You are building R2 · Bring Your Own Algorithm for COCO Lab (repo GauthamCodes/coco-labs, live at https://gauthamcodes.github.io/coco-labs/).

Where we are.

G1 and G2 gave COCO Lab a polished game front door with a real ROS 2 identity.
R1 turned Research into a Workbench: experiments, statistics, benchmark suites (COCO-Bench v0, 1,970 reference runs), exports, and links that reproduce exactly in three browsers and natively.
One thing still makes it a showcase rather than a lab: nobody can test their own algorithm.

What R2 must achieve. Anyone, a student in a browser or a researcher with a laptop, can:

write a planner, controller or localiser in Python, in the browser, with no install
watch it think exactly like the built-in algorithms do, in GAME view, SIM view and Compare
benchmark it on COCO-Bench with honest statistics
share it as a link that reproduces exactly
submit it to a public leaderboard that is verified automatically by re-running it
run the same file as a real ROS 2 node, driving COCO in Gazebo through Nav2

Step 6 matters most: it is the bridge from "imitation of ROS 2" to "your code runs in real ROS 2". It is the project's strongest claim, and it must be true.

0. Setup and rules
Branch. git fetch origin; create a worktree ~/coco_labs_ws/worktrees/r2 on a new branch v2/r2-byoa, from origin/main (with #30 merged) or from origin/v2/r1-workbench if #30 isn't merged yet. Say which.
Paperwork.
Save this prompt as docs/v2/r2/R2_PROMPT.md and keep progress in docs/v2/r2/R2_STATUS.md.
Add a dated (2026-11-04) entry to STATUS's plan-change log, and update README §7 for R2.
Commit [R2.n] per checkpoint and push.
Read first: README.md, AGENTS.md, docs/STATUS.md, docs/v2/r1/R1_RESULTS.md, ADR 0011 (coco.experiment.v1), the coco_lab planner/controller/localiser interfaces, coco_lab.experiments, the Compare and Workbench sources, and the M6F.7 ROS shapes.
All earlier rules hold:
The model and the truth:
Rendering never changes the model. Hashes are versioned.
Evidence labels are truthful.
Honest statistics (R1 §0.4).
Never invent numbers.
Git and evidence:
Never merge, deploy or release.
No destructive git commands. Never delete evidence.
Machine and phone:
Balanced profile on AC.
One simulator at a time; never Gazebo --fast.
The phone: restore its settings afterwards, and black out its status bar in screenshots.
Security (non-negotiable: R2 runs strangers' code).
In the browser:
User code runs only in a dedicated Pyodide worker that has no network, no DOM and no storage access. Before user code loads, remove or stub fetch, XMLHttpRequest, WebSocket, importScripts, indexedDB, caches and BroadcastChannel in that worker.
Block import js and pyodide.ffi (and similar escape hatches) with an import hook, and allow only an explicit list of modules (math, heapq, collections, itertools, functools, random through the provided seeded generator only, numpy if it is already shipped, and coco_lab.api).
Enforce a hard time limit per call (terminate and restart the worker) and a memory ceiling.
Add CSP headers or meta where GitHub Pages allows them.
Opening a link that contains code always shows the code and an explicit "Run this code" button. Nothing runs automatically.
In CI (the leaderboard verifier):
Untrusted code runs only on pull_request (never pull_request_target), with no secrets, read-only permissions, --network none, a timeout, and CPU and memory limits.
Results are written only by a separate trusted workflow that reads the verifier's artifact.
In ROS 2: generated packages run the user's code with the same allowed-modules guard.
Document the threat model in ADR 0012.
Algorithms must be deterministic. User code gets a seeded generator from the API and must be a pure function of its inputs. The runner checks this by running each scenario twice and comparing hash chains. A non-deterministic algorithm is flagged and cannot be submitted; it can still run, labelled "non-deterministic".
1. What to build
1.1 The algorithm API (coco_lab.api, coco.algorithm.v1, ADR 0013)

Three small, documented contracts, with type hints and validation:

```python
# Global planner
def plan(costmap: Costmap, start: Pose2D, goal: Pose2D, ctx: Context) -> list[Pose2D] | None

# Local controller (called every tick)
def control(state: RobotState, scan: LaserScan, path: list[Pose2D], ctx: Context) -> Twist

# Localiser (called every tick)
def localise(odom: Odometry, scan: LaserScan, map: OccupancyGrid, ctx: Context) -> PoseWithCovariance
```

The types are the same shapes as the ROS 2 messages from M6F.7 (nav_msgs/OccupancyGrid, sensor_msgs/LaserScan, geometry_msgs/Twist and so on), so the code maps one-to-one onto a ROS 2 node.
ctx provides:
randomness: the seeded RNG
robot geometry: the footprint radius and limits, read from COCO's real config values
costmap helpers: cost lookup, world_to_map and the reverse
tracing: ctx.emit(kind, data), so user algorithms show their thinking (expansions, frontier, candidate trajectories, particles) in the same glass-box visualisations the built-ins use, with event types documented
time: a step budget, and ctx.time (sim time)
Output is validated: paths within bounds, Twist within the robot's limits (clamped and logged, never silently accepted), and covariance positive semi-definite.
The built-in algorithms are re-expressed through the same API where practical, or wrapped to it, so user code and built-ins are measured identically.

Hashes: the built-ins must give byte-identical results through the API wrapper. Prove it with the existing goldens and the 1,970 reference runs (re-run a 10% sample). If an unavoidable change appears, stop and report.

1.2 The in-browser editor ("Algorithm Studio", in Workbench)
A code editor with CodeMirror 6, from npm (MIT, recorded in the licence manifest): Python syntax, line numbers, error markers, and autocomplete for the coco_lab.api types.
Starter templates:
Planner: A* (well commented), greedy best-first, and an empty template.
Controller: pure pursuit and an empty template.
Localiser: a minimal particle filter and an empty template.
Plus two teaching starters for R4 later: "Write the heuristic" (A* with the heuristic left to the student) and "Tune DWA" (with its weights exposed).
Run against:
one scenario, live in GAME or SIM view, with your algorithm's ctx.emit thinking drawn as it runs
Compare: your algorithm as a pane beside any built-in
an experiment: any COCO-Bench suite, with full R1 statistics against the built-ins
Feedback: Python tracebacks mapped to editor lines; stdout and stderr in a console; a validation report (contract errors, clamped outputs, the determinism check, the time-budget overruns); and per-call compute time with its device label.
Saving: a local draft in prefs; download or upload a .py file; and a share link with the code compressed in the URL fragment (a size limit of about 64 KB, with a clear error past it).
1.3 Native side and parity
coco experiment run spec.json --algorithm my_planner.py runs user code natively under the same allowed-modules guard.
CI parity: each starter template on a small suite gives 0 differences between browser and native, the same as R1's parity check.
1.4 The verified leaderboard (no server)
A submission is a pull request adding leaderboard/submissions/<suite>/<name>/ with algorithm.py, meta.yaml (author, display name, description, licence, an optional paper link) and the claimed summary.json.
The verifier workflow, with the sandbox in §0.5:
re-runs the algorithm natively on the full suite
checks determinism (two runs, identical hash chains) and contract compliance
compares the results with the claim
Pass: a "verified" label and a results artifact. Fail: a clear report on the PR.
The leaderboard page has one table per suite, ranked by deterministic metrics only: success rate with its interval, the median ratio of path length to optimal, the median of expansions or the controller's own cost, and clearance. Compute time is shown per device but never used for ranking. Each entry links to its code, a reproduce link, the replay of its worst run, and its failure list.
Seed it with the built-ins as reference entries, plus one submission by Gautham (for example, a Theta* or a JPS planner written through the API) to prove the whole loop end to end on a real PR.
Write leaderboard/CONTRIBUTING.md: how to submit, the rules (no hard-coding scenarios; suites have hidden held-out variants, see §1.5), the licence requirement (MIT or Apache-2.0), and the code of conduct.
1.5 Fair benchmarking
Held-out scenarios: each suite gets a held-out set generated from a secret-free but unpublished seed scheme. The verifier generates them at verification time from the PR's merge-base and a fixed salt committed only in the trusted workflow, and the leaderboard reports public and held-out results side by side. This catches overfitting to public scenarios. If a sound no-secret scheme can't be built, state the limitation honestly in CONTRIBUTING and ADR 0012; don't fake it.
Version everything: the suite version, model hash version, API version and verifier version are recorded with every entry. A version bump re-verifies all entries automatically.
1.6 From browser to real ROS 2 ("Run in ROS 2")

The most important feature of R2.

Export. An "Export as ROS 2 package" button (and a matching CLI) generates a ready ament_python package, coco_user_<name>, containing:
a planner as a node serving the nav2_msgs/action/ComputePathToPose action. It converts the real /global_costmap/costmap (OccupancyGrid) and the poses into the API types and calls the user's plan().
a controller as a node subscribing to /scan, /odom and /plan and publishing /cmd_vel. It feeds into COCO's real cmd_vel_arbiter (never bypassing it), so STOP and the safety chain still apply.
a localiser as a node publishing the map→odom transform and /amcl_pose-compatible output, replacing AMCL.
a launch file that swaps the user node into COCO's Nav2 bring-up in place of the matching Nav2 component, using the generated params, and a README.
The user's algorithm.py is included unchanged. That is the point: one file runs in both places.
Validate on the laptop with real Gazebo + Nav2:
Planner: the A* starter and Gautham's leaderboard planner, run as the planner on a subset of depot-nav-100 (at least 20 scenarios, 3 repeats), against stock Nav2's planner on the same scenarios. Record the success rates, path lengths, and the browser-vs-Gazebo gap, as STACK evidence.
Controller: the pure-pursuit starter as the controller on the four colour rounds, 5 of 5 each.
Localiser: a smoke run on one round, with pose error measured against Gazebo's ground truth.
Raw logs go to ~/coco_lab_runs/r2/, and summaries and checksums go into the repository.
The research payoff: a "Browser vs ROS 2" panel on each leaderboard entry and in the Studio. For algorithms that have real ROS 2 runs, it shows browser-model results beside real Gazebo + Nav2 results on the same scenarios, labelled MODEL and STACK, with the gap stated.
If the timing works out, add a "Run in Live ROS 2" option for users who have the Docker image from R5. Otherwise list it as R5 work; don't build Docker here.
1.7 Polish and understanding
Phone: the Studio is usable in landscape for reading, running and comparing. Editing long code on a phone may be basic; say so in the interface instead of hiding it.
Learn tie-in: the two teaching starters appear on the Learn page as "Try it yourself" next to the matching missions.
Write docs/v2/r2/API.md: the full API reference, worked examples, and the event types for ctx.emit, linked from the Studio.
2. Checkpoints (in this order; commit and push each)
R2.0 Baseline

Setup, build, all suites. Before screenshots of Workbench, Compare and Learn, at desktop and on the phone.

R2.1 API and security design

ADRs 0012 and 0013, the coco_lab.api types and validation. The built-ins wrapped through the API with byte-identical goldens.

R2.2 Sandboxed worker

The browser user-code worker: the stubs and the import guard, plus the time and memory limits. Escape tests must fail safely:

network calls
DOM access
import js
infinite loops
memory blow-ups
huge outputs
R2.3 Algorithm Studio

The editor, the templates, single-scenario runs with the thinking drawn, the console, validation and the determinism check.

R2.4 Compare, experiments and native

User algorithms in Compare panes and in experiments, the native CLI, and the parity CI.

R2.5 Share links

Code links with the explicit Run consent; download and upload of .py files.

R2.6 Leaderboard

The submission format, the sandboxed verifier workflow, the trusted writer workflow, the held-out scenarios, the leaderboard page, the built-in entries, and Gautham's submission PR as the end-to-end proof (opened, verified, and left for him to merge).

R2.7 Run in ROS 2

The package exporter, then the laptop validation in Gazebo + Nav2 for planner, controller and localiser, and the "Browser vs ROS 2" panel.

R2.8 Phone and Learn

The phone pass, the Learn tie-ins and API.md.

R2.9 Close

After screenshots, docs/v2/r2/BEFORE_AFTER.md, all suites, v1/v2/v3 determinism, the R1 reference sample, the security tests, the real phone if connected. Then R2_RESULTS.md, and a PR "R2 · Bring Your Own Algorithm" into main, ready for review. Don't merge.

3. Stop and report if
A built-in algorithm's result or hash changes through the API.
Any sandbox escape test succeeds.
The verifier would need secrets or pull_request_target to work.
Real Gazebo + Nav2 can't run the user node without changing COCO's own robot repository.
Play's frame rate gets worse.
4. Final report
Checkpoints done (R2.x):
Branch, SHAs, pushed, clean:
API: contracts, built-ins wrapped byte-identical? (evidence)
Security: escape tests (each → result), CI sandbox settings, ADR 0012 summary
Studio: templates, thinking visualised, determinism check, phone usability
Parity: browser vs native per template
Leaderboard: suites, entries, held-out scheme (or its stated limitation), Gautham's submission PR (link, verified?)
Run in ROS 2: package exported; Gazebo results per component (success, gap vs stock Nav2, MODEL vs STACK)
Tests and determinism:
Performance: Play fps unchanged; Studio and experiment timings (device)
Screenshots: BEFORE_AFTER.md
Questions for Gautham:
Next step (R3 · COCO-Bench v1 and the paper):
