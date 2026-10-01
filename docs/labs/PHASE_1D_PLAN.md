# COCO Lab — Phase 1D implementation plan (APPROVED)

## How this file came to be (recorded 2026-09-30, implementation session 1D-0)

The planning session wrote this plan to the owner's Claude plan store
(`~/.claude/plans/pasted-content-id-b193-coco-vast-boot.md`, sha256
`9bccfe5a…`, 699 lines) and did not commit it. The owner reviewed and
approved it. Everything below the rule is that file **verbatim**, except that its
first line (the title) is replaced by the one above. Nothing in it is
redefined after a measurement.

The owner's implementation instruction for 1D (2026-09-30) changes only
**when the session stops**, not the scope:

| plan text | as executed |
|---|---|
| §K/§N: stop for approval after 1D-0 and between blocks | the sub-milestones are internal checkpoints; the session continues through 1D-8 without stopping |
| §I, §K-8: ask to enable Pages, then fast-forward `main` once the owner rules on the red `ci.yml` | **`main` is not touched in 1D.** Deployment is prepared and proven on `lab1`; the Pages toggle and the `main` fast-forward stay owner actions and are reported as blockers, never claimed |
| §B-5 / §L-13: a missed performance target stops the session with options | unchanged: a missed target is still reported with options and numbers |

The implementation's sub-milestone numbering follows §K below (1D-1 is
the Python tools, 1D-2 the skeleton, …), not the session prompt's.

---

## Context

Phase 1C closed on `lab1` (ca8ce79). It left three recorded-run bundles in schema 1.1
and a golden-fixture set written so that "Phase 1D's TypeScript decoder is tested against
these bytes". Phase 1D (`docs/LAB_PHASES.md:357-401`) builds the first browser tier:
- a Vite + TypeScript + React shell with Canvas 2D rendering;
- a TS bundle decoder that agrees exactly with `coco_lab/bundle.py`;
- a trace player;
- a lazy Pyodide worker that runs the real `coco_lab`;
- measured performance numbers;
- CI, and a Pages deploy from `main`.

The browser renders and asks `coco_lab`. It never re-implements a search. This session
is **plan only**. Nothing in the repo was modified.

Owner decisions taken in this session:
- **Mode labels.** The label comes from `provenance.source_kind`. Recorded runs show
  "Replay — recorded real run". Glass-box bundles show "Replay — coco_lab computation
  (glass-box)". A browser recompute is written as `glass-box` with
  `tool='lab_web/pyodide'` and shows "Replay — computed in your browser by coco_lab".
  `sketch` stays reserved for Phase 3 (Sketch mode; it read "Phase 2" until
  the 2026-09-30 plan revision made Phase 2 Live). No new mode, and no
  CLAUDE.md edit.
- **Base path.** `/coco-robot-jazzy-2.0/`, set in one constant and overridable by the
  env var `LAB_BASE`. A build test asserts every asset URL is under it.

---

## A. VERIFIED CURRENT STATE

Verified this session:

| claim | result |
|---|---|
| branch `lab1`, HEAD `ca8ce79`, tree clean | **verified** (`git status`, `rev-parse`) |
| `jazzy2/lab1` = `ca8ce79` | **verified** (`git ls-remote`) |
| 1A/1B/1C COMPLETE, 1D not started | **verified** (SESSION_LOG:5620-5680, "NEXT MILESTONE: Phase 1D … Not started") |
| three 1.1 bundles, 909,380 B total | **verified** (`du -cb docs/data/lab1c/bundles/*/*` = 909,380; all `version "1.1"`, gzip, 4/4 streams present) |
| mission `nav2_params.yaml` unchanged | **verified**: `gazebo_models/config/nav2_params.yaml` sha256 `06c308af…` = the 1C invariant |
| rosbags outside git | **verified**: no bag in `git ls-files`; `runs.json` carries their hashes |
| test counts (coco_lab 333 pip / 336 colcon, coco_lab_ros 69, gazebo_models 229, custom_teleop 75, 0 fail, 0 skip) | **recorded in SESSION_LOG:5626-5630, NOT re-measured here.** A bare-shell `--collect-only` found 102 tests plus 10 import errors: `hypothesis` and the ament linters are absent from the system Python. That is an environment gap, not a regression. Re-measured in 1D-0 |
| "five golden fixtures" | **corrected: six.** The five 1B fixtures (1.0) are `astar_open`, `dijkstra_cost_field_gz` (the only gzipped one), `weighted_astar_greedy_trap`, `bfs_no_path` and `astar_turn_trap_heading` (heading_grid). 1C added `recorded_run_synthetic_1_1` (1.1, synthetic streams, `cmd` listed missing, **map `geo: null`**) |

Environment facts relevant to 1D:
- **Toolchain:** Node v20.20.2 and npm 10.8.2 are installed. Node 20 is past its EOL.
  34 GB of disk is free.
- **Repo:** `GauthamCodes/coco-robot-jazzy-2.0` is PUBLIC, and Pages is not enabled
  (the API returns 404).
- **`main` = `6853517`** is an ancestor of `lab1`, 9 commits behind. A fast-forward is
  possible.
- **The existing ROS `CI` workflow (`.github/workflows/ci.yml`) has FAILED on the last 5
  pushes to `main`, at the "Build" step.** The cause was not diagnosed: the failed-log
  fetch returned nothing. That workflow also does not build `coco_lab` or `coco_lab_ros`.
