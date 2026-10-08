# v1 baseline — what v2 is measured against (M0.3)

Measured 2026-10-08 on `coco-lab-v1-final` (`3571169`), before anything in
M0 touched the site. Every number below comes from a file in
[`docs/v2/data/m0/`](data/m0/), produced in this session. Evidence class:
**MODEL** (the browser site, `coco_lab` under Pyodide). Nothing here is a
STACK, REMOTE or HARDWARE measurement.

## Conditions

| | |
|---|---|
| Device | Laptop: Intel Core i5-13420H (8 cores / 12 threads), 15 GiB RAM, RTX 4050 Laptop GPU, Ubuntu 24.04, kernel 6.8.0-142 |
| Machine state | No simulator, Isaac or ROS process running (`ps aux` checked); load average 0.35–1.2 during the runs |
| Site | Local **production** build of `3571169`: `build_catalog.py` then `npm run build` (Node 24.21.0, the `.nvmrc` pin), served by `vite preview` on `127.0.0.1:4173/coco-labs/`. `check_dist` tree hash `81254cde…abb52`, failures none |
| Browser | Playwright 1.64.0, Chromium headless shell 156.0.8078.4, headless, viewport 1400 × 1000 |
| Network | Site from loopback; Pyodide 314.0.7 from its pinned CDN (`cdn.jsdelivr.net`) over the laptop's home connection |
| Harness | [`lab_web/tools/perf/baseline.mjs`](../../lab_web/tools/perf/baseline.mjs) — 5 runs of every measurement, **each in a fresh browser (empty HTTP cache)** |
| Raw data | [`data/m0/perf/baseline.json`](data/m0/perf/baseline.json), [`weight.json`](data/m0/perf/weight.json), [`dist_sizes.json`](data/m0/perf/dist_sizes.json) |

Command (from `lab_web/`, with `vite preview` running):
`node tools/perf/baseline.mjs --runs 5 --out ../docs/v2/data/m0/perf`, then
`--only weight` for the transfer sizes.

## 1. Pyodide cold start and warm map edit (Plan view)

The flow is Phase 1D's (`tools/browser/check.py` `edit`), so the numbers
compare with `docs/RESULTS.md`: open `?view=plan&perf&bundle=arena_0_10m`
(the 0.10 m arena), choose the paint tool, click ONE cell with the 1 × 1
brush, time `edit-click` → `edit-first-frame` from the page's own `?perf`
marks. Four edits per run: edit 1 is **cold** (it loads Pyodide from the
CDN and installs the `coco_lab` wheel), edits 2–4 are **warm**.

| measurement | n | median | range |
|---|---|---|---|
| **Cold first edit**, click → first frame | 5 | **12,857 ms** | 6,567 – 42,882 ms |
| of which "Pyodide load" (the page's own figure, includes the CDN download) | 5 | 9,412 ms | 3,937 – 39,736 ms |
| of which wheel install | 5 | 632 ms | 528 – 751 ms |
| **Warm edit** (edits 2–4), click → first frame | 15 | **1,445 ms** | 1,265 – 1,686 ms |

Per run (cold, then warm ×3, ms): 42,882 / 1,424 / 1,445 / 1,481;
37,772 / 1,567 / 1,686 / 1,562; 12,857 / 1,552 / 1,614 / 1,603;
7,568 / 1,369 / 1,273 / 1,287; 6,567 / 1,265 / 1,267 / 1,276.
Inside `coco_lab` on the warm edits: search 686–915 ms, load 372–443 ms,
write 504–631 ms (status line of each run).

**What the spread is.** The cold time is dominated by the CDN download:
"Pyodide load" fell 39.7 → 30.9 → 9.4 → 4.6 → 3.9 s across the five
consecutive runs while the in-browser work stayed flat. Every run used an
empty browser cache, so the browser cache cannot be the cause; a warming CDN
or network path is plausible but **not attributed** (UNRESOLVED). Phase 1D
saw the same 16–95 s range on this connection. A v2 cold-start budget must
therefore be judged on a stated network, not on this median.

**Warm edits are slower than Lab 1's record** (1,158–1,172 ms at Lab 1.1
Part A). Not investigated; the machine, browser (Chromium here, Firefox
then) and harness all differ. Reported, not explained.

