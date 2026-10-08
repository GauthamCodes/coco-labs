# lab_web — COCO Lab in the browser (Phase 1D, Lab 1.1)

> **Deprecated parts (COCO Lab v2, 2026-10-08).** The Canvas 2D renderers,
> the per-lab bundle/trace decoders and the six separate views are
> replaced in M1–M2 by one Three.js Arena on one trace envelope; the React
> + Vite + TypeScript shell is kept. **Every current view keeps working
> until its replacement ships.** Which part, which milestone:
> [`docs/v2/DEPRECATIONS.md`](../docs/v2/DEPRECATIONS.md).

The browser tier of COCO Lab. It **renders** search traces that `coco_lab`
produced, and **asks** `coco_lab` (running in the browser via Pyodide) to
recompute when you paint a map, change a search setting or start a race.
It never implements a search: no priority
queue, no neighbour generator, no heuristic
(`tools/test_tools.py::test_lab_web_src_has_no_search_implementation`).
This was v1's "COCO Lab" rule 8; v2 replaces it with a testable invariant —
a second implementation of an algorithm must be trace-equivalent to the
Python reference on the property-test corpus, checked in CI (`CLAUDE.md`,
"The replaced invariant"). Until such a check exists, the test above stands.

Plan: [`docs/labs/PHASE_1D_PLAN.md`](../docs/labs/PHASE_1D_PLAN.md).
Measurements: `docs/RESULTS.md`, "COCO Lab Phase 1D" and "COCO Lab 1.1,
Part A".
Not a ROS package: `COLCON_IGNORE` keeps colcon out.

## Run it

Toolchain: Node **24.21.0** (`.nvmrc`; `nvm install` reads it) and npm
11.19.0, which it bundles. Python with `coco_lab` importable (a plain venv,
or the colcon overlay), for the data build. No ROS.

```bash
cd lab_web
npm ci                                   # exact pins, from the lockfile
python3 tools/build_catalog.py           # = npm run tools: validate every bundle with coco_lab, build the wheel
npm run dev                              # http://localhost:5173/coco-labs/
npm test                                 # vitest: decoder, player, renderer
python3 -P -m pytest tools               # the Python half (needs coco_lab + pytest)
npm run build && npm run check:dist      # production build + static checks
npx vite preview                         # serve dist/ at http://localhost:4173/coco-labs/
python3 tools/browser/check.py http://127.0.0.1:4173/coco-labs/ out/   # headless Firefox
```

The base path `/coco-labs/` (the GitHub Pages project path) is
defined once, in `site.config.ts`; `LAB_BASE=/ npm run build` overrides it.
The Pyodide pin (314.0.7) lives beside it and fills the CSP in `index.html`.

## Layout

```
site.config.ts        base path + Pyodide pin (the only place either is written)
src/bundle/           the decoder: PURE TypeScript, no DOM, no React
  json.ts             lossless JSON (int vs float kept, exact ints, duplicate keys refused)
  pyrepr.ts           Python float repr
  canonical.ts        Python canonical JSON (code-point key order, ensure_ascii)
  sha256.ts gzip.ts   WebCrypto SHA-256; bounded gunzip with a magic check
  arrays.ts           unaligned little-endian arrays -> aligned copies (+ DataView path)
  decode.ts load.ts   bundle.py's structural checks, in Python's order; the catalog gate
  model.ts            the normalized DecodedBundle every renderer reads
src/trace/            cursor (display state at event k), hover (stored g/h/f), coords
src/render/           Okabe–Ito palette, pure RGBA layer builders, Canvas 2D, overlays
src/model/mode.ts     mode labels (rule 4) and sameInputs (rule 6)
src/lab/              Lab 1.1 page logic: settings LOOKUPS (never verdicts), brush
                      strokes, race synchronisation, the swept footprint's geometry
src/ui/               React: App, ModeBadge, Player, MapView, panels, Editor (useLab:
                      every worker request), SettingsPanel, Tools, Ladder, Race
src/loc/              Lab 2 (Localise): the loc-bundle decoder, catalog types, display arithmetic
src/map/              Lab 3 (Map): the map-bundle decoder (pinned to coco_lab/slambundle.py by
                      test/slamdecode.test.ts), catalog types, display arithmetic (view.ts)
src/ui/loc/ src/ui/map/  the Lab 2 and Lab 3 views, lazily loaded (?view=localise, ?view=map)
src/move/             Lab 5 (Move): the replan- and drive-bundle decoders (pinned to
                      coco_lab/movebundle.py by test/golden/move_expected.json), catalog
                      types, display bookkeeping (time lookup, the map at step k) -- no
                      controller, no D* Lite, no metric
src/ui/move/          the Lab 5 view, lazily loaded (?view=move): Replay of the Gazebo
                      controller runs, run 15, the D* Lite Sketch (coco_lab in Pyodide via
                      worker/recompute.py `replan_lab`)
src/live/             the Live tab's coco.v1 client (Phase 2)
src/worker/           the Pyodide worker, its protocol, recompute.py (glue only: recompute,
                      localise, mapping)
tools/                Python: expectations, corpora, catalog, tests; check_dist.mjs; browser/check.py
test/                 vitest suites; golden/ and invalid/ are GENERATED by tools/ (byte-checked)
```