- **Browser harness:** `scripts/browser_check/` drives headless Firefox over WebDriver
  BiDi, and `render.py` has `--width/--height`. It is reusable for the phone-width check
  and for timings. The Chrome extension is not needed.
- **Existing JS test pattern:** the Python encoder produces fixtures and `node --test`
  decodes them (`coco_web/test/frame_decode.test.js`, driven by `test_frontend_frame.py`).
- **`.gitignore`** has no `node_modules` or `dist` entries yet.

## B. PHASE 1D CONTRACT (LAB_PHASES §1D, verbatim scope)

**Required**
1. Create `lab_web/` with `COLCON_IGNORE`. Stack: Vite + TypeScript, React for the
   shell, Canvas 2D for maps and traces. No analytics, no cookies, and no third-party
   calls except the pinned Pyodide CDN.
2. A TS bundle decoder tested against the golden fixtures, using the cross-language
   pattern of `frame_decode.test.js`. Both sides must agree exactly on every fixture.
3. A trace player:
   - play, pause, step, scrub and speed controls;
   - keyboard: space and the arrow keys;
   - open, closed and path overlays in a colourblind-safe (Okabe–Ito) palette;
   - hover shows g, h and f;
   - respects `prefers-reduced-motion`.
4. Pyodide in a Web Worker, lazy-loaded only on a map edit. It installs `coco_lab` from
   a pure-Python wheel that CI builds and the site serves. The Pyodide version is pinned
   and **looked up, not guessed**.
5. Measure and report as (measured), against these targets:
   - full-arena Dijkstra playback ≥ 60 fps;
   - warm edit → first frame ≤ 1.5 s;
   - Pyodide cold load;
   - initial page weight, excluding Pyodide.

   **If a target is missed: bring options with numbers and STOP.**
6. CI on GitHub Actions:
   - `coco_lab` tests in a plain venv with no ROS;
   - the TS tests;
   - the site build;
   - a Pages deploy from `main`.

   The owner enables Pages when asked. The base path is the current repo name (decided).
7. Replay works at phone width; editing may be desktop-first. Say how this was checked.
8. Checkpoint, commit, stop.

**Implied by other docs:**
- The decoder must read the 1.1 recording arrays (SESSION_LOG 1C "EXACT NEXT ACTION").
- The ROADMAP §8 golden-file pinning.
- CLAUDE.md platform rules 1–9: rule 4 (labels), rule 5 (citations), rule 8 (no
  algorithm in TS).
- Standing approvals:
  - commit and push to `lab1`: pre-approved;
  - push to `main`: **only as a fast-forward from `lab1` with every test green**.

**Optional / deferred to 1E (not in 1D):**
- the settings panel and admissibility badge;
- the map ladder and footprint sweep;
- race mode and synchronised comparison;
- predict-then-reveal;
- full painting UX and blocked start/goal UX;
- share links;
- the challenge;
- "Driven by COCO" replay with the tracking-error plot;
- the A\* myth exhibit.

1D only lays the foundations for these.

**Out of scope:** Phase 2 and later, Live mode, Sketch mode, SLAM, Isaac, RL, any ROS or
arbiter change, and user uploads of arbitrary bundles.

**Unknown (resolve by measurement or lookup in 1D, not by guessing):**
- the current Pyodide release;
- whether `micropip` accepts `coco_lab`'s wheel, whose `data_files` put the ament marker
  into `.data/`;
- Pyodide's slowdown versus CPython for the 0.10 m arena search;
- how the Vite dev server and Pages serve `arrays.bin.gz` (the `Content-Encoding` risk);
- why the ROS CI fails on `main`.

**Acceptance criteria:** section L.

## C. EXISTING DATA/SOURCE INTERFACES

**Bundle** (`docs/labs/BUNDLE_FORMAT.md`, `coco_lab/coco_lab/bundle.py`)
- **Files.** A directory holding `manifest.json` (canonical JSON: sorted keys, compact,
  no NaN) plus `arrays.bin` or `arrays.bin.gz` (gzip, `mtime` 0). The manifest never
  names a file.
- **Versions.** `"1.0"`, and `"1.1"` only for a recorded-run bundle that carries a
  recording. A MINOR or unknown field is ignored. An unknown MAJOR is refused. The array
  table is **exact**, so a 1.0 reader refuses 1.1 arrays.
- **Manifest fields:**
  - `schema`, `version`, `provenance`, `run`, `map` (id, content_hash, width, height,
    cost_layer, geo, meta), `trace` (header and summary), `arrays[]`, `encoding`,
    `content_hash`, and in 1.1 an optional `recording`.
  - `provenance`: `source_kind`, `coco_lab_version`, `git_commit`, `git_dirty`,
    `created_utc`, `seed`, `episode_spec_hash`, `rosbag {sha256, sim_time_start,
    sim_time_end}` (required for recorded-run), `tool`.
- **Array order**, contiguous and little-endian:
  1. `trace.kind` u8;
  2. `trace.row`, `trace.col`, `trace.sub` i32;
  3. `trace.g`, `trace.h`, `trace.f` f64;
  4. `trace.parent_row`, `trace.parent_col`, `trace.parent_sub` i32;
  5. `map.occupancy` u8 (row-major; 0 free, 1 occupied, 2 unknown);
  6. `map.cost` f64 (present iff `cost_layer`);
  7. then per present group:
     - `gt` and `amcl`: `recording.<g>.{t,x,y,yaw}`;
     - `plan`: `recording.plan.{x,y,yaw}`;
     - `cmd`: `recording.cmd.{t,v,w}`.

   **Offsets are not aligned:** `trace.kind` is N bytes, then i32 data follows.