## 2. Frame rate during playback, each current view

Each view's own player was started and the browser's
`requestAnimationFrame` callbacks were timestamped for 5 s. Two numbers:

- **rAF rate**: frames the browser delivered (60 = the display cap; lower
  means the main thread was blocked).
- **View updates/s**: frames in which the picture actually changed (any 2D
  canvas draw call or DOM/SVG mutation). This is the playback's real
  redraw rate, set by each view's step rate, not by performance.

| view | what played | rAF fps (median, range) | view updates/s | long tasks (> 50 ms) | max frame gap |
|---|---|---|---|---|---|
| `?view=plan` | Lab 1 full-arena native Dijkstra trace (283k events), default speed | 60 (60–60) | 60.0 (60.0–60.0) | 0 | 16.8 ms |
| `?view=localise` | Lab 2 default Sketch bundle, 4× sim time (the default) | 60 (60–60) | 6.4 (6.4–6.4) | 0 | 16.8 ms |
| `?view=map` | Lab 3 recorded tour (Replay), 8× sim time (the default) | 60 (60–60) | 8.8 (8.8–8.8) | 0 | 16.8 ms |
| `?view=search` | Lab 4 recorded Gazebo search (Replay) | 60 (60–60) | 1.0 (1.0–1.0) | 0 | 16.8 ms |
| `?view=move` | Lab 5 static room, three controllers (Replay) | 60 (60–60) | 17.6 (17.6–17.6) | 0 | 16.8 ms |
| `?view=live` | — no playback without a running Stack | not measured | not measured | — | — |

n = 5 fresh browsers per view. Lab 1's own draw time per frame
(`perfFrame`): median 0.4 ms, p95 0.5–0.6 ms. On the laptop every view
holds the display rate with zero long tasks, so the **laptop gives no
performance signal for v2** — the phone baseline
([`PHONE_BASELINE.md`](PHONE_BASELINE.md)) is the one that matters.
Headless Chromium on this machine; a headed browser and Firefox/Safari were
not measured.

## 3. Production bundle sizes

`dist/` of the production build (raw bytes on disk;
[`dist_sizes.json`](data/m0/perf/dist_sizes.json)):

| part | files | bytes |
|---|---|---|
| **total `dist/`** | 78 | **23,010,799** |
| `generated/loc` (Lab 2 bundles) | 10 | 9,240,476 |
| `generated/map` (Lab 3 bundles) | 10 | 5,122,539 |
| `generated/move` (Lab 5 bundles) | 16 | 3,996,956 |
| `generated/bundles` (Lab 1 bundles) | 22 | 2,902,162 |
| `assets/` (app JS, CSS, Pyodide worker) | 7 | 559,706 |
| `generated/catalog.json` | 1 | 557,674 |
| `generated/loc_exhibits.json` | 1 | 324,932 |
| `generated/py` (`coco_lab` wheel) | 1 | 180,744 |
| `generated/tracking`, `search`, `exhibit.json`, `coco/frame.js`, `index.html` | 10 | 125,610 |

App assets (raw / gzip -9): `index` JS 337,864 / 107,569 B; `MoveLab`
48,607 / 15,319; `Localise` 45,654 / 14,308; `MapLab` 45,645 / 14,912;
`SearchLab` 35,008 / 11,075; Pyodide worker 27,929 / 8,155; CSS 18,999 /
4,704; `index.html` 1,179 / 596.

**Pyodide assets** (not in `dist/`; fetched by the worker on the first edit
from `cdn.jsdelivr.net/pyodide/v314.0.7/full/`, encoded body bytes as
received; [`weight.json`](data/m0/perf/weight.json)):

| file | bytes |
|---|---|
| `pyodide.asm.wasm` | 3,442,784 |
| `python_stdlib.zip` | 2,508,511 |
| `pyodide.asm.mjs` | 262,670 |
| `micropip-0.11.1-py3-none-any.whl` | 111,808 |
| `pyodide-lock.json` | 25,115 |
| `pyodide.mjs` | 8,021 |
| **total, 6 requests** | **6,358,909** |

