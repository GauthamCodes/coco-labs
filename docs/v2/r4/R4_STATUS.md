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
| PR #38 Theta\* v1 claim | **merged** `4d52d63` 2026-11-22 (bot-commit runs approved via the API; exact head `242c5ab` all green; local verify VERIFIED, same numbers; tests 31/31); deployed run 45055100174; live smoke PASS 9/9; live board: Theta\* v1 held-out 20/20 and secret held-out 20/20 | PR #38 self-review, [deploy_a1](data/deploy_a1/) |
| MCL reference | **done**: 2,000 particles + injection; loc-global-20 public 1/20, held-out 1/6; loc-kidnap-20 0/20, 0/6: NOT shown solvable (closed-loop: driving on a wrong belief) | [mcl_reference](data/mcl_reference/README.md) |
| reference rows unranked; looks 1 and 3 | **done** (Waypoint driver and MCL reference pinned, greyed, unranked with a note; Model vs ROS 2 contents list; "scrolls sideways" on narrow screens) | `leaderboard.py REFERENCES`, test |
| Gazebo repeats 2-3 | repeat 2: 8/14 control+loc sessions DONE (RPP, DWB); MPPI x4, loc x2 and all of repeat 3 (14) left = 20 sessions; resumed 2026-11-22 19:33 UTC (`overnight_2026-11-23.log`); first session `ctrl-corridor-30_mppi_rep2` loaded calibration 1.323 on `~/coco_lab_r3_ws` | `~/coco_lab_runs/r3/r34/queue.log` |

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

(2026-11-22) R4 shipped and Part A merged (PR #41). Left: PR #38 (Theta\* v1 claim; its bot-commit runs were
approved through the API on 2026-11-22), then the Gazebo repeats 2-3 (20 sessions, `tools/r3/overnight_r34.sh LOG`
from this checkout, overlay `~/coco_lab_r3_ws`), then `tools/r3/finalize_r34.py`, `make -C docs/paper generated check`,
PR, merge under the gate, deploy, live smoke. `worktrees/r4` was removed after R4 shipped; this checkout
(`worktrees/r1`, branch `v2/r4a-loose-ends`) is the live one, and the overlay's symlinks point into it.

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
- **Correction (2026-11-22): the entry above is wrong.** Re-read from the run directories: every void try (7) came
  from the deleted `~/coco_lab_r2_ws` (`package 'gazebo_models' not found`; `/home/gautham/coco_lab_r2_ws/install/
  local_setup.bash: No such file`). The one session run on `~/coco_lab_r3_ws`, `ctrl-dynamic-30-noyield_dwb_rep2`,
  loaded the odometry calibration through the runner's own VOID guard (`tools/m6/m6f8_run.sh` 147-162:
  `wheel_separation_multiplier 1.323`, `calibration.txt`: "Double value is: 1.323") and finished DONE (rc 0). The
  installed `coco_controllers.yaml` reads 1.10 in the overlay AND in the source tree by design: the per-level
  `gazebo/diff_drive_calibration.yaml` is loaded over the running controller. **No rebuild is needed.**
- That session spans **670 min of wall clock with no runner output** (02:26:07 -> 13:36:43 UTC) against ~40 min for
  repeat 1: most likely a suspend (the lid) -- the journal for 2026-11-11 has rotated, so UNRESOLVED. Kept as is
  (`~/coco_lab_runs` is read-only evidence): its results are sim-time and match repeat 1's (10 SUCCEEDED / 5
  ABORTED both; 13/15 scenarios the same status; 1,550 vs 1,387 sim s); flagged here and in the finalize notes.
- 2026-11-22: `leaderboard-reverify.yml` on main has been **cancelled at its 6 h limit** on 62096d1, 5a9f54d and
  0dff353 (and was still running on 4d52d63 at deploy): pre-existing since R3 (more entries, v1 suites); the R3/R4
  deploys shipped without it and so did this one. Open for Gautham (shard it or raise the limit).
- 2026-11-22: the laptop's Playwright browsers had been deleted (cleanup); the first smoke attempt failed before
  reaching the site. `npx playwright install chromium` (the pinned 1.64 build), smoke re-run against the same deploy
  with its tab opened before the Deploy job: PASS.
- 2026-11-22 23:19-23:39 UTC: `loc-track-30_pf_rep2` VOID x4 (`package 'coco_user_particle_filter' not found`):
  the r3 overlay never held the `coco_user_*` packages (repeat 1 ran on the deleted r2 overlay; the runner's comment
  "r3's holds the same packages" was wrong for these). Fixed 2026-11-23 ~17:00 UTC: the starter exported with
  `python -m coco_lab.ros2_export` into `~/coco_lab_r3_ws/user_src/` and built into that overlay (`algorithm.py`
  sha256 `de1102c9...` = repeat 1's logged file). Only the pf sessions use a `coco_user_*` package in this queue;
  `loc-track-30_pf_rep2` is re-run by starting `overnight_r34.sh` again once the queue ends (DONE sessions skip).
- 2026-11-23 02:36-15:43 UTC: `ctrl-corridor-30_dwb_rep3` **spanned a suspend** -- journal: "Lid closed" 08:06:56
  IST, "System returned from sleep" 20:27:20 IST (12.3 h). Kept (read-only evidence); results are sim-time and in
  range: 14/20 SUCCEEDED (rep1 14/20, rep2 15/20), 3/20 scenarios differ from rep2.