- **`recording`** has exactly the keys `{groups, missing, run_id, meta}`.
  - `groups[g] = {frame, source, count}`.
  - Every group is in exactly one of `groups` and `missing`.
  - Every value is finite, and `t` never decreases.
  - A recording is allowed only on a `recorded-run` bundle.
- **`content_hash`** = sha256(canonical JSON of the manifest minus `content_hash`,
  `encoding` and `provenance.created_utc`, then `"\n"`, then the **uncompressed** array
  bytes).
- **Map `content_hash`** = sha256 of:
  1. `coco_lab.map/1 W H\n`;
  2. the occupancy bytes;
  3. `cost\n` plus the LE f64 cost, or `nocost\n`;
  4. `geo <repr(res)> <repr(ox)> <repr(oy)> <frame>\n`, or `nogeo\n`.

  This uses **Python `repr` floats** (MAP_FORMAT §Identity; exact newlines to confirm in
  `maps.py:230`).
- **Python `load_bundle` checks, in two tiers:**
  - (i) Structural: bounds, schema/MAJOR, array table, exact length, content hash,
    dtypes, finite g/h/f, map hash, recording structure, run-versus-header agreement,
    and the `Trace.validate()` event-log invariants.
  - (ii) **Semantic, on the rebuilt graph**: start and goal free, the first push is the
    start, the relax/expand/parent order, the path moves only between neighbours, and
    the path cost is recomputed via `edge_cost`.

  Tier (ii) needs the graph's neighbour and cost functions. **That is algorithm code, and
  TS must not re-implement it.**
- **Bounds:** manifest ≤ 1 MiB; arrays ≤ 256 MiB; ≤ 16 M cells; ≤ 50 M events; JSON
  depth ≤ 32; bounded gunzip.

**Trace** (`TRACE_SCHEMA.md`)
- Columnar events: kinds push 0, expand 1, relax 2 and path 3, each carrying row, col,
  sub, g, h, f and parent (row, col, sub), where −1 means none.
- `f` is the priority actually used, so BFS's f is its depth.
- Summary: status, expansions, pushes, relaxes, path_cost, path_length, path_steps.
- In a heading grid, `sub` is 0–7 for the heading, 8 for the start and 9 for the goal
  sink, which repeats the goal cell.

**Map** (`MAP_FORMAT.md`)
- Row 0 is the TOP row. The metric origin is the bottom-left corner.
- Cell centre: `x = ox + (col+.5)·res`, `y = oy + (H-1-row+.5)·res`.
- `geo` may be null (teaching grids).

**Recorded-run content** (1C bundles):
- **Map:** `costmap_raw`, 500 × 380 at 0.05 m, origin (−6.5, −9.5).
- **Trace:** 4,368 events (greedy), 18,660 (A\*) and 71,900 (Dijkstra).
- **Recording, per run:**
  - `gt`: 3,351–3,890 samples, already transformed into `map` by the exporter
    (`world_to_map [2,0]`);
  - `amcl`: 11–37;
  - `plan`: 154–183;
  - `cmd`: 490–665, in the `base_footprint` frame.
- **`recording.meta`** holds the exporter's measured results:
  - `result.phase`, with greedy `follow_failed` (code 105);
  - `duration_sim_s`;
  - `tracking_error_m {mean,p95,max,n}` and `endpoint_error_m`;
  - `recoveries`, `belief_gap_m`;
  - the arbiter and collision-monitor timelines;
  - `window_sim`, `consistency` and `checks`.
- Uncompressed sizes: 2.05, 2.77 and 5.38 MB. The 1B full-arena native Dijkstra trace
  (283,378 events) is 14.08 MB raw, 1.44 MB gzip, and can be regenerated by
  `docs/data/lab1b/resolution.py`.

**Coordinate trap (found this session).** SESSION_LOG writes the start as cell
`(130, 190)` in (col, y-up) form. The bundle stores `[189, 130]` as [row, col], and
189 = 379 − 190. The UI shows the bundle's [row, col] form plus metric x/y, never the
log's form.

## D. PROPOSED WEB ARCHITECTURE

The stack is prescribed, so there is no framework comparison. Dependencies are kept
minimal and pinned to exact versions, with no `^`:
- `vite`, `@vitejs/plugin-react`, `typescript`, `react`, `react-dom`, `@types/react`,
  `@types/react-dom`, `vitest`;
- nothing else. There is no `pako`: native `DecompressionStream` does gzip. There is no
  npm `pyodide`: it loads from the pinned CDN inside the worker.
- Lockfile committed; `npm ci`; the Node version pinned in `.nvmrc` and used by CI.

```
lab_web/                    COLCON_IGNORE · package.json · package-lock.json · .nvmrc
  vite.config.ts            base = process.env.LAB_BASE ?? '/coco-robot-jazzy-2.0/'
  index.html                CSP <meta> (self + pinned Pyodide CDN + 'wasm-unsafe-eval')
  .gitignore                node_modules/ dist/ public/generated/
  src/bundle/               PURE TS, no DOM/React: the decoder (section E)
  src/trace/                cursor.ts (event log -> cell state at k), coords.ts
  src/render/               palette.ts (Okabe–Ito), mapLayer, traceLayer, overlays, recordingLayer
  src/ui/                   React: App, ModeBadge, CatalogPicker, Player, HoverReadout,
                            ProvenancePanel, SummaryPanel, RecordingInspector
  src/worker/               pyodide.worker.ts (lazy), protocol.ts, recompute.py (glue only)
  tools/                    PYTHON (runs where coco_lab is installed; no rclpy)
    build_catalog.py        validate + replay every served bundle, copy to public/generated/,
                            write catalog.json, build edit map (arena 0.10 m) + benchmark bundle
    make_expectations.py    golden decode expectations + invalid-bundle corpus + JSON corpus
    test_tools.py           pytest: regeneration byte-equal; Python refuses every invalid case
  test/                     vitest suites + committed expectations/invalid fixtures
```

