# R6 status — R5 follow-ups, then Fidelity, more algorithms, multi-robot

Prompt: [R6_PROMPT.md](R6_PROMPT.md). Worktree `~/coco_labs_ws/worktrees/r6`, branch `v2/r6` (from main `63a97f6`).
Resume: *Continue COCO Lab R6: read docs/v2/r6/R6_PROMPT.md and R6_STATUS.md, then carry on.*

## Gautham's decisions, 2026-11-28 (R5 follow-ups)

1. Image size: trim first (multi-stage, no build tools or docs in the final layer, only the levels it needs), target
   ≤ 3.5 GB; if it can't get under 4.0 GB without dropping a feature, report each part's cost and keep the 4.0 GB budget.
2. foxglove_bridge 3.6.3 ignoring `client_topic_whitelist`: file nothing; write a minimal reproduction and a
   ready-to-paste issue (`UPSTREAM_foxglove_issue.md`), linking an existing upstream report if there is one.
   Gautham files it.
3. The ~2 m gateway truth offset: investigate; fix if ours; show true-vs-estimated distance only when they agree
   within 0.05 m on a test route.
4. Actors must move in the image and in level packages (the G2.9 scenario-rule driver); test move + yield in one
   Depot round.
5. Rewrite `~/Downloads/COCO_Lab_STATUS.md` as a 1–2 page summary of v2 through R5; commit it as `docs/OVERVIEW.md`.
6. WebKit: rely on CI; no local rebuild.
7. Carry-overs: localisation v1.1 suites (`loc-global-active-20`, `loc-kidnap-active-20`) and the leaderboard
   re-verify matrix.

## Machine and disk (2026-11-28)

- Laptop: balanced, AC; no simulator, Isaac or FR3 process; `gh` logged in.
- Disk: 11 GB free before the worktree, **9.7 GB after** (floor 8 GB). So: **no local Docker build or pull of
  coco-ros2** (the pulled image takes 5.42 GB on this Docker's containerd store, measured in R5). Every image build,
  size measurement and container run happens in CI (`.github/workflows/coco-ros2-image.yml`, which now also triggers
  on `v2/r6*` pushes). Nothing reclaimable without touching Gautham's own caches (browser caches 1.3 GB) or the
  Playwright browsers the tests need.

## Steps

| step | state | evidence |
| --- | --- | --- |
| R6.0 prompt, status, worktree | done | this file |
| A1 image trim | in progress: CI breakdown of the current image first | — |
| A2 foxglove issue draft | pending | — |
| A3 2 m offset | pending | — |
| A4 moving actors | pending | — |
| A5 OVERVIEW.md | pending | — |
| A6 loc v1.1 suites | pending | — |
| A7 re-verify matrix | pending | — |
| B1 fidelity knobs | pending | — |
| B2 algorithms | pending | — |
| B3 multi-robot | pending | — |

## A1 · image size

What exists (reused): `docker/coco-ros2/Dockerfile` is already three stages (levels → overlay → runtime);
the workflow measures `docker image inspect` and `du /` against `MAX_IMAGE_BYTES` and records `docker history`.

Before (main `78b662b`, CI run 45956389403, `history.txt`): 3,797,579,707 bytes (inspect). Layers: the runtime
stage's one `apt-get install` **3.01 GB**; the `ros:jazzy-ros-base` base underneath it: ros-core 413 MB, **build
tools 303 MB** (build-essential, git, colcon, rosdep: the prompt's "no build tools in the final layer"), ros-base
84 MB; our overlay 21.5 MB and levels 7.5 MB. Per-package breakdown: `docker/coco-ros2/size_breakdown.sh`, run by CI
inside the image (`size_breakdown.json` in the artifact).
