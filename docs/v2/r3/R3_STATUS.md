# R3 · COCO-Bench v1 and the paper — status

Prompt: [`R3_PROMPT.md`](R3_PROMPT.md) (Part B; Part A in [`LANDING_STATUS.md`](LANDING_STATUS.md)).
Branch `v2/r3-bench-paper` from main `5df4427` (PR #32 merged). Worked in the
`~/coco_labs_ws/worktrees/r1` checkout (this session is pinned to it; `worktrees/r3` was not created).
Overlay for local package tests: `~/coco_lab_r3_ws` (symlink-install of this checkout).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R3.0 Start, A1 follow-up tooling | in progress | `tools/r2/ros2_bench.py` (`--snap`, `--costs`), `tools/r3/ros2_queue_a1.sh` |
| R3.1 COCO-Bench v1 suites, tiers, datasheets | in progress: 12 suites written and frozen; `make_suites_v1.py --check` regenerates all 12 byte for byte; `test_bench_v1.py` 13/13, ament lint clean; every new condition smoke-run once (below). To do: the suites in the browser (Benchmarks tab, Studio picker), datasheet `--check` in CI | `coco_lab/coco_lab/benchmarks/*.v1.json`, `docs/bench/v1/` |
| R3.2 Browser-model baselines | — | |
| R3.3 Held-out from a secret salt (ADR 0014) + hostile tests | — | |
| R3.4 Gazebo + Nav2 baselines | — | |
| R3.5 Gap analysis, "Model vs ROS 2" page | — | |
| R3.6 Leaderboard v1 | — | |
| R3.7 The paper | — | |
| R3.8 Launch kit | — | |
| R3.9 Close | — | |

## Machine log

- 2026-11-06: start balanced/AC (profile changed from power-saver; restore at the end). Later the same day
  AC went offline (battery discharging, 98 %): the A1 Gazebo queue was stopped before any simulator started;
  it now waits for AC + balanced before every session (`on_ac` in the queue).

- 2026-11-07 (after midnight): still on battery (33 %, discharging). Work committed and pushed; a suspend
  would stop local runs, which resume from the last commit.

## R3.1 smoke (MODEL, one run each, laptop on battery: a functional check, not a measurement)

| suite / scenario | algorithm | status | note |
| --- | --- | --- | --- |
| depot-clutter-50 c001 | A* | found | 55.3 m |
| depot-long-50 l001 | D* Lite | found | 48.4 m |
| ctrl-dynamic-30 d001_yield | RPP | no_valid_control | ended at 59.9 s; cause not yet examined |
| ctrl-dynamic-30 d001_no_yield | RPP | succeeded | 1 contact |
| ctrl-corners-30 t001 | DWA | succeeded | |
| loc-global-20 g001 | MCL + injection | timeout (300 s) | final error 21.9 m: not localised |
| loc-kidnap-20 q001 | MCL + injection | timeout (300 s) | final error 28.7 m: no recovery |
| loc-track-30 p001 | EKF | localised | final error 0.139 m |

Cost: MCL runs took ~11 min each on one core: the localisation baselines need the
worker pool and hours; budgeted in R3.2.

## Part A open items

- PR #32 merged `5df4427` (2026-11-06). PR #33 (leaderboard scope fix, found landing #31) merged
  `90c3dce` (2026-11-07) after green CI on `a47a20e`.
- PR #31: retargeted to main; main merged in (`01b8794`, pushed); waiting for its verify + writer +
  CI runs on that head. Then merge under the gate; deploy (`gh workflow run lab.yml --ref main -f
  confirmation=DEPLOY`); live smoke (Playwright on the public URL).
- On `01b8794` the verifier passed (run 42276302298) and the trusted writer re-committed
  `result.json` (`06a1cc9`): R2's held-out seed hashes the PR's merge-base, which moved from
  `5df4427` to `90c3dce` when main was merged in, so the held-out set and the result legitimately
  changed (same-repo branch: overwritten, as PR #33 intends). The bot commit's runs needed approval
  (`action_required`); approved through the API (runs 42277291466 verify, 42277291467 CI,
  42277291430 Lab). On `06a1cc9` the merge-base is unchanged, so the writer should find the same
  result and make no further commit. Merge #31 once those are green.
- Battery reached 5 % at that point (no charger since the evening of 2026-11-06): a suspend is
  expected; resume here.

## Next step

Finish Part A (above). Then R3.1: `python tools/r3/make_suites_v1.py --check`, the condition smoke
(`actors`, global init, kidnap), tests for `bench_v1`, the suites listed in the browser. The A1 Gazebo queue
(`tools/r3/ros2_queue_a1.sh`) starts by itself when AC + balanced are back.