Transfer for the Plan view on the 0.10 m arena: **590,902 B in 6 requests**
to the first drawn frame (no Pyodide request before the first edit), then
**6,537,154 B in 8 requests** through the first edit (Pyodide plus the
wheel and the result).

## 4. Bundle and trace formats in use

Every format v1 writes or reads. "Files in repo" counts tracked files whose
top-level `schema` is that name ([`formats.json`](data/m0/formats.json));
"in site" counts what the production build ships (manifests, where traces
are embedded). All are deprecated by the plan's one-envelope MCAP design
and are replaced in **M1–M2** ([`DEPRECATIONS.md`](DEPRECATIONS.md)).

| format | version(s) | producer | consumer | files in repo | in site |
|---|---|---|---|---|---|
| `coco_lab.bundle` (Lab 1) | 1.0, 1.1 | `coco_lab/bundle.py` | `lab_web/src/bundle/{load,decode,json}.ts`, `worker/recompute.py` | @1.0: 40 (35 deliberately invalid test vectors in `lab_web/test/invalid/`, 5 fixtures); @1.1: 9 (5 invalid vectors, 3 Lab 1C recorded runs, 1 fixture); plus one @2.0 and one @"v1" invalid vector | 8 @1.0, 3 @1.1 |
| `coco_lab.trace` (inside a bundle) | 1.0 | `coco_lab/trace.py` | `bundle/decode.ts` | embedded only | 11 |
| `coco_lab.map` (inside a bundle) | 1.0 | `coco_lab/maps.py` | `bundle/decode.ts`, `trace/coords.ts`, `ui/map/MapLab.tsx` | embedded only | in every Lab 1 bundle |
| `coco_lab.loc_bundle` / `loc_trace` (Lab 2) | 1.0 / 1.0 | `coco_lab/locbundle.py` / `localise.py`; site copies by `lab_web/tools/build_localise.py` | `lab_web/src/loc/decode.ts` | 2 (fixtures) | 5 bundles, 12 traces |
| `coco_lab.slam_bundle` / `slam_trace` (Lab 3) | 1.0 / 1.0 | `coco_lab/slambundle.py` / `slam.py`; `tools/build_map.py` | `lab_web/src/map/decode.ts` | 3 | 5 bundles, 28 traces |
| `coco_lab.search_bundle` / `search_trace` (Lab 4) | 1.0 / 1.0 | `coco_lab/searchbundle.py` / `regionsearch.py`; `tools/build_search.py` | `lab_web/src/search/decode.ts` | 3 | 2 bundles, 23 traces |
| `coco_lab.replan_bundle` (Lab 5) | 1.0 | `coco_lab/movebundle.py`; `tools/build_move.py` | `lab_web/src/move/decode.ts` | 2 | 4 |
| `coco_lab.drive_bundle` (Lab 5) | 1.0 | `coco_lab/movebundle.py`; `tools/build_move.py` | `lab_web/src/move/decode.ts` | 5 | 4 |
| `coco_lab.catalog` (site index) | 1.5 | `lab_web/tools/build_catalog.py` | `lab_web/src/bundle/load.ts` | 0 (generated) | 1 |
| `lab_web.tracking` (Lab 1C plot data) | 1.0 | `build_catalog.py` | `ui/TrackingPlot.tsx` | 0 (generated) | 3 |
| `lab_web.exhibit` (A\* myth) | 1.0 | `build_catalog.py` | `ui/Exhibit.tsx` | 0 (generated) | 1 |
| Share link (`?…&v=1`) | `SHARE_VERSION` "1" | `lab_web/src/lab/share.ts` | same | 1 golden vector file (`lab_web.share_vectors` 1.0) | — |
| `coco.v1` wire protocol (Live) | `coco.v1` | `coco_web/platform_server` | `lab_web/src/live/{client,protocol,frame}.ts` | — (`docs/WEB_API.md`) | — |
| Lab 1C evidence: `coco_lab.lab1c.runs/1`, `coco_lab.lab1c.conformance/1` | 1 | `coco_lab_ros` scripts | docs only | 1 + 1 | — |
| Lab 5 evidence: `coco_lab.lab5_results`, `lab5_replan_c` | 1.0 | `docs/data/lab5` scripts | `build_move.py` | 1 + 1 | — |
| Lab 5 inputs: `coco_lab_ros.lab5_path`, `lab5_scenarios` | 1.0 | committed config | `docs/data/lab5/lab5_capture.py`, `coco_lab_ros` tests | 2 + 1 | — |

