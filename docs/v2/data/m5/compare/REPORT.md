# M5.7 Compare — implementation in progress

M5.6 is committed at `8b426db`. This substep establishes the costmap and
viewport foundations; it does **not** complete M5.7 or any later checkpoint.

## Implemented

- `coco_lab.costmap`: static occupancy, current LiDAR obstacle marks,
  an inflation halo and their maximum combined layer. Uses the existing
  exact Euclidean distance transform. Costs are 254 lethal, 253 inscribed,
  otherwise truncated `252 exp(-k (d-r))` within the inflation radius.
- Circular MODEL radius is the inscribed radius. This is explicitly not a
  polygon-footprint reconstruction or Nav2's persistent obstacle layer.
- Additive `costmap.layers` header/cell channels, generated Python/TypeScript
  messages, column-table checks and a separate M5 cross-language corpus.
  The historical M2 corpus remains byte-for-byte unchanged.
- An optional Compare worker request builds a separate costed graph, emits
  all four layers and uses it for both planners. The original request keeps
  the original graph. Neither path assigns Arena state, radius or graph.
- Additive two/four-planner worker request, validated before execution; each
  pane uses the same independent graph/start/goal, with distinct trace IDs.
  Legacy scene callers retain the two-pane contract.
- One-context scissor rectangle support for 1/2/4 views; four landscape
  views form a two-by-two grid and portrait views stack. The current visible
  Compare screen still requests two views; UI wiring is next.

Formula reference: [Nav2 Jazzy InflationLayer::computeCost](https://api.nav2.org/nav2-jazzy/html/inflation__layer_8hpp_source.html).
The upstream unsigned-byte cast truncates the positive exponential value.

## Evidence and checks

| Check | Result | Evidence |
| --- | --- | --- |
| Hand-computed bands, diagonal distance, scan projection and family batching | 16 passed | `coco_lab/test/test_costmap.py`; included in package run |
| Optional inflation preserves state bytes, hash, chain and graph for v1/v2 and 2/4 panes | 4 passed | `glue-four-panes.txt`, `lab_web/tools/test_costmap_glue.py`; earlier 2-case run retained |
| Build-tool suite | 197 passed, before 195 | `tools-costmap.txt` |
| Web suite | 482 passed, before 477; repeated after request extension | `vitest-four-panes.txt`; first run retained |
| Cross-language schema subset | 22 passed | `web-schema.txt` |
| Scissor tiling/no overlap/portrait order | 3 passed | `pane-layout.txt` |
| Typecheck | passed after four-pane request extension | `typecheck-four-panes.txt` |
| Production build | passed; existing chunk-size warning retained | `build-costmap.txt` |
| Generated schemas and legacy/new vectors | current | `schema-generation.txt`, `legacy-vectors.txt`, `m5-vectors.txt` |
| Affected package suites | coco_lab 821 passed, 3 lint failures; coco_schemas 231 passed | `packages-costmap.txt` |
| Corrected copyright/import/indent/docstring lint issues, plus costmap tests | 19 passed | `lints-fixed.txt`; original failures retained in `lints-initial.txt` |

The 197-test tool suite preceded the request extension; the expanded four-case
integration test was rerun after it.

The affected-package run exercised all existing functional/golden tests;
its failures were new-file copyright/style/docstring checks. Their focused
rerun is green. Full checkpoint suites will run at M5.7 closure.

## MODEL vs recorded STACK costmaps

`stack-costmap-comparison.json` compares both full committed Lab 5 before/after
snapshots, without editing them. Reproduce with:

```bash
PYTHONPATH=coco_lab /home/gautham/coco_labs_ws/test_venv/bin/python -P \
  lab_web/tools/compare_costmap_stack.py --out /tmp/coco-m57-costmap.json
```

Lethal recorded cells seed inflation; unknown cells are excluded from scoring.
Two declared parameter profiles compare a circular 0.20 m radius with the
padded 16-gon apothem derived from 0.20 + 0.01 m. The measured differences
remain in the JSON; neither profile is labelled Stack-equivalent. Historical
snapshot metadata records configuration hashes, so current committed settings
are a declared comparison, not proof of the historical merged runtime values.

Conditions are captured in `CONDITIONS.json`: balanced, AC, NVIDIA RTX 4050,
driver 580.178.04. These are numeric comparisons and functional checks, not
startup/frame-rate measurements. The profile was not changed. ADB found no
connected phone; real-phone acceptance remains pending USB. No new emulated
phone result or physical-device claim is made by this substep.

## Exact remaining work

Wire 2/4 panes and costmap layers/hover/band outlines into Compare; add the
required existing global/local/localization families; implement difference,
lockstep timeline, measured results and evidence-backed tours; test all old
routes/replays/hashes and capture desktop plus both emulated Nothing Phone (1)
orientations. Then finish M5.7 and proceed M5.8–M5.11 in order.

No whole files moved or removed, no new ADR/owner decision, no parked idea,
no new world/game/algorithm beyond authorized costmap inflation. No stop
condition hit. Earlier screenshots remain awaiting Gautham's soft review.
