# R1.3 Builder and results

Evidence class: MODEL (results) / TESTED (checks). Screenshots are regression references; Gautham judges the look.

## What was added (`lab_web/src/workbench/`)

- `WorkbenchApp.tsx` at `?view=workbench` (Experiments · Benchmarks · Recordings · Datasets; Benchmarks and
  Datasets arrive at R1.5–R1.6; Recordings is today's library at `?view=research`).
- `Builder.tsx`: the form (title, family, world, seed; algorithms with their common parameters and "all
  parameters"; scenarios — seeded random pairs with zones/stratification/reachability, a suite, hand-placed
  pairs, or a full task's committed rounds; a one- or two-parameter sweep; time limit and kidnap) and the same
  spec as JSON or YAML text (`yaml` 2.8.1, lazy-loaded), applied both ways. A size warning above an estimated
  amount of work (stricter on phones). `coco_lab.experiments.plan` in the worker is the authority; its refusal
  is shown with its reason.
- `Results.tsx`: progress bar (pause, resume, cancel keeping partial results, ETA labelled "this device");
  a live count while running; then the summary per algorithm (N, success k/n with Wilson 95%, outcomes, the
  chosen metric's N · median [IQR]); charts (`charts.tsx`): success bars with Wilson whiskers, box plots
  (IQR box, median, min–max whiskers, N), a scatter (one point per run; selecting one opens it in Compare),
  a sweep line with the IQR band, a two-parameter heatmap; the paired comparison (pairs used and excluded,
  median difference, Hodges–Lehmann, rank-biserial r, Wilcoxon p with Holm and its method, the plain verdict,
  McNemar for success; the reason when a test is undefined); and every run in a sortable, filterable table
  with a Failures filter and a Replay link (at the failing tick for a failed run).
- `meta.json` (`tools/r1/build_meta.py`, kept current by `lab_web/tools/test_r1_generated.py`).
- Phones get at most two workers; after Run the page scrolls to the progress and results.

## Checks

| Check | Result |
| --- | --- |
| typecheck; vitest (whole suite) | pass; 623 tests, 81 files |
| build; `check_dist` | pass; title-critical app + worker 308,095 gzip bytes (baseline 304,656; budget 350,000) — the worker carries the experiment entry points; the Workbench itself is a lazy chunk |
| [`a11y/a11y.json`](a11y/a11y.json) (`tools/r1/a11y_check.mjs`, M5.11's audit): Workbench with a finished 16-run experiment, Benchmarks, Datasets × dark/light × desktop/emulated phone landscape | **passed**: 12 pages, 0 contrast failures (AA), 0 unfocusable controls, reduced motion honoured, no horizontal page scroll |
| [`palette.txt`](palette.txt): the 8 categorical slots, `validate_palette.js` | dark: every check PASS (worst adjacent CVD ΔE 8.4); light: PASS but contrast WARN for aqua, yellow, magenta (< 3:1) — relief rule: every chart has a legend, shapes per algorithm, and its table |
| the experiment in the a11y run (browser, Chromium) | 16 runs on 6 desktop workers / 2 emulated-phone workers, summary and paired test computed by coco_lab in the worker |

Colour-blind safety: identity is never colour alone — each algorithm has a fixed colour slot **and** a
shape, a legend, direct N labels, and the same numbers in a table.

Screenshots: [`a11y/`](a11y/) (full pages; desktop 1440 × 900 and emulated Nothing Phone (1) landscape,
dark and light). The phone run is emulated (viewport, touch, 4× CPU throttle on this laptop), not a phone.
