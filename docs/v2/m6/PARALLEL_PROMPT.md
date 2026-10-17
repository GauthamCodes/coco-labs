# M6 foundations — the parallel prompt (saved verbatim, 2026-10-17)

Issued by Gautham on 2026-10-17. It authorises one plan change (recorded in
`PARALLEL_STATUS.md`): M6's foundations, the parts with no user interface,
start in parallel with M5 on branch `v2/m6-foundations`, and merge only after
M5 merges.

---

You are building the foundations of Milestone M6 · COCO Depot for COCO Lab, in parallel with another agent (Codex) that is finishing M5 on branch v2/m5-focus.

Your work must never collide with Codex's. Every checkpoint is committed, so the work survives if this session's credits run out.

0. Authority and ground rules

Read first:

README.md (revision 3, the authority), especially sections 1 ("ROS 2 at its core"), 3, 5.1, 5.2, 5.8, 5.9, 7 (M6) and 9
the repository's agent rules in CLAUDE.md (or AGENTS.md if it exists on your branch)

Gautham authorizes, by issuing this prompt, one plan change. M6's foundations (the parts with no user interface) start now, in parallel with M5, on a separate branch. They merge only after M5 merges.

Record this as a dated entry (2026-10-17) in docs/v2/m6/PARALLEL_STATUS.md, under "Plan-change entries to copy into docs/STATUS.md at merge".
Do not edit docs/STATUS.md yourself.

1. How to stay out of Codex's way (hard rules)

Your own worktree. Never use, edit, build in, or run git commands that change ~/coco_labs_ws/src/coco-labs (Codex's working tree), or ~/ros2_ws(personal).
Create your own worktree: git -C ~/coco_labs_ws/src/coco-labs worktree add ~/coco_labs_ws/worktrees/m6-foundations -b v2/m6-foundations origin/v2/m5-focus. Run git fetch origin first; this is read-only for Codex.
If that path or branch already exists, reuse it.
Never push to v2/m5-focus, never merge into it, never rebase anything. To pick up Codex's newer M5 commits, use git merge origin/v2/m5-focus into your branch, only at a checkpoint boundary and only if you need them. Resolve conflicts in your branch only.
Files you may create or change:
worlds/: new files; the existing v1 and v2 specs stay byte-identical
coco_lab/coco_lab/: new modules only, plus the smallest needed registration lines in existing files
coco_lab/test/ and coco_lab_ros/test/: new tests
coco_schemas/: new .proto files only, plus the regenerated code for them
new scripts under tools/m6/
docs/v2/m6/, and new ADRs in docs/v2/adr/ numbered from 0100 upward so they can't collide with Codex's
Files you must not touch:
lab_web/src/, apart from newly generated schema files for your new protos; if an existing generated index or barrel file must change, note it in PARALLEL_STATUS.md as a known merge point
README.md, docs/STATUS.md, AGENTS.md, CLAUDE.md, PROJECT_STATE.md
docs/RESULTS.md: write your numbers to docs/v2/m6/RESULTS_M6_FOUNDATIONS.md, to be appended at merge
CI workflows
anything Codex's M5 checkpoints own: the Compare, Play, shell and design-system code
Heavy jobs share one laptop. Before any heavy job (Gazebo, Nav2, long benchmarks, full suites), check whether Codex is active (pgrep -fa codex, plus any playwright, vite preview or Chromium measurement runs) and whether a robot-project batch is running (ps aux | grep -Ei 'gz|gazebo|isaac|ros2').
If either is active: run only light work (unit tests under nice -n 19, code, docs), and mark heavy items pending, machine busy.
Never start Gazebo while Codex might be measuring. It would corrupt Codex's M5 numbers.
Never run two simulators at once. Never use --fast.
Never:
delete evidence, tags or releases
create or edit releases
use git clean, git reset --hard, force-push, or delete branches
touch the robot repo
invent a number
mark anything MEASURED without committed data
merge anything
Label all browser or CPU numbers with the machine state, including whether Codex was running.
Use credits sparingly.
Read files in targeted pieces; never read docs/v2/STATUS_HISTORY.md, full Case File data or generated code in full.
Prefer focused tests during work; run each changed package's suite at a checkpoint's end.
Commit at every checkpoint ([M6F.n] …) and push your branch, so nothing is lost.

2. Checkpoints (in this order; stop wherever the credits end, with everything committed)

M6F.0 Setup
Create the worktree and branch as in rule 1.
Save this prompt as docs/v2/m6/PARALLEL_PROMPT.md, and create docs/v2/m6/PARALLEL_STATUS.md. It holds:
the current checkpoint and next step
the plan-change entries
known merge points
pending heavy items
Set up a separate Python environment for this worktree, and run the coco_lab and coco_schemas suites as your baseline.

M6F.1 World Spec v3 and the modular level kit
Design World Spec v3 as a superset: every v1 and v2 world still loads and produces byte-identical model state. Prove this with the existing golden traces and flat-scene hashes.
The kit: wall, door opening, rack (with aisle clearance), bench, pallet, ramp, platform or mezzanine, dock or drop zone, object spawn, and actor lane (a path, speed and footprint for moving forklifts and walkers, each with a collision body).
Add a validator and schema docs (docs/v2/m6/WORLD_SPEC_V3.md), plus ADR 0100.

M6F.2 Generators: one level, three outputs
Arena model world. Occupancy at a chosen resolution (0.1 m for the game; 0.05 m allowed for Research), elevation and the object catalog, consumed by coco_lab.
Gazebo SDF world.
Static geometry with matching collision.
Ramps and mezzanine.
Spawnable objects.
Moving actors as models with collision bodies, not Gazebo's visual-only actors. (Lab 5's lesson: an actor with no collision body let controllers report "reached" through it.)
Nav2 map (PGM and YAML), plus a parameter file derived from the existing gazebo_models/config/nav2_params.yaml. Don't edit the original.
Tests:
Geometry round trip: parse the SDF back to footprints and match the World Spec within a stated tolerance.
PGM pixels against the model's occupancy.
The YAML origin and resolution.
SDF check. If Gazebo's CLI is installed, run gz sdf -k on every generated world. It is light, and allowed even while Codex runs.
Prove the generators on the Proving Ground. Run them on the existing COCO arena (v2 spec), and compare the generated SDF geometry with the original Gazebo world it came from (gazebo_models/config/navigation_world.json and its world). Report the differences honestly.