**Data flow**

```
 catalog.json ──(built by tools/build_catalog.py: coco_lab.load_bundle + replay() = full
      │          tier-(i)+(ii) validation; records content_hash, source_kind, citation)
      ▼
 loader (src/bundle/load.ts)     fetch manifest (≤1 MiB) + arrays[.gz] (≤ declared+1 B)
      │  errors → BundleError{code,msg} → UI error panel, nothing drawn
      ▼
 validator/decoder (src/bundle)  lossless JSON → structural checks → bounded gunzip →
      │                          exact table/length → content_hash (Python-canonical) →
      │                          map hash → recording structure → Trace invariants →
      │                          content_hash == catalog entry (else refuse)
      ▼
 normalized model  DecodedBundle { provenance, run, map{typed}, trace{header,summary,
      │            events: typed columns}, recording?{groups,missing,meta,streams: typed},
      │            contentHash, validatedBy: 'catalog:coco_lab' | 'pyodide:coco_lab' }
      ▼
 trace cursor / coords (pure)    event-log interpretation only (TRACE_SCHEMA semantics)
      ▼
 renderer (Canvas 2D) + React shell   ModeBadge ← provenance.source_kind
                                      algorithm identity ← trace.header / run
                                      metrics ← trace.summary + recording.meta AS STORED
                                      provenance panel ← provenance + catalog citation

 edit (1D minimal) → worker: coco_lab.load_bundle(same bytes, MEMFS) → edit LabMap →
   coco_lab search with the bundle's run inputs → write_bundle(glass-box, tool=lab_web/pyodide)
   → bytes → SAME decoder above (validatedBy 'pyodide:coco_lab')
```

The UI cannot become a second experiment engine:
- Every trace comes from a bundle `coco_lab` wrote, either at build time or in the
  worker.
- TS derives only display state from the event log, never a cost, a neighbour or a
  priority.
- Metrics are displayed as stored, never recomputed.

## E. BUNDLE 1.0/1.1 DECODER DESIGN

**Validation boundary.**
- **TS** ports Python tier (i) exactly: `parse_manifest`, then `decode` up to
  construction, `_check_recording`, the run-versus-header field equality, and the
  `Trace.validate()` invariants. The implementer reads `trace.py` `validate()` first.
- **Tier (ii) is not ported.** Semantic validity comes from `coco_lab` itself:
  - at build time (`build_catalog.py` runs `load_bundle`, plus `replay()` for glass-box
    bundles, and records the result);
  - or in the worker, where `write_bundle` calls `validate()`.
- The browser draws only bundles whose `content_hash` equals a catalog entry, or one the
  worker just produced.
- This boundary is documented in a new `lab_web/README.md` §Decoder and in
  `docs/labs/BUNDLE_FORMAT.md`. The BUNDLE_FORMAT addition is additive, under a "Readers"
  heading. The doc-pinning test must still pass, so its scope is checked first.

**The canonical-JSON problem, and the core design decision.**
- `JSON.parse` then `JSON.stringify` cannot reproduce Python's hash input:
  - `252.0` becomes `252`, and ints and floats become indistinguishable;
  - the exponent thresholds differ (`1e-05` versus `0.00001`);
  - Python's `ensure_ascii` escapes non-ASCII characters and DEL as `\uXXXX`;
  - key order: Python sorts by code point, while JS sorts UTF-16 units.
- The decoder therefore uses:
  - `json.ts`: a strict, **lossless** parser. It keeps each number's lexeme and its
    int/float kind. It refuses NaN/Infinity, depth > 32, input > 1 MiB and **duplicate
    keys**. Python keeps the last duplicate key; TS is stricter here, a documented
    divergence that a canonical writer never triggers.
  - `pyrepr.ts`: Python float `repr` built from JS shortest round-trip digits. The two
    languages use the same digits and different formatting:
    - scientific notation when the exponent is < −4 or ≥ 16;
    - `e-05` and `e+16` exponent forms;
    - a `.0` suffix on integral floats.

    Ints keep their lexeme, except that `-0` becomes `0`.
  - `canonical.ts`: sorts by code point, uses `,` and `:` separators, and applies Python's
    `ESCAPE_ASCII` rules.
- `hash.ts` uses `crypto.subtle.digest('SHA-256')`, which needs a secure context. Pages
  (https), localhost and Node ≥ 20 all qualify.
  - The map hash is rebuilt byte-for-byte, with `pyrepr` for the geo floats.
  - SubtleCrypto has no incremental API, so the hash input is one concatenated buffer:
    peak ≈ 2 × raw.

**Compression.**
- Choose the file name from `encoding.compression`.
- Check the gzip magic `1f 8b` before inflating. If it is missing, refuse with "the server
  decoded the gzip (Content-Encoding)". Never repair.
