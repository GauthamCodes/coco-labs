# COCO Lab — rules for every coding agent

## Authority and read first

1. Read README.md (master plan), this file, then docs/STATUS.md.
2. Read the active milestone prompt and its owner amendments:
   docs/v2/M5_PROMPT.md and docs/v2/M5_CONTINUATION.md for M5.
3. The repository and committed evidence describe what exists; README
   describes what becomes; STATUS records progress and dated owner decisions.
4. Owner instructions and approved dated amendments take precedence over
   old defaults. Never infer a new milestone or enlarge scope.
5. Before every task name milestone, checkpoint and exit criterion (drift test).
   If none applies, park it in docs/IDEAS.md:
   `date | idea | gap it closes | earliest milestone`.
6. M5: focus/polish existing Play, Compare, Research; no new world,
   mini-game, cloud, experiment builder or physics engine. Costmap inflation
   is the only new algorithm. Reuse existing reference algorithms.
7. Continue checkpoints in order without asking unless a listed stop condition
   fires. Visual review is a soft gate; retain screenshots and carry on.

## Workspaces and boundaries

- Canonical checkout: /home/gautham/coco_labs_ws/src/coco-labs.
- Workspace: /home/gautham/coco_labs_ws. Use only its source and overlays.
- Never use ~/ros2_ws(personal), the robot repository or robot worktrees,
  including ~/coco-isaac-21 and ~/coco-p03d-target-search.
- ~/coco_lab_runs is read-only evidence. Never modify it.
- Frozen robot-stack packages remain; no new features. M5.2 explicitly
  authorizes moving RL-era scripts and repairing their references.
- Before heavy work: `ps aux | grep -Ei 'gz|gazebo|isaac|ros2'`.
  If an actual simulator/Isaac/robot batch is active, run no heavy jobs;
  report and wait. Do not kill someone else's process. M5 needs no Gazebo.
- Never Gazebo --fast; never run two simulators. Historical hygiene is archived.
- Source only setup_env.sh and install/local_setup.bash, not an inherited
  unrelated overlay. Setup removes foreign prefixes; keep that guard.

## Model and integrity invariants

- coco_lab never imports rclpy; browser Stack control names no ROS topic,
  speaks coco.v1 intents only; protocol growth is additive within a major.
  Future teaching ROS names/visitor-owned bridge are outside this boundary.
- cmd_vel_arbiter is the only wheel publisher. STOP wins over teleop,
  which wins over assists/autonomy. Control is exclusive and interruptible.
- Ground truth comes only from truth. Never invent z/roll/pitch for a recording.
- The model is differential-drive planar kinematics plus terrain following:
  no strafing, excess speed, tipping, contact forces, friction or browser physics.
- Cameras, lighting, wall display height and interpolation never alter the model.
- Every model view displays MODEL · kinematic. No physical robot exists.
  STACK means the full ROS 2 stack in Gazebo, never hardware.
- Gripper: two fingers and a magnet; the magnet holds the object.
- Comparisons keep map, start, goal, seed and every non-compared variable fixed.
- Version formats/hashes; major change gets a converter. Older links keep
  their version. V1 hash layout and golden traces stay unchanged.
- Any second algorithm implementation must be trace-equivalent to Python on
  the property corpus in CI. Port only after a measured failed budget.
- Scores use real metrics/decision quality; never rewards for luck, XP or loot.
- Claims in missions/tours/Case Files cite committed evidence and pass CI.
  Negative results stay visible. Never round away or explain away failures.
- RESULTS.md is append-only. Never delete evidence, tags, releases, branches
  or working public URLs; never create/edit releases. Draft notes only.
- No invented numbers. A claim is measured only with committed re-checkable data.
- Preferences/progress: one module, localStorage accesses inside try; works
  without storage. No cookies/sessionStorage/personal IndexedDB or tracking.
- Service worker: static assets only, content-hashed/versioned, old caches
  cleared on activation. One aggregate cookieless counter, off until configured.
- Every shipped asset has a permissive licence, source and checksum in manifest.

## Evidence classes

MODEL: Python reference/browser Arena. STACK: recorded full ROS 2 in Gazebo.
REMOTE: simulated Stack over internet. EXTERNAL: visitor's own ROS 2 (M7).
HARDWARE: physical robot (none exist). UNRESOLVED: unexplained/untested or
statistically unresolved. CONCEPT: discussed, not built.
Learner labels: MEASURED, TESTED, ASSUMPTION, SIMPLIFIED MODEL, SIMULATION
RESULT, REAL ROBOT RESULT, INFERENCE, UNRESOLVED; preserve original evidence.
Head-on Lab 5: actor walked into stopped robot; reached depended on missing
actor collision body. Run 15 mechanism is reproduced, exact original unresolved.

## Build and tests (exact commands)

Node 24.21.0 is pinned by lab_web/.nvmrc; use the existing binary below.
Python 3.12.3 test venv: ~/coco_labs_ws/test_venv. Do not override interpreter
in a way that lets user-site networkx precede its pinned 2.8.8.

