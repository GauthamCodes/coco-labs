# ADR 0015 · The Learn course: `coco.lesson.v1` and exact, answer-seeded grading

- **Status:** accepted 2026-11-10 (R4.1).
- **Context:** R4 (Gautham, 2026-11-10) turns Learn into a course: predict, observe, explain, try, check,
  "In real ROS 2", in three tracks, graded automatically and exactly, free, no account, on a phone.

## Decision

1. **Two kinds of data, one schema id.** Lessons (text, links, claims) are YAML in `lab_web/course/NN-<id>.yaml`,
   checked at build by `lab_web/tools/course.py` (shape; Explain ≤ 250 words; every claim's evidence resolves as a
   mission's does, or to a checked primary source in `docs/v2/r4/SOURCES.md`; anything unverified must say
   `[CHECK]` and is listed). Everything gradeable -- questions, misconception notes, exercises, grading contracts,
   hints -- is JSON in coco_lab (`coco_lab/coco_lab/course/exercises.v1.json`), with starter and reference files
   in `course/files/`, so the grader runs natively and in CI without the site. Both carry `coco.lesson.v1`;
   growth is additive within v1 (new exercise types or check kinds), a breaking change is v2 with a converter.
2. **One grader.** `coco_lab.course.grade(exercise, answer)` grades every type -- predict (choice/tick/cell),
   tune (built-in parameters), failure (a tick of a recorded MODEL run), code and benchmark (an algorithm file
   through the R2 guard) -- and returns `coco.lesson.grade.v1` with a digest. The browser calls the same function
   in the Studio's sandbox worker (op `grade`); a completion link is re-verified by calling it again. A predict's
   immediate feedback on the page is equality with the data's answer (the grader's own rule).
3. **Exact checks, never text.** Checks compare deterministic counts and properties -- success, path length
   against the reference solution on the same scenario, summed expansions against a baseline, minimum clearance,
   contacts, no path cell inside a no-go zone, a function's return values against the reference's, resampling
   properties -- each with its measured value, target and scenario, so the page can open the scenario in Compare.
   Thresholds are measured, not guessed (each exercise's window is recorded in `R4_RESULTS.md`).
4. **Hidden scenarios seeded by the answer.** Public scenarios come from the exercise's seed. Hidden ones are
   drawn by COCO-Bench's generator from `sha256("coco.lesson.v1.hidden" | id | seed | sha256(answer))`: a file
   that hard-codes the public scenarios (or any draw it has seen) meets scenarios it has never seen; change one
   character and the draw changes. A **tune** answer is parameters only (nothing to hard-code), so its hidden set
   is the exercise's own and moving a slider does not redraw it. There is no secret: the course is
   self-verified, not proctored, and anyone can recompute both sets.
5. **Progress and links without accounts.** Progress is one pref (`coco.prefs.v1.course`, prefs.ts's try-guarded
   storage), exportable as a file. Completion and assignment links carry deflate-compressed JSON in the URL
   fragment (never sent to a server). A completion link's pass/fail is recomputed; its hints and name are
   declared by the learner and shown as such. Stars count help honestly (3 no hint; 2 the first two hint levels;
   1 the third hint or the reference solution, which unlocks only after a real attempt).

## Consequences

- Browser and native grading agree by construction (the same Python); CI checks every reference passes, every
  starter and every committed wrong solution fails with a message, and that hard-coding fails the hidden set
  (`coco_lab/test/test_course.py`).
- The grader is trusted code: the learner's file runs only through the R2 guard, in the browser inside the
  locked-down worker (ADR 0012). Long built-in runs beat the worker's watchdog every tick.
- Not a proctoring system: a determined learner can read the reference solution from the site's files. The
  course says so on every completion link.