- Inflate through `DecompressionStream('gzip')`, accumulating chunks and **aborting at the
  declared total + 1 byte**, the same gzip-bomb bound as Python.
- Uncompressed arrays are read with a `Content-Length` pre-check and a stream cap.

**Arrays.**
- Offsets are unaligned, so zero-copy views are impossible in general. Each array is
  copied with `buffer.slice(off, off+len)` into an aligned typed array on a little-endian
  host.
- A `DataView` path handles big-endian hosts. It is selected at runtime, and a test
  forces it so both paths are pinned equal.
- Raw evidence is kept whole: every typed column is exposed, and nothing is dropped or
  rounded.
- Once the hash is verified, the compressed buffer and the concatenated hash buffer are
  released.

**Version detection.**
- `schema` must equal `coco_lab.bundle`, and MAJOR must be 1.
- MINOR is parsed:
  - a `recording` under MINOR 0 is refused;
  - a 1.1 bundle without a recording decodes like 1.0;
  - unknown manifest fields are ignored;
  - an unknown **array** is refused, because the table is exact.

**Errors.** `BundleError{code, message}`. Codes mirror the Python rejection classes:
`bounds`, `schema`, `version`, `structure`, `table`, `length`, `hash`, `map_hash`,
`dtype`, `nonfinite`, `recording`, `run_header`, `trace_invariant`, `compression`,
`catalog_mismatch`. The UI shows the code and message, with no partial drawing.

**Memory.** Everything is loaded fully, because the hash needs every byte.
- Peak is roughly compressed + raw + typed copies, about 2–2.5 × raw.
- Measured-size inputs: 5.4 MB raw (largest 1C bundle) and 14.1 MB raw (1B native
  benchmark). Both fit comfortably.
- The Python caps (256 MiB) are enforced before allocation.
- Streaming and lazy decode are unnecessary at these sizes. They are logged as future
  work if a bundle over ~64 MB ever appears (release-asset hosting, ROADMAP §10).

## F. TRACE + RECORDED-RUN RENDERING DESIGN

**Trace (all derivable directly from the event log):**
- **Cell state at event k:**
  - push or relax → open;
  - expand → closed;
  - path → path.
- **Heading grids:** a cell takes the highest-precedence state among its subs, in the
  order path > closed > open. Hover lists every sub.
- **Cursor:** moving forward applies the events incrementally. Moving backward recomputes
  from 0. That is O(k) and should take a few ms at 283k events. Keyframes are added
  **only if** the measured scrub latency calls for them.
- **Hover:** g, h and f come from the last event ≤ k for each state at that cell, found
  by a backward scan. The `f` label comes from the header's algorithm, following
  TRACE_SCHEMA (BFS f = depth).
- **Drawing:**
  - map occupancy and cost go into one `ImageData` (cost as a sequential ramp), built
    once;
  - trace state goes into a second `ImageData`, updated for changed cells only;
  - both are blitted to 1 px/cell offscreen canvases and `drawImage`-scaled with
    smoothing off;
  - start and goal are markers;
  - the path is a polyline.
- **Palette:** Okabe–Ito. Open = sky blue #56B4E9, closed = orange #E69F00,
  path = vermillion #D55E00, start = bluish-green #009E73, goal = reddish-purple #CC79A7.
  Obstacles are black and unknown is grey. The exact assignment is fixed in `palette.ts`
  and tested.
- **Identity and metrics shown:** algorithm, heuristic, weight, tie-break, graph block,
  and the summary counts exactly as stored.
- **Controls:** play, pause, step ±1, scrub slider, and speed (events/frame). Space
  toggles play; ←/→ step; Shift+←/→ step ×100.
- **`prefers-reduced-motion`:** no autoplay, and play advances in discrete jumps with no
  animated transitions.

**Recorded run (1D = data layer plus a minimal static overlay; the full player is 1E
item 8):**
- `recording` streams are exposed raw as `Float64Array`s. `recordingLayer` draws gt, amcl
  and plan as polylines through `coords.metricToCanvas`, using the map's `geo`.
- If the map has **no `geo`**, the overlay is refused with an explicit message rather
  than guessed. The synthetic fixture exercises exactly this.
- Missing groups are named ("cmd: not captured"), never drawn as empty.
- `RecordingInspector` shows the fields listed below. Each is labelled "as exported by
  coco_lab_ros.lab_export", and each block cites the RESULTS.md 1C-5 anchor:
  - `run_id`;
  - groups (frame, source, count) and missing;
  - `rosbag.sha256`;
  - `sim_time` range and `window_sim`;
  - `result.phase` and code;
  - `duration_sim_s`;
  - tracking and endpoint error;
  - recoveries.
- TS computes none of these.
- `cmd` (v, w) and time are exposed in the model and shown as counts only. The plot and
  the time scrubber are 1E.
- **Display decimation:** none needed (gt ≤ 3,890 samples). If one is ever added, it
  lives in `render/` as a view over the untouched source arrays.

## G. EDUCATIONAL UX SKELETON

- **Layout:**
  - header with the ModeBadge, always visible and derived from `source_kind`;
  - catalog picker (bundle list, grouped: "Recorded real runs (1C)", "Teaching traces");
  - canvas;
  - player bar;
  - side panel with tabs: Summary / Provenance / Recording / Hover;
  - footer with the site build commit (`GITHUB_SHA`) and the no-analytics note.
- **Phone width (≤ 420 px):** one column, with the side panel below the canvas. The
  player bar has touch-size buttons. There is no horizontal page scroll.
