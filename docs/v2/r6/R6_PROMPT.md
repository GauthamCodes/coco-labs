# Claude Code prompt — R5 follow-ups, then R6 · Fidelity, more algorithms, multi-robot

Run on the laptop: `cd ~ && claude`, Opus at the highest effort, the lid open, `gh auth status` logged in. To resume
later, paste only: *Continue COCO Lab R6: read docs/v2/r6/R6_PROMPT.md and R6_STATUS.md, then carry on.*

Continue COCO Lab (repo GauthamCodes/coco-labs), starting from main (63a97f6 or later). Worktree
`~/coco_labs_ws/worktrees/r6`, branch `v2/r6`. Save this prompt as `docs/v2/r6/R6_PROMPT.md`, track progress in
`R6_STATUS.md`, commit `[R6.n]` per step and push. Ship each part as its own PR, merged and deployed under the gate
with the live smoke test.

All earlier rules and the standing authority still apply, including R5's rules against guessing:

- reuse what exists, and list it first
- install or run every package, API and command to check it before relying on it
- a feature counts as done only if a test or a recorded run shows it working; list everything else as "not verified"
- labels are MODEL, STACK and LIVE
- never invent numbers
- one simulator at a time, and never while Gautham's FR3 or Isaac work is running
- disk: keep at least 8 GB free, and never delete `~/coco_lab_runs/`

## Part A · R5 follow-ups (Gautham's decisions, 2026-11-28: record them in STATUS)

- **Image size:** trim it first: a multi-stage build, no build tools or docs in the final layer, only the levels it
  needs. Target ≤ 3.5 GB. If it can't get under 4.0 GB without dropping a feature, report the size and what each
  part costs, and keep the 4.0 GB budget.
- **foxglove_bridge 3.6.3 ignoring its allowlist:** don't file anything. Write a minimal reproduction and a
  ready-to-paste upstream issue in `docs/v2/r6/UPSTREAM_foxglove_issue.md`, after checking the upstream tracker for an
  existing report and linking it if one exists. Gautham files it himself.
- **The 2 m position offset:** investigate it. Compare the gateway's "true pose" source with Gazebo's ground truth,
  and check frame origins, the world offset in the generated SDF, and the map origin in the YAML. Fix it if the cause
  is ours. Show a true-vs-estimated distance only when the two agree within 0.05 m on a test route.
- **Moving actors:** forklifts and people must move in the image and in level packages, as they do in the browser and
  the R3 gate, using the existing G2.9 scenario-rule actor driver. Test that they move and yield in one Depot round.
- **`~/Downloads/COCO_Lab_STATUS.md`:** rewrite it as a 1–2 page plain-English summary covering v2 through R5: what
  exists, the live links, key numbers (each with its evidence path), open issues, and what's next. Also commit it as
  `docs/OVERVIEW.md`.
- **WebKit:** rely on CI; don't rebuild it locally.

The decided carry-overs:

- the localisation v1.1 suites `loc-global-active-20` and `loc-kidnap-active-20`, with the robot allowed to stop or
  explore until it reports "localised", and time-to-localise scored; re-run the built-ins and the MCL reference
- the leaderboard re-verify split into a matrix (one job per suite × entry, each under 1 hour), re-checking only
  entries whose versions changed

## Part B · R6 (each item: model + tests + Workbench/Compare support + a short Learn note)

**Fidelity knobs**, all deterministic and seeded, with every knob off by default:

- LiDAR range noise and dropout
- odometry slip, using the measured Gazebo values (turn scale 1.10 before calibration, and the measured residuals) as
  presets, each one cited
- command latency
- acceleration limits

Turning a knob on changes the experiment spec and is shown on every result. Knobs off must leave every golden and hash
byte-identical.

**More algorithms**, each in the plan/control/localise API with reference tests and COCO-Bench baselines:

- planners: RRT, RRT* and PRM (seeded), Theta* as a built-in (credit Gautham's leaderboard entry), Hybrid-A* (a simple
  Reeds-Shepp or Dubins version, stating which)
- localisation: EKF with scan matching, if it can be done honestly; otherwise report why not

**Multi-robot (2–4 COCOs):**

- each robot gets its own TF namespace in SIM view
- prioritised planning and CBS (conflict-based search) on the grid
- a new suite, `multi-depot-30`, with metrics: makespan, sum of costs, conflicts and deadlocks
- Compare and Workbench support
- a Free Drive mode where you drive one robot and the others run AUTO

Scope it as MODEL only. LIVE multi-robot in Docker is out of scope; note it as future work.

**Ship order:** Part A as 1–2 PRs, then B1, B2 and B3 as separate PRs, each merged and deployed under the gate.

## Stop and report if

- A golden or model hash changes with knobs off.
- An algorithm's reference test can't be made deterministic.
- Disk would drop below 8 GB.
- Any change would need the COCO robot repo.

## Final report

- Part A: image size before → after; upstream issue draft path; 2 m offset (cause, fix, error after); actors moving
  (evidence); OVERVIEW.md; loc v1.1 results; leaderboard matrix (job count, longest job)
- Part B: knobs (list, off = identical? evidence); algorithms (list, baselines); multi-robot (planners, suite results,
  deadlocks)
- Not verified (honest list):
- Tests, determinism, parity, Play fps:
- PRs, merges, deploys, live smoke:
- Questions for Gautham:
