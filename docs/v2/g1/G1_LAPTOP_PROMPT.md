# G1 · laptop prompt (2026-10-22)

Gautham's prompt for finishing G1 on the laptop, saved as given. Progress: [`G1_STATUS.md`](G1_STATUS.md).

## Before you start (Gautham)

- Merge PR #25 on GitHub (CI green; merging publishes nothing).
- Plug in the charger, switch to the balanced power profile, and close Isaac Sim, Gazebo and any
  other agent. `~/franka_ws` can stay untouched; just don't run the FR3 launch at the same time.
- If you can, plug in the Nothing Phone (1) with USB debugging on.
- Start Claude Code in a terminal: `cd ~ && claude`, choose Opus with /model, and pick the
  highest effort it offers.

To resume later, paste only:

> Continue COCO Lab G1 laptop work. Work only in ~/coco_labs_ws/worktrees/g1. Read
> docs/v2/g1/G1_LAPTOP_PROMPT.md and docs/v2/g1/G1_STATUS.md there, then carry on from the next step.

## The prompt

You are finishing G1 · Game Look for COCO Lab on Gautham's laptop. All of G1 was built in the
cloud on branch `claude/serene-davinci-v9y796`, which is PR #27 (draft) at `8849a91`. Several
checks can only run here: the real GPUs, the phone, ROS and Gazebo. Codex is no longer used.

### 0. Setup and rules

- Create a worktree: `git -C ~/coco_labs_ws/src/coco-labs fetch origin`, then
  `git -C ~/coco_labs_ws/src/coco-labs worktree add ~/coco_labs_ws/worktrees/g1 claude/serene-davinci-v9y796`.
  Reuse it if it exists.
- Save this prompt as `docs/v2/g1/G1_LAPTOP_PROMPT.md`. Keep progress in `G1_STATUS.md`.
  Commit `[G1.13] …` per step and push to the same branch.
- Rebuild what the 22 October cleanup removed. Many colcon `build/` and `install/` folders and
  `node_modules` were deleted.
  - Build a colcon overlay for this worktree (`--symlink-install`).
  - Run `npm ci` in `lab_web`, and create a Python venv with CI's package list.
  - Don't touch other workspaces, `~/franka_ws` or the eYRC `~/ros2_ws`.
- The rules from `G1_PROMPT.md` all hold:
  - Never merge, deploy (the "Deploy site" button) or release.
  - No destructive git commands; never delete evidence; never invent numbers.
  - Balanced profile on AC; record the machine state with every measurement.
  - One simulator at a time; never Gazebo `--fast`; clean up with the repository's cleanup script.
  - Never use `~/ros2_ws(personal)` or the COCO robot repo for this work.

### 1. Gautham's decisions on the G1.12 questions

Record them in G1_STATUS and STATUS's plan-change log, dated 2026-10-22.

- **Phone round budget:** use the smallest budget, from 22 m up, that gives at least 3 distinct
  rounds with every timer ≤ 5:00. If none does, keep 22 m (one round, 4:36). Don't move objects
  next to the lanes. Regenerate the references and update GAMES.md.
- **Spawn heading:** face the clear heading closest to the direction of the first route, still
  ≥ 1.5 m from the lanes.
- The camera look in "After G1.12" is approved.

Commit these first.

### 2. The laptop-only items

- **AUTO tick gaps:** run `fetch_timing.mjs` (before = `a4b39a6`, after = head) on the laptop. The
  target is no model-tick gap over 100 ms around an AUTO press. If it's missed, find the cause and
  fix it once, then re-measure.
- **Real-GPU frame rates** for title, Play (Depot, Fetch Rush, 10 minutes) and four-pane Compare:
  - both GPUs (NVIDIA and Intel)
  - the default and high tiers
  - Record the median, minimum, p95 frame time, any context loss, and the driver versions.
- **The Nothing Phone (1)**, if `adb devices` lists it: run M5's USB/CDP procedure on the phone's
  own network.
  - cold start stages
  - Play fps for 1 and 10 minutes
  - touch-to-motion latency
  - battery level and temperature
  - check `PHONE_PROFILE.md`'s viewport and safe-area assumptions
  - Set the default tier and frame-rate cap from these results. If the phone isn't listed, mark it
    pending and say so in the report.
- **Four-engine determinism:** the full 100-session v2 corpus in Chromium, Firefox, WebKit and
  Pyodide-in-Node, plus the v3 native-vs-Pyodide gate.
- **ROS package suites** in the overlay (`coco_lab_ros` and the rest), and `pytest -m gz` for the
  gz-marked tests.
- **M6F.4**, the Depot planning benchmark, only if it is not already in
  `docs/v2/m6/RESULTS_M6_FOUNDATIONS.md`: run it in CPython and Pyodide, 5 repeats.
- **M6F.8**, Gazebo + Nav2 on the Depot, following `docs/v2/m6/M6F8_PLAN.md`:
  - launch the generated Depot SDF headless with COCO, plus Nav2 with the generated map and params
  - a smoke test across the zones; record each goal as STACK evidence
  - then record one real ROS 2 ghost of a Fetch Rush phone round (driving legs only), converted
    with the ROS-to-event adapter
  - raw logs go to `~/coco_lab_runs/m6/`; summaries and checksums go into the repository

### 3. Close G1

- Rerun every suite, write the laptop numbers into `G1_RESULTS.md` (keeping the cloud numbers
  labelled as cloud), and fill in `BEFORE_AFTER.md` with screenshots from the real GPU.
- Update PR #27's description. Mark it ready for review, but don't merge it.
- Note in the PR that it already contains PR #24 (M6 foundations), so #24 can be closed once #27
  merges.

### 4. Final report

Steps done (G1.13 …); branch, SHAs, pushed, clean; decisions applied (phone budget chosen —
rounds, timers — and spawn heading); AUTO tick gaps (before / after, met or not); real GPU (per
GPU and tier — median / min / p95, context loss); phone (results, or "not connected"; defaults
chosen); determinism (four-engine v2, v3 gate); ROS suites and gz tests (passed / failed /
skipped); M6F.4 benchmark (results or "already done"); M6F.8 Gazebo + Nav2 (per-goal results,
ghost recorded with checksum, problems); tests (all suites); PR #27 (ready for review, CI status);
questions for Gautham; next step.
