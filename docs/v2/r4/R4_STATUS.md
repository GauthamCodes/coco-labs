# R4 · Learn Course (and R3's loose ends) — status

Prompt: [`R4_PROMPT.md`](R4_PROMPT.md) (Gautham, 2026-11-10).

## Gautham's decisions (2026-11-10)

- Set `COCO_HELDOUT_SECRET` myself, never exposing it; commit only its commitment (ADR 0014).
- A stronger localisation reference: **yes** ("MCL reference", labelled reference, slow, own row); the 60-particle
  built-ins' 0/40 and 0/60 stay visible as negative baselines.
- Reference rows are never ranked: the Waypoint driver and the MCL reference are pinned, greyed, unranked, with a
  one-line note; the other two BEFORE_AFTER "looks" are fixed the same way (honest, smallest fix).
- Gazebo repeats 2–3 for control and localisation only while the laptop is otherwise free.
- The paper: nothing submitted; Gautham decides.

## Part A · R3 loose ends (branch `v2/r4a-loose-ends`, checkout `worktrees/r1`)

| item | state | evidence |
| --- | --- | --- |
| secret set | **done** 2026-11-10 13:19:42 UTC; commitment `e3195c2f…52ebd7` | [secret](data/secret/README.md), [commitments](../r3/HELDOUT_SECRET_COMMITMENTS.md) |
| proof: verifier run with the secret | **done**: PR #38, results run 42824431748, secret held-out 20/20 | [secret](data/secret/README.md) |
| proof: attack tests | **done**: 3 runs; run 1 FAIL under R3's check (the accepted T5 residual matched a coordinate < 10; R3 had passed by formatting); check fixed honestly; runs 2–3 PASS | [secret](data/secret/README.md) |
| PR #37 (deploy record) | **merged** `60c6e1f` (exact head 4da1587, 5/5 green) | PR #37 self-review |
| PR #38 Theta\* v1 claim | VERIFIED; the writer's commit `242c5ab` needs its 3 CI runs **approved** (refused to me as self-approval) | PR #38 |
| MCL reference | **done**: 2,000 particles + injection; loc-global-20 public 1/20, held-out 1/6; loc-kidnap-20 0/20, 0/6: NOT shown solvable (closed-loop: driving on a wrong belief) | [mcl_reference](data/mcl_reference/README.md) |
| reference rows unranked; looks 1 and 3 | **done** (Waypoint driver and MCL reference pinned, greyed, unranked with a note; Model vs ROS 2 contents list; "scrolls sideways" on narrow screens) | `leaderboard.py REFERENCES`, test |
| Gazebo repeats 2-3 | **running overnight** 2026-11-10 20:56 UTC, guarded (`tools/r3/overnight_r34.sh`); finalize + paper macros next session | |

## Part B · R4 (branch `v2/r4-learn`, worktree `~/coco_labs_ws/worktrees/r4`)

| checkpoint | state | evidence |
| --- | --- | --- |
| R4.0 Baseline | — | |
| R4.1 Lesson engine | — | |
| R4.2 Modules 1–2 | — | |
| R4.3 Modules 3–6 | — | |
| R4.4 Modules 7–10 | — | |
| R4.5 Progress and teaching | — | |
| R4.6 Glossary and accessibility | — | |
| R4.7 Grading integrity | — | |
| R4.8 Close | — | |

## Machine log

- 2026-11-10 ~18:45 IST start: no simulator, Isaac, FR3 or `~/franka_ws` process; **AC offline, power-saver**;
  disk 3.9 GB free (so Part A works in `worktrees/r1`, switched from the merged, clean, pushed R3 branch).

## Next step

MCL reference probes → reference rows → Part A PR; R4.0 in parallel.
