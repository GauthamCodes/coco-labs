# M5.7 Compare — implementation and verification

M5.6 baseline: `8b426db`; foundations: `440f7e3`, `0254dea`.
The following final implementation supersedes the foundation-only progress notes below.

## Final workspace

Two/four scissored viewports share one WebGL context, map, seed, start, goal, camera,
costmap settings and timeline. Portrait panes stack; controls become a bottom sheet
and results swipe horizontally. Floor picking and numeric goals, four costmap layers,
cell hover, lethal/inscribed contours and A/B/both difference patterns are available.
Blue expanded cells retain their semantic colour; stripe directions distinguish sets.

All six existing global planners, three existing local controllers and MCL with/without
injection plus EKF run their Python reference implementations. D* Lite displays its
native first-plan trace; it does not claim to replay historical repair work. Local
comparisons use a stated 60-tick window (optional 200), common 12-beam sensors and
60-particle teaching profile, shared commands/relocation and unchanged non-compared
settings. Results show actual model-window compute time, truth travel, clearance and
window outcome. Unrecovered/window-incomplete results remain visible. Timings in
these functional captures are not device performance claims.

Seven original missions retain claims and evidence inside guided tours, with existing
mapping/decision Inspect continuations. Five additional story tours each cite committed
evidence and retain unresolved caveats; see TOUR_EVIDENCE.md. Mapping comparison is
parked for M7 in docs/IDEAS.md.

Play vision now requests a view-only costmap snapshot. It adds no simulation tick,
input or hash-chain event; historical views explicitly report missing cost snapshots.

### Final checks

- All 12 package suites passed (`packages-closure.txt`); after the byte-preserving
  v2 encoder optimization, affected coco_lab passed 834 (`packages-cached.txt`).
- Web: 486 passed (`vitest-cached.txt`); tools: 204 (`tools-final.txt`); typecheck
  and production build passed (`build-cached.txt`).
- Eight layouts: final/checks.json under screens/compare, one context, no scroll,
  zero console errors, desktop 1440×900/844×390 and both emulated Nothing Phone (1)
  orientations. All desktop algorithm families: families-cached/checks.json.
- Twelve tours and frozen Play costmap hash/input-log checks: closure-live/checks.json.
- 50 URL forms + six archive views pass (`urls-final/v1_links_check.json`); five replays pass (`replays-final/replay_check.json`).
- Five legacy canvases are pixel-identical (`canvases-final/screenshots.json`).
- ADR 0009 records measured serialization overhead and byte-preserving optimization.
  Both recursive reference encoding and optimized encoding match eight hashes saved
  before the change, including MCL/EKF, with mutation/type/alias/cache-bound tests.
  V1 layout and golden fixtures were not edited.

Earlier failed/timeout/selector runs are retained. Localization originally exceeded
browser timeouts because repeated v2 JSON encoding dominated the model window; the
fix caches only exact byte-validated content, without dropping any behavioural field.
No physical robot or real-phone performance claim is made.

## Foundation history (retained)

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
  views form a two-by-two grid and portrait views stack. The final workspace wires both two and four views.

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
