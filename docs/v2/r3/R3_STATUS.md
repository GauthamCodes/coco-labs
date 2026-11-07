# R3 · COCO-Bench v1 and the paper — status

Prompt: [`R3_PROMPT.md`](R3_PROMPT.md) (Part B; Part A in [`LANDING_STATUS.md`](LANDING_STATUS.md)).
Branch `v2/r3-bench-paper` from main `5df4427` (PR #32 merged; main merged in again after PR #33).
Worked in the `~/coco_labs_ws/worktrees/r1` checkout (this session is pinned to it; `worktrees/r3` was
not created). Overlay for local package tests: `~/coco_lab_r3_ws` (symlink-install of this checkout).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R3.0 A1 follow-up tooling + Gazebo runs | tooling done; queue running (Theta\* costs session done: 0/5 again; A\* starter and stock costs sessions, then 3 snapped planning sessions) | `tools/r2/ros2_bench.py` (`--snap`, `--costs`), `tools/r3/ros2_queue_a1.sh`, `tools/r3/a1_costs.py`; raw `~/coco_lab_runs/r3/a1/` |
| R3.1 COCO-Bench v1 suites, tiers, datasheets | 12 suites frozen; `make_suites_v1.py --check` byte for byte; `test_bench_v1.py` 13/13; lint clean; conditions smoke-run. To do: suites in the browser (Benchmarks tab, Studio picker); datasheet `--check` in CI | `coco_lab/coco_lab/benchmarks/*.v1.json`, `docs/bench/v1/` |
| R3.2 Browser-model baselines | not started (needs the CPU: waits until the Gazebo queue is done) | |
| R3.3 Held-out from a secret (ADR 0014) + hostile tests | implemented (inline scenarios, `tools/r3/heldout.py`, the verifier's `heldout`, the trusted job, the writer); `test_r3_heldout.py` 11/11; functional run outside docker passed. To do: hostile check in the real container (`tools/r3/hostile_check.py`, after Gazebo), then ADR 0014 accepted or rejected; the repository secret | `docs/v2/adr/0014-held-out-secret-salt.md` (proposed) |
| R3.4 Gazebo + Nav2 baselines | not started (after A1) | |
| R3.5 Gap analysis, "Model vs ROS 2" page | not started | |
| R3.6 Leaderboard v1 | not started | |
| R3.7 The paper | draft: sections, 43 macros from data, suite table, tier figure, checked bibliography (18), venues; `make check` passes; PDF builds in CI only (no TeX here; downloading Tectonic was refused by the permission check). Experiments section waits for R3.2/R3.4/R3.5 | `docs/paper/` |
| R3.8 Launch kit | drafts: demo script, LinkedIn, résumé, architecture SVG; CITATION.cff + Cite section on About. To do: README front page | `docs/launch/`, `CITATION.cff` |
| R3.9 Close | — | |

## Part A open items

- PR #32 merged `5df4427` (2026-11-06). PR #33 (writer scope, found landing #31) merged `90c3dce`.
- PR #34 (leaderboard index generated at build, found landing #31: the committed index went stale
  when the writer committed a result) — CI running. After it: GitHub "update branch" on PR #31 (no
  local checkout needed), approve the bot's runs if asked, merge #31; deploy; live smoke.
- PR #31 history: verify passed on `01b8794`; the writer re-committed `result.json` (`06a1cc9`)
  because R2's held-out seed hashes the merge-base, which moved; the runs on `06a1cc9` were approved;
  Lab failed there only on the stale index (fixed by #34).

## Decisions

- 2026-11-07 (Gautham): no affiliation on the paper or in CITATION.cff; author "Gautham".

## Machine log

- 2026-11-06: start balanced/AC (profile changed from power-saver; restore at the end). AC went offline in
  the evening; the A1 queue waits for AC + balanced before every session.
- 2026-11-07: battery reached 5 %; the laptop restarted (session resumed ~07:40 IST, AC back, balanced).
  All work had been pushed; the queue was restarted at ~08:05.

## R3.1 smoke (MODEL, one run each, on battery: a functional check, not a measurement)

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

MCL runs took ~11 min each on one core: the localisation baselines need the worker pool and hours.

## Interruptions

- 2026-11-08 ~00:42: the laptop rebooted during depot-nav-100/localisation (183/300; partial runs discarded,
  the family re-runs from the start). The five finished suite/family sets kept their DONE markers and were
  skipped on restart (00:55, same command, `--workers 10`); the R3.4 queue re-chained behind the baselines.

## Next step (updated 2026-11-08 ~02:40)

1. **R3.2** baselines running (restarted after the reboot). Committed and checked: arena-nav-50 ×3,
   depot-nav-100 planning/control (`f398617`). As each further set finishes: `check_carried.py` for
   depot-narrow-30, commit the set, `builtin_bench` for it (reference entries; done for the first five, `8c580ba`),
   `docs/paper/scripts/tables.py` (the baseline tables list unfinished sets as not yet run).
2. **R3.4** starts by itself after the baselines (`tmp/chain_r34.sh` → `tools/r3/ros2_queue_r34.sh`); then `gap.py` →
   `docs/v2/r3/data/r35/gap.json` and the Model vs ROS 2 tab.
3. Leaderboard page with the new control/localisation boards: check rendering in the close's screenshots.
4. After R3 merges: Theta\*'s v1 claim PR (`9ca4d58`); the repository secret `COCO_HELDOUT_SECRET` + commitment.
5. R3.9 close.