Also tracked: 374 `.json` and 7 `.json.gz` files with no top-level schema
(mostly robot-project evidence under `docs/data/`) and 3 deliberately
unreadable test vectors (`lab_web/test/invalid/`). Six bundle families, six
trace/data shapes, and five TypeScript decoders (`bundle`, `loc`, `map`,
`search`, `move`) for one site.

## 5. Duplicated visualization and rendering code in `lab_web`

Read from the source at `3571169` (static inspection, not a metric):

**Five separate drawing stacks for one arena.**

| stack | file(s) | technique |
|---|---|---|
| Lab 1 (Plan) | `src/render/draw.ts` (192 lines), `render/layers.ts`, `render/overlays.ts`, `render/palette.ts`, `ui/MapView.tsx` (151) | Canvas 2D, pre-rendered RGBA layers |
| Live | `src/live/mapdraw.ts` (140), `ui/LiveView.tsx` | Canvas 2D, its own `fit()` / `gridImage()` / `robot()` |
| Lab 2 (Localise) | `src/ui/loc/LocCanvas.tsx` (209) | Canvas 2D, own transform |
| Lab 3 (Map) | `src/ui/map/MapCanvas.tsx` (298) | Canvas 2D, own transform |
| Lab 4 (Search) | `src/ui/search/SearchLab.tsx` `Arena` (l. 88–150) | SVG, own `sx()`/`sy()` |
| Lab 5 (Move) | `src/ui/move/shared.tsx` `MapSvg`/`Walls`/`frameOf` | SVG, own frame |

**Repeated in several of them:**

- **Canvas sizing**: `ResizeObserver` + `devicePixelRatio` + "device px per
  cell" scale, three times — `ui/MapView.tsx` l. 56–75,
  `ui/loc/LocCanvas.tsx` l. 45–55, `ui/map/MapCanvas.tsx` l. 77–87.
- **World→pixel transforms**, six independent definitions:
  `live/mapdraw.ts` `fit()`, `LocCanvas.tsx` `X()/Y()`, `MapCanvas.tsx`
  `X()/Y()`, `render/draw.ts` cell scale, `SearchLab.tsx` `sx()/sy()`,
  `move/shared.tsx` `frameOf()`; plus `trace/coords.ts`, `loc/view.ts`,
  `map/view.ts`.
- **Occupancy grid → image**: `render/draw.ts` `putRGBA()` and
  `live/mapdraw.ts` `gridImage()` (the second flips rows, the first does
  not need to).
- **Robot glyph**: `live/mapdraw.ts` `robot()`, `LocCanvas.tsx` (l. ~145),
  `MapCanvas.tsx` (l. ~238), `render/draw.ts` footprint sweep — four
  drawings of the same robot.
- **Playback clocks**, five: `ui/Player.tsx` (rAF + interval),
  `ui/loc/Localise.tsx` l. 130–140 (rAF), `ui/map/MapLab.tsx` l. 90–98
  (rAF), `ui/search/SearchLab.tsx` `useStepper` l. 164, `ui/move/shared.tsx`
  `useClock` l. 104 and `ui/move/ReplanView.tsx` `useStep` l. 19.
- **Player controls**: `Player.tsx`, `Localise.tsx` `LocPlayer`,
  `MapLab.tsx` `Player`, `SearchLab.tsx` `Stepper`, `move/shared.tsx`
  `Clock` — the same play / step / end / speed row five times.
- **Decoders**: `bundle/decode.ts` (542), `loc/decode.ts` (317),
  `map/decode.ts` (380), `search/decode.ts` (294), `move/decode.ts` (383) —
  1,916 lines for one envelope's worth of work.

These are the duplications M1's single renderer (Three.js, one layer
vocabulary, one timeline) and one trace envelope remove.
