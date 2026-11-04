# R2 · Bring Your Own Algorithm — status

Prompt: [`R2_PROMPT.md`](R2_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-11-04).

## Now

- **State (2026-11-04): R2.0 Baseline done** ([`data/r20/README.md`](data/r20/README.md)): main `4894c76`'s tree is R1's
  final tree byte for byte (`git diff 8b40a41 4894c76` empty), so R1.9's committed suites are its baseline; a re-run
  here gave coco_lab 1191 passed + 1 failure caused by an R2 file appearing in the tree mid-run (fixed in R2.1), and was
  stopped before steps that would have measured R2 work. Before screenshots = R1.9's after set (same tree), checksummed.

## Setup facts

- Base: `origin/main` `4894c76` (Merge PR #30, R1 · Research Workbench — merged 2026-11-04 16:21Z, so R2 branches from
  main, not from `v2/r1-workbench`). Branch `v2/r2-byoa`. Worktree `~/coco_labs_ws/worktrees/r2` (created with
  `git worktree add`; the session's own worktree tool accepts only `.claude/worktrees/` paths, so work happens there
  by absolute path).
- Test venv `~/coco_labs_ws/r1_venv` (Python 3.12.3, CI pins from `coco_lab/requirements-test.txt`), reused: it holds
  only pinned third-party packages; `coco_lab` is reinstalled into it from this tree by the suite runner.
  ROS overlay `~/coco_lab_r2_ws` (`scripts/build_overlay.sh`). Node 24.21.0 (`~/coco_v2_ws/node/...`).
- Laptop at start: power profile **power-saver, on battery (AC 0)**; ~9.1 GB disk free. No simulator running.
  Timing measurements only on balanced + AC (original profile restored afterwards).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R2.0 Baseline | done | [`data/r20/README.md`](data/r20/README.md) |
| R2.1 API and security design | | |
| R2.2 Sandboxed worker | | |
| R2.3 Algorithm Studio | | |
| R2.4 Compare, experiments and native | | |
| R2.5 Share links | | |
| R2.6 Leaderboard | | |
| R2.7 Run in ROS 2 | | |
| R2.8 Phone and Learn | | |
| R2.9 Close | | |