```bash
cd /home/gautham/coco_labs_ws/src/coco-labs
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:$PATH
export PYTHONPATH=/home/gautham/coco_labs_ws/src/coco-labs/coco_schemas:/home/gautham/coco_labs_ws/src/coco-labs/coco_schemas/coco_schemas/gen:/home/gautham/coco_labs_ws/src/coco-labs/coco_lab:/home/gautham/coco_labs_ws/src/coco-labs/coco_config
NODE_OPTIONS=--test-reporter=tap ROS_DOMAIN_ID=78 scripts/run_all_package_tests.sh
PYTHONDONTWRITEBYTECODE=1 /home/gautham/coco_labs_ws/test_venv/bin/python -P -m pytest -q -p no:cacheprovider lab_web/tools
PYTHONDONTWRITEBYTECODE=1 /home/gautham/coco_labs_ws/test_venv/bin/python lab_web/tools/build_catalog.py
cd lab_web
npm ci
npm run arena-assets
npm run typecheck
npm test
npm run build
node tools/check_dist.mjs
```

- Catalog generation MUST precede arena-assets; do not parallelize builders
  which recreate public/generated. Generated data are disposable, evidence isn't.
- Package runner sets cwd per package, pinned deps and user-space MoveIt prefix.
  Use it for focused packages too: `scripts/run_all_package_tests.sh coco_rl`.
- Need ROS overlay build: `scripts/build_overlay.sh /home/gautham/coco_labs_ws`;
  never use a robot overlay. Build only when needed, no simulator is required.
- Schemas: `python3 coco_schemas/scripts/generate.py --lang ts --check`.
  Keep major compatibility baseline and golden fixtures untouched.
- Focused checks while editing; all three suites at checkpoint end. Run URL,
  replay, screenshot and coco verify checks when required by the checkpoint.
- A known live-graph node creation flake needs investigation/recheck, not waiver.
- Frozen /v1 is fetched/checksummed from pinned v1-site. Source reproducibility
  job is explicitly disabled (M5.1); see data/m5/defects/V1_WORKFLOW.md.

## Measurements and phone

- Laptop budgets: balanced on AC. Capture original power profile, use
  `powerprofilesctl set balanced` only if needed, restore original afterwards.
  Record power/AC, device, GPU driver and actual renderer with each measurement.
- No GPU/network/evidence access or no AC: affected item pending, needs laptop;
  continue independent work. Never estimate. Label all emulation as emulated.
- Shared profile: lab_web/tools/phone/nothing-phone-1.mjs: 412×915 or 915×412,
  DPR 2.625, mobile/touch, Android UA, 4× CPU proxy, emulated 4G for cold starts.
- Nothing Phone (1) facts are assumptions until measured on the actual device.
  Phone profile/provisional defaults: docs/v2/PHONE_PROFILE.md.
- Real phone checks are agent-owned. Real USB/CDP measurement alone can meet
  Phone; emulation never does. Five-person usability remains Gautham-owned,
  gates public launch only. The pre-design prerequisite is explicitly waived.
- Local adb: ~/coco_labs_ws/m5-tools/adb/root/usr/bin/adb, with Android libs at
  that root's usr/lib/x86_64-linux-gnu/android (LD_LIBRARY_PATH). Check devices;
  forward 9222 to chrome_devtools_remote, use Playwright CDP; no manual phone
  measurements requested. If absent, pending: connect phone over USB.
- At M5.4 ask once in STATUS to plug it in when convenient; never wait for it.
- Each look-changing checkpoint saves desktop and both emulated phone
  orientations under docs/v2/data/m5/screens and lists them for owner review.
  Screenshots catch regressions; Gautham judges the look. Apply recorded feedback.

## Git, checkpoint discipline and stop conditions

- Branch v2/m5-focus. Prefix commits [M5.x]. Never force-push, git clean,
  git reset --hard, delete branches/tags, or merge the milestone PR.
- Commit every checkpoint; update short STATUS (<=200 lines) with tested SHA,
  branch, evidence, open rows, screenshots and exact next step. Append history
  to docs/v2/STATUS_HISTORY.md. AGENTS stays <=250 lines.
- Use git mv for archival moves. Only deletion allowed in M5: tracked root
  node_modules test cache via git rm --cached; list every file in commit message.
- Stop and ask only for M5_PROMPT stop conditions: changed v1 hash/golden,
  old URL with no home, claim losing evidence, Focus needing capability removal,
  dirty/unpushed initial M5.0 checkout, or deletion of protected evidence/URL.
- At close push branch and open PR into main with gh pr create; never merge it.
  Public release/announcement are Gautham's after final launch gates pass.

## End-of-session report

Milestone / checkpoints completed:
Start SHA → end SHA, branch, worktree clean (y/n):
Gautham's notes: found/not found; phone result; design inputs addressed:
Per checkpoint: change | evidence | evidence class:
Tests: suite → passed/failed/skipped (before vs after):
Measurements (device/emulation, power, driver, conditions):
Acceptance criteria: each → met/not met/pending Gautham/pending laptop, evidence:
Screenshots awaiting Gautham:
Files moved/removed (full list) and why:
ADRs and plan-change log:
Deviations and reasons:
Ideas parked in docs/IDEAS.md:
Stop condition hit? Which:
Questions for Gautham:
Next step according to README:
Phone: emulated Nothing Phone (1) | real results/not connected | cap, pixel ratio, tier:

## Archives (read only when relevant)

- docs/archive/robot_stack/CLAUDE_robot_stack.md: full prior rules/lore,
  verbatim; historical paths refer to repository root.
- docs/archive/robot_stack/PROJECT_STATE_full.md: prior state/evidence record.
- docs/v2/STATUS_HISTORY.md: milestone history and older plan-change entries.
- docs/archive/v1/: v1 plans/rules. Release tags and evidence remain intact.