- **Future hooks, present only as data-model and state shape, not UI:**
  - `selection: BundleRef[]`, so N panes later;
  - a pure `sameInputs(a, b)`, true iff map hash, start, goal, model and seed are equal
    (rule 6), unit-tested;
  - `settings` state reserved for 1E.

  Algorithm and map selection in 1D means choosing a catalog entry. Nothing is recomputed
  except by the worker on an edit.
- **Minimal edit (to exercise item 4 and measure item 5):**
  - desktop only;
  - on a teaching trace or the arena 0.10 m edit map, clicking a cell toggles it free or
    occupied, and the worker re-runs the **same** run inputs;
  - coco_lab errors, such as a blocked start, are shown verbatim.

  Full painting UX is 1E item 5.
- The synthetic 1.1 fixture is **not** in the public catalog. It is a decoder fixture,
  not evidence. Golden glass-box teaching traces and the three 1C runs are.
- No game mechanics.

## H. TEST PLAN

**Python (`lab_web/tools/test_tools.py`, run in the plain-venv CI job and locally):**
- `make_expectations.py` regenerates `lab_web/test/golden/expected.json` **byte-equal**,
  the same pattern as `golden_bundles.py`. For each of the six golden fixtures and the
  three 1C bundles it records:
  - version, content_hash, map hash, summary, recording groups and missing;
  - per array: count, sha256 of its LE bytes, first/last values;
  - cursor checkpoints: a sha256 of the cell-state array at k ∈ {0, N/2, N} under the
    documented display rule;
  - hover samples;
  - `LabMap.cell_at` for every `recording.plan` point, which is the orientation oracle.
- An invalid corpus (`lab_web/test/invalid/`, derived from `astar_open` and the synthetic
  1.1 fixture). The cases mirror `test_bundle.py`'s rejection classes:
  - truncated, padded, flipped bit;
  - major 2, bad version, wrong array order, wrong dtype;
  - NaN in g, over-deep JSON, oversize manifest;
  - gzip bomb, gzip-claimed-but-raw;
  - recording under 1.0, recording on glass-box, a group both present and missing, a
    count mismatch, decreasing t;
  - map-hash mismatch, run/header disagreement.

  **Python `load_bundle` must refuse every case**, and the test asserts it.
- `make_json_corpus.py`: at least 1,000 seeded random JSON values mixing floats of every
  magnitude, ints, `-0`, non-ASCII and control-character strings, and nested objects.
  Each gets its expected Python `canonical_json` and sha256.
- `build_catalog.py`: `load_bundle` OK and, for glass-box, `replay().reproduced` for
  every served bundle. It also checks that the catalog hashes equal the manifests.

**TypeScript (vitest, `lab_web/test/`):**
- decode all 9 bundles, and every value equals `expected.json` (per-array hash, plus
  counts, summary and hashes);
- 1.0 decode, 1.1 decode, and a 1.1 bundle without a recording written as 1.0;
- every invalid case is refused with the expected code. TS is never more permissive than
  Python; the extra refusals (duplicate keys) are listed and tested;
- the JSON/pyrepr/canonical corpus agrees exactly (string and hash);
- gzip: the fixture and three real bundles inflate, the bomb stops at the bound, and a
  missing magic is refused;
- the LE fast path equals the forced DataView path;
- coords: MAP_FORMAT formulas; every plan point's `cell_at` equals Python's; row 0 is
  drawn at the top;
- cursor checkpoints and hover samples equal the expectations; backward scrub equals
  forward replay to the same k;
- heading-grid (turn_trap) aggregation, and the goal sink sub 9;
- synthetic fixture: overlay refused (geo null), and `cmd` reported missing;
- `sameInputs`; the ModeBadge mapping for all three source kinds;
- render: the layer builders are pure functions returning `Uint8ClampedArray`, and their
  sha256 equals a committed snapshot for fixed fixtures and k. Deterministic, with no
  canvas dependency.
- a large-array test on the generated 283k-event benchmark bundle (not committed): it
  decodes within the bounds, and decode time is logged.

**Static / build checks:**
- `tsc --noEmit`;
- `vite build` twice gives an identical `dist/` hash;
- every asset URL in `dist` is under the base path;
- `dist` contains no external URL except the pinned Pyodide CDN;
- no cookie or storage writes except try/catch per-viewer UI prefs, and ideally none;
- a guard test (`tools/test_tools.py`) fails if `lab_web/src` defines a priority queue or
  heap, a neighbour generator, or a heuristic function, using a named-pattern list. This
  test is backed up by review.

**Browser (via `scripts/browser_check/bidi.py`, headless Firefox):**
- phone width 390 × 844: screenshot, `scrollWidth ≤ innerWidth`, and the controls are
  clickable (the `elementFromPoint` pattern already in `render.py`);
- the BiDi network log shows only same-origin requests, plus the Pyodide CDN after the
  first edit;
- `prefers-reduced-motion` is set via a profile pref and verified.

**Regression:** `coco_lab` (pip and colcon), `coco_lab_ros`, `gazebo_models` and
`custom_teleop` counts are unchanged from 1D-0. `lab_web` is COLCON_IGNOREd, so the
colcon package set is unchanged. The existing golden-bundle tests are not modified.

## I. DEPLOYMENT PLAN

