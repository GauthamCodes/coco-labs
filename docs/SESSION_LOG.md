# Session log

One entry per working session, newest at the bottom. Append, never rewrite.

The point of this file is that a session ending mid-phase should be resumable
by someone with no memory of it — including you, three weeks later. The "next
command" line is the most important line in every entry; if it is vague the
entry has failed.

**Format:**

```
## YYYY-MM-DD — <phase>, <one-line summary>

**Built:**      what changed, by file or package
**Measured:**   numbers produced from runs IN THIS SESSION only
**Unverified:** written but not observed working
**Open:**       questions, blockers, decisions deferred
**Next:**       the exact command to run
```

`Measured` and `Unverified` are separate fields on purpose. Anything that has
not been observed working goes in `Unverified`, no matter how confident the
code looks. M6 is currently open precisely because a fix was written into the
approach window without a run behind it.

---

## 2026-08-06 — state at the start of M7

**Built:**
M0–M6 complete as source. Eight packages. `coco_mission` composes the full
stack. `traverse_demo.py` sequences the seven-step fetch.

**Measured:**
- M0: sim RTF ≈ 1.0, every sensor at nominal rate, in sim time
- M2: Nav2 + SmacPlanner2D, 10/10 goals, mean 34.7 s, 36.3 m, home to 12 cm,
  paths 6.2 % shorter than Dijkstra
- M3: `arm_ik` 20,000/20,000 round trips, max error 1.7e-16 m, 1.5 µs/solve;
  MoveIt pick-and-place 4/4 at the tuned target
- M3: `--target` re-targeting 5/14 with the magnet grasp; failures split
  cleanly on x, every point ≥ 0.1505 completes, every point ≤ 0.1468 rejected
- M4: five-stage curriculum, 10/10 deterministic at both 18° and 24°,
  126–127 steps, returns 69.5–69.9; re-verified 10/10 after ramp rebuild
  without retraining
- M4: `--fast` A/B, same seed and config — with: 531/533 tipped, eval 0/10;
  without: 0/533 tipped, eval 10/10, and faster (8.7 vs 8.2 steps/s)
- M5: perception 16/16 lane × station cells within ±2 mm vs `gz model -p`
- M6: bare policy at yaw 0 drifts +0.03 m over 2.5 m in every lane
- M6: `lateral_hold` at K_Y 3.0 / K_YAW 2.5 takes worst-case drift to
  0.053 m, 8/8 summits, no retraining
- Tests: 250, 0 failures
- Training throughput ceiling: ~8.6–8.7 env-steps/s

**Unverified:**
- **M6 end-to-end fetch has never completed.** Best run reached step 4 and
  failed at grasp approach, stopping at base-x 0.1443 — inside the measured
  self-collision bound of 0.150.
- The corrected approach window `[0.1510, 0.1565]` is **written and unit
  tested but never run in simulation**.
- CI workflow and Dockerfile have never executed (no Docker or runner on
  this machine).

**Open:**
- ~111 commits unpushed; `origin` has only `main`.
- `FUTURE_WORK.md` 9(b): the 12° full-distance stage evaluates 0/10 alone —
  a greedy stall at 4.34 m, reproducible to within 0.02 of return.
  `MIN_LIN = 0.15` sitting between a 0.10 m/s timeout and a 0.17 m/s finish
  is the leading suspect. Unexplained.
- `gazebo_models/scripts/` and `coco_moveit_config/scripts/` have no linters;
  ~118 docstring and import-order findings remain.

**Next:**
Phase 0. One blue fetch on the v1 world, fresh simulator:

```bash
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py \
    policy:=~/coco_rl_runs/curriculum_20260726_211008/phase5_24deg_s0p0.zip
ros2 run gazebo_models traverse_demo.py --colour blue
```

Report the base-x the creep phase achieved and whether `/grasp/pick` planned.

---

## 2026-08-06 — Phase 0, M6 closes: the fetch completes end to end

**Built:**
No source changes. Docs only: the end-to-end result in `docs/RESULTS.md`,
the `policy:=` command corrected to an absolute path in `docs/RUNNING.md`,
the M6 row in `README.md`, and this entry.

**Measured** (all from one run in this session, v1 wedge world, fresh
simulator, `gui:=false`, never `--fast`):
- **`FETCH COMPLETE — blue delivered`.** All seven steps, 230.9 s from the
  first log line to the last, home to within 0.06 m of the start.
- **base-x 0.1544** reported by `approach_server` against the window
  `[0.1510, 0.1565]` — +3.4 mm above the near bound, −2.1 mm below the far
  one, +0.7 mm off the 0.15375 centre. The previous attempt's 0.1443 was
  5.7 mm *below* `GRASP_SELF_COLLISION_X`; this is 4.8 mm above it.
- **base-x 0.1548 by Gazebo ground truth** — robot at world
  (3.89573, 0.26346) yaw −0.08396, `target_blue` at (4.049990, 0.250000),
  giving (0.1548, −0.0005) in `base_footprint`. Agrees with the
  dead-reckoned estimate to 0.45 mm in x, 0.48 mm in y.
- **`/grasp/pick` planned and held**: `outcome=held`, `lifted=1`, grasp
  `[0.2728, 0.5052]`, hover `[-0.1054, 0.2935]`.
- **Lift 34.8 mm** (z 0.7288 → 0.7636), read from Gazebo. Place confirmed
  at z 0.0790, `target_blue` ending at world (−1.909110, −0.054373).
- Climb `outcome=goal`, 60 steps, progress 4.72, **lateral +0.09** with the
  lane hold on. Descent `outcome=goal`, 322 steps, progress 6.65.
- Arbiter trace `idle → nav → rl → idle → approach → idle → rl → nav →
  idle`, no double-publisher warning at any point.
- Tests: **250, 0 failures, 0 skipped** (57/67/50/44/20/12). A bare
  `colcon test-result` said 266 — the stale-XML inflation already noted in
  RESULTS.md; the per-package current files sum to 250.
- Bringup gates all passed first time: `verify_sim.py` all checks passed,
  four controllers active, all 4 magnets released, `bt_navigator` active.

**Unverified:**
- **Repeatability. This is 1/1 for blue, not a success rate.** No colour
  other than blue has been driven end to end, and no run has been repeated.
- CI workflow and Dockerfile still have never executed here.
- No video recorded — the run was headless. Still open from the M7_DESIGN
  precondition list.

**Open:**
- `ramp_driver` has **no `os.path.expanduser`** on its `model` parameter,
  and bash does not tilde-expand after `:=`. The documented
  `policy:=~/coco_rl_runs/...` (see the previous entry's Next block, left
  intact as the historical record) reaches `PPO.load` as a literal `~` and
  raises inside the climb worker, surfacing as a failed `/ramp/climb`. The
  docs now use the absolute path; the one-line code fix is NOT done.
- Untracked and therefore unpushed: `CLAUDE.md`, `docs/M7_DESIGN.md`,
  `docs/M7_PHASES.md`, `docs/README_BANNER_snippet.md`. They exist only on
  this machine. Committing them is a call for the repo owner.
- `FUTURE_WORK.md` 9(b) unchanged: 12° full-distance evaluates 0/10 alone,
  a reproducible greedy stall at 4.34 m.
- `gazebo_models/scripts/` and `coco_moveit_config/scripts/` still unlinted.

**Next:**
M6 is closed, so M7 is unblocked. Phase 1 of `docs/M7_PHASES.md` — the
MuJoCo throughput baseline. The figure to beat is 8.7 env-steps/s, and the
instruction is to stop and report if MuJoCo is not meaningfully faster.

Before anything else, re-read that block. Then:

```bash
source ~/ros2_ws/src/coco-robot-ros2/setup_env.sh
cd ~/ros2_ws && colcon test --packages-select coco_rl && colcon test-result
```

To re-run the M6 fetch instead (fresh simulator, absolute policy path):

```bash
bash ~/ros2_ws/src/coco-robot-ros2/gazebo_models/scripts/ros_clean.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py \
    policy:=/home/gautham/coco_rl_runs/curriculum_20260726_211008/phase5_24deg_s0p0.zip
ros2 run gazebo_models traverse_demo.py --colour blue
```

---

## 2026-08-06 — Phase 0.5, M6 consolidated: 19/20, and the drift explained

**Built:**
No source changes; docs only. Phase 0.5 block added to `M7_PHASES.md`;
`CLAUDE.md` and `M7_DESIGN.md` brought into the tree; `README_BANNER_snippet.md`
deleted; `FUTURE_WORK.md` 7b and 8b added. The 20-run harness, the
ground-truth/AMCL logger and the analysers live in the job scratch dir,
deliberately outside the repo.

**Measured** (20 runs, 5 per colour, fresh simulator each, headless, never
`--fast`):
- **19/20 complete.** red 5/5, green 5/5, yellow 5/5, blue 4/5.
- **Approach: 20/20 inside `[0.1510, 0.1565]`.** Ground truth 0.1534–0.1556,
  mean 0.1543, **sd 0.6 mm**. Reported 0.1530–0.1547. |truth − reported|
  0.05–0.92 mm, mean 0.53 mm.
- **Grasp held 20/20**, lift 33.9–35.9 mm from Gazebo ground truth.
- Vision confirmed the requested colour **20/20**.
- Run durations 116.7–322.5 s.
- **Drift at summit** +0.020 to +0.280 m, mean +0.081, sd 0.072. Exceeds the
  documented 0.053 m worst case in **9/20**; max is **5.3×** it. Positive in
  all 20 runs. Per lane: red +0.034, green +0.058, blue +0.086, yellow +0.146.
- **Entry heading at `/ramp/climb`** |yaw| 0.104–0.472 rad, mean 0.290,
  **outside Nav2's `yaw_goal_tolerance: 0.25` in 14/20** — settled, not
  transient (Δyaw over the next second = 0.0000 in all 20; stationary for the
  prior 2 s in 12 of the 14).
- **AMCL is not the cause**: |ground-truth yaw − AMCL yaw| 0.006–0.165 rad,
  mean 0.076; the two disagree about tolerance compliance in 1 run of 20.
- Drift vs entry heading: Pearson **r = +0.565** (r² = 0.32); fit
  drift = 0.132·yaw₀ + 0.073.
- **Lane offset at the summit** −0.012 to +0.301 m. Two runs finished more
  than a half-lane off centre: run 16 at y +1.0512 (**0.199 m from the
  platform edge**), run 19 at y +0.5041 (nearer yellow's lane than blue's,
  and colour-based selection is what kept it correct).
- **AMCL gap at descent end** 0.119–1.183 m, mean 0.378. Every run ≤ 0.470 m
  drove home; the single 1.183 m run did not.
- Tests: **250, 0 failures, 0 skipped** — unchanged.

**Unverified:**
- **Nothing is pushed.** `gh auth status` still reports no host despite the
  task stating `gh auth login` had been run; `~/.config/gh` does not exist.
- **No video.** `ffmpeg` is not installed and `sudo` needs a password.
- The mechanism behind the yaw-tolerance breach (FUTURE_WORK 8b) — candidates
  listed, none tested.
- The residual +y drift bias — observed in all 20 runs, unexplained.

**Open:**
- Two blockers above, both needing the operator: `gh auth login`, and
  `sudo apt install ffmpeg`.
- FUTURE_WORK 7b: 1/20 of the mission is lost to the deliberately unmapped
  corridor, after a successful pick. Mapping it is probably cheaper than
  tuning AMCL.
- `ramp_driver` still has no `os.path.expanduser` on its `model` parameter.
- The lane-hold gains were deliberately NOT retuned.

**Next:**
Land the two blocked deliverables, in this order:

```bash
gh auth login                                  # operator
git -C ~/ros2_ws/src/coco-robot-ros2 push -u origin jazzy-harmonic-port
git -C ~/ros2_ws/src/coco-robot-ros2 ls-remote --heads origin
```

Then the video (needs `sudo apt install ffmpeg`), then M7 Phase 1 — the
MuJoCo throughput baseline in `docs/M7_PHASES.md`. The figure to beat is
8.7 env-steps/s, and the instruction there is to stop and report if MuJoCo
is not meaningfully faster.

---

## 2026-08-07 — Phase 0.6: pushed, cross-track fixed, the +y bias is the policy

**Built:**
First source change of these phases, and it is confined to reporting:
`ramp_driver` now publishes `lateral` as signed distance from the **target
lane centreline** and keeps the old quantity as `disp`. It takes ground
truth from `/model/coco/odometry` and the lane from
`/mission/target_colour` via `coco_config`'s colour→lane table, with a
`lane_y` parameter for standalone runs. **`ramp_env` is untouched** —
`obs[1]` is a policy input and redefining it would have broken the shipped
policy and every number measured against it. `lateral_hold`'s control
input is unchanged and the gains were not retuned.

Also: `docs/RESULTS.md` and `docs/FUTURE_WORK.md` 7b/8b/9(a) amended;
diagnostics and the fetch-matrix harness live in the job scratch dir,
outside the repo.

**Measured** (this session):
- **Cross-track, recomputed over the 20 logged runs — no new simulation.**
  Recomputed `disp` reproduces the logged `lateral` to **0.0050 m**, which
  is the status line's own 2 dp quantisation, so the recomputation is
  sound. `disp` mean +0.0814 / max +0.2793; **cross-track mean +0.1203 /
  max +0.3012**. Mean error was understated by 0.039 m (~48 %).
- **The old metric ranked the lanes backwards.** By `disp`: red +0.0344
  (best) → yellow +0.1472. By cross-track: blue +0.0592 (best), red
  **+0.1249** (second worst), yellow +0.2099. Red arrives +0.127 m
  off-lane and then barely drifts.
- **The +y bias is the policy, not the machine.** Open loop (constant
  `linear.x`, `angular.z` = 0, no policy), 3 trials over **10.05 m**:
  lateral **+0.0000 m**, yaw change **0.00000 rad**. Bare policy, same
  lane: **+0.3115 / +0.3107 m over 6.13 m** (≈ +50.8 mm/m). Bare policy
  teleported to **exactly yaw 0** on the ramp: **+0.0452 / +0.0452 /
  +0.0438 / +0.0438 m** in lanes +0.75 / +0.25 / −0.25 / −0.75 — same sign
  and magnitude on both sides of the centreline. The bias follows the
  robot, not the lane.
- Tests: **253, 0 failures, 0 skipped** (up from 250; `coco_rl` 50 → 53).

**Corrected** (both errors were mine, in text committed last session):
- "Every run ≤ 0.470 m got home" was **circular** — 0.470066 m is simply
  the largest AMCL gap among the successes, so it was true by
  construction. The data brackets the threshold to **(0.470, 1.183) m with
  nothing sampled between**, and supports no stronger claim.
- The half-lane count was **three** runs, not two: run 20 (+0.2581) was
  missed alongside 16 (+0.3012) and 19 (+0.2541).

**Unverified:**
- **No demo video.** See below — it is a tooling gap, not a failed run.
- The bias rate is ~2.5× larger on the flat (50.8 mm/m) than on the grade
  (20.2 mm/m). Unexplained.
- The mechanism behind Nav2 finishing legs outside its own
  `yaw_goal_tolerance` (FUTURE_WORK 8b) is still untested.

**Open:**
- **The video needs a window-manager tool.** `wmctrl` and `xdotool` are
  both absent and `sudo` needs a password. Without one, the Gazebo GUI and
  RViz cannot be placed or raised, so they open behind the fullscreen
  terminal and `x11grab` records the terminal instead of the robot. The
  first attempt was aborted the moment a layout probe showed this, and the
  capture was deleted rather than kept. `~/.gz/sim/8/gui.config` was
  temporarily resized to 952×1000 and has been restored to its original
  1000×845.
- Pushed to **`GauthamCodes/coco-robot-jazzy-2.0` (private)**, a *new*
  repo, as instructed. `origin` (coco-robot-ros2) is untouched and still
  carries only `main` at 34f151c.
- `ramp_driver` still has no `os.path.expanduser` on its `model` parameter.

**Next:**
For the video, one of:

```bash
sudo apt install wmctrl        # then I can tile and raise both windows
```

— or arrange the Gazebo GUI and RViz side by side by hand and say when
they are placed. Otherwise, M7 Phase 1, the MuJoCo throughput baseline:

```bash
source ~/ros2_ws/src/coco-robot-ros2/setup_env.sh
sed -n '/## Phase 1/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

The figure to beat is 8.7 env-steps/s, and that block says to stop and
report if MuJoCo is not meaningfully faster.

---

## 2026-08-07 — Phase 0.5/0.6 closed, history rewritten, published

**Built:**
No new features. History rewritten with `git-filter-repo`, the demo video
published as a release asset, README gains a video link and an attribution
line. Phases 0.5 and 0.6 are closed.

**The rewrite — what it did and did not touch.** Blobs only; **no commit
message was modified**. Two things removed: the 5 `.pyc` blobs that should
never have been committed, and `/home/akshayr2003` (a third party's home
path, present in history but not in the working tree), replaced with
`/home/user`. The superseded `gautham@gmail.com` was replaced with
`gauthamanil888@gmail.com` so the identity is consistent.

Deliberately **kept**: the 106 `Co-Authored-By` trailers and the 26
`Claude-Session:` URL trailers. Both were flagged before the rewrite and
the decision was to leave existing history alone and simply stop adding
trailers from now on. Anyone minding the session URLs being public should
know they are there.

**Verified before pushing** (all six, on the rewritten branch):
- `akshayr2003` anywhere in history: **0**
- authors: **only `GauthamCodes <gauthamanil888@gmail.com>`**
- `.pyc` anywhere in history: **0** (was 5)
- commit count: **128 → 128** (`--prune-empty=never`; no commit touched
  only `.pyc`, so none could have been pruned anyway)
- tracked content vs the pre-rewrite tip: **exactly 2 changed lines in 2
  files**, both `maintainer_email` — i.e. only the intended replacement.
  Note the HEAD *tree* SHA did change (`51af1444` → `137d38c9`), which is
  expected: the email replacement edits tracked files, so byte-identity
  was never achievable and "unchanged tree hash" was the wrong check.
- `colcon build` clean, tests **253 / 0 / 0**

**Published:**
- Public repo `coco-robot-ros2`, branch `jazzy-harmonic-port` at `82a2297`.
  **`main` untouched, still `34f151c`.**
- Private mirror `coco-robot-jazzy-2.0` force-updated to the same SHA;
  local, origin and jazzy2 all agree.
- Release `m6-fetch-demo` with `coco_fetch_demo.mp4` (1920×1004, 75.28 s,
  936 kbps, 8.8 MB). Not in git. Also at `~/Videos/coco_fetch_demo.mp4`.

**Backup — keep this.** `~/coco-backup-20260807-0543.bundle` (4,731,170
bytes), `git bundle verify` reported *"is okay"* and *"records a complete
history"* before anything was rewritten. Pre-rewrite ref state is beside it
in `~/coco-backup-20260807-0543.refs.txt`; the old tip was `d270e77`.

**Measured across Phases 0.5–0.6** (carried forward, all from those runs):
19/20 fetches complete; approach inside the 5.5 mm window **20/20**
(sd 0.6 mm); grasp held **20/20**, lifts 33.9–35.9 mm; cross-track at the
summit mean **+0.120 m**, max **+0.301 m**; entry heading outside Nav2's
own `yaw_goal_tolerance` in **14/20**; constant policy bias **+0.045 m**
with open-loop drive measuring **+0.0000 m** over 10.05 m.

**Unexplained, and this is the honest headline:** the **majority of mission
cross-track drift has no established cause**. The constant policy bias
accounts for ~15 % of the 0.301 m worst case; entry heading covers some
further part at r² = 0.32; the remainder — including the arrival offset of
up to +0.158 m the robot inherits at the ramp foot — is unattributed. Also
open: why Nav2 finishes legs outside its own yaw tolerance (not AMCL error
— estimate and truth agree to 0.076 rad), and why the policy bias rate is
~2.5× larger on the flat than on the grade.

**Next:**
M7 Phase 1 — the MuJoCo throughput baseline. `coco_config` does **not**
currently hold wheel radius, track or masses (they live in the xacro and
`coco_controllers.yaml`), so generating an MJCF "from coco_config" requires
adding them there first, with a test pinning them to the xacro.

```bash
sed -n '/## Phase 1/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-07 — M7 Phase 1: MuJoCo throughput and the fidelity gap

**Built:**
- `coco_config.robot` gains the base physics constants — `WHEEL_RADIUS`,
  `WHEEL_WIDTH`, `WHEEL_MASS`, `WHEEL_SEPARATION`, `WHEELBASE`,
  `CHASSIS_MASS`, `CHASSIS_SIZE`, `WHEEL_SEPARATION_MULTIPLIER` — each with
  its provenance. They were readable only from the xacro and
  `coco_controllers.yaml` before, which was tenable with one simulator and
  is not with two. `test_base_matches_urdf.py` pins them to both sources,
  including deriving the track from where the wheel joints actually sit
  rather than trusting the typed parameter.
- **`coco_sim`** (ament_python): generates the MJCF from those constants.
  `test_mjcf_traces_to_config` rebuilds with a monkeypatched constant and
  asserts the model changed, plus a guard asserting an *unused* constant
  leaves it unchanged — together they make "generated from coco_config" a
  fact rather than a comment.
- **`coco_rl/coco_rl/mujoco_env.py`**: Gymnasium env, shape-identical to
  `ramp_env` (`Box(-1,1,(2,))` action, 8-dim obs, `STEP_DT` 0.1,
  `MAX_LIN` 0.4 / `MAX_ANG` 0.5). Zero `rclpy`, enforced by a hostile test
  that strips ROS from `sys.modules` and poisons `__import__`, with a
  further test asserting the guard itself still raises.

**Measured** (this session, this machine):
- **Throughput**: 1 / 4 / 8 / 12 workers → **805 / 2,126 / 2,791 / 2,826**
  steps/s. Peak **2,826 = 325×** Gazebo's 8.7. Inside M7_DESIGN §5.1's
  2,000–6,000 target, at the low end.
- Scaling **saturates at 8 workers** (8 → 12 buys 1.3 % on 12 cores).
- `SubprocVecEnv` at 1 worker (805) is **slower** than in-process (1,026):
  IPC costs ~22 %, so it only pays from 2 workers up.
- **Attribution, not assertion**: raw `mj_step` = 100,401 physics/s =
  **1,004** control-step equivalents; full env step = **1,026**. They agree
  to ~2 %, so the env loop costs nothing measurable. Combined with the v1
  A/B (8.7 without `--fast`, 8.2 with — unlocking physics made it *worse*),
  the ~118× single-process gain is almost entirely **the removal of the ROS
  round trip**, not MuJoCo's solver. Multiprocessing adds the rest.
- **Fidelity**, identical open-loop sequence, 10 s, ground truth both sides:
  straight leg **0.0779 m error over 1.9874 m (3.9 %)** with yaw matched to
  **0.02°**; arc leg **1.0959 m** and **1.2015 rad (68.8°)**.

**Unverified / unexplained:**
- **Turning does not transfer, and the obvious explanation is wrong.** The
  `wheel_separation_multiplier: 1.10` predicts a yaw ratio of 1.10; the
  measured ratio is **2.902**. Both simulators under-turn a commanded
  2.5 rad (Gazebo 1.833, MuJoCo 0.632) as a skid-steer should, but disagree
  by 2.9×. The remaining ~2.6× is **unexplained**; contact modelling is the
  leading candidate per M7_DESIGN §5.3. **Not tuned** — Phase 1 states the
  divergence, §5.3's calibration is where it gets closed.
- Consequence for Phase 2: straight-line dynamics transfer well enough to
  train against; anything depending on commanded yaw tracking — including
  §4.3's cross-track reward term — will not, until contact is calibrated.
- The MJCF is base-only (no arm, no sensors, no meshes) and its inertias are
  primitive-shape approximations carrying the xacro's masses.
- Carried forward, still open: the majority of mission cross-track drift
  remains unattributed; why Nav2 finishes legs outside its own yaw
  tolerance.

**Open:**
- `mujoco` 3.11.0 and `git-filter-repo` 2.47.0 are `pip --user` installs,
  not in any package manifest. `coco_sim`/`mujoco_env` will not build on a
  machine without them.
- History backup bundle kept at `~/coco-backup-20260807-0543.bundle`.

**Next:**
M7 Phase 2 — The Yard, per `docs/M7_PHASES.md`. Before any policy training,
§5.3's contact calibration is now a stated precondition rather than an
optional step, because of the 2.9× yaw divergence above.

```bash
sed -n '/## Phase 2/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-07 — Phase 1.5: contact calibration, and a Phase 1 number corrected

**Corrected:** the "2.9× yaw divergence" reported in the Phase 1 entry was
roughly half harness error. `fidelity_mujoco.py` sent a **normalised**
action (0.5, scaled by `MAX_ANG` → 0.25 rad/s); `fidelity_gazebo.py`
published a **raw** twist (0.5 rad/s). The two simulators were driven at
different yaw rates. Compared against commanded rather than against each
other, the real gap was ~1.45×. Everything in Phase 1.5 commands both
sides in rad/s.

**Built:**
- Calibrated contact in `coco_sim/mjcf.py`: sliding friction 0.7 → **0.4**,
  `solref` 0.02 → **0.1**, `solimp` d0 0.9 → **0.5**.
- `mujoco_env` now applies `WHEEL_SEPARATION_MULTIPLIER` in its IK, which
  is parity with the deployed `diff_drive_controller` rather than a tuning
  knob — the same `cmd_vel` must mean the same motion in both.
- `M7_DESIGN.md` §2.5 gains a **yaw-gain randomisation term, 0.70–1.45**;
  §5.3 gains the line that transfer is bought by making the policy
  insensitive to steering authority, not by making the engines agree.
- `coco_sim` now declares `mujoco==3.11.0` in `setup.py` and records it in
  `package.xml` (no rosdep key exists). Pinned because the contact fit is
  against 3.11.0's solver.

**Measured:**
- Yaw sweep, 7 magnitudes × both signs, both simulators.
- Gap **worst at the smallest commands**: 1.711× at 0.05 rad, i.e. exactly
  the lane-hold band — and roughly constant proportional loss, not a slip
  nonlinearity (MuJoCo loses ~40 % even at 0.01 rad/s).
- **Calibrated: worst deviation 1.707× → 1.274×.** Target of 1.3× met.
- **Straight-line improved**: 4.1 % → **2.8 %** of distance over 5 s.
- Three hypotheses tested and two killed: anisotropic friction (refuted at
  source — the xacro is isotropic `mu1=mu2=0.7`, no `fdir1`, and warns
  against anisotropy in DART); torsional friction (`condim=3` moved
  achieved yaw 60.6 % → 60.7 %); actuator tracking (servos deliver 98.8 %
  of the commanded wheel-speed difference). The cause is skid-steer scrub,
  and **sliding friction is a weak lever on it** (0.2 → 1.5 moves
  efficiency only 59.5 % → 65.2 %) while contact softness is the strong one.
- **Gazebo is not self-consistent above 1 rad**: its own +/− asymmetry is
  ≤1.014 up to 1.0 rad, 1.174 at 1.5, and **1.361 at 2.5** — larger than
  the 1.3× tolerance being targeted. Comparisons use the magnitude average
  and say so.

**Unverified / open:**
- Residual 1.27×–0.86× is **not closed**, by choice: friction is a weak
  lever and the reference disagrees with itself at the top of the range, so
  further tuning would fit one yaw rate and degrade the model elsewhere.
  Handled by randomisation instead.
- Single Gazebo run per sweep point. At 1.5 and 2.5 rad the sign spread
  exceeds the difference being measured, so those rows are approximate;
  repeats not run.
- Calibration is on a flat plane only. The Yard's grades and heightfields
  are a different contact regime and are not covered by this fit.
- Carried forward: the majority of mission cross-track drift is still
  unattributed; Nav2 still finishes legs outside its own yaw tolerance.

**Next:**
M7 Phase 2 — The Yard, per `docs/M7_PHASES.md`. The contact calibration
that Phase 1 flagged as a precondition is now done for flat ground.

```bash
sed -n '/## Phase 2/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-09 — M7 Phase 2: The Yard in both simulators, and three closeout checks

**Built:**
- `coco_sim/worlds/yard_params.yaml` — the single source of Yard geometry.
  Every rescaled value carries `spec:`, `value:` and `derivation:`.
- `coco_sim/coco_sim/yard.py` — one generator, two engines. Analytic
  `height(x, y)` is the sole truth; both the MJCF and the SDF are emitted
  from the same `features()` list; heightfield STLs written on MuJoCo's own
  triangulation diagonal, which was **measured** rather than assumed.
- `coco_sim/coco_sim/probes.py` — where parity probes go and why there.
- `coco_rl/coco_rl/yard_env.py` — full §2.5 randomisation, applied to a
  compiled model **in place** (no per-episode recompile), reproducible from
  a seed alone.
- `gazebo_models/worlds/coco_yard.world` + `meshes/yard/*.stl`, generated.
  **`coco_world.world` untouched.**
- Tests: **335 passing** (was 250). `coco_sim` 42, `coco_rl` 93,
  `coco_config` 70. The 6 remaining failures are `flake8`/`pep257`/
  `copyright` in `custom_teleop` and `coco_perception` — **pre-existing**,
  verified by re-running them on a stashed tree; neither package was
  touched this session.

**Measured:**
- **Cross-engine parity 0.242 mm worst case** over 264 plumb-bob probes
  dropped in both engines, of which 0.197–0.201 mm is a *constant*
  compliance offset present on flat ground too — **geometric parity is
  0.138 mm**. Concave features genuinely entered: the bridge void drops the
  full 0.650 m in both engines; troughs, depressions and the under-deck
  cavity all agree.
- **Yard throughput at 8 workers: 2,287 / 2,222 / 751 steps/s** on routes
  A / B / C. **Route C is 3.0× more expensive** (the rubble heightfield);
  still above the 500 steps/s stop threshold.
- **Per-route feasibility:** A completable (24/25 at ≤0.65 throttle), B
  marginal (caps at 15/25, friction-limited), C completable but
  throttle-sensitive (23/25 at 0.35, 8/25 at full). A and C fall
  monotonically with throttle, B is flat — torque-limited vs
  friction-limited, cleanly separated.
- **The curb: the spec's 60 mm needs 1.00 m/s, which is 2.5× `MAX_LIN`.**
  Not mountable as this robot is commanded. The built 28 mm needs 0.35 m/s
  (88 % of maximum), and is unmountable at μ = 0.6 — the bottom of Route
  C's own range.
- **Calibration conditioning:** not flat (span 0.113 over μ ∈ [0.30, 0.50],
  9.3 % of the fitted score) and the fitted μ = 0.40 is **not** the
  optimum — μ = 0.30 scores better.

**Found and fixed (defects in already-committed work):**
- `CAMERA_MASS = 0.040` mislabelled; the extra 10 g was the **IMU**. Root
  cause was a test regex that did not handle self-closing `<link/>` tags
  and swallowed the next link's mass. Split, parser fixed, guard added.
- **Neither MuJoCo env limited acceleration**, while the deployed
  controller ramps at 2.0 m/s². Caused wheelies that read as "grippy
  ground is hard to climb". Wired in `yard_env`.
- `torque_scale` scaled `gainprm` but not `biasprm` — a **speed** scale,
  not a torque scale.
- A **curb overhang of my own design** that made the curb unclimbable at
  any speed. Found by the probes; removed.
- The **spawn transient**: only spawning at exactly the wheel radius is
  stable. Spawning 2 mm clear leaves the robot still descending 0.1 s
  later (0.25 s contact time constant, 11.8 mm overshoot); spawning at the
  settled depth throws it 85 mm in the air.

**Unverified / open:**
- **Check 1 is half done.** MuJoCo's yaw efficiency across μ is measured;
  **the Gazebo half was not**, because it needs a world variant per μ and
  `full_world_robo.launch.py` has no `world` argument while
  `coco_world.world` is do-not-touch. **The 0.70–1.45 question is
  unanswered.** Recommendation recorded (narrow the friction
  distribution rather than widen the gain range) but **not acted on**.
- **`refit.py`'s `solref` lever is disconnected** — three values return
  bit-for-bit identical scores, caught by `coco_sim.sweep`. The accepted
  calibration is **not reproducible from the committed harness** (1.211 vs
  the recorded 1.170), and `solimp = 0.9` scores better than the fitted
  0.5. Re-fit with all levers verified before reusing those numbers.
- Non-monotonicity of yaw efficiency in μ is **rate-dependent** and at
  0.50 rad/s, μ = 1.5 the sign inverts. **Hypothesis (labelled): mostly a
  solver artefact** — halving the timestep cuts the high-friction end by a
  third while leaving the low end alone, and a physical optimum does not
  move with the integrator.
- `mujoco_env` still has no acceleration limit; left alone deliberately so
  Phase 1.5's steady-state numbers stay valid. Unify in Phase 3.
- Nothing was trained. Deck traverse open-loop is 0/17, 3/9, 0/8.

**Next:**
Phase 3 — the classical baselines, per `docs/M7_PHASES.md`. Re-fit the
contact calibration first, with every lever asserted connected.

```bash
sed -n '/## Phase 3/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-09 (later) — Phase 2 aftermath: the harness, Check 1 finished, Route C options

**Built:**
- `build_mjcf()` now takes `friction` / `solref` / `solimp` / `timestep` /
  `kv` as **arguments**, defaulting to the committed constants. This is
  the structural fix for the disconnected lever: the old harness swept by
  string-replacing literals in the generated XML, so there is now no
  literal for a sweep to miss.
- `coco_sim/coco_sim/calibrate.py` — the calibration harness, in the
  package and under test, with `audit_levers()`. Reference data committed
  at `coco_sim/reference/yaw_gazebo_baseline.csv`, recomputed rather than
  transcribed. A test forbids `.replace(`/`re.sub(` in the harness source.
- **`world` launch argument** on `full_world_robo.launch.py` (bare name →
  package `worlds/`, absolute path → as given, default unchanged), so
  terrain can be swept without touching frozen files.
- Tests **335 → 348**; `coco_sim` 42 → 55.

**Measured:**
- **All four levers now live** (`friction` 0.2401, `solref` 0.0765,
  `sep_mult` 0.1480, `solimp` **0.0078** — weak but connected, which is a
  different statement from disconnected).
- **The committed calibration does not reproduce as recorded.** `mjcf.py`
  claims worst deviation 1.170×; the committed parameters actually score
  **1.2696 over all seven commands** and 1.2105 over the four the harness
  scores. 1.170 is reachable only over a **two-command subset** — and it
  was compared against Phase 1.5's 1.274×, which was explicitly over
  seven. Like-for-like, the re-fit moved 1.274 → **1.270**: a wash, not an
  improvement.
- **The committed parameters rank 26th of 60.** Best is the same
  solref/solimp at **friction 0.30 → 1.1714**, confirming Check 2's
  finding by an independent route.
- **Check 1 finished. The ratio does NOT stay inside 0.70–1.45** — it
  leaves at 4 of 15 combinations, reaching **0.526**, and sits at 0.709 at
  μ = 0.70 (inside by 1.3 %).
- **Gazebo cannot express terrain friction above 0.7.** Its yaw response
  is two plateaus with one step between μ 0.5 and 0.7, flat at 69.6 / 69.3
  / 69.6 % for μ 0.70 / 0.90 / 1.10 — the wheels are pinned at 0.7 in the
  xacro. So the μ ≥ 0.9 rows compare MuJoCo at 0.9–1.1 against Gazebo
  still at 0.7; that divergence is a definition mismatch, not an engine
  disagreement. Exact mirror of the MuJoCo max-rule bug the `<pair>`
  elements were added to fix.
- **Route C curb, minimum approach speed by height and μ** — 24 mm is
  mountable across the whole of Route C's friction range inside `MAX_LIN`
  (0.35 m/s at μ = 0.6); the built 28 mm needs 0.50 m/s at μ = 0.6.

**Reported, not acted on (awaiting decision):**
- **Route C**: four options with costs — raise `MAX_LIN` to 0.50 (breaks
  the shipped policy's action scale and the 10/10 and 19/20 measured with
  it, and argues against a measured v1 finding); shrink the curb to 24 mm
  (**my recommendation** — confined to Route C, preserves the momentum
  demand at 88 % of `MAX_LIN`); raise the friction floor to 0.8 (halves
  the route's adaptation demand); or drop the curb (removes the world's
  only discontinuity).
- **Friction definition**: fix what μ means in Gazebo *before* touching
  `YAW_GAIN_RANGE`. Raising the xacro's wheel μ is the correct fix and the
  expensive one; capping §2.5 at 0.35–0.70 is the cheap one and rewrites
  Routes A and C.
- **Re-fitting at friction 0.30**: not done. It would change the contact
  model every Phase 2 number was taken through — parity, throughput and
  per-route feasibility would all need re-running.

**Corrections recorded** in `DESIGN_DECISIONS.md`: the quasi-static
"60 mm is impossible" derivation (right regime, wrong question), and the
NavFn "terminates the fill early" explanation (both modes stop at the
start cell — `navfn_planner.cpp:272` passes `atStart=true`; the real
mechanism is `calcPath` abandoning gradient descent for a grid-locked step
whenever any of nine neighbourhood cells is unvisited).

**Unverified / open:**
- The 24 mm margin (0.35 against 0.40, **12 %**) was measured on a **flat
  run-up**, not over 2.17 m of heightfield. Not measured.
- Gazebo's ± yaw asymmetry is ~1.35× at 2.5 rad **at every friction**.
- `mujoco_env` still has no acceleration limit.

**Next:**
Decisions pending on Route C and on the friction definition. Phase 3 —
classical baselines — after those, per `docs/M7_PHASES.md`.

```bash
sed -n '/## Phase 3/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-09 (later still) — three decisions applied, and the state at restart

**Note on coverage.** The phases requested for this checkpoint already have
their own entries above and are not repeated: Phase 0.5/0.6 close-out and
the history rewrite (2026-08-07), M7 Phase 1 (2026-08-07), Phase 1.5
(2026-08-07), Phase 2 (2026-08-09), Phase 2 aftermath (2026-08-09). This
entry covers the decisions applied on top of them, and ends with a single
state-of-play block for picking the work back up.

**Decided and applied:**

1. **Route C curb 28 mm → 24 mm**, validated on the ACTUAL 2.17 m rubble
   run-up rather than flat ground. In situ it needs **0.50 of 1.00
   throttle** across Route C's range — **2× margin**, not the 12 % the
   flat measurement implied. The flat figure was **pessimistic**: the
   robot arrives already pitched nose-up by the 16° grade, which lifts the
   wheel's contact relative to the step. Constraint recorded: at μ = 0.35
   neither 24 nor 28 mm mounts at any throttle, so Route C's 0.50 floor is
   now load-bearing.
2. **Calibration NOT re-fitted.** Parameters stand at 0.4 / 0.25 / 0.5.
   `mjcf.py` and RESULTS.md now record **1.2696× over the seven measured
   commands** (inside the 1.3× target) with the scope stated. The old
   "1.170×, better than 1.274×" was scope-free and not a comparison —
   **like-for-like the re-fit was 1.274 → 1.270, a wash.** Friction 0.30
   at **1.1714** recorded as known-better-and-not-adopted, because
   re-fitting changes the contact model every Phase 2 number was taken
   through.
3. **§2.5 friction narrowed 0.35–1.10 → 0.35–0.70**, reasoning in
   M7_DESIGN §2.5. Per-route ranges **re-derived, not clipped** (A
   0.55–0.70, B 0.35–0.70, C 0.50–0.70) because Route A's old range lay
   entirely at or above the cap. **Check 1 re-run: 12 of 12 combinations
   inside 0.70–1.45**, span 0.709–1.142.

---

### State of play at restart

**MEASURED and standing:**
- MuJoCo throughput **3,712 steps/s at 8 workers = 427×** (flat model);
  Yard **2,287 / 2,222 / 751** on routes A / B / C — Route C 3× dearer.
- Cross-engine parity **0.242 mm** worst case over 264 settle probes;
  **0.138 mm geometric** once the 0.197 mm constant compliance offset is
  removed.
- Contact calibration **1.2696× worst over seven commands**, inside 1.3×.
- Per-route open-loop ascent: A completable (24/25 at ≤0.65 throttle), B
  marginal (15/25, friction-limited), C completable but throttle-sensitive
  (23/25 at 0.35 throttle, 8/25 at full).
- Curb: spec 60 mm needs **1.00 m/s** = 2.5× `MAX_LIN` (not reachable);
  built 24 mm needs **0.50 throttle in situ**.
- Yaw ratio across the narrowed friction range: **0.709 – 1.142**, inside
  `YAW_GAIN_RANGE`.
- **349 tests passing.**

**BROKEN:**
- Nothing known-broken in the harness. `refit.py`'s disconnected `solref`
  lever — three values returning bit-for-bit identical scores — was fixed
  at the cause in `5785b28`: `build_mjcf()` takes contact parameters as
  arguments, the harness is `coco_sim.calibrate` with `audit_levers()`,
  and a test forbids the string-replacement idiom. All four levers
  audited live.
- **Pre-existing and not ours:** 6 `flake8`/`pep257`/`copyright` failures
  in `custom_teleop` and `coco_perception`, confirmed on a stashed tree.

**UNMEASURED:**
- The 0.70–1.45 yaw-gain question is **answered** for the narrowed range
  (12/12 inside). What remains unmeasured: whether raising the xacro's
  wheel μ would let Gazebo express the original 0.35–1.10 — that needs
  v1's 10/10 and 19/20 re-checked on a different surface pairing.
- IMU noise σ: the xacro declares no `<noise>` element, so there is
  nothing to match. Sampler applies zero.
- Deck traverse beyond ascent: open loop is 0/17, 3/9, 0/8.
- `mujoco_env` still has no acceleration limit (deliberate — Phase 1.5's
  steady-state numbers were taken through it).

**UNDECIDED:**
- Nothing blocking. Route C is decided (24 mm, in-situ validated). The
  calibration is decided (not re-fitted). The friction range is decided
  (0.35–0.70).
- Open but not blocking: `YAW_GAIN_RANGE`'s floor sits **1.3 % above** the
  measured minimum ratio of 0.709. Widening it to ~0.60 would restore
  margin; not changed.

**Next:** Phase 3 — the classical baselines, `docs/M7_PHASES.md`
unchanged.

```bash
sed -n '/## Phase 3/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-09 (Phase 3) — the classical baselines, and one claim refuted

**Built:**
- `coco_rl/coco_rl/lateral.py` — `lateral_hold` and its gains, moved out of
  `ramp_driver` **unchanged**, so B1 can import the shipped function
  without dragging `rclpy` into the training environment.
  `test_ramp_driver.py` reaches it through `ramp_driver` and passes
  untouched.
- `coco_rl/coco_rl/baselines.py` — B0 / B1 / B2 and the shared reference
  path, with the **tuned** B2 schedule committed alongside.
- `coco_rl/coco_rl/baseline_eval.py` — the runner and a failure taxonomy
  that is *measured*: `slid back` and `high-centred` both look like a
  timeout if you only read the terminator, and they are what separates a
  friction failure from a geometry one.
- Tests **349 → 361**.

**Measured (120 episodes per cell, 1,080 total; B2 tuned on seeds
10000–10011, evaluated on 0–119, disjoint):**

| | A success | B success | C success |
|---|---|---|---|
| B0 open-loop | 0 % | 8 % | 0 % |
| B1 shipped PD | 0 % | 2 % | 0 % |
| **B2 scheduled PD** | **98 %** | 3 % | 15 % |

- **Claim 1 (camber needs adaptation) is REFUTED.** Measured on the ramp,
  where camber actually acts: B2 holds **1.26 cm mean / 6.66 cm worst**
  across camber 0–8°, four times inside the 5 cm falsifier, **with no
  trend in camber** (1.39 / 1.05 / 1.23 / 1.31 cm). Even B1, un-retuned,
  averages 3.79 cm. **This changes what M8 should be:** Route A's
  contribution is now the deck convergence and the bridge, not the camber,
  and 98 % is the number a policy has to beat there.
- Claim 2 (friction) **stands** — B1 gets 0 % below μ 0.55 and 9 % at the
  top, 2 % overall, against a ≥90 % falsifier.
- Claim 3 (curb) **stands for the 60 mm spec step** (needs 1.00 m/s =
  2.5× `MAX_LIN`) but is **refuted at the built 24 mm**, which B2's fixed
  schedule mounts across the whole friction range.
- Claim 4 (washboard) **stands** — constant throttle crosses only below
  ~0.14 m/s and tips at ≥0.22 m/s.
- Claim 5 (loaded descent) **not tested** — the Phase 3 task ends at the
  bay, so the descent is never exercised.

**Found and fixed:**
- **Bridge falls were being reported as tips.** The detector waited for
  z < 0.30 m, by which point the robot had rolled 43° on the way down and
  the tip terminator had fired — measured at z = 0.610, two control steps
  after it left the deck. Now positional. One of the five failure modes
  this phase must report, so it would have mislabelled a whole column.
- **B2 was under-tuned on the first pass and lost to B0 on Route B**
  (0 % vs 8 %), because the grid searched throttle only to 0.65 and never
  tried what a 26° chute needs. Re-searched to 1.0: A 88 → 98 %, B 0 → 3 %,
  C 7 → 15 %. Exactly the "a weak B2 makes the entire M8 result worthless"
  failure §3.1 warns about.

**Unverified / open:**
- Claim 4's measurement establishes that constant throttle fails above a
  speed threshold; it does **not** separate resonance from plain
  over-speed. Rows above 0.4 m/s are post-tip tumbling.
- Route C tips 101/120 under B2 at the **lowest** cross-track of any cell
  (0.035 m). Not a steering failure — the rubble pitches it over — and the
  mechanism is not isolated.
- Claim 5 needs the descent added to the task before it can be tested.
- Route B is unsolved by every baseline (best 8 %, by B0 of all things).

**Next:** Phase 4 — policy training, `docs/M7_PHASES.md`. Note that Phase
3 has narrowed what M8 can claim: camber is off the table.

```bash
sed -n '/## Phase 4/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---

## 2026-08-09 (Phase 3 close-out) — the two routes diagnosed, and what gates Phase 4

Written for a cold start: assume only the repo, no memory of this session.

**MEASURED — standing results**

- **Phase 3 baseline matrix**, 1,080 episodes (120 per baseline per route).
  B2 tuned on seeds 10000–10011, evaluated on 0–119, disjoint.

  | | Route A | Route B | Route C |
  |---|---|---|---|
  | B0 open-loop | 0 % | 8 % | 0 % |
  | B1 shipped PD | 0 % | 2 % | 0 % |
  | B2 scheduled PD (privileged) | **98 %** | 3 % | 15 % |

- **Claim 1 REFUTED.** On the ramp, where camber acts, a retuned PD holds
  **1.26 cm mean / 6.66 cm worst** across camber 0–8°, four times inside
  the 5 cm falsifier, **with no trend in camber**. Camber alone is not
  evidence for learning; Route A's contribution to M8 is now the deck
  convergence and the bridge, and 98 % is the bar.
- **Claim 3 REFUTED at 24 mm** (the height the world contains — B2's fixed
  schedule mounts it across the whole friction range); stands only at the
  60 mm spec step, and there only because 60 mm needs 2.5× `MAX_LIN` and
  is outside the action space.
- **Claims 2 and 4 stand.** Claim 2 with a wide margin: B1 gets 0 % below
  μ 0.55, 2 % overall, against ≥90 %.
- **Claim 5 not tested** — the Phase 3 task ends at the bay, so the loaded
  descent is never exercised.
- Earlier phases: MuJoCo throughput **3,712 steps/s at 8 workers (427×)**;
  cross-engine parity **0.242 mm** worst case, **0.138 mm geometric**;
  contact calibration **1.2696× over seven commands**, inside the 1.3×
  target; Yard throughput 2,287 / 2,222 / 751 on A / B / C.
- **361 tests passing.**

**BROKEN**

- Nothing known-broken in the code. The `refit.py` disconnected-lever
  defect was fixed at the cause (`5785b28`); all four calibration levers
  audited live.
- **Pre-existing, not ours:** 6 `flake8`/`pep257`/`copyright` failures in
  `custom_teleop` and `coco_perception`, confirmed on a stashed tree. Run
  tests **per package** — several packages share test module names and a
  single pytest invocation dies with `ImportPathMismatchError`.

**UNMEASURED**

- The tipped-vs-completed correlation on Route C. The diagnostic harness
  omitted the completion check `baseline_eval` uses, so it recorded 0
  completions where the matrix records 18; the tip *characterisation* is
  unaffected but the correlation was not obtained.
- The 24 % of Route C tips in the **first quarter** of the ramp — a
  separate population from the 65 % at the curb, not explained by the
  terminator mechanism, not diagnosed.
- Claim 4's measurement shows constant throttle fails above ~0.22 m/s but
  does **not** separate resonance from plain over-speed.
- Claim 5 needs the descent added to the task.
- Whether raising the xacro's wheel μ would let Gazebo express the
  original 0.35–1.10 friction range (would require re-checking v1's 10/10
  and 19/20 on a different surface pairing).

**UNDECIDED — all three gate Phase 4**

1. **The deck convergence geometry.** The deck demands up to **1.95 m of
   lateral shift in 1.80 m of travel** before a 0.65 m bridge, against a
   0.40 m minimum turn radius at 0.2 m/s. B1 tracks the lane well, reaches
   the deck 99 % of the time, and then **falls off the bridge 105 times in
   120**. B2 only clears it by slowing to 0.6 deck throttle. Options not
   explored: lengthen the deck before the bridge, move the routes closer
   in y, or widen the bridge. **Nothing changed.**
2. **Route B's viability.** Best success is 8 %, by B0. **39.3 % of its
   episodes have μ < tan(grade) and are physically unclimbable** — no
   controller can help, and it matches the observed `slid back` counts.
   Four options costed in RESULTS.md (reduce grade to 19–22°, widen — which
   does not address it, raise the friction floor to 0.55 at the cost of
   narrowing 2.00× → 1.27×, or drop the route and lose claim 2's only
   home). **None chosen.**
3. **Route C's tipping mechanism.** 101/120 tips are **pitch events, 0 of
   101 roll-dominated**, 65 % at the curb approach. `TIP_LIMIT` is 0.6 rad
   **absolute**; the 16.3° grade consumes 16.3° of it, leaving 18.1°, and
   the measured excursion is 20.6° — while the robot's **true static
   rear-over is 54.5°**. The terminator fires 34° short of falling over,
   on the very manoeuvre that mounts the curb. **This is instrumentation,
   not control.** The fix (measure tip relative to the local surface
   normal) is **not applied**, because `TIP_LIMIT` is shared with
   `ramp_env`, the v1 curriculum and the shipped policy's training
   conditions.

**Next:** these three decisions, then Phase 4 (policy training). Phase 3
has already narrowed what M8 can claim — camber is off the table, and two
of the three routes currently fail for reasons a policy cannot address.

```bash
sed -n '/## Phase 4/,/^```$/p' ~/ros2_ws/src/coco-robot-ros2/docs/M7_PHASES.md
```

---
## 2026-08-16 — COCO 2.0 M1: observability, and three defects only a live run could find

Written for a cold start: assume only the repo, no memory of this session.

**Context change.** Work continues under a new plan (COCO 2.0) whose
milestone 1 is visualisation and mission observability, ahead of any
further terrain-control or RL work. M7 Phase 4 is therefore **not**
started, and the three decisions gating it (deck convergence geometry,
Route B viability, Route C tip instrumentation) are **still open and
unchanged**.

**Built**

- `coco_mission/scripts/mission_hud.py` — subscribes 10 status topics and
  renders one block on `/mission/hud` at 2 Hz. Subscribe-only; publishes
  nothing any other node reads, so it cannot affect a run. Ages come from
  a steady clock, not `/clock`, so it keeps marking sources stale even if
  sim time stops.
- `gazebo_models/rviz/mission.rviz` — 14 displays, fixed frame **`map`**.
  A NEW file. `coco_robot.rviz` is deliberately untouched: it is loaded by
  `rsp.launch.py` where `base_footprint` is the only frame that exists.
- `/mission/state` from `traverse_demo` (step labels, previously stdout
  only) and `/mission/goal` from `mission_hud`.
- `coco_mission` gains a pytest suite: **30 new tests, all passing**.
  (The earlier commit message in this branch says "361 -> 391". That
  arithmetic assumed the documented 361 baseline still held. It does
  not — see below.)

**Measured**

- Two full fetch missions, fresh sim each, `--colour blue`.
  Run 1 **FAILED** at nav-home (vision unconfirmed, `found=0`,
  cross-track `+0.52 m` at climb end). Run 2 **FETCH COMPLETE**, approach
  arrived **0.4 mm** from window centre (base-x 0.1541 vs 0.1537), home
  to within **0.06 m**. **1 of 2 is not a success rate and is not offered
  as one** — the standing M6 figure remains 19/20 from a dedicated matrix.
- Every RViz display topic and every HUD input probed live. Full table in
  `RESULTS.md`, "M1 observability".
- `rviz2 -d mission.rviz` against the live stack: **zero** plugin, type or
  QoS errors; three occupancy grids created (`243x175` twice, `60x60`),
  which is evidence those displays received real data.
- AMCL covariance ~0 before motion (yaw **1.09e-13**), growing to
  **sigma x 0.229 m** while driving and **0.452 m** at the platform.

**The documented 361-test baseline does not currently hold**

Measured per package with cwd set to the package dir: **375 passing, 29
failing.** All 29 are in `coco_rl`, they reproduce **identically on an
unmodified checkout**, and every one is `FileNotFoundError:
.../ros2_ws/build/coco_sim/worlds/yard_params.yaml`. That directory does
not exist; the file is present in source. The workspace's `coco_sim`
build is stale. Fix, **not applied** (it is the user's workspace):

```bash
cd ~/ros2_ws && colcon build --packages-select coco_sim
```

Separately, three packages score **higher** than CLAUDE.md recorded —
`custom_teleop` 67 (not 64), `coco_perception` 44 (not 41),
`coco_moveit_config` 12 (not 5). The six "pre-existing"
flake8/pep257/copyright failures and the seven missing
`coco_moveit_config` tests were an artefact of invoking pytest from the
repo root, where the `coco_rl/` directory shadows the installed module.
With the correct cwd they pass. CLAUDE.md corrected.

**Found and fixed**

1. `mission_hud.py` lacked the executable bit. With
   `--symlink-install` that aborted all of `mission.launch.py`, which
   SIGINT'd six nodes mid-import and surfaced as a numpy/rclpy
   `ImportError` storm in healthy processes. Cause was a file permission.
2. **`ros_clean.sh` had no `mission_hud` pattern** — same trap its own
   header documents for `parameter_bridge`. Two HUDs published
   `/mission/hud` at once and the stale one won often enough to make a
   fixed field look unfixed. **Anything added to a launch file must be
   added to `ros_clean.sh`.**
3. `/goal_pose` is advertised and **never publishes** in an autonomous
   run — the sequencer uses the `NavigateToPose` action, and
   `/goal_pose` is RViz's own goal tool only. Replaced with
   `/mission/goal`, derived from the end of the global plan.
4. `LOCALIZATION` showed `STALE` and hid the sigmas while the robot was
   correctly localised, because AMCL publishes only after
   `update_min_d 0.25 m`. Age is no longer staleness for that field.

**Unverified / open**

- Run 1's `+0.52 m` climb cross-track: variance, regression, or
  `lateral_hold` not engaging. **Not diagnosed.**
- `ROBOT PITCH` read `-0.314 rad` during the platform approach, where the
  robot should be flat. Either genuine, or `/ramp/status`'s `pitch` is
  held from the climb while the driver is idle. **Not diagnosed**, and it
  matters for M2's grade estimator.
- The rendered RViz window has never been visually inspected or recorded.
- `rviz_2d_overlay_plugins` is not installed, so `_publish_overlay` has
  never executed. Install with
  `sudo apt install ros-jazzy-rviz-2d-overlay-plugins`.
- M7 Phase 4 and its three gating decisions remain untouched.

**Next:** decide whether to install the overlay plugin and record the
demo, or move to COCO 2.0 milestone 2 (terrain control: tip-termination
correction, grade and friction estimators, observer-driven controller).
Note that milestone 2's first item is the same Route C tip-instrumentation
decision M7 Phase 3 left open.

```bash
# reproduce the M1 verification
bash gazebo_models/scripts/ros_clean.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false   # T1
ros2 launch coco_mission mission.launch.py \
    policy:=/home/gautham/coco_rl_runs/curriculum_20260726_211008/phase5_24deg_s0p0.zip \
    rviz:=true                                                                   # T2
ros2 run gazebo_models traverse_demo.py --colour blue                            # T3
ros2 topic echo /mission/hud --field data                                        # T4
```

---
## 2026-08-16 (checkpoint) — persistent state files added, C2-M1 closed

*This entry keeps this file's Built/Measured/Unverified/Open/Next fields
and adds the Objective/Commands/Interpretation fields the COCO 2.0
handoff protocol asks for. Both are satisfied; the file's format is not
broken.*

**Objective:** establish repository-authoritative state files so a fresh
agent with zero conversation memory can continue, and formally close
COCO 2.0 milestone 1. No hypothesis — this is bookkeeping, not an
experiment.

**Built:**
- `PROJECT_STATE.md` (new, repo root) — the authoritative snapshot.
- `docs/ROADMAP.md` (new) — all three milestone tracks with completion
  criteria and measured results.
- No source changes.

**Commands run:**

```bash
git status --short                # clean but for untracked .build_wt/ .install_wt/
git rev-parse --abbrev-ref HEAD   # worktree-coco2-m1-observability
git log --oneline -3              # dfcc49c, 0766781, 22c793c
# per-package pytest, cwd = package dir
```

**Measured — and this checkpoint produced a real result:**

Re-running the suite showed `coco_rl` at **106 passed, 0 failing**, not
the 77/29 recorded earlier the same day. The difference is that this
worktree's overlay build of `coco_sim` had since been created, which
produced the `worlds/` directory the tests were looking for. Re-running
against the unmodified main checkout still gives 77/29. So:

| `coco_sim` build | `coco_rl` |
|---|---|
| stale (the user's `~/ros2_ws`) | 77 passed, 29 failing |
| fresh (this branch's overlay) | **106 passed, 0 failing** |

That turns the earlier diagnosis from a hypothesis into a **measured
fix**, and takes the suite to **404 passing / 0 failing**. `CLAUDE.md`,
`RESULTS.md` and `PROJECT_STATE.md` updated from 375/29 to 404/0 with
the precondition stated.

**Unverified:** the rebuild has **not** been applied to the user's
`~/ros2_ws` — that is theirs to run. Until they do, their tree still
shows the 29.

**Interpretation / decisions:**

- **The session log stays at `docs/SESSION_LOG.md`.** The handoff
  protocol names a root-level `SESSION_LOG.md`, but this file already
  holds 1000+ lines and `CLAUDE.md` points here. A second log would
  fragment history, which is worse than a naming deviation.
  `PROJECT_STATE.md` states the location in its read-order section.
- **Milestone IDs are now namespaced `C2-`.** The COCO 2.0 plan's
  milestone numbers collide with the repo's existing M0–M7 — "M2" could
  mean the v1 world rebuild or COCO 2.0 terrain control. `PROJECT_STATE.md`
  and `docs/ROADMAP.md` both lead with this.
- **`docs/ROADMAP.md` carries all three tracks**, not just COCO 2.0,
  because M7 Phase 4's three gating decisions are the same decisions
  C2-M2 has to take. Splitting them across files would hide that.

**Failures:** none this checkpoint.

**Open (carried forward, all unresolved):** the stale `coco_sim` build
(29 failing tests, one colcon command, deliberately not applied because
it mutates the user's workspace); run 1's `+0.52 m` climb cross-track;
the `-0.314 rad` `ROBOT PITCH` during the platform approach; the three
M7 Phase 4 decisions.

**Next:** clear KNOWN PROBLEM #1, then diagnose #4, then take the
Route C tip-terminator decision — which is C2-M2's first item.

```bash
cd ~/ros2_ws && colcon build --packages-select coco_sim
cd ~/ros2_ws/src/coco-robot-ros2/coco_rl && python3 -m pytest test -q
```

---
## 2026-08-17 — the persistence layer moved to the trunk

**Objective:** fix the branch architecture of the state files. No C2-M1
implementation touched.

**Built:** nothing new. Two files *moved* branches.

**The defect:** `PROJECT_STATE.md` and `docs/ROADMAP.md` were committed
on this feature branch (`625a659`). Both describe the *project*, not the
branch, which broke the handoff protocol in two ways:

1. **A fresh agent checking out the trunk saw no state at all.** The
   whole point of the protocol is that clearing the conversation is safe.
   It was not — the state was hiding on a branch nobody had been told to
   check out. Flagged at the end of the previous session; this fixes it.
2. **They are singleton mutable snapshots.** Any second feature branch
   that checkpoints rewrites the same lines and conflicts on every merge,
   forever. Not a merge accident — the predictable result of
   version-controlling a "current value" on parallel branches.

**Result:**
- New commit `6c06c45` on branch `coco2-state`, based directly on the
  trunk (`33110a6`), carrying `PROJECT_STATE.md`, `docs/ROADMAP.md`, the
  new `docs/STATE_PROTOCOL.md`, a "State first" pointer at the top of
  `CLAUDE.md`, and the `.gitignore` entry. It **fast-forwards** onto
  `jazzy-harmonic-port`.
- This commit deletes those two files from this branch, so the two
  branches no longer both own them and the C2-M1 merge stays clean.

**Interpretation / decisions:**
- **The trunk, not a long-lived `state` branch.** A parallel state branch
  would have to be merged into every feature branch to be readable from
  them — strictly more work than keeping state where a fresh agent
  already lands, and more likely to go stale.
- **`PROJECT_STATE.md` gained a BRANCH MAP.** That table is what makes
  trunk-only state honest: the trunk does not *contain* the C2-M1 code,
  but it always *knows where it is*, and says so before a reader can
  mistake a missing `coco_mission` package for a bug.
- **`docs/SESSION_LOG.md` stays shared and append-only**, and is
  deliberately not touched on `coco2-state`. Two tails on two branches
  would manufacture exactly the conflict this work removes. Append-only
  files conflict only at the end and resolve as "keep both, in date
  order".
- **`CLAUDE.md` is edited on both branches on purpose, in different
  hunks** — "State first" at the very top here, the Tests baseline far
  below there — so git auto-merges them instead of conflicting.

**Measured:** none. No runs; no code changed. Tests not re-run because
no source, test or launch file was modified — `git diff --stat` against
the previous commit is two deletions, both Markdown.

**Unverified:** the merge itself. `coco2-state` fast-forwards onto the
trunk by inspection (one commit, direct descendant of `33110a6`), and
the C2-M1 merge is expected clean now that the overlap is gone, but
**neither merge has been performed** — merging is the repo owner's call.

**Open:** unchanged — the stale `coco_sim` build, run 1's `+0.52 m`
cross-track, the `-0.314 rad` `ROBOT PITCH`, and M7 Phase 4's three
decisions.

**Next:** land the state layer on the trunk, then decide on C2-M1.

```bash
cd ~/ros2_ws/src/coco-robot-ros2
git checkout jazzy-harmonic-port
git merge --ff-only coco2-state
git ls-tree --name-only HEAD PROJECT_STATE.md docs/ROADMAP.md   # both must list
```

---

---
## 2026-08-17 — C2-M1.5: the HUD's pitch was a fossil, and the failed fetch was two failures

**Objective:** a runtime-integrity and signal-semantics gate before C2-M2.
C2-M2's first deliverable is a grade estimator, and C2-M1 had left the one
field it would be built on undiagnosed. Diagnose only; fix only what the
diagnosis proves. No C2-M2 implementation, and none was started.

**Hypotheses under test, all pre-registered by the previous checkpoint:**
(A) what diverged first in the failed fetch of 2026-08-16; (B) what
`ROBOT PITCH = -0.314 rad` actually was; (C) whether `/approach/target`'s
one-shot VOLATILE publication is a defect.

**Built**

- `gazebo_models/scripts/pitch_probe.py` — new, subscribe-only. Puts every
  pitch-shaped signal in one CSV at 10 Hz with timestamps: `/ramp/status`'s
  `pitch`, `/imu`, ground-truth odometry orientation, `/mission/state`, and
  the number parsed back off `/mission/hud`. Two independent ground truths
  on purpose, so "the IMU is lying" and "the field is stale" stay
  separable. Installed in `CMakeLists.txt`; `pitch_prob[e]` added to
  `ros_clean.sh`.
- Ten new tests: `coco_rl` 106 -> **109**, `coco_mission` 30 -> **37**.

**Commands run**

```bash
# baseline, per package, cwd = the package dir
for p in coco_config custom_teleop coco_rl coco_perception gazebo_models \
         coco_moveit_config coco_sim coco_mission; do (cd $p && pytest test -q); done
# three live runs, fresh sim each, ros_clean between, gui:=false, never --fast
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py policy:=<phase5_24deg_s0p0.zip> rviz:=true
ros2 run gazebo_models pitch_probe.py --out /tmp/pitch.csv --hz 10
ros2 run gazebo_models traverse_demo.py --colour blue            # exp 1
ros2 run gazebo_models traverse_demo.py --colour blue --no-grasp  # exp 2
ros2 topic info -v /approach/target                               # exp 1, live
```

**Measured — (B), the pitch. This was the gate and it is now closed.**

`ramp_driver` writes `self.pitch` only inside its climb and descend loops.
Between segments nothing assigns it, while the 5 Hz status timer keeps
publishing it. The message is never late; the number in it is minutes old.
Over one full fetch, 1,900 samples:

| step | `segment` | `/ramp/status` pitch | `/imu` | max diff |
|---|---|---|---|---|
| 2. RL climb | climb | −0.314 .. 0.000 | −0.315 .. 0.000 | 0.140 (sampling skew) |
| 3. approach the target | idle | −0.314 | −0.314 .. +0.000 | **0.314** |
| 4. pick it up | idle | −0.314 | +0.000 | **0.314** |
| 6. nav home | idle | −0.000 | −0.217 .. +0.004 | **0.217** |

`/ramp/status`'s pitch changed **21 times in 1,899 sample pairs**; `/imu`
changed 144. It held one value for **79.2 s** while the robot pitched to
−0.217. `/imu` and ground-truth odometry agreed to 3 dp everywhere, so the
sensor was never in question.

**Diagnosis: stale ramp-driver state** — option B of the five. Three things
matter more than the label:

1. `-0.314` is genuine *at its sample instant*. `RAMP_ANGLE_DEG = 18`, and
   18° = **0.31416 rad**. The reading is the ramp, exactly.
2. It is *always* the ramp grade, structurally: the climb stops
   `GOAL_MARGIN = 0.3` m short of the crest, so the last sample is taken
   on the uniform 18° face, quasi-statically, where body pitch and surface
   grade coincide. **A grade estimator built on this field would have
   matched ground truth on every metre of ramp and then reported 18° on
   flat ground forever.** It would have passed its own tests.
3. The C2-M1 note's premise was itself half wrong. The robot is *not* flat
   when the approach begins — `/imu` independently reads −0.314 there. It
   levels *during* the approach, and that is where the field stops
   tracking.

**Measured — (A), the failed fetch.** `~/.ros/log` still held both
2026-08-16 runs, with timestamps, so this needed no re-running.

*First divergence: inside the RL climb, and nothing before it.*
`climb finished: ... disp +0.51 m, cross-track +0.524 m`. Cross-track minus
disp is **+0.014 m** — Nav2 delivered the robot to within 14 mm of the blue
lane centreline and the entire 0.51 m accumulated during the climb.
`lateral_hold` was **on and reached its clamp** (peak 0.800 = exactly
`LATERAL_CLAMP`), so "lateral_hold not engaging" is **refuted**. It does
not follow that the clamp was binding: the 2026-08-17 run also peaked at
0.800 and finished at cross-track +0.036 m. Saturation happens on good
climbs too.

*`found=0` is a consequence.* Logged **3.0 s after** the climb ended, with
the robot 0.52 m off a lane grid of 0.5 m spacing, and `seen=blue,yellow`
is the wrong-lane signature `target_finder` documents itself. Blue was in
frame; `_locate` rejected it on either the 0.15–2.00 m range gate or the
`plausible_blob` width check — **which one is not determined**, because the
status line records `found=0` and not the reason.

*The step that actually ended run 1 was nav home, and it is independent.*
A 2026-08-17 run with a clean climb, vision CONFIRMED and a successful pick
(x=0.1537, dead on the window centre) **still failed at nav home**, and not
even the same way:

| | run 1 | run 3 (2026-08-17) |
|---|---|---|
| AMCL at leg start | map (8.07, −2.33) vs truth ≈(8.65, +0.84) → **≈3.2 m** | (9.11, 0.06) vs (8.66, 0.25) → 0.45 m |
| ending | `bt_navigator: Goal failed` at 76.1 s | client 240 s timeout, goal cancelled |
| symptoms | — | 11× `Failed to make progress`, 2× Spin timeout, repeated `collision_monitor: PolygonStop` |
| stopped at | (4.74, −2.90) | (0.53, 0.73), **2.59 m short**, stationary 49.7 s |

Run 1 is the AMCL-divergence family (M6 run 15; `M7_DESIGN.md` §2.7 item 1,
the EKF). Run 3 is not. **Confound stated:** run 3 logged `Control loop
missed its desired rate of 10.0000 Hz. Current loop rate is 4.8077 Hz`
with Gazebo, RViz, move_group and the probe all running. Not isolated.

Nav-home across the four recorded legs: FAILED, SUCCEEDED, FAILED,
SUCCEEDED (traverse-only, home to **0.10 m**). Carrying the cylinder splits
one-one across both outcomes. **Four runs are not a success rate and none
is offered** — the standing figure is M6's 19/20. What they do establish is
that nav home fails for reasons that are not downstream of the climb or of
vision. **That is C2-M5's** (localisation health and recovery), which
already names M6 run 15 as its benchmark.

**Measured — (C), `/approach/target`. No change made.** `ros2 topic info
-v` on the live stack: publisher `approach_server` RELIABLE/VOLATILE,
subscribers `grasp_server` and `rviz2`, QoS compatible, one message per
approach. TRANSIENT_LOCAL would be a **defect, not a fix**: the payload's
frame is `base_footprint`, so latching it hands a late joiner a coordinate
in a frame that has since moved. And there is no reliability hole to close
— both nodes start together from `mission.launch.py`, and `grasp_server`
gates on `APPROACH_FIX_MAX_AGE = 120 s` and otherwise warns and grasps at
the nominal stop pose. The `PROJECT_STATE.md` "future idea" to make it
TRANSIENT_LOCAL is **dropped, not deferred**. The real mismatch is that
this is the *result of* `/approach/run` and a `Trigger` response cannot
carry a point; that belongs to **C2-M3**, when actions replace the Trigger
services.

**Found and fixed**

1. **`ramp_driver` publishes `pitch=--` while idle**, matching the `--`
   that `lateral` already used for "no lane, so no cross-track". The
   segment-final sample moved into the `climb finished` / `descend
   finished` log line, so the datum is filed under a timestamp instead of
   broadcast as current.
2. **`mission_hud` takes `ROBOT PITCH` from `/imu`**, BEST_EFFORT, aged
   like every other field, printed in radians and degrees. Body attitude
   was never the ramp driver's to publish, and routing it through the node
   that runs the policy meant the field could only be alive during two of
   the mission's seven steps.

Verified live on a fresh traverse: `pitch=--` before any segment and after
both; `ROBOT PITCH +0.000 rad (+0.0 deg)` on the flat; `-0.315 .. +0.000`
during the climb and `-0.314 .. +0.314` during the descent, tracking `/imu`
to within one sample. `/ramp/status` held `--` for **148.7 s** of nav home,
the interval that used to carry a stale number.

**RViz — inspected for the first time.** Five screenshots of the rendered
window across live missions. Working by inspection: global plan (a legible
green line), camera framing of the target, goal arrow, laser scan, Global
Status Ok, 14 displays in 3 groups. The occupancy map's wall cells sit
under the global costmap's inflation, which is ordinary Nav2 appearance and
not a defect.

**One objective defect, fixed:** the robot leaves the viewport. At
`Distance: 9` / `Focal Point (1.5, 0)` it was near centre at startup,
clipped at the bottom-right on the outbound leg, and off-screen entirely
during the descent and the drive home. The focal point moved to the
**centre of the map** — `(3.956, -0.535)`, computed from
`maps/coco_world.yaml`, which the old value was not in either axis — and
`Distance` was swept against the rendered window on one live stack:
**14 overflows, 18 fits with margin, 22 is a postage stamp**. Shipped at
18. Acceptance test, a property of the config rather than of a run: the
whole occupancy map is inside the viewport, so every reachable pose is
visible without touching the mouse.

The first attempt (`Distance: 14`, focal point at the middle of the
*traverse* rather than of the *map*) was **worse than what it replaced**,
and only the screenshot caught it. Reasoning about a perspective camera's
ground coverage from two numbers and a yaw does not work; looking at the
window takes 25 seconds. Nothing else in the view was touched — this was
not a UI pass, and C2-M9 owns that.

**Unverified / open**

- Why *that* climb drifted 0.51 m when others peak at the same correction
  and stay on the lane. Clamp saturation is **not** established as the
  binding constraint.
- Which of the two gates in `_locate` rejected blue. The status line does
  not record it.
- Nav home: two distinct failure mechanisms in four legs, and the
  degraded-control-loop confound not isolated. **C2-M5.**
- `rviz_2d_overlay_plugins` still not installed, so
  `mission_hud._publish_overlay` has still never executed.
- M7 Phase 4's three gating decisions: untouched.

**Tests:** 404 -> **414 passing, 0 failing**, per package with cwd set to
the package directory, against this branch's overlay build. The stale
`coco_sim` question needed no re-investigation — `coco_rl` was already
106/0 here, the established signature of a fresh build.

**Next:** C2-M2 is **READY**. The pitch signal now has known semantics, a
known source, a known sign convention and a staleness contract, and the
field that would have poisoned the grade estimator no longer exists. Start
with the Route C tip-terminator decision, which is C2-M2's first item and
M7 Phase 4's third gate.

```bash
cd ~/ros2_ws && colcon build --packages-select coco_sim   # if 29 coco_rl tests are red
ros2 run gazebo_models pitch_probe.py --out /tmp/pitch.csv --hz 10  # the C2-M2 instrument
```

## 2026-08-17 — C2-M1.6: the map was fine, the overlay was not

**Objective:** answer two questions that look identical on a screen and
have opposite answers — *is the occupancy map poor* or *is the RViz
presentation cluttered* — then fix the second without touching anything
that could change the first. Presentation only. No SLAM, Nav2, planner,
controller, costmap, robot-model or perception change, and none was made.
No C2-M2 work, and none was started.

**The rule set in advance:** measure the map before touching the display,
and classify it explicitly. If the map had a real defect, document and
stop rather than change SLAM inside a visualization milestone.

**Built**

- `gazebo_models/rviz/mission_debug.rviz` — **new**, the engineering view.
  It is the C2-M1.5 `mission.rviz` preserved: byte-identical below the
  comment header, verified by diff. Everything on — TF, particle cloud,
  both costmaps, laser, the camera pane, the oblique Distance-18 camera.
- `gazebo_models/rviz/mission.rviz` — **rewritten** as the clean operating
  view. Same topics, fewer enabled, re-framed.
- `coco_mission/launch/mission.launch.py` — `rviz_config:=mission` (the
  default) or `mission_debug`, via `PathJoinSubstitution`. `os.path.join`
  would stringify the substitution object into the path.
- `gazebo_models/test/test_rviz_configs.py` — **new**, 21 tests.
- `docs/data/map_audit.py` — **new**, the instrument. Read-only, no ROS,
  not installed by CMakeLists: it is evidence, not a runtime tool.

**Commands run**

```bash
# the map audit, offline, reproducible
python3 docs/data/map_audit.py -o docs/images/c2m16_map_audit.png

# framing sweep: RViz reads the view at startup, so restart the VIEWER,
# not the simulator. map_server + rviz2 only, no Gazebo needed.
ros2 run nav2_map_server map_server --ros-args \
    -p yaml_filename:=gazebo_models/maps/coco_world.yaml
xwd -id <rviz window> -silent -out shot.xwd      # NOT x11grab; see below

# live: one fresh sim, one viewer at a time, both configs on the same run
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py policy:=<zip> rviz:=false
ros2 run gazebo_models traverse_demo.py --colour blue --no-grasp

# the launch argument
ros2 launch coco_mission mission.launch.py --show-args
```

**Measured — the map. Question 1 is answered: GOOD.**

The decisive test is registration, because it is the one a drifted or
ghosted map cannot pass. Five free-standing objects in
`worlds/coco_world.world` have known poses; located independently in the
map they agree on a **single rigid offset (+2.0560, +0.0150) m** with
peak-to-peak **(0.0500, 0.0000) m** and a **worst residual of 25 mm —
half a cell**. Drift makes landmarks disagree; these do not.

- 186 occupied components, **156 of them ≤ 2 cells**. The eight largest
  are every structure that exists. **No ghost walls, no duplicates.**
- The ramp reads 0.575 m short at the up-ramp foot and 0.625 m short at
  the down-ramp foot. Those imply a scan plane at **186.8 mm and
  203.1 mm**, agreeing to **16.2 mm**, against `LIDAR_MOUNT_XYZ`
  z = 0.200 m. **Symmetric** — a defect would not be.
- Free 73.830 m²; the arena is **66.08 m² (89.5%)** of it in one
  component; **51.66 m² drivable** after a 0.2225 m erosion. Speckle is
  85 cells = 0.2125 m²; inflating all of it by 0.30 m costs **0.73%** of
  drivable space and the drivable region stays **one** component.
- Unknown 23.310 m², fully accounted: 15.143 m² outside the arena hull,
  7.625 m² the platform's own occluded interior.

**The one honest caveat.** The north and south walls have continuous gaps
of **0.55 m and 0.85 m**, which do exceed the robot's 0.297 m footprint.
They sit in the far east corners the mapping drive never entered —
**unobserved, not distorted** — and they are not navigable: they open onto
unknown cells, and `nav2_params.yaml` has `track_unknown_space: true` with
`allow_unknown: false` on both planners, so no plan can route through
them. **Recorded, not fixed.** Changing SLAM was out of scope and the
finding does not justify it.

**Measured — the framing.** Map bbox in pixels inside the 1220 × 806
render area of a 1600 × 900 window:

| Distance | Pitch | map bbox | margins L/R/T/B |
|---|---|---|---|
| 12 | 1.30 | 1092 × 691 | 64 / 64 / 91 / **24** |
| **13** | **1.45** | **949 × 652** | **135 / 136 / 90 / 64** |
| 14 | 1.30 | 922 × 591 | 149 / 149 / 132 / 83 |
| 16 | 1.30 | 798 × 516 | 211 / 211 / 164 / 126 |

Yaw 5.9 → **4.712389 = 3π/2**, which puts +x screen-right and +y
screen-up. Not cosmetic: the arena is 12.15 m along x and 8.75 m along y
in a window wider than it is tall, and yaw 5.9 laid the long axis down
the short axis of the window. Turning the map to match the window is what
let the distance come in. Pitch 1.45 beat 1.30 on measurement — less
foreshortening draws a **bigger** map at equal bottom margin.

**Net: the clean view draws the map 36% larger in linear terms than the
preserved C2-M1.5 camera** (949 px against 700 px, same rig, same window),
and both still fit the whole map inside the viewport. C2-M1.5's
"Distance 18 fits with margin" is **confirmed**, not corrected.

**Found and fixed, and only by looking**

1. **The robot lost the frame to its own costmap.** At local-costmap
   alpha 0.32 the two inflation blooms around the gate cubes read louder
   than the robot did. RViz cannot scale a `RobotModel` and the robot is
   frozen, so: alpha **0.22**, plus a saturated blue AMCL arrow at the
   robot in a colour nothing else uses.
2. **The laser was nearly invisible.** The light blue chosen to replace
   the original orange disappeared against the map's *white* free space.
   Recoloured to a mid-saturation teal.
3. **A claim written into the config was wrong, and measuring killed it.**
   The comment said the camera pane costs 3D render width. It does not.
   Measured side by side on one run: the render area is **1220 × 806 px
   in both** files. The pane stacks *above* the Displays tree and costs
   **304 px, 41% of the dock** — the display tree goes 740 px → 436 px.
   The pane still stays out of the clean view, but for the other reason:
   that view's premise is diagnostics-present-but-unticked, and a tree
   you have to scroll is a worse place to keep them.

**Three harness traps, all of which produced a wrong measurement first**

- **`x11grab` captures a screen region.** Another terminal window raised
  itself over RViz and was scored as a framing result.
  `xwd -id <win>` asks the X server for the window's own pixels and
  cannot be occluded.
- **Parking the mouse in a screen corner.** `xdotool mousemove 5 5` hits
  the desktop's top-left hot corner; several renders came back with the
  camera silently orbited away from the config under test. Park it
  somewhere neutral. The tell is the status bar reading
  "Left-Click: Rotate" instead of "RViz is ready".
- **Not killing the previous viewer.** `xdotool search --name RViz` then
  returns whichever window it finds last, and a screenshot gets scored
  against a config that was not the one under test.

RViz was checked and does **not** write the `-d` config back on exit; the
shipped values were verified intact after every sweep.

**Unverified / open**

- **Two traverse runs, `--no-grasp`, fresh sim each: neither completed.**
  Both climbed cleanly (`outcome=goal`, cross-track −0.01 m, disp
  +0.03 m) and confirmed blue at 1.159 m; both then **timed out in the
  scripted descent at 90.1 s** on the platform's far edge, world
  (4.50, 0.24). **No diagnosis attempted** — nothing this milestone
  changed can reach the controller. **Confound stated:** run 1 ran with
  two RViz instances alive, and C2-M1.5 already recorded a 4.8 Hz control
  loop against a 10 Hz target under Gazebo + RViz + move_group. Two runs
  are not a rate; the standing figure is M6's **19/20**.
- The AMCL arrow is drawn at z = 0 and `rviz_default_plugins/Pose` has no
  z-offset, so the robot model hides most of the shaft. Locator and
  heading indicator, not a beacon.
- `/perception/target` is published in `base_footprint`
  (`target_finder.py:566`), so the marker rides with the robot instead of
  pinning a world position. Perception is frozen; this is **C2-M4's**.
- The launch argument was verified by `--show-args` and by resolving the
  substitution to files that exist; RViz itself was started directly on
  each config rather than through `mission.launch.py rviz:=true`.
- `rviz_2d_overlay_plugins` still not installed, so
  `mission_hud._publish_overlay` has still never executed.
- M7 Phase 4's three gating decisions: untouched.

**Tests:** 414 → **435 passing, 0 failing**, per package with cwd set to
the package directory. All 21 new ones are in
`gazebo_models/test/test_rviz_configs.py` (20 → 41) and every one is a
silent-failure mode: a QoS mismatch, a wrong fixed frame, a topic nobody
publishes, a plugin that cannot subscribe to the message type it is
pointed at. RViz does not error on any of those — it draws nothing and
looks like a broken robot. Colours, alphas, widths and camera distance
are deliberately **not** asserted; they were judged against rendered
windows and pinning them would only make them harder to re-judge.

**Next:** C2-M2 remains next and its gate is still open. Nothing here
changed that. Start with the Route C tip-terminator decision, which is
C2-M2's first item and M7 Phase 4's third gate.

```bash
# the mission, either view
ros2 launch coco_mission mission.launch.py policy:=<zip>                      # clean
ros2 launch coco_mission mission.launch.py policy:=<zip> rviz_config:=mission_debug
# re-check the map claim without a simulator
python3 docs/data/map_audit.py
```

---
## 2026-08-19 — C2-M2.0: grade is observable, friction is not, and the tip terminator was measuring the wrong angle

**Objective:** the first of two sessions on C2-M2. Take the Route C
tip-terminator decision, audit the existing baselines, build the terrain
observer and its controller, test them, and leave C2-M2.1 a frozen
benchmark. No large sweep, no RL training. None was started.

**The Route C decision — option B, and it turned out to be nearly free.**

M7 Phase 3 diagnosed this and declined to fix it, on the stated grounds
that `TIP_LIMIT` was shared with `ramp_env`, the v1 curriculum and the
shipped policy. **It is not.** `TIP_LIMIT` is not in `coco_config`; it is
written out independently in four modules, and only `yard_env` is the
Yard. So the Yard's terminator was corrected without touching a number
any v1 result was measured against, and a test now asserts the other
three are still 0.6 rad absolute.

What changed is the **reference frame, not the threshold**: `|roll|` and
`|pitch|` are now measured from the local surface normal, with 0.6 rad
kept exactly, so no new tuning constant enters the repo. Two guards, both
from numbers that already existed — an absolute backstop at the measured
**54.5°** static rear-over, and the surface correction bounded by
`TIP_LIMIT` itself so a bad surface reading can at worst double the
effective absolute limit.

**Reproduced live before changing anything.** Route C seed 7, open loop:
terminated at step 184 at body pitch **−45.30°** on a **+20.16°**
surface — **25.14° surface-relative**, against a 54.5° rear-over. After
the change it fires at step **185**, at −54.51°, which is a genuine
rear-over. **The mechanism is fixed; whether the population of 101 Route
C tips changes is a C2-M2.1 measurement and is not yet measured.**

**The baseline audit produced one finding that shapes the whole
experiment.** In `TUNED_SCHEDULE`, `grade_k = 0.0` and
`lateral_lo == lateral_hi` on all three routes. So B2's entire privileged
advantage, as tuned, is **one number**: throttle interpolated on true μ,
over a range of 0.20 action units. Grade is in B2's interface and has no
effect. That is worth knowing before reading C2-M2.1's table.

**Built**

- `coco_rl/coco_rl/terrain_observer.py` — new, pure Python, no `rclpy`
  (it is reached from `baselines` and so from `yard_env`; CLAUDE.md §2 is
  structural here, not aspirational). `GradeEstimator`,
  `TractionEstimator`, `TerrainObserver`, and the `DeployableSignals` /
  `TerrainEstimate` types.
- `coco_rl/coco_rl/sensor_model.py` — new. **The information boundary, as
  code.** `deployable_signals()` builds what the robot could know;
  `ground_truth()` builds what only the simulator knows. They are
  different types sharing **no field name**, so feeding truth to the
  observer is a `TypeError` rather than a review miss. A 50 Hz
  `ImuSampler` — the rate `coco_robo2.xacro` declares — that reads
  `qpos`/`qvel` and writes nothing.
- `coco_rl/coco_rl/baselines.py` — `B3`, and `schedule_gains()` extracted
  from `B2.reset` so B3 reuses the privileged controller's *relationship*
  rather than a copy of it. A test pins the extracted function against
  B2's original arithmetic.
- `coco_rl/coco_rl/terrain_observer_node.py` — new. Publishes
  `/terrain/state` as `diagnostic_msgs/DiagnosticArray` (no custom
  message; `level` carries validity, `values` the numbers). **Adds no
  publisher to any `cmd_vel` topic** — `cmd_vel_arbiter` remains sole
  publisher to the controller.
- `coco_rl/coco_rl/terrain_benchmark.py` — new. **C2-M2.1's benchmark,
  frozen**: B0/B1/B2/B3 × routes A/B/C × seeds 0–119 = 1,440 episodes,
  metrics fixed, and the decision rule's task named **before** any result
  existed.
- `docs/data/c2m2_sanity.py` — new, the five sanity checks. Read-only, no
  ROS, deliberately not installed by any `CMakeLists.txt`, same shape as
  `map_audit.py`.
- `coco_rl/coco_rl/yard_env.py` — the terminator, the IMU sampler, and
  `flat_reference` captured inside the settle `_measure_rest_z` already
  did.
- `gazebo_models/scripts/ros_clean.sh` — `terrain_observe[r]` added
  **before it is ever launched**, per the rule `mission_hud` paid for.

**Measured**

- **Nose-up is NEGATIVE pitch.** Route A's uniform 12.000° face reads
  **−12.00°**. A `body_pitch → grade` rename would have been wrong in
  *sign* as well as in reference.
- Grade MAE, both axles on one plane: **A 0.106°, B 0.366°, C 1.433°**.
  Flat ground: worst 0.2057° against a true zero.
- **Friction is not identifiable.** τ equals tan(grade) to four decimal
  places at every μ — Route A spans **0.0003** across a μ span of 0.35.
  The encoders cannot see friction at all (wheel speed and servo lag
  identical to four decimals across μ), and an inertial body-velocity
  estimate lost 0.10–0.15 m/s in two seconds against a true 0.28.
- Instrumentation cost 1.5–4.1% of single-worker throughput; a test
  asserts the sampler cannot move the simulation.
- **Tests 428 → 471, 0 failing**, per package with cwd inside each.

**Three things that were wrong first and were caught by measuring**

1. The normal load modelled as `g·cos(grade)` instead of measured — the
   bound `τ ≤ μ` held on **27%** of Route B's samples.
2. The ratio taken in the body frame instead of the contact frame — broke
   on **47%**, *and produced a spurious monotone reading in μ that looked
   exactly like the result being sought*. The apparent signal was the
   error.
3. Both confidence thresholds guessed from filtered-signal behaviour and
   set below the **median** of the raw distribution they gate, so the
   observer disqualified itself and B3 ran in fallback 78–94% of the
   time. Re-set from measured distributions, chosen before B3's outcome
   was looked at.

**Unverified / open**

- **No benchmark was run.** The only multi-episode runs were 4- and
  6-seed smoke tests to prove the runner works; their numbers are **not**
  results and are not recorded as any.
- Whether Route C's 101-tip population changes under the new terminator.
- Whether B3 closes the 10-percentage-point gap. **Not yet measured** —
  that is C2-M2.1 and the whole point of freezing the config now.
- The bound `τ ≤ μ` has **two known exceptions**, both stated: a slope
  break (the robot straddles the ramp foot for one wheelbase with its
  rear axle still on the apron) and a vertical face (Route C's curb
  pushes back with a *normal* reaction). Neither is detectable from an
  IMU and encoders alone, so the benchmark reports `mu_bound_held` as a
  measured rate rather than asserting it.
- The simulated IMU is **noiseless** (`imu_noise_sigma:
  not_yet_measured`). No noise floor was invented. This is why nothing in
  the observer integrates, and it bounds what C2-M2.1 can claim about a
  real robot.
- `terrain_observer_node` has **never been run against a live Gazebo**.
  It is unit-tested through its pure core only; the ROS wiring is
  unexercised.
- M7 Phase 4's other two gating decisions: untouched.

**Not changed, deliberately:** Nav2, SLAM, AMCL, the map, perception, the
robot model, the terrain geometry, the action space, `cmd_vel_arbiter`,
the reward, the shipped policy, `GOAL_SUMMIT`/`GOAL_MARGIN`, and the v1
tip terminator in all three of its non-Yard homes.

**Next:** C2-M2.1 — run the frozen benchmark, then analyse and apply the
decision rule. The rule and its task were fixed here and must not move.

```bash
# the benchmark. 1,440 episodes, ~30-60 min at 8 workers.
python3 -m coco_rl.terrain_benchmark --out docs/data/c2m2_benchmark.json

# re-report an existing run without re-running it
python3 -m coco_rl.terrain_benchmark --report docs/data/c2m2_benchmark.json

# the implementation checks, before trusting any of it
python3 docs/data/c2m2_sanity.py
```

## 2026-08-19 — C2-M2.1: the benchmark ran, the observer cleared the bar, and the bar is the result

**Objective:** the second and final session of C2-M2. Validate the
observer live in Gazebo, run the frozen 1,440-episode benchmark, apply
the 10-percentage-point rule unchanged, and close the phase. No RL
training. None was started.

**The live gate found three defects, and every one was invisible to the
pure-core tests.** C2-M2.0 shipped `terrain_observer_node` having never
run it against a live Gazebo. It did not survive first contact:

1. `is_best_effort()` called with **no argument** — it takes the topic,
   and every other caller in the repo passes one. `TypeError` in the
   constructor: **the node could not start at all.**
2. The estimator was advanced from the **10 Hz publish timer**, so
   samples reached the observer exactly `MAX_AGE` apart and it withdrew
   itself on **431 of 431** — `stale input: 0.100 s > 0.100 s`, a full
   climb without one valid estimate. C2-M2.0 had fixed the observer rate
   at 50 Hz and `B3.observe` says why in as many words; the node put
   estimation and publication on the same clock. They are separate now.
3. `on_declared_flat` was **never passed**, so the flat reference could
   never be learned and `calibrated` was False forever — while the node's
   own comment claimed the opposite.

All three are wiring, not estimation, which is exactly the class a test
that drives the observer directly cannot reach. **12 new tests now
construct the real node**, because nothing off-line ever had.

**Live, after the fixes.** Fresh sim each, `gui:=false`, never `--fast`.

- `/imu` **49.1 Hz** (declared 50), `/terrain/state` **10.02 Hz**,
  422/422 estimates finite, stamps monotonic sim-time.
- Grade on the flat **0.0000°** at confidence **1.000**; on the 18° face
  MAE **0.672°**, and the settled tail sits **0.0035°** off the built
  18.000.
- `/diff_drive_controller/cmd_vel` publisher count **1** — the arbiter —
  before and after the observer started. The observer publishes
  `/terrain/state` and nothing else.
- On the Yard's Route B the bound established at t=3.10 s
  (μ_lower **0.3529**), **B3 engaged on 167 of 200** samples with
  throttle 0.638 / lateral 6.000, and on deliberate withdrawal fell to
  throttle **0.5** / lateral **3.0** — B1's shipped gains exactly.

**And the gate returned a physics result nobody asked it for.** τ settles
at **0.3248** against tan(18°) = 0.3249, and peaks at **0.4865** against
tan(26°) = 0.4877. C2-M2.0's equilibrium-pinning result was measured in
MuJoCo; it now holds in **Gazebo**, on two grades, in a different physics
engine.

**The benchmark: 1,440 intended, 1,440 completed, 0 runner errors.**
Nothing dropped, retried or re-seeded.

**The rule, applied unchanged.** Task `ascent`, margin 10 pp, both fixed
in C2-M2.0 before any result existed:

| route | B2 | B3 | gap |
|---|---|---|---|
| A | 99.2 % | 99.2 % | **+0.0 pp** |
| B | 34.2 % | 32.5 % | **+1.7 pp** |
| C | 65.8 % | 58.3 % | **+7.5 pp** |

**RL is justified on 0 of 3 routes. Additional learned control is NOT
justified by this benchmark.**

**The finding that matters more than the verdict, and it is not the
comfortable reading.** B3 ≈ B2 on ascent is a statement about the **task**,
not about the estimator.

On Route A, B3 fell back on **120 of 120** episodes — identical outcome on
every seed, identical cross-track to four decimals. **B3 is B1 there**, and
necessarily: tan(12°) = 0.213 is below the 0.35 a-priori friction floor,
so the bound can never become informative and the observer correctly
refuses to schedule on an assumption. It recovered **nothing**.

Meanwhile B2 **completed 97.5 % of Route A against B1's and B3's 0.0 %** —
a **97.5-point** difference bought by one number, throttle interpolated on
true μ. The ascent gap is 0.0 pp because ascent does not discriminate on
Route A (B0 through B3 all reach the deck 92–99 %), not because
estimation succeeded.

C2-M2.0 chose ascent for a stated reason: Phase 3 saw B1 reach the deck
99 % and then fall off the bridge 105 times in 120, so completion looked
like it was scoring deck geometry rather than terrain control. **This
benchmark weakens that premise** — B2 crosses the bridge 117 times in 120
on terrain-aware throttle alone, and a pure geometry problem would not
yield to terrain information.

The rule was applied unchanged and its verdict stands as recorded. Whether
`ascent` was the right task is a question for whoever sets the next rule,
and the evidence to decide it is now in `RESULTS.md`.

**Measured**

- Grade MAE by route: **A 0.057°, B 0.253°, C 2.681°** (worst 11.220°),
  convergence **0.94 / 2.73 / 10.10 s**. Route C's rubble is where body
  pitch stops representing the surface, and the tail runs to 20°.
- **τ − tan(grade) = −0.0012 / −0.0034 / +0.0043** over 1,440 episodes.
  τ is pinned by geometry and carries no information about μ. **No
  friction MAE is reported, and none exists to report.**
- The traction bound held on **100.0 %** of single-plane samples on all
  three routes — C2-M2.0 declined to assert this and reported it as a
  rate; measured, it holds.
- Scheduling-input gap on Route A: **0.280 against a μ range of 0.35**.
  Four fifths of the range, unrecovered.
- **Route C is where the observer costs something.** B3 ascends **58.3 %**
  against B1's **84.2 %** — 25.9 points worse than the baseline it falls
  back to — losing ascent on 32 seeds and gaining it on 1, while engaging
  on only 13 % of steps against a grade MAE of 2.681°.
- Route C tips: **B1 106, B3 116** under the surface-relative terminator,
  against Phase 3's 101 under the absolute one. **The population did not
  shrink.** What changed is that the terminator now fires at a genuine
  rear-over instead of 34° short of one. This entry does not claim the
  count improved.
- Tests **478 → 490**, 0 failing.

**Terminology corrected BEFORE the benchmark ran**, not after seeing a
result: `mu_mae`/`mu_bias` → `sched_mu_gap_mae`/`sched_mu_gap_bias`,
`mu_hat` on the wire → `mu_sched_input`, plus new `tau_mean` and
`tau_minus_tangrade_*` columns and a `note` field on `/terrain/state`
stating that true μ is not identifiable.

**On the test count, 471 → 478 before any change.** C2-M2.0's 471 was
measured without the user-space MoveIt prefix on the path, which **skips**
`coco_moveit_config`'s 7 `test_pick_poses` tests. `setup_env.sh` puts it
there; a hand-built environment omits it. Sourced, they pass. **471 was
reproduced exactly in this session on the unmodified tree** before the
prefix was added, so the delta is environmental and not a regression.
`gazebo_models` additionally needs `--ignore=test_integration`, whose
`launch_testing` suite is off by default and kills collection outright.

**Unverified / open**

- **Whether `ascent` is the right decision task.** The evidence above says
  it does not discriminate where the privileged advantage is largest.
  Not resolved here — changing the rule after seeing the result is the
  failure the freeze existed to prevent.
- Whether Route C's tips are avoidable by control at all. The terminator
  is now honest; the population is unchanged.
- Whether B3's Route C behaviour improves with a better grade channel on
  rubble. The correlation is suggestive (2.681° MAE, 10.10 s convergence,
  13 % engagement, worst ascent) and is **not** a demonstrated cause.
- The simulated IMU is still **noiseless**
  (`imu_noise_sigma: not_yet_measured`). Nothing here integrates, and this
  still bounds what any of it claims about a real robot.
- M7 Phase 4's other two gating decisions: untouched.

**Not changed, deliberately:** Nav2, SLAM, AMCL, the map, perception, the
robot model, the terrain geometry, the action space, `cmd_vel_arbiter`,
the reward, the shipped policy, `GOAL_SUMMIT`/`GOAL_MARGIN`, the v1 tip
terminator in all three non-Yard homes, **the tuned schedule, the routes,
the seeds, the decision task and the 10-point margin**. `baselines.py`,
`yard_env.py`, `terrain_observer.py` and `sensor_model.py` are
byte-identical to C2-M2.0, verified with `git diff` before the benchmark
ran.

**Next:** C2-M3, the mission executive. **Do not start it by editing
`traverse_demo.py`** — read `ROADMAP.md`'s C2-M3 block first; the
milestone is about states with entry conditions, timeouts and recovery,
and `/mission/state` is a stepping stone rather than a substitute.

```bash
# reproduce the whole benchmark (~25 min at 8 workers, 12 cores)
python3 -m coco_rl.terrain_benchmark --out docs/data/c2m2_benchmark.json

# re-report, analyse and plot WITHOUT re-running it
python3 -m coco_rl.terrain_benchmark --report docs/data/c2m2_benchmark.json
python3 docs/data/c2m2_analysis.py
python3 docs/data/c2m2_plots.py

# the implementation checks, before trusting any of it
python3 docs/data/c2m2_sanity.py

# the live gate, if the node is ever touched again
ros2 launch gazebo_models full_world_robo.launch.py gui:=false
ros2 run coco_rl terrain_observer --ros-args -p use_sim_time:=true \
    -p declare_flat:=true
ros2 run custom_teleop cmd_vel_arbiter --ros-args \
    -p use_sim_time:=true -p initial_mode:=rl
python3 docs/data/c2m2_live_gate.py /tmp/gate.csv 40 0.35
```

---

## 2026-08-20 — C2-M3.0, the mission is a state machine and it completed a fetch

**Built:**

- `coco_mission/scripts/mission_states.py` — **new**, the machine. Pure
  Python, no `rclpy`, no clock, no I/O: an `Observation` in, a
  `Directive` out. 18 states, a contract table (mode, owner, timeout,
  max retries, retry target, escalation), ~40 structured failure
  reasons, and one uniform failure path through `RECOVERY`.
- `coco_mission/scripts/mission_executive.py` — **new**, the ROS
  adapter. Subscriptions → `Observation`; one idempotent request out per
  state. Publishes `/mission/mode`, `/mission/state` and (only when it
  was told the colour) `/mission/target_colour`. Offers
  `/mission/start` and `/mission/abort`. **No velocity publisher.**
- `coco_mission/launch/mission.launch.py` — starts the executive
  (`executive:=true` by default, `mission_autostart:=false`).
- `coco_mission/scripts/mission_hud.py` — renders the new
  `/mission/state` line, and the `RECOVERY` row finally has a source.
  Both formats render, so `traverse_demo.py` stays readable.
- `gazebo_models/launch/nav.launch.py` — pins `autostart: 'true'` on the
  nav2_bringup include. Interface bug, see below.
- `gazebo_models/scripts/ros_clean.sh` — `mission_executiv[e]`.
- Tests: `test_mission_states.py` (**new**, 62) and
  `test_mission_executive.py` (**new**, 35, every one constructing the
  real node), plus 3 in `test_mission_hud.py`.

`traverse_demo.py` is **unchanged and kept**: it is the harness the
M4/M5/M6 numbers were measured with.

**Measured:**

- **One full fetch completed end to end through the executive**, blue,
  fresh simulator, `gui:=false`, RViz off, never `--fast`. All 15
  nominal transitions in order, `IDLE → COMPLETE`, `result=fetch`,
  **zero RECOVERY entries and zero retries** (`attempts={}`).
- **175.8 s** from `/mission/start` to `COMPLETE`. Per state:
  LOCALIZE 0.1, NAVIGATE_TO_RAMP 14.5, ALIGN_FOR_CLIMB 0.2, CLIMB 13.1,
  VERIFY_CLIMB 0.2, SEARCH_TARGET 0.2, STOW_ARM 3.2, APPROACH_TARGET
  13.1, GRASP 27.5, VERIFY_GRASP 0.2, DESCEND 16.5, RETURN_HOME 69.4,
  PLACE 17.4, VERIFY_PLACEMENT 0.2 seconds.
- **Home to 7 mm.** Final world pose `(-2.0008, +0.0070)` against a
  `(-2.0, 0.0)` goal.
- **Arbiter invariant held: publisher count on
  `/diff_drive_controller/cmd_vel` = 1**, measured before the mission
  started and again after it finished. One `mission_executive` on the
  graph.
- **The descent did NOT reproduce KNOWN PROBLEMS 3b.** `outcome=goal` in
  16.5 s against the 90.1 s timeout seen twice in C2-M1.6 — under light
  load and with RViz off, which is exactly the confound 3b named. One
  run is not a rate and 3b is not closed.
- **Nav home succeeded first time**, no repeat of KNOWN PROBLEMS 1. Also
  one run.
- **Pre-climb heading +0.281 rad (+16.1°)**, measured against ground
  truth at the ramp foot, gate off. An earlier run measured **+0.28**
  and, after re-driving the leg, **+0.26** — see below.
- Tests **490 → 589**, 0 failing. Per package: `coco_config` 70,
  `custom_teleop` 67, `coco_rl` 164, `coco_perception` 44,
  `coco_moveit_config` 12, `coco_sim` 55, `coco_mission` **136**,
  `gazebo_models` 41.

**Two defects the live runs found that no test could have:**

1. **`autostart` leaked into Nav2 and stopped the whole stack.**
   `mission.launch.py` declared a launch argument called `autostart`.
   Launch configurations are inherited by every include, and an
   inherited value shadows the included file's own
   `DeclareLaunchArgument` default — so `nav2_bringup`'s `autostart`
   (default `true`) became `false`. **Every Nav2 lifecycle node came up
   `unconfigured`**: `map_server`, `amcl`, `planner_server`,
   `controller_server`, `bt_navigator`. `/amcl_pose` had **0
   publishers**, and the mission aborted in `LOCALIZE` with
   `NO_LOCALIZATION` after its 40 s budget — correctly, and four layers
   from the cause. **Nothing in any log contained the word `autostart`;**
   it was found with
   `ros2 param get /lifecycle_manager_localization autostart`, which
   answered `False` against a params file that never mentions it. Fixed
   twice over: the mission's argument is now `mission_autostart`, and
   `nav.launch.py` pins Nav2's `autostart` explicitly rather than
   inheriting it. Two tests assert both.

2. **The heading gate was calibrated to the wrong reference and is now
   off by default.** `ALIGN_FOR_CLIMB` originally failed the mission if
   |yaw| exceeded 0.25 rad — nav2_params' own `yaw_goal_tolerance`. It
   fired: the leg arrived at **+0.28 rad** and, re-driven, at
   **+0.26 rad**, and the mission aborted with `ALIGN_HEADING`. Both are
   *inside* Nav2's checker, because **Nav2 judges yaw against the AMCL
   pose it is steering by while this check reads ground truth**, and the
   two differ by the localisation error. Re-driving cannot fix it
   either: the same goal through the same goal checker cannot beat the
   checker's own tolerance, so the retry was structurally futile. The
   mission it aborted is the mission that completes 19/20. Following
   C2-M1's precedent for the HUD's localization verdict, the threshold
   is **not asserted**: the heading is measured, logged and exposed, and
   the gate is off unless `yaw_tolerance` is set to a float.

**One bug found by the unit tests before any live run:** a `RECOVERY`
that timed out was handed to `_fail`, which re-entered `RECOVERY` and
reset its clock — the mission would have sat there for ever with the
robot possibly still moving. It escalates to `ABORT` now.

**Unverified:**

- **Every failure path.** The live run was clean, so `RECOVERY` fired
  only in the two aborted runs (`NAVIGATION_FAILED` ×3 and
  `ALIGN_HEADING` ×2, both retrying and then aborting as specified).
  `skip_grasp`, `CLOCK_STALLED`, `OPERATOR_ABORT`, every worker-outcome
  reason and every timeout are unit-tested and **have not run on the
  robot**.
- `--no-grasp` through the executive has not been run live.
- The HUD's `RECOVERY` row was not read end to end live: `ros2 topic
  echo` truncates the block. The `STATE` row was — it rendered
  `NAVIGATE_TO_RA...` and, in the aborted run, `RECOVERY   (0....`.
- `rviz_2d_overlay_plugins` is still not installed, so the overlay path
  has still never executed.

**Open:**

- **`ALIGN_FOR_CLIMB` has no calibrated threshold and therefore gates on
  nothing but the lane and the ramp foot.** Turning the heading gate on
  needs either a tighter goal checker for that leg (nav2_params already
  defines a `precise_goal_checker` at 0.05 m) or an aligner **behind the
  arbiter**, plus a threshold measured against climbs that actually
  failed. C2-M3.1.
- **One clean run is not a rate.** The standing figure is M6's 19/20 and
  nothing here changes it.
- `grasp_server` writes outcomes containing spaces (`failed at hover`)
  into a space-separated `key=value` line. The executive reads the first
  token and classifies correctly by accident. Not touched — it is a
  pre-existing quirk in a subsystem this milestone must not modify.
- Two publishers on `/mission/mode` is now possible by operator error
  (executive + `traverse_demo.py`). Documented in three places and
  guarded by `executive:=false`; nothing enforces it at runtime.

**Next:** C2-M3.1 — end-to-end mission and recovery behaviours. The
first concrete action is to exercise the failure paths on the robot
rather than only in the harness, starting with `OPERATOR_ABORT` mid-climb
(the one that proves `/ramp/stop` is really reached before the wheels
age out against the arbiter's watchdog).

```bash
# the mission, through the executive
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py rviz:=false \
    policy:=/home/gautham/coco_rl_runs/curriculum_20260726_211008/phase5_24deg_s0p0.zip
ros2 service call /mission/start std_srvs/srv/Trigger
ros2 topic echo /mission/state
ros2 service call /mission/abort std_srvs/srv/Trigger     # the C2-M3.1 test

# the old blocking script, still reproducible
ros2 launch coco_mission mission.launch.py policy:=<abs> executive:=false
ros2 run gazebo_models traverse_demo.py --colour blue

# tests, from inside each package directory
cd coco_mission && python3 -m pytest test -q
cd gazebo_models && python3 -m pytest test -q --ignore=test_integration
```


## 2026-08-22 — C2-M3.1: the failure paths ran on the robot, and the machine did not need changing

**Built:** nothing in the robot. `mission_states.py` and
`mission_executive.py` are **byte-identical to C2-M3.0** — verified with
`git diff` — and that is the result of this milestone rather than an
omission. Five live missions, four deliberately broken, all behaved
exactly as their contracts specify.

The work was instrumentation and injection, all of it outside the repo:
a subscribe-only witness node recording `/mission/state`, `/ramp/status`,
`/cmd_vel_arbiter/status`, `/perception/status`, `/grasp/status`,
odometry, every controller command and the controller topic's publisher
count, stamped on both the simulation and a steady clock; and two witness
nodes that fire an injection on an **observed state**, never on a sleep.

Documentation changed: `docs/RESULTS.md` (new C2-M3.1 section),
`docs/DESIGN_DECISIONS.md` (three entries), `CLAUDE.md` (one trap row).

**Measured — five runs, fresh simulator each, `gui:=false`, RViz off,
never `--fast`:**

| Scenario | Trigger | Retries | Final | Result |
|---|---|---|---|---|
| Operator abort during `CLIMB` | `/mission/abort` on a moving robot | 0 | `ABORT` `OPERATOR_ABORT` | pass, x3 |
| Navigation failure | `--lane 5.0`, goal off the map | 2 | `ABORT` `NAVIGATION_FAILED` | pass |
| Perception failure | `target_blue` removed from the sim | 2 | `ABORT` `TARGET_NOT_FOUND` | pass |
| Manipulation failure | cylinder removed at `GRASP` entry | 2 | `ABORT` `GRASP_FAILED` | pass |
| Retry exhaustion | both escalation targets | max | `ABORT` | pass |

- **All four routes into `RECOVERY` now have a live run**: operator
  request, navigation action status, state timeout, and worker terminal
  outcome. Both escalations — `ESCALATE_ABORT` and
  `ESCALATE_SKIP_GRASP` — were reached.
- **Operator abort, three runs.** Fired only once `/mission/state`
  reported `CLIMB` *and* three consecutive odometry samples exceeded
  0.05 m/s, so the robot was provably climbing under RL control. Service
  replied in **24-32 ms**; last nonzero controller command at **+20 /
  +30 ms**; `CLIMB -> RECOVERY` at **+36 / +44 / +104 ms**; arbiter
  `active=none` at **+44 / +152 / +158 ms**; `RECOVERY -> ABORT` at
  **+180 / +204 / +304 ms**. Travel after the abort: **13.1 / 15.3 /
  23.6 mm**. Velocity below 2 mm/s at **+142 / +220 / +436 ms**.
- **The stop is commanded, not coasted.** Run 1c captured every message
  on the controller topic: **10 explicit zero commands over 0.88 s**
  after the last nonzero one — `cmd_vel_arbiter`'s
  `ZERO_HOLD_SECONDS = 1.0`.
- **No stale command resumed motion in any run.** After the last moving
  odometry sample, `max |vx| = 0.0` and `max |wz| = 0.0` across 50, 264
  and 482 further samples.
- **Retry counts are exact.** `attempts={'NAVIGATE_TO_RAMP': 2}`,
  `{'SEARCH_TARGET': 2}`, `{'GRASP': 2}` — read from the executive's own
  `MISSION ABORT` line, each equal to that state's `max_retries`.
- **Nav2's own words for the unreachable goal**, three times identically:
  `"Goal Coordinates of(2.500000, 5.000000) was outside bounds"`. The
  goal was chosen from the map, not guessed: free cells in
  `coco_world.pgm` span map-y `[-4.585, 3.565]` and the array ends at
  `3.840`. `IDLE -> ABORT` in **1.2 s**, robot never moved.
- **`SEARCH_TARGET` timed out three times at 15.09 / 15.00 / 15.09 s**
  against a 15.0 s contract, then `grasp abandoned; coming home`.
- **`GRASP` failed three times at 13.99 / 15.60 / 15.39 s** against a
  180 s timeout — a genuine worker outcome, not a timeout in disguise.
  `grasp_server` ran its whole unmodified sequence and reported
  `outcome=failed at magnet attach`.
- **No accidental COMPLETE.** Runs 3 and 4 descended, drove home (**120
  mm** and **63 mm** from home) and still ended `ABORT` carrying the
  original reason. A mission that did everything but the grasp reports
  failure.
- **cmd_vel invariant: 1,134 publisher-count samples across five runs,
  every one of them 1** — before each mission, through every recovery
  and retry, and after every abort.
- **0 states entered after `ABORT`** in 5 of 5 runs.
- Tests **589 passing / 0 failing**, unchanged. Per package:
  `coco_config` 70, `custom_teleop` 67, `coco_rl` 164,
  `coco_perception` 44, `coco_moveit_config` 12, `coco_sim` 55,
  `coco_mission` 136, `gazebo_models` 41.
- **Run the suite on a clean ROS graph.** Measured this session: with a
  live stack still up from a mission run, `coco_mission` gives
  **134 passed / 2 failed** — 35 of its tests construct the real node,
  and a populated graph is not the graph they assume. The same suite,
  after `ros_clean.sh`, gives **136 / 0**. The failures are graph
  pollution, not a regression; `ros_clean.sh` before `pytest` is the fix.

**One instrumentation defect, found the expensive way.**
`/diff_drive_controller/cmd_vel` reports **two** types —
`geometry_msgs/msg/Twist` and `geometry_msgs/msg/TwistStamped` — and the
arbiter publishes the second. The first recorder subscribed as `Twist`,
matched no publisher, and captured **zero** commands. That reads exactly
like "no stale command was ever issued", which is the conclusion the test
existed to reach. The run was repeated against `TwistStamped` and the
real answer is stronger than the empty file looked. Recorded in
`CLAUDE.md`'s trap table with the general form: **any check whose success
condition is "we saw nothing" must first prove it can see something.**

**One C2-M3.0 open item confirmed live.** `grasp_server` writes
`outcome=failed at magnet attach` into a space-separated `key=value`
line. `parse_kv` reads `outcome=failed`; the executive classifies
`GRASP_FAILED` **correctly**, but `at magnet attach` — the whole
diagnosis — never reaches the log or `/mission/state`. Not fixed:
`grasp_server` is a subsystem this milestone must not modify, and the
classification does not depend on it.

**Unverified — and this matters for how C2-M3.1 is described.** Four
representative branches ran live. **The following did not** and remain
unit-tested only: `CLOCK_STALLED`, `--no-grasp` through the executive,
`NAVIGATION_REJECTED`, `NAVIGATION_UNAVAILABLE`, `SERVICE_UNAVAILABLE`,
`SERVICE_REFUSED`, `RECOVERY_TIMEOUT`, every `ALIGN_*`, `CLIMB_TIPPED`,
every `DESCENT_*`, `RETURN_*`, `STOW_*`, `APPROACH_*`, `PLACE_*` and
`VERIFY_PLACEMENT`. The correct sentence is "live validation completed
for operator abort, navigation failure, perception failure and grasp
retry" — **not** "the recovery system is validated".

Also unverified: the **no stale completion** invariant. The token
mechanism was never made to race — no late worker reply arrived after a
cancel in any of the five runs — so that invariant is still argued from
the code and the unit tests rather than measured.

**Open:**

- `ALIGN_FOR_CLIMB` still has no calibrated heading threshold; the gate
  is still off and the number still only reported. Untouched by this
  milestone, which had no evidence to calibrate it with.
- **One run is still not a rate.** These five runs say the failure paths
  behave; they say nothing about how often the mission fails. The
  standing figure is M6's **19/20**.
- `KNOWN PROBLEMS 1` (nav home) did not reproduce in any of the three
  runs that drove home. Not closed.
- Two publishers on `/mission/mode` remains possible by operator error.

**Note for whoever runs this next.** The workspace checkout at
`~/ros2_ws/src/coco-robot-ros2` is on the **trunk**, which does not
contain the executive, so `~/ros2_ws/install` cannot run these tests.
This session built the worktree into a separate overlay at
`~/ros2_ws/c2m31_overlay` and sourced it on top, leaving the user's
`~/ros2_ws/install` untouched. `source ~/ros2_ws/c2m31_overlay/env.sh`
reproduces the environment; `bash ~/ros2_ws/c2m31_overlay/build.sh`
rebuilds it.

**Next:** C2-M4 — perception-driven manipulation.

```bash
# the environment these runs used
source ~/ros2_ws/c2m31_overlay/env.sh

# a failure run, end to end (fresh simulator, executive run directly so
# the documented --lane / --no-grasp parameters can be passed)
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py rviz:=false executive:=false \
    policy:=/home/gautham/coco_rl_runs/curriculum_20260726_211008/phase5_24deg_s0p0.zip
ros2 run coco_mission mission_executive.py --colour blue --lane 5.0 \
    --ros-args -p use_sim_time:=true
ros2 service call /mission/start std_srvs/srv/Trigger

# operator abort, on a moving robot
ros2 service call /mission/abort std_srvs/srv/Trigger

# make a target unavailable, without touching coco_perception
gz service -s /world/coco_world/remove --reqtype gz.msgs.Entity \
    --reptype gz.msgs.Boolean --timeout 5000 --req 'name: "target_blue" type: MODEL'

# tests, from inside each package directory
cd coco_mission && python3 -m pytest test -q
```

---

## 2026-08-29 — C2-M4.0: the target pose is measured, and the depth gate has a radius

**Built.** The perception-to-pose half of C2-M4, as two files plus a
node beside `target_finder` rather than inside it:

- `coco_perception/coco_perception/target_pose.py` — **new**, pure. No
  `rclpy`, no `tf2`, no message types. The validity states, the target
  representation, the selection policy, the depth quality metrics, the
  deprojection and the reachability verdicts. Same split C2-M2 made
  between `terrain_observer` and its node, for the same reason: the
  C2-M2.1 live gate's three defects were all in the node and none in
  the arithmetic.
- `coco_perception/coco_perception/target_pose_node.py` — **new**, thin.
  Subscribes, calls `target_pose`, asks `tf2` for one transform,
  publishes. Holds no geometry.
- `coco_perception/test/test_target_pose.py` — **new**, 70 tests.
- `docs/data/c2m4_localisation.py` — **new**, the instrument. Also the
  C2-M4.1 benchmark runner; `--benchmark` is the full grid.
- `coco_perception/setup.py`, `package.xml`,
  `gazebo_models/scripts/ros_clean.sh` — wiring.

`target_finder.py` is **byte-identical**. `/perception/target` still
carries `PointStamped` in `base_footprint` and `approach_server`'s servo
mode still consumes it — the path M6's 20/20 approach ran through.

**New topics.** `/perception/target_pose`
(`vision_msgs/Detection3DArray`), `/perception/grasp_point`
(`geometry_msgs/PoseStamped`), `/perception/target_pose/status`
(`std_msgs/String`, 5 Hz, key=value).

**Measured.** Fresh simulator, clean graph, never `--fast`. Twenty
placements, four colours, five stand-offs, **240 of 240 frames
detected**, every one in `base_footprint` with a frame id and a
validity.

| stand-off 0.35-0.90 m, 16 placements | min | median | max |
|---|---|---|---|
| horizontal error | **1.1 mm** | **1.6 mm** | **2.1 mm** |
| vertical error | 0.7 mm | 1.1 mm | 1.7 mm |
| Euclidean error | 1.3 mm | 1.9 mm | 2.7 mm |

Colour-independent to within 0.8 mm. This is an independent
corroboration of the `~2.0 mm` perception residual
`GRASP_MAX_LATERAL`'s comment has carried since M5 as a budget line; it
is now a measurement.

**The residual is bias, not noise.** `spread_x` and `spread_y` — the
frame-to-frame range at a fixed pose — were **0.0000 m in all 20
placements**. Averaging would buy nothing.

**The estimate tracks a moving target.** The sweep moves the robot;
a second experiment moved the *target* with the robot parked, which a
pipeline that had latched a constant or was reading `lane_for_colour`
would fail. It moved **70.1 mm against 70 mm commanded in x** and
**100.9 mm against 100 mm in y**, and "home" repeated to the last digit
after an excursion.

**One defect found, diagnosed to arithmetic, and NOT fixed.**
`min_range` interacts with the target's own radius. At a 0.28 m
stand-off the camera is 0.155 m from the axis, so a cylinder's near face
sits at `0.155 - r` = 0.145/0.143/0.141/0.139 m — **all under the 0.15 m
gate**. `robust_depth` rejects them and the surviving median is biased
away:

| stand-off 0.28 m | default 0.15 | control 0.11 |
|---|---|---|
| red / green / blue / yellow `dx` | **+4.1 / +5.5 / +6.9 / +8.3 mm** | **−1.0 / −1.0 / −1.3 / −1.4 mm** |

The bias is proportional to radius, which is the signature; the control
changed one parameter and it collapsed to the far-field figure.

**The node announced this itself, without ground truth.**
`hypothesis.score` — the fraction of blob pixels carrying usable depth —
read **1.0000 from 0.35 m out** and **0.0423-0.0706 at 0.28 m**. A
consumer gating on `score` would have refused those measurements. The
quality field justified itself on its first run.

**Left at 0.15 deliberately**: it matches `target_finder`, the operating
envelope starts around 0.30 m anyway because the approach's last leg is
blind below `min_range` by construction, and retuning a gate on one
session's evidence is what the evidence discipline exists to slow down.
One parameter, data recorded, C2-M4.1's call.

**A second, independent close-range effect.** `dz` at 0.28 m was
−4.3 to −5.4 mm and **did not move** when the gate was lowered, so it is
not the gate: it is the framing effect `target_finder`'s docstring
predicted — the cylinder's top has left the frame and the visible
centroid rides down. It costs the grasp nothing: `grasp_point.z` is
`TARGET_GRASP_Z` from the arm's geometry and never comes from the
camera.

**The far-field `dx` bias is explained too.** `SURFACE_TO_AXIS = 0.8`
under-shoots the cylinder's true median offset of `r*sqrt(3)/2 = 0.866r`
by `0.066r` — −0.7 to −1.1 mm across the four diameters, which is what
the −0.4 to −1.5 mm residual is. Recorded, not tuned: it is under a
millimetre and `0.8` is the constant M6 was measured with.

**Reachability reaches the real solver.** `arm_ik` is resolved through
`ament_index` at start-up and injected, so `IK_UNAVAILABLE` is a state
rather than an ImportError. Two verdicts are published because one would
mislead: `reach` read `OUT_OF_WORKSPACE` on all 20 placements, which is
*correct* — the arm reaches base-x 0.157 and perception sees the target
at 0.28-0.90 m — and `reach_appr`, evaluated at `approach_stop_x` with
the measured lateral offset, read `REACHABLE` on all 20. Since the
approach drives straight forward, **perception's `dy` is the whole of
what decides post-approach feasibility**, against
`GRASP_MAX_LATERAL = 0.010`.

**Unverified / not done.** No grasp was attempted. No approach was
driven — the robot was placed with `gz set_pose`. Lateral offsets were
not swept (on-lane only); that is C2-M4.1's grid. The depth camera is
noiseless, so `spread = 0.0000` is a statement about gz and not about a
sensor. `min_range` is diagnosed, not fixed.

**Traps paid for.** The job scratch directory carried a previous
session's `numbers.py` and `trace.py`. Python puts a script's own
directory at `sys.path[0]`, so both shadowed stdlib modules: `numbers`
broke `numpy` at import inside `rclpy`'s parameter service, and `trace`
printed a previous run's mission trace into the middle of this one's
output. Run instruments from a directory you control.

**Tests.** `coco_perception` **41 -> 111 passing, 0 failing**, run from
inside the package directory. Its `flake8` and `pep257` baselines were
clean, so all 14 style errors the new files introduced were fixed rather
than counted against the pre-existing allowance.

**Next:** C2-M4.1 — four-colour benchmark, grasp integration, final
validation. The benchmark runner exists and is parameterised; the grid
is four colours x five stand-offs (0.30/0.40/0.55/0.70/0.90) x three
lateral offsets (0.0/−0.010/+0.030), 60 placements.

```bash
# environment
source ~/ros2_ws/c2m31_overlay/env.sh
bash   ~/ros2_ws/c2m31_overlay/build.sh          # rebuild the overlay

# T1 — fresh simulator, ALWAYS. traverse:=true spawns the targets.
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false

# T2 — the node under test. Nav2 and MoveIt are NOT needed to measure
#      the pose: robot_state_publisher alone supplies the TF chain.
ros2 run coco_perception target_pose_node \
    --ros-args -p use_sim_time:=true -p target_colour:=blue

# T3 — the C2-M4.1 benchmark, 60 placements
cd docs/data && python3 c2m4_localisation.py --benchmark \
    --frames 12 --out c2m4_benchmark.csv

# the min_range control that diagnosed the close-range bias
ros2 run coco_perception target_pose_node --ros-args \
    -p use_sim_time:=true -p min_range:=0.11
cd docs/data && python3 c2m4_localisation.py \
    --colours red green blue yellow --standoffs 0.28 0.35

# tests, from inside the package directory
cd coco_perception && python3 -m pytest test -q
```

## 2026-08-29 — C2-M4.1: the benchmark ran, the grasp is perception-driven, and the lateral budget has no headroom

**Built.** One parameter, one instrument, one analysis, and nothing else
touched:

- `coco_perception/coco_perception/target_pose_node.py` — added
  `point_topic`, **empty by default**. Set to `/perception/target` the
  node stands exactly where `target_finder` stood and the whole existing
  manipulation chain — servo, align, creep, `/approach/target`,
  `check_target_pose`, `arm_ik`, MoveIt, the magnet — runs unmodified on
  the C2-M4.0 estimate. That is the entire C2-M4.1 integration.
- `coco_perception/test/test_target_pose.py` — **+6 tests** (73 in the
  file, 117 in the package) pinning the seam: the default is off, the
  publisher is conditional, the **axis** point is published and not the
  grasp point, the stamp is the **image's**, and the publish sits inside
  the `is_valid` branch.
- `docs/data/c2m4_grasp.py` — **new**, the manipulation instrument. One
  perception-driven grasp per invocation, one fresh simulator per
  invocation, and a physical verdict read from gz independently of the
  server's own.
- `docs/data/c2m4_analysis.py` — **new**, post-processing. Reads the
  benchmark CSV, reads nothing live, re-derives the IK verdict from the
  *measured* pose with the same `coco_config` bounds the robot uses.
- `docs/data/c2m4_benchmark.csv`, `docs/data/c2m4_grasp.csv`,
  `docs/data/c2m4_scatter.png` — the data.
- `CLAUDE.md` — one trap row: the grasp and approach services are
  **asynchronous**.

**Not changed, deliberately:** `target_finder.py`, `approach_server.py`,
`grasp_server.py`, `arm_ik.py`, `arm_control.py`, MoveIt, the arbiter,
Nav2, AMCL, the map, the robot model, the world, the action space, the
shipped policy. `GRASP_MAX_LATERAL` and `min_range` were **not retuned**
— see below, both are deliberate.

**Measured — perception.** Fresh simulator, clean graph, sim time, never
`--fast`, configuration fixed before the first placement.

```bash
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 run coco_perception target_pose_node \
    --ros-args -p use_sim_time:=true -p target_colour:=blue
cd docs/data && python3 c2m4_localisation.py --benchmark \
    --frames 12 --out c2m4_benchmark.csv
```

**60 of 60 placements measured. 720 of 720 frames detected. 0
wrong-colour selections.** Horizontal error **0.7 / 1.4 / 2.4 mm**
(min/median/max). Frame-to-frame spread **0.0000 m in all 60** — bias,
not noise, and a statement about gz's noiseless depth camera rather than
about any real sensor.

Colour-independent to within 0.47 mm of median (blue 1.47, green 1.21,
red 1.37, yellow 1.68 mm). No per-colour branch exists anywhere in the
pipeline and the benchmark says none is needed.

**The error grows with range and it grows in `dy`.** `|dy|` median runs
0.39 / 0.57 / 1.12 / 1.41 / 1.75 mm at 0.30 / 0.40 / 0.55 / 0.70 /
0.90 m while `dx` stays between −1.8 and −0.4 mm throughout.

**The lateral bias is sub-pixel and geometric.** On-lane, `dy` is
identical across all four colours to within 0.01 mm at every stand-off —
four diameters, four lanes, one number. As a bearing it is 1.30 to
1.95 mrad; at the image it is **0.29 to 0.43 pixels**. The node's own
`CameraInfo` log reads `cx=160.00` on a **320-pixel-wide** image, half a
pixel off the geometric centre under the pixel-centre convention, which
is the right sign and order — but the equivalent offset *rises* across
the sweep rather than holding flat, so that does not account for all of
it and the mechanism is **not claimed**.

**The operational consequence.** Because the bias grows with range, the
lateral estimate is best from close in. The approach's last visual fix
lands at ~0.29 m by construction, so the number that actually reaches
the grasp is the ~0.4 mm one, not the ~2 mm one — and that is what the
existing approach already does, with no change.

**`min_range`: decision B — no change, envelope documented instead.**
C2-M4.0 measured `dx` of +4.1 to +8.3 mm at 0.28 m, proportional to
radius. At the operating floor of 0.30 m the defect is **already gone**:
`dx` is −0.68 / −0.97 / −1.27 / −1.58 mm (the ordinary negative
far-field residual) and `qual` reads **0.9989 or better** against
**0.0423-0.0706** at 0.28 m. The gate is rejecting essentially nothing
where the robot actually works. It stays at 0.15 because that is what
`target_finder` uses, because the defect does not occur inside the
envelope, and — the reason that generalises — because **`qual`
announces the failure without ground truth**, so a consumer gating on it
is protected at stand-offs nobody has characterised.

**THE RESULT: the lateral budget has no headroom.**

| commanded lateral | true \|y\| | measured \|y\| min/med/max | feasible (measured) | feasible (truth) |
|---|---|---|---|---|
| 0.000 | 0.0 mm | 0.39 / 0.95 / 1.75 mm | **20 of 20** | 20 of 20 |
| **−0.010** | **10.0 mm = the budget** | 10.22 / 10.52 / 12.22 mm | **0 of 20** | 20 of 20 |
| +0.030 | 30.0 mm | 27.92 / 28.72 / 29.88 mm | **0 of 20** | 0 of 20 |

Three rows, three different reasons, and collapsing them would lose the
result:

- **+0.030 is geometry, not perception.** Three budgets out; measured and
  truth agree perfectly, 0 disagreements in 20. The arm is *planar* —
  both joints rotate about the base y-axis — so an off-plane target is
  unreachable at every joint angle and no sensor could fix it. The
  pipeline refuses on its own measurement, before any motion is planned.
- **0.000 works,** with 8.25 mm of margin at worst.
- **−0.010 is the finding.** The target sits *exactly* on
  `GRASP_MAX_LATERAL`, so `abs(y) > max_lateral` is a tie a perfect
  sensor wins by nothing. The residual is biased **outward**, so the
  measured value lands 0.22 to 2.22 mm over the limit in **20 of 20**.

That is not perception failing — 0.2-2.2 mm against a 10 mm budget is a
good sensor with zero headroom. **`GRASP_MAX_LATERAL` was not moved.**
Moving a decision rule after seeing the cases it rejected is the failure
`DESIGN_DECISIONS.md` already records for the terrain observer. What
C2-M4.1 owes the next session is the number, and the number is on the
record.

**Measured — the perception-driven grasp, live.** Eight runs, **one
fresh simulator each** (the gz `DetachableJoint` binds its child once),
never `--fast`, `target_finder` NOT running, publisher count on
`/perception/target` verified 1 before every run.

Integration is one parameter: `-p point_topic:=/perception/target`.
`approach_server`, `grasp_server`, `arm_ik`, `arm_control` and MoveIt
are **byte-identical**.

| | |
|---|---|
| perception VALID at the start | **8 of 8** |
| approach `arrived` | **8 of 8** |
| `check_target_pose` accepted the perception-derived fix | **8 of 8** |
| IK + MoveIt planned and executed | **8 of 8** |
| **grasp physically verified** (object rose, read from gz) | **8 of 8** |
| **placement physically verified** (object back on its deck) | **7 of 8** |
| fixes inside the window [0.1510, 0.1565] | **8 of 8**, 0.15341-0.15471 |
| median run | 71.0 s |

Four colours at 0.45 m, blue at 0.30 / 0.45 / 0.70 m, blue at laterals
0.000 / −0.010 / +0.030. No per-colour manipulation logic exists and
none was added.

**THE CORRECTION THE LIVE HALF MAKES TO THE STATIC HALF.** Both lateral
placements were judged `OFF_ARM_PLANE` by the static verdict and **both
grasped successfully**:

| lateral | perception `y` | static verdict | `y` delivered to the grasp | live |
|---|---|---|---|---|
| −0.010 | +10.2 mm | OFF_ARM_PLANE | **+1.68 mm** | **grasped, verified** |
| +0.030 | −29.2 mm | OFF_ARM_PLANE | **−3.0 mm** | **grasped, verified** |

`approach_server`'s `align` phase pivots until the bearing is nulled and
only then takes the fix the creep and grasp use, so the offset is
absorbed rather than carried. `reachability_after_approach` models the
approach as translation-only — its docstring says so — and therefore
**under-predicts** feasibility. That is the safe direction for a gate to
be wrong in, but it is a **lower bound, not a forecast**. Not changed;
measured and recorded. Both lateral runs are `n = 1` and 30 mm is the
largest offset tried, not a characterised limit.

**The one failure, and the gap it exposed.** `blue` at 0.30 m: grasp
succeeded, placement did not. With `PLATFORM_Z = 0.64984` and
`TARGET_HEIGHT = 0.158`, a standing cylinder's centre is at **0.72884**
and one lying on its side at `0.64984 + r` = **0.66384**. The instrument
read 0.72884 (standing) right after the approach; `grasp_server`'s own
pre-grasp read was **0.6638 — already down**. The target was **toppled
during the pick sequence**; which motion did it was **not isolated**
(1 of 1 at 0.30 m, 0 of 4 at 0.45 m, 0 of 1 at 0.70 m).

The magnet then welded to the fallen cylinder, lifted it 43.7 mm, and
**`check_lifted` passed** — correctly by its contract, because it did
come up. So:

> **`check_lifted` verifies the object moved up, not that it is
> upright.** A toppled cylinder is lifted, carried and delivered lying
> down, and every step reports success.

Not fixed: deciding what "upright" means for a grasp allowed to be
imperfect is a design decision, not a patch.

**A second unstated precondition, found the same way.**
`grasp_server.check_released` asserts the placed object stands at
`TARGET_HEIGHT / 2` — the floor **at home**. All eight runs place on the
platform, `PLATFORM_Z` higher, so all eight logged "not standing on the
ground (0.0790)" and `/grasp/place` returned failure — **including the
seven that released perfectly**. Correct in the M6 mission, where the
robot *is* at home; the precondition was simply never written down.
Recorded, not fixed. The instrument answers the physical question
against the deck the object actually started on.

**Tests: 662 passing / 0 failing**, up from 656, on a **clean ROS
graph**, run per package from inside each package directory.

```
coco_config 70   custom_teleop 67   coco_rl 164   coco_perception 117
gazebo_models 41  coco_moveit_config 12  coco_sim 55  coco_mission 136
```

**Still unverified.** The full mission through the executive was not
re-run on the new path — these eight runs are the perception -> approach
-> grasp chain in isolation, deliberately, to keep the Gazebo + RViz +
`move_group` confound out. The climb, the lane hold, the descent and the
delivery at home were not exercised. Eight runs is not a rate; the
standing mission figure is still M6's **19/20**.

**Next.** `point_topic` is opt-in and nothing launches with it yet —
`perception.launch.py` still starts `target_finder`, and that is
deliberate until the executive has run a full mission on the new path.
The next concrete step is exactly that: a full `mission.launch.py` fetch
with `target_pose_node` driving `/perception/target` in
`target_finder`'s place, which is the run that would let the default
move.

## 2026-08-29 — C2-M4.2: the swap needed a second topic, and the mission completed on it

**The task was an integration gate, not a milestone:** run one full
fetch through the real mission executive with `target_pose_node` in
`target_finder`'s place, and prove the C2-M4 pose survives the trip.
It did — but not with the handover C2-M4.1 left behind, and the missing
half was found by reading rather than by spending a run on it.

**The defect, found statically before the simulator was started.**
C2-M4.1's `point_topic` feeds `approach_server` through
`/perception/target`, and that is genuinely all the *manipulation* chain
needs. The *executive* needs something else:
`mission_states._check_search_target` gates `SEARCH_TARGET` on
**`/perception/status`** reading `found=1` with a matching `sel`.
`target_pose_node` publishes `/perception/target_pose/status`, a
different topic whose key set has no `found` in it at all.

So the obvious swap — kill `target_finder`, set `point_topic`, run —
fails like this: zero publishers on `/perception/status`,
`obs.perception.newer_than(entered_at)` never true, `SEARCH_TARGET`
never leaves RUNNING, and the mission dies on the state's 15 s timeout
with `TARGET_NOT_FOUND`. A topic-name problem wearing a perception
diagnosis. **First broken boundary: the subscriber assumption** — not
the message type, not the QoS, not the frame, all three of which were
already compatible (`geometry_msgs/PointStamped`, depth 10, RELIABLE,
`base_footprint`).

**Built.** Four files, and no algorithm in any of them:

- `coco_perception/coco_perception/target_pose.py` — new pure function
  `finder_status_fields(observation)`, mapping a `TargetObservation`
  onto `target_finder`'s `/perception/status` fields. Returns a dict, so
  the module stays free of any `target_finder` import and the *format*
  has exactly one definition, in `target_finder.format_status`, which
  the node calls with these fields. Geometry is gated on `is_valid`,
  mirroring `target_finder`: a compat line whose whole purpose is
  substitutability has to be substitutable in behaviour, not merely in
  key names. `lane` and `age` render `--` because this pipeline computes
  neither and a plausible invented number is the failure the `--`
  convention exists to prevent.
- `coco_perception/coco_perception/target_pose_node.py` —
  `status_compat_topic`, **empty by default**, exactly like
  `point_topic`. Set to `/perception/status` the node answers the
  vision gate with its own verdict, `found=1` iff `validity == VALID`.
  Published on the existing 5 Hz status timer, so it keeps arriving
  whether or not a frame did — the executive ages the topic against the
  state's entry time.
- `coco_perception/launch/perception.launch.py` — `target_source`,
  `target_finder` (default) or `target_pose`, dispatched in an
  **`OpaqueFunction`**. Not two `IfCondition`s: two conditions over one
  argument can both be false on a typo, which launches a mission with no
  perception at all, and both can be true if someone edits one and not
  the other, which is two estimates racing for `/perception/target` with
  the grasp taking whichever landed last. The function returns a
  one-element list and raises on an unknown value. It also sets **both**
  handover parameters together, because setting one without the other is
  precisely the defect above.
- `coco_mission/launch/mission.launch.py` — declares `target_source` and
  forwards it. That is the whole of the mission-side change.

**Not changed:** `target_finder.py`, `approach_server.py`,
`grasp_server.py`, `arm_ik.py`, `arm_control.py`, `mission_states.py`,
`mission_executive.py`, MoveIt, Nav2, AMCL, the arbiter, the map, the
robot model, the world, the action space, the policy. The default is
still `target_finder`, so the path M6's 19/20 was measured on is
untouched and still what a bare `mission.launch.py` starts.

**Measured — one full fetch, and it completed.** Fresh simulator, clean
graph, sim time, `rviz:=false`, never `--fast`, publisher counts checked
before *and* after.

```bash
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py rviz:=false \
    target_source:=target_pose target_colour:=blue policy:=<zip>
ros2 service call /mission/start std_srvs/srv/Trigger
```

**COMPLETE, all 16 states, `retries=0`, `reason=--` at every sample,
178 s** from LOCALIZE to COMPLETE. `/perception/target` and
`/perception/status` each had **exactly one publisher, `target_pose_node`**,
before and after; `target_finder` never ran; one executive; `/amcl`
`active [3]`. Both legacy consumers of `/perception/status` —
`mission_executive` and `mission_hud` — took the compat line unchanged.

The chain, measured: first `found=1` was
`sel=blue found=1 u=168 v=162 area=30 w=5 h=6 range=1.378 x=1.503
y=-0.050 z=-0.189 lane=-- seen=green,blue,yellow age=--`, and
`SEARCH_TARGET` passed on the first sample after entry. **62 `found=1`
samples and 62 `validity=VALID` samples — the same number**, which is
the check that `found` is exactly `validity == VALID`. 190 points on
`/perception/target`. Approach `outcome=arrived`, travel 1.139 m,
bearing nulled to `-0.000`. Grasp `x=0.1540 lifted=1 outcome=held`, then
`outcome=placed` — **0.1540 is inside the 5.5 mm window
[0.1510, 0.1565]**, and it came from the camera.

`RETURN_HOME` succeeded in 59.9 s. That is KNOWN PROBLEMS 1's leg, and
it is now the second consecutive success under light load with RViz off.
**Three of six recorded legs have failed; six is still not a rate** and
it stays open for C2-M5.

**Tests: 684 passing, 0 failing** (was 662). All 22 new tests are in
`coco_perception`, which moves 117 → 139: twelve on the compat line
(`found=1` only when VALID, `found=0` for each of the five non-VALID
states, the key set is `target_finder`'s exactly, geometry withheld
unless valid, `range` is the axis and not the surface, `lane`/`age`
absent rather than invented), four on the parameter (off by default,
conditional publisher, separate from the node's own status topic,
published on the status timer), and six on the launch invariant (each
source builds **exactly one** node, the two are different executables,
an unknown value **raises**, `target_pose` sets **both** handover
parameters, and the default is still `target_finder`). Run per package,
cwd inside each, on a clean graph.

**What this is not.** One run. The standing mission figure is still
M6's **19/20**. This is an existence proof that the swap works through
the executive — not a rate, not a comparison against `target_finder` on
the same course, and no claim the new path is better. It is measured to
**work**, not to win.

**Two known verification limitations, deliberately untouched.**
`VERIFY_PLACEMENT` passed here, and that is a precondition holding, not
a fix: `check_released` asserts the floor height **at home**, and this
mission places at home. C2-M4.1's finding that it fails every correct
*platform* placement stands, and the platform figure stays **7 of 8**.
`check_lifted` still verifies the object moved **up**, not that it is
**upright**. Neither was changed; the gate did not require it.

**Next.** C2-M5 — localization health and recovery. `RETURN_HOME` and
M6's run 15 are both its benchmark. Read `docs/ROADMAP.md`'s C2-M5 block
first.

```bash
# reproduce this run
source ~/ros2_ws/c2m31_overlay/env.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py rviz:=false \
    target_source:=target_pose policy:="$COCO_POLICY"
ros2 topic info -v /perception/target | grep -i 'publisher count'  # must be 1
ros2 lifecycle get /amcl                                           # active [3]
ros2 service call /mission/start std_srvs/srv/Trigger
```

## 2026-08-31 — C2-M5.0: covariance is the wrong signal, and the wheel path has a loop

**Milestone:** C2-M5.0, localization health characterization. The first
of two C2-M5 sessions. **No recovery was implemented, deliberately** —
the rule for this session was OBSERVE → CLASSIFY → DEFINE, and only then
RECOVER.

**Branch:** `coco2-m1-observability`. State layer on `coco2-state`.

### What was built

* **`docs/data/c2m5_locrec.py`** — a subscribe-only recorder for the
  whole localization stack at 10 Hz: AMCL pose and covariance, `map->odom`
  and its age, wheel odometry, the four stages of the command chain,
  collision-monitor state, `navigate_to_pose` status, the plan, RTF, and
  a `gt_`-prefixed ground-truth block for **offline scoring only**. It
  also computes, from the map and the laser alone, the **likelihood field
  `nav2_amcl` scores particles against and never publishes**.
  `--topology` prints the command chain off the live graph.
* **`docs/data/c2m5_analysis.py`** — per-state scoring and the
  healthy-vs-bad range table.
* **`coco_mission/scripts/localization_health.py`** — the pure health
  core. **Imported by nothing**, by design. 30 unit tests.
* Added `c2m5_locre[c]` to `ros_clean.sh`.

### What was measured — five missions, fresh simulator each, never `--fast`

| run | injection | RETURN_HOME | outcome |
|---|---|---|---|
| `healthy1` | none | 80.3 s | **COMPLETE**, home to 0.078 m |
| `healthy2` | **none** | 12.0 s, 3 attempts | **ABORT** |
| `obstacle1` | a cylinder into the corridor | 50.0 s | **COMPLETE**, home to 0.079 m |
| `diverged1` | `/initialpose` −3 m in y, tight covariance, plus heading error | 131.5 s | **ABORT** `RETURN_FAILED` |
| `diverged2` | the same, heading preserved | 24.7 s | **ABORT** `RETURN_FAILED` |

**`healthy2` failed with no injection at all** — the spontaneous
return-home failure KNOWN PROBLEMS 1 describes, caught with
instrumentation running for the first time.

### The three findings

**1. AMCL's covariance does not detect a divergence, and points the wrong
way.** `sigma_xy` fell to **0.070 m** — below anything in either leg that
finished — at the instant the pose became 3 m wrong, and took **24.5 s**
(13.9 s on the second run) to pass the healthy maximum. On common ground
the run that was 3.14 m wrong had the **lowest** covariance of all five
(0.281 vs 0.370/0.389/0.372). `healthy2`, the uninjected failure, had the
lowest whole-leg median of all five. Part of the dip is imposed by the
injection; the time AMCL took to notice is not.

**2. The scan-vs-map likelihood detects it in 0.4 s, replicated on both
divergence runs**, and stayed outside the healthy envelope for 62.6% and
91.5% of those legs. It is computed from the map, the laser and TF — no
ground truth.

**3. The command chain loops, and the collision monitor's gating never
reaches the wheels.** `nav2_bringup` remaps `controller_server` and
`velocity_smoother` to `/cmd_vel_nav`; `nav.launch.py arbiter:=true`
points `cmd_vel_relay`'s **output** at the same topic. Confirmed on the
live graph: **7 publishers, 2 subscribers**. Measured at the wheels, the
robot receives **10.15–10.77 Hz more than the collision monitor
publishes** — exactly `controller_frequency: 10.0` — and during an active
SLOWDOWN, gated cap 0.090 m/s, wheel commands reached **0.300 m/s** on
84.2% of `obstacle1`'s slowdown samples. **A safety defect, not a
localization problem, and NOT fixed** — the wheel path is frozen and this
milestone's job was to characterize.

### What the evidence does not support

**No threshold was picked.** Class A separates at almost any value.
Class B does not separate: on common ground the gap between the worst leg
that finished and the best that failed is **0.054 m**. `Thresholds` in
`localization_health.py` therefore has **no defaults** and cannot be
constructed without naming every number; `classify()` returns `UNKNOWN`
rather than guess, and `UNKNOWN` is falsy so `if health:` cannot read it
as good news.

**Collision-monitor activity is not the discriminator, in either
direction.** `obstacle1` (finished) and `diverged1` (aborted) logged the
**same 36 PolygonLimit entries**. `diverged2` was 3.2 m wrong with the
monitor at `DO_NOTHING` for the entire leg. And
`/collision_monitor_state` is **edge-triggered**: `healthy1` received
**zero messages in 219.7 s**, so silence and "not running" are identical
to a subscriber.

**Not reproduced:** the 2026-08-17 `PolygonStop` stall, and the 4.8 Hz
control loop. RTF never fell below 0.818 and `/scan` held 10 Hz in all
five runs, with RViz off throughout — consistent with the degradation
being load-induced, and not establishing it. Both stay open.

### Two defects found in my own instrumentation, and what they cost

* **`/mission/state` is a whole `key=value` line, not a label.** Reading
  it raw made every 2 Hz republication look like a transition and meant
  `--stop-on-terminal` could never match. Fixed in the recorder and in
  the injector, where it would have meant the injection silently never
  fired.
* **The first recorder ran on the system clock, not sim time.** Every
  `*_age` column came out as the Unix epoch and `rtf` was
  d(wall)/d(wall) ≡ 1.000 — a number that looks like a healthy simulator
  and is a tautology. `use_sim_time` is now forced, with the tick timer
  on a steady clock so a stalled `/clock` is still recordable.
  `healthy1`'s age and RTF columns are excluded from the results; its
  other columns are unaffected and are used.

**And a frame trap worth the line it costs.** `/amcl_pose` is in the
**map** frame, `/model/coco/odometry` in Gazebo's **world** frame, and
map (0,0) is world (−2, 0) — `mission_states.WORLD_TO_MAP_X`, which
already existed. Subtracting them raw makes the healthy run read as
**2.2 m of localization error on a mission that finished 0.078 m from
home**.

**Tests: 714 passing, 0 failing** (was 684). All 30 new tests are in
`coco_mission`, 136 → 166. Run per package, cwd inside each, on a clean
graph.

### Next

**C2-M5.1 — localization recovery and mission resume.** The requirements
it inherits are in `RESULTS.md`, "Recovery requirements for C2-M5.1". The
first one is the awkward one: **the collision monitor cannot be relied on
to stop the robot**, so the stop must be the arbiter's and must be proved
at the arbiter.

```bash
# reproduce any run in this session
source ~/ros2_ws/c2m31_overlay/env.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py rviz:=false \
    target_source:=target_pose policy:="$COCO_POLICY"
ros2 lifecycle get /amcl                                    # active [3]
python3 docs/data/c2m5_locrec.py --topology                 # 7 pubs on /cmd_vel_nav
cd docs/data && python3 c2m5_locrec.py --out run.csv --events run_events.txt \
    --tag mytag --hz 10 --map ../../gazebo_models/maps/coco_world.yaml \
    --stop-on-terminal &
ros2 service call /mission/start std_srvs/srv/Trigger
python3 docs/data/c2m5_analysis.py docs/data/c2m5_*.csv --states --compare
```


## 2026-08-31 — C2-M5.1: localization health, recovery, and what it cannot fix

**Built.** `localization_monitor.py`, the ROS face of C2-M5.0's pure
`localization_health.py`; a `RELOCALIZE` state in `mission_states.py`
reached only from `RECOVERY` and only for a localization failure; the
`/reinitialize_global_localization` + Spin recovery in
`mission_executive.py`; `docs/data/c2m51_hrec.py` (health recorder) and
`docs/data/c2m51_inject.py` (the C2-M5.0 class-A injection, written down
for the first time); `HOW_TO_RUN.md`.

**Measured.**

* The threshold, from the committed C2-M5.0 CSVs and not from a search:
  `lik_mean_d > 0.40 m`, strictly above every gated sample on a leg that
  finished (largest 0.3851).
* Experiment 1, one healthy mission with the signal published and unread:
  **COMPLETE**, 1714 samples, **0 INCONSISTENT on mapped ground**.
* Experiment 4, the final nominal mission with everything on:
  **COMPLETE in 184 s, `attempts={}`, 0 triggers**, wheel-topic publisher
  count 1.
* Detection latency for the class-A injection: **3.33 s, 4.52 s, 82.9 s**
  across three runs. Highly variable, and that is a property of the
  signal.
* Safe stop: `RECOVERY → RELOCALIZE` in **0.30 s / 0.40 s**, proved at
  the arbiter (`active=none`), never by a dwell.
* Recovery duration, entry to health re-verified: **9.1 s to 33.9 s**.
* Tests **829 passing / 0 failing**, up from 714. All 115 new ones are in
  `coco_mission` (166 → 281).

**Five defects found live and fixed, each with a test.** The node built
its own `Thresholds` and silently kept a default; `amcl_age` is not a
staleness test on an event-driven topic; strict-contiguity persistence
discarded real evidence; the two latches could both be set; the
mapped-ground gate was x-only and blanked the corridor the robot drives
home through; the recovery shared a retry budget Nav2's own abort had
already spent; and the resume did not wait for the spin to finish.

**Unverified, and stated as such.** No live run produced degradation →
recovery → resume → **COMPLETE**. The recovery restores the health
signal but not reliably a pose Nav2 can plan from, for two measured
reasons: `recovery_alpha_fast/slow: 0.0` means AMCL cannot escape a
confident wrong mode, and global relocalization on this near-rectangular
map converged to world (2.60, −0.64) — inside the wedge — after which
the planner reported "Start occupied". Evidence in
`docs/data/c2m51_planner_after_recovery.txt`.

**Not touched, deliberately.** The `/cmd_vel_nav` loop and the collision
monitor's gating. AMCL's parameters — `recovery_alpha_*` is diagnosed,
not changed, because tuning AMCL to make one mission succeed is the thing
NEXT EXACT ACTION forbids.

**Next command to run:**

```bash
source ~/ros2_ws/c2m31_overlay/env.sh
cd ~/ros2_ws/src/coco-robot-ros2/coco_mission && python3 -m pytest test -q
```

---

## 2026-08-31 — Release: one repository, one branch, and the numbers re-measured

**What this session was.** No feature work, by instruction. Consolidate,
verify, document, release. COCO 2.0 is frozen at C2-M5.

**The consolidation.** The work was split across two branches by
`docs/STATE_PROTOCOL.md`: implementation on `coco2-m1-observability`,
and `PROJECT_STATE.md` / `docs/ROADMAP.md` / `docs/STATE_PROTOCOL.md` on
`coco2-state`. Both descend from the trunk at `33110a6`. Neither is
readable alone, so the release is their union, taken as a real merge
rather than a copy. The only conflict was `.gitignore` and both sides
were kept. Verified afterwards by diffing the merge against each parent:
**no file from either side is missing**, and both trunks are ancestors.
The ancient `main` (a Layer-1 stub) is also an ancestor, so
fast-forwarding it loses nothing.

**Measured this session, on the consolidated tree:**

* **Tests: 829 passing, 0 failing, 0 skipped.** Per package, cwd inside
  the package, clean ROS graph, against a fresh overlay built from the
  release tree: `coco_config` 70, `custom_teleop` 67, `coco_rl` 164,
  `coco_perception` 139, `gazebo_models` 41, `coco_moveit_config` 12,
  `coco_sim` 55, `coco_mission` 281. Run twice — before and after the
  documentation work — with the same result.
* **One nominal fetch mission: COMPLETE.** Fresh simulator,
  `gui:=false`, `rviz:=false`, never `--fast`,
  `target_source:=target_pose`, colour blue. All four pre-start
  invariants passed (AMCL `active [3]`, publisher count 1 on each of
  `/perception/target`, `/perception/status`, `/localization/health`,
  `/diff_drive_controller/cmd_vel`). All 16 nominal states,
  **`attempt=1` on every sample and `reason=--` throughout**, **186.7 s**.
  Grasp verified from Gazebo ground truth: **lifted 35.1 mm**
  (z 0.7288 → 0.7639), inside the M6 band of 33.9–35.9 mm.
  `place finished: placed`. Final line:
  `MISSION COMPLETE: result=fetch reason=-- attempts={}`.
* **Localization health on that mission: 0 triggers.** `degraded=0` on
  **all 5,784 samples**; 5,173 `CONSISTENT`/`OK` and 611
  `UNKNOWN`/`OFF_MAPPED_GROUND` — the ramp and platform, excluded by the
  mapped-ground gate by design. Committed as
  `docs/data/release_nominal_mission.txt`.

**One field that reads like a failure and is not.** The `/mission/state`
status line's `retries=` field is the contract's `max_retries` **budget**
(`contract.max_retries`), not a count; `attempt=` is the counter. A first
pass at scoring the run flagged 344 samples as retried because it matched
`retries=[1-9]`. The run used no retries at all.

**Corrections made to the documentation, each checked against source:**

* **The executive has 19 states, not 16.** 16 is the *nominal path*;
  `RECOVERY`, `RELOCALIZE` and `ABORT` are the other three. Both numbers
  now appear, each labelled with its frame.
* **Nine packages, not eight.** Eight carry test suites; `coco_web` has
  no `test/` directory.
* **The `CLAUDE.md` test baseline was 404**, four milestones stale.
* **`CLAUDE.md` contradicted itself** on the six "pre-existing"
  `flake8`/`pep257` failures: one paragraph explained they were a
  wrong-cwd artefact, the next still counted them as a standing
  allowance. Resolved in favour of the measurement.
* **`PROJECT_STATE.md` claimed "C2-M5 … NOT STARTED"** while C2-M5.0 and
  C2-M5.1 were both complete — exactly the drift the file exists to
  prevent.

**Documentation.** `README.md` rebuilt for a reader who has never seen
the milestone numbering: what the robot does, then measured results, then
**Known limitations** stated plainly, then the engineering lessons, and
only then the historical M0–M6 / M7 tracks. `HOW_TO_RUN.md` gained the
Clone section it lacked and lost the side-overlay instructions, since the
branch they worked around is now merged; every launch file, RViz config,
executable and `docs/data` script it names was checked to resolve against
a build of this tree. `PROJECT_STATE.md` frozen: 1764 lines to 1294, with
every section carrying measured evidence kept verbatim. `ROADMAP.md`
closed and C2-M6…C2-M9 relabelled *scoped, not undertaken*.
`STATE_PROTOCOL.md` marked historical — a clone of `main` is now
sufficient and no branch hides code.

**Two limitations are deliberately kept prominent** rather than softened,
in `README.md`, `PROJECT_STATE.md` and `CLAUDE.md`: severe confident AMCL
divergence is **detected but not reliably recovered** to a Nav2-plannable
pose, and the `/cmd_vel_nav` topic loop means **the collision monitor's
gating does not reach the wheels**. Neither was fixed. Both are
characterized with the runs that show them.

**Next command to run:**

```bash
source ~/ros2_ws/src/coco-robot-jazzy-2.0/setup_env.sh
cd ~/ros2_ws/src/coco-robot-jazzy-2.0/coco_mission && python3 -m pytest -q
```

---

## 2026-08-31 — Public release: one demo, and the policy ships with the repo

**What this session was.** No feature work, by instruction. Simplify the
public entry point so a stranger can clone, build, launch once and watch
the fetch. The autonomy was not touched.

**The problem with the previous guide.** It asked the reader to run four
demonstrations — fetch, terrain, perception, localization — each with its
own terminals, invariant checks and harness scripts. Those are components
of one mission, and presenting them separately made a finished robot read
as a workspace. `HOW_TO_RUN.md` is now one flagship demo: **540 lines to
235**, four demos to one, three commands.

**Three setup defects fixed, each of which blocked a documented command:**

* **`COCO_POLICY` is gone.** The trained ramp policy was a file on the
  author's machine that the reader had to find and export. It is 149 KB.
  It now ships at `coco_rl/policies/phase5_24deg_s0p0.zip` (md5
  `1421ce4af745a8f60f5591efedcdc485`, byte-identical to the curriculum
  artefact), installs to `share/coco_rl/policies/`, and is
  `mission.launch.py`'s `policy` default, resolved through the ament
  index so it carries no machine-specific path. `.gitignore` gains one
  negation; `*.zip` still ignores every other training artefact.
* **`rosdep install` now works.** `coco_sim/package.xml` line 13 contained
  `pip --user install` inside an XML comment, and `--` is not legal there,
  so rosdep refused the whole tree. **Measured both ways: exit 1 before,
  exit 0 after.** The guide can now document the dependency step instead
  of apologising for it.
* **`docs/RUNNING.md` no longer hard-codes `/home/gautham/`.** Five
  `policy:=` invocations lost their absolute paths; the policy defaults.

**Measured this session, on this tree:**

* **Flagship mission: COMPLETE.** Exactly the three commands the new guide
  documents, no policy argument, Gazebo GUI on, `rviz:=false`, fresh
  simulator, never `--fast`. All four pre-start invariants passed. All 16
  nominal states in order, **`attempt=1` and `reason=--` throughout**,
  **303 s**, grasp verified from Gazebo ground truth at **35.1 mm** lift
  (z 0.7288 → 0.7639), `place finished: placed`,
  `MISSION COMPLETE: result=fetch`. Committed as
  `docs/data/release_flagship_mission.txt`.
* **The run before it aborted, and it is in that file too.** With both
  renderers on it fetched correctly and then failed `RETURN_HOME`:
  `planner_server` refused every path because AMCL came off the descent at
  (6.14, **4.20**), outside the global costmap. Known failure class,
  reported rather than dropped.
* **Tests on the three changed packages: `coco_rl` 164, `coco_sim` 55,
  `coco_mission` 281 — all passing**, cwd inside each package, clean ROS
  graph. Unchanged from the 829 baseline.
* **Build: `Summary: 9 packages finished`, 0 errors.**

**Repository shape.** `release-consolidation` was merged into `main` as a
fast-forward and every other branch deleted, local and remote, after
verifying each tip is an ancestor of `main`. One branch, `main`, is now
the whole project.

**One thing deliberately not done.** 303 s is not a timing result — the
Gazebo window was rendering and `RETURN_HOME` took 161.7 s against the
headless 81.0 s. The measured nominal stays **186.7 s** from
`release_nominal_mission.txt`. The new guide says so.

**Next command to run:**

```bash
cd <clone> && source ./setup_env.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true
```

## 2026-09-17 — C2-NAV.43: the command-path fix integrated from `main`, and an optional depth source measured

Branch `c2nav43-integration`, cut from `main` (`ea66155`), pushed to `jazzy2`,
**not merged**. Full report: `docs/agents/C2-NAV.43_RESULTS.md`.

**Built.**
- The C2-NAV.42 fix, integrated commit by commit after inspection: `d707327`
  wiring, `8bf1fe4` tests, `57f75d8` gz world-path quoting, the net of
  `ad2b8b8` (accepted nav2 defaults, sha256 `6f61e499…`), `9412719` docs,
  plus the tour tooling at `1235502` as files. No run data came across.
- `depth_cloud.launch.py`: `image_proc` resize x0.5 nearest, then
  `depth_image_proc` → `/camera/depth/points`, off by default
  (`nav.launch.py depth_cloud:=false`).
- A narrow `perception` experiment key and `verify-perception` in
  `nav_params_overlay.py`.
- Experiments `baseline_lidar_only.yaml` and `depth_fusion.yaml`, which
  differ only in `perception`.
- The instruments `docs/data/c2nav43_perception.py` (sensors | rates | capture
  | record | selftest), `c2nav43_compare.py` and `c2nav43_ramp.py`.

**Measured.**
- Tests 940 / 0 / 0 on the integrated tree and **975 / 0 / 0** on the final
  one.
- Live topology B: 13 / 13 chain links; a held raw 0.30 m/s gave wheels above
  the monitor 0 / 278, STOP held 0.249 m from the wall.
- Tours: A 7/7 (exceeded 0 / 2072); B 6/7 (bypass 0, stale drops 0).
- `/camera/points` is in the link convention under an optical frame_id
  (median error 0.0015–0.0020 m against the link projection, 0.64–0.73 m
  against optical).
- A full-resolution cloud (1.23 MB) reached a best-effort raw subscriber once
  in 12 s; the half-resolution one, 14.97 Hz.
- Capture: 0 phantoms at six poses in every arm; ramp coverage 0.086 → 0.904
  and 0.058 → 0.864.
- Part K (3 + 3 fresh, topology B): legs **16/21 → 18/21**, entry 1/3 → 2/3,
  exit 0/3 → 1/3, deadlocks 5 → 2, raw bypass 0 in all six. Off-geometry
  marks while driving **15,438 → 50,068**. Nav2 CPU 1.196 → 1.195 cores, plus
  0.125 for the depth nodes.

**Verdict.** The command-path fix is KEPT. Depth fusion is KEPT AS CANDIDATE,
not made default.

**Unverified.**
- M6 19/20 on the fixed path.
- Ramp navigation with fusion (no tour leg drives it).
- The cause of the 3.2× stale marks: consistent with a planar-LiDAR clearing
  asymmetry, not tested.
- The attribution of the trace residual (0.088–2.92 % per tour).
- N = 3 is not statistical.

**Traps paid for this session.**
- `ros_clean.sh`'s new `c2nav43_perceptio[n]` pattern matches any Bash call
  whose text names the instrument, so the session runner refused twice. Run
  the instrument in a command of its own.
- A shipped-params path containing `nav2_` in an instrument argument trips
  the same guard; use a copy named without it.
- `nav2_voxel_grid` marks a voxel with bits k AND k+16; the low bit alone
  means unknown. The first decoder put every column top at 0.8 m.
- A background tour sequence dies with the Claude session that launched it
  (`baseline_lidar_only_r03`, marked VOID). Launch long sequences with
  `setsid nohup`.

**Next command to run** (M6 on the fixed path, a fresh sim per run, both
terminals with `setup_env.sh` sourced):

```bash
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true   # T1
ros2 launch coco_mission mission.launch.py rviz:=false              # T2
```

## 2026-09-17 — C2-NAV.44: M6 re-measured on the fixed command path

Branch `c2nav43-integration`, HEAD `c8a8206`, clean tree, no production file
changed. Full report: `docs/agents/C2-NAV.44_RESULTS.md`.

**Why.** `PROJECT_STATE.md` KNOWN LIMITATIONS 0 said M6's 19/20 was *not yet
measured* on the fixed path. It was measured with the `/cmd_vel_nav` loop in
place, so it could not be quoted as evidence for the shipping architecture.

**Built** (instruments only, all in `docs/data/`): `c2nav44_m6_run.sh` (the
C2-NAV.42 `live_mission.sh` with the fault injection removed — fresh sim,
bring-up checks, recorders, `/mission/start`, teardown),
`c2nav44_m6_run_traverse.sh` (the same with `executive:=false` +
`traverse_demo.py`), `c2nav44_m6_report.py` (offline, no ROS) and
`c2nav44_poserec.py` (`/amcl_pose` beside ground truth).

**Measured — six fresh executive-driven missions, one simulator each,
depth fusion off, never `--fast`:**
- **3 COMPLETE** (r01 red, r03 blue, r04 yellow) — 16 nominal states,
  `attempt=1`, `attempts={}`, 149.3 / 145.4 / 165.0 s sim.
- **3 ABORT, all green**, all `PRE_RAMP_POSE_OUT_OF_REGION`, before the climb.
- **Command path clean in all six:** raw-controller → wheel bypass **0**,
  wheels above the monitor **0** on Nav2-owned rows, stale command drops
  **0**, PolygonStop activations **0**, exactly one wheel publisher, live
  chain 12/12 OK, live nav2 parameter readback 0 mismatches.
- Grasp and approach held the historical bands: lift 35.3 / 34.6 / 35.6 mm,
  base-x 0.1540 / 0.1547 / 0.1546 — 3/3 inside the 5.5 mm window.

**The three aborts, diagnosed (not a command-path failure).**
`NAVIGATE_TO_RAMP` ended 0.3097 / 0.3115 / 0.3047 m from the pre-ramp goal by
ground truth, stopping within 6 mm of the same point across three fresh
simulators, while Nav2 logged `Reached the goal!` and `Goal succeeded` on
every attempt. Nav2's `SimpleGoalChecker` uses `xy_goal_tolerance: 0.25` on
the pose it steers by; the executive re-checks with `GOAL_XY_TOLERANCE =
0.25` on **ground truth**. Two 0.25 m tolerances from two different poses
leave zero margin. Both retries commanded **0.000 m/s** — the same
"structurally futile" retry the repo already documents for the yaw gate.
AMCL was not diverged: with `/amcl_pose` recorded, its error is 0.004–0.049 m
read right after each correction, `degraded=0` throughout. On red/blue/yellow
the estimate lags and the robot stops 0.056–0.147 m out; on green it leads.

**Comparability, and the harness run (`t02_green_traverse`).** 19/20 is
**not** a control: that matrix ran `traverse_demo.py`, whose `nav_to()`
returns on Nav2's `SUCCEEDED` alone and has no ground-truth arrival gate, so
this abort cannot occur in it. Run on this branch, same fixed command path,
fresh sim, `executive:=false` + `traverse_demo.py --colour green`: **all
seven steps, `outcome=held` base-x 0.1545, home to within 0.04 m, `FETCH
COMPLETE`, rc 0, 413 s wall** — the leg the executive rejected three times
was accepted and the mission finished. Command path on that run: bypass 0,
stale drops 0, STOP rows 0, wheels above the monitor 3/947 (0.32 %, inside
C2-NAV.43's unattributed residual). Its home leg took 190.7 s against the
historical single run's 103.6 s — N=1 vs N=1, reported, no causal claim.
**So the command-path fix does not break the fetch.**

**Unverified / not done.**
- Why the estimate's offset sign is lane-dependent. Not investigated: this
  sprint was forbidden from AMCL work, DWB tuning and goal changes.
- Three runs per lane is not a rate.
- No STOP hold occurred in any run, so this sprint adds no new PolygonStop
  evidence beyond C2-NAV.43's controlled test.
- Nothing was changed to improve the number: no gate, tolerance, goal,
  parameter or default was touched.

**Traps paid for.**
- `ros_clean.sh`'s `g[z] sim` pattern kills **every** Gazebo on the machine.
  An unrelated `eyantra_kepler_colony` simulator from `~/ros2_ws` started
  mid-run and the teardown killed it. The runner's refusal check only proves
  the machine was idle at the start.
- A 20 s watcher shelling out to `ros2 topic info` / `echo` creates DDS
  participants; with a second stack up, domain 0 ran out and the **next**
  process to start died with "Failed to find a free participant index for
  domain 0". That voided one run (`t01`), which was replaced.
- `/amcl_pose` publishes only on resample updates, so comparing it to ground
  truth at an arbitrary instant measures staleness, not localization error.

**Next command to run.** Reproduce the abort in ~25 s on one fresh simulator,
or re-run any colour:

```bash
bash docs/data/c2nav44_m6_run.sh ~/coco_nav_runs/c2nav44_m6/rNN_green green
```

---

## C2-NAV.45 — the pre-ramp arrival gate reports instead of retrying (2026-09-18)

Branch `c2nav43-integration`. Fix `56c324b`. A narrow mission-logic sprint:
C2-NAV.44 had already attributed its three green aborts to the executive's
arrival gate rather than to the command path, so this closed that one defect
and re-measured M6 on the green lane.

**What was built.** `mission_states._check_nav_leg` had one threshold and one
verdict, with `xy_tolerance` set to Nav2's own `xy_goal_tolerance` (0.25 m) so
as not to invent a second number — which is exactly what made it a gate with
**zero margin**: Nav2 stops when the pose it is *steering by* is inside 0.25 m,
the check then measured the *true* pose against the same 0.25 m, and any
localisation offset pointing away from the goal failed a leg the planner had
already declared finished. It now has three named bands: clean inside
`xy_tolerance`; **accepted, recorded in `arrival_discrepancy` and logged at
WARN** inside `xy_consistency`; hard failure beyond it, reason unchanged.
`mission_executive._log_event` prints the ground-truth error on every nav leg
and warns explicitly when Nav2 SUCCESS and ground truth disagree.

**The band is derived, not invented.** `GOAL_XY_CONSISTENCY = 2 x
GOAL_XY_TOLERANCE = 0.50 m`. Nav2 halts with its estimate inside 0.25 m, so a
true error past 0.50 m needs the estimate to be wrong by more than the whole
arrival window — a localisation failure, owned by the C2-M5 health monitor
already checked at the top of the same function. Run 15's 3.4 m divergence sits
far outside it. `xy_consistency == xy_tolerance` restores the old gate, and a
test asserts it. Applied in the shared helper, so `RETURN_HOME` gets it too:
the mechanism there is identical and leaving it out would knowingly keep a
futile retry behind.

**Measured — the old behaviour, re-derived this session.** Running the new
`docs/data/c2nav45_gate_report.py` over C2-NAV.44's committed run directories
reproduces its published numbers exactly, which is also the tool's validation:
true error **0.3097 / 0.3115 / 0.3047 m**, Nav2 `Reached the goal!` x3 in each,
7 region failures, 3 RECOVERY entries, 2 retries, and **max wheel speed after
the first stop 0.000 m/s in all three** — the retries provably could not move
the robot.

**Measured — three fresh green M6 missions** (one simulator each, headless,
never `--fast`, depth fusion off, no Nav2/goal/safety change, HEAD `56c324b`
with 0 dirty paths, C2-NAV.44's runner unmodified):

- **3 of 3 COMPLETE**, `result=fetch`, `reason=--`, `attempts={}`, all 16
  nominal states, **0 RECOVERY entries and 0 retries** in every run.
- **The original failure still occurs and is handled**: pre-ramp ground-truth
  error **0.348 / 0.315 / 0.316 m** — outside 0.25 m in all three, bracketing
  C2-NAV.44's range — accepted each time with an explicit WARN.
- Lift **36.0 / 35.4 / 34.9 mm**, `pick finished: held`, `place finished:
  placed`. Home to **0.070 / 0.038 / 0.022 m**, all clean at INFO.
- Pre-climb heading -0.160 / -0.209 / -0.132 rad, reported, gate still off.
- Command path: **bypass 0, wheels above the monitor 0, stale drops 0,
  PolygonStop 0** in all three. Runner 22 PASS / 0 FAIL each.
- Localization: **0 degraded samples, 0 relocalizations** over 6,317 samples.
- Wall time start to terminal: 825 / 450 / 424 s.

**Tests: 997 passing, 0 failing, 0 skipped.** Per package, cwd inside each
package, clean ROS graph. The branch's 975 plus **22** new in
`TestArrivalConsistency`, covering all three bands, the recorded r02/r05/r06
stop points, Nav2 failure with ground truth close, the absence of a second goal
after an accepted arrival, a full fetch from a discrepant arrival, and the
yaw/lane gates unchanged. Measured before and after the live sweep, identical.

**Unverified / not claimed.** AMCL is unchanged and the lane-dependent sign of
its offset is still undiagnosed. Localization recovery, the enclosure problem
and depth fusion are untouched. The collision monitor's 0.088-2.92 %
short-streak residual is not refuted by three clean runs. **Three runs of one
colour is not a rate** — this says the demonstrated abort no longer occurs, not
that M6 has a new success percentage. 19/20 remains not a like-for-like
comparison.

**Trap paid for.** Comparing Nav2's wall-clock log stamps against the
executive's *mission* clock made a healthy 165 s home leg look like a 398 s
overrun of a 240 s budget. `/mission/state` carries `elapsed=` and `timeout=`;
read those, not the difference between two nodes' log timestamps.

**Next command to run.** Re-measure the other three colours on the fixed gate,
to turn "the green abort is gone" into a fetch matrix:

```bash
bash docs/data/c2nav44_m6_run.sh ~/coco_nav_runs/c2nav45_m6/r04_red red
```

---

## 2026-09-18 — C2-NAV.46: the M6 fetch colour matrix

**Branch** `c2nav43-integration`, sweep at `ff98171`/`e73494d`, clean tree,
`dirty_paths=0` recorded in all nine new runs.

**What was built.** Nothing in the runtime. Two offline tools:
`docs/data/c2nav46_matrix_sweep.sh`, the nine-run driver, and
`docs/data/c2nav46_matrix_report.py`, a composer over the two existing
per-run reports (`c2nav44_m6_report.py`, `c2nav45_gate_report.py`), both
left untouched so C2-NAV.44's, C2-NAV.45's and this sprint's numbers stay
directly comparable. Colours were **interleaved by round**, not grouped, so
two hours of machine drift is not confounded with colour.

**What was measured.** Three fresh executive-driven missions each for red,
blue and yellow, fresh simulator per run, headless, never `--fast`, depth
fusion off, no Nav2/goal/planner/controller/safety change. Green's three
C2-NAV.45 runs carried over unchanged.

- **11 of 12 fetches. 12 valid runs, 0 void.** red 3/3, green 3/3,
  blue **2/3**, yellow 3/3.
- **The gate generalises.** All 12 passed the pre-ramp gate, the outer
  0.50 m band was **never reached**, and futile retries were **0 everywhere**.
- **The green discrepancy is lane-specific.** green 0.315-0.348 m uses the
  consistency band in all three runs; red 0.108-0.131 m, blue 0.066-0.085 m
  and yellow 0.030-0.047 m are **clean inside the original 0.25 m tolerance**
  in all nine. Red, blue and yellow would all have passed the *old* gate.
- **Command path clean in all 12:** bypass **0**, stale drops **0**.
- Wheels above the monitor **4 of 9744** nav-active samples = **0.0411 %**,
  worst gap 0.0316 m/s.
- Grasp **12/12** inside `[0.1510, 0.1565]` (0.1534-0.1547 m), lift
  34.5-36.4 mm, across four cylinder radii. Not colour-sensitive.
- Tests **997 passed, 0 failed, 0 skipped**, measured after the sweep.

**The one failure.** `r2_blue`, ABORT `RETURN_FAILED`, a **valid** run (22/22
checks, clean shutdown), classified **navigation**: pre-ramp gate was clean at
0.066 m, the pick succeeded (lift 36.2 mm), and the mission died on the way
home. PolygonStop held the robot **595.5 s**, 5920 rows inside `RETURN_HOME`;
`min_scan_m` 0.15 m; 40 `controller_failed_progress`, 38 costmap clears,
spin x9 / wait x9 / backup x6; ended at world (0.17, 0.35). AMCL was
**CONSISTENT 6873/7486, 0 degraded**, final gap 0.113 m, so not localisation;
bypass 0, so not the command path. The documented `enclosure_entry`/PolygonStop
deadlock class, on the return leg, **intermittent** — the same lane completed
cleanly twice with PolygonStop 0.

**Unverified / not claimed.** Three runs per colour is **not a rate**; 11/12
is not a 92 % reliability figure and blue 2/3 is one failure, not a
blue-specific failure rate. The `r2_blue` deadlock is **classified, not
diagnosed** — no root cause, no fix proposed. The wheels-above-monitor
residual stays **unattributed**. Depth fusion stayed off and is not mixed in.
The per-package test split (notably `gazebo_models` 171 vs the release
table's 41) does not match `CLAUDE.md`'s release baseline though the 997 total
does; not investigated.

**Trap paid for.** The matrix composer, run against the three known-good green
runs *before* any new data existed, scored all three VOID and one as
non-nominal. Both were the tool's fault: `process_died` also catches the
**teardown**, where every launched process dies by design, and the 10 Hz
`state_path_sim` sampler drops `LOCALIZE`, which lasts ~0.1 s. Validate a new
report against a known-good run before trusting it on new runs.

**Next command to run.** The matrix is clean, so the next step is integration,
not another M6 experiment. Review what the branch carries ahead of `main`:

```bash
cd ~/ros2_ws/src/coco-robot-ros2 && git log --oneline main..c2nav43-integration
```

## 2026-09-19 — C2-NAV.47: the C2-NAV.43–46 work prepared as the new main baseline

**Integration sprint, not an investigation.** No runtime code changed. Full
write-up in `docs/agents/C2-NAV.47_RESULTS.md`.

**Built.** Nothing in the runtime. This sprint adds the results document, the
missing `docs/data/README.md` index rows for evidence already committed
without them, this checkpoint, and its own regression readbacks under
`docs/data/c2nav47_live/`.

**One defect the merge itself would have introduced, fixed.**
`c2nav45_m6_sweep.sh` and `c2nav46_matrix_sweep.sh` hardcoded
`WT=<...>/.claude/worktrees/c2nav43-integration` — a path that stops existing
the moment the branch merges. Both now use the self-locating idiom
`c2nav44_m6_run.sh` already used, verified to resolve two directories up to
the repo root and to stay overridable by `COCO_WT`. Their `ROOT` defaults
moved from `/home/gautham/...` to `$HOME/...`.

**Still hardcoded, reported not changed.** `c2nav44_m6_run.sh:41` and
`c2nav44_m6_run_traverse.sh:46` set
`MV=/home/gautham/ros2_ws(personal)/moveit_prefix/...`. That path is the real
workspace's, not the worktree's, so it survives the merge and nothing breaks.
Deriving it would need a live run to validate, and these scripts are the
recorded provenance of committed evidence — not worth changing on a sprint
that is meant to change no behaviour.

**Measured.**
- **Ancestry, checked not assumed:** `main` is `ea66155` and **has not
  moved**; the merge base of `main` and `c2nav43-integration` **equals
  `main`**, so the branch is a strict descendant and **a fast-forward is
  available**.
- **Clean build 9/9, exit 0**, from a wiped `build/ install/ log/`.
- **Tests 997 passed, 0 failed, 0 skipped**, per package, cwd inside each.
- **M6 green: COMPLETE, `result=fetch`**, one fresh executive-driven mission
  at `aa5b968`, `dirty_paths=0`.
- **The arrival gate used both bands in that one run:** pre-ramp 0.290 m →
  WARN, accepted, **no retry**; `RETURN_HOME` 0.108 m → INFO, clean.
- **Command path, mission:** raw-controller → wheel bypass **0** (0/78 bypass
  rows, 0/498 nav-owned). Smoother followed on 90 of 109 rows where raw ≠
  smoothed, 1 raw-only. Monitor SLOWDOWN 18 / LIMIT 5, obeyed.
- **Command path, controlled STOP experiment:** `stop_held: true`, **69 STOP
  rows, 0 with the wheels driven**; smoother **9 of 9**, `wheel_eq_raw_only`
  **0**; monitor authority 252 samples **0 exceeded**. Robot halted with
  `min_scan_m` **0.342 m** while the probe still commanded a raw 0.30 m/s.
- **Arbiter is the sole wheel publisher:** `Publisher count: 1`,
  `cmd_vel_arbiter`, read off the live graph.
- **Depth fusion off, read back live:** no depth-cloud process, all four
  costmap observation sources `scan`.
- **The two production config lines** are the NavigateThroughPoses tree and
  local `cost_scaling_factor` 5.0 → 65.0. `BaseObstacle.scale` was **already
  8.0**; the **global** costmap stays at 5.0; the collision-monitor block is
  **byte-identical to `main`**.

**Resolved, from the last checkpoint's open list.** The per-package test split
*does* reconcile with `CLAUDE.md`'s release baseline — it was new tests, not a
discrepancy. `gazebo_models` 41 + **130** (`test_cmd_vel_wiring` 25,
`test_nav2_params_guard` 7, `test_nav_params_overlay` 63,
`test_perception_experiments` 35) = **171**; `custom_teleop` 67 + 8 = 75;
`coco_mission` 281 + 30 = 311. 829 + 168 = **997**. Nothing is missing.

**Also measured, and worth knowing before trusting a re-run.** The committed
run directories are **slimmed**: re-running `c2nav45_gate_report.py` against
`docs/data/c2nav45_live/r01_green` prints `no arrival recorded`. The report
*outputs* (`gate_report.json`, `matrix.json`, `matrix_report.txt`) are the
committed artefact. Now said plainly in `docs/data/README.md`.

**Unverified / not claimed.** The green pre-ramp discrepancy is now
**0.290–0.348 m over four runs** — this run's 0.290 m is *below* the
previously measured 0.315–0.348 m range. Four runs is **still not a rate**.
The `gated_zero_moving` residual (3 of 498 nav rows, 0.60 %, worst wheel
0.0158 m/s) sits inside the documented 0.088–2.92 % band and stays
**unattributed**. The `r2_blue` return-leg PolygonStop deadlock (595.5 s)
remains **classified, not diagnosed** — untouched here by instruction. Depth
fusion remains a **candidate**: not re-benchmarked, its ~3.2× stale-mark
result and unvalidated ramp driving stand. `coco_web` exits **5**, not the
**4** `CLAUDE.md` records; a documentation nit, left alone rather than edited
silently.

**Next command to run.** The branch is ready and `main` has not moved, so the
merge is a fast-forward. **The human performs it**; nothing here modified
`main`.

```bash
cd ~/ros2_ws\(personal\)/src/coco-robot-ros2
git checkout main
git merge --ff-only c2nav43-integration
```

---

## 2026-09-19 — C2-NAV.48: the branch merged to main, and the blue return-leg deadlock diagnosed

**The merge happened.** `main` `ea66155` → **`1425e6c`**, fast-forward, one
parent, **no merge commit**; `ea66155` verified as an ancestor. The previous
entry's "next command" was exactly this, and it is now done rather than
pending. Zero untracked collisions: the five tracked `C2-NAV.4x_RESULTS.md`
files have different names from the four local `docs/agents/` scaffolding
files, so `docs/agents/` now holds all nine. Local-only state (`.codex/` at
4529 files, `AGENTS.md`, `docs/RSE_ASSIGNMENT_PLAN_V2.md`, the four scaffolding
files and `tatus --short`) was md5-verified into
`~/coco_premerge_backup/20260919_033040/` first and verified intact after.
`tatus --short` is **not** junk — it is a captured `git diff` of the local
`CLAUDE.md` change, and it was kept.

**`CLAUDE.md` conflicted, and was reconciled rather than resolved one way.**
The stashed local version replaces the whole document with a ten-line pointer
to `AGENTS.md`; applied onto the new `main` it would have deleted 288 lines
including the entire C2-NAV.43–47 record. Kept both: the integrated content in
full **plus 14 lines, 0 deletions** adding a "Multi-agent protocol" section
pointing at `AGENTS.md` and `docs/agents/`. Left **uncommitted**, as it was
before the merge, and the stash was left on the stack (`apply`, never `pop`).

**Clean build 9 of 9, exit 0. Tests 997 → 1001, 0 failed, 0 skipped.** The
clean-build wipe was scoped to the nine packages under test rather than all of
`install/`: `<ws>/install` also holds `turtlebot3_*` prefixes whose
`local_setup.bash` is already missing and which `turtlebot3_node` cannot
rebuild, so a full wipe would have destroyed an unregenerable install. Every
package under test still built from scratch.

**C2-NAV.46's `r2_blue` deadlock is diagnosed.** Root cause: **the local
costmap and the collision monitor disagreed about which poses are navigable.**
`cylinder_obstacle` (a static model at (−0.2, 0.6), r 0.2, h 0.6) had its
surface **0.2486 m** from `base_footprint` — **1.4 mm inside** PolygonStop's
0.25 m circle, and **43 mm outside** the costmap's real inscribed radius of
**0.2060 m**. The planner scored that pose **15.8 of 254**; the monitor held the
wheels. The obstacle is identified to **0.9 mm**: predicted laser range to its
surface 0.3657 m against `scan_min` 0.3666 m, the difference explained entirely
by `LIDAR_MOUNT_XYZ = (-0.09, 0.10, 0.20)`, a 0.1345 m offset.

**Why nothing escaped, measured.** PolygonStop is a *circle* with
`action_type: stop`, so it is direction-agnostic. Across the 5955 held rows Nav2
commanded motion in **5423**, including **905** rows of `spin` (`w=+1.0`) and
**603** rows of `backup` (`v=−0.15`). **The wheels moved in 0.** Both escape
primitives were issued and both were vetoed identically. True chassis clearance
was **49 mm** — the robot was never in contact and could have moved.

**The first divergence is 23.8 mm.** `r3_blue` passed the same obstacle at
0.2724 m and completed; `r2_blue` passed at 0.2486 m and held 595.5 s.

**Fix, one parameter:** `local_costmap.robot_radius` **0.20 → 0.25**, so the
inflation layer's inscribed radius goes 0.205965 → **0.255004 m**, 5.0 mm past
the stop circle, and `r2_blue`'s pose becomes cost 253. Verified in Nav2's
source, not assumed: `BaseObstacleCritic::isValidCost` rejects
`INSCRIBED_INFLATED_OBSTACLE` and `scorePose` throws
`IllegalTrajectoryException`, and that critic scores the **centre** cell — the
same `base_footprint` origin PolygonStop measures from. **`PolygonStop` is
untouched**, honouring C2-NAV.6's ruling that neither of its knobs should move;
this generalises C2-NAV.7's accepted goal stand-off to the *transit* poses a
stand-off cannot reach. The inscribed-radius model reproduces **C2-NAV.0's
measured 0.205879 m to 0.086 mm**, and a test guards that.

**The global costmap is deliberately left at 0.20, and that is measured.** At
`cost_scaling_factor` 5.0 it already prices `r2_blue`'s pose at **203.6 of
254** and avoids the band unaided; the local costmap's 65.0 prices the identical
pose at **15.8**. The defect is local, so the fix is local. A test records it.

**Validated: 6 fresh missions, 6/6 `result=fetch`** — three blue plus red,
green and yellow smoke. **PolygonStop rows 0 in all six.** Closest approach to
`cylinder_obstacle` across them was **0.2905 m**, 40.5 mm outside the stop
circle. Command path: bypass **0** in all six, PolygonStop rows with wheels
driven **0** in all six. Mission regression went the *good* way:
`controller_failed_progress` **0** in all six against 40 in `r2_blue`, goals
aborted 0, RECOVERY entries 0. Arrival gate clean (0.094/0.108 m pre-ramp,
0.062/0.014 m return, **0** WARN-band entries); grasp base-x 0.1539 and 0.1545,
inside the measured window. 0 orphan processes, and all seven run directories
record `ros_clean: 0 matched, 0 still running`.

**Two harness defects had to be fixed before anything could run.** (1) The three
live-run scripts conflated the repo root with the colcon workspace root and
refused to start on `main`; worse, a **stale `<repo>/install` from 2026-07-27
holding one package, `coco_rl`**, did source successfully and layered a
seven-week-old build over the fresh one — the refusal is the only reason that
was not a silent wrong-overlay run. `WS` is now derived as `setup_env.sh`
derives it, overridable by `COCO_WS`. (2) **`<ws>/install` cannot launch Gazebo
at all**: its half-installed `turtlebot3_*` prefixes do not resolve, and
`ros_gz_sim`'s `GazeboRosPaths.get_paths()` enumerates every package in the
index, so one bad entry kills the launch. Measured: `<ws>/install` 1
unresolvable entry, an isolated overlay **0 of 490**. Runs used
`$HOME/c2nav48_overlay`.

**Unverified / not claimed.** **The deadlock was NOT reproduced on unmodified
runtime.** The base rate is 1 in 12, and the three runs that executed were
already on the fixed value — the overlay is `--symlink-install`, so the
installed `nav2_params.yaml` symlinks to source, which was edited at 22:30:50
UTC before Nav2 loaded parameters at ~22:31:36. So KEEP rests on the root cause
measured from C2-NAV.46's own trace, the mechanism verified in Nav2's source,
and six post-fix missions without regression — **not** on an A/B against a
reproduced failure. Six runs is **not a rate**. `robot_radius` is now in
`nav_params_overlay.py`'s `LIVE_CHECKS` for both costmaps so no future run has
to infer it. The **rasterisation residual stands**: at 0.05 m resolution the
inscribed boundary is about one cell accurate, so this is a large reduction in
exposure, not a proof. One run was **VOID** — `nav2_container` died in
bring-up to a SIGSEGV reported by ImageMagick's handler, caused by running the
runner under `env -i` (3 of 3 aborts, against 0 of 3 for the C2-NAV.46 worktree
runs, and bring-up slowed 19 s → 2 min 42 s); isolating only the ROS/colcon
variables fixed it. **Do not run these harnesses under `env -i`.**
`gated_zero_moving` (0–34 rows, worst wheel ≤ 0.0199 m/s) stays inside the
documented 0.088–2.92 % band and **remains unattributed**. One
`monitor exceeded` row appeared in two of six runs and 0–6 smoother raw-only
rows across them; reported, no mechanism claimed. `PROJECT_STATE.md` and
`CLAUDE.md` still say this deadlock is "classified, not diagnosed" and need
updating — not edited here because the tree carries an unrelated local
`CLAUDE.md` change.

**Next command to run.** Re-measure the colour matrix on the fixed
configuration, to replace C2-NAV.46's 11-of-12 with a figure measured on
`robot_radius` 0.25:

```bash
cd ~/ros2_ws\(personal\)/src/coco-robot-ros2
COCO_WS=$HOME/c2nav48_overlay \
  bash docs/data/c2nav46_matrix_sweep.sh ~/coco_nav_runs/c2nav48_matrix
```

---

## 2026-09-19 — C2-NAV.49: C2-NAV.48 integrated, and the colour matrix re-measured on `robot_radius` 0.25

**What was built.** Nothing new in the runtime. C2-NAV.48 was integrated onto
`main` and its fix validated across all four lanes. Branch
`c2nav49-integration` from `main` @ `1425e6c`, fast-forwarded to `04f9711`:
C2-NAV.48 is a strict two-commit descendant, `ea66155` is an ancestor, and
inspecting both commits showed nothing experiment-only in runtime code, so a
selective cherry-pick would have changed the tree for no reason. Added:
`docs/data/c2nav49_matrix_sweep.sh` (four colours x three rounds, interleaved),
`docs/data/c2nav49_clearance.py` (the deadlock-mechanism reader), the
`ros_clean.sh` scope fix and its three tests, and
`docs/agents/C2-NAV.49_RESULTS.md`.

**What was measured.** **12 of 12 fetches, 12 valid runs, 0 void — red 3/3,
green 3/3, blue 3/3, yellow 3/3.** All four colours re-run with none carried
over, because a changed costmap parameter invalidates every lane. Fresh
simulator per run, headless, never `--fast`, depth fusion off, `dirty_paths=0`,
**22 runner checks passed / 0 failed** in all twelve, 16 nominal states, 0
re-entries, Nav2 goals 2 succeeded / 0 failed / 0 aborted, 0 recoveries, 0
relocalizations, clean shutdown. Live readback confirmed
`local_costmap.robot_radius` **0.25** and `global_costmap.robot_radius`
**0.20** in every run, with PolygonStop 0.25 / 4, CSF 65 / 5, BaseObstacle
8.0 and the NavigateThroughPoses tree unchanged.

**The blue deadlock did not recur.** Over all twelve traces: PolygonStop rows
**0**, episodes **0**, duration **0.0 s**, stop-with-wheels-driven **0**,
`controller_failed_progress` **0** (C2-NAV.46's `r2_blue`: 40), costmap clears
**0**. Closest approach to `cylinder_obstacle` in any run **0.2894 m**
(`r1_blue`, return leg), **39.4 mm outside** the 0.25 m stop circle. Blue is
the exposed lane by geometry — **0.2894 / 0.4024 / 0.3335 m**, all three on
the return leg — against green 0.4054–0.5343, yellow 0.4532–0.4628 and red
never closer than **0.6214 m**. Grasp 12 of 12 inside `[0.1510, 0.1565]`
(0.1535–0.1547 m), lift 34.1–36.6 mm, mission 145.6–192.4 s sim. Tests
**1004 / 0 / 0** (`gazebo_models` 178). 9/9 packages built, colcon exit 0.

**Unverified / not claimed.** **The fix's mechanism was never exercised.** It
works by making the 0.2059–0.25 m band inscribed-lethal, and **no run entered
that band**: 0.2894 m is outside even the *old* 0.205879 m inscribed radius,
so none of these twelve would have deadlocked on 0.20 either. This matrix is
**not an A/B of the fix** — it shows no recurrence and no regression on the
corrected value, nothing more. KEEP still rests where C2-NAV.48 put it: a root
cause measured from C2-NAV.46's own trace and a mechanism verified in Nav2's
source. **Twelve runs is not a rate; 12/12 is not a 100 % figure.**
`min_scan_m` is useless for clearance here — it saturates at the 0.15 m LiDAR
floor in all twelve, so the ground-truth geometry is the only measure.
**Wheels above the monitor is 8 of 7,781 nav-active samples = 0.1028 %**,
worst gap 0.1250 m/s — *higher* than C2-NAV.46's 0.0411 %, inside the
documented 0.088–2.92 % band, still **unattributed** and **not** claimed fixed
or improved. Green's pre-ramp discrepancy **reproduces** (0.298 / 0.307 /
0.330 m against C2-NAV.46's 0.315–0.348) and is still **green's alone**; the
outer 0.50 m band was never reached and futile retries were 0 in all twelve.
`r1_red` ran at `3a22201` and the other eleven at `553f219`; the only
difference is an offline reader, no runtime change.

**Two environment findings, both re-measured rather than inherited.**
(1) `<ws>/install` still cannot launch Gazebo: **2** unresolvable ament-index
entries — `red_ball_nav` and `turtlebot3_teleop` — against **0 of 462** for an
isolated overlay. C2-NAV.48 measured 1; it is 2 today. Runs used
`$HOME/c2nav49_overlay`, selected with `COCO_WS`. This is the user's
environment and is reported, not changed. (2) `coco_world.world` is **not
well-formed XML** — its prose comments contain `--` (`--randomize`,
`--target`), which XML forbids — so ElementTree refuses the raw file while gz
parses it happily. `c2nav49_clearance.py` strips comments before parsing
rather than editing a world frozen as `world_v1`.

**`ros_clean.sh` no longer sweeps other people's simulators.**
`'g[z] sim'` → `'g[z] sim.*gazebo_models/worlds'`. C2-NAV.44 measured the cost
of the bare pattern: an unrelated `eyantra_kepler_colony` simulator from
`~/ros2_ws` started mid-run and the teardown killed it. **Scoping the sweep to
the current experiment was rejected**, not overlooked — this file exists to
kill orphans of *previous* runs, which are never in the current process group,
and a session-scoped sweep could not kill one of them. Every coco simulator
still matches, in both `gui` modes. Three tests assert **both** directions,
because a test that only checked the foreign simulator survives would also
pass on a pattern matching nothing — a typo that silently disarms the sweep.
Against the pre-fix script in an isolated copy: **2 failed, 1 passed**, the
pass being the positive control. Against the fixed script: **3 passed**.
**Not fixed, not claimed:** a hand-started `gz sim -g` carries no world path
and is not swept; no launch file here starts one.

**Stale artifacts removed.** `<repo>/install` (148K, 2 packages, newest file
2026-07-27 21:35) and `<repo>/build` (56K, 5 package dirs, newest 2026-07-28
16:35) in the main checkout — both `COLCON_IGNORE`d so colcon never refreshed
them, both holding a seven-week-old `coco_rl`, both existing only to be
sourced by mistake. **`<ws>/install` was NOT touched**: it carries the
unrelated turtlebot3 and `red_ball_nav` prefixes, 19 before and after. This
worktree's own `install/`+`build/` (2026-09-19 02:55) were left in place —
gitignored build output, not what C2-NAV.48 flagged, and nothing sources them
now that the runners take their overlay from `COCO_WS`.

**Next command to run.** The matrix is clean and the COCO core is stable
across all four lanes, so the next step is productization, not another
C2-NAV investigation. Merging is the owner's call:

```bash
cd ~/ros2_ws\(personal\)/src/coco-robot-ros2
git checkout main && git merge --ff-only c2nav49-integration
```

---

## 2026-09-20 — P0.2, the platform becomes usable

**Built:**

- `coco_web/mission_view.py` — the executive's state, translated. Reads
  all **twelve** fields `/mission/state` carries; P0.1 read two and
  looked for three (`colour`, `target`, `detail`) that the line has never
  contained, so the mission colour on the wire was permanently null.
  Carries both vocabularies: `phase` (ten product words) and `state` (the
  executive's own name). `RECOVERY`/`RELOCALIZE` keep the phase of the
  state they are retrying; `ABORT` with `OPERATOR_ABORT` is STOPPED, not
  FAILED. Constants duplicated from `coco_mission` (importing it would
  close a cycle) with an `ast` drift test in **both** directions.
- `telemetry.parse_grasp_status` — `/grasp/status` is the one status
  topic whose values contain spaces (`phase=pick:hover above target`), so
  `parse_kv` silently truncates it. Slices to the next known key instead.
- `coco_web/streams.py` — per-client subscriptions, rates and the bounded
  queue. `subscribe`/`unsubscribe`/`set_stream` honoured. Default set is
  P0.1's, which is what let the protocol stay `coco.v1`.
- `coco_web/binary.py`, `imaging.py` — self-describing binary frames for
  LiDAR, camera and depth. No ROS message on the wire; no topic in any
  header. Nine malformed shapes tested.
- `coco_web/metrics.py` — measured rates, drops, CPU, mission latency, at
  `/api/metrics` and in telemetry.
- `session.py` — a second axis: `lifecycle` (CREATED…FAILED) beside
  `state` (readiness), so `/healthz` stays 200 during a mission. Plus
  `connection`, and pilot/viewer drive arbitration.
- `web/index.html`, `app.js`, `style.css` — Play and Engineering modes
  rebuilt. The world view draws the real ramp, platform and target lanes
  from `coco_config`. The hard-coded phase list and interpolated
  percentage are **deleted**.
- `gazebo_models/scripts/ros_clean.sh` — gained `platform_serve[r]`.

**Measured (this session, one machine, one sitting):**

- **A complete green fetch driven entirely through the browser
  protocol**: all 16 states in order, `result=fetch`, **170.4 s**.
- Telemetry **1 714 frames, 0 dropped**, peak socket buffer **0 B**.
- Mission-state latency **18.4–82.7 ms** (1 714 samples in that run).
- LiDAR binary frame **668.8 bytes** mean, **10.0 Hz**.
- Camera **3 467 bytes** mean JPEG (q60, 320×240), **6.17 fps** under a
  10 fps cap. Depth **19 frames in 5 s** with `depth_topic` set, **0**
  without it.
- Platform CPU **67–75 % of one core**.
- `/diff_drive_controller/cmd_vel` **publisher count 1** (`cmd_vel_
  arbiter`); the platform's only velocity publisher is `/cmd_vel_teleop`;
  `-p teleop_topic:=/diff_drive_controller/cmd_vel` still refuses to
  start with `UnsafeTopicError`.
- Drive path: browser `drive` moved the wheels (40 commands, max
  0.15 m/s); `stop` zeroed them; a second client's `drive` refused
  `not_in_control` while its **STOP was honoured and reached the
  wheels**; disconnecting the last client ended stopped. Positive control
  honoured — the recorder saw **97** wheel commands.
- Compatibility, both directions: a text-only client received **51 JSON
  scans and 0 binary frames**; a binary client **50 binary frames and 0
  duplicate JSON**.
- Tests **1334 passing, 0 failing, 0 skipped** (was 1139). `coco_web`
  116 → 291, `gazebo_models` 178 → 181. Clean 9/9 build.

**Unverified:**

- **The browser was never driven.** The Chrome extension was not
  connected on this machine. The page is covered by static asset tests
  (73 element ids used, 73 present; every frame type it sends is in the
  server's schema; no ROS topic string in it) and by a WebSocket client
  exercising the same server paths. **Rendering, layout and interaction
  are unverified.**
- **Docker, still.** Not installed. No port and no dependency was added
  by P0.2. `docs/DOCKER.md` carries the exact procedure.
- Camera/depth behaviour with **two simultaneous viewers** — the
  shared-encode path is written and unit-tested but was never exercised
  by two real clients at different settings.

**Found, and fixed, by the live run:**

- **P0.2's own bug.** `wants()` gated binary delivery on
  `BINARY_STREAMS` (camera, depth) while `push_sensors` also framed
  **lidar** as binary — so a client declaring `binary: false` got binary
  lidar frames, which is exactly the compatibility guarantee the design
  claims. Surfaced as a `UnicodeDecodeError` in a probe calling
  `json.loads` on bytes. Split `BINARY_CAPABLE` from `BINARY_STREAMS`;
  six tests pin it.
- **A P0.1 gap.** `ros_clean.sh` had no `platform_server` pattern — the
  node was added to a launch file and not to the sweep, the same rule
  `mission_hud` already broke. An orphan holding :8080 was observed and
  the next launch died `Address already in use`.

**Open:**

- **One of two mission attempts aborted**, reaching `RETURN_HOME` (13 of
  16 states, including a verified grasp) and then failing
  `RETURN_FAILED` with `planner_server: GridBased plugin failed to plan
  from (7.97, 1.15) to (0.00, 0.00): "Start occupied"` — the robot's
  believed pose inside an occupied cell after the descent. A
  localisation outcome upstream of the web layer, which publishes no TF
  and no goals during a mission. **Two runs is not a rate** and this does
  not re-measure M6.
- **`/healthz` 200 does not mean localised.** Two missions started in
  that window aborted instantly with `NAVIGATION_FAILED` and
  `bt_navigator` logging *"Initial robot pose is not available"*. The
  bring-up script now waits for `map → odom`; the platform does not, and
  arguably should expose that wait.
- **AMCL dropped every scan** in one bring-up —
  *"timestamp earlier than all the data in the transform cache"* —
  alongside `robot_state_publisher: Moved backwards in time`. One
  `/clock` publisher, one bridge, sim time advancing, so **not** the
  documented stale-clock failure. Not diagnosed further; out of scope.
- `<ws>/install` still cannot launch gz — the half-installed
  `turtlebot3_teleop` (egg-link, no package marker) makes
  `GazeboRosPaths.get_paths()` throw. P0.2 worked around it with a fully
  isolated overlay at `/home/gautham/coco_p02_overlay`, built with
  `AMENT_PREFIX_PATH` unset first, because a login shell on this machine
  leaks another workspace onto the path and colcon bakes that chain into
  the overlay's own `setup.bash`.

**Next:**

```bash
# One command. It now sanitises AMENT_PREFIX_PATH first (a stray
# half-installed package on it kills every gz launch) and waits for
# map->odom after /healthz, because 200 does not mean localised:
cd <repo> && ./scripts/run_platform.sh --native

# then OPEN http://localhost:8080 IN A BROWSER and verify the UI --
# the one thing P0.2 could not check. Specifically:
#   Play mode draws the ramp, platform and four target lanes
#   the joystick drives and STOP halts
#   "show camera" starts frames; unticking stops them
#   picking a colour and pressing Start advances the step counter
#   switching to Engineering shows in/out rates and drops
```

If the simulator will not start, the cause is almost certainly a
half-installed package on `AMENT_PREFIX_PATH` rather than anything in
this repo — check with `printf '%s\n' "$AMENT_PREFIX_PATH" | tr : '\n'`
and look for a prefix whose `share/ament_index` is missing.

### Addendum, same session — two bring-up bugs found by running the entry point

Both pre-existing in P0.1's `scripts/run_platform.sh` and
`docker/entrypoint.sh`, both found by actually invoking the documented
command rather than reading it.

1. **`AMENT_PREFIX_PATH` was inherited.** ros_gz_sim's
   `GazeboRosPaths.get_paths()` enumerates every package on it, so one
   half-installed entry anywhere — here a stray `turtlebot3_teleop`, an
   egg-link with no package marker — killed every gz launch with
   *"package 'turtlebot3_teleop' not found"*. Two bring-ups were lost to
   it before the error was recognised, because it names a package this
   repo does not use.

2. **`| grep -q` under `set -o pipefail` fails when it MATCHES.**
   `grep -q` exits on the first match, closing the pipe; `ros2 topic
   info` then dies of EPIPE (Python exits **120**) and `pipefail`
   propagates that. **Measured: exit 0 without pipefail, exit 120 with
   it, on the same matching input.** So the readiness wait never broke
   out: `run_platform.sh --native` sat at `[coco] simulator…` for
   **13+ minutes** with a robot that had been publishing odometry the
   whole time. `docker/entrypoint.sh` had the identical line in the
   function that sequences the simulator before the mission stack.

   **After dropping `-q`: 15 seconds** from simulator launch to mission
   stack launch (09:58:59 → 09:59:14), then `/healthz` 200. The fix is
   `| grep PATTERN >/dev/null`, so grep drains the stream and the writer
   never sees EPIPE.

   The localisation wait added earlier in this same session had the bug
   too, copied from the line above it — which is the argument for
   `coco_rl/test/test_platform_scripts.py` asserting no `| grep -q`
   survives in a script that sets pipefail, rather than a comment.

**Verified after the fixes:** `./scripts/run_platform.sh --native`
launches the simulator, waits 15 s, launches the mission stack, reports
`drivable` at `/healthz` 200 and then waits for `map -> odom`.

## 2026-09-22 — Clean COCO runtime: `turtlebot3_teleop` was never a COCO dependency

Branch `coco-clean-runtime`, from `p02-browser-experience` @ `8991249`
(the platform the success condition needs — `mission.launch.py
platform:=` and `:8080` — exists only there; `main` d317d85 has the old
rosbridge panel). No Nav2, PolygonStop, DWB, costmap, AMCL, goal or
depth-fusion change.

**The symptom, reproduced first.** A `bash --noprofile --norc` started
from the developer's terminal, `source /opt/ros/jazzy/setup.bash`, the
main checkout's `setup_env.sh`, then the user's exact command:
`ros2 launch gazebo_models full_world_robo.launch.py traverse:=true
gui:=true` → exit **1**, `package 'turtlebot3_teleop' not found`.

**Root cause — environmental, not in this repo. Measured:**

1. **No COCO → TurtleBot edge exists.** Every `package.xml`, every launch
   file, `setup.py`, `CMakeLists.txt` and YAML value was audited; the
   only mentions are comments (nav2_params.yaml's provenance). Every
   package any COCO launch file looks up is declared.
2. **The trace:** `full_world_robo.launch.py:102` includes ros_gz_sim's
   `gz_sim.launch.py`, whose `launch_gz` (an `OpaqueFunction`, line 180)
   starts with `GazeboRosPaths.get_paths()`. That lists every package on
   `AMENT_PREFIX_PATH` (`ros2pkg.api.get_package_names` →
   `ament_index_python.get_resources`, `os.listdir`) and resolves each
   (`get_package_share_directory` → `get_resource`, `os.path.isfile`). A
   marker that is a **dangling symlink** is listed and not resolvable.
3. **`<ws>/install` put 2 such markers on the path** (colcon's own
   `_local_setup_util_sh.py`, asked directly): `turtlebot3_teleop` and
   `red_ball_nav`, both `--symlink-install` markers pointing into
   `/home/gautham/ros2_ws/build/...` — the workspace's pre-rename path.
   Installed 2026-07-29 / 07-21 and never rebuilt; the COCO packages were
   rebuilt 2026-09-19 and re-pointed. colcon orders `turtlebot3_teleop`
   first, so it is the one named. This matches C2-NAV.49's count of 2.
   (My first replay said 8; it added every install dir with a `share/`,
   which local_setup does not. Retracted.)
4. **Correction to the repo's notes:** "an egg-link with no package
   marker" was wrong. A prefix with NO marker is never listed and is
   harmless — `turtlebot3_node` / `turtlebot3_example` sat in the same
   install with none. Pinned in `test_no_turtlebot_dependency.py`.
5. **Two contamination paths from `$HOME/ros2_ws/install`** (now an
   unrelated e-Yantra workspace: `ur_description`,
   `eyantra_kepler_colony`, `ebot_description`, `algorithms`):
   `<ws>/install/setup.bash:25` froze it into the overlay's underlay
   chain at build time, and `~/.bashrc:149` exports it into every
   terminal — which `bash --noprofile --norc` does NOT clear.

**Built:**

- `setup_env.sh` — (a) removes every entry under an inherited non-ROS
  ament/colcon prefix from nine path-like variables before sourcing ROS
  (`COCO_PRESERVE_PATH=1` opts out, the knob `run_platform.sh` already
  had); (b) sources the overlay's `local_setup.bash`, not `setup.bash`;
  (c) finds `moveit_prefix` in the source workspace when `COCO_WS` points
  at an isolated overlay; (d) runs `scripts/check_ament_path.py`, which
  names every listed-but-unresolvable package. Warns; never edits.
- `scripts/build_overlay.sh [DEST]` — this repo only (`--base-paths`),
  clean package path, `--symlink-install`.
- Tests: `gazebo_models/test/test_no_turtlebot_dependency.py` (25) and
  `coco_rl/test/test_setup_env.py` (18). Swapping the old `setup_env.sh`
  back in fails 3 of the first 8 (underlay leak, no dangling report,
  MoveIt lost); the pre-sanitise version fails 8 of 18.

**A wrong turn, measured and reverted:** `build_overlay.sh` first
defaulted to a COPYING install (so a moved tree could not dangle).
44 `coco_rl` tests then failed (34 failed, 10 errors), all
`FileNotFoundError` on
`<install>/coco_sim/lib/python3.12/site-packages/worlds/yard_params.yaml`
— `coco_sim/yard.py:103` resolves `worlds/` from its source file.
`--symlink-install` is now required and tested.

**Measured:**

- Tests **1607 / 0 / 0** on `~/coco_ws_build`, per package, cwd inside,
  clean graph: coco_config 70, custom_teleop 75, coco_rl 216,
  coco_perception 139, gazebo_models 206, coco_moveit_config 12,
  coco_sim 55, coco_mission 317, coco_web 517. (1564 + 25 + 18.)
- Overlay `~/coco_ws_build`: 9 packages, 16.0 s, underlay chain
  `/opt/ros/jazzy` only, 0 dangling symlinks, 459 packages enumerated,
  0 unresolvable, `GazeboRosPaths.get_paths()` OK.
- Environment after, same inherited terminal (4 e-Yantra entries in):
  `AMENT_PREFIX_PATH` = MoveIt prefix + 9 COCO + `/opt/ros/jazzy`;
  0 entries under `$HOME/ros2_ws/` and 0 turtlebot entries across nine
  variables; `gazebo_models`, `coco_mission`, `coco_web` resolve from
  `~/coco_ws_build`.
- **Live, three fresh simulators, green, browser-driven** (headless
  Firefox, `scripts/browser_check/live.py`); evidence and the full table
  in `docs/data/clean_runtime/`:
  - Runs 1 and 2 — the user's exact commands, `gui:=true`: Gazebo server
    + GUI as one tree, controllers active 7 s / 10 s after launch,
    `/healthz` 200 10 s after the mission launch, Nav2 lifecycles active,
    0 turtlebot mentions and 0 `[ERROR]` in `sim.log`. Both climbed,
    found, approached and grasped (lift **35.8 / 34.8 mm**, ground truth),
    descended — and **both ABORTED `RETURN_FAILED`**: `planner_server`
    `"Start occupied"` ×3 from (8.00, 1.17) and (7.87, 1.25), the foot of
    the ramp, after ~17 s of return driving under PolygonSlow/Limit.
  - Run 3 — `live_run.sh` unmodified, `gui:=false`: **COMPLETE,
    `result=fetch`, `attempts={}`**, all 16 states on the page, lift
    35.2 mm, `place finished: placed`.
  - Safety, all three: STOP with W held → first zero 16.2 / 3.8 / 3.0 ms;
    browser SIGKILLed mid-drive → first zero 75.5 / 89.2 / 92.4 ms; moving
    commands > 600 ms after either: 0. One publisher on
    `/diff_drive_controller/cmd_vel` (`cmd_vel_arbiter`) throughout; the
    platform's only velocity publisher is `/cmd_vel_teleop`. 8/8 hostile
    frames refused. 0 dropped frames. Orphans after teardown, 55
    `ros_clean.sh` patterns: 0.

**Correction to P0.2's addendum** (above, not edited): its tip "look for a
prefix whose `share/ament_index` is missing" finds the harmless case. The
fatal one is a marker that EXISTS as a dangling symlink;
`python3 scripts/check_ament_path.py` finds it.

**NOT established:** why the GUI runs fail the return leg. GUI 0/2 vs
headless 1/1 is three runs, not a rate, and P0.2's first pass saw the
same `Start occupied` headless (1 of 2). It is Nav2 territory; nothing
was investigated or tuned.

**Unverified:** the user's own terminal (this ran from the job's shell,
which carries the same `~/.bashrc` exports); `<ws>/install` itself is
untouched and still cannot launch Gazebo; one completed fetch is not a
rate; the GUI return-leg failure is unexplained.

**Next command** (the configuration that completed; `gui:=true` also
launches cleanly but 0 of 2 fetches got home with it):

```bash
export COCO_WS="$HOME/coco_ws_build"
source <repo on coco-clean-runtime>/setup_env.sh
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=false
ros2 launch coco_mission mission.launch.py platform:=true rviz:=false   # 2nd terminal
# browser: http://localhost:8080 -> pick a colour -> Start
```

## 2026-09-22 — P0.2 release pass: Claude + Codex integrated, release candidate

Branch `p02-release-candidate`, from `coco-clean-runtime` @ `b32539e`.
No robot, Nav2, arbiter, safety-allowlist or perception code changed;
`docs/RSE_ASSIGNMENT_PLAN_V2.md` untouched; protocol stays `coco.v1`.

**Built.**

- Codex: 10 of its 13 listed commits were already on the branch;
  `c0d2f11` cherry-picked (`-x`); `09a77aa` ported selectively (decoder
  strictness + stale-socket guard into `web/frame.js` / `app.js`, not the
  `Transport` class); `fcefc1b` (evidence/replay) and the handoff commit
  left on `codex/p02-hardening`.
- All ten of Codex's caller-side blockers resolved: stored lifecycle with
  explicit `LIFECYCLE_EDGES` (health never moves it; only COCO's simulator
  loss fails it); every browser write bounded (state streams superseded,
  4 MiB abandon, STOP at receipt); per-client `dropped`; close path
  tested; padded rows tested at the ROS boundary; MJPEG at
  `/video/<alias>` with `web_video_server` on loopback and 8080 the only
  published port; `mission.timing` with named clocks, `changed_at` null;
  telemetry kept pinned (explicit decision); keepalive 10/10 with a
  startup check; decoder + stale guard ported to the page.
- Harness: joystick drag, STOP hit-tests, MJPEG check, measured RTF,
  `COCO_LIVE_GUI`, a dedicated ROS domain (61), a session-sweep teardown.

**Measured.**

- Tests, per package, cwd inside, clean ROS graph on a quiet machine:
  coco_config 70, custom_teleop 75, coco_rl 218, coco_perception 139,
  gazebo_models 206, coco_moveit_config 12, coco_sim 55, coco_mission
  317, coco_web 575 = **1667 / 0 / 0**. Clean build 9/9.
- **Under load, one timing test fails**: after a foreign COCO stack
  (`~/c2nav49_overlay`, `gui:=true`, RViz) started at ~21:02, load average
  43 on 12 cores, `gazebo_models/test/test_cmd_vel_wiring.py::TestLiveGraph::
  test_the_relay_output_is_restamped_and_unaltered` failed 8 of 9 runs
  (9 of the 10 messages it needs inside its window; private DDS domain, so
  not the foreign graph). No code it tests changed. Not the documented
  `TestTheOldLoopIsDetected` flake.
- Slow client (tests): peer that stopped reading, 200 ticks, 3 runs —
  its buffer 74–89 kB, healthy neighbour 200/200 frames, longest tick
  40–42 ms, STOP from the stalled client reached the wheels.
- **Live, 5 / 5 browser-driven fetches COMPLETE**, fresh simulator each:
  red, blue, yellow, green headless; green `gui:=true`. Lift 35.6–36.0 mm,
  all `placed`, `attempts={}`; 16/16 states on the page; transitions
  9.6–101.7 ms to the DOM; RTF 0.455–0.506; joystick exercised (first
  wheel motion 72.8–161.2 ms); STOP with W held and browser SIGKILL both
  0 moving commands after; 1 wheel publisher; 8/8 hostile refused; 0
  drops; 0 JS errors. `docs/data/p02_release/`.
- GUI run: no divergence in timing or mission state; an unattributed
  `/mission/mode` + Nav2 goal (2.50, 2.00) on shared domain 0 moved the
  wheels at ≤ 0.012 m/s / 0.5 rad/s for 50 ms; `gz sim server` orphaned by
  the process-group teardown, killed by PID (ours: our session, our
  overlay, our cwd).

**Unverified.** Docker (not installed); touch-screen joystick; any
browser but Firefox; the source of the domain-0 goal; any rate.

**Next command** — the configuration that completed five times:

```bash
export COCO_WS="$HOME/coco_ws_build"
source <repo on p02-release-candidate>/setup_env.sh
scripts/build_overlay.sh "$COCO_WS"
scripts/browser_check/live_run.sh "$PWD" "$COCO_WS" out/live blue   # one fresh run
```

## 2026-09-23 — Larger navigation world, verification ongoing

Starting HEAD d317d85ee6f1575c2620f4e467d7e322d0310bc0.
Current implementation and measured failures are in
docs/NAVIGATION_WORLD.md and docs/NAVIGATION_WORLD_RESULTS.md.

FACT: generated 24 x 18 m arena, matching 500 x 380 map at 0.05 m,
four colour bays, automatic grouped RViz using real /plan and /local_plan,
and disabled dynamic-obstacle example are implemented. Nav2 plugins,
parameters and command routing are unchanged.

FACT: red-v6 completed with physical grasp, home return and release, but
the other colours failed return localization on that older geometry.
Later tests identified a low-ramp planner shortcut, an entrance-turn stall,
and a physical hang-up caused by a shortened/steeper downhill wedge.
Those failures are recorded, not counted as successes.

The current geometry restores both original 18-degree / 2 m slopes and
shortens the platform to 1.2 m, retaining rod X=4.05 and all mission goals.
The mapped-ground predicate now derives the four actual bay centres rather
than wrongly excluding a single Y=0 wedge. Its thresholds/recovery logic
are unchanged. This is a concrete new-geometry consistency correction.

FACT: coco_config, gazebo_models and coco_mission built in the fresh
coco_navigation_overlay; all 565 tests passed. A subsequent explicit
rod support/static-intersection check passed with the seven geometry tests.
GUI/server split startup was verified with sensors and visible rendering.
The active fresh run is /tmp/coco-large/green-v10; red/blue/yellow are queued
by /tmp/coco-large/matrix_v10.sh only if green completes.
The task is NOT complete until every colour has a physical completed fetch
on the final geometry. User-owned local files remain untouched.

## 2026-09-24 — Larger-world implementation verified

FACT: final runtime revision 474601a completed four fresh simulator fetches:
green, red (Gazebo GUI enabled), blue, yellow. Every colour physically lifted
its rod, returned home, detached the magnet, placed the rod standing at
Z=0.0790 m and passed VERIFY_PLACEMENT -> COMPLETE/fetch.
Home errors: red 0.095 m, green 0.060 m, blue 0.085 m, yellow 0.133 m.
Green and blue each needed one successful localization recovery near home;
red and yellow needed none. These runs are not a measured reliability rate.

The final geometry uses stronger asymmetric bay pilasters and offset exit
columns, original 18-degree / 2 m slopes, 1.2 m platforms, and 1.2 m-clear
approach corridors with open turning space and closed low-ramp shortcuts.
Nav2 parameters, command routing, executive transitions, perception, grasp
and depth fusion remain unchanged. The mapped-ground predicate derives the
actual four bay centres; only its geometry was corrected.

A host reboot cleared temporary /tmp captures after the matrix completed.
Persistent executive, grasp, Nav2, RViz and simulator logs survived and are
archived with hashes and colour-specific results in
docs/data/navigation_world_final. Prior development results are retained too.
The report distinguishes archived logs from lost temporary topic captures
and screenshots; no lost files are claimed to remain available.

FACT: post-reboot builds of only coco_config, gazebo_models and coco_mission
passed. The final regression suite passed 730 tests. An earlier 9-versus-10
message-count failure in the unchanged wiring test is retained in the test
record; the isolated 25-test module and subsequent full suite both passed
without changing the test or command path.

See docs/NAVIGATION_WORLD_RESULTS.md for evidence and limitations,
docs/NAVIGATION_WORLD.md for the three-command workflow and overlay setup,
and docs/NAVIGATION_WORLD_FILES.txt for the changed-file manifest.
Next: repeat the fresh-colour regression matrix for reliability before the
first opt-in dynamic obstacle; dynamic behavior remains unimplemented.

## 2026-09-24 — P0.3 stage B: the episode specification; the machine; Isaac Sim on this hardware

Branch `p03-episode-spec` from `p02-release-candidate` @ `c40098f`
(unchanged). Design and assessment: `docs/EPISODE_ARCHITECTURE.md`.

**Built.**

- `coco_sim/coco_sim/episode.py`: `generate_episode(seed, level, backend,
  world_variant, …)` → frozen `EpisodeSpec`; `manifest()` (privileged) vs
  `task_view()` = `{episode_id, requested_colour}` (robot); levels
  `fixed` (default, P0.2 pose for pose) · `colours` · `positions`;
  `validate_episode()` against an envelope DERIVED from `coco_config`;
  `ObstacleSpec` with motion fields, never generated; `EpisodeResult` +
  `check_reproducible()`; timing keys must name their clock. Stdlib +
  `coco_config` only.
- The approach-corridor rule (`16e575b`), after measuring its absence.
- Evidence: `docs/data/p03_episode_spec/`, `docs/data/isaac_foundation/`.

**Measured.**

- Tests, per package, cwd inside: coco_sim **55 → 128**, 0 failed, 0
  skipped; coco_config **70**, coco_rl **218** unchanged. ament_flake8 and
  ament_copyright clean on the new files (pep257 D213 only, the repo's
  existing style).
- Same seed → byte-identical manifest at every level; 10000 seeds × 3
  levels all pass `validate_episode`.
- Approach corridor blocked: `positions` **1012 / 10000** (276 on the
  requested target) before `16e575b`, **0 / 10000** after; `fixed` and
  `colours` 0 / 10000 both times.
- Home cleanup: **1.61 GiB** reclaimed (40384126976 → 42111000576 B
  free): a byte-identical backup of `.codex/worktrees/c2nav0-implementation`
  (`diff -rq` empty; its small unique files kept), `~/ros2_humble` (103
  upstream repos, 0 dirty, 0 unpushed), four `coco_ff_profile*` dirs.
- Isaac Sim: hardware below the 6.x minimum on four counts, 6.1 not
  downloaded. Existing 4.5.0 pip install: default start blocks forever in
  `_wait_for_viewport`; with `create_new_stage=False` it starts in 12.4 s
  and physics runs (60 s, 5114 steps, peak RSS 4.77 GB); rendering ends in
  `LLVM ERROR: out of memory`; Jazzy discovers Isaac's endpoints on domain
  77 but no message was delivered — 2/2 bridge-loaded runs aborted.

**Unverified.** No episode has been spawned in Gazebo or driven. The
`colours`/`positions` levels are geometric only, and the P0.2 mission
cannot complete a `colours` episode (it navigates by `lane_for_colour`).
Isaac ↔ Jazzy message exchange. Why the bridge-loaded runs abort. Docker.

**Needs the owner.** Keep or remove Isaac Sim 4.5 (13.2 G, physics-only
here); old `.claude/jobs/*/tmp` (1.18 G, one holds a rendered
`candidate.mp4`); `~/.local/share/Trash` (327 M); `.cache/codex-runtimes`
(1.8 G, re-downloads).

**Next command** — stage C, spawn from the manifest behind a switch that
defaults to today's layout:

```bash
cd coco_sim && python3 -c "from coco_sim.episode import generate_episode as g; print(g(seed=1827).to_json())"
```

## 2026-09-26 — P0.3 stage C: the episode spawns the Gazebo world; the mission resolves lanes by region

Branch `p03c-episode-gazebo` from `p03-episode-spec` @ `b3c6598` (the
verified episode baseline). Design: `docs/EPISODE_ARCHITECTURE.md` §0.
Evidence: `docs/data/p03c_episode_gazebo/`. `main` (`b15d445`, the
24 × 18 m arena) is a different lineage and was not touched.

**Built.**

- `coco_config`: `TARGET_REGIONS` (`lane_1…lane_4`, derived from
  `TARGETS`), `FIXED_REGION_MAP`, `parse/format_region_map`,
  `resolve_lane(colour, region_map)` (= `lane_for_colour` with no map).
- `coco_sim.episode`: `TargetSpec.region_id` (manifest = source of truth
  for colour → region); `positions` redrawn inside a region-local area
  (±0.030 m across, row outward along); region checks run after p03's;
  `region_map()` + `compat_mission_inputs()` (names only); `resolve_episode()`
  shared by both launches; target z follows the episode's grade;
  `validate_episode(area_slack=)` for read-back only.
- `coco_sim.backends`: `TargetBody`, `GazeboBackend` (SDF + argv,
  byte-identical to the old launch for FIXED), `IsaacBackend` (USD prim
  specs, data only; `missing` names the world pieces Isaac lacks),
  `check_instantiation()`; `coco_episode` CLI.
- `full_world_robo.launch.py`: `episode_level` (default `fixed`),
  `episode_seed`, `episode_colour`, `episode_manifest`, `episode_record`.
- `mission.launch.py` + `mission_executive` + `ramp_driver`: the
  `region_map` parameter (empty by default).
- Harness `docs/data/p03c_episode_run.sh` / `_matrix.sh` / report.

**Measured.**

- Tests, per package, cwd inside, private domain, MoveIt on the path:
  **1877 / 0 / 0** on this branch against **1740 / 0 / 0** measured on
  `b3c6598` in this session (coco_config 70 → 92, coco_rl 218 → 229,
  gazebo_models 206 → 219, coco_sim 128 → 199, coco_mission 317 → 337;
  the other four unchanged). One pre-existing assertion extended
  (`region_id` in the manifest), none deleted.
- Generator: same seed → identical manifest at every level; 10000/10000
  valid and in-region per level; all 24 assignments reached; POSITION dx
  [0, +0.3739] m, dy [−0.0300, +0.0300] m.
- Gazebo, 10 fresh runs (`docs/data/p03c_episode_gazebo/`): gz spawned
  every manifest within 10 µm; region map on executive + ramp_driver as
  expected 10/10; Nav2 arrival 0.005–0.080 m from the episode lane
  (1.013–1.513 m from the frozen lane when moved); **8/10 COMPLETE —
  FIXED 4/4, COLOUR 2/3, POSITION 2/3**; approach stop 0.1539–0.1545; one
  wheel publisher, bypass 0, stop-breach 0 in all ten.
- The two failures: lane_4, thinner target (green 24 mm, red 20 mm), lost
  at SEARCH_TARGET after climbs 0.233 / 0.206 m off-lane (one then
  `DESCENT_TIMEOUT` at x 4.50). Repeated once each with perception
  recorded: found both (climbs 0.152 / 0.101 m); one COMPLETE, one void
  (return leg outlasted the 900 s wall budget after a Nav2 abort). First
  detections 3 × 4 and 4 × 4 px at ~1.40 m. Not attributed.
- A read-back checker defect (no slack on the region's near edge; gz
  settled FIXED targets 10 µm toward the crest) failed one runner check;
  fixed in `df796dd`, all recorded poses pass re-judged.
- A repeat refused to start because `ros_clean.sh --list` matched this
  session's own waiter shell (its text contained a process pattern) — the
  pre-flight working; relaunched.

**Unverified.** Any rate. Why thin targets were lost after ~0.2 m climbs
(not attributed). Isaac instantiating any of this (the adapter is data
only; the Isaac world geometry does not exist). The browser's drawing in
COLOUR/POSITION (it draws the frozen layout). Docker with episodes.

**Next command** — reproduce one episode end to end:

```bash
export COCO_WS=$HOME/coco_p03c_ws
bash scripts/build_overlay.sh "$COCO_WS"
ln -s "<ws>/moveit_prefix" "$COCO_WS/moveit_prefix"   # once; the runner refuses without MoveIt
bash docs/data/p03c_episode_run.sh ~/coco_nav_runs/p03c_next positions 4 green
```

---

## Milestone 0A — Phase 0 repository + system cleanup (2026-09-29)

**Status:** COMPLETE (all 0A acceptance criteria met; the push, the tags and the public actions await approval, as the milestone requires)

**Repository**
- main SHA: the commit that carries this entry, a child of the merge commit `232454d`. Local only.
- merge SHA: `232454d` — parents `b15d445` (main) and `917bc59` (p03c-consolidation)
- `jazzy2/main` (GauthamCodes/coco-robot-jazzy-2.0): `ea66155`. Local main is ahead of it and 0 behind, so a push would be a fast-forward. **Not pushed.**
- `origin/main` (GauthamCodes/coco-robot-ros2, the old repo): `34f151c`. No shared history with main.
- p03c branch: `p03c-consolidation` `917bc59` (local only, worktree `~/coco-p03c-consolidation`); now contained in main.
- working tree: the user's checkout keeps its own uncommitted `CLAUDE.md` edit (14 lines, "Multi-agent protocol"), preserved byte-for-byte across the fast-forward. Its untracked `ROADMAP.md`, `AGENTS.md`, `.codex/`, `docs/agents/{DECISIONS,HANDOFF,RESULTS,TASK}.md`, `docs/RSE_ASSIGNMENT_PLAN_V2.md`, `P02_NOTE_FOR_CODEX.md` and `tatus --short` are untouched.

**P03C**
- **Verified:** main and p03c had diverged from `d317d85`: 22 commits on main (the 24×18 arena), 63 on p03c. `917bc59` re-typed main's arena work as content and dropped part of it. So there was no fast-forward: this is a real merge.
- **Conflicts, resolved by hand:**
  - `setup_env.sh`: p03c's MoveIt fallback.
  - `full_world_robo.launch.py`: p03c's episode spawning, plus main's separate Gazebo GUI process (61ff385), which p03c had dropped.
  - `coco_config/robot.py`: p03c's constants, main's comments.
  - `docs/SESSION_LOG.md`: both sides, in date order.
  - Auto-merged and checked: `README.md` (main's text), `localization_health.py` (comments only), `coco_web/CMakeLists.txt` (deleted, as on p03c).
- **Tests (measured):** **1966 passed / 0 failed / 0 skipped**, on the staged tree and again on the committed `232454d`.
  - Per package, run from inside each package, `ROS_DOMAIN_ID=77`, overlay `~/coco_p0merge_ws` (MoveIt linked).
  - coco_config 93, coco_mission 338, custom_teleop 75, coco_rl 229, coco_perception 139, coco_moveit_config 12, coco_sim 280, coco_web 575, gazebo_models 225.
  - p03c *alone* on `~/coco_consolidation_ws` reproduces only 1959 + 7 skipped, because that overlay has no MoveIt.
- **Present in the merged tree:** 24×18 arena (`coco_navigation.world`, `navigation_world.json`), `EpisodeSpec` (`coco_sim/episode.py`), `TargetRegion` (`coco_config/robot.py`), `platform_server` (`coco_web/`), and the `/cmd_vel_gated` wiring (6503cd5, integrated by c8a8206).
- **Unresolved issues:**
  - The P03C 13/13 matrix (`~/coco_runs_p03c`) recorded head `dfcbc4b`, not `917bc59`: it ran on an uncommitted tree.
  - Its report claims "exactly 35.8 mm lift on all 13" and "targets at X ∈ [6.3, 7.3]". The spawned targets are at x = 4.05 (measured, this session), so the INV-3 wording is wrong. The lift figure is not verified.
  - The launch-file comment "Each bay ends at x=6.5" is stale; `robot.py` gives 6.2.

**Collision monitor**
- **Commit inspected:** the wiring change is `6503cd5` (C2-NAV.42). `c8a8206` is the C2-NAV.43 results commit that integrated it. Both are in main; nothing was re-applied, and `cmd_vel_arbiter.py` is unchanged.
- **Topology (live, every run):**
  - `/cmd_vel_nav`: pub `controller_server`, `behavior_server`; sub `velocity_smoother` only.
  - `/cmd_vel_smoothed` → `collision_monitor` → `/cmd_vel` (+ inert `docking_server`) → `cmd_vel_relay`.
  - `/cmd_vel_gated`: **1 pub (`cmd_vel_relay`), 1 sub (`cmd_vel_arbiter`)**.
  - Wheel topic: **1 pub (`cmd_vel_arbiter`)**.
  - The relay no longer feeds the smoother, so the loop is gone.
- **Slowdown result:**
  - Setup: injected SLOWDOWN (side wall at 0.32 m, raw 0.30 m/s held, frozen `coco_world.world`). Three valid fresh-sim runs; r03 is VOID (killed by a stale teardown of mine).
  - Rates: monitor 19.98–20.02 Hz, relay 19.98–20.01 Hz, wheel 19.70–25.97 Hz. Wheel > relay is the arbiter's 20 Hz gap-fill re-emitting the latest command: 695 of 695 wheel messages equal the latest gated command.
- **Wheel speed distribution:** 300 SLOWDOWN rows pooled; p50 / p90 / p99 / max = **0.090 / 0.090 / 0.090 / 0.090 m/s**. **0 of 300 rows over the cap (0.0 %).**
- **Cap:** `slowdown_ratio` 0.3 (read back live) × 0.30 = **0.090 m/s**.
  - Control (no wall): 0 SLOWDOWN rows; the wheel follows the raw 0.300.
  - STOP probe: stopped by APPROACH at 0.264 m, wheels 0.0000 for the last 6 s while raw held 0.30. STOP itself never fired (`stop_held: false`), unlike C2-NAV.47.
- **Four-run result:** **4 / 4 COMPLETE/fetch** (red, green, blue, yellow; commit `232454d`; fresh sim each; 17/17 runner checks each). Home error 0.103 / 0.075 / 0.108 / 0.129 m. Every target physically ended at home. Nav-owned rows over the monitor: **0 of 2,724**. `gated_zero_moving` 38 rows (1.39 %), inside the documented 0.088–2.92 % residual. Bypass rows matching the raw controller: 0. STOP rows: 0. The missions hit LIMIT only (plus 1 APPROACH row) and **no SLOWDOWN**. Historical P03C FIXED (`dfcbc4b`): 4/4 COMPLETE/fetch, home error 0.087 / 0.124 / 0.013 / 0.176 m. A separate series.
- **Comparability:** a new series.
  - v1 19/20 and C2-M5.0's 84.2 % were measured WITH the loop.
  - The P03C 13/13 was measured WITHOUT it (6503cd5 predates `dfcbc4b`), on a different harness version.
  - Details: `docs/data/m0a_cmdpath/README.md`.

**Master context**
- path: **MASTER CONTEXT PATH UNRESOLVED**
- status: not found in the repo, any worktree, `~/Downloads`, `~/.claude/plans`, the Claude paste cache, or the Antigravity transcripts. The nearest candidate (paste-cache `260a52b0…`, "COCO 2.0 — POST-P0.2 PRODUCT + RESEARCH ROADMAP") has no §45 and no P0.4, so it is not treated as the master context. B2 was left untouched.

**Cleanup**
- **Protected locations:**
  - **e-Yantra = `~/ros2_ws`** (origin eYantra-Robotics-Competition/eYRC_26-27_Strata-Cobot; `.bashrc` sources its install).
  - `~/isaac-sim` and `~/.local/share/ov` (Isaac runtime data), `~/coco-isaac-backend`, `~/coco-infra-worktree`, `~/forge`, `~/forge-lab`, `~/dev/amr-fleet-nav`, `~/amr-fleet-nav-backup`, `~/ros2_ws(personal)/src/red_ball_nav`, `~/simple_bot_tutorial`, `~/robotic_arm_ws`.
  - `~/assignment` and `~/assignment_ws` (ERICR assignment).
  - All COCO worktrees; the evidence in `~/coco_nav_runs`, `~/coco_runs_p03c`, `~/coco_p03d_runs`, `~/coco_container_evidence`, `~/coco_runtime_runs` and `~/ros2_ws(personal)/rl_runs`.
  - `~/ros2_ws(personal)/moveit_prefix`; Docker images; Downloads, Documents, Videos and Pictures; the Firefox and Brave profiles; the `~/.claude` and `~/.gemini` transcripts.
- **Disposable candidates found:** caches, stale overlays, the npm cache and more; see the retained list.
- **Deleted:**
  - 420 `__pycache__`/`.pytest_cache` dirs outside protected trees (30.5 MB). The p03d worktree's were left while its batch was live.
  - Overlays `~/p01_wt_overlay`, `~/coco_p02b_overlay`, `~/coco_p02c_overlay` (unreferenced, regenerable symlink installs) and `~/ros2_ws(personal)/c2m31_overlay` (131 dangling links): 7.5 MB.
  - The npm cache (`npm cache clean --force`): 166.3 MB.
- **Retained as unknown / awaiting approval:**
  - `~/Downloads/Antigravity.tar.gz` (165 MB installer; `agy` is installed)
  - `~/ros2_ws(personal)/src/coco-robot-ros2/.codex/worktrees/c2nav0-implementation` (219 MB, orphaned Codex worktree, UNKNOWN)
  - the stray `tatus --short` (saved `git diff` output, Sep 19)
  - `~/coco_consolidation_ws`, `~/coco_p03c_ws`, `~/coco_p02_overlay`, `~/c2nav48_overlay`, `~/coco_navigation_overlay` (referenced by docs or memory)
  - `~/simple_gz_ws` (small personal project)
  - `/var/crash` (117 MB, needs sudo)
  - the Brave cache (1.7 GB, Brave running)
  - Docker `coco-platform` images (8.4 GB shared, 91 MB reclaimable)
  - `~/.local/share/claude` versions (tool-managed)
  - registered worktrees whose branches are now in main
- **Disk before:** used 62.93 GiB, free 33.77 GiB; home 27.48 GiB.
- **Disk after:** used 62.70 GiB, free 34.00 GiB; home 27.26 GiB. This includes about 13 MB of new evidence and the new `~/coco_p0merge_ws`.
- **Space recovered:** 204.4 MB deleted (apparent size, measured per item before deletion). `df` rose about 0.2 GiB net of the new run evidence.

**Public/repository actions awaiting approval**
- `git push jazzy2 main` (fast-forward from `ea66155`).
- `archive/<branch>` tags for every remote branch (see the table in the final report), then any remote-branch deletions.
- The fetch-video release asset; the coco-robot-ros2 pointer README and archival.
- A name choice among the five free candidates, and the rename.

**Unverified**
- Why the STOP probe now ends under APPROACH rather than STOP. Suspected cause, not measured: C2-NAV.48's `robot_radius` 0.25.
- The P03C report's 35.8 mm lift figure.
- What `.codex/worktrees/c2nav0-implementation` contains.

**Decisions required from human**
- Approve `git push jazzy2 main`.
- Give the master context's path, or confirm that B2 is dropped.
- Approve the archive tags, then any branch deletions.
- Choose a name.
- Approve or deny each retained cleanup item above.
- Whether PROJECT_STATE KL0 should be rewritten now (Phase 0 D1/C4) using `docs/data/m0a_cmdpath/README.md`.

**Next milestone:** Phase 0 continuation (0B: B1–B3 roadmap install and CLAUDE.md addendum; C4/D1–D2 honest PROJECT_STATE and README; D3–D5 after approvals). Phase 1A only after Phase 0 closes.

**EXACT NEXT ACTION:** after the owner approves: `cd "~/ros2_ws(personal)/src/coco-robot-ros2" && git push jazzy2 main`. Then start 0B with "Resume from the latest milestone checkpoint."

---

## Milestone 0B-H — Canonical home/workspace cleanup

Status:
    COMPLETE

Disk:
    before:
        root used: 67,314,102,272 bytes (62.69 GiB / 67.31 GB)
        root free: 36,515,110,912 bytes (34.01 GiB / 36.52 GB)
        home: ~29 GiB
    after:
        root used: 67,155,456,000 bytes (62.54 GiB / 67.16 GB)
        root free: 36,673,757,184 bytes (34.16 GiB / 36.67 GB)
        home: ~29 GiB
    recovered:
        158,646,272 bytes (151.29 MiB / 158.65 MB) reclaimed on root filesystem
        141,881,994 bytes (135.31 MB) apparent file data deleted across 2,088 directories and 4,623 files

Deleted:
    Stale ROS Overlays & Test Workspaces (8 directories):
      - ~/c2nav48_overlay (1.42 MB, 177 symlinks, stale C2-NAV.48 branch overlay)
      - ~/c2nav49_overlay (2.67 MB, 179 symlinks, stale C2-NAV.49 branch overlay)
      - ~/coco_navigation_overlay (0.72 MB, 98 symlinks, incomplete 3-package nav test overlay)
      - ~/coco_p02_overlay (1.15 MB, 183 symlinks, stale P0.2 overlay)
      - ~/coco_p03c_ws (4.09 MB, 187 symlinks, stale episode-gazebo overlay superseded by main)
      - ~/coco_infra_host_ws (1.71 MB, 187 symlinks, reproducible host overlay for infra worktree)
      - ~/coco_isaac_ws (3.26 MB, 188 symlinks, reproducible overlay for isaac backend)
      - ~/coco_navigation_validation (0.23 MB, 100% duplicate of checked-in docs/data/navigation_world_final/)
    Accidental colcon directories in ~ (4 directories):
      - ~/build (16 KB, accidental colcon build from April 2025)
      - ~/install (56 KB, accidental colcon install from April 2025)
      - ~/log (4.75 MB, accidental colcon log trees from April 2025 - March 2026)
      - ~/workspace (0 KB, empty directory)
    Loose diagnostic & temporary files in ~ (6 files):
      - ~/frames_2026-04-25_19.46.32.gv (1.8 KB, one-off tf2_tools visualizer dump)
      - ~/frames_2026-04-25_19.46.32.pdf (16.4 KB, one-off tf2_tools visualizer dump)
      - ~/gz_sysinfo.sh (2.7 KB, one-off system capture script from June 2026)
      - ~/gz_sysinfo.txt (17.0 KB, one-off system capture output from June 2026)
      - ~/camera_check.py (2.1 KB, one-off camera topic probe from Sep 12)
      - ~/depth_qos_check.py (0.8 KB, one-off depth topic probe from Sep 12)
    Duplicate downloads (2 files):
      - ~/Downloads/ROADMAP.md (22.3 KB, byte-for-byte duplicate of repo ROADMAP.md)
      - ~/Downloads/LAB_PHASES (1).md (23.8 KB, byte-for-byte duplicate of repo LAB_PHASES.md)
    System crash dumps in /var/crash (6 files, 115.15 MB):
      - /var/crash/_usr_bin_ruby3.2.1000.crash (93.78 MB)
      - /var/crash/_opt_ros_jazzy_lib_rclcpp_components_component_container_isolated.1000.crash (11.77 MB)
      - /var/crash/_usr_bin_eog.1000.crash (4.74 MB)
      - /var/crash/_opt_ros_jazzy_lib_ros_gz_bridge_parameter_bridge.1000.crash (4.07 MB)
      - /var/crash/_usr_bin_node.1000.crash (0.62 MB)
      - /var/crash/_opt_ros_jazzy_lib_rviz2_rviz2.1000.crash (0.19 MB)

Preserved:
    Active Workspaces & Overlays:
      - ~/coco_ws_build (canonical clean workspace documented in HOW_TO_RUN.md & CLAUDE.md)
      - ~/coco_p0merge_ws (active build overlay for main, MoveIt linked)
      - ~/coco_consolidation_ws (active build overlay for p03c-consolidation worktree)
      - ~/coco_p03d_ws (active build overlay for coco-p03d-target-search worktree)
    Active Repositories & Worktrees:
      - ~/ros2_ws(personal)/src/coco-robot-ros2 (canonical COCO repo, branch main @ 442bca0)
      - ~/coco-p03c-consolidation (worktree p03c-consolidation @ 917bc59)
      - ~/coco-p03d-target-search (worktree p03d-autonomous-target-search @ d220ab8)
      - ~/coco-infra-worktree (worktree claude/docker-reproducibility @ 23f372c)
      - ~/coco-isaac-backend (worktree p03-isaac-backend @ ffb3fc6)
      - All 7 .claude worktrees (.claude/worktrees/* all dirty, preserved intact)
    COCO Experimental Evidence:
      - ~/coco_container_evidence (70.2 MB container reproducibility benchmarks)
      - ~/coco_nav_runs (268.3 MB navigation test & live run logs)
      - ~/coco_p03d_runs (38.2 MB autonomous target search runs)
      - ~/coco_rl_runs (4.8 MB PPO curriculum training logs & benchmarks)
      - ~/coco_runs_p03c (4.9 MB 13/13 multi-bay simulation matrix logs & report)
      - ~/coco_runtime_runs (10.4 MB live GUI/headless validation logs)
      - ~/ros2_ws(personal)/rl_runs (historical RL runs)
    Required Backups:
      - ~/coco-backup-20260807-0543.bundle (4.7 MB canonical COCO git bundle)
      - ~/coco-backup-20260807-0543.refs.txt (references manifest)
      - ~/coco_premerge_backup (152 KB pre-merge stash & untracked backup)
      - ~/amr-fleet-nav-backup (14.2 MB fleet nav backup)
      - ~/.bashrc.bak-2026-06-12 (4.5 KB bashrc backup)
    RL Policy Artifacts:
      - ~/ppo_coco_ramp.zip (144.7 KB ramp climb PPO policy)
      - ~/ppo_coco_ramp.monitor.csv (105 B monitor log)
    System Services & Tools:
      - ~/lo-multicast.service (218 B loopback multicast systemd service definition)
      - ~/bin (gh GitHub CLI, forge launcher)
      - ~/isaac-sim (6.7 GB Isaac Sim installation)
      - ~/.local/share/ov (7.3 GB Omniverse cache)
      - Docker images coco-platform:61bef2ab3bdf and coco-platform:main-b15d445

Protected:
    - e-Yantra / eYRC material: ~/ros2_ws (eYRC_26-27_Strata-Cobot), ~/task1a_scratch, ~/SC#2200_task1A_detection.png, ~/Downloads/KD_2200*, ~/Downloads/result-*, ~/Downloads/Task 1*, ~/Downloads/you-are-helping-me-greedy-puppy.md, ~/.local/share/Trash/files/SC#2200_task1A.zip
    - Active academic / other projects: ~/assignment, ~/assignment_ws, ~/dev/amr-fleet-nav, ~/forge, ~/forge-lab, ~/robotic_arm_ws, ~/simple_bot_tutorial, ~/ros2_ws(personal)/src/red_ball_nav
    - User data: ~/Desktop, ~/Documents, ~/Downloads (personal documents & offer letters), ~/Music, ~/Pictures (screenshots), ~/Public, ~/Templates, ~/Videos (screencasts)

E-Yantra:
    confirmed untouched (E-YANTRA PROTECTED — NO FILES MODIFIED)

COCO canonical:
    Repo: ~/ros2_ws(personal)/src/coco-robot-ros2 (branch main, HEAD 442bca0)
    Clean build overlay: ~/coco_ws_build
    Active test overlay: ~/coco_p0merge_ws

COCO evidence:
    ~/coco_container_evidence, ~/coco_nav_runs, ~/coco_p03d_runs, ~/coco_rl_runs, ~/coco_runs_p03c, ~/coco_runtime_runs, ~/ros2_ws(personal)/rl_runs (all verified intact)

Active projects:
    COCO 2.0 (main + worktrees), eYRC_26-27_Strata-Cobot, amr-fleet-nav, forge, forge-lab, assignment_ws, robotic_arm_ws, simple_bot_tutorial, red_ball_nav

Unknown items:
    - ~/Downloads/Antigravity.tar.gz (172 MB): installer archive; agy is installed in ~/.local/bin/agy, retained awaiting user decision per Part H.
    - ~/ros2_ws(personal)/src/coco-robot-ros2/.codex/worktrees/c2nav0-implementation (219 MB): orphaned Codex worktree with missing gitdir reference; retained awaiting user decision.
    - ~/ros2_ws(personal)/src/coco-robot-ros2/tatus --short (19 KB): stray git diff output from Sep 19 in repo root; retained awaiting user decision.
    - ~/simple_gz_ws (1.3 MB): personal empty world simulation workspace from April 2025; retained awaiting user decision.

Git/worktrees:
    All 11 registered worktrees verified via git worktree list; no worktree removed; git status on main clean except user-owned / untracked files.

Risks or unresolved items:
    - Decisions required on the 4 retained unknown items above.
    - Pending approval from human for git push jazzy2 main and remote branch archive tags.

NEXT MILESTONE:
    Phase 0B repository/public-state work

EXACT NEXT ACTION:
    Resume from the Phase 0B checkpoint after human decisions on unknown items and push approval.

---

## Milestone 0B — Phase 0 closure preparation (2026-09-29)

**Status:** PARTIAL. Every 0B deliverable is committed on the working branch
`p0-consolidation-merge`. Two things are not done:
- **Not landed on local `main`.** Your main checkout carries another agent
  session's uncommitted `docs/SESSION_LOG.md` edit (see *Concurrent
  activity*). A fast-forward would touch that file, so it is left to the
  owner.
- **One disposable item is not cleaned.** The permission classifier denied
  the `/tmp/launch_params_*` sweep.

Nothing public was changed.

**Repository**
- local main: `442bca0`
- remote main: `jazzy2/main` `442bca0`. Pushed from this machine
  2026-09-29 01:54:44 +0530, after 0A closed and not by this session
  (remote-tracking reflog). 0 ahead / 0 behind.
- P03C: in `main` through merge `232454d` (parents `b15d445`, `917bc59`).
  `p03c-consolidation` `917bc59` is an ancestor of `main`.
- `p0-consolidation-merge`: this commit, a child of `442bca0`, so
  `main` → this commit is a fast-forward.
- working tree (main checkout):
  - `M CLAUDE.md`: the owner's 14-line "Multi-agent protocol" edit.
  - `M docs/SESSION_LOG.md`: another session's +129-line "Milestone 0B-H" entry.
  - Untracked: `ROADMAP.md`, `AGENTS.md`, `.codex/`,
    `docs/agents/{DECISIONS,HANDOFF,RESULTS,TASK}.md`,
    `docs/RSE_ASSIGNMENT_PLAN_V2.md`, `P02_NOTE_FOR_CODEX.md` and
    `tatus --short`.
  - This session changed none of them.

**Documentation**
- ROADMAP: `docs/ROADMAP.md` is the new COCO Lab roadmap, byte-identical to
  the owner's file (sha256 `09c65bed…c19e`).
- Old roadmap: kept byte-for-byte as `docs/history/ROADMAP_COCO2.md`
  (`git mv`; identical to `442bca0:docs/ROADMAP.md`).
- `docs/history/README.md` records the planner-framing correction and which
  references still point at old-roadmap sections.
- LAB_PHASES: `docs/LAB_PHASES.md`, byte-identical to
  `~/ros2_ws(personal)/src/LAB_PHASES.md` (sha256 `622c9db3…2d735`).
- Links: every rendered link in the changed docs resolves (54 checked).
  The one unresolved path, at LAB_PHASES:162, is inside a fenced prompt:
  it is the README banner's own root-relative text.
- PROJECT_STATE:
  - Header is now "ACTIVE — building COCO Lab", with the old header quoted.
  - New section: CURRENT STATE (2026-09-29), covering direction, canonical
    branch, P03C, tests, command-path topology, SLOWDOWN verified, STOP not
    re-verified, fetch 4/4, P03C matrix, and the master context.
  - Corrections to the P03C report.
  - Known-limitations summary and the unresolved list.
  - KL0 gets a new, current "Milestone 0A update" at its head. The C2-NAV.43
    text and the original C2-M5.0 text stay below it as history.
  - The milestone-status sections are marked superseded, not deleted.
- README:
  - The status banner from LAB_PHASES is at the very top.
  - Planner claim corrected in the results table and in "A note on the
    planner name". The 6.2 % is SmacPlanner2D vs NavFn (`use_astar: false`),
    an implementation difference, not A\* beating Dijkstra. The numbers are
    unchanged, the old wording is quoted as corrected, and Lab 1 is named
    as where it will be shown.
  - Tests row: 1,966 (0A), with 829 kept as the freeze figure.
  - Collision-monitor bullet: SLOWDOWN verified, STOP not re-verified.
  - Development-history table: a COCO Lab row.
  - `docs/RESULTS.md`: same planner correction, plus a dated correction
    note; the measured table is unchanged.
- CLAUDE: the LAB_PHASES B3 addendum is appended verbatim (+27 / −0). Its
  9 rules cover all 12 standing rules in the 0B prompt. The owner's
  uncommitted edit is not in this commit; it survives a fast-forward
  (3-way apply, disjoint hunks). The file's older "COCO 2.0 is frozen"
  lines are unchanged, because edits are additive only.
- AGENTS: not a mirror of CLAUDE.md (it is a 248-line multi-agent
  protocol), so it gets no addendum. Untracked and untouched.
- Master context: **MASTER CONTEXT PATH UNRESOLVED.** Re-searched for §45 /
  "master context" in the repo, worktrees, `~/Downloads`, `~/Documents`,
  `~/Desktop`, `~/.claude/plans`, the Claude paste cache, the Antigravity
  and Antigravity-CLI brains, and `~/.codex`. Every hit is a reference to
  the 0A search. No replacement was created.
- Also repointed: `docs/PRODUCT_ARCHITECTURE.md`'s four citations of
  old-roadmap sections now name `docs/history/ROADMAP_COCO2.md`.

**Collision monitor**
- current topology (measured, 0A):
  - `/cmd_vel_gated`: 1 publisher (`cmd_vel_relay`), 1 subscriber
    (`cmd_vel_arbiter`).
  - Wheel topic: 1 publisher (`cmd_vel_arbiter`).
- slowdown evidence (measured, 0A): 300 SLOWDOWN samples, wheel p50 / p90 /
  p99 / max = 0.090 / 0.090 / 0.090 / 0.090 m/s. 0 over the 0.090 cap.
- STOP behaviour: **not re-verified.** The probe stopped 0.264 m from the
  wall under FootprintApproach, and STOP never fired. Historical: STOP at
  0.249 m.
- unresolved: why the probe now ends under APPROACH (the `robot_radius`
  0.25 hypothesis is unverified), and the unattributed short-streak
  residual. `cmd_vel_arbiter.py` untouched.

**Corrections recorded (derived, from recorded evidence, no new run)**
- P03C lift: the report's `lift` field is the constant "35.8 mm" on all 13
  rows. The runs' own `mission.log` files record 34.3–35.8 mm, median 35.3,
  with 35.8 in only 2 of 13.
- P03C target location: the report says "X ∈ [6.3, 7.3]", but the targets
  spawn at x = 4.05 (0A, and `TARGET_ROW_X`).
- P03C comparability: the 13/13 was measured after the `/cmd_vel_nav` fix,
  not with the loop. This contradicts LAB_PHASES C3's premise.
- 0A's cleanup note: `/var/crash` does not need sudo. It is sticky and
  world-writable, and the dumps were owned by `gautham`.

**Cleanup** (`docs/data/m0b_phase0/README.md` §5 has the full table)
- deleted by this session: `~/coco_consolidation_ws`, **5,127,285 B**. It
  was a symlink overlay of the clean `917bc59` (ancestor of `main`), with 0
  dangling links, no process using it, and it can be rebuilt with
  `scripts/build_overlay.sh`.
- removed by another session, not this one:
  - `~/coco_p03c_ws`: 4,292,602 B when this session measured it. It was
    already classified DELETE: symlinks of the clean `dfcbc4b`.
  - all six `/var/crash` dumps, 120,765,102 B. Three were COCO-stack
    crashes that this session would have kept.
- retained:
  - UNKNOWN: `~/Downloads/Antigravity.tar.gz` (172,322,487 B). It is the
    Antigravity IDE, which is installed nowhere. `agy` 1.2.12 works but is
    the separate CLI.
  - UNKNOWN: `tatus --short` (19,011 B). An accidental `less` save, but the
    only durable record of an abandoned CLAUDE.md stub; its blob
    `7f93a36` is dangling.
  - ARCHIVE: `.codex/worktrees/c2nav0-implementation` (219,462,730 B).
    - It is orphaned: its gitdir was pruned.
    - 64 of 65 post-checkout files are already in git history.
    - `.navbench/c2nav35` (the patched `nav2_amcl` overlay and its logs)
      is not in git.
    - `.codex/` is user-owned.
  - KEEP for now: the Brave cache (1,696,777,591 B), because Brave is
    running (PID 3747).
  - Not cleaned: `/tmp/launch_params_*` (837 files, 4,109,543 B from the 0A
    runs; the classifier denied the sweep). `~/.local/bin/agy.*.old`
    (218,132,688 B) is tool-managed.
- protected: e-Yantra `~/ros2_ws` (eYRC_26-27_Strata-Cobot). This session
  modified nothing under it; only read-only, home-wide `find` scans
  traversed it. No new e-Yantra location
  was found by this session. The other session's entry lists further eYRC
  files in `~` and `~/Downloads`; this session did not verify them.
- disk before: 36,522,295,296 B free (df, session start)
- disk after: 36,751,978,496 B free (df, 02:12 IST). **+229,683,200 B, of
  which 5,127,285 B is this session's deletion.** The rest is the
  concurrent session's cleanup and other machine activity, so no
  "recovered by 0B" figure beyond 5,127,285 B is claimed.

**Concurrent activity**
- Codex (`codex resume`, PID 9146) and `agy` (PID 9641) ran throughout.
- An uncommitted "Milestone 0B-H — Canonical home/workspace cleanup" entry
  (+129 lines) appeared in the main checkout's `docs/SESSION_LOG.md` at
  02:06:43. The Antigravity-CLI brain `314eefc7…` read the 0A log at 01:58,
  which suggests `agy` wrote it (inference, not verified).
- That entry lists `~/coco_consolidation_ws` as "Preserved", and this
  session had already deleted it. The two entries must be merged when this
  branch lands.

**Remote actions awaiting approval** (exact commands in
`docs/data/m0b_phase0/README.md`)
- `git push jazzy2 main`, once `main` has fast-forwarded to this commit.
- 12 annotated `archive/<branch>` tags (commands prepared, not created),
  then `git push jazzy2 'refs/tags/archive/*'`.
- Delete 11 remote branches after the tags. `claude/docker-reproducibility`
  and `main` are kept.
- The `m6-fetch-demo` release on this repo at `9b1ed7f`, with
  `coco_fetch_demo.mp4` (8,805,381 B, sha256 `7a2f761e…5674`), then the
  one-line README pointer change.
- The coco-robot-ros2 pointer banner, added not replaced (the repo cites an
  IEEE ICRM 2025 paper), then its archival.

**Name decision:** waiting on the owner. All eight candidates are free under
GauthamCodes. Repositories with the name in their name: cutaway-robotics 0,
coco-robot-lab 0, robotlab-live 0, botbench-lab 0, open-robotics-lab 4,
coco-lab 271, ros-lab 1,660, nav-lab 1,933. The factual comparison is in the
evidence file.

**Video migration:** prepared, not run.
- The current asset is the only copy anywhere under `~`.
- Proposed: release `m6-fetch-demo` on coco-robot-jazzy-2.0 at `9b1ed7f`.
- README line 59 is the only pointer.

**Tests:** not re-run. This commit changes only `.md` files, and no test
reads any of them (checked by grep over every package's `test/`). The count
therefore stands at 0A's measured 1,966 / 0 / 0.

**Unverified**
- The STOP-probe change of mechanism.
- The short-streak residual's cause.
- Which process wrote the 0B-H entry and removed `/var/crash` and
  `~/coco_p03c_ws`.
- Whether the Docker image works on `main`.

**Decisions waiting on the owner**
1. Land this branch: merge the two SESSION_LOG entries, then fast-forward
   `main`.
2. Approve `git push jazzy2 main`.
3. Approve the archive tags, then the 11 remote deletions.
4. Choose a name.
5. Approve the video migration, then the coco-robot-ros2 banner and
   archival.
6. Decide the retained items: the Antigravity IDE tarball, `tatus --short`,
   the Codex worktree's `.navbench`, the Brave cache and
   `/tmp/launch_params_*`.
7. Give the master context's path, or drop B2.

**NEXT MILESTONE:** Phase 1A — coco_lab core and proofs. Start it only after
Phase 0 closes: this branch on `main` and pushed, the tags pushed, and the
name decided.

**EXACT NEXT ACTION:** in the main checkout, once the other session has
finished:
1. Save the other session's entry:
   `git diff docs/SESSION_LOG.md > ~/coco_0bh_entry.patch`
2. Restore the file: `git checkout -- docs/SESSION_LOG.md`
3. Set CLAUDE.md aside:
   `git stash push -m m0b-claude -- CLAUDE.md`
4. Fast-forward: `git merge --ff-only p0-consolidation-merge`
5. Re-apply your CLAUDE.md edit by SHA:
   `git stash apply <sha of m0b-claude>`, then drop that stash entry.
6. Paste the 0B-H entry back in above or below this one, and commit it.
7. `git push jazzy2 main`

---

## Milestone 0C — Phase 0 closure (2026-09-29)

**Status:** COMPLETE, for everything this milestone may do locally. Each
public action is prepared and awaits the owner. Nothing was pushed, tagged,
published, renamed, archived or deleted remotely.

**Local main**
- SHA: the commit that carries this entry. Its parent is `cdcf17d` (the
  0B-H entry preserved), whose parent is `b55f24f` (0B), fast-forwarded
  from `442bca0`. **No merge commit.**
- Clean: yes for tracked content, with one exception left deliberately:
  - `M CLAUDE.md`: the owner's own 14-line "Multi-agent protocol" section.
    It refers to the local, untracked `AGENTS.md`; committing it is the
    owner's call.
  - The untracked user-owned files (`.codex/`, `AGENTS.md`, `ROADMAP.md`,
    `docs/agents/*`, `docs/RSE_ASSIGNMENT_PLAN_V2.md`,
    `P02_NOTE_FOR_CODEX.md`, `tatus --short`) are unchanged.
- Contains P03C: yes (merge `232454d`).
- Contains Phase 0: yes (`b55f24f` + this commit).

**Public main**
- SHA: `jazzy2/main` = `442bca0`, the same as at session start. This
  session did not change it.
- Ahead / behind: local `main` is ahead of `jazzy2/main` by the 0C commits
  and behind by 0. `442bca0` is their merge-base, so the push is a
  fast-forward.
- Push awaiting approval: `git push jazzy2 main`.

**How the agent race was reconciled**
1. Froze the state (`status`, `HEAD 442bca0`, worktree list, `diff`). The
   only tracked changes were `CLAUDE.md` +14 (the owner's) and
   `docs/SESSION_LOG.md` +129 (the 0B-H entry); nothing was staged.
2. Safety copy: `~/coco_phase0_backups/0C_20260929_021946/`, containing
   the full working-tree patch, the 0B-H patch, the CLAUDE patch, both
   working files byte-for-byte, `HEAD.txt`, the stash SHA and `SHA256SUMS`.
3. Compared the two logs. They were not identical and neither contained
   the other:
   - The branch had the 0B entry, which only mentions 0B-H.
   - The working copy had the full 0B-H entry: its deletions, disk
     figures, protected eYRC paths and `~/simple_gz_ws`.
4. Checked the working files were unchanged since the backup. Stashed them
   with the tag `m0c-preserve-0BH-CLAUDE-…` (`b9d1a1f`, captured by SHA).
   Ran `git merge --ff-only p0-consolidation-merge`, which fast-forwarded
   `442bca0..b55f24f`. `b55f24f` had been verified first:
   - exactly 1 commit ahead and 0 behind;
   - only `.md` files (11), with CLAUDE.md and SESSION_LOG as pure
     additions.
5. Re-applied the CLAUDE hunk from the stash; it is identical to the
   backup's. Inserted the 0B-H block (7,647 B) verbatim between 0A and 0B.
   Removing it again reproduces the committed file exactly; only the `---`
   separators are shared. Committed as `cdcf17d`.
6. Dropped only stash `b9d1a1f`, found by SHA. The owner's stash `fcf5fa4`
   is untouched.
- `git checkout -- <file>`, `reset --hard`, `clean` and force-pushes were
  not used, and no agent's work was discarded.

**Documentation (verified)**
- ROADMAP:
  - `docs/ROADMAP.md` is byte-identical to the owner's untracked root
    `ROADMAP.md`.
  - `docs/history/ROADMAP_COCO2.md` is byte-identical to
    `442bca0:docs/ROADMAP.md`.
  - The `~/Downloads` copies were deleted by 0B-H, which recorded them as
    identical.
- LAB_PHASES: byte-identical to `~/ros2_ws(personal)/src/LAB_PHASES.md`.
- Links: 81 of 82 repo-internal links in all tracked `.md` files resolve.
  The one exception is the README banner's text inside a LAB_PHASES code
  fence.
- PROJECT_STATE:
  - Phase 0 is marked closed locally, with its public actions pending.
  - The master-context row is updated.
  - No hit in the scan repeats a corrected claim: every match is inside a
    correction.
- README: consistent with the new direction. The planner wording appears
  only as a correction.
- CLAUDE: the committed addendum, from 0B. The frozen-era text above it is
  unchanged because edits are additive only; the addendum supersedes it.
- SESSION_LOG: 0A → 0B-H → 0B → 0C, with nothing removed.
- Master context: **MASTER CONTEXT: NOT PRESENT IN REPOSITORY.**
  - The final targeted search covered every `.md`, `.txt`, `.json` and
    `.jsonl` under `~`, except caches, `~/ros2_ws` and the run trees. It
    looked for a §45 section co-occurring with P0.4, or a master-context
    title.
  - Only Phase 0 transcripts and plans matched, and every match is the B2
    instruction or a "not found" report. No §45 body exists on this
    machine.
  - **B2: DROPPED — the canonical master context does not exist as a
    repository file.** No substitute was created.
  - The verbatim ROADMAP and addendum texts still mention it.

**Collision monitor** (documentation unchanged in 0C; it was verified
truthful)
- slowdown: verified post-fix (0A), 300 valid samples.
- wheel cap: 0.090 m/s. Wheel p50 / p90 / p99 / max = 0.090 / 0.090 /
  0.090 / 0.090. 0 samples above it.
- STOP behaviour: **not verified.** The wall probe stopped ≈0.264 m from
  the wall under FootprintApproach, and STOP never fired. The cause is
  unknown; `robot_radius` 0.25 is a hypothesis only. The pre-fix
  historical results are kept separately (KL0 history, C2-M5.0's 84.2 %).
- unresolved: the STOP mechanism change, and the short-streak residual.

**P03C report** is kept as history. PROJECT_STATE carries the corrections:
- the targets are at x = 4.05, not 6.3–7.3;
- the lift is 34.3–35.8 mm, median 35.3, per the logs, not "35.8 mm on all
  13".

**Cleanup**
- Remaining unknowns, now classified (details in
  `docs/data/m0b_phase0/README.md` §7):
  - Antigravity.tar.gz: **KEEP / owner decision.** The IDE is not
    installed, the tarball is the only local copy, and the IDE has been
    unused since 2026-09-11.
  - Codex worktree: **KEEP.** It holds unique source and evidence, and its
    committed work is only on the local, unpushed
    `codex/c2nav34-odom-final`.
  - `tatus --short`: **SAFE-TO-DELETE**, as a duplicate of the backup and
    of stash `fcf5fa4`.
  - `~/simple_gz_ws`: **SAFE-TO-DELETE** (pkg-create boilerplate with a
    Gazebo Classic empty world).
- Correction to 0B: blob `7f93a36` is held by stash `fcf5fa4`; it is not
  dangling.
- Correction to 0B-H: its "Preserved" list includes
  `~/coco_consolidation_ws`, which 0B had already deleted (see 0B).
- deleted this milestone: **nothing.**
- disk: 36,748,484,608 B free at the start and 36,743,479,296 B at the end.
  No recovery is claimed; this session only added the ~310 KB backup.
- preserved: the four items above, the backups in `~/coco_phase0_backups/`
  and `~/coco_premerge_backup/`, all worktrees, and all run evidence.
  `/tmp/launch_params_*` (0A leftovers) is still pending the owner.
- **E-YANTRA PROTECTED — NO FILES MODIFIED.**
  - `~/ros2_ws` (eYRC_26-27_Strata-Cobot at `4559a79`): 0 files modified
    since 01:58 IST.
  - `~/task1a_scratch`, `~/SC#2200_task1A_detection.png` and the eYRC
    downloads are present and untouched.

**Remote branches**
- Archive preparation: unchanged and still exact.
  - 12 `archive/<branch>` tag commands are in
    `docs/data/m0b_phase0/README.md` §2.
  - The 13 tips are re-verified.
  - Proposed deletions: 11 branches after the tags. Keep `main` and
    `claude/docker-reproducibility`, which is unmerged (+10).

**Repository name:** awaiting the owner's choice. All eight candidates are
reconfirmed free (404): cutaway-robotics, coco-robot-lab, robotlab-live,
open-robotics-lab, botbench-lab, coco-lab, nav-lab, ros-lab. The factual
comparison is in §3 of the evidence file.

**Video migration:** awaiting approval, with commands in §4 of the evidence
file.
- Release `m6-fetch-demo` on coco-robot-jazzy-2.0 at `9b1ed7f`, with
  `coco_fetch_demo.mp4` (8,805,381 B, sha256 `7a2f761e…5674`, still the
  only copy).
- Then the README line 59 pointer change.
- Then an added banner on coco-robot-ros2, not a replacement, because it
  cites the IEEE ICRM 2025 paper.
- Then its archival.

**Tests**
- existing measured baseline: 1,966 / 0 / 0 (0A, `232454d`).
- additional tests run this milestone: none. Every 0B and 0C change is to
  `.md` files, and no test reads them.

**UNVERIFIED**
- The STOP-probe mechanism change.
- The short-streak residual's cause.
- Which process wrote 0B-H.
- Whether the master context exists outside this machine (for example, in
  a chat). Only its absence from the machine is established.

**HUMAN DECISIONS REQUIRED**
1. `git push jazzy2 main`.
2. Commit, or keep local, your CLAUDE.md "Multi-agent protocol" edit.
3. The archive tags, then the 11 remote-branch deletions.
4. The platform name.
5. The video migration, then the coco-robot-ros2 banner and archival.
6. The cleanup items: delete `tatus --short` and `~/simple_gz_ws` (both
   SAFE-TO-DELETE)? Keep or delete Antigravity.tar.gz? Clear
   `/tmp/launch_params_*`?
7. Optionally, push or archive the local-only
   `codex/c2nav34-odom-final`. It is the only git home of the C2-NAV.34/35
   work.

**NEXT MILESTONE:** Phase 1A — coco_lab core and proofs.

**EXACT NEXT ACTION:** Begin Phase 1A only after Phase 0 is explicitly
closed. That means the owner approves and runs `git push jazzy2 main`, and
decides items 3–5 above, or explicitly defers them.

---

## PHASE 0 — CLOSED (2026-09-29)

**Public main**
- Pushed with the owner's approval: `git push jazzy2 main`, `442bca0..6853517`.
- Before the push: local `6853517`, remote `442bca0`, 0 behind / 3 ahead,
  and the push was verified to be a fast-forward.
- **Public main SHA: `6853517`**, equal to local `main` (checked with
  `git ls-remote`).
- The GitHub API confirms the public tree carries the Phase 0
  documentation:
  - `docs/ROADMAP.md`, whose blob `c5b132d` matches local;
  - `docs/LAB_PHASES.md`;
  - `docs/history/ROADMAP_COCO2.md`;
  - `docs/data/m0b_phase0/README.md`;
  - the README's COCO Lab banner;
  - PROJECT_STATE's "ACTIVE — building COCO Lab" header.
- This checkpoint commit is local only. The owner approved one push, not
  this commit.

**Cleanup completed** (owner-approved; apparent sizes measured just before
each deletion)
- `<repo>/tatus --short`: 19,011 B. Before deleting, it was re-confirmed
  md5-identical (`d8443d89…`) to
  `~/coco_premerge_backup/20260919_033040/repo_local_files/tatus --short`.
  Its content is also held in stash `fcf5fa4`.
- `~/simple_gz_ws`: 626,692 B. Before deleting, it was re-confirmed that
  it is not a git repo, has the same 4 boilerplate source files, and no
  open handles.
- `/tmp/launch_params_*`: 837 files, 4,109,543 B.
  - Deleted: files dated 2026-09-28 01:13 to before 02:30 on 09-29 (the
    0A-era set). The list was built explicitly, not with a glob, and
    covers only files older than 08:40 that no live process named on its
    command line.
  - **Kept: 23 files belonging to a LIVE COCO run.** It is a p03d mission
    on `~/coco_p03d_ws`, launched 08:41:40 by another session. All 17
    files named on its live command lines are verified present.
- Total deleted: **4,755,246 B**. `df` free went from 36,726,976,512 B to
  36,734,537,728 B; the gain is larger because of block rounding, and the
  live run is writing.

**Codex work preserved**
- `<repo>/.codex/worktrees/c2nav0-implementation` is untouched: 219,462,730
  B, the same as in 0B.
- The local-only branch `codex/c2nav34-odom-final` is untouched at
  `5c7f597`.
- The owner's note named `~/.codex/worktrees`; that path does not exist.
  The worktree is under the repository's `.codex/`.

**Antigravity installer preserved:** `~/Downloads/Antigravity.tar.gz`,
172,322,487 B, unchanged since 2026-09-11. It awaits the owner's decision.

**E-YANTRA PROTECTED — NO FILES MODIFIED.**
- `~/ros2_ws` (eYRC_26-27_Strata-Cobot at `4559a79`): 0 files modified
  since 01:58 IST.
- `~/task1a_scratch` and `~/SC#2200_task1A_detection.png` are present.

**Still awaiting the owner:**
- archive tags, then remote-branch deletions;
- the name;
- the video migration and the coco-robot-ros2 archival;
- the Antigravity installer;
- the owner's uncommitted CLAUDE.md edit;
- pushing this checkpoint.

NEXT MILESTONE: Phase 1A
EXACT NEXT ACTION: Start a fresh Claude Code session and execute LAB_PHASES.md §1A.

---

## Phase 1A — the coco_lab core and its proofs (2026-09-29)

**Status:** COMPLETE. Only 1A was done. There is no 1B work, no web code,
no ROS code, and no algorithm beyond the five.

**Precondition, checked at session start**
- `SESSION_LOG.md` shows PHASE 0 — CLOSED and Milestone 0C COMPLETE.
- Local `main` is `9ee4a52`, the CLOSED checkpoint.
- Public `jazzy2/main` is `6853517`. The Phase 0 docs are public; the
  CLOSED checkpoint commit is still local-only, as that entry itself
  records.

**Where**
- Branch `lab1`, created from `main` `9ee4a52`.
- Worktree `<repo>/.claude/worktrees/lab1`.
- The SHA is the commit that carries this entry. `main` is untouched.

**What was built**
- `coco_lab/`, an ament_python package. Its runtime is standard-library
  only (`install_requires=[]`) and it never imports rclpy. It builds with
  colcon AND pip-installs into a plain venv. Modules:
  - `graph.py`: the SearchGraph interface — `neighbours`, `edge_cost`,
    `heuristic`, `locate`, `is_valid`. A (cell, heading) state space
    plugs in without touching the algorithms; `test_graph_interface.py`
    proves it with a toy heading space defined only in the test.
  - `grid.py`: occupancy plus an optional cost layer; 4- and
    8-connectivity; diagonal cost √2 (or 1); corner cutting off by
    default, with a toggle. The declared cost function is
    `base × (1 + cost_weight · cost[b] / cost_scale)`, with defaults 2.0
    and 252.
  - `heuristics.py`: zero, Manhattan, Euclidean and octile, plus
    `analyse()`, which gives the admissible/consistent verdict with a
    witness move and an exact single-move proof.
  - `search.py`: BFS, Dijkstra, A\*, greedy and weighted A\*.
    - The goal test runs on expansion, and closed states are never
      reopened.
    - Tie-breaking is `low_h` by default, with `fifo` behind a toggle.
    - It is deterministic.
  - `trace.py`: trace schema v1, with columnar push/expand/relax/path
    events, a summary, and MAJOR.MINOR versioning.
- `docs/labs/TRACE_SCHEMA.md`, pinned to the code by a test.
- `requirements-test.txt` pins hypothesis 6.98.15, networkx 2.8.8 and
  pytest 7.4.4. `package.xml` declares `python3-hypothesis` and
  `python3-networkx` as test_depend.
- `docs/RESULTS.md` has a new section, "COCO Lab Phase 1A".

**Measured**
- Tests:
  - colcon route (ROS Jazzy, the colcon install tree imported): **141
    passed, 0 failed, 0 skipped**, 22.89 s.
  - pip route (plain venv, `env -i`, rclpy absent): **138 / 0 / 0**, the
    3 ament linters excluded, 22.50 s.
  - Load average was ≈ 3. Runs at load 28 took 49–61 s.
- Properties: 7 roadmap properties plus the heuristic-analysis
  cross-check. Each ran **1,000 passing examples, 0 failing**. The
  path-cost properties' 1,000 all have a path of at least one move
  (49–71 trivial draws discarded).
- Oracle: networkx on the identical graph, exact within 1e-9 relative.
- Committed counterexamples:
  - greedy costs 7 against an optimum of 5;
  - A\* with Manhattan on √2 diagonals costs 5 + √2 against an optimum of
    3 + 2√2.
- Mutation check: 5 of 6 injected bugs are caught by the properties.
  - The survivor, weight w² instead of w, passes the loose w·C\* bound.
  - It is now caught by a test pinning `f` on every event.
- Determinism: one SHA-256 for all five traces under three
  PYTHONHASHSEEDs.
- rosdep keys verified with `rosdep resolve`. On this machine they
  resolve to apt 6.98.15 / 2.8.8.

**Failures, all fixed.** Every failure was a test or evidence defect, and
none came from an algorithm. RESULTS.md lists all six with causes. The
most important one: the first property design gave about 500 path-bearing
maps per property, not 1,000.

**UNVERIFIED**
- A bare `colcon test`. `python3-hypothesis` is not apt-installed, and
  there is no passwordless sudo. The colcon run used a
  `--system-site-packages` venv that adds only the two pins.
- Pyodide loading `coco_lab` (1D).
- The declared cost function against SmacPlanner2D's (1C). No
  equivalence is claimed.
- A\*'s expanded set on no-path maps. Its branch in the ⊆-Dijkstra
  property is dead, because that property now draws reachable goals.
  The five algorithms' status agreement on no-path maps IS tested (610
  such maps).

**Traps paid this session**
- ament's pep257 enforces D213: the docstring summary starts on the line
  after `"""`.
- `python3-venv` is missing here. Use `python3 -m venv --without-pip`,
  then `python3 -m pip --python <venv>/bin/python install …`.
- In this worktree, the Bash sandbox refuses compound commands that use
  `env -i`, `$VAR` as the command name, loops, or heredocs. Put the steps
  in a script file and `bash` it.
- The worktree session cannot run a command that names another path as
  its executable through a variable. Use absolute paths.

**HUMAN DECISIONS REQUIRED**
1. Optional: `sudo apt install python3-hypothesis`, or `rosdep install
   --from-paths coco_lab --ignore-src`, so a bare `colcon test` can run.
2. Phase 1B step 4 asks you for the ISRO simulator's source. Without it,
   1B's result is labelled a reconstruction, never a diagnosis.
3. Carried from Phase 0: pushing the local `main` checkpoint `9ee4a52`;
   the archive tags; the name; the video migration; the Antigravity
   installer; your uncommitted CLAUDE.md edit.

NEXT MILESTONE: Phase 1B — bundles, maps, and the ISRO reconstruction.
EXACT NEXT ACTION: In a fresh session, on branch `lab1`, execute
LAB_PHASES.md §1B, and have the ISRO source (or the decision to go without
it) ready.

## Phase 1B — bundles, maps and the ISRO reconstruction (2026-09-29, in progress)

Checkpoints are appended per sub-milestone.

**Owner decisions this session (asked, answered):**
1. The ISRO algorithm functions may be vendored VERBATIM into `coco_lab`,
   pinned to upstream commit `5aad7b3`, with per-function hash checks.
   They become public when `lab1` is pushed.
2. There is no original internship-era `.py` and no
   `simulation_metrics.csv`. The report's code listing, transcribed at
   `5aad7b3`, is the source of truth. Table 1's raw data is absent.
3. The arena map precision/recall is reported as a
   rasterisation-consistency check, NOT map quality. The honest number is
   deferred to 1C, because the saved Nav2 map is generated from the same
   parameters as the world.

### 1B-0 — recovery and baseline (2026-09-29)

- Branch `lab1` at `c3713dd` == `jazzy2/lab1`, tree clean. The Phase 1A
  entry above matches the repository.
- Doc paths: `AGENTS.md` does not exist. `PROJECT_STATE.md` and
  `HOW_TO_RUN.md` are at the repo root, not under `docs/`.
- No 1A venv survived, so both routes were rebuilt in the job's tmp
  directory.
- **Measured baseline:**
  - pip route (plain venv, `env -i`, `rclpy` absent): **138 / 0 / 0**,
    20.00 s.
  - colcon route (the tmp install tree imported): **141 / 0 / 0**,
    21.09 s.
  - Load average 0.2 to 1.4; hypothesis 6.98.15, networkx 2.8.8.
- **Trap:** `pip install ./coco_lab` builds in-tree, creating
  `coco_lab/build/` and `coco_lab.egg-info` (both gitignored). ament_flake8
  then also lints the stale `build/lib` copy. Install from a copy of the
  package outside the source tree instead. The two artefacts from this
  session were removed.

### 1B-1 — map contract (2026-09-29)

- **Built:**
  - `coco_lab/maps.py`: map schema v1 (`coco_lab.map` "1.0"), `LabMap`
    (occupancy free/occupied/unknown, optional cost layer, optional
    placement), `content_hash`, `to_grid`, `downsample`, `Raster`, the
    Nav2 saved-map import/export, and `compare_occupied`.
  - `coco_lab/teaching.py`: eight 20 x 20 fixtures, each with a claim.
  - `docs/labs/MAP_FORMAT.md`, pinned to the code by a test.
  - `docs/data/lab1b/arena_maps.py` and its output `arena_maps.json`.
- **Decisions:**
  - The move model is a run input, not part of the map. Unknown cells are
    blocked by default.
  - Row 0 is the top row, and `origin` is the bottom-left corner.
- **Found:**
  - A saved map read with `free_thresh` 0.25 turns map_saver's unknown
    pixel 205 (occ 0.196) into FREE. `to_nav2` writes 0.196, as the repo's
    generator does, and a test pins the difference.
- **Measured:**
  - Tests: pip route **219 / 0 / 0** (20.89 s); colcon route
    **222 / 0 / 0** (21.83 s).
  - Arena maps, a rasterisation-consistency number and NOT map quality
    (decision 3).
    - All occupied cells: precision **0.9456**, recall **0.5771**.
    - Boxes only: precision **0.8941**, recall **1.000**.
    - The saved map marks **13,186 of 15,600** ramp-body cells unknown.
- **Unverified:** a map-quality number. That needs a slam_toolbox map of
  `coco_navigation`, which is 1C at the earliest.
- Committed as `a12462a`. The push failed twice, because the tool's
  permission check returned no verdict; it was retried with the next
  commit.

### 1B-2 to 1B-4 — bundles, the ISRO source and the experiment (2026-09-29)

These were committed together. `bundle.py` rebuilds heading-grid graphs and
the golden set includes one, so the split commits would not each have been
green.

- **Built:**
  - `coco_lab/bundle.py`: bundle format v1, a directory holding
    `manifest.json` plus `arrays.bin[.gz]`. It covers provenance, the
    content hash, bounded loading, trace-on-graph validation and replay.
    `docs/labs/BUNDLE_FORMAT.md` is pinned by a test, and five golden
    bundles live in `coco_lab/test/fixtures/bundles/`.
  - `coco_lab/heading.py`: `HeadingGrid`, the (cell, incoming heading)
    SearchGraph. The unchanged `coco_lab.search` runs on it, which
    confirms 1A's seam.
  - `coco_lab/isro/upstream_v3_6.py`: the ISRO search functions VERBATIM
    from `5aad7b3`. It is generated by `docs/data/lab1b/vendor_isro.py`,
    and each range is hash-checked.
  - `coco_lab/isro/historical.py`: the harness.
  - The `turn_trap` teaching fixture.
  - `docs/data/lab1b/isro_experiment.py` and `resolution.py`, with their
    JSON output.
  - `docs/labs/ISRO_INVESTIGATION.md`.
  - `coco_lab` bumped to 0.2.0.
- **Findings (full list in ISRO_INVESTIGATION.md):**
  - SOURCE-VERIFIED: the logged "Steps" is `len(smooth_path(path))`, so
    the report's "4 %" is 3.5 % in waypoint count.
  - SOURCE-VERIFIED: the state is the cell, and relaxation is on a
    strict `<`.
  - SOURCE-VERIFIED: hypothesis (b) is refuted, since diagonals cost √2.
  - MEASURED: on fixed inputs over 1,800 maps the Steps gap does not
    reproduce (ratio 0.9993 / 0.9966).
  - MEASURED: the time ratio is 4.5–5.4x on long trips.
  - MEASURED: cell-only suboptimality occurs on about 1 map in 6 (max
    +2.4 %), symmetric between A\* and Dijkstra. With the penalty at 0,
    or with heading in the state, there are 0 discrepancies.
  - MEASURED, NEW: the historical `smooth_path` can loop forever.
    Harness-predicted hangs agreed with the verbatim function 20 of 20.
- **Resolution (1B.3), measured:** full-arena Dijkstra takes 1.022 s at
  0.05 m and 0.228 s at 0.10 m, and the bundle gzips to 1.44 MB and
  0.38 MB. Recommendation: 0.10 m for edit mode.
- **Traps paid:**
  - The harness first called the verbatim smoother directly. The 20 x 20
    trap search died with exit 137 (memory), and a test run hung for over
    10 minutes, before the loop was diagnosed.
  - Hypothesis biases integer draws small, so the first heading property's
    1,000 maps were mostly 2 x 2. Sizes now come from the seed, and the
    statistics show 77 % with a side over 6.
  - The tool's permission check returned no verdict for a stretch of the
    session, which blocked all Bash and ended one turn. Files were written
    meanwhile, and nothing was lost.

### 1B-5 — integration and release gate (2026-09-29)

- **Tests, measured on installed copies:**
  - pip route **314 / 0 / 0**, 33.48 s;
  - colcon route **317 / 0 / 0**, 35.49 s, linters included;
  - load average ≈ 2.4. The re-run after the documentation edits is
    recorded in the commit message.
- **Docs:**
  - `docs/RESULTS.md` has a new section, "COCO Lab Phase 1B".
  - Root `PROJECT_STATE.md` has a new COCO LAB table, plus a dated
    correction: its "no `coco_lab` package exists yet" had been false
    since 1A.
  - Root `HOW_TO_RUN.md` has a `coco_lab` tests subsection.
  - `TRACE_SCHEMA.md` has a graph-kinds note (additive; trace stays 1.0).
  - `MAP_FORMAT.md` lists `turn_trap`.
- **Architecture, unchanged:** no ROS, web, TypeScript, arbiter, coco.v1
  or Nav2 file was touched. `coco_lab` still never imports `rclpy`; the
  guard now walks subpackages. No simulator was run.
- **Cleanup:** only my own artefacts were removed (`coco_lab/build`,
  `coco_lab.egg-info` from the first pip install). No cleanup candidates
  were surveyed; that is outside 1B.

## Phase 1B — COMPLETE (2026-09-29)

**Status:** COMPLETE, with two items recorded as not measured rather than
done:
- a map-quality number, which needs a SLAM map (owner decision: defer to
  1C);
- an explanation of the internship runs' 3.5 %, because their inputs no
  longer exist.

**UNVERIFIED:**
- Pyodide loading `coco_lab`, including `bundle.py` (1D).
- Whether the historical runs hit the smoother loop.
- Why A\* logged more Steps in Table 1 (HYPOTHESIS: small-sample,
  non-fixed inputs).

**HUMAN DECISIONS REQUIRED:**
1. Phase 1C go-ahead.
2. Carried over: the Phase 0 public actions (the `main` push, archive tags,
   the name, video migration).
3. Optional: `sudo apt install python3-hypothesis`, for a bare
   `colcon test`.

NEXT MILESTONE: Phase 1C — the real-stack hook, conformance and three
real runs (LAB_PHASES.md §1C). Not started.
EXACT NEXT ACTION: In a fresh session on branch `lab1`, read this entry
and `docs/labs/ISRO_INVESTIGATION.md`, then execute LAB_PHASES.md §1C.

## Phase 1C — the real-stack hook, conformance and three real runs (2026-09-29, in progress)

Checkpoints are appended per sub-milestone. The approved plan, with the
owner's decisions D-1 … D-6 at its top, is `docs/labs/PHASE_1C_PLAN.md`.

### 1C-0 — reconstruction, baseline and plan checkpoint (2026-09-29)

**Owner decisions (approved before this session; recorded, not re-asked):**
- D-1: the real SLAM map-quality number is OUT of 1C and moves to Lab 3.
  No generated or privileged map is substituted for it.
- D-2: the costmap snapshot is `/global_costmap/costmap_raw`.
- D-3: the smoothing comparison uses Smac's `unsmoothed_plan` output. It is
  never described as "smoothing disabled": 1.3.11 has no such parameter.
- D-4: the three runs' goal is world (0.5, 6.0), yaw 0.
- D-5: bundle 1.1, additive, carries the recorded-run streams.
- D-6: bundles go into git only if their committed total is ≤ 10 MB.

**Starting state (FACT)**
- Branch `lab1`, worktree `<repo>/.claude/worktrees/lab1`, HEAD
  `e06dc94893a3f61138f7b68f0f4c4ccdc7329883`, equal to `jazzy2/lab1`
  (fetched this session), tree clean.
- Plan source `~/coco_lab_phase1c_plan.md`, SHA-256
  `35ba2f85e455d5d62012cbac45082cc7bb5cc6efd9d05f443fa71b7ffe80c438`,
  committed verbatim under the decisions header.
- Installed: `nav2_smac_planner`, `nav2_costmap_2d`, `nav2_navfn_planner`,
  `nav2_planner`, `nav2_controller`, `nav2_msgs` all `1.3.11-1noble.20260412`;
  `rosbag2_py` 0.26.10; `slam_toolbox` 2.8.5.
- Nav2 tag `1.3.11` is upstream commit
  `6e0958affab9bc6c2367aa68c3bead164c2bc697` (`git ls-remote`). The sources
  were re-fetched at that tag into `~/coco_lab_runs/lab1c/nav2_src_1.3.11/`
  and hashed; the hashes and the installed-header cross-check are in
  `docs/labs/CONFORMANCE.md`.
- The mission `gazebo_models/config/nav2_params.yaml` SHA-256 is
  `06c308aff78d4e7327212bbca280f62be7a7baef604ae41676e886b72301db8c`,
  equal to `e06dc94`'s blob. This is the byte-identity reference for J4.
- The saved map `coco_navigation` is 500 x 380 cells at 0.05 m, origin
  (−6.5, −9.5), as the plan states.
- No Gazebo, Nav2 or ROS process was running at session start. The Codex
  desktop app was running, idle.

**Baseline, measured (load average ≈ 1)**
- `coco_lab` pip route (plain venv, `env -i`, rclpy absent, installed from
  a copy outside the tree): **314 passed, 0 failed, 0 skipped**, 33.32 s.
- `coco_lab` colcon route (job-local install, linters included):
  **317 / 0 / 0**, 35.06 s.
- Both equal the 1B-5 figures.
- From a COCO-only overlay of this worktree (private ROS domain):
  `gazebo_models` **227 / 0 / 0** (`--ignore=test_integration`),
  `custom_teleop` **75 / 0 / 0**.

**Discrepancies found (reported before implementing)**
1. The session prompt names `docs/labs/RESULTS.md` and
   `docs/PROJECT_STATE.md`. Neither exists: results live in
   `docs/RESULTS.md` and the state file is the root `PROJECT_STATE.md`, as
   1B-0 already recorded. Those are the files updated.
2. **`scripts/build_overlay.sh` could not build this branch (measured).**
   It requires `--symlink-install`, under which colcon runs `coco_lab`'s
   `setup.py` through a symlink in the build directory; `setup.py` located
   `requirements-test.txt` with `abspath`, beside the link, and failed with
   `FileNotFoundError`, aborting every other package. The 1A/1B test routes
   never used `--symlink-install`, so neither caught it. Fixed with
   `realpath` (one line) and pinned by
   `test_dependencies.py::test_setup_py_runs_through_a_symlink`. The overlay
   then built all 10 packages. `coco_lab` after the fix: pip route **315 / 0 / 0**, colcon route **318 / 0 / 0** (each + the new test).
3. The plan's line citations for `nav2_params.yaml` (":345-383") point a
   few lines off in this file; the content (planner block) is as stated.

**Source facts noted BEFORE any measurement (so they cannot be read as
post-hoc explanations)**
- `a_star.cpp:350-355`: once the best pushed heuristic is under
  `tolerance / resolution` (5 cells), Smac counts "approach" iterations and
  after `max_on_approach_iterations` (1000) returns the best-heuristic
  node's CURRENT parent chain. That node can be the goal cell pushed but
  not yet popped, so a path whose endpoint is the goal is not guaranteed
  optimal. The pre-registered prediction (E equal within 1e-4 whenever the
  endpoint is right) stands as written; this is the mechanism to examine
  first if it fails (F-6).
- `utils.hpp:44-53` (installed header): `getWorldCoords` returns
  `origin + mx · res` for integer cell indices, i.e. the cell's lower-left
  CORNER, not its centre. Smac 2D's raw and smoothed poses are therefore
  expected half a cell (0.025 m) toward −x, −y of the cell centres. Smac
  poses are mapped back to cells with `round`, not `floor`. To be checked
  live in the static smoke test.
- `a_star.cpp:425-437` + `smac_planner_2d.cpp:237-247`: the heuristic is
  the Euclidean distance to the goal's CONTINUOUS map coordinates, so
  h(goal cell) is up to √2/2, not 0. It remains consistent (1-Lipschitz),
  so a popped goal is still optimal.

NEXT: 1C-1 — `coco_lab_ros` skeleton, guards, pure modules and their tests.

### 1C-1 — `coco_lab_ros`: pure modules, guards, tests (2026-09-29)

- **Built** (`coco_lab_ros/`, ament_python, depends on `coco_lab`, rclpy,
  nav2_msgs; nothing depends on it, so the graph stays acyclic):
  - `costmap.py` — a `nav2_msgs/Costmap` snapshot: content hash (stamp
    excluded), Nav2's own `worldToMapContinuous` with the float32 step
    emulated, the row flip, 253/254 → OCCUPIED, 255 → UNKNOWN, raw value
    kept in the cost layer for every cell (lossless, tested).
  - `planning.py` — C0 and C1 exactly as plan §D pre-registered; the run
    table (A* euclidean, Dijkstra zero, greedy euclidean, plan §E.2).
  - `metrics.py` — L, E (undefined, never coerced, for a non-move), I
    (2.5 mm midpoint sampling), c_max, endpoint, nearest-rank p95,
    linear-interpolation quartiles. `pathing.py` — cell centres, travel
    yaw, goal yaw last; Smac poses mapped back by `round` (corners).
  - `params.py` — deep merge, lists replaced, deterministic dump;
    `config/nav2_lab_overlay.yaml` adds only `NavFnAStar`.
  - `safety.py` — the forbidden topics (wheel, arbiter inputs, command
    chain) and `violations()`.
- **Guards**: the forbidden list is read from the arbiter's own source;
  no Twist import; every `create_publisher` names a lab topic; no
  forbidden topic literal outside `safety.py`; a constructed node
  publishes only the four lab topics; `coco_lab` never imports
  `coco_lab_ros`; the pure modules import with ROS poisoned.
- **Properties** (1,000 path-bearing random RAW costmaps each, measured
  with `--hypothesis-show-statistics`): E\*(C0) ≥ E\*(C1) — 1000 passing,
  0 failing, 2 rejected by `assume`; the C1 optimum (Dijkstra and A\*)
  equals networkx — 1000 passing, 0 failing, 10 rejected.
- Golden `costmap_raw` fixture with pinned costs and trace hashes.

### 1C-2 — the hook: node, launch, overlay, bundle 1.1, exporter (2026-09-29)

- **Built**: `lab_planner` (one plan, one FollowPath goal, no replanning;
  latched `/lab/plan`, `/lab/status` JSON, `/lab/costmap_snapshot`,
  `/lab/trace_gz`; a glass-box bundle on disk); `nav2_client.Nav2Probe`
  (publishes nothing); `lab_stack.launch.py` (arbiter `initial_mode:=nav`
  + `nav.launch.py arbiter:=true params_file:=<merged>`);
  `lab_static_smoke.launch.py`; `export.py` (bag → 1.1 bundle + metrics,
  built from the BAG and cross-checked with the node's glass-box bundle);
  `run_analysis.py`; `ros_clean.sh` patterns for every new executable,
  launch file and script (install-path anchored; tested with a decoy).
- **Bundle 1.1** (`coco_lab/bundle.py`, D-5): an optional `recording`
  block + `recording.<group>.<col>` f64 arrays (gt, amcl, plan, cmd); a
  stream not captured is listed in `recording.missing`, never
  zero-filled. A bundle without a recording is still written as `"1.0"`:
  the five 1.0 golden fixtures are unchanged, byte for byte. A 1.0
  reader refuses a bundle WITH a recording (its array table is exact) —
  stated in BUNDLE_FORMAT.md, not hidden. New golden fixture
  `recorded_run_synthetic_1_1` (synthetic streams, labelled so).
- **Static smoke, measured on the real Nav2 1.3.11 binaries** (map_server
  + planner_server, no Gazebo, a committed 80 x 60 map): all three
  planner ids answer; `/unsmoothed_plan` is the topic name and is
  published for GridBased only; **Smac's poses sit on cell corners**
  (residual 1.0e-6 cells), confirming the 1C-0 source reading; on that
  map E(Smac raw) = E\*(C1) to 2.8e-16 relative. A smoke number, not the
  experiment.
- **Found and fixed before any Gazebo run:**
  1. **NavFn writes into the shared global costmap (measured, then
     source-confirmed).** In a dry run of the conformance tool against the
     static stack, 12 of 12 pairs went VOID: the costmap hash changed
     after every NavFn request and never after Smac's.
     `NavfnPlanner::clearRobotCell` sets the START cell to FREE_SPACE in
     the costmap planner_server shares (`navfn_planner.cpp` @1.3.11
     :241-242, :519-524), and the write persists. See the amendment below.
  2. `lab_planner` looped on the global `rclpy.ok()`, false under a
     non-default context; now `self.context.ok()`.
  3. The suite hung for 10 minutes: `ament_flake8`'s forked workers
     blocked on a futex after rclpy threads had run in the process. The
     linters now run first (a stable reorder in `conftest.py`); 3 of 3
     consecutive runs then passed.
  4. `export.py` named the wheel topic as a literal (to read it); the
     guard refused it; it uses `safety.WHEEL_TOPIC` now.
- **Tests, measured (load ≈ 0.5):** `coco_lab_ros` **69 / 0 / 0** (15.6 s,
  3 consecutive runs); `coco_lab` colcon **336 / 0 / 0**, pip route
  **333 / 0 / 0**; `gazebo_models` **229 / 0 / 0** (227 at 1C-0; the two
  new are existing parametrized `ros_clean.sh` tests over the new
  patterns).

### 1C-3 pre-registration — written BEFORE the Gazebo conformance run

These fix how the approved design is executed. None is a reaction to a
Gazebo measurement; there has been none yet.

1. **Two passes (forced by finding 1 above).** Pass 1 asks Smac for every
   draw, each request bracketed by the costmap hash, which must equal S0
   (else VOID — the plan's rule, unchanged). Pass 2 asks NavFn then
   NavFnAStar on the same valid pairs; after each, the costmap's
   cell-level difference from S0 is recorded, and the NavFn half is
   accepted only if every changed cell is an earlier NavFn start cell,
   now 0. The pair distribution, the metrics and coco_lab (always on S0)
   are unchanged.
2. **"Draw" and "valid".** A draw is one pair meeting the 2.0 m separation
   rule; separation rejections are resampled and counted
   (`separation_rejects`), not drawn. A valid pair is non-void AND C1
   reachable; C1-unreachable pairs are listed in `no_path` with Smac's
   answer. Stop at 50 valid or 100 draws (F-5 below 50).
3. **Start/goal** are sent as cell centres, yaw 0, `use_start`.
4. **Named extra**: the M3 analogue, spawn (map (0, 0)) → G\* (map
   (2.5, 6.0)), asked in both passes.

**M3 — discrepancy with the approved plan (FACT, git).** The plan says
M3's goal "does not exist in this world". True of `coco_navigation`, the
current world (lanes at y = ±2, ±6; no gate). But M3 (commit `58b307e`)
ran on the frozen v1 `coco_world.world`, which still contains the Zone A
gate, with goal world (0.5, 0.75): **the world file and its map
(`coco_world.pgm/.yaml`) are byte-unchanged since `58b307e`**. What
changed: `nav2_params.yaml` (the diff touches the local costmap, not the
planner or global costmap blocks) and the robot xacro — **the lidar mast
moved from the front to a rear corner**, which changes what the live
scan layers mark. So M3's world, map, start and goal survive and its
parameters are recoverable from git, but its live costmap cannot be
re-created identically. 1C runs only the approved present-day analogue;
a re-run on the frozen world would be a close replication, not identical
inputs, and is an owner decision (not run).

### 1C-3 / 1C-4 — the dry run, and the conformance sweep on a live stack (2026-09-29)

**Dry run (plan I.8; its data is NOT a result).** One A\* run end to end,
18:17–18:20 UTC, `~/coco_lab_runs/lab1c/dry_1`. It reached the goal with
every live check clean, confirmed the recorded topic set (the hidden
behavior-server action status topics included, `/diff_drive_controller/
cmd_vel` as `TwistStamped`, no `/mission/mode` publisher at all), the
exporter on a real bag, and the world/map check: with `traverse:=true`,
all 19,031 lethal cells of the live snapshot are occupied in the saved
map and every occupied map cell is lethal live. It exposed three tool
defects, fixed in `cb4e2b3` before any counted session (a watcher
segfault at exit, a core dump, a runner exiting 0 on a FAIL).

**Conformance session, MEASURED** — `lab1c_run.sh conformance`, commit
`cb4e2b3`, tree clean, ROS domain 65, 18:23:13–18:30:31 UTC, load
1.3 → 3.5. Evidence: `docs/data/lab1c/conformance/`.
- Runner checks all PASS: mission params byte-identical; 67 live
  planner_server/global_costmap parameters equal the merged file; wheel
  topic's only publisher `cmd_vel_arbiter` at start and end; 341 watch
  samples, 0 violations (arbiter `mode=nav` throughout, arbiter inputs
  unchanged).
- S0 `sha256:f7797c19…`, 500 x 380, 117,387 candidate cells (raw ≤ 252).
  The dry run's snapshot had the same hash.
- **50 draws, 50 valid, 0 void, 0 no-path**; 3 separation rejects. F-5 not
  triggered. `unsmoothed_plan` captured 50 / 50 (one message each); every
  raw start cell correct; corner residual ≤ 7.2e-6 cells.
- **The pre-registered prediction held on every pair it applies to:
  36 / 36 within 1e-4** (largest relative gap 1.08e-15).
- **14 / 50 Smac raw paths did not end on the goal cell** — 1 or 2 cells
  short (0.035–0.127 m). The pre-declared rule excluded them from the E
  comparison. POST-HOC (`lab1c_offgoal.py`, written after the sweep, rule
  unchanged): all 14 are the C1 optimum to the cell where they stopped
  (largest gap 2.0e-15); their goals sit in costlier cells (median raw
  cost 122 against 0). HYPOTHESIS, not traced: the on-approach exit
  (`a_star.cpp:350-355`).
- E(C0) = E(C1) on 50 / 50: corner cutting never changed an optimum here.
  C1 A\* cost = C1 Dijkstra cost on 50 / 50.
- NavFn pass: 51 / 51 accepted (50 pairs + the M3 analogue), at most 14
  cells changed from S0, all cleared NavFn starts, 0 unexplained.
  NavFnAStar failed once (draw 46, `NO_VALID_PATH` 208) where NavFn's
  Dijkstra succeeded.
- Distributions are in `conformance_summary.json` and RESULTS.md.

NEXT: 1C-5 — the three real runs, fresh simulator each: A\*, Dijkstra,
greedy.

### 1C-5 — the three real runs (2026-09-29, measured)

`lab1c_run.sh run`, commit `248cac1` (clean), a fresh simulator each, in
the approved order, 18:33–18:41 UTC, ROS domain 65, load 1.5–5.7.
Evidence: `docs/data/lab1c/runs/`, `runs.json`, bundles in
`docs/data/lab1c/bundles/`, bags in `~/coco_lab_runs/lab1c/run_<algo>/bag`.

- Every runner check PASS in all three; 0 voids, 0 re-runs. All three
  planned on the identical snapshot (`f7797c19…` = the conformance S0)
  from the identical start cell (130, 190) to G\* (180, 310).
- **A\***: SUCCEEDED, 27.372 s sim / 30.708 s wall, tracking error mean
  0.072 m (p95 0.162, max 0.177), endpoint 0.191 m, 0 recoveries.
- **Dijkstra**: SUCCEEDED, 27.456 s sim / 30.213 s wall, tracking mean
  0.064 m (p95 0.153, max 0.208), endpoint 0.171 m, 0 recoveries. Same
  optimal cost as A\* (160.0416) on a different, tied cell path; 33,374
  expansions to A\*'s 7,100.
- **Greedy**: FollowPath **ABORTED, `FAILED_TO_MAKE_PROGRESS` (105)** after
  18.364 s sim. Its plan cost 369.1705 (2.31× the optimum) through 58
  cells of raw cost ≥ 128; the robot stalled 1.27 m along the 11.25 m
  plan, 5.289 m from the goal, 0.049 m moved in the last 10 s (the
  progress checker needs 0.1 m per 10 s), collision monitor in
  `PolygonSlow` for the last 12.8 s. A result (F-4), not a void.
- Bundles 1.1 (all four streams present), built from each bag and equal
  in trace and map to the node's glass-box bundle. Total 909,380 B ≤ 10 MB
  → committed (D-6). Bags 6.9–8.4 MB each, external, SHA-256 in
  `runs.json` and RESULTS.md.

## Phase 1C — COMPLETE (2026-09-29)

**Status:** COMPLETE: J1–J11 hold, with the negative results documented as
results (plan §K).

- **Branch** `lab1`. Commits this phase: `9daa3be` (1C-0), `0684b0f`
  (1C-1/1C-2), `cb4e2b3` (dry-run fixes), `248cac1` (1C-3/1C-4), and the
  closeout commit carrying this entry.
- **Tests (measured, final regression, fresh overlay):** `coco_lab` pip
  route **333 / 0 / 0**, colcon route **336 / 0 / 0**; `coco_lab_ros`
  **69 / 0 / 0**; `gazebo_models` **229 / 0 / 0**; `custom_teleop`
  **75 / 0 / 0** (untouched). 0 skipped anywhere.
- **Invariants at close:** mission `nav2_params.yaml` SHA-256 `06c308af…`
  (= `e06dc94`); no file of `custom_teleop`, `coco_mission`, `coco_web`,
  `coco_config` or the mission's Nav2 config changed; the wheel topic's
  only publisher was `cmd_vel_arbiter` in every sample of every session;
  `ros_clean.sh --list` empty after every session.
- **Conformance:** 50 valid pairs; the prediction held 36 / 36 (max
  1.08e-15); 14 / 50 Smac raw paths stopped 1–2 cells short (post-hoc:
  C1-optimal to where they stopped). **NavFn/M3:** M3's goal is absent
  from the current world; M3's 6.2 % is neither reproduced nor refuted;
  the present-day analogue measured Smac 1.378 % shorter than NavFn on one
  pair. **Runs:** A\* and Dijkstra succeeded, greedy failed.
- **Artifacts:** bundles in git (0.91 MB); bags external under
  `~/coco_lab_runs/lab1c/` with their hashes committed; Nav2 1.3.11
  sources fetched to `~/coco_lab_runs/lab1c/nav2_src_1.3.11/`, hashed in
  CONFORMANCE.md.

**Traps paid this phase (for CLAUDE.md's list; not added there — it is
user-owned):**
- `scripts/build_overlay.sh` requires `--symlink-install`, which runs a
  package's `setup.py` through a symlink: resolve its own directory with
  `realpath`, never `abspath`.
- NavFn's `makePlan` writes FREE_SPACE into the global costmap it shares
  with every other planner on planner_server, at each request's start
  cell, and the write persists.
- `ament_flake8` forks worker processes; forked after rclpy threads ran
  in the same pytest process, a worker deadlocked on a futex. Run the
  linters first.
- Destroying an rclpy node under a still-spinning executor segfaulted at
  exit: shut the executor down and JOIN its thread first.
- A scratch script named `inspect.py` shadowed the stdlib for every script
  in its directory (the CLAUDE.md scratch-dir trap, paid again).

**UNVERIFIED / not measured:** a real map-quality number (Lab 3, D-1);
any rate (one snapshot, one run each); M3 on its own world (an owner
decision); the mechanism of the 14 short Smac paths beyond post-hoc
consistency; NavFn's propagation in detail; the `lab_stack.launch.py
planner:=true` route live (tested structurally only).

**HUMAN DECISIONS REQUIRED:**
1. Phase 1D go-ahead.
2. Optional: a close replication of M3 on the frozen v1 world (world and
   map unchanged since `58b307e`, lidar moved), as its own experiment.
3. Carried: the Phase 0 public actions; `sudo apt install
   python3-hypothesis` for a bare `colcon test`.

NEXT MILESTONE: Phase 1D — the web app skeleton, measured
(`LAB_PHASES.md` §1D). Not started.
EXACT NEXT ACTION: In a fresh session on branch `lab1`, read this entry and
`docs/labs/BUNDLE_FORMAT.md` (1D's decoder must read 1.1's recording
arrays), then execute LAB_PHASES.md §1D.

## Phase 1D — the web app skeleton, measured (2026-09-30, in progress)

Plan: `docs/labs/PHASE_1D_PLAN.md` (APPROVED; committed in 1D-0 from the
planning session's plan store, verbatim below its header). The owner's
instruction for this session: run 1D-0 … 1D-8 in one sitting, with no
approval stops between blocks; do not touch `main`.

### 1D-0 — reconstruction, baseline and toolchain (2026-09-30)

**Repository state (verified):** branch `lab1` at `ca8ce79` ==
`jazzy2/lab1`. **Discrepancy:** the tree was not clean. An untracked
`AGENTS.md` (49,955 B, mtime 2026-09-30 01:02) is present; below its first
line it is byte-identical to `CLAUDE.md`. It is user-owned (LAB_PHASES
standing approvals), so it is left untracked and untouched, and it is
never committed by this phase.

**1C facts re-verified:**
- The three 1C bundles total **909,380 B** (`du -cb`). All three are `1.1`,
  gzip, `recorded-run`, `tool coco_lab_ros.lab_export`, with all 4 streams.
- There are **six** golden fixtures: five `1.0` glass-box (`astar_open`,
  `dijkstra_cost_field_gz` (the only gzip), `weighted_astar_greedy_trap`,
  `bfs_no_path`, `astar_turn_trap_heading` (heading_grid)), and
  `recorded_run_synthetic_1_1` (`1.1`, `missing ['cmd']`). **All six have
  `geo: null`**, not just the synthetic one; the teaching grids are unplaced.
- The mission `nav2_params.yaml` sha256 is `06c308af…`. No rosbag file is
  tracked.

**Baseline (measured, load 0.66–0.83, job-local overlay of this worktree,
the 1C routes):**

| suite | result |
|---|---|
| `coco_lab` pip route (plain venv, `env -i`, `-P`, 3 linters excluded) | **333 / 0 / 0** (33.09 s) |
| `coco_lab` colcon route, linters included | **336 / 0 / 0** (35.27 s) |
| `coco_lab_ros` | **69 / 0 / 0** (15.59 s) |
| `gazebo_models` (`--ignore=test_integration`) | **229 / 0 / 0** (11.76 s) |
| `custom_teleop` | **75 / 0 / 0** (1.37 s) |

All equal the 1C close.

**Toolchain (looked up 2026-09-30, not guessed):**

| tool | pinned | source / reason |
|---|---|---|
| Pyodide | **314.0.7** (2026-09-14) | GitHub releases API + npm `pyodide` time list. Pyodide now versions by CPython (314 = Python 3.14). 0.29.5 / 0.27.8 (2026-09-16) are maintenance releases of older lines; 315.0.0a2 is a prerelease. `pyodide-lock.json` on the CDN: Python **3.14.2**, emscripten 5.0.3, micropip **0.11.1**. CDN `cdn.jsdelivr.net/pyodide/v314.0.7/full/` answers 200 (`pyodide.asm.wasm` 9,598,218 B) |
| Node | **24.21.0** (`.nvmrc`) | nodejs.org `index.json`: newest LTS ("Krypton", 2026-09-07). The machine has Node **20.20.2**, which is EOL and below Vitest 5's engine range (`^22.12 \|\| ^24 \|\| >=26`). 24.21.0 is installed **job-locally** from the official tarball (sha256 checked against `SHASUMS256.txt`); the system Node is not touched |
| npm | **11.19.0** | bundled with Node 24.21.0 |
| vite | **8.3.1** | npm registry, latest |
| @vitejs/plugin-react | **6.1.1** | npm registry, latest |
| typescript | **7.0.2** | npm registry, latest (the native compiler; used only for `tsc --noEmit`) |
| react / react-dom | **19.3.0** | npm registry, latest; `@types/*` 19.3.0 |
| vitest | **5.0.2** | npm registry, latest |

**Pages and `main` CI (verified):**
- `GET /repos/GauthamCodes/coco-robot-jazzy-2.0/pages` → **404**. Pages is
  not enabled.
- `ci.yml` failed on the last 5 pushes to `main`, at "Build". **The cause is
  diagnosed from the job log** (run 36516234213, job 109239016703). The
  workflow's `colcon build --packages-select gazebo_models custom_teleop
  coco_config coco_moveit_config coco_web coco_rl coco_perception
  coco_mission` omits **`coco_sim`**, on which `gazebo_models` has depended
  since the episode work. colcon fails with `Failed to find …
  install/coco_sim/share/coco_sim/package.ps1 … Check that the following
  packages have been built: coco_sim`. The failure predates 1D and is not
  caused by it. Per the owner's instruction it is **documented, not fixed**,
  in this phase.

NEXT: 1D-1, the Python tools (expectations, invalid corpus, JSON corpus,
catalog).

### 1D-1 — the Python tools (2026-09-30)

- `lab_web/` (with `COLCON_IGNORE`) gained `tools/`:
  - `make_expectations.py` writes `test/golden/expected.json` (all nine
    decoder bundles) plus the two corpora. `--check` regenerates the
    outputs into a temporary directory and compares them byte for byte.
  - `invalid_corpus.py` writes 48 tampered bundles and `index.json`, each
    with its TypeScript error code and Python's verdict. Two cases are
    `semantic` (only coco_lab can refuse them), one is TS-stricter
    (`duplicate_key`), and one more (`oversize_manifest`) is generated by
    each test suite.
  - `json_corpus.py` writes 1,218 seeded JSON texts (1,217 with a
    canonical form, plus `1e400`, which Python refuses to serialise), with
    Python's `canonical_json` and sha256, and 4,000 float `repr`s.
  - `build_catalog.py` builds the site data. `test_tools.py` holds the
    tests, including the no-search guard.
- The display rule is written down once, as the Python oracle in
  `tools/common.py`: max over events before k of push/relax = open,
  expand = closed, path = path.
- Two defects in my own generator were found by its tests and fixed:
  - an `int` leaked into the float list;
  - the NaN case inserted a trailing comma into an empty `meta`.

### 1D-2 / 1D-3 — the skeleton and the decoder (2026-09-30)

- Vite 8.3.1, TypeScript 7.0.2, React 19.3.0 and Vitest 5.0.2, exact pins
  with a committed lockfile; `.nvmrc` 24.21.0.
- `site.config.ts` holds the base path and the Pyodide pin, each written
  once. The CSP allows only `self` and the pinned CDN directory.
- `src/bundle/` has seven parts:
  - a lossless JSON parser;
  - Python float `repr`;
  - Python canonical JSON;
  - WebCrypto SHA-256;
  - a bounded gunzip with a magic-byte check;
  - unaligned little-endian array copies, with a forced `DataView` path;
  - a port of `bundle.py`'s structural checks, in Python's order.
- **Gate met (measured):**
  - all nine bundles agree exactly, per array, with the content hash and
    map hash recomputed in TS;
  - all 1,217 canonical cases and 4,000 reprs agree;
  - every structural invalid case is refused with its named code;
  - the two semantic cases decode and are then refused by the catalog gate.
- The first vitest run of the decoder passed with no fix needed. Commits
  `c021f35` (skeleton), `00aeefa` (decoder).

### 1D-4 / 1D-5 — the player, the overlays and Pyodide (2026-09-30)

- Player and renderer:
  - cursor (forward incremental, backward recompute), hover with stored
    g/h/f per sub, coordinates from `LabMap`;
  - Okabe–Ito palette; pure RGBA layer builders, pinned by snapshot;
  - recorded-run overlays, placed only with geo and a matching frame;
  - mode badge, player (Space, arrows, Shift ×100, scrub, speed, reduced
    motion), and summary, provenance, recording and hover panels.
- The Pyodide worker:
  - is created on the first edit and never before;
  - installs coco_lab from the site's wheel after a sha256 check;
  - runs `recompute.py` (glue: `load_bundle`, `search`, `write_bundle`);
  - returns a glass-box bundle with `tool` `lab_web/pyodide`, decoded by
    the same decoder.
- **Found and fixed (measured):**
  1. `vite dev` and `vite preview` serve `*.gz` with
     `Content-Encoding: gzip`. The browser would inflate `arrays.bin.gz`
     first, and the decoder refuses a file without the gzip magic (it
     never repairs). Fixed at the SERVER: a Vite middleware serves `.gz`
     as plain `application/gzip` bytes, byte-identical to the committed
     file (`cmp`). How GitHub Pages serves them is unverified until Pages
     is enabled.
  2. Play started from the end of a trace stopped at once. The first frame
     read a stale position ref. It is fixed; this also explains the first
     phone "tap does nothing" reading.
  3. A harness bug (speed 5000 is not an option) made playback look stalled.
     The app now ignores a non-positive speed.
  4. **Warm edit 1,943–1,975 ms → 1,391–1,429 ms.** The glue copied the
     JS `Uint8Array` into Python with `bytes(proxy)`, element by element:
     `load_bundle` took ~805 ms in Pyodide against 76 ms in CPython. It
     now uses `to_bytes()` (one memcpy), and load fell to ~270 ms. This is
     a defect fix in the glue, not one of the plan's scope options.
  5. The glue's fixed `/tmp/lab_N` directories were not cleaned after a
     refused edit. It now uses `tempfile.mkdtemp` with cleanup in `finally`.
  6. After an edit the picker still named the catalog bundle. It now says
     "Your edit of … — computed in your browser by coco_lab".
- micropip 0.11.1 accepted coco_lab's wheel with its `.data/` directory
  (the ament marker and `package.xml`) as it is. The plan's
  packaging-change stop did not arise.

### 1D-6 — measurements (2026-09-30, headless Firefox 156, load 0.5–1.0)

See `docs/RESULTS.md` "COCO Lab Phase 1D" and `docs/data/lab1d/`.
- Full-arena Dijkstra (283,378 events): **60.07 fps**, 0 dropped frames.
- Warm edit: **1,405–1,421 ms**.
- Cold first edit: 13,453 ms.
- Initial page weight: 100,573 B.
- Phone width: no horizontal scroll.
- No third-party request before the first edit, and afterwards only the
  pinned Pyodide directory. No cookies or storage.
- Two builds give an identical `dist` tree hash.

### 1D-7 — CI (2026-09-30)

- `.github/workflows/lab.yml` sits beside `ci.yml`, which is untouched. It
  has three jobs:
  - `coco-lab-venv`: coco_lab in a plain venv, with a floor of 333 tests and
    no skips;
  - `lab-web`: tools with a floor of 58, the catalog and wheel, `npm ci` on
    the `.nvmrc` Node, typecheck, vitest, two builds compared by hash, dist
    checks, and the Pages artifact;
  - `deploy`: a push to `main` only.
- The first run (36661285245) was red in `coco-lab-venv`: 332 passed and 1
  failed. `test_setup_py_runs_through_a_symlink` executes `setup.py`, and a
  Python 3.12 venv has no setuptools. The local plain venv has setuptools
  84.0.0, which CI now pins. `lab-web` was green on the first run.

### 1D-8 — regression, documentation, checkpoint (2026-09-30)

- **Final regression (measured, fresh job-local overlay, load 0.95):**
  - `coco_lab` pip **333 / 0 / 0**, colcon **336 / 0 / 0**;
  - `coco_lab_ros` **69 / 0 / 0**; `gazebo_models` **229 / 0 / 0**;
    `custom_teleop` **75 / 0 / 0**, all equal to 1D-0;
  - `lab_web/tools` **58 / 0 / 0**; vitest **142 passed**.
- CI `lab.yml` run 36661469461 is **green on `lab1`** (Node v24.21.0 / npm
  11.19.0, as local). `deploy` was skipped because it runs only on `main`.
- **Invariants:**
  - mission `nav2_params.yaml` sha256 is `06c308af…`;
  - `git diff ca8ce79` is empty for every ROS / coco_lab package directory,
    the golden fixtures and the 1C bundles;
  - no rosbag is tracked, and the largest new file is
    `lab_web/test/golden/json_corpus.json` (509,781 B);
  - `AGENTS.md` is still untracked and untouched.
- **Documentation:**
  - new: `lab_web/README.md`;
  - additive: a "Readers" section in `docs/labs/BUNDLE_FORMAT.md` (the
    doc-pinning test still passes);
  - updated: `HOW_TO_RUN.md` (the `lab_web` section), `PROJECT_STATE.md`
    (the 1D and deployment rows) and `docs/RESULTS.md` ("COCO Lab
    Phase 1D").

## Phase 1D — IMPLEMENTATION COMPLETE; deployment awaits the owner (2026-09-30)

Against `PHASE_1D_PLAN.md` §L:

| # | criterion | status |
|---|---|---|
| 1 | `COLCON_IGNORE`; `colcon list` excludes `lab_web` | **met**: 11 packages, no `lab_web` |
| 2 | exact pins, lockfile, `npm ci && npm run build`, identical `dist` twice | **met**: locally and in CI |
| 3 | TS decodes the six golden fixtures and the three 1C bundles; every array's sha256 equals Python's; content and map hashes recomputed | **met** |
| 4 | the invalid corpus is refused by Python and by TS with a matching class | **met**. 48 cases plus 1 generated; the semantic cases are refused by the catalog gate; one TS-stricter case is listed |
| 5 | ≥ 1,000 canonical-JSON cases byte- and hash-equal | **met**: 1,217, plus 4,000 reprs |
| 6 | golden-bundle tests unmodified; package counts equal 1D-0, 0 failed, 0 skipped | **met** |
| 7 | the guard finds no search in `lab_web/src`; every trace comes from coco_lab | **met** |
| 8 | cursor checkpoints and hover equal Python; backward = forward; plan-point orientation for all three 1C runs | **met** |
| 9 | play, pause, step, scrub, speed, Space and arrows, hover g/h/f; Okabe–Ito; reduced motion verified in the harness | **met** |
| 10 | gt/amcl/plan drawn for the three 1C runs; the synthetic fixture shows "no geo — cannot place" and "cmd: not captured" | **met**. The synthetic case is verified at the overlay and data layer (vitest); the fixture is deliberately not in the public catalog (plan §G) |
| 11 | a ModeBadge in every state, its text from `source_kind` | **met**: 10 of 10 catalog bundles, plus edits |
| 12 | a worker edit gives a `glass-box` / `lab_web/pyodide` bundle, same decoder, played; no Pyodide before the first edit | **met** |
| 13 | fps, warm edit, cold load, page weight in RESULTS | **met**. 60.07 fps (at the 60 Hz refresh cap); warm edit 1,405–1,421 ms (the target was missed at first, 1,943–1,975 ms, then met by fixing a glue defect; ~80 ms margin); cold 13,453 ms; 100,573 B |
| 14 | 390 px replay: no horizontal scroll, clickable, screenshot committed | **met**: `docs/data/lab1d/phone_390x844_*.png` |
| 15 | no third-party request except the Pyodide CDN; no cookies | **met** |
| 16 | `lab.yml` green on `lab1`; `deploy` green on `main`; the public URL at phone width | **half**. Green on `lab1`. `deploy` / the public URL: **BLOCKED on owner actions** |
| 17 | SESSION_LOG entry; docs updated; nav2 sha unchanged | **met** |

Per plan §M, **1D implementation is done** (criteria 1–15 and `lab.yml`
green on `lab1`). **1D is CLOSED only at criterion 16**, which needs two
owner actions:
1. **Enable GitHub Pages**: Settings → Pages → Build and deployment →
   Source: **GitHub Actions**. The API returned 404 on 2026-09-30.
2. **Rule on `main`.** The standing approval allows a fast-forward of
   `main` from `lab1` only with every test green. The ROS `ci.yml` has been
   red on `main` for 5 pushes, for a pre-existing, now diagnosed reason
   (`coco_sim` is missing from its `--packages-select`; 1D neither caused
   nor touched it). This session did not push `main`, per the owner's 1D
   instruction.

Once both are done, `lab.yml`'s `deploy` job publishes
`https://gauthamcodes.github.io/coco-robot-jazzy-2.0/`. That URL is not
verified, and is not written anywhere as working.

**Commits this phase:**
- `780c7a0` (1D-0);
- `26e5792` (1D-1);
- `c021f35` (1D-2);
- `00aeefa` (1D-3);
- `fe087b6` (1D-4/5);
- `1d31fca` (1D-6);
- `a2db3b1` and `80510e1` (1D-7);
- the closeout commit carrying this entry.

**Traps paid this phase (not added to CLAUDE.md, which is user-owned):**
- Vite's static server sends `.gz` with `Content-Encoding: gzip`. A
  gzip-checking decoder then sees raw bytes.
- In Pyodide, `bytes(js_uint8array_proxy)` copies element by element (a
  3.5 MB bundle took ~800 ms). Use `proxy.to_bytes()`.
- A Python 3.12 venv has no setuptools. `test_setup_py_runs_through_a_symlink`
  needs it, so a bare CI venv fails 1 of 333.
- React: a playback loop that seeks and then reads a ref on the next
  animation frame reads the pre-render value. Update the ref inside the
  seek.
- This worktree's sandbox refuses compound shell commands that name git,
  `source` or `env -i` with variables. Put the steps in a script file.

**UNVERIFIED / not measured:**
- the public site and how Pages serves `.gz`;
- a headed browser, a real phone, Safari and Chrome (all numbers are
  headless Firefox 156);
- warm-edit timing on any other machine (the margin is ~80 ms);
- decoding far beyond 14.1 MB raw.

**HUMAN DECISIONS REQUIRED:**
1. Enable Pages (Source: GitHub Actions).
2. Decide whether the pre-existing `ci.yml` red blocks the `lab1` → `main`
   fast-forward. The fix is one word, adding `coco_sim` to its
   `--packages-select`, but it was left for the owner as out of 1D's scope.
3. Carried from 1C: the Phase 0 public actions; `sudo apt install
   python3-hypothesis` for a bare `colcon test`.

NEXT MILESTONE: close 1D (deploy and verify the public URL at phone width),
then **Phase 1E — Lab 1's content** (`LAB_PHASES.md` §1E). 1E has not
started.
EXACT NEXT ACTION: after the owner's two actions, fast-forward `main` to
`lab1` (no force). Watch `lab.yml`'s `deploy`, then run
`python3 lab_web/tools/browser/check.py https://gauthamcodes.github.io/coco-robot-jazzy-2.0/ out/ smoke phone weight`
and record the result.

---

## PHASE 1 — COMPLETE (2026-09-30)

This is the final Phase 1 entry. No further Phase 1 milestone exists.
1D is closed with this entry, and no 1E, 1F or other subdivision was
created. `LAB_PHASES.md` §1E was not undertaken inside Phase 1, by the
owner's closure instruction.

**What Phase 1 delivered**

| part | what |
|---|---|
| Pathfinding | `coco_lab` (1A): graph and grid, four heuristics, and five algorithms (A\*, Dijkstra, Weighted A\*, BFS, Greedy best-first) with trace schema v1. ROS-free, standard library only |
| Maps | Map schema v1, Nav2 saved-map import and nine teaching fixtures (1B) |
| Bundles | Bundle format 1.0 (1B) and 1.1 with recorded-run streams (1C). Six golden fixtures |
| ISRO | The investigation: "4 %" is waypoint count; not reproduced on fixed inputs (1B) |
| Real Nav2 | `coco_lab_ros` (1C). Smac 2D's raw A\* cost equals coco_lab's C1 on 36 / 36 comparable pairs. The robot moves only via `FollowPath` |
| Real runs | Three recorded runs to (0.5, 6.0): A\* and Dijkstra succeeded, greedy failed `FAILED_TO_MAKE_PROGRESS` (1C) |
| Browser | `lab_web` (1D): a TypeScript decoder exactly equal to `bundle.py`, the trace player, recorded-run overlays and mode badges |
| Pyodide | A lazily started worker reruns `coco_lab` itself on an edit (1D) |
| Deployment | GitHub Pages, from `lab.yml`'s `deploy` on `main` (this entry) |

**This session**

1. **Verified the starting state** (measured): `lab1` = `jazzy2/lab1` =
   `ef94b5a`, and `jazzy2/main` = `6853517`, an ancestor 18 commits
   behind. The Pages API returned `build_type: workflow` and the URL.
   `AGENTS.md` was untracked; it was not touched.
2. **Diagnosed main's red `ci.yml` from its logs, not from memory.** 1D
   had called it a one-word fix (add `coco_sim`); **that diagnosis was
   incomplete**. There were three layers:
   - Build: `coco_sim` was missing (run 36516234213).
   - Collection: `mujoco` was missing, so coco_rl exited 2 (run
     33418188446).
   - Tests: 22 failures and 9 errors, from missing `nav2_bringup` and
     `ros_gz_sim`. This only appeared once the first two were fixed (PR
     run 36670100628).

   Two commits fixed it:
   - `b1e9f85` added `coco_sim` to both package lists and
     `mujoco==3.11.0`, coco_sim's own pin;
   - `59af2f6` added `ros-jazzy-nav2-bringup` and `ros-jazzy-ros-gz-sim`,
     both existing `gazebo_models` exec_depends.

   No test, floor or package was removed.
3. **Local equivalent of the CI** (measured; fresh job-local overlay;
   the workflow's package lists and guard): 9 / 9 built, 1059 tests,
   0 failures, 7 skipped. All 7 skips are `test_pick_poses`, which needs
   `moveit_msgs`: not on this machine's path, but apt-installed on the
   runner, where all 7 ran.
4. **Final regression** (measured, load 0.7–1.4). Every count equals 1D-8:
   - coco_lab pip 333 / 0 / 0, colcon 336 / 0 / 0;
   - coco_lab_ros 69 / 0 / 0;
   - gazebo_models 229 / 0 / 0;
   - custom_teleop 75 / 0 / 0;
   - lab_web/tools 58 / 0 / 0;
   - vitest 142; typecheck clean;
   - two builds identical (`5f6a6489…`).
5. **Gate.** PR #1 `lab1` → `main`: `CI` passed (run 36670545174: 1059
   tests, 0 failures, 0 errors, **0 skipped**), and `Lab` passed.
6. **Fast-forwarded `main`**: `git push jazzy2 59af2f6:main`,
   `6853517..59af2f6`, no force and no merge commit. `jazzy2/main` was
   re-checked just before. PR #1 then read MERGED.
   - This also made public the Phase 0 checkpoint `9ee4a52`, which the
     PHASE 0 entry recorded as "local only". It is an ancestor of `lab1`.
   - The local `main` branch (`9ee4a52`, checked out in the owner's
     primary checkout) was not touched.
7. **Deployed** (measured):
   - `CI` on `main` succeeded (run 36671154026);
   - `Lab` on `main` succeeded, **including `deploy`** (run 36671154008);
   - GitHub lists a `github-pages` deployment of `59af2f6`.
8. **Verified the public site** (measured, headless Firefox 156 against
   the URL itself; RESULTS "COCO Lab Phase 1 — closure"):
   - all 10 catalog bundles (7 of format 1.0, 3 of format 1.1) decode and
     draw with the right badge;
   - 0 console errors, no cookie, no storage;
   - player, reduced motion and phone 390 × 844 pass;
   - no Pyodide request before the first edit, and only the pinned CDN
     after it;
   - `arrays.bin.gz` is served as `application/gzip` with no
     `Content-Encoding`, byte-identical to the build.

   Timings came from two samples:
   - at load ~30, from another session's live COCO mission sweep: warm
     edit 3,871–4,395 ms, a **miss**;
   - at 1-minute load ~2: warm edit 1,412 / 1,468 / 1,493 ms, **met,
     with a 7 ms margin**. Playback was 59.94 fps at the 60 Hz cap.

**Final commit**
- The deployed and verified Phase 1 state is **`59af2f6`**.
- The closeout commit carrying this entry changes documents and
  `docs/data/lab1d/live/` only. `main` and `lab1` are both fast-forwarded
  to it; its SHA is in `git log` and the final report.

**Public URL:** <https://gauthamcodes.github.io/coco-robot-jazzy-2.0/>

**Remaining limitations (factual)**
- The warm-edit target holds on the public site only narrowly (7 ms at
  load ~2), and fails under heavy load. It is not measured on an idle
  machine or on any other machine.
- Every browser number is headless Firefox 156 on this machine. A headed
  browser, a real phone, Safari and Chrome are not measured.
- Three real runs are not a rate. M3's 6.2 % was neither reproduced nor
  refuted (1C). Map quality is not measured (moved to Lab 3).
- A bare `colcon test` of `coco_lab` locally still needs
  `python3-hypothesis` (1C).
- Phase 0's public actions (archive tags, name, video migration) are
  still the owner's.

**Traps paid this session**
- A `until grep -q PATTERN` waiter matched the text of its own command
  line, which `pgrep -af` had printed into the same output file. The
  p03c waiter trap, again: anchor the pattern (`^check.py exit`).
- A diagnosis written as "the fix is one word" had not been run. Adding
  `coco_sim` exposed the next two layers. CI fixes are only known once CI
  has run them.

**Phase 2 has NOT started.**

NEXT MAJOR PHASE: Phase 2, not started.
- The owner's closure instruction names it "SLAM Lab".
- `docs/ROADMAP.md` names Phase 2 **"Localise"** (Lab 2: MCL against EKF,
  kidnap recovery), and places the slam_toolbox map of the arena in Lab 3.
- The two names disagree. The owner decides which is Phase 2 before it
  starts; this entry does not.
- *(Resolved later on 2026-09-30 by the plan revision: Phase 2 is **Live**;
  SLAM is Phase 4, Map; Localise is Phase 3. See the next entry.)*
EXACT NEXT ACTION: none inside Phase 1. Open a fresh session for Phase 2
only when the owner asks.

---

## Plan revision — Phase 2 · Live added (2026-09-30)

Docs only; no code, config, launch, world or test changes. Owner-approved
as a revision on top of the closed Phases 0 and 1: the original
installation prompt assumed Phase 0 had not started, and Phase 0 had in
fact already installed the first COCO Lab plan (Milestone 0B, `b55f24f`).

**Source files** (`~/Downloads`, copied from, never moved or edited):
- `ROADMAP.md`: 27,191 B, 2026-09-30 11:41:25, sha256 `ed79b83b…c11c4e3`.
- `LAB_PHASES.md`: 24,430 B, 2026-09-30 11:41:16, sha256 `eb223591…c5656`.
- Diffed against `main` (`e5ad135`), they differ only by the Live delta,
  so nothing added to either doc during Phases 0–1 was lost.

**Installed:**
- `main`'s `docs/ROADMAP.md`, unchanged, is archived as
  `docs/history/ROADMAP_LAB_2026-09-28.md` (`ROADMAP_COCO2.md` untouched).
- The Live delta was patched onto `docs/ROADMAP.md` and
  `docs/LAB_PHASES.md`:
  - Phase 2 · Live, and the renumbering: Localise 3, Map 4, Search 5,
    Move 6;
  - §3.5 "The live robot";
  - invariant 9, live control;
  - addendum rule 10;
  - the 1D "leave room for Live" note;
  - the 1F next-step line.
- **One delta hunk was left out:** a new STEP 0 reading item inside the
  closed Phase 0 prompt ("which coco.v1 intents exist today …; Phase 2
  (Live) reuses them"). It was not in the approved list.

**Facts checked against `main`** (all hold): the coco.v1 intents
- `set_mode` with `teleop`/`auto`/`stop`;
- `drive`;
- `nav_goal` `{x, y}` only;
- `select_target`;
- `mission` `start`/`abort`;
- `stop`;

and these:
- `safety.PUBLISH_ALLOWLIST`;
- the server's `/model/coco/odometry` subscription;
- MJPEG at `/video/<alias>`;
- `session.py`'s "SINGLE USER / SINGLE SESSION";
- the 1C `FollowPath` hook;
- 1,966 tests;
- `b15d445` and `p03c-consolidation` are ancestors of `main`;
- M3 3.165 m vs 3.373 m.

**Fact corrected:** in §3.5, the mission is told its lane by
`resolve_lane()`, which uses the episode's region map, or exactly
`lane_for_colour()` without one. The downloaded text named only
`lane_for_colour()`.

**Phase 1 recorded as it ran:**
- In `LAB_PHASES.md`, each block heading is annotated:
  - 1A–1D DONE;
  - 1E SKIPPED;
  - 1F PARTIAL;
  - 1G NOT RUN.
- The ROADMAP status line reads "plan revised (Phase 2 · Live added).
  Phase 0 closed. Phase 1 closed by decision with open items: … Phase 2
  not started."
- Every undelivered 1E and 1F must-have is listed under **"Lab 1.1"** in
  ROADMAP §5.
- **Rule 9** is written beside the phases table: Phase 2 (Live, not a lab)
  is not blocked; Lab 2 (Phase 3) is blocked until Lab 1 has its video and
  `LAB1_PLAN.md`.

**Master context:** `~/Downloads/COCO2_MASTER_CONTEXT.md` does not exist.
- The CLAUDE.md addendum now says the master context lives outside the
  repository.
- The §45 banner was skipped.
- **The path remains UNRESOLVED**, as recorded in Phase 0.

**Other docs:**
- CLAUDE.md:
  - rule 10 added;
  - the master-context sentence reworded, which is the only non-additive
    change, and was owner-approved.
- AGENTS.md got the identical edits; it is still **untracked**.
- "Superseded by docs/ROADMAP.md on 2026-09-30" banners were added at the
  top of `docs/FUTURE_WORK.md`, `docs/M7_DESIGN.md` and
  `docs/M7_PHASES.md`; the items themselves are unedited.
- PROJECT_STATE's header and Next row now say Phase 2 = Live and list
  Lab 1's open items.
- The PHASE 1 — COMPLETE entry's "SLAM Lab vs Localise" note is marked
  resolved: **Phase 2 is Live; SLAM is Phase 4 (Map).**

**Flagged, not changed:**
- `lab_web/README.md:122` says `sketch` is "reserved for Phase 2"; under
  the revised plan Sketch arrives in Phase 3.
- `docs/labs/PHASE_1D_PLAN.md` says the same; it is an approved-plan
  record.
- PROJECT_STATE's COCO 2.0 "## NO NEXT MILESTONE" heading sits in the
  section the file marks as history.
- `LAB_PHASES.md` keeps its "Before Phase 0" and Phase 0 blocks
  unadapted, as history.

**Phase 2 has NOT started.**

NEXT: the owner writes the Phase 2 (Live) prompt from `docs/ROADMAP.md`
§3.5 and §6. Before Lab 2 (Phase 3), Lab 1 needs its video and
`docs/labs/LAB1_PLAN.md` (ROADMAP §5, "Lab 1.1").

---

## Lab 1.1 — Part A: make it a lab (2026-10-01)

Precondition met: the plan revision is at `ee8aace` (`lab1` = `main`).
Scope as directed:
- the break-the-planner challenge, beat-the-planner, stars and the daily
  seed moved to a new **"Lab 1.2"** list in ROADMAP §5;
- no sixth algorithm.

**Built**
- The settings panel (1E.1).
- The map ladder with COCO's footprint swept along the path (1E.2).
- Race mode (1E.3).
- Brush painting and erasing, with start and goal protected (1E.5).

Details are in `docs/RESULTS.md`, "COCO Lab 1.1, Part A", and in the Lab 1.1
list in ROADMAP §5, where these four are marked done.

**New in `coco_lab`**
- `search.suboptimality_bound`.
- Property 8 (the bound the UI shows holds, for every algorithm and
  heuristic, on 1,000 maps).
- A w = 1 ≡ A\* property (`test_weight_one_reproduces_astar`).
- `test_bound.py`.

The page shows only verdicts `coco_lab` computed at site build time (catalog
1.1 `settings`).

**Decisions taken here, stated, cheap to change**
1. **The footprint** is the rectangle enclosing the chassis and wheels,
   0.297 m × 0.314 m (derived from `coco_config/robot.py`).
   - `coco_config` has no footprint or robot-radius constant.
   - Nav2's `robot_radius` (0.20 m global, 0.25 m local) is a costmap
     parameter, not a robot dimension, and was not used.
2. **The weight slider** moves in 0.25 steps, so that every bound shown is
   one `coco_lab` computed.
3. **The costmap rung** is the 1C A\* run's recorded global costmap,
   downsampled ×2 by `coco_lab`, so its edits run at the edit map's 0.10 m.
4. **Settings and races** apply to grid bundles. The heading exhibit keeps
   its recorded settings (and can be painted); recorded runs stay
   read-only.
5. **Painting reruns the shown bundle's own settings.** "Run" applies the
   panel's settings; a race uses them for every entrant.

**Measured** (local production build, headless Firefox 156, load 1.0–1.7)
- Tests, all 0 failed, 0 skipped:
  - `coco_lab` pip 349, colcon 352;
  - `coco_lab_ros` 69, `gazebo_models` 229, `custom_teleop` 75;
  - `lab_web/tools` 69; vitest 157;
  - builds identical (`19df8d0f…`).
- Warm paint → first frame: **1,158 / 1,172 / 1,159 ms** (target ≤ 1.5 s;
  1D 1,405–1,421).
- Playback: **59.96 fps**, 0 frames over 25 ms; 10k events/frame 59.87.
  An interleaved A/B against the 1D build on the same machine cannot tell
  them apart.
- Phone: 378 ≤ 390. Weight: 107,321 B. Smoke: 11 of 11, 0 console errors.

**Found and fixed** (each measured, then fixed)
1. The player stole the arrow keys from every range input, so the weight
   slider could not be moved by keyboard.
2. The swept footprint, rendered lazily inside a playback frame, dropped
   1–2 frames per full-arena playback. Memoising the panels did not help;
   turning the sweep off did. It is now pre-rendered outside the frame
   loop.
3. An unbreakable citation widened the page to 401 px at phone width.

**Unverified**
- Race timing on the 0.10 m arena.

(Added after the fast-forward of `main` to `dfa388e`: the public site with
Part A was measured. Warm paint 1,165 / 1,169 / 1,165 ms; playback 60.02
fps; phone 378; smoke 11 of 11; `lab` scenario passed. See RESULTS
"COCO Lab 1.1, Part A". `lab.yml` first failed on `d7e176b`: the new glue
test wrote a `.pyc` into `src/` whose embedded runner path held the repo
name. It was fixed in `dfa388e` with `sys.dont_write_bytecode`, and the
site test was left unchanged.)
- A headed browser, a real phone, Safari and Chrome.

**Traps paid this session**
- `pgrep -f "gz sim"` in a compound shell matched the shell's own command
  line, and reported a simulator that did not exist. Check `ps` instead.
- A `-k` pytest filter plus an explicit file path silently widened the
  collection. Run a new file alone.
- WebDriver key presses sent right after a `<select>` change can reach a
  control React has not yet re-enabled. Wait for the control's `disabled`
  to clear.

NEXT: Part B (LAB_PHASES Lab 1.1 prompt, items 6–9) on "continue". Phase 2
(Live) has not started.

---

## Lab 1.1 — Part B: make it teach (2026-10-01)

Continued on the owner's "continue", from `main` = `lab1` = `3b4be8f`.

**Built** (details in `docs/RESULTS.md`, "COCO Lab 1.1, Part B"; ROADMAP §5
Lab 1.1 now marks 1E.4, 1E.6, 1E.8 and 1E.9 done)
- **Predict-then-reveal**, before a race and before a settings run.
- **Share links**, format v1. Opening one reruns coco_lab and compares the
  trace digest. The round trip is tested in CI in both languages, through
  committed vectors (`test/golden/share_vectors.json`).
- **The tracking-error plot and provenance** on the 1C replays. The series
  is recomputed by 1C's code at site build, and refused unless it
  reproduces the recorded statistics exactly.
- **The exhibit, "The A\* myth, twice":** (a) live; (b) from 1C's record;
  (c) from 1B's, labelled a reconstruction. A test checks that every test
  the page cites exists.

**Reported, not filled in**
- 1C's analogue recorded path lengths, not path coordinates, so exhibit (b)
  draws no paths.
- M3's 6.2 % was never re-run. The exhibit says "neither reproduced nor
  refuted".
- Share links carry no seed, because no Lab 1 input is random (the daily
  seed is Lab 1.2).

**Measured** (local build, headless Firefox 156, load 0.3–0.9)
- Tests, all 0 failed, 0 skipped:
  - `coco_lab` 349 / 352, unchanged;
  - `coco_lab_ros` 69, `gazebo_models` 229, `custom_teleop` 75;
  - `lab_web/tools` 72; vitest 180;
  - builds identical (`88a148b5…`).
- Share links:
  - a link made from a painted, re-set view, opened in a fresh browser,
    reproduced the exact trace;
  - so did both committed CI vectors, which means CPython's and Pyodide's
    digests agree;
  - 3.6–3.8 s from open to verdict.
- Budgets: playback 60.01 fps with 0 frames over 25 ms; warm paint
  1,134–1,145 ms; phone 378; smoke 11 of 11; weight 115,555 B (+8,234 B on
  Part A).
- 0 console errors in all eleven scenarios.

**Found and fixed during Part B**
- The plot's hover readout covered the top y-axis label. It now has a
  reserved line above the plot.
- The dataviz palette check **failed** the site's dark accent as a series
  colour (lightness 0.735 on the dark surface). The chart uses `#3A96CF`
  in dark mode instead, which passes.
- The harness's new scenarios first waited for readiness marks that only
  exist with `?perf`. That was a harness bug, fixed in the harness.

**Unverified**
- A headed browser, a real phone, Safari and Chrome.

(Added after the fast-forward of `main` to `aa0935a`, deployed: Part B on
the public site, load 0.23–0.69. Every share link reproduced its trace
exactly, in 4.7–5.7 s. Playback 60.03 fps; warm paint 1,137–1,159 ms;
phone 378; smoke 11 of 11; 0 console errors. See RESULTS
"COCO Lab 1.1, Part B".)

NEXT: Part C (items 10–16: LAB1_PLAN.md, README, the three stale spots,
the demo video, the tag and the draft release, the owner's phone check,
and the closing status) on "continue". Phase 2 (Live) has not started.

---

## Lab 1.1 — Part C: ship it; LAB 1.1 COMPLETE (2026-10-01)

Done on the owner's "continue", then on their reply of 2026-10-01. The
reply had three parts:
- the phone check;
- approval to publish;
- an instruction to move COCO Lab to its own repository, named "coco
  labs", and to return `coco-robot-jazzy-2.0` to its state before COCO Lab.

**Delivered** (details in `docs/RESULTS.md`, "COCO Lab 1.1, Part C")
- **10.** `docs/labs/LAB1_PLAN.md`. Every cited test name is verified to
  exist. Earlier-phase numbers carry their phase and date.
- **11.** README: "Try it" at the very top, a short Lab 1 section, and the
  6.2 % paragraph linked to the exhibit. `?view=exhibit` opens it.
- **12.** The three stale spots: Sketch is Phase 3 in `lab_web/README` and
  `PHASE_1D_PLAN`, and PROJECT_STATE points to the current plan under
  "NO NEXT MILESTONE".
- **13.** The demo video: 65.3 s, viewport only, recorded by
  `lab_web/tools/browser/record_demo.py`. The probe frame was taken first;
  the probes and frames were deleted. It is not in git; a copy is in
  `~/Videos/coco_lab1_demo.mp4`.
- **14.** `lab1-v1.0` was **published with the owner's approval** on
  `GauthamCodes/coco-labs`.
- **15. The owner's phone check, as reported:** Nothing Phone (1), Chrome.
  The page loaded and the trace played; the share link showed "This link
  reproduced the exact trace".
- **16.** The ROADMAP status line, the Lab 1.1 list (every item delivered)
  and the rule 9 note (satisfied); LAB_PHASES 1E and 1F marked DONE; 1G's
  stale "precondition never met" corrected; PROJECT_STATE's header and Next
  row; this entry.

**The move to `GauthamCodes/coco-labs`** (created public; Pages set to
GitHub Actions; default branch `main`)
- `main` and `lab1` were pushed with their history; local remote `labs`.
- Every live reference to the repository was renamed (commit `bd77ed9`).
  The evidence and history keep the URL they were measured at, with dated
  notes.
- On the new repo, `CI` and `Lab` passed and `deploy` published the site
  at <https://gauthamcodes.github.io/coco-labs/>. Headless Firefox measured
  it at 11 of 11 bundles, 59.95 fps, warm paint 1,170–1,195 ms and phone
  378. A share link made there, and both CI vectors, reproduced exactly.
- The demo video was **re-recorded from the new URL** before publishing.
  The approved cut ended on the old URL; the new one is the same tour,
  65.3 s.
- On the old repository, the unpublished draft release was deleted; no
  `lab1-v1.0` tag was ever pushed there.

**Measured:** in RESULTS "COCO Lab 1.1, Part C". Tests on the release
commit, unchanged since Part B: `coco_lab` 349 / 352; `lab_web/tools` 72;
vitest 180; 0 failed, 0 skipped.

**NOT done, and why: resetting `GauthamCodes/coco-robot-jazzy-2.0`.** The
owner asked to return it to "the state it used to be in … when I tried to
integrate Isaac Sim". That rewrites a public repository's `main`, and the
history admits more than one reading:
- `b15d445` (2026-09-24): `main` during the Isaac work.
- `442bca0` (2026-09-29): after the P03C merge and Milestone 0A, both of
  which landed as COCO Lab's Phase 0.

It also leaves three things to decide: the old repo's `lab1` branch, its
Pages site, and whether to force-push or add a restoring commit. The owner
was asked; nothing on the old repository was changed except deleting its
unpublished draft.

LAB 1 IS COMPLETE AND RELEASED. Lab 1.2 (challenge, beat-the-planner,
stars, daily seed) is deferred. **Phase 2 (Live) has not started.**

NEXT: the owner's answer on the old repository. Then Phase 2 (Live), only
when the owner asks. Its prompt is to be written from `docs/ROADMAP.md`
§3.5 and §6.

## Old repository restored; COCO Lab gets its own workspace (2026-10-01)

Done on the owner's answers of 2026-10-01 to the four questions above:
- restore target `b15d445`, as one restoring commit, not a force-push;
- delete the old `lab1` and turn off the old Pages, keeping `archive/*`
  tags;
- a dedicated colcon workspace at `~/coco_labs_ws/src/coco-labs`;
- then build, test and launch there, and stop.

**The old repository, `GauthamCodes/coco-robot-jazzy-2.0`**
- **Backup first.** A mirror of every ref was bundled to
  `~/coco-robot-jazzy-2.0-backup-20261001.bundle` (27,079,954 B, sha256
  `8aadf89b…5628e134`). `git bundle verify` reports it complete. The bundle
  holds 15 refs (14 branches and `refs/pull/1/head`), listed in
  `~/coco-robot-jazzy-2.0-backup-20261001.refs.txt`.
- **`main` restored by commit `2bb57c2`**, pushed as a fast-forward from
  `60519f6` with no force. Its tree is `b15d445`'s plus one change:
  `git diff b15d445 2bb57c2` shows only README.md, the two-line note the
  owner wrote. The full history stays reachable.
- **`lab1` deleted** after checking that all of its commits are in
  coco-labs (`60519f6` is an ancestor of `labs/lab1`; 0 commits missing).
- **Pages turned off.** The API returns 404 for the site, and the old URL
  returns HTTP 404.
- **Tags: none to keep.** The old repository has **0 tags**, `archive/*`
  or otherwise (`git ls-remote --tags`), so nothing was touched.
- **The old repo's CI is red on `2bb57c2`, as expected.** The `CI`
  workflow failed with `coco_rl` exiting 2 after 1.84 s, at collection.
  `b15d445` never had a CI run of its own. The `ci.yml` fixes that made
  main green came after it, and an exact restore removes them again.
  Recorded, not changed.

**coco-labs: paths point at the new workspace** (`6307949`, fast-forwarded
to `main`; `CI` and `Lab` both green on `main`; Pages 200)
- The workspace is now `~/coco_labs_ws`, and the clone is
  `src/coco-labs`, in:
  - `setup_env.sh`, `HOW_TO_RUN.md`, `README.md`, `docs/RUNNING.md`,
    `PROJECT_STATE.md`, `docs/FUTURE_WORK.md`, the Docker files and
    `CLAUDE.md`'s Environment section;
  - the runner scripts, which now work out the repo and workspace from
    their own location instead of a deleted consolidation worktree.
- `build_overlay.sh` with no argument now builds `$HOME/coco_labs_ws`.
- **CLAUDE.md now says never to source the old workspace and this one in
  the same shell**, because duplicate package names shadow each other.
- Recorded measurements that name old paths are history, and unchanged.

**The new workspace, `~/coco_labs_ws`** (measured)
- A fresh `git clone` of coco-labs. The user-space MoveIt prefix is
  **copied** (90 MB) into `~/coco_labs_ws/moveit_prefix`, not linked into
  the old workspace. The copy leaves out the old prefix's stray self-link.
- Clean build, from a scrubbed environment:
  `Summary: 11 packages finished [8.73s]`, exit 0. Once sourced,
  `AMENT_PREFIX_PATH` holds only this workspace's install, its MoveIt
  prefix and `/opt/ros/jazzy`.
- **Tests: 2391 passed, 0 failed, 0 skipped.** Run per package, with cwd
  in the package and on ROS domain 73. coco_lab's pinned hypothesis and
  networkx came from a system-site venv, since there is no sudo here.

  | package | tests |
  |---|---|
  | coco_config | 93 |
  | coco_lab | 352 |
  | coco_lab_ros | 69 |
  | coco_sim | 280 |
  | coco_rl | 229 |
  | coco_perception | 139 |
  | coco_moveit_config | 12 |
  | custom_teleop | 75 |
  | gazebo_models | 229 |
  | coco_mission | 338 |
  | coco_web | 575 |

  coco_moveit_config's 12 includes the 7 MoveIt pick-pose tests, so the
  copied prefix works.

**Teleop through the browser panel: FAILS on `main`; one defect, fixed on
a branch** (measured; `docs/data/coco_labs_ws/`)
- **Run 1, on `main` (`6307949`).** HOW_TO_RUN's two terminals ran
  headless through `scripts/browser_check/live_run.sh`, on domain 61.
  - The stack itself was healthy. `/healthz` returned 200
    (READY/HEALTHY) 4 s after the controllers came up. The arbiter was the
    sole wheel publisher, the platform the sole teleop publisher, and
    AMCL localised.
  - **The page never connected.** It read `Disconnected` for the whole
    420 s wait, and the platform logged **1,193** `Uncaught exception GET
    /ws` errors, each `AttributeError: 'tuple' object has no attribute
    'x_min'`.
  - **The robot did not move.** Odometry stayed at (−0.0006, 0.0)
    through W, S and both joystick drags, and the recorder saw no message
    on the teleop topic or the wheel topic.
- **Cause.** `917bc59` (2026-09-28, P03C consolidation) made
  `TargetRegion.platform_bounds` a plain tuple, but
  `CocoWebNode.world_geometry()` still read `.x_min`/`.x_max`. It runs in
  `ControlSocket.open()`, so every browser connection has died since that
  commit. coco_web's 575 tests stayed green because every one that
  reaches `welcome` stubs `world_geometry`.
- **Fix: branch `fix/platform-world-geometry` (`95c1eef`), pushed to
  coco-labs and NOT merged.** The fix indexes the tuple and adds
  `coco_web/test/test_world_geometry.py`, which runs the real method
  against the real `coco_config`. The new test fails 2/2 on the pre-fix
  code with the same `AttributeError` and passes 2/2 on the fix; coco_web
  then has 577 passed, 0 failed.
- **Run 2, on the fix, fresh simulator.** 0 `/ws` exceptions; the page
  read `Ready`/`Healthy` immediately.
  - **The panel drives the robot.**

    | action | wheel commands | key to first wheel motion | odometry x |
    |---|---|---|---|
    | W held 2 s | 53 | 36.9 ms | −0.0006 → 0.5304 m |
    | S held 2 s | 54 | 22.5 ms | 0.5304 → −0.0514 m |
    | joystick up 1.5 s | 49 | 112.2 ms | −0.0514 → 0.4719 m |
    | joystick down 1.5 s | 46 | 70.0 ms | 0.4719 → −0.0369 m |

  - **STOP with W still held:** wheels at zero 59.7 ms later.
  - **Browser SIGKILLed while driving:** wheels at zero 48.3 ms later.
    After both, 0 moving commands past 600 ms.
  - Wheel publishers: exactly 1, `/cmd_vel_arbiter`. The safety probe
    refused all 8 hostile frames.
  - **The green fetch through the browser completed**: `COMPLETE`,
    `result=fetch`, 194.1 s wall, RTF 0.823. It took one
    RECOVERY → RELOCALIZE on the return, so it finished with
    `reason=LOCALIZATION_DEGRADED`. Every ROS state was rendered on the
    page. One run is not a rate.
- **HOW_TO_RUN corrected.** It sent readers to `:8000` and rosbridge, but
  `mission.launch.py` serves the platform on **:8080** (measured). The
  rosbridge panel is `:8000/legacy.html`, only with `platform:=false`.
  The test expectation is now this session's 2391 across eleven packages,
  replacing the stale 1564 across nine.

**Unverified / not done**
- `scripts/run_all_package_tests.sh` was repointed but never run. It calls
  plain `pytest`, which has no hypothesis here.
- The Docker image path change (`src/coco-labs`) is only statically
  tested.
- **The old checkout and its worktrees were left exactly as they were.**
  `~/ros2_ws(personal)` and the old `coco-robot-ros2` clone were only
  read: the MoveIt prefix was copied, not moved.

**Phase 2 (Live) has not started.** Its starting point is a working
teleop panel, and on `main` it is not one until
`fix/platform-world-geometry` is merged.

NEXT: the owner decides on `fix/platform-world-geometry` (`95c1eef`). To
reproduce the live check, with the new workspace on that branch:
`~/coco_labs_ws/src/coco-labs/scripts/browser_check/live_run.sh
~/coco_labs_ws/src/coco-labs ~/coco_labs_ws <out> green`, then
`analyse_live.py <out>`.

## The world-geometry fix merged; coco_web in CI; COCO in Docker (2026-10-02)

Done on the owner's seven-point instruction of 2026-10-01: merge after two
checks; fast-forward main only with both workflows green; run
`run_all_package_tests.sh` once; prove the Docker path; disable the old
repo's CI; log; stop.

**1. Consumer audit of `TargetRegion.platform_bounds`.** 917bc59 did not
convert an existing value. It *introduced* `platform_bounds` as a plain
tuple `(x_min, x_max, y_min, y_max)` and, in the same commit, the
`coco_web` reader that treated it as an object. Every consumer in every
package:
- `coco_sim/test/test_multi_bay_invariants.py:122` unpacks the tuple.
  Correct.
- `coco_web/coco_web/platform_server.py` (`world_geometry`) read
  `.x_min`/`.x_max`. This was the only wrong one, and the fix makes it
  index the tuple.

The sibling tuple fields 917bc59 introduced also have no attribute-style
reader:
- `approach_corridor` has no consumers at all.
- The five 3-tuple poses are read only through `TargetRegion`'s own
  indexing properties.
- `coco_web/web/app.js` reads the dict `world_geometry` builds, not the
  tuple.

No further fixes were needed.

**2. Tests on the real path.**
- **New end-to-end test:**
  `test_platform_server.py::test_welcome_carries_the_real_world_geometry_end_to_end`.
  `RealWorldNode` is `FakeNode` with the real `CocoWebNode.world_geometry`,
  run through the real `make_app` and `ControlSocket.open()`. A real
  WebSocket client checks every bay in `welcome` against `coco_config`,
  then checks that STOP is honoured.
- **Fails first.** On the pre-fix server it fails with a `TypeError` on a
  `None` frame, because the socket closes without a welcome, which was the
  live symptom. On the fix it passes. coco_web: **578 passed**, 0 failed.
- **Stubs, reported and not rewritten:** **37 coco_web tests run on a
  stubbed `world_geometry`**: 33 `FakeNode` (returns None) in
  `test_platform_server.py` and 4 `Mock` (returns `{}`) in
  `test_transport.py`. 22 of the 37 open a WebSocket and are greeted with
  the stub.
- **Others hiding something similar:** three more `welcome` fields come
  from `coco_config` at runtime, and **no coco_web test calls the real
  loaders** (`_load_colours`, `_load_depth_clip`, `_load_joint_limits`).
  `_load_joint_limits` also catches `KeyError`, so a renamed joint would
  disable arm control with a warning, not fail a test.
- **CI did not test coco_web at all.** `ci.yml` built it but listed only
  seven packages under `colcon test`, so the new test would never have
  failed CI. The PR's run on 23e99db collected 1057 tests across 7 suites,
  and the new tests were absent from its log. Fixed in 4661898: coco_web
  is now in the test step, with tornado 6.5.7 pinned. `coco_mission` is
  still built and not tested; left as it is.
- **Proved in CI:**

  | run | colcon summary |
  |---|---|
  | 23e99db, before | 1059 tests, 0 failures |
  | 4661898, the fix | **1637 tests, 0 failures** |
  | throwaway 1593af9 = 4661898 with only the fix reverted | 1637 tests, **3 failures**, exactly the three world-geometry tests |

  The throwaway was draft PR #2, closed with its branch deleted.

**3. Fast-forward.** main had not moved (44e7d76). PR #1, a draft used as
the CI gate, was green on both workflows on 4661898, so main was
fast-forwarded `44e7d76..4661898` by push. GitHub then marked PR #1
merged. `lab1` was fast-forwarded to match.
- **main's own push-triggered CI** sat in "Setup ROS 2 Jazzy" for nearly
  2 h (the ROS apt mirror was also slowing the Docker build). It was
  cancelled and re-run: attempt 2 **succeeded**, 1637 tests, 0 failures, 8 suites.

**4. `scripts/run_all_package_tests.sh`, run once in `~/coco_labs_ws`**
(main 4661898, scrubbed env, domain 74). The script **exited 0 while two
packages did not run**: it calls plain `pytest`, the system Python has no
`hypothesis`, and its `|| true` swallows the collection error. Reported,
not changed.

| package | script | per-package (2026-10-01) |
|---|---|---|
| coco_config | 93 | 93 |
| coco_sim | 280 | 280 |
| coco_mission | 338 | 338 |
| coco_web | 578 | 575 (+3 new tests) |
| gazebo_models | 229 | 229 |
| coco_rl | 229 | 229 |
| coco_perception | 139 | 139 |
| coco_moveit_config | 12 | 12 |
| custom_teleop | 75 | 75 |
| coco_lab | **collection error** | 352 |
| coco_lab_ros | **collection error** | 69 |

**5. Docker, measured** (`docs/data/coco_labs_ws/docker/`)
- **Build.** `docker compose build` on main 4661898 produced
  `coco-platform:jazzy` (`13a4f1cf7f7a`, 8.18 GB, 9 packages) in 4353 s.
- **Run.** `docker run` mirrored the compose service (port 8080, shm 2g,
  env) plus `--ulimit core=0`, which compose lacks; `docker compose up`
  itself was not run. `/healthz` returned 200 12 s after start. Headless
  Firefox on the host drove the page at `:8080`, and the page read
  `Ready`/`Healthy` with 0 JS errors. The recorder ran inside the
  container, because the image's DDS is loopback-only.

  | browser action | wheel commands | key to first wheel motion | odometry x |
  |---|---|---|---|
  | W held 2 s | 52 | 60.4 ms | −0.0006 → 0.4222 m |
  | S held 2 s | 53 | 29.2 ms | 0.4222 → 0.0469 m |
  | STOP clicked with W still held | — | wheels at zero 67.5 ms after the click | — |

  After the STOP, 0 moving commands arrived past 600 ms. The wheel topic
  had 1 publisher, `cmd_vel_arbiter`.
- **Teardown** left 0 Gazebo processes and 0 containers.
- The image ships **tornado 6.4** (apt), not the 6.5.7 coco_web's suite
  runs on. No mission ran in the container.
- `docs/DOCKER.md` has a dated note: its "never built" line was false as
  of today.

**6. Old repo.** Its `CI` workflow is `disabled_manually` and its `main`
is still `2bb57c2`, so the tree is unchanged. The **existing** failed
check on `2bb57c2`, recorded before disabling, still shows. Removing it
means deleting that run's record (`gh run delete 36825530637 -R
GauthamCodes/coco-robot-jazzy-2.0`), which was not asked for and was not
done. The README carries no CI badge.

**Unverified / not done**
- `docker compose up` itself.
- A mission inside the container.
- Any coco_web test on tornado 6.4.
- `coco_mission` in CI.
- `run_all_package_tests.sh` hiding collection errors.
- The three untested `_load_*` loaders.

**Phase 2 (Live) has not started.** Its starting point, teleop through the
browser panel, now works on main both natively and in Docker.

NEXT: Phase 2, only when the owner asks.

## Phase 2 prep: honest test script, coco_mission in CI, real-path tests, Docker pins, CI timeouts (2026-10-02)

Done on the owner's six-point prep instruction: small fixes only, no
features, on `lab1`, with `main` fast-forwarded once both workflows were
green. Evidence: `docs/data/coco_labs_ws/phase2_prep/`.

**1. `scripts/run_all_package_tests.sh` fails when anything fails.**
- **The `|| true` is gone.** Any non-zero pytest exit fails the package
  and the script (exit 1): failures (1), collection errors (2), no tests
  (5), anything else. A per-package table is printed at the end.
- **The interpreter is chosen deliberately**: `$COCO_TEST_PYTHON`, else
  `<ws>/test_venv` (built by `--make-venv` from
  `coco_lab/requirements-test.txt`, with system site-packages), else
  `python3`. The script refuses (exit 2) if the interpreter cannot import
  pytest, hypothesis and networkx.
- **Found on the way.** `setup_env.sh` puts `~/.local` first on
  `PYTHONPATH`, deliberately, so the runtime's pip `--user` packages win.
  That silently replaced the venv's pinned networkx 2.8.8 with a
  user-site 3.6.1 (measured). Every earlier coco_lab run in this session
  therefore ran on 3.6.1. The script now puts the venv's site-packages
  first; `setup_env.sh` is unchanged.
- **Proved** (each throwaway reverted):

  | case | script exit |
  |---|---|
  | a failing assertion in coco_lab | 1 (coco_lab `1 failed, 351 passed`) |
  | an unresolvable import in a coco_lab test | 1 (pytest exit 2) |
  | `/usr/bin/python3` | refused, exit 2 |

- **Green run** in `~/coco_labs_ws` at lab1 adb7d55, on a quiet machine,
  domain 74, with hypothesis 6.98.15 and networkx 2.8.8: **all 11
  packages, 2400 passed.**

  | package | tests |
  |---|---|
  | coco_config | 93 |
  | coco_sim | 280 |
  | coco_mission | 338 |
  | coco_web | 582 |
  | gazebo_models | 229 |
  | coco_rl | 231 |
  | coco_perception | 139 |
  | coco_moveit_config | 12 |
  | custom_teleop | 75 |
  | coco_lab | 352 |
  | coco_lab_ros | 69 |

  HOW_TO_RUN documents the script and the count.

**2. coco_mission is tested in CI.**

| run | colcon summary | suites |
|---|---|---|
| 4661898, before | 1637 tests | 8 |
| adb7d55 | **1982 tests**, 0 failures | 9 |

The +345 is coco_mission's 338 plus the 7 tests added in this pass. The
proof was a throwaway draft PR, #4, closed with its branch deleted: lab1
with one `test_mission_states.py` assertion broken. CI failed on exactly
`TestContractTable.test_every_nominal_state_has_a_contract`. The summary
read "2 failures" because ament_cmake wraps the whole pytest run as one
ctest test (`Testing/…/Test.xml: 1 test, 1 failure`), so one broken test
counts twice. That wrapper is also why the colcon summary is 3 above the
collected count.

**3. Real-path tests for colours, depth clip and arm limits.**
- **The tests run the real loaders.** `RealConfigNode` calls the real
  `_load_*` loaders in `CocoWebNode.__init__`'s order, against the real
  `coco_config`:
  - colours go through the real server and a real WebSocket (`welcome`,
    each colour accepted, `purple` refused);
  - arm limits are checked in `welcome`;
  - the depth clip goes through the real `_encode_image` into the frame's
    `min_m`/`max_m`, using the existing `_boundary_stub` as frame store.
- **A renamed joint now fails loudly.** `_load_joint_limits` raises
  `RuntimeError`, naming the missing joint, when `coco_config` is present
  but a joint is not. A stripped image with no `coco_config` still warns.
- **Fail first.** A pytest plugin, `coco_breakers.py`, applied one break
  per test:

  | test | broken input | how it failed |
  |---|---|---|
  | colours | `TARGET_COLOURS` removed | the captured fallback warning |
  | depth clip | `CAMERA_DEPTH_CLIP` removed | `None` clip |
  | arm limits | shoulder joint renamed | the new `RuntimeError` |
  | renamed joint | the pre-change loader | `DID NOT RAISE` |

  All pass unbroken. coco_web: **582 passed.**

**4. Docker: compose is safe and is the path.**
- **Changes.** tornado is pinned to 6.5.7 in its own image layer, and the
  compose service sets `ulimits: core: 0/0`. Two static tests pin both;
  each failed first on the old files (no pin; `KeyError 'ulimits'`).
- **Build.** `docker compose build` took 16 s, with apt and torch cached;
  image `d940c8f4fd68`.
- **Run.** `docker compose up -d` was healthy in 12 s. Inside the
  container, `ulimit -c` was 0 (soft and hard), and tornado was 6.5.7 from
  `/usr/local`. Browser on `:8080`:

  | action | wheel commands | key to first wheel motion | odometry x |
  |---|---|---|---|
  | W held 2 s | 49 | 68.5 ms | −0.0006 → 0.4252 m |
  | S held 2 s | 53 | 29.8 ms | 0.4252 → 0.0024 m |
  | STOP clicked with W held | — | first zero 4.3 ms after the click | — |

  After the STOP, 0 moving commands arrived past 600 ms. The wheel topic
  had 1 publisher, the arbiter. `docker compose down` left 0 containers
  and 0 Gazebo.
- **Wait.** The run started only after an unrelated e-Yantra Kepler
  simulator, from another session, had run for about 71 min. It was left
  untouched, and the run waited for it.
- `docs/DOCKER.md` has a dated note.

**5. CI timeouts.** Every job in both workflows now has a timeout, set from
the slowest GREEN run measured over every successful run on both repos:

| job | slowest green | `timeout-minutes` |
|---|---|---|
| build-and-test | 24.8 min | 60 |
| coco-lab-venv | 1.4 min | 20 |
| lab-web | 1.3 min | 20 |
| deploy | 0.2 min | 10 |

The two 2026-10-01 hangs (~2 h each) would now end at 60 min. **No
ROS/apt cache:** `ros-tooling/setup-ros@v0.7`'s `action.yml` has no cache
input, and hand-caching `/var/cache/apt` is not clean. Skipped, and the
reason is written beside the timeout.

**Merged.** `main` was fast-forwarded `0cb574b..adb7d55` after CI and Lab
were green on adb7d55 through draft PR #3, which GitHub marked merged.
`main`'s own push CI and Lab are both green on adb7d55. This entry follows
the same gate.

**Unverified / not done**
- No mission ran in the container.
- The depth test still uses the encoder's node-state stub (the clip and
  encoder are real).
- The colour and depth loaders still fall back quietly on an
  `ImportError`; only the joint rename is loud, as asked.
- The 37 stubbed `world_geometry` tests are unchanged.

**Phase 2 (Live) has not started.**

NEXT: Phase 2, only when the owner asks.

**Addendum, same day: build-and-test timeout 60 → 90.**
- `main`'s push CI on 8bd8041 (run 36930257226) **succeeded in
  44.3 min**, almost all of it in 'Setup ROS 2 Jazzy' on a slow mirror.
  That is a new slowest green run, and against it the 60-min limit would
  have left only 1.35x.
- Following the rule (base the limit on the slowest green run seen),
  build-and-test is now 90 min, about 2x 44.3. That still ends a ~2 h
  hang.
- The Lab job limits are unchanged; their slowest green run is 1.4 min.

## Phase 2 · Live — Part A: audit and design (2026-10-02)

Branch `live` (from 6249e7d). No code changed. The precondition was
checked against the Phase 2 prep entry above, and all five items hold.
Report: `docs/live/PART_A_AUDIT.md`. Evidence: `docs/data/live/part_a/`.

**Measured** (one live run: fresh sim, mission.launch.py, domain 62, quiet
machine; one run is not a rate):
- **Safety defect: `stop` does not stop a running mission.** Sent exactly
  as the page's STOP sends it during `NAVIGATE_TO_RAMP`:
  - wheels zero at +1.5 ms;
  - the executive re-asserted `nav` at +698 ms;
  - wheels moving again at +723 ms, then 152 moving commands over 7.7 s;
  - only `mission abort` stopped them (+87 ms).
- **Teleop preemption works.** 30/30 drive frames acked, first at the wheel
  topic in 1.6 ms, arbiter `active=teleop`. The mission resumed on release.
- **Nav2 mode does not drive under `mission.launch.py`.** The idle executive
  re-asserts `idle` at 2 Hz, so `set_mode auto` lasted about 390 ms.
  - Nav2 still planned (25 `/plan`) and commanded (499 moving
    `/cmd_vel_gated`).
  - The wheels moved 0.
- Teleop with no mission: 3.2 ms to the wheel topic.
- Telemetry 10.00 Hz received.
- Wheel publishers: 1 (`cmd_vel_arbiter`) in every sample.
- `localised` stayed false for 400 s at rest: no AMCL update without motion.

**Designed** (report §4–§6):
- lab_web reuses `frame.js` unchanged, with shared committed fixtures.
- 11 additive changes.
- A pure `control.py` driver/spectator model.
- Truth reaches the telemetry builder only (AST test). The executive already
  reads `/model/coco/odometry` itself, so the invariant is scoped to the web
  layer.
- Tunnel comparison: Cloudflare named tunnel if there is a domain on
  Cloudflare, else Tailscale Funnel.

**Open: owner decisions Q1–Q4** (report §7): `stop` aborts an active
mission; executive asserts mode only while a mission runs; spectator STOP in
code mode; tunnel choice.

**Unverified**
- `/local_plan` on this stack.
- Chrome's LNA prompt for the Pages site → `ws://localhost` (vendor docs
  only).
- Every tunnel property (vendor docs only).

NEXT: Part B, on the owner's "continue" and Q1–Q4.

## Phase 2 · safety fixes merged to main (2026-10-02)

Owner decisions on Part A:
1. STOP is latched.
2. The executive asserts its mode only while a mission runs.
3. Spectators get no STOP.
4. Tunnel: the reply left the placeholder unfilled, so the choice is still
   open (needed in Part C).

Write-up: `docs/live/SAFETY_FIXES.md`. Evidence: `docs/data/live/safety/`.

**Built** (failing-first tests):
- latched STOP in coco_web (`stop_latch.py`), f1600b2;
- executive mode only while running, 6c1653f;
- `/amcl_pose` TRANSIENT_LOCAL plus one `request_nomotion_update`, 54133fe.

Test counts: coco_web 582 → 629, coco_mission 338 → 344.
`run_all_package_tests.sh` now takes package names.

**Measured**
- **STOP at five stages.** Wheel command zero in 1.4–5.8 ms, body at rest
  in 63–225 ms. 0 moving commands to +10 s, no moving mode re-asserted,
  RECOVERY → ABORT in about 1.8 s, latched with 0 violations.
- **On the ramp it holds.** 28–32 mm stopping distance, then ≤ 0.001 mm
  over 9 s.
- **Nav2 with no mission:** 7/7 goals native and 7/7 in Docker compose,
  with Nav2's commands at the wheels.
- **Regression fetch:** COMPLETE, with 1 RELOCALIZE.
- **Localised** 0.05–0.11 s after connect.
- **CI:** 2035 tests, 0 failures on 54133fe.
- **main** fast-forwarded 6249e7d..54133fe.

**Unverified**
- Whether the arm stops mid-grasp.
- Every number is a single run per row, not a rate.

NEXT: Part B (Live view).

## Phase 2 · Part B — Live view, local (2026-10-02)

Report: `docs/live/PART_B.md`. Evidence: `docs/data/live/part_b/`.
Harness: `scripts/live_check/`.

**Built**
- coco_web, additive telemetry: `you`, `config`, `robot.belief`,
  `robot.truth` (display only), `nav.local_path`, `nav.goal`,
  `nav.path_rx`. coco.v1 is frozen at 54133fe by `test_additive.py`.
- lab_web Live tab: three modes, STOP always visible, belief and truth
  toggle, camera, the arbiter's source and who holds control, honest
  labels.
- Binary frames are decoded by coco_web's own `frame.js` against shared
  committed fixtures.

**Measured** (headless Firefox, fresh simulator per run)
- drive frame → wheel: p50 4.6 ms, max 9.7 ms (n = 170);
- STOP → wheel zero: 6.2 ms;
- `nav_goal` → `/plan`: p50 8.6 ms (n = 7), and 7/7 goals succeeded;
- telemetry received at 10.0 Hz;
- preemption: 3.5 ms to the wheels;
- fetches from the page: **3/3 COMPLETE** (blue preempted, green,
  yellow), recoveries 1/1/0;
- 1 wheel publisher throughout;
- the platform's live publishers are exactly the allowlist.

Tests: 2512 across 11 packages, plus lab_web 194.

**Unverified**
- Part B in Docker.
- The camera fps on the page.
- A real touchscreen.

NEXT: Part C, which needs the owner's tunnel choice (the reply left it as
a placeholder).

## Phase 2 · Part C — driver, spectators, remote sessions (2026-10-02/03, IN PROGRESS: waiting on the tunnel choice)

Report: `docs/live/PART_C_REPORT.md`. Evidence: `docs/data/live/part_c/`.
Branch `live`, commits 213f9bd..HEAD, **not pushed** (pushing re-runs CI
on the PR; the brief asks for CI at the end of Part C). `main` untouched
(54133fe).

**Precondition** held, checked against the repo: Part A, the safety fixes
on main, Part B and its invariants. CI and Lab were green on 74ab139 on
GitHub; the Part B entry above had not recorded that.

**Built**
- `coco_web/control.py` (pure, injected clock): one driver per host code,
  spectators refused every command **including STOP** (owner decision 3),
  idle release, session cap, per-client token buckets, host kill; every
  ending calls the latched STOP. `access:=open` (default) is P0.1 exactly.
- Server wiring, `remote:=true` (`/ws` + `/healthz` only), `origins`
  allowlist, `/healthz` `live` summary + CORS for allowlisted origins;
  host-only Trigger services `session_kill/new/code`;
  `scripts/live_session.sh`.
- `docker-compose.remote.yml`: code, remote, origins, host port on
  127.0.0.1 only. **No tunnel**: the choice is the owner's.
- lab_web: claim/release UI, spectator controls held back, STOP shown
  "driver only" for spectators; public status (`status.ts`, empty
  `schedule.json`, Replay + Docker fallback); `LIVE_REMOTE = null`.

**Measured** (n = 1 each, not rates)
- C1 Docker fetch, fresh container: red **COMPLETE**, 259.5 s wall, 0
  recoveries, 0 relocalisations, 1 wheel publisher.
- C2 live (remote compose, idle 20 s, cap 150 s): **20/20** checks; 0
  moving wheel commands in the spectator phase; driver disconnect
  mid-drive → wheels zero +16.8 ms; kill mid-drive → zero +318.4 ms
  (includes docker exec), 0 moving after; cap while driving → socket
  4403, 0 moving to +10 s, truth 0.000 m/s by +0.31 s.
- C4 host half: only 127.0.0.1:8080 published; LAN and bridge IPs no
  connection; every path but `/ws` and `/healthz` 404; bad origins 403.
- Tests: `run_all_package_tests.sh` **2665 passed** (2512 at Part B;
  coco_web 688→836, coco_rl 231→236); lab_web vitest **234** (194).

**Unverified**: everything through a tunnel; the policy defaults in real
use; a real phone.

**Waiting on the owner**
1. The tunnel: Tailscale Funnel, or a Cloudflare named tunnel (and its
   hostname). Part A §6.
2. Confirm the idle exemption while a mission or a browser Nav2 goal runs.
3. Whether to push `live` now (one CI run) or only at the end of Part C.

NEXT: on the tunnel choice, C3 (that tunnel only, at 127.0.0.1:8080),
then C4 external checks, set `LIVE_REMOTE`, then C6 with the owner.

## Phase 2 · Part C — tunnel-independent work finished; at the tunnel gate (2026-10-03)

Fresh session. Reconciled against git: branch `live`, cbc1e26, matched the
expected checkpoint (Parts A and B, C1, C2, C4 host half and C5 done). The
untracked `AGENTS.md` is not ours and was left alone. `live` is **not
pushed** (the brief: CI once, at the end of Part C).

**Owner decisions in the brief:** STOP is driver/host only; control is
exclusive; every ending stops; during a mission or an active Nav2 goal,
**autonomy holds the inactivity lease**, made explicit rather than faked
as heartbeats; don't push yet. The tunnel is still **not chosen**: the
brief says not to choose for the owner.

**Built**
- 89e0239: `control.py` lease. `tick(busy=True)` suspends idle without
  touching the driver's input time. Fields `lease` and `last_input_s`.
  A full `idle_s` window starts after autonomy ends; nothing carries to
  the next driver. The cap is never suspended. lab_web: "Idle release
  paused: autonomy is running". `remote:=true` refuses empty/`*` origins.
  No tornado banner and a JSON 404 on the remote surface. status.ts: 503
  wording, negative numbers dropped. `docs/WEB_API.md`.
- `docs/live/tunnel/`: both tunnels as inactive compose sidecars,
  `ingress_check.sh` (offline), `external_check.sh` (to run from outside),
  README with the vendor facts re-read today and both runbooks.

**Measured**
- cloudflared 2026.9.3, `--network none`: ingress validate OK; only `/ws`
  and `/healthz` on the hostname route to coco; 13 other paths/hosts 404.
- Tests: coco_web 836 → **850**, coco_rl **236**, lab_web vitest 234 →
  **238**, all 0 failed; tsc, build, check_dist clean. The full
  `run_all_package_tests.sh` is owed at the end of Part C.

**Unverified**: all of Tailscale; anything through a tunnel;
`external_check.sh` never run; the lease never driven live.

**Waiting on the owner (the one decision):** Cloudflare named tunnel (a
hostname on a domain on Cloudflare DNS, plus `tunnel login/create/route
dns` in a browser), or Tailscale Funnel (the tailnet name; MagicDNS, HTTPS
and the `funnel` attribute in the admin console; a `tag:coco-live` auth
key). Hostname-independent preparation is done.

NEXT: on the choice, `docs/live/tunnel/README.md` for that option, then
`external_check.sh` from another network, set `LIVE_REMOTE`, then the
"Remote drive gate ready" handoff to the owner's phone (C6).

## Phase 2 · Part C — Tailscale chosen; remote-config fetch; flood close fixed (2026-10-03, later)

Owner decisions (brief): **Tailscale Funnel**, nothing paid; every
session rule as built (lease paused explicitly, cap always runs,
spectators no STOP). Reconciled: `live` at fbc0f77, matches.

**Measured** (n = 1; `docs/live/PART_C_REPORT.md` C1b):
- image 0a325ed08650 (fbc0f77). The remote compose with real defaults
  completed a red fetch: all 16 states, 468.3 s wall, 0 recoveries,
  0 relocalisations, 1 wheel publisher in 111/111 samples. :8080 inside
  the container is `platform_server`.
- Lease: `autonomy` throughout; `last_input_s` peaked at 528.1 s with
  the driver kept. Lease back 0.05 s after COMPLETE, then idle release
  59.91 s later with STOP latched. Nav2 goal: lease autonomy; goal → plan
  5.2 ms.
- Spectator STOP/abort mid-CLIMB: refused, mission unaffected. Driver
  burst of 40: 20/20 ack/rate_limited. Kill → 4403, 0 moving after.
- **Defect found and fixed:** a flooded socket closed without a close
  code (RST after an uncaught write to a closing socket). on_message now
  ignores frames once closing; failing-first regression test. coco_web
  850 → 851.

**Built**: `probe_remote_fetch.py`, `an_remote_fetch.py`; the Tailscale
sidecar runs as uid 1000 with all capabilities dropped (it reaches its
login step, measured), image pinned to v1.102.5; `ts.sh
login|wait|caps|stop`.

**Found**: the public Pages site (deployed from `main` 54133fe) has **no
Live tab** (the deployed bundle has none of its strings), and only the
Pages origin and localhost may open `/ws`. A phone session therefore
needs `live` on `main`, i.e. a push, which this brief forbids. That is
for the owner.

NEXT: the owner's Tailscale login (policy snippet, DNS/HTTPS, login URL
from `ts.sh login`) and a ruling on the push. Then `ts.sh caps` (funnel
true), the compose sidecar, the external check from another network,
`LIVE_REMOTE`, and the remote drive gate.

### Checkpoint: waiting on the owner (2026-10-03, ~22:10 IST)

- Done since 40b5b5d: 6a30783. `ts.sh login` now waits (containerboot
  timed out at 60 s, measured). `external_check.sh` is scoped to the
  owner's own Funnel hostname: the host's public address is a shared NAT
  owned by the network operator and is not scanned. The idle host has
  **no TCP listener on any non-loopback address** and no sshd (measured,
  `c4_exposure/host_listeners_idle.txt`). `test_tunnel_config.py`:
  coco_rl 236 → 241.
- A login is pending in container `coco-ts-login` (state
  `~/coco_tailscale_state`). On resume: `bash docs/live/tunnel/tailscale/ts.sh caps`
  (needs `funnel True`, `https True`, tag `tag:coco-live`). If the login
  URL has expired, run `ts.sh login` again.
- Owner actions asked for: (1) the policy snippet (tagOwners + nodeAttrs
  funnel for tag:coco-live), (2) DNS: MagicDNS + HTTPS certificates,
  (3) open the login URL. Plus a ruling: the phone needs the Live tab on
  Pages, which needs `live` on `main` (push + fast-forward after CI).
- Then: `ts.sh stop`; bring up remote compose + sidecar; `funnel status`;
  external check from another network; `LIVE_REMOTE`; gate.

## Phase 2 · Part C — Funnel live, exposure checked, tunnel measured; at the remote-drive gate (2026-10-03, late)

Continued in the same session after the owner's Tailscale login.

**Done** (commits 6a30783, 5b58960 and this checkpoint):
- The Funnel node is `coco-live.taile7cb60.ts.net`, `tag:coco-live`, with
  funnel and https caps read from the machine before it served anything.
  Funnel serves exactly `/ws` and `/healthz` → `coco:8080`.
- `--shields-up` cannot be combined with Funnel (measured): dropped.
  `--reset` added. `LIVE_REMOTE` set; the CSP gains exactly two origins.
- Exposure. Host: no non-loopback TCP listener. External (check-host.net
  nodes, WebFetch): paths and ports as intended. Through Funnel: origin
  and path checks pass. No address was port-scanned (shared NAT, not the
  owner's). Two "remote" agents ran on this machine and are counted as
  host-side only.
- **Defect:** through Funnel the shipped page lost its socket 17 times in
  ~15 min. Funnel carries ~58 KiB/s, DERP-relayed (uplink 1.83 MB/s), so
  the backlog hid beyond the server and the keepalive closed the socket.
  **Fix:** a remote stream budget (telemetry 5 Hz, camera 3 fps at half
  scale). After it, the shipped page through Funnel: drive → wheel p50
  45.2 ms (n = 170), STOP → zero 148.4 ms, goal → plan p50 153.3 ms,
  goals 5/5. But telemetry gaps reached 15.5 s, app RTT p50 0.56–1.46 s,
  and there were 2 keepalive drops in 407 s.
- Tests: `run_all_package_tests.sh` **2691 / 0** (11 packages); lab_web
  238, tsc, build, check_dist clean. The bundle contains 0 topic names.
- Stack and tunnel **down** (public endpoint times out).

**Unverified**: the phone session; a fetch through the tunnel; CI.

**Owner**: (1) approve pushing `live` and fast-forwarding `main` once both
workflows are green, so Pages serves the Live tab (the phone has no other
allowed origin); (2) optional: a longer keepalive for remote sessions;
(3) the phone session.

NEXT: on approval, push `live` and wait for CI; ff `main` and wait for
the Pages deploy. Then bring the stack up fresh with the tunnel
(`docs/live/tunnel/README.md`), `live_session.sh code`, and the phone
session.

## Phase 2 · Part C — deployed; at the phone-test gate (2026-10-04)

Owner approved the deployment gate. Keepalive unchanged (owner).
- Pushed `live` 74ab139..a61150c; PR #8 CI 37144071122 and Lab
  37144071114 both **success**.
- Fast-forwarded `main` 54133fe..a61150c; CI 37144441639 and Lab
  37144441651 (including the Pages deploy job) **success**.
- The deployed bundle has the Live tab and the Funnel endpoint, and 0
  topic names. The CSP allows exactly the Funnel's two origins. The
  public Live URL rendered with the stack down reads "No live session
  right now. No session is scheduled.", with Replay and Docker links.
- No release, no tag, no branch deletion, no force-push.
- Stack and tunnel **down** until the owner says "start".

NEXT: on "start", run `docs/live/tunnel/README.md` (compose up with the
sidecar), `scripts/live_session.sh code`, recorder in the container,
then the phone session. Record instrumented and user-reported values
separately.

## Phase 2 · Part C closed with gaps; Part D (ship) — docs and release readiness (2026-10-04)

**The phone session** (owner, 2026-10-03 18:52–19:02Z; `PART_C_REPORT.md`
C6; `c6_phone_session/`, analysed by `an_phone.py`):
- Instrumented. Phone connected 18:53:45.8Z and claimed 18:54:23Z (one
  driver id all session, ≤ 2 clients). Three teleop bursts. A Nav2 goal
  (goal → plan 13.1 ms). Mission start → NAVIGATE_TO_RAMP (step 3 of 16).
  **Driver disconnect at 18:58:02.005Z**: STOP latched, mission
  RECOVERY → ABORT `OPERATOR_ABORT`, robot 0.3 m/s → rest in 0.54 s, 0
  moving commands for 10 s, no reconnect. 1 wheel publisher (123/123).
- Owner-reported (screenshots): RTT ≈ 282–293 ms, telemetry 5 Hz, Nav2
  goal executing, mission at step 3 of 16.
- **Gaps**, not assumed: STOP pressed on the phone; the cause of the
  disconnect; a second-device spectator; preemption from the phone; a
  completed mission from the phone; idle/cap from the phone. Also, the
  browser goal still read `executing` for 34 s after the mission's goal
  replaced it.

**Part D (this session):**
- `docs/live/LIVE.md` (new): architecture, security boundaries, safety
  behaviour, the host runbook, local use, recovery, measured summary,
  limitations, and the prioritised backlog with acceptance criteria
  (remote stability first). README Live section; ROADMAP status and
  "as built"; PROJECT_STATE Now/Next.
- Validated: the three compose combinations parse (local 0.0.0.0:8080,
  remote 127.0.0.1:8080, tunnel sidecar none). lab_web 238, tsc, build,
  check_dist clean. 0 broken relative links in the changed docs.
- `run_all_package_tests.sh` **2691 / 0**.
- Stack and tunnel down.

**Release readiness:** ROADMAP §6 "done when" for Phase 2 is met, with the
phone gaps above. A `live-v1.0` release and tag are owner-gated (Lab 1's
precedent was a release with a video). Not done.

NEXT: the owner's release decision (video, `live-v1.0`), then LIVE.md §9
item 1.

## Phase 3 · Localise (Lab 2) — IN PROGRESS checkpoint (2026-10-04)

One session, the whole phase (owner's brief). Branch **`lab2`**, cut from
`live` = `main` = 4530a8b. Worktree `.claude/worktrees/lab1`; tests and
real-stack runs use a COPY overlay `~/coco_loc_ws` (the parenthesised
worktree path breaks colcon/gz quoting; Phase 2 did the same with
`~/coco_live_ws`). `LAB_SOURCE.txt` in the copy names the source commit.

**Reconciled before starting.** Phase 2: Parts A–C done, Part D docs done;
`live-v1.0` release/video owner-gated, not done. Rule 9 applies to labs,
not phases, and Lab 1 has URL + video + write-up, so Lab 2 is not blocked.
Baseline (measured, this session): `run_all_package_tests.sh` **2691 /
0 / 0** (11 packages); lab_web vitest **238**, tsc clean.

**Built so far (commits 530fac0, 4b711a4, 4222306, 50bab2c):**
- coco_lab (stdlib, no rclpy): `sketch.py`, `localise.py` (MCL with
  nav2_amcl's likelihood field AND score `1 + sum pz^3`, augmented MCL
  seeded as nav2_amcl pf.c seeds it; EKF on raw beams), `kalman.py`,
  `locbundle.py` (loc bundle 1.0, replay_check), `loc_teaching.py`.
- lab_web: Lab 2 view (`?view=localise`), TS loc decoder pinned to Python,
  worker `localise` glue, catalog 1.2, exhibits.
- Real stack: `docs/data/lab2/` runner, probe, batch, overlays
  `nav2_loc_{shipped,recovery}.yaml`, `ekf_odom_imu.yaml` (lab only).

**Measured so far:** Sketch fidelity (2 fresh sims, 237 scans, 111,804
beams: |e| median 2.2 mm, 86.7 % < 5 cm; odometry: straight 0.000 m,
square 2.30 m / 2.45 rad, tours 17.2 m and 2.6 m); Sketch rates over 20
seeds (`sketch_rates.json`); robot_localization replay (square 2.30 →
0.05 m; tour max 21.6 → 0.45 m, at 4x — being redone at 1x, the 4x
replay lags 0.12 m while moving). Kidnap A/B: running.

**Defects found and fixed:** a subnormal heading made a Sketch ray NaN;
augmented MCL never injected until seeded like pf.c; the probe never saw
AMCL's latched pose (2 sessions VOID, kept as `*.void1`); the landmarks
kidnap moved 1.45 m while the lab said "across the room" (now 9.2 m,
pinned by a test).

NEXT (if this session is cleared): finish the A/B batch
(`~/coco_lab_runs/lab2/batch.tsv`), `an_kidnap.py`, the 1x replays +
`an_ekf.py`, `amcl_replay.py` per drive and arm, then docs and CI.

### Checkpoint — usage limit reached (2026-10-04 ~12:40 UTC)

Since the entry above (commits through this one, pushed to `labs/lab2`):
- Probe and runner fixes: `--to=` (K2/K4 negative x VOIDed `recovery_K2`,
  kept as `.void2`); observe-only `lab_ekf.launch.py` + `ros_clean.sh`
  patterns; `test_ekf_config.py`, `test_sketch_constants.py` (the latter
  NOT yet run: it needs the overlay's coco_config); `LOC_FORMAT.md`
  (pinned); view, glue, catalog-1.2 tests; Lab 2 lazy-loaded (main JS
  108 KB gz, Localise chunk 14 KB gz); phone overflow fixed.
- **Measured:** browser — cold in-browser run 9.6 s, warm 3.6 s, 0
  console errors; Pyodide vs CPython on identical inputs: same outcomes,
  NOT the same bits (`docs/data/lab2/browser/report.json`). Lab 1's
  browser scenarios: no regression (warm edit 1.36–1.48 s; share link
  reproduces). lab_web vitest **257**, tools **86**, tsc/build/check_dist
  clean. robot_localization at 1x on fidelity_s1: square 2.30 → 0.05 m,
  tour max 21.6 → 0.45 m, straight 0.000 → 0.120 m — the controller's
  TWIST integrates 1.9 % more than its pose (measured from the bag); a
  pose-differential variant (`docs/data/lab2/ekf_variants/`) is queued.
  Kidnap A/B so far: K1 shipped and K1 recovery both NOT recovered in
  180 s (injection active in B: the estimate hops between wrong modes).
- **Still running in the background (job scripts in
  `~/.claude/jobs/eb997671/tmp/`, may finish without this session):**
  round 1 of the A/B (`batch2.log`), then `chain.sh`: round 2 (`:r2`
  sessions + K2 rerun) → variant replays (`rlpd_*`) → `amcl_replay.py`
  for 5 drives × 2 arms into `~/coco_lab_runs/lab2/amcl_replay/`.
  Check with `cat ~/coco_lab_runs/lab2/batch.tsv`; if nothing is running,
  `pgrep -af 'g[z] sim|lab2_'`.

**Remaining to close Phase 3:** `an_kidnap.py ~/coco_lab_runs/lab2 --out
docs/data/lab2/kidnap_ab.json`; `an_ekf.py` on both 1x replays (and the
variant) → `ekf_drift.json`, choose the config the data supports;
`an_amcl.py ~/coco_lab_runs/lab2/amcl_replay --out
docs/data/lab2/amcl_odom.json`; rebuild the catalog; fill the PENDING
sections of `docs/RESULTS.md` and `docs/labs/LAB2_LOCALISE.md`; README,
ROADMAP and PROJECT_STATE; run `test_sketch_constants.py` and the full
`run_all_package_tests.sh` (COCO_WS=~/coco_loc_ws, after `sync.sh`);
record the demo (`record_lab2_demo.py`); open a draft PR lab2 → main for
CI. Deploying (main) and a release stay owner-gated.

## Phase 3 · Localise (Lab 2) — implemented, measured, documented (2026-10-04)

Resumed from the checkpoint above; every run it left in the background
had finished. Branch `lab2`.

**Measured (the remaining real-stack work):**
- **Kidnap A/B** (`docs/data/lab2/kidnap_ab.json`), 20 valid
  fresh-simulator trials, 5 targets × 2 rounds per arm, 180 s of rotation:
  shipped `recovery_alpha` 0/0 recovered **0 of 10**; Nav2's suggested
  0.001/0.1 recovered **2 of 10** (6.5 s, 36.0 s). One-sided Fisher p =
  0.237 (derived): not resolved. 3 VOID kept. 4,344 watch samples, wheel
  topic `cmd_vel_arbiter` only.
- **robot_localization**: the first configuration (wheel TWIST + gyro) had
  0.12 m on a 6.4 m straight because the controller's twist integrates
  1.9 % more than its pose (measured from the bag). The wheel POSE
  differential + gyro configuration beat it on 4 of 5 drives and was
  adopted (`ekf_odom_imu.yaml`; the twist one kept as a variant): square
  2.30 → 0.065 m, tours' worst error 21.6 → 0.21 m and 33.6 → 0.24 m.
  Upper bound (noiseless sim gyro). Observe-only live.
- **AMCL on each odometry**, offline on identical scans
  (`amcl_odom.json`): in the fully mapped arena AMCL absorbs the drift
  (means within 0.02 m); the EKF lowers the tours' worst error 0.41 →
  0.20 and 0.30 → 0.22 m. Run 15's unmapped-corridor case NOT tested.
- Browser (local build): cold 9.4 s, warm 3.5 s, 0 console errors, phone
  width clean, Lab 1 unchanged (smoke 11/11). Demo video 91.6 s
  (`docs/data/lab2/video/`, file outside git).

**Tests:** `run_all_package_tests.sh` **2,772 / 0 / 0** (coco_lab 352 →
416, coco_lab_ros 69 → 86); lab_web vitest 257, tools 86; tsc, build,
check_dist clean. One genuine failure found and fixed on the way:
`robot_localization` undeclared in `coco_lab_ros/package.xml` (and added
to CI's apt list).

**Docs:** `docs/labs/LAB2_LOCALISE.md`, `docs/labs/LOC_FORMAT.md`,
`docs/RESULTS.md` "COCO Lab Phase 3", `docs/data/lab2/README.md`, README,
ROADMAP, PROJECT_STATE.

**Unverified:** the public site (not deployed); a real phone; a real
IMU; robot_localization feeding AMCL live; recovery with motion other than
rotation; rates (every real-stack count is n ≤ 10).

**CI:** draft PR #10 (`lab2` → `main`) at 56a6ffc — all checks green:
ROS build-and-test 2,273 tests / 0 failures / 0 skipped; coco_lab venv
413; lab_web tools 86, vitest 257, site build; deploy skipped (main only).

NEXT: the owner's decisions — fast-forward `main` to `lab2` (deploys Lab
2 to Pages), then the release gates (`live-v1.0`, a Lab 2 release with
the video at `~/coco_lab_runs/lab2/video/`). Phase 4 (Map) is not started.

## Phase 3 · ship: deployed, verified on the public site, releases prepared (2026-10-04)

Owner's prompt: ship the completed Phase 3; FF `main` if the rule permits
and CI is green; verify the public site; prepare `live-v1.0` and
`lab2-v1.0`; **publish nothing without explicit approval**.

**Done:**
- PR #10 green on `4405065` (CI 37218065856, Lab 37218065868). Only docs
  changed since the full local run on `56a6ffc` (2,772 / 0 / 0), so the
  standing rule (FF only, every test green) held.
- `main` fast-forwarded `4530a8b..4405065` on `labs` (plain push, no
  merge commit, no force). On `main`: CI 37219611482 and Lab 37219611486
  (with the Pages deploy) **success**. Deployment 6844092018 of `4405065`;
  live catalog `built_from 4405065`, `dirty: false`.
- **Public site (measured)**, headless Firefox 157, `check.py <public>
  smoke localise localise_phone` → `docs/data/lab2/public/report.json`:
  Lab 1 smoke 11/11; Lab 2 Sketch label + fidelity note, predict/reveal,
  play, truth toggle, race (3 maps), kidnap target by click, 4 exhibits;
  cold 11.35 s, warm 3.05 s; Pyodide = CPython outcomes; 390 px clean;
  **0 console errors**. The Live view (stack down) reads "No live session
  right now. No session is scheduled." (its only console errors are the
  failed `ws://localhost:8080` connects — no local stack).
- **Video:** the local-build recording validated (sha256 matches); a
  public-site recording made with the same script, 91.76 s, one 10.56 s
  cut, 0 console errors, sha256 `b13aa1fe…`
  (`~/coco_lab_runs/lab2/video_public/`, outside git;
  `docs/data/lab2/video/`). That is the `lab2-v1.0` asset.
- Docs: RESULTS "On the public site" + video note; LAB2_LOCALISE §4.4/§5;
  ROADMAP; PROJECT_STATE Now/Next; release notes `docs/releases/`.
- No Phase 2 video exists (a live session needs the stack + tunnel up).

**Releases (prepared, NOT published):** `live-v1.0` → `4530a8b` (Phase 2
on `main`, deployed then); `lab2-v1.0` → the `main` commit carrying this
entry. Annotated tags local, drafts on GitHub — see the next entry for
what exists.

**Unverified (unchanged, Phase 3's limitations):** no real-phone test, no
real IMU, no live robot_localization → AMCL integration, run 15 not
reproduced, real-stack counts n ≤ 10.

NEXT: the owner's approval to push the two tags and publish the two
drafts. Phase 4 (Map) not started.

### Checkpoint — at the release-publication gate (2026-10-04, ~17:50 UTC)

- PR #10 was recorded MERGED by GitHub when `main` reached its head
  (`4405065`), so the docs commit got its CI gate on new draft **PR #11**
  (`lab2` → `main`): CI and Lab green on `4b675c1`.
- `main` fast-forwarded `4405065..4b675c1`. Lab 37221184498 (with the
  deploy) green; Pages deployment 6844374404 of `4b675c1`, live catalog
  `built_from 4b675c1`, `dirty: false`. **CI 37221184465 failed attempt
  1** on `gazebo_models`
  `TestLiveGraph::test_the_relay_output_is_restamped_and_unaltered`,
  `assert 9 >= 10`: the load-sensitive test CLAUDE.md records (9 of the
  10 messages in its window). The same code had passed that job three
  times. **Re-run (attempt 2): success.** Not root-caused; recorded.
- Public checks re-run on the `4b675c1` build (load 0.12–0.62): same
  results, 0 console errors; cold 9.28 s, warm 3.05 s
  (`docs/data/lab2/public/report_4b675c1.json`).
- **Tags, LOCAL ONLY (not pushed):** `live-v1.0` (annotated) → `4530a8b`;
  `lab2-v1.0` (annotated) → `4b675c1` (= `main` = the deployed site).
  Neither exists on `labs`.
- **Draft releases on `labs` (not published):** `live-v1.0`, target
  `4530a8b`, no asset; `lab2-v1.0`, target `4b675c1`, asset
  `coco_lab2_demo.mp4` (the public-site recording, 3,399,232 B; the
  download was checked, sha256 `b13aa1fe…`). Bodies = `docs/releases/*.md`.
- This entry is on `lab2` (PR #11) only; `main` stays at `4b675c1`.

NEXT (owner): on approval, `git push labs live-v1.0 lab2-v1.0`, then
`gh release edit <tag> -R GauthamCodes/coco-labs --draft=false` for each.
Optionally fast-forward `main` to this record commit afterwards.

## Phase 2 + 3 RELEASED; Phase 4 (Map, Lab 3) opened (2026-10-04, ~18:20 UTC)

Owner's prompt (Phase 4): "The owner has explicitly approved publication
of live-v1.0 and lab2-v1.0", then ship, reconcile and continue into
Phase 4 in the same session.

**Published (measured, checked unauthenticated with curl):**
- `git push labs refs/tags/live-v1.0 refs/tags/lab2-v1.0` — both
  annotated tags now on `labs` (`live-v1.0` → `4530a8b`, `lab2-v1.0` →
  `4b675c1`), beside `lab1-v1.0`.
- `gh release edit live-v1.0 --draft=false --latest=false --verify-tag`,
  then `lab2-v1.0 --draft=false --latest --verify-tag`. Published
  18:17:00Z / 18:17:02Z; `lab2-v1.0` is "Latest".
  <https://github.com/GauthamCodes/coco-labs/releases/tag/live-v1.0>,
  <https://github.com/GauthamCodes/coco-labs/releases/tag/lab2-v1.0>.
- Release bodies = `docs/releases/*.md` (diff: only a trailing newline).
- `lab2-v1.0`'s asset `coco_lab2_demo.mp4` downloads 200, 3,399,232 B,
  sha256 `b13aa1fe…` = the PUBLIC-site recording recorded in
  `docs/data/lab2/video/README.md` (`~/coco_lab_runs/lab2/video_public/`).
  The file in `~/coco_lab_runs/lab2/video/` (`7dd04673…`) is the earlier
  local-build recording — not the release asset, as that README says.
- Every link in both notes answers 200 (Pages root, `?view=live`,
  `?view=localise`, both `blob/<tag>/…` write-ups).
- Pages: latest `github-pages` deployment 6844374404 of `4b675c1`.

**Reconciled:** `main` fast-forwarded `4b675c1..e128036` (the docs-only
release-gate commit; plain push, no force, no merge commit). `main` is
not branch-protected.

**Correction to the prompt:** none of substance — the repo agreed with
it (e128036 was the release-gate commit and a descendant of `main`).

Phase 4 work is on branch **`lab3`** (from `e128036`), worktree
`.claude/worktrees/lab1` of the old checkout (remote `labs`).

### Phase 4 (Map, Lab 3) — design checkpoint (2026-10-04, ~18:40 UTC)

Survey findings (the repository, checked this session):
- **Drives exist; no new recording needed to start.** Lab 2's `fidelity`
  sessions recorded, each on a FRESH simulator, the same commanded 121 m
  tour (`docs/data/lab2/tour_route.txt`): `fidelity_1` (sim t 191.7–632.2)
  and `fidelity_s1` (253.6–694.1), each 4,385 rows, ending where they
  began (a loop). Bags under `~/coco_lab_runs/lab2/<s>/bag` carry `/scan`
  (480 beams, 10 Hz, frame `lidar_link`), `/tf` (`odom→base_footprint` =
  wheel odometry, joints, AND AMCL's `map→odom` — must be dropped before a
  SLAM replay), `/tf_static`, `/imu`, `/diff_drive_controller/odom` and
  the truth `/model/coco/odometry` (world frame; map = world + (2, 0)).
  Wheel-odometry drift on these tours: 17.2 m and 2.6 m (historical, Lab 2).
- **slam_toolbox 2.8.5 is installed**; the project's own config is
  `gazebo_models/config/slam_params.yaml` (online async, Ceres) — used
  unchanged as the shipped arm.
- **Cartographer is NOT installed** and there is no sudo. The released
  `ros-jazzy-cartographer-ros` 2.0.9003 is in apt; its only missing system
  dependency is `liblua5.2-0`. Plan: a user-space prefix of the released
  debs (`~/coco_labs_ws/cartographer_prefix`, `apt-get download` +
  `dpkg -x`), the same pattern as `moveit_prefix`.
- **Map score already defined by the project:** `coco_lab.maps.
  compare_occupied` against `docs/data/lab1b/arena_maps.py ground_truth`
  (rasterised from `navigation_world.json` at LiDAR height, rule centre).
  Phase 1B's 0.9456 / 0.5771 is rasterisation consistency, NOT map
  quality; D-1 moved map quality to Lab 3.

Design (decided here; each is documented where it lands):
1. `coco_lab` (stdlib only, no rclpy): `occgrid` (log-odds, Bresenham,
   ROS-style 0..100/255 cells), `landmarks` (deterministic corner
   extractor + IDEALISED range-bearing sensor with known association and
   ray-cast visibility), `ekfslam`, `fastslam` (grid-based RBPF, as
   GMapping minus its scan-matched proposal), `posegraph` (ICP front end,
   loop closure by ICP near old nodes, Gauss–Newton + preconditioned CG),
   `mapeval` (ATE with SE(2) alignment; occupied precision/recall exact =
   `compare_occupied` and with a stated tolerance against truth SURFACE
   cells; coverage), `slambundle` (map bundle 1.0, locbundle's rules).
2. Runs on one world: known poses, odometry poses (the naive baseline),
   EKF-SLAM, FastSLAM, pose graph (± loop closure). Identical inputs by
   construction.
3. Real drives: derived replay bags (tour window, `map→odom` dropped) →
   slam_toolbox (shipped params; loop closing on/off), Cartographer
   (released 2D config adapted to COCO's frames; odometry on, IMU off so
   every backend gets scans + wheel odometry), and coco_lab's SLAMs on
   the same scans. ATE vs truth, map score vs the ground-truth raster.
4. lab_web `?view=map`: Sketch mapping (route by clicking, noise, loop
   closure toggle, corridor, compare, belief/truth), the "map the arena"
   challenge, and a Replay of the real tour's backends.

### Phase 4 checkpoint — implementation in place, evidence being finished (2026-10-05, ~09:45 UTC)

Branch `lab3` (pushed to `labs`). What exists (code + tests; nothing below
is a final number unless marked):
- `coco_lab`: `occgrid`, `landmarks` (IDEALISED sensor), `slam`,
  `ekfslam`, `fastslam` (plain RBPF), `posegraph` (MAP point-to-line ICP
  with odometry prior, scan = one measurement, odometry information from
  the told motion model, loop closure gated on a well-constrained match,
  Gauss-Newton + chain-preconditioned CG), `mapping`, `mapeval`,
  `mapworld`, `slambundle` (map bundle 1.0, `docs/labs/SLAM_FORMAT.md`,
  doc pinned by a test), `map_teaching` (loop room, corridor, landmarks
  room, arena challenge; routes planned by coco_lab's A*).
  coco_lab focused runs green (last full venv run 484 before later
  additions; final count at the end).
- `lab_web`: `?view=map` (Sketch / challenge / Replay), map decoder pinned
  byte-for-byte to Python (`slamdecode.test.ts`), `mapview.test.ts`,
  worker `mapping` glue (`test_map_glue.py`), guard extended to mapping
  code, `build_map.py` (catalog 1.3). Local site build + headless Firefox
  (`check.py ... mapping`): works, 0 console errors, Pyodide = CPython to
  the 6th decimal.
- Real backends (`docs/data/lab3/`): drives extracted from Lab 2's two
  recorded tours (`make_drive.py`), `slam_replay.sh` (slam_toolbox with the
  project's params; Cartographer from the RELEASED debs in a user-space
  prefix — runs cleanly, no missing library), `an_backend.py`.

Findings so far (to be finalised in RESULTS):
- Round 1 (`~/coco_lab_runs/lab3`, all 8 runs) found loop closure ON
  making Cartographer's map much worse on both drives (F1 0.17-0.19 vs
  0.88-0.92 off) and slam_toolbox's worse on tour 1 — but several runs
  overlapped heavy load (other sessions' simulators, load up to 47).
  Round 2 (`~/coco_lab_runs/lab3_r2`) is also under external load and two
  s1 Cartographer runs were REFUSED by the runner's process check (to be
  filled). A quiet round is still owed before any claim.
- coco_lab on the real tour: FastSLAM depends on the motion model (AMCL
  alphas diverge, calibrated alphas track); a greedy improved proposal was
  tried and REMOVED (worse). Final coco_lab numbers being re-run at
  `da253eb` (pose graph told the calibrated model).

NEXT: finish round 2, fill the refused runs, a quiet round 3; final
coco_lab runs; `make_replay_bundle.py` → `docs/data/lab3/replay/`;
`an_results.py` → `results.json`; docs (LAB3_MAP, RESULTS, README for
docs/data/lab3, PROJECT_STATE, ROADMAP); full tests; PR + CI; deploy;
public check; video; release draft.

## Phase 4 · Map (Lab 3) — implemented, measured, documented (2026-10-05)

Branch `lab3`. Everything below is in `docs/labs/LAB3_MAP.md` and
`docs/RESULTS.md` "COCO Lab Phase 4" with commands and evidence paths.

**Built:** coco_lab occupancy mapping, EKF-SLAM (IDEALISED landmarks),
grid FastSLAM, pose-graph SLAM, metrics, map bundle 1.0
(`SLAM_FORMAT.md`), the Lab 3 view (Sketch, challenge, Replay), the
real-backend pipeline (`docs/data/lab3/`), Cartographer from the released
debs in `~/coco_labs_ws/cartographer_prefix`.

**Measured:** real backends on two identical recorded tours, three rounds
(two async, one slam_toolbox sync), 20 runs + 1 diagnostic: results agree
across rounds and loads 1.5–37; loop closure hurt (Cartographer both
tours, slam_toolbox one), NOT attributed, odometry hypothesis rejected.
coco_lab on the same tours (pose graph 0.267 / 0.758 m; FastSLAM depends
on the motion model; 13 of 13 loop closures true). Scan sigma and motion
model calibrated on data no claim uses. Sketch 20-world counts. Local
browser: 0 console errors, phone width clean, Labs 1/2 unchanged.

**Tests:** run_all_package_tests 2,848 / 0 / 0 (coco_lab 416 → 492);
vitest 275; tools 95; tsc/build/check_dist clean.

**Unverified:** a physical robot (Gazebo only), why the backends' loop
closure hurt, a real phone, rates (2 drives, 5 seeds).

NEXT: draft PR `lab3` → `main`, CI green, fast-forward `main` (deploys),
public-site checks, video from the public site, tag `lab3-v1.0` locally
and a draft release (publishing is the owner's call).

### Phase 4 — deployed, verified on the public site, release gate prepared (2026-10-05, ~17:00 UTC)

- **PR #12** (`lab3` → `main`, draft): `CI` 37337531668 and `Lab`
  37337531548 green on `ee9bd65`.
- **`main` fast-forwarded `e128036` → `ee9bd65`** (plain push, no force).
  `CI` 37340218072 and `Lab` 37340217984 green on `main`; Pages deployment
  6864344558; the live catalog's `built_from` = `ee9bd65`, not dirty.
- **Public-site checks** (measured, headless Firefox 157, load 2.4–3.1,
  `docs/data/lab3/public/report.json`): `check.py <public> smoke mapping
  mapping_phone localise` — 0 console errors in all four; Lab 3 cold 15.7 s,
  warm 8.3 / 3.1 s, the challenge 3.1 s; Pyodide = CPython (F1 identical,
  ATE to the 6th decimal); no overflow at 390 × 844; Lab 1 smoke 11 of 11;
  Lab 2 cold 10.1 s, warm 3.2 s.
- **Video** recorded from the public site (`record_lab3_demo.py`): 122.3 s,
  H.264 1120 × 920, 5,268,119 B, sha256 `0d964890…`, 0 console errors,
  three listed cuts (`docs/data/lab3/video/`). A first recording was
  discarded: `Recorder.cut` stamped mid-video cuts on the monotonic clock
  (`at_video_s` 78581.53); fixed in `record_demo.py` (Lab 3 is the first
  demo to cut mid-recording; no earlier evidence affected) and re-recorded.
- Placeholders filled in `LAB3_MAP.md`, `RESULTS.md`; release notes
  `docs/releases/lab3-v1.0.md` committed; `PROJECT_STATE.md` and
  `ROADMAP.md` say deployed. Tools tests 95 / 0 after the recorder fix.
- **`lab3-v1.0`: annotated tag LOCAL only and a DRAFT GitHub release with
  the video.** Publishing (pushing the tag, un-drafting) is the owner's
  call; it was not covered by this session's approval.

NEXT: the owner decides on publishing `lab3-v1.0`:
`git push labs lab3-v1.0 && gh release edit lab3-v1.0 -R GauthamCodes/coco-labs --draft=false --latest --verify-tag`.
Phase 5 (Search) NOT started.

### Lab 3 released — `lab3-v1.0` published (2026-10-06, ~09:40 UTC)

The owner approved publishing `lab3-v1.0` in this session ("approve
lab3-v1.0", 2026-10-06). Before that, the gate was checked and found
closed: no approval was recorded in `PROJECT_STATE.md`, this log, or
`labs/main`, the tag was local only, and the release was a draft.

Done:
- `git push labs lab3-v1.0` (annotated tag `e46b0d7` → commit `a63a4c8`).
- `gh release edit lab3-v1.0 -R GauthamCodes/coco-labs --draft=false
  --latest --verify-tag`. Published 2026-10-06T09:38:28Z, marked Latest.

Verified (measured, this session):
- `git ls-remote --tags labs` lists `lab3-v1.0` → `a63a4c8`.
- `gh release list`: Lab 3 = Latest, Lab 2 / Live / Lab 1 unchanged.
- The release asset `coco_lab3_demo.mp4`, downloaded from its public URL,
  is 5,268,119 B with sha256 `0d9648909acb6365bb29856489062c339ef473a9203db7c6d69f7f03f19c4e66`,
  the hash recorded at recording time.
- Both links in the release notes answer HTTP 200 (`?view=map` on the
  public site; `docs/labs/LAB3_MAP.md` at the tag).

No Lab 3 engineering was redone. Phase 5 (Search, Lab 4) starts on branch
**`lab4`** (from `a63a4c8`), same worktree.

### Phase 5 (Search, Lab 4) — survey findings and design checkpoint (2026-10-06, ~10:30 UTC)

Branch **`lab4`** (from `a63a4c8` + the release record `534e52a`), worktree
`.claude/worktrees/lab1` of the old checkout, remote `labs`.

Survey findings (the repository, checked this session):
- **The master context's P0.4 design is not in the repository** (as Phase
  0 recorded). ROADMAP §5 Lab 4 and the Phase 5 prompt are the spec.
- **Prior search work exists but is NOT on this lineage:** local branch
  `p03d-autonomous-target-search` (9 commits, 2026-09-28..30, by a
  concurrent session; on no remote), built on the OLD single-crest
  four-lane world. Reference only: its lessons are taken (perception-only
  acquisition; colour must not change the order; stale frames rejected;
  failures kept), its code is not — this lineage is the 24 x 18 m arena
  with FOUR SEPARATE BAYS (`bay_1..bay_4` at y -6/-2/+2/+6, each its own
  ramp and platform). It also edited `coco_perception/target_pose.py`,
  which this phase does not need to touch.
- **The crest occludes the platform from the flat** (target_finder's
  docstring; `lane_for_colour`), so surveying a bay means climbing it.
- **target_finder already gives a negative observation:** `found=0
  seen=<colours>`; on `found=1` it carries the perceived base_footprint
  `x y z range`. Its `lane=` field is `lane_for_colour(sel)` — the TOLD
  lane — and the search must never read it (to be pinned by a test).
- **Cross-bay sightings are impossible by geometry:** HFOV 1.25 rad
  (±35.8°); a neighbouring bay's target is ~72° off-axis at the survey
  pose, behind side guards.
- **The executive's arrival checks read ground-truth pose** (pre-existing,
  C2-NAV.45). The search decision must therefore take no pose input.
- **A miss leaves another colour's target on the deck.** The existing
  `skip_grasp` path DESCENDs forward over the platform — straight through
  x = 4.05 on the centreline, where that target stands (heading-hold at
  yaw 0). A fetch never meets this because the target is held by then; a
  search meets it on every miss. Not measured; a hazard by geometry.
- **Docker builds nine named packages and not `coco_lab`.**
- **Gazebo is BLOCKED right now:** three simulators are running, none
  started by this session — two e-Yantra Kepler worlds (pids 388835,
  389677, since 2026-10-05 23:25) and one `gz sim server` with no world path
  (pid 270753, since 2026-10-05 14:45, reparented to systemd — the shape of
  an orphaned GUI-mode server). Per the owner's instruction, not touched;
  no simulator is started while any runs.

Design (decided here; each is documented where it lands):
1. **`coco_lab.regionsearch`** (stdlib only): regions as semantic places
   (approach = pre-ramp pose, ramp, platform/survey area, exit), a belief
   over regions, a detection model (`d` = P(found | there), no false
   alarms — a positive is confirmed by approach and grasp), Bayesian
   negative updates, travel costs in metres (derived: A* on the robot's
   own Nav2 map, inflated by the robot radius, plus the ramp up and back),
   exact expected-search-cost minimisation over every remaining order
   (≤ 8 regions), deterministic tie-break by region order, re-planned
   after every observation. Teaching policies beside it: nearest-first,
   most-likely-first, the learner's order. A versioned trace and
   **search bundle 1.0** (locbundle's rules).
2. **Mission prior is uniform.** The frozen colour→bay table is the
   told channel; using it as a prior would be telling by another name.
3. **FSM (search mode):** LOCALIZE → SELECT_SEARCH_REGION →
   NAVIGATE_TO_RAMP → ALIGN_FOR_CLIMB → CLIMB → VERIFY_CLIMB →
   SURVEY_REGION → (found) STOW_ARM … COMPLETE; (miss)
   MARK_REGION_SEARCHED → LEAVE_REGION → SELECT_SEARCH_REGION, or
   RETURN_HOME → ABORT `SEARCH_EXHAUSTED` when none remain. A miss is an
   observation, not a failure: it never enters RECOVERY.
4. **LEAVE_REGION backs down the ramp it climbed** (`/ramp/retreat`, a
   scripted heading- and lane-hold reverse in ramp_driver, published on
   ramp_driver's existing `/cmd_vel_rl`, mode `rl`): never over a deck that
   still holds a target, and the next bay is then on the near side. NEW
   motion, unmeasured until Gazebo is free; fallback if it fails there: a
   far-side descent held to an offset line clear of the target.
5. **Anti-cheat on the existing seam:** `mission.launch.py search:=true`
   (default) hands both nodes ONLY `task_view()['requested_colour']` — an
   empty region map, whatever the manifest says; ramp_driver in search mode
   ignores the colour and follows `/mission/search_region`. Discovery =
   target_finder `found=1` while surveying; the pose the grasp uses is
   approach_server's from `/perception/target`. The manifest is never a
   fallback. `search:=false` keeps the told mission exactly as measured.
6. **Reporting:** `/mission/search` (key=value: mode, order, current,
   searched, belief, discovered); `mission_view` adds `mission.search`
   (additive); the Live label is driven by it — "discovers" only when the
   running mission says `mode=discover`.
7. **Lab 4 view `?view=search`:** Sketch (coco_lab via Pyodide: belief,
   learner order vs policy, expected cost, predict-then-reveal,
   truth/belief), Replay of the Gazebo matrix runs, exhibits cited.

Next: `coco_lab.regionsearch` + tests.

### Phase 5 — checkpoint: search implemented, first Gazebo evidence (2026-10-06, ~13:05 UTC)

Commits on `lab4`: `15a358b` coco_lab.regionsearch; `d050b49` the mission
discovers (search mode default on; anti-cheat on the EpisodeSpec seam);
`180c9f1` default-launch fix + search bundle 1.0 + runner; `9c574ee`
runner rosbag; `3288cc0` Lab 4 site plumbing (catalog 1.4 `search` block,
worker glue, TS decoder). Focused tests green at each commit (coco_mission
371, coco_rl 250, coco_sim 323, coco_web 862+1, coco_lab regionsearch +
searchbundle 40, vitest searchdecode 8, glue 6).

**Found and fixed (measured):** since `c921ec4` (2026-10-02) the DEFAULT
`mission.launch.py` died before starting anything: platform.launch.py
passed `origins` (default `*`) as a bare substitution and launch_ros
YAML-parses it ("Unable to parse the value of parameter origins as
yaml"). Now an explicit string; `test_web_assets.py::test_platform_launch_
parameters_evaluate_with_every_default`. Also: p03c's runner idiom
`check ... || exit 4` never exits (check returns 0); the Phase 5 runner
uses `must`.

**Gazebo, smoke only (not results):** overlay `~/coco_search_ws`
(`sync.sh`, `t.sh`, `run.sh`), evidence `~/coco_lab_runs/lab4/`.
- `smoke1_fixed_yellow`: INCOMPLETE -- the launch bug above.
- `smoke2_fixed_yellow` (code 9c574ee): every bring-up check PASS,
  including both nodes with an EMPTY region map, `search=true`,
  `search_mode=true`. Told "yellow" only, the mission chose bay_3 (as
  coco_lab predicts), climbed, saw blue in 100 perception lines, marked
  bay_3 searched (belief 0.3226/0.3226/0.0323/0.3226 = Bayes at d 0.9),
  `/ramp/retreat` backed down to x = 0.75 with 0.003 m drift, chose bay_4,
  climbed, FOUND yellow, stowed, approached, grasped, verified the grasp
  and entered DESCEND -- then the MACHINE REBOOTED (uptime reset; the
  session ended). INCOMPLETE, not a result. Cause of the reboot unknown.

**Gazebo is free now** (no simulator after the reboot). Next: the Lab 4
view (`lab_web/src/ui/search/`), then the 16-run matrix with
`~/coco_search_ws/run.sh NAME LEVEL SEED COLOUR [ORDER]`.

### Phase 5 — checkpoint: Lab 4 built, matrix RUNNING (2026-10-06, ~14:10 UTC)

Commits since d78a1d8: `3288cc0` site plumbing, `4327c2d` the Lab 4 view +
Live label from `/mission/search`, `9e0a954` SEARCH_FORMAT.md + extractor,
`f5d2a0d` browser checks, `03ce2bb` sim-time timeline from rosbag,
`28abcdf` write-up draft (LAB4_SEARCH.md §1-3), `ab87786` demo recorder,
`f3f366e` WEB_API + LIVE.md.

**The matrix is running** in the background since 13:05 UTC:
`~/coco_search_ws/matrix.sh` (= `docs/data/p05_matrix.sh`), overlay at
`d78a1d8`, ~28 min wall per run (16 runs ≈ 7.5 h). Resumable: rerun
`~/coco_search_ws/matrix.sh` after any interruption (a run dir without
result.json becomes `NAME.void-N` and is rerun). Log:
`~/coco_lab_runs/lab4/matrix_driver.log`. DO NOT `sync.sh` the overlay
while it runs (the runner reads from it).

- **A1_fixed_red COMPLETE (measured):** told "red", searched bay_3 (saw
  blue), bay_4 (yellow), bay_2 (green), found red in bay_1 at look 4,
  fetched, 0.016 m from home, 410.6 s sim, 0 recoveries, every runner check
  PASS. Its recorded search replays byte-identically through coco_lab
  (the robot chose exactly what coco_lab chooses).

Local browser checks (headless Firefox, `vite preview`): Lab 4 search flow
end to end incl. a Pyodide run (cold 17.6 s, coco_lab 22 ms), Replay of A1
with its FSM timeline, Evidence tab; phone width 390 px no overflow on any
tab; 0 console errors. vitest 283 (+8), live tests updated, tools 101 (+6)
+3 Lab 4 tool tests, tsc/build/check_dist clean.

**When the matrix ends:** `~/coco_search_ws/py.sh docs/data/p05_bagtimes.py
~/coco_lab_runs/lab4/matrix/*/`, then `python3 -P docs/data/p05_evidence.py
~/coco_lab_runs/lab4/matrix` (writes docs/data/lab4/{results.json,runs/,
replay/p05_matrix/}), finish LAB4_SEARCH.md §4-6, RESULTS.md "COCO Lab
Phase 5", PROJECT_STATE, ROADMAP; full `run_all_package_tests.sh` on a
quiet machine (`COCO_WS=~/coco_search_ws ROS_DOMAIN_ID=77`, after
sync.sh); PR lab4 -> main, CI; deploy; public checks; video
(`record_lab4_demo.py`).

### Phase 5 — checkpoint: matrix done, tests green, ready to deploy (2026-10-07, ~00:45 UTC)

**Matrix COMPLETE** (16 valid runs + 1 void; `docs/data/lab4/`, commit
`39b2303`): 14 COMPLETE (3 after one relocalisation on the return), 2 ABORT
— B2 `RETURN_FAILED` after a correct find + lift (AMCL 4.8 m from truth on
the return, monitor UNKNOWN; not attributed) and C1 `SEARCH_EXHAUSTED`
(the deliberate stop-after-the-first-bay order). 39 looks all agreed with
the truth; 24/24 retreats; lift 15/15; home error 0.016–0.169 m over the
14; every recorded search replays byte for byte through coco_lab. B3's
first attempt void (harness: leaked bag recorders exhausted DDS domain 64
participants; runner fixed `3ddfe74`, B3 rerun COMPLETE).

**Tests:** `run_all_package_tests.sh` **2,975 / 0 / 0** (overlay of
`e25f9c8`); vitest 286; tools 104; tsc/build/check_dist clean. Local
browser checks (full 16-run Replay): 0 console errors, phone width clean.
Docs: LAB4_SEARCH.md §1–7 (public-site §4.5 pending), RESULTS.md "COCO Lab
Phase 5", ROADMAP, PROJECT_STATE, LIVE.md, WEB_API.md. Branch pushed
(`labs/lab4`), PR #14 (draft).

**Waiting on:** the owner's approval to fast-forward `main` to `lab4` (the
Pages deploy runs from `main`; this session's rules forbid pushing/merging
`main` unasked). After that: verify the public site (`check.py
https://gauthamcodes.github.io/coco-labs/ <out> smoke search
search_phone`), record the video from it (`record_lab4_demo.py`), write
§4.5, tag `lab4-v1.0` locally + a DRAFT release (publishing is the owner's
call), checkpoint. Phase 6 NOT started.

### Phase 5 — deployed, verified on the public site, video, release notes (2026-10-07, ~02:10 IST)

The owner approved deploying Phase 5 to `main` ("approve deployment of
Phase 5 / lab4 to main"). `main` fast-forwarded `a63a4c8..0cb5588`. The
Pages deploy job then sat in `waiting` (~30 min) during a GitHub incident
("Several services are degraded"; `gh run cancel` answered HTTP 502); once
githubstatus said all systems operational, the run was cancelled and
re-run and the deploy succeeded (Pages deployment 6894319926).

- **Public site (measured):** catalog 1.4 from `0cb5588` (clean); headless
  Firefox 157 against the public URL: 0 console errors in Lab 1's smoke,
  Lab 4's two scenarios, Lab 2's and Lab 3's phone checks; the Lab 4 reveal
  9.1 s incl. the cold Pyodide start (coco_lab 9 ms); Replay loads with the
  truth toggle; no overflow at 390 px. `docs/data/lab4/public/report.json`.
- **Video (measured):** `record_lab4_demo.py` from the public site: 95.8 s,
  1,795 frames, 2 cuts listed, 0 console errors, sha256 `979ee7d5…`
  (`docs/data/lab4/video/`). Its matrix shows `COMPLETE (--)`; fixed after
  (`3529f8b`, outcome in words; extractor records no reason as null;
  provenance taken before rewriting tracked evidence, `f3b5d7b`). Evidence
  regenerated at `f3b5d7b` (clean).
- vitest 289 (3 view tests added). Release notes
  `docs/releases/lab4-v1.0.md`.

NEXT: push `lab4`, new PR for CI (the FF marked #14 merged), FF `main`
again (the release record + the cosmetic fix; same approval), re-check the
public page, tag `lab4-v1.0` LOCALLY + DRAFT release with the video —
publishing is the owner's call. Phase 6 NOT started.

### Phase 5 — COMPLETE (2026-10-07, ~02:20 IST)

- PR #15 (release record + cosmetic fix) CI green; `main` fast-forwarded
  `0cb5588..b554910` (same owner approval); Pages deploy succeeded; the
  public catalog is 1.4 built from `b554910` (clean); Lab 4 re-checked on
  the public URL: 0 console errors, the matrix without `(--)`.
- `lab4-v1.0`: annotated tag LOCAL at `b554910` + DRAFT GitHub release with
  `coco_lab4_demo.mp4` (2,505,787 B, sha256 `979ee7d5…`). Publishing is the
  owner's call:
  `git push labs lab4-v1.0 && gh release edit lab4-v1.0 -R GauthamCodes/coco-labs --draft=false --latest --verify-tag`.
- Phase 6 (Move) NOT started.

### Lab 4 released — `lab4-v1.0` published (2026-10-07, ~10:16 UTC)

The owner approved publishing `lab4-v1.0` ("approve lab4-v1.0",
2026-10-07), exactly as prepared.

Done:
- `git push labs lab4-v1.0` (annotated tag `f4f11da` → commit `b554910`).
- `gh release edit lab4-v1.0 -R GauthamCodes/coco-labs --draft=false
  --latest --verify-tag`. Published 2026-10-07T10:16:04Z, marked Latest.

Verified (measured, this session):
- `git ls-remote --tags labs` lists `lab4-v1.0` → `b554910`.
- `gh release list`: Lab 4 = Latest; Labs 1–3 and Live unchanged.
- The asset `coco_lab4_demo.mp4`, downloaded from its public URL, is
  2,505,787 B with sha256
  `979ee7d57ca367f6fb3ff89a2d88ebf5607cba7c8b76e840c1316b862ea97ed8`, the
  hash recorded at recording time.
- Both links in the release notes answer HTTP 200 (`?view=search` on the
  public site; `docs/labs/LAB4_SEARCH.md` at the tag).

Phase 5 / Lab 4 is SHIPPED. No engineering redone. `PROJECT_STATE.md` and
the ROADMAP status line updated to say so (on branch `lab4`; `main` stays
at `b554910`, the tagged commit).

NEXT: Phase 6 (Move, Lab 5) — NOT started: `docs/ROADMAP.md` §5 "Lab 5 —
Move" and §6.


## Phase 6 · Move (Lab 5) — survey, design and first Gazebo evidence (2026-10-07)

Branch **`lab5`** (from `1970e42`), worktree `.claude/worktrees/lab1` of the
old checkout, remote `labs`. Overlay `~/coco_search_ws` (reused from Phase 5:
`sync.sh`, `t.sh`; new `lab5.sh`, `ex.sh`), evidence `~/coco_lab_runs/lab5/`.

**State reconciled first.** `1970e42` (the Lab 4 release record, docs/state
only: PROJECT_STATE, ROADMAP, SESSION_LOG) was a direct descendant of
`main` = `b554910`. PR #16, CI green (build-and-test, plain-venv coco_lab,
lab_web), then `main` fast-forwarded `b554910..1970e42` by plain push. No
history rewritten.

**Survey findings (checked this session):**
- Nav2 1.3.11 here ships all three controllers: `nav2_dwb_controller`,
  `nav2_mppi_controller`, `nav2_regulated_pure_pursuit_controller`.
- Debug output each publishes (measured in the smoke bags): DWB
  (`debug_trajectory_details: true`, already the mission's) `/evaluation`
  = every scored candidate, **819 per control cycle** (the same count as run
  15's "0 of 819": same sampling config) — rejected ones carry `total -1`
  and the rejecting critic's raw score -1; `/local_plan`. MPPI (`visualize:
  true`) `/trajectories` = one SPHERE marker per sampled point (400 of 2000
  trajectories x 10 points), **stamps zero** (log time used), and
  `/optimal_trajectory`; no per-sample cost is published. RPP
  `/lookahead_point` (in **base_footprint**), `/lookahead_collision_arc`.
- No dynamic-obstacle infrastructure existed (only an unused
  `dynamic_obstacles.example.yaml` proposal); no D* Lite or replanning code.
- The robot's LiDAR is `gpu_lidar` (renders visuals); the world has
  UserCommands (`/world/coco_world/set_pose`); `gz.transport13` Python
  bindings are installed.
- The apron (map frame = world + (2, 0)): x -1.7..1.0, y -8.9..8.9, between
  the west corridor landmarks and the bays' approach walls; the robot spawns
  mid-apron at map (0, 0).
- Run 15 (v1 wedge world, M6 matrix) cannot be re-run as such: that world's
  corridor is not this arena. Its evidence is RESULTS.md's log excerpt and
  AMCL-vs-truth table. Plan: reproduce the MECHANISM (an operator
  `/initialpose` 3.4 m off — run 15's measured gap — then FollowPath) and
  label it a mechanism reproduction, never run 15.

**Design (decided here):**
1. `coco_lab_ros/config/nav2_move_overlay.yaml`: controller_server loads
   `FollowPath` (the mission's DWB, untouched), `MPPI`, `RPP` (Nav2 docs
   examples), every robot limit set to DWB's (0.3 m/s, no reverse, 1.0
   rad/s, accel 3.0/-2.5, yaw accel 3.2); MPPI model_dt 0.1 at the shared
   10 Hz. Merged onto a copy; mission file sha pinned (06c308af…).
2. Frozen global paths: SmacPlanner2D asked ONCE (`lab5_run.sh capture`),
   written to `coco_lab_ros/config/lab5_paths/` (room 13.020 m, 248 poses;
   apron 7.500 m, 151 poses; captured 11:17 UTC from source `1970e42`+WIP);
   `lab_planner path_file:=` sends that file unchanged with
   `controller_id:=FollowPath|MPPI|RPP`.
3. Scenarios (`coco_lab_ros/config/lab5_scenarios.json`): `static_room`
   (around the west spine's end, a hairpin, into the room), `crossing`
   (an actor crosses the apron at y -4.5, triggered at robot y < -1.8),
   `oncoming` (an actor walks up the robot's path, triggered at y < -1.0),
   `mislocalised` (`/initialpose` +3.4 m in y, run 15's gap).
4. Actors (`coco_lab_ros/actors.py`, node `lab_actors`): M7_DESIGN §2.6 —
   apron only (validated), grey Ø0.30 x 0.60 m, **visual only, no collision
   geometry**, gravity off, pose driven through gz `set_pose` at 20 Hz of
   sim time, robot-triggered from GROUND TRUTH, 0.25 m/s. Contacts are never
   felt; they are measured (clearance <= 0).
5. Metrics (`coco_lab.movemetrics`, fixed before measuring): tracking error
   (1C's: GT distance to the path polyline; mean, p95 nearest rank, max);
   travel time (FollowPath accept -> result, sim s); smoothness (RMS of the
   CONTROLLER's commanded dv/dt and dw/dt from `/cmd_vel_nav`); minimum
   clearance (exact footprint-rectangle 0.297 x 0.314 m to box / to actor
   cylinder, from GT and `navigation_world.json`).
6. D* Lite (`coco_lab.dstarlite`, Koenig & Likhachev Fig. 3) on the
   SearchGraph interface; `coco_lab.replan` = the episode (optimistic map,
   sense radius, scheduled world changes, A* from scratch beside every
   round); `coco_lab.movebundle` = replan bundle 1.0 + drive bundle 1.0.

**Found and fixed (measured):**
- D* Lite returned a cost 0.59 BELOW optimal on 3 of 400 random cases:
  equal keys formed in a different order differ in the last bit
  (7.242640687119286 vs …285) and ended the search one state early. Keys
  now compare within `KEY_EPS` 1e-9 — and the heap peek must use the SAME
  tolerant order (a second failure: an entry (…0955, 5.41) sat behind
  (…095, 11.66) in raw heap order). After both: 0 mismatches in 3,000
  random change sequences and 1,000-map properties.
- `lab1c_watch.py`'s parameter readback pattern is blind to a request that
  names ANY undeclared parameter: rclcpp then returns an EMPTY list and
  `zip` checks nothing (the first smoke "checked 63", silently skipping
  controller_server and local_costmap). `lab5_watch.py` falls back per name
  and fails a section that checks nothing: now 253 of 255 leaves checked,
  the 2 undeclared being pre-existing mission keys (`FollowPath.stateful`,
  a `static_layer` key on the local costmap). Phase 1C's own readback did
  check all 67 of its leaves (its committed params_readback.json files), so
  its evidence stands. (Corrected later this phase: this entry first said
  63.)
- `ros_clean.sh --list` matched an orphaned `target_finder` of ANOTHER
  workspace (`~/coco_m1_ws`, ROS domain 181, parent systemd --user), not
  started by this session. It was left alone; `lab5_run.sh` now sweeps only
  processes whose environment has its own `ROS_DOMAIN_ID` (66) and still
  refuses if any Gazebo runs.

**Smoke runs (static_room, one each — NOT results):** all runner checks
PASS, wheel topic publisher `cmd_vel_arbiter` only throughout.
- DWB: `FAILED_TO_MAKE_PROGRESS` after 43.7 s sim, stalled at map
  (-1.16, 7.06) before the hairpin, heading swinging, `Oscillation`
  rejecting 400 of 819 candidates per cycle.
- MPPI: succeeded, 55.2 s; tracking max 0.548 m (cuts the hairpin), min
  clearance 0.226 m.
- RPP: succeeded, 51.2 s; tracking max 0.175 m; lookahead point a median
  0.627 m from the true robot (lookahead_dist 0.6): frame chain verified.

NEXT: commit; then the measured matrix (A static_room, B crossing +
oncoming, mislocalised) with `~/coco_search_ws/lab5.sh run NAME SCENARIO
CONTROLLER`, extraction `~/coco_search_ws/ex.sh NAME...`; meanwhile the
Lab 5 view in lab_web.


### Phase 6 — checkpoint: matrix measured, Experiment C, Lab 5 page built (2026-10-07, ~16:40 UTC)

Commits on `lab5` (pushed to `labs/lab5`): `f64ba87` controllers/paths/
actors/D* Lite/metrics; `656264a` matrix driver + tests (the matrix ran from
this source, clean); `39ab63c` formats, decoders, the Move page, worker glue,
site build; `4cb984f` Experiment C capture; `89c69b1` evidence; `5cd039d`
write-up and docs.

**Measured (Gazebo, all in `docs/labs/LAB5_MOVE.md` §4 and RESULTS.md "COCO
Lab Phase 6"):**
- Matrix (54 runs, fresh simulator each, 0 void, every runner check PASS):
  static_room DWB 0/5 (105, stalled before the hairpin), MPPI 5/5 (corner
  cut, max tracking 0.554 m median), RPP 5/5 (closest); crossing 15/15, no
  contact; oncoming DWB 5/5 and MPPI 5/5 "reached" with contact 5/5 each,
  RPP 0/5 (104) with contact 5/5 after its abort — nobody swerved (≤ 0.261 m
  off the line), wheels at 0 m/s at every first contact; mislocalised 9/9
  failed in the first cycle with INVALID_PATH (103, "Resulting plan has 0
  poses"), gap 3.401–3.403 m — run 15's mechanism, NOT its "0 of 819".
- Actor visibility: crossing 1,523/1,523 in-view scans hit; oncoming 777/939.
- Experiment C (`snapshot_c1`, source `4cb984f`): 443 cells changed, 104
  newly blocked; D* Lite 3,209 expansions vs A* from scratch 1,114, same
  cost 160.598. Sketch seeds 0–199: D* Lite below A* in 191/200 episodes,
  above in 188/2,204 replans.

**Local site (headless Firefox):** 0 console errors; Replay, reveal, Run 15,
D* Lite run in Pyodide (5.8 s cold, coco_lab 158 ms), no overflow at 390 px.

**Tests so far (focused):** coco_lab dstarlite/replan/movemetrics/movebundle
+ lint; coco_lab_ros 68 (test_lab5 etc.); lab_web tools 117; vitest 307.
Full `run_all_package_tests.sh` running on the overlay of `5cd039d`.

**Corrected in this entry's predecessor:** Phase 1C's readback checked 67
leaves, not 63.

NEXT: full test totals into LAB5_MOVE.md §4.7; PR `lab5` -> `main`; CI;
fast-forward `main` (green-CI rule); public checks
(`check.py https://gauthamcodes.github.io/coco-labs/ OUT move move_phone smoke`);
video `record_lab5_demo.py`; release notes; tag `lab5-v1.0` LOCAL + draft
release (publishing is the owner's call).


### Phase 6 — deployed, verified on the public site, video, release gate (2026-10-07, ~18:00 UTC)

- **PR #17** (`lab5` → `main`): CI and Lab green on `0fef157` after one fix
  (the catalog-version pin 1.4 → 1.5; a local vitest run had used a catalog
  built before Lab 5). GitHub rejected every push for ~25 min (HTTP 500 at
  ref update, status page green, Actions queue stalled); nothing was forced,
  the push went through on retry.
- **`main` fast-forwarded `1970e42..0fef157`** (plain push, green-CI rule);
  both workflows green on `main`; Pages deployment 6916595601; the public
  catalog is 1.5 from `0fef157`, clean.
- **Public site** (measured, `docs/data/lab5/public/report.json`): 0 console
  errors in `move`, `move_phone`, Lab 1 `smoke` (11/11), `localise_phone`,
  `mapping_phone`, `search_phone`; D\* Lite in Pyodide 13.4 s cold (coco_lab
  95 ms); no overflow at 390 px on any Lab 5 tab.
- **Video** from the public site: 122.5 s, 3,615,891 B, sha256 `442cc010…`,
  2 cuts listed, 0 console errors (`docs/data/lab5/video/`).
- Release notes `docs/releases/lab5-v1.0.md`.
- **Evidence provenance:** drive bundles regenerated from clean `59a65b6`,
  Experiment C from clean `e5913c8` (its arrays byte-identical to the first
  build at `89c69b1`).

**Phase 6 acceptance (against the brief):** three controllers on identical
inputs — yes (54 runs, same frozen path files, hashes in every run);
metrics published — yes (RESULTS.md "COCO Lab Phase 6", LAB5_MOVE.md §4.1);
dynamic obstacles demonstrated — yes (crossing, oncoming; visibility 1,523
/ 1,523 and 777 / 939 scans); D\* Lite tested and integrated — yes
(coco_lab, worker, page, Experiment C); Lab 5 public — yes; video — yes;
write-up — yes; CI green — yes; no prior lab regressed — yes (package
counts unchanged outside coco_lab/coco_lab_ros; Labs 1–4 public checks
clean). **Run 15:** mechanism reproduced, its "0 of 819" symptom NOT —
stated everywhere it appears.

**Unverified:** physical robot; rates (5 runs per controller); why DWB
stalls at the hairpin, why no controller swerved, why D\* Lite out-worked A\*
on Experiment C, why oncoming scans miss; tuned controllers; D\* Lite in the
Nav2 loop.

NEXT: the owner's call on publishing `lab5-v1.0` (tag LOCAL at the release
record on `main`, DRAFT release with `coco_lab5_demo.mp4`):
`git push labs lab5-v1.0 && gh release edit lab5-v1.0 -R GauthamCodes/coco-labs --draft=false --latest --verify-tag`.
No later phase started.


### Phase 6 — COMPLETE: release record on `main`, `lab5-v1.0` tag local + draft release (2026-10-07, ~19:30 UTC)

- PR #18 (release record): Lab green; CI's `build-and-test` hung ~1 h in
  "Setup ROS 2 Jazzy" (before any repository code), was cancelled and
  re-run: green. `main` fast-forwarded `0fef157..2b6f8ad` (plain push).
- On `main` = `2b6f8ad`: CI, Lab and the Pages deploy green; the public
  catalog is 1.5 from `2b6f8ad`, clean. Re-checked on the public URL (19:25
  UTC): Lab 5 and Lab 1 smoke 0 console errors, 11/11 bundles drawn, D\*
  Lite in Pyodide 6.1 s (coco_lab 166 ms).
- `lab5-v1.0`: annotated tag LOCAL at `2b6f8ad` + DRAFT release (target the
  full sha) with `coco_lab5_demo.mp4`; the uploaded asset downloads with
  sha256 `442cc010…`, the hash recorded at recording time. Publishing is
  the owner's call:
  `git push labs lab5-v1.0 && gh release edit lab5-v1.0 -R GauthamCodes/coco-labs --draft=false --latest --verify-tag`.
- Phase 6 / Lab 5 is complete apart from that decision. No later phase
  started.


### Lab 5 released — `lab5-v1.0` published (2026-10-08, ~05:13 UTC)

The owner approved publishing `lab5-v1.0` ("approve lab5-v1.0",
2026-10-08), exactly as prepared. No Phase 6 engineering was redone.

Done:
- `git push labs lab5-v1.0` (annotated tag `4df59f9` → commit `2b6f8ad`,
  `main`'s release record).
- `gh release edit lab5-v1.0 -R GauthamCodes/coco-labs --draft=false
  --latest --verify-tag`. Published 2026-10-08T05:11:35Z, marked Latest.

Verified (measured, this session):
- `git ls-remote --tags labs` lists `lab5-v1.0` → `4df59f9`, peeled
  `^{}` → `2b6f8ad` (= `labs/main`).
- `gh release list`: Lab 5 = Latest; Labs 1–4 and Live unchanged.
- The asset `coco_lab5_demo.mp4`, downloaded from its public URL, is
  3,615,891 B with sha256
  `442cc010206399fcfc9c64314cd74f13c91e9a654032942775181182b4adb3cf`, the
  hash recorded at recording time.
- The release-note links answer HTTP 200 (`?view=move` on the public site;
  `docs/labs/LAB5_MOVE.md` at the tag), and so does the release page.
- The public site still serves catalog 1.5 built from `2b6f8ad` (clean);
  headless Firefox at 05:12 UTC: Lab 5 0 console errors, the Replay labelled
  "recorded real run", a D\* Lite run in Pyodide 7.3 s (coco_lab 186 ms).

Phase 6 / Lab 5 is SHIPPED. PROJECT_STATE and the ROADMAP status line say so
(on branch `lab5`; `main` stays at `2b6f8ad`, the tagged commit). No later
phase started.


## COCO Lab v2 · M0 Transition (2026-10-08)

The v2 master plan (`README.md`, "the Glass-box Arena") is installed as the
authority. Branch **`v2/m0-transition`** from `3571169` (coco-labs `main`
`2b6f8ad` fast-forwarded to `lab5`; two documentation-only commits), in
a fresh worktree `.claude/worktrees/v2-m0` of the old checkout, remote
`labs`. Copy overlay `~/coco_v2_ws` (`sync.sh`, `alltests.sh`,
`m0/*.sh`); Node 24.21.0 from the official tarball at
`~/coco_v2_ws/node`. No simulator was launched.

**Done (one commit per checkpoint, prefixed `[M0.n]`):**
- M0.1 starting state and preflight tests (`docs/v2/data/m0/START_STATE.md`).
- M0.2 annotated tag `coco-lab-v1-final` on `3571169`; the six releases are
  published (five with videos; `live-v1.0` has none, by design); the three
  Lab 1C bags cited by checksum resolve (`FREEZE.md`).
- M0.3 laptop baseline with Playwright 1.64.0 (new exact-pinned
  devDependency; `lab_web/tools/perf/baseline.mjs`), `docs/v2/BASELINE.md`,
  `docs/v2/PHONE_BASELINE.md` (+ `tools/perf/phone_marks.js`), RESULTS.md
  section "COCO Lab v2 · M0 baseline" (appended).
- M0.4 `README.md` = the master plan byte for byte; v1 README, ROADMAP,
  LAB_PHASES and retired CLAUDE.md rules in `docs/archive/v1/`; new
  `docs/ROADMAP.md`, `docs/STATUS.md`, `docs/IDEAS.md`; PROJECT_STATE and
  CLAUDE.md updated.
- M0.5 Remove: nothing to delete (no Isaac-in-Lab, VLM or browser policy
  training code exists; `REMOVALS.md`).
- M0.6 copy: "Live Stack (simulated)", no "real robot" for the Gazebo
  stack on the site, correction notes on three lab write-ups and the lab4
  release notes.
- M0.7 `FROZEN.md` in the nine robot-stack packages.
- M0.8 `docs/v2/DEPRECATIONS.md`.

**Measured (this session):** preflight at `3571169` packages 3,081 / 0 /
0, vitest 308 / 0 / 0, tools 117 / 0 / 0; after M0.8: packages 3,081 / 0 / 0,
vitest 308 / 0 / 0, tools 117 / 0 / 0. Laptop (MODEL): cold first edit
median 12,857 ms (6,567–42,882), warm edit median 1,445 ms
(1,265–1,686), every playing view 60 fps rAF, 0 long tasks. Exit load
check: plan/localise/map/search/move 0 console errors; Live logs browser
network errors when no Stack runs (same as v1).

**Unverified:** the phone baseline (method only); why cold start fell
39.7 → 3.9 s over five runs; why warm edits are slower than Lab 1.1's
Firefox numbers; CI on the PR at the time of writing.

NEXT: the owner reviews the PR `v2/m0-transition` → `main` and approves the
merge; a fresh review session verifies the M0 report (README §9.9); then
M1 · Glass-box Arena core (README §7), starting with M1.1 `coco_schemas`.