Data flow: `catalog.json` → fetch → `parseManifest` → bounded gunzip →
`decode` (structural checks, content and map hashes recomputed) →
`requireValidated` (hash must be one `coco_lab` validated) →
`DecodedBundle` → cursor/coords → layers → canvas. A paint stroke, a
settings change or a race sends the current bundle's **bytes** and the
change to the worker, which returns one to four new bundles' bytes; they
go through the same decoder.

Catalog 1.1 adds three blocks, all computed by `tools/build_catalog.py`,
never by the page: `settings` (per move model, `coco_lab.heuristics.analyse`
and `coco_lab.search.suboptimality_bound`, the latter at each of the
weight slider's 21 positions, 0 to 5 in 0.25 steps), `ladder` (the three
map rungs) and `footprint` (COCO's footprint, derived from
`coco_config/robot.py`, with its derivation). Part B adds `exhibit`
(`exhibit.json`, built from committed evidence only) and, on each recorded
run, `tracking` (`tracking/<id>.json`, 1C's tracking-error series,
recomputed by 1C's code and checked against the recorded statistics); both
are fetched only when shown.

**Share links** (`src/lab/share.ts`, format v1) name the bundle, the
settings, the map edits and a 12-hex prefix of the trace's sha256. Opening
one reruns coco_lab on those inputs and says whether the trace is
identical. The round trip is tested in both languages against
`test/golden/share_vectors.json` (`tools/make_share_vectors.py`).

## The decoder and its validation boundary

The content hash is sha256 over Python's canonical JSON of the manifest. A
`JSON.parse`/`JSON.stringify` round trip does not reproduce those bytes
(`252.0` → `252`, `1e-05` → `0.00001`, UTF-16 key order, `\u` escapes), so
the decoder parses losslessly and re-serialises the Python way. It agrees
with Python on 1,217 seeded JSON texts and 4,000 float reprs
(`test/golden/json_corpus.json`), and on every array of all nine bundles
(six golden fixtures, three 1C runs; `test/golden/expected.json`).

**The browser checks structure; `coco_lab` checks semantics.** The TS
decoder ports `bundle.py`'s tier (i): `parse_manifest`, `decode` up to
construction, provenance, `Trace.validate`, the run block and its agreement
with the trace header, the map and its hash, the 1.1 recording. It adds
one check a renderer needs: every event and the start/goal are in the map.
It does **not** port tier (ii) — start/goal free, event ordering against
the graph, the path moving between neighbours, the path cost — because
that needs the graph's neighbour and cost functions, which are algorithm
code. `coco_lab` itself runs those: at site-build time
(`tools/build_catalog.py`: `load_bundle` + `replay` for glass-box) or in
the worker (`write_bundle` validates). The browser draws a bundle only if
its content hash is a catalog entry, or the worker just produced it.

It is **stricter than Python** in documented ways, never looser: duplicate
JSON keys (Python keeps the last), `NaN`/`Infinity` literals anywhere
(Python refuses them only where it hashes), non-ASCII digits in `version`,
a `map.meta` that is a list of pairs. Test: `test/invalid.test.ts`.

## What the player shows

- **Display rule** (a presentation choice over the event log, pinned against
  the Python oracle in `tools/common.py`): a cell's state at cursor k is the
  max over events i < k at that cell of push/relax = open, expand = closed,
  path = path. On a (cell, heading) graph a cell shows its highest-precedence
  sub (path > closed > open); hover lists every sub, including the goal sink
  (sub 9).
- **Hover** shows the stored g, h and f of each sub's last event before k;
  the `f` label says what the algorithm used (`f = g + h`, BFS: depth).
- Metrics and recorded-run results are displayed **as stored**; display
  rounding (6 significant digits) is presentation only.
- **Not shown in 1D** (kept in the model, not drawn): `relax` is drawn as
  open, like a push, so a relaxation is visible only in hover; the `parent`
  columns (in the model and the hover data, not displayed; no parent arrows); `cmd` (v, w) streams
  (counted, plotted in 1E); `recording.meta`'s arbiter and collision-monitor
  timelines and `checks` (in the model, not rendered); map `meta`.
- **Recorded runs:** ground truth, AMCL and the published plan are drawn only
  when the map has geo and the stream's frame is the map's frame; otherwise
  the reason is shown ("no geo — cannot place"). A missing stream is named
  ("cmd: not captured"). Nothing is decimated.

## Modes (rule 4)

The badge text comes from the bundle's own `provenance`:

| provenance | badge |
|---|---|
| `recorded-run` | Replay — recorded real run |
| `glass-box`, `tool` = `lab_web/pyodide` | Replay — computed in your browser by coco_lab |
| any other `glass-box` | Replay — coco_lab computation (glass-box) |
| `sketch` | Sketch — coco_lab's 2D model, not the robot (Labs 2 and 3); with `tool` = `lab_web/pyodide`: Sketch — computed in your browser by coco_lab |

Lab 3's Replay of the recorded tour carries `recorded-run` provenance (the
bag's sha256 and sim-time range) and is labelled "Replay — a recorded run of
the real stack in Gazebo". The Live tab (`src/live/`) talks to a local or
scheduled COCO stack over coco.v1 only (`docs/live/LIVE.md`); nothing else in
lab_web talks to ROS.
*(Until 2026-10-05 this section said `sketch` was "reserved… never produced"
and "Live mode does not exist here"; both stopped being true in Phases 2 and
3.)*

## Pyodide

Pinned **314.0.7** (Python 3.14.2, micropip 0.11.1), from
`https://cdn.jsdelivr.net/pyodide/v314.0.7/full/`. The worker is created on
the first paint stroke, settings run or race, never before (verified: no
CDN request before one).
It installs `coco_lab` from the wheel this site serves, after checking its
sha256 against the catalog; micropip accepts the wheel's `.data/` (ament
marker, `package.xml`) as it is. No other package is installed. Recorded
runs are not editable; glass-box bundles are painted with a 1, 3 or 5 cell
brush (a drag is one stroke), on a phone too once a paint tool is chosen.
The glue caches each bundle it validated or wrote by content hash, so only
the first change to a bundle pays for `load_bundle`.

## Known limitations

- Measured in **headless** Firefox 156 on the development machine; a headed
  browser, a phone or another engine was not measured. Safari < 16.4 lacks
  `DecompressionStream`; no polyfill.
- GitHub Pages serves `arrays.bin.gz` as `application/gzip` with no
  `Content-Encoding` (measured at the Phase 1 closure). `vite dev`/`preview`
  were measured to add `Content-Encoding: gzip` to `.gz` files, which the
  decoder refuses (it never repairs); `vite.config.ts` serves them as plain
  bytes instead.
- A bundle is decoded fully in memory (the hash needs every byte): peak
  about 2–2.5 × its raw size (14.1 MB for the largest served, the native
  arena). Lazy decoding is future work, needed only past ~64 MB.
- The phone check is a 390 × 844 headless viewport, not a phone.