- **New workflow `.github/workflows/lab.yml`.** The existing `ci.yml` stays untouched.
  - Triggers: push to `lab1` and `main`, and PRs to `main`.
  - **Job `coco-lab-venv`:**
    - Python venv, no ROS;
    - `pip install ./coco_lab` plus the pinned test requirements;
    - pytest with cwd `coco_lab`;
    - fail if collected < the 1D-0 count or if skipped > 0 (the `ci.yml` floor
      pattern).
  - **Job `lab-web`:**
    - Python venv with `coco_lab`, then `pytest lab_web/tools`;
    - `pip wheel --no-deps ./coco_lab`, placed into `public/generated/py/`;
    - `build_catalog.py`;
    - `.nvmrc` Node, then `npm ci`, `tsc`, `vitest` and `vite build`;
    - the dist checks;
    - `actions/upload-pages-artifact`.
  - **Job `deploy`:** runs only on `main`; `actions/deploy-pages` with
    `permissions: pages: write, id-token: write`.
- **Pages enablement is an owner action** (Settings → Pages → Source: GitHub Actions).
  The implementation session asks for it at 1D-7 with a `needs input:` line.
- **Getting to `main`:**
  - A fast-forward of `main` to `lab1` is pre-approved **only with every test green**.
  - `ci.yml` is currently red on `main` at Build, for a pre-existing, undiagnosed reason.
  - **The implementation session must not treat that as green.** It reports the cause,
    if it can read the log, and asks the owner whether the pre-existing red blocks the
    fast-forward.
  - That is the second gated decision.
- **Local dev:** `cd lab_web && npm ci && npm run dev`. `npm run tools` runs the Python
  catalog build against the dev overlay's `coco_lab`. Documented in `HOW_TO_RUN.md`.
- The public URL
  (`https://gauthamcodes.github.io/coco-robot-jazzy-2.0/`) is verified only after the
  deploy, and only then written anywhere.

## J. RISKS / UNKNOWNS

| risk | handling |
|---|---|
| Python-canonical JSON not reproduced in TS gives false hash failures | lossless parser + `pyrepr` + a ≥1,000-case corpus; the 9 real hashes must match before anything else is built |
| Unaligned array offsets throw `RangeError` on typed views | always slice-copy, and test the DataView path |
| The server applies `Content-Encoding: gzip` to `.gz`, so the browser pre-inflates | a magic-byte check refuses loudly; verified on the Vite dev server and on Pages in 1D |
| `micropip` rejects or mishandles the wheel's `.data/` (ament marker) | test in 1D-5; if it fails, stop with options (e.g. a wheel built without `data_files` via a build flag) — do not hand-edit artefacts |
| Pyodide too slow for the ≤ 1.5 s warm edit on the arena at 0.10 m (CPython 0.228 s, measured in 1B) | measure; if missed, STOP with numbers (a coarser map, teaching grid only, worker pre-warm); a TS hot loop only as a last resort, and the owner decides |
| ≥ 60 fps on the 283k-event trace | incremental ImageData updates; measured in headless Firefox. **Headless timing may not equal a headed browser**, so report which was used and do not extrapolate |
| SubtleCrypto needs a secure context; there is no streaming hash | Pages is https and dev is localhost; memory ≈ 2 × raw is acceptable at measured sizes |
| `DecompressionStream` availability (Safari < 16.4) | state the browser support floor; no polyfill in 1D |
| The meta CSP does not govern a same-origin worker (Pages cannot set headers) | "no third-party calls" is verified by the dist scan **and** the BiDi network log, not claimed from the CSP |
| Coordinate conventions: (col, y-up) in the logs vs [row, col] in bundles; the metric y axis is flipped | the orientation oracle via `LabMap.cell_at` on every plan point |
| Heading-grid display aggregation is a presentation choice | documented and tested; hover shows every sub |
| Trace volume grows (native 283k now; 50 M cap) | measured sizes are fine; lazy decode and keyframes only on measured need |
| Node 20 locally is EOL; CI Node version | pin `.nvmrc` to a supported LTS looked up in 1D-0; record local vs CI versions; compare `dist` hashes across them and report any difference |
| ROS `ci.yml` red on `main` | undiagnosed; owner decision before the fast-forward (section I) |
| No Pages redirect on a later rename (not verified this session) | base path in one constant; re-verify at rename |
| Prose vs schema mismatch | 1D prose says "1B's golden fixtures" (5 × 1.0); the decoder must also pass the 1.1 synthetic fixture and the 3 real 1.1 bundles. Adopted as the stricter reading |

## K. IMPLEMENTATION SEQUENCE

Each block is committed on `lab1` and pushed. That is pre-approved.

1. **1D-0 baseline + plan in repo.**
   - Re-measure `coco_lab` (pip venv via `python3 -m venv --without-pip`, per
     SESSION_LOG:5152; and colcon via `scripts/build_overlay.sh`), plus `coco_lab_ros`,
     `gazebo_models` and `custom_teleop` counts.
   - Look up and record the current Pyodide release and exact Vite / React / TS / Vitest
     / Node LTS versions.
   - Write this plan to `docs/labs/PHASE_1D_PLAN.md` and add a SESSION_LOG 1D-0 entry.
2. **1D-1 Python tools.** `make_expectations.py` (expectations, invalid corpus, JSON
   corpus), `build_catalog.py` (catalog, edit map, benchmark bundle) and `test_tools.py`.
   Commit the expectations and corpora; generated bundles stay ignored.
3. **1D-2 skeleton.**
   - `lab_web/` with COLCON_IGNORE, pinned `package.json` and lockfile, `.nvmrc`, Vite
     config (base constant), `index.html` with CSP, `.gitignore`, and the empty React
     shell with ModeBadge.
   - `npm ci && npm run build` green.
