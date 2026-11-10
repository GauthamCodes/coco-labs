# R4 · Learn Course — results

Branch `v2/r4-learn`. Evidence: MODEL (the browser model, coco_lab) unless a line says STACK. Phone results are
EMULATED (the Nothing Phone (1) was not connected). Part A (R3's loose ends) is in [R4_STATUS](R4_STATUS.md).

## The course

| | count |
| --- | --- |
| modules | 10 (find a path · costmaps · the world changes · following a path · where am I · building a map · moving things · where to look · why it failed · browser to ROS 2) |
| lessons | 20: Explorer 10, Builder 8, Researcher 2 |
| exercises | 39: predict 25 · tune 2 · find-the-failure 2 · code 9 · benchmark 1 |
| claims | 66, every one resolving to committed evidence or a checked primary source ([SOURCES](SOURCES.md), 13 checked statements; 3 of my draft statements were wrong and are corrected there); **0 `[CHECK]`** |
| glossary | 54 terms (ROS 2 terms included) |
| diagrams | 10 own SVGs, Okabe-Ito palette, no colour-only distinction |

Format and grading: [ADR 0015](../adr/0015-lesson-format-and-exact-grading.md) (`coco.lesson.v1`; one Python
grader, answer-seeded hidden scenarios, exact checks, progress and links without accounts).

## R4.7 · grading integrity (`coco_lab/test/test_course.py`, `test/course_wrong/`)

For every code exercise: the reference passes, the starter fails, and at least three plausible wrong solutions fail
with a message; a file that hard-codes the public scenarios fails the hidden ones (four planners and three
function exercises tested).

| exercise | reference | wrong solutions caught | hard-coding |
| --- | --- | --- | --- |
| m1-heuristic (A*'s heuristic) | pass | h = 0, 3 x octile, Manhattan | fails hidden |
| m1-dijkstra | pass | the empty loop, BFS (FIFO), unit diagonals, geometric-only | fails hidden |
| m1-bench (Researcher) | pass | straight line, greedy, depth-first | fails hidden |
| m2-inflation (Nav2's formula) | pass (= `coco_lab.costmap`) | rounding, no radius offset, 253 scale, strict radius | lookup table fails hidden |
| m3-nogo | pass | zone ignored, x only, swapped axes | fails hidden |
| m4-lookahead | pass | 1.5 m, 2.0 m, 3.0 m | n/a (one constant) |
| m4-goal (Nav2's goal checker) | pass | no angle wrap, strict boundary, no yaw, Manhattan | lookup table fails hidden |
| m5-resample | pass (= the filter's own step) | identity, uniform, argmax, off by one | n/a (properties on fresh weights) |
| m6-logodds | pass (= `coco_lab.occgrid`) | clamp at the end, no clamp, swapped | lookup table fails hidden |
| m10-export | pass | straight line, `import os`, a syntax error | — |

**Negative results, kept** ([course_wrong_uncaught](../../../coco_lab/test/course_wrong_uncaught/README.md)):

- The first full run was 69/75. BFS and "stop on first push" **passed** the first Dijkstra exercise: on an
  8-connected grid with uniform step costs the shortest paths are also fewest-step paths. Fixed by what Dijkstra is
  for: the exercise now uses the costmap's costs (BFS caught at 1.19-1.66x the optimal cost).
- "Stop when the goal is first pushed" is **not caught** even then (its path cost equalled the optimum on every
  public and hidden scenario); "block only lethal cells" is **not caught** in the benchmark (with the cost weight
  the optimal paths never enter an inscribed cell). Both documented, not hidden.
- Two answers meet their targets as stated and are not wrong: lookahead 1.0 m (clearance 0.03-0.05 m against the
  reference's 0.13-0.18 m; Nav2 RPP's own maximum is 0.9 m) and weighted x5 A* in the benchmark (median ratio
  1.005 / 1.026 hidden).
- The clearance tune: its first target (1.15x the shortest paths' mean clearance) was above what ANY setting reaches on the public routes (1.126-1.129x for every weighted setting); now 1.10x (weight 0 gives 1.0x and fails), measured on the fixed hidden set too (1.21-1.24x). Test run 75/76 before, 76/76 after.
- The weighted-A* tune window moved when the hidden set was fixed per exercise: w 2.5-4.0 passes (w <= 2.0 needs
  more than half of A*'s expansions on the hidden routes; w = 5 makes a path 11.7 % longer).

**Browser = native:** `lab_web/tools/r4/course_check.mjs` entered 7 answers on the built site (4 references, 2 wrong
files, slider values) and every grade digest equalled the native one ([course_check.json](data/r47/course_check.json));
one mismatch found on the way (a slider sent `3`, Python `3.0`: same grade, different digest) was fixed by
normalising parameter values.

## R4.5 · progress and teaching

Browser check 15/15: a completion link made from the passed lessons re-verifies in the browser; an assignment link
carries no student data; the class dashboard re-verified two links and reported a damaged one; the CSV export
(cells quoted, formula-looking text neutralised). Unit tests: `lab_web/test/r4_course.test.ts` (links round-trip,
damaged and foreign links refused, names stripped of markup, stars, progress import).

## R4.6 · accessibility and phone

- Accessibility (WCAG AA contrast, every control focusable, reduced motion, no sideways scroll): **28/28** course
  pages (home, predict, explain, code try, glossary, teacher, progress × desktop + emulated phone × dark + light)
  ([a11y.json](data/r46/a11y/a11y.json)). Found and fixed: the editor in the light theme (45 contrast failures).
- Phone (EMULATED Nothing Phone (1), landscape, 4x CPU): an Explorer lesson played end to end by taps, graded on
  the phone (first check 39 s, booting Python), no sideways scroll on any step
  ([phone_explorer.json](data/r46/phone_explorer.json)). Real phone: not connected.

## Study

[STUDY.md](STUDY.md): 30-minute protocol for 5-8 people (modules 1-2), consent note, anonymous results template.
Gautham runs it.