M6F.3 The COCO Depot level
Author worlds/coco_depot_v1.yaml, about 48 × 32 m, with the six zones:
loading dock
high-bay aisles
mezzanine with a ramp
office block with doorways
workshop maze
forklift lanes with moving forklifts and walkers
Add a short design note per zone (docs/v2/m6/DEPOT_DESIGN.md) saying which algorithm behaviour each zone makes visible.
Object catalog with grasp affordances: graspable cans, bottles and magnetic canisters within COCO's gripper envelope (two fingers and a magnet; the magnet does the holding), and deliberately ungraspable items (too wide, out of reach, not magnetic). Take every envelope number from existing coco_lab or coco_config constants, and cite where each comes from; never invent one.
Generate all three outputs for the Depot, and commit the sources plus checksums of the outputs.

M6F.4 Planning at the Depot's scale (light CPU benchmark)
Time every global planner across the Depot at 0.1 m, over representative start and goal pairs, in CPython and in Pyodide-in-Node, with nice off and only if Codex is idle. Otherwise mark it pending, machine busy.
Record the load average and machine state.
If any planner is clearly too slow for interactive play (state the budget used, for example 300 ms warm), write an ADR proposing the WebAssembly gate (README invariant 9). Do not port anything.

M6F.5 Grasp Assist pipeline (model side, no UI)
A new coco_lab module implementing README section 5.8 deterministically:
detect objects in range
check each one, with a reason code per refusal (too wide, out of reach, not magnetic, blocked)
choose the best candidate
approach: the global planner to the pre-grasp pose, then the local controller into the existing proximity-gate window
reach: IK and a joint trajectory, using the existing arm module
grip and verify
Events: a new additive manip.grasp family in coco_schemas, carrying every stage's data so the UI can draw it later.
Reuse existing code: extend the existing grasp.py gate and arm IK; don't duplicate their constants.
Tests:
every refusal reason
a successful pick ends inside the Stack's approach window
determinism across repeated runs
golden traces for a few Depot scenarios