4. **1D-3 decoder.** `src/bundle/*` and the vitest suites.
   **Gate: all 9 bundles agree exactly; every invalid case is refused.**
5. **1D-4 player + renderer.** cursor, coords, layers, palette, controls, keyboard,
   hover, reduced motion, the recording overlay and inspector, provenance/summary
   panels, catalog picker.
6. **1D-5 Pyodide worker.** Wheel build, lazy load, the minimal edit → recompute → same
   decoder path, and errors surfaced.
7. **1D-6 measurements.**
   - fps (283k-event trace), warm edit → first frame, cold load, page weight, phone
     width, the network-log audit.
   - Write to RESULTS.md (measured).
   - **Any missed target → STOP with options.**
8. **1D-7 CI + deploy.**
   - `lab.yml`; push `lab1`; CI green on `lab1`.
   - Ask the owner to enable Pages, and decide the `ci.yml` red.
   - Then fast-forward `main`, the deploy runs, and the public URL is verified at phone
     width.
9. **1D-8 docs + close.**
   - `lab_web/README.md`, the BUNDLE_FORMAT "Readers" note (additive), and
     HOW_TO_RUN / PROJECT_STATE / RESULTS.
   - SESSION_LOG checkpoint, final regression, commit, stop.

## L. ACCEPTANCE CRITERIA (each objectively checkable)

1. `lab_web/COLCON_IGNORE` exists, and `colcon list` does not include `lab_web`.
2. Exact-pinned `package.json` and a committed lockfile. `npm ci && npm run build`
   succeeds, and two builds give an identical `dist` sha256.
3. The TS decoder decodes **all six golden fixtures** (five 1.0 and one 1.1) **and the
   three 1C bundles**. For every array of every bundle, the sha256 of the decoded LE
   bytes equals Python's (`expected.json`). The `content_hash` and map hash are
   recomputed in TS and equal the manifests.
4. Every case in the invalid corpus is refused by Python (pytest) **and** by TS (vitest),
   with a matching error class.
5. The canonical-JSON corpus (≥ 1,000 cases) matches Python byte-for-byte and
   hash-for-hash.
6. The existing `coco_lab` golden-bundle tests are unmodified and green. The
   `coco_lab` / `coco_lab_ros` / `gazebo_models` / `custom_teleop` counts equal the 1D-0
   baseline, with 0 failed and 0 skipped.
7. The guard test finds no priority queue, neighbour generator or heuristic function
   in `lab_web/src`. Every rendered trace comes from a bundle written by `coco_lab`.
8. For the display rule:
   - cursor checkpoints and hover samples equal the Python expectations;
   - backward scrub equals forward replay;
   - the plan-point orientation oracle passes for all three 1C bundles.
9. The player supports play, pause, step, scrub, speed, space and arrows, and hover
   g/h/f. The palette is Okabe–Ito (tested constants). Reduced motion is verified in the
   browser harness.
10. Recorded-run data is accessible to the renderer: gt, amcl and plan are drawn for the
    three 1C bundles. The synthetic fixture shows "no geo — cannot place" and
    "cmd: not captured".
11. A ModeBadge is visible in every state, and its text follows `source_kind` as
    decided.
12. A worker edit on the edit map produces a `glass-box` bundle with
    `tool='lab_web/pyodide'`, which is decoded by the same decoder and played. Pyodide
    is not requested before the first edit (BiDi network log).
13. Measured and in RESULTS.md: fps, warm edit, cold load and page weight. Each is either
    within its target, or reported missed with options, and 1D stops there.
14. Replay at 390 px wide: no horizontal scroll, the controls are clickable, and a
    screenshot is committed to `docs/data/lab1d/`.
15. The network log shows no third-party request except the pinned Pyodide CDN, and
    there are no cookies.
16. `lab.yml` is green on `lab1`. After the owner's actions, `deploy` is green on `main`
    and the public URL loads at phone width (checked through the harness).
17. SESSION_LOG 1D entry; the docs are updated; `mission nav2_params.yaml` sha256 is
    still `06c308af…`.

## M. MILESTONE BOUNDARY

- **1D implementation is done** at criteria 1–15 and `lab.yml` green on `lab1`.
- **1D is CLOSED** at criteria 16–17. That depends on two owner actions: enabling Pages,
  and the ruling on the pre-existing `ci.yml` red before the `main` fast-forward.
- 1E's precondition ("site deploying") is met only then.

Not in 1D:
- 1E's settings, badge, race, predict, share links, challenge, "Driven by COCO" plot and
  exhibit;
- user bundle upload;
- Live and Sketch modes;
- any ROS, arbiter or Nav2 change;
- any change to `coco_lab`'s algorithms or bundle schema.

If the wheel needs a packaging change, that is a stop-and-ask.

## N. EXACT NEXT ACTION

In a fresh session on branch `lab1` at `ca8ce79`, execute **1D-0**:
1. Re-measure the per-package test baseline (`coco_lab` pip venv and colcon overlay,
   `coco_lab_ros`, `gazebo_models`, `custom_teleop`).
2. Look up and record the current Pyodide release and the exact web-toolchain and Node
   LTS versions to pin.
3. Commit this plan as `docs/labs/PHASE_1D_PLAN.md`, with a SESSION_LOG "1D-0" entry.
4. Push `lab1`, then stop for approval before 1D-1.
