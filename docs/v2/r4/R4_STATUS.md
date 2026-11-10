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
| MCL reference | probing | |
| reference rows unranked; looks 1 and 3 | to do | |
| Gazebo repeats 2–3 | to do (laptop on battery at the start: AC offline) | |

## Part B · R4 (branch `v2/r4-learn`, worktree `~/coco_labs_ws/worktrees/r4`)

| checkpoint | state | evidence |
| --- | --- | --- |
| R4.0 Baseline | before-screenshots taken from the live site (desktop + emulated phone, 9); suites: main's CI on `60c6e1f` (CI, Paper green); local heavy suites deferred to the close (the laptop was on battery) | `screens/before/` |
| R4.1 Lesson engine | `coco_lab.course` (coco.lesson.v1, ADR 0015): 5 exercise types, answer-seeded hidden scenarios, 14 check kinds; `test_course.py`; sandbox ops `grade`/`inspect`; the course pack | `docs/v2/adr/0015-lesson-format-and-exact-grading.md` |
| R4.2 Modules 1-2 | content done; UI written, typechecked, unit-tested (`test/r4_course.test.ts` 9); site build + screenshots in progress | `lab_web/course/`, `lab_web/src/course/` |
| R4.3-R4.4 Modules 3-10 | content done (20 lessons total, 66 claims, 0 evidence problems, 0 [CHECK]) | |
| R4.5 Progress and teaching | written (progress pref + file export, completion links, verify page, assignments, class dashboard + CSV) | |
| R4.6 Glossary, a11y, phone | glossary 54 terms; 10 SVG diagrams (Okabe-Ito, never colour alone); audit and phone pass to do | |
| R4.7 Grading integrity | first full run 69/75: 6 failures, each analysed -- see below | |
| R4.8 Close | — | |

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