M6F.6 Mini-game rules: Fetch Rush and Rush Hour (model side, no UI)
Rules engines in coco_lab:
Fetch Rush: seeded order generation, deliveries, a timer, path efficiency against the planner ghost, contacts.
Rush Hour: the crossing, minimum clearance, contacts, and the "fragile cargo" jerk rule. It is labelled as a game rule, not physics (README invariant 13).
Stars come from reference-algorithm results, never hand-picked. Scores never reward luck.
Headless proof: a scripted bot (planner plus Grasp Assist) completes each game on the Depot with seeded runs. Commit the reference results and thresholds to docs/v2/m6/GAMES.md.
Python side of verification: game runs are reproducible from spec plus seed plus input log, with bounded inputs consistent with M5's link limits. The browser and coco verify wiring comes later; note it as a merge point.

M6F.7 ROS-shaped message model (no UI)
A coco_lab module that maps the model's events to ROS 2 message shapes: sensor_msgs/LaserScan, nav_msgs/OccupancyGrid, geometry_msgs/Twist, nav_msgs/Path, nav_msgs/Odometry, and TF frames (map, odom, base_footprint, laser).
A machine-readable "ROS graph" description (nodes, topics, rates) for the panel the UI will draw later.
Field-by-field tests against the real ROS 2 message definitions. Where a recorded Case File contains the same topic, compare shapes and values and report the result.

M6F.8 Real Gazebo and Nav2 validation (heavy; only when the machine is free)
Only if Codex is idle, no robot batch is running, and the laptop is on AC. Otherwise leave everything here pending, machine busy and say so.
Launch the generated Depot SDF headless in Gazebo Harmonic with COCO spawned, plus Nav2 with the generated map and params.
Run a planning smoke test (several goals across the zones), and record whether each succeeds as STACK evidence. Raw logs go to ~/coco_lab_runs/m6/, never into git; summaries and checksums go into the repository.
If that works, record a first real ROS 2 ghost: Nav2 driving one Fetch Rush route (the driving legs only). Convert it with the existing ROS-to-event adapter into a Research recording with a checksum.
MoveIt picks in the Depot are not in scope here. Note them as M6 UI-phase work.
One simulator at a time; a fresh simulator per run; clean up with the repository's cleanup script.

M6F.9 Wrap up
Write docs/v2/m6/RESULTS_M6_FOUNDATIONS.md (every number with its conditions) and docs/v2/m6/MERGE_NOTES.md. The merge notes list:
every file touched outside your own new files
expected conflicts with M5
what the M6 UI phase still needs: Depot rendering and streaming, the Grasp Assist visuals, the game HUDs, the ROS graph panel, coco verify and link wiring in the browser, MoveIt ghosts
Push the branch, and open a draft pull request into main titled M6 foundations (depends on M5). Do not merge it, and do not open it against v2/m5-focus.

3. Stop and report if

A v1 or v2 world's model state, a golden trace or a flat-scene hash changes.
Supporting v3 would require editing files Codex owns.
A gripper or robot constant you need doesn't exist in the repository.
Any step would require deleting evidence or touching Codex's working tree.

4. Final report (end of every session)

Fill this in and make docs/v2/m6/PARALLEL_STATUS.md match:

Checkpoints completed (M6F.x):
Branch / worktree, start SHA → end SHA, pushed (y/n), clean (y/n):
Codex activity observed (and how heavy jobs were scheduled around it):
Per checkpoint: what changed | evidence file(s) | evidence class
Tests: suite → passed / failed / skipped (before vs after)
Measurements (device, machine state, Codex running or not, power, driver):
Golden traces and flat-scene hashes unchanged? (evidence)
Known merge points with M5:
Pending heavy items:
Plan-change entries to copy into STATUS at merge:
Questions for Gautham:
Next step:
