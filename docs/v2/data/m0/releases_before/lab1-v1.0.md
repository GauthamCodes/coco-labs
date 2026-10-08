<!-- Published GitHub release text as fetched with `gh release view lab1-v1.0` on 2026-10-08, before the M0 fix A.4 wording edit. Metadata (must be unchanged after): {"tagName": "lab1-v1.0", "isDraft": false, "isPrerelease": false, "targetCommitish": "main", "publishedAt": "2026-10-01T06:06:30Z", "assets": [{"name": "coco_lab1_demo.mp4", "size": 2005151}]} -->

# Title

COCO Lab 1 — Plan (v1.0)

# Body

**Try it:** https://gauthamcodes.github.io/coco-labs/ · the
exhibit: https://gauthamcodes.github.io/coco-labs/?view=exhibit

COCO Lab's first lab, **Plan**: graph search for robot path planning, in
the browser, on the maps a real robot used. Five algorithms are traced
event by event: BFS, Dijkstra, A\*, greedy best-first and weighted A\*.
Every search runs in `coco_lab` (Python, in your browser via Pyodide); the
page never searches. Write-up, every claim's evidence and the limitations:
[`docs/labs/LAB1_PLAN.md`](https://github.com/GauthamCodes/coco-labs/blob/lab1-v1.0/docs/labs/LAB1_PLAN.md).

### In the lab

- **Settings.** coco_lab's admissibility verdict for each heuristic, and
  the guarantee for each algorithm. With an admissible heuristic, weighted
  A\* gives cost ≤ w × the optimum (a property tested on 1,000 maps).
- **Race mode.** Two to four algorithms on identical inputs, advanced
  together by expansions, after you predict which expands the fewest.
- **Painting.** Paint walls and erase them; coco_lab reruns the search.
- **The map ladder.** A teaching grid, then the arena, then Nav2's own
  inflated costmap, with COCO's footprint swept along the path.
- **Three real runs.** Planned by coco_lab and driven by Nav2, with ground
  truth, AMCL belief, the plan, a tracking-error plot and provenance.
- **Share links.** A link reproduces your exact trace, checked by digest.
- **The exhibit, "The A\* myth, twice".** A\* against Dijkstra, live; COCO's
  6.2 % (planner implementations, neither reproduced nor refuted); and the
  ISRO "4 %" (a reconstruction, not reproduced).

### Measured (headless Firefox 156; details in `docs/RESULTS.md`)

| | target | public site |
|---|---|---|
| full-arena playback (283,378 events) | ≥ 60 fps | 60.03 fps, 0 frames > 25 ms |
| paint a cell → first frame, warm | ≤ 1.5 s | 1,137–1,159 ms |
| share link → "reproduced the exact trace" | works | 3 of 3 |
| phone width 390 px, horizontal scroll | none | none (378 px) |

Tests: `coco_lab` 349 / 352, `lab_web` tools 72, vitest 180; 0 failed, 0
skipped.

Real stack (Phase 1C, 2026-09-29): Smac's raw A\* cost equals coco_lab's
optimum on 36 / 36 pairs. In three real runs, A\* and Dijkstra succeeded and
greedy aborted.

### Limitations

- Measured in headless Firefox on one machine. A headed browser, Safari,
  Chrome and a real phone are not measured.
- Three real runs are not a rate.
- The first change pays Pyodide's start-up (3–95 s across this lab's
  measurements, set by the CDN).
- 1C recorded the exhibit's analogue paths as lengths, not coordinates, so
  they are not drawn.

### The video

`coco_lab1_demo.mp4`: 65.3 s, 1120 × 920, recorded from the public site by
`lab_web/tools/browser/record_demo.py`. It captures the headless browser's
viewport only, at real pacing. **One cut:** the one-time Pyodide start-up
and a warm-up search (6.6 s) happened before recording began. The captions
were added to the page by the recorder; they are not part of the site.

