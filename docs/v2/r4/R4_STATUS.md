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
| R4.0 Baseline | done: before-screenshots from the live site (9); suites: main's CI on `60c6e1f`; local heavy suites at the close | `screens/before/` |
| R4.1 Lesson engine | done: `coco_lab.course`, ADR 0015, `test_course.py`, sandbox ops, the course pack | ADR 0015 |
| R4.2 Modules 1-2 | done, end to end in the browser; 30 look-review screenshots (desktop + emulated phone) | `screens/r42/`, [BEFORE_AFTER](BEFORE_AFTER.md) |
| R4.3-R4.4 Modules 3-10 | done (20 lessons, 66 claims, 0 evidence problems, 0 [CHECK]) | `lab_web/course/` |
| R4.5 Progress and teaching | done: browser check 15/15 (completion link re-verified, class dashboard, CSV) | `data/r47/course_check.json` |
| R4.6 Glossary, a11y, phone | done: 54 terms; a11y 28/28; Explorer on the EMULATED phone 6/6 (real phone not connected) | `data/r46/` |
| R4.7 Grading integrity | done: every code exercise's reference passes, >= 3 wrong solutions caught, hard-coding fails hidden; browser = native 7/7; 2 uncaught bugs documented | [R4_RESULTS](R4_RESULTS.md) |
| R4.8 Close | **shipped**: PR #39 merged `5a9f54d` under the gate, deployed (run 42893898506), live smoke PASS, a code exercise passed on the live site (digests = native) | [deploy](data/deploy/README.md) (PR #40) |

### R4.7 findings so far (kept; negative results stay)

- BFS (FIFO) and "stop when the goal is first pushed" PASSED Dijkstra on the Proving Ground's easy routes:
  probing harder Depot routes.
- Lookahead 1.0 m PASSES the lookahead exercise even on harder corner routes (clearance 0.03-0.05 m vs the
  reference's 0.13-0.18 m): not a grading hole -- it meets the stated target (reach every goal, no contact,
  body never in a wall) just above Nav2 RPP's own 0.9 m maximum. Recorded; the wrong solutions are 1.5, 2.0, 3.0 m.
- Weighted x5 A* PASSES the benchmark (median ratio 1.005 public, 1.026 hidden): a valid planner meeting a median
  target. Recorded; the third wrong solution is now "blocks only lethal cells" (a real bug).
- The hard-coding test was wrong itself (keyed on the unsnapped start); fixed.
- The tune exercise's window moved once the hidden set was fixed per exercise: w 2.5-4.0 passes; hint corrected.

## Machine log

- 2026-11-10 ~18:45 IST start: no simulator, Isaac, FR3 or `~/franka_ws` process; **AC offline, power-saver**;
  disk 3.9 GB free (so Part A works in `worktrees/r1`, switched from the merged, clean, pushed R3 branch).

## Next step

MCL reference probes → reference rows → Part A PR; R4.0 in parallel.

## Interruptions

- 2026-11-11 02:15-02:35 UTC: the Gazebo queue voided `ctrl-corridor-30_mppi_rep2` four times (the simulator never
  published /scan). Cause, my own: the session runner's default overlay `~/coco_lab_r2_ws` had been deleted in the
  disk cleanup an hour earlier (`gazebo_models` not found). No data affected: the 7 finished repeat-2 sessions kept
  their DONE markers; the void tries are kept (`*_void2..4`). Fixed by defaulting to `~/coco_lab_r3_ws` (the same
  packages; `tools/r2/ros2_session.sh`, `tools/r3/overnight_r34.sh` now refuses to start without an overlay) and
  restarting the queue, which skips DONE sessions.
- 2026-11-11 02:25 UTC: the restart on `~/coco_lab_r3_ws` voided at once: that overlay's `diff_drive_controller` has
  `wheel_separation_multiplier` 1.1 (built 2026-11-06, before G2's calibration to 1.323 reached it), so it is NOT the
  deleted r2 overlay's equal. The queue was then killed with the laptop (exit 143, 13:51 UTC); no data affected
  (the void tries are kept). Needed before the repeats can resume: rebuild the overlay from the current tree
  (`scripts/build_overlay.sh ~/coco_lab_r3_ws`), with the laptop otherwise free. On 2026-11-13 it was running
  Gautham's e-Yantra task3b simulator, so the rebuild and the repeats wait.
