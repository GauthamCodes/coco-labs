# G1.8 — M5 carry-overs: deterministic numerics (hash v3), the native gate, update isolation

Evidence class MODEL (the Arena model) and TESTED (the CI checks). Cloud container: Intel
Xeon 2.1 GHz × 4, Chromium (Playwright) on SwiftShader, CPython 3.12, Pyodide 314.0.7
(Python 3.14) in Node 24.21.0. No phone, no GPU.

## 1. Why CPython and Pyodide differed

G1.6 found it (`../g16/README.md`): at tick 0 of the Depot, 2 of 480 LiDAR ranges differ
in the last bit between CPython and Pyodide, and hash v2 encodes exact floats. The cause
is the C library, not the model: IEEE 754 fixes `+ - * /` and `sqrt` bit for bit but
not `sin`, `cos`, `atan2`, `exp`, `log` or `pow`, and glibc (x86-64, FMA variants picked
at load time) and musl (Pyodide's, compiled to WebAssembly) round some of them
differently. A LiDAR endpoint 1 ulp away can land in another costmap cell (M5's review:
`LocalWindow.index`'s `floor`), and from there trajectories diverge.

## 2. The fix: state hash v3 ([ADR 0010](../../../adr/0010-state-hash-v3.md))

`coco_lab/numerics.py`: fdlibm's `sin cos atan atan2 acos exp log` in pure Python on
exactly-rounded operations (`tan = sin/cos`, `hypot = sqrt` of a sequential sum),
switched in by hash version (`numerics.use`), with `x**2 / x**3 / x**0.5` written as
`sq / cube / root`. Every coco_lab module takes `math` from there; under v1 and v2 it is
the real `math`, so **old hashes are unchanged** — the coco_lab suite's v1/v2 goldens,
golden traces and bundle tests all pass. v3 goldens are new files:
`coco_lab/test/fixtures/v3/` (`tools/g1/make_v3_goldens.py --check` reproduces them).

New runs use v3 (the Arena page, the game, Compare's arms and live Arena); links and
records without `hv` stay v1, `hv: 2` replays under v2, M5's recorded Compare requests
(no `hash_version`) stay v2.

## 3. Three runtimes, one chain

A Fetch Rush session played in Chromium under v3 through the page's own keys
(`lab_web/tools/g1/fetch_play.mjs`; AUTO, GRAB, AUTO, DROP): 1 delivery, 0 contacts,
1,423 ticks, no page errors — [`browser_v3/browser_record.json`](browser_v3/browser_record.json).
Replayed:

| Runtime | Chain | Evidence |
| --- | --- | --- |
| Pyodide in Chromium (the page's worker) | `38ea10feb6de222943b9f631128d5e7297f5ba7c6ec02328b265344674cb6531` | `browser_v3/browser_record.json` |
| Pyodide in Node (`game_node.mjs --record`) | same | [`node_replay_v3.json`](node_replay_v3.json) |
| CPython 3.12 (`tools/g1/game_parity.py`) | same, every tick's hash, last hash and scorecard identical; first differing tick: none | [`cpython_parity_v3.json`](cpython_parity_v3.json) |

## 4. The native-vs-Pyodide gate (CI: `lab_web` job)

`lab_web/tools/g1/native_gate.mjs` runs `native_gate_cases.py` in CPython (the
installed coco_lab) and in Pyodide (the shipped packs) — M5's review requests (four-arm
control Compare `dwa rpp mppi dwa`, four-arm localisation `mcl mcl_augmented ekf mcl`,
goal (2.5, 2), 60 ticks; every global planner on Compare's costmap) and every tick's
hash of the G1.6 Fetch Rush record on the Depot. Rule: global families (planner events,
paths, summaries, costmap, state hashes, scorecard) exact; continuous families (poses,
particles, trajectories, distances, errors) within 1e-9; discrete fields exact;
`compute_ms` (wall clock) excluded.

| Case | Family rule | v3: compared / identical / failures | v2 (control): failures, max abs diff |
| --- | --- | --- | --- |
| planners | global (exact) | 818,951 / 818,951 / 0 | 0, 0 |
| fetch_rush | global (exact): every tick's state hash, the scorecard | 1,436 / 1,436 / 0 | 1,420, 6.7209207088581024e-09 |
| control | continuous (1e-9); discrete fields and hashes exact; compute_ms excluded | 6,440 / 6,440 / 0 | 1,063, 0.446011142799704 |
| localise | continuous (1e-9); discrete fields and hashes exact; compute_ms excluded | 25,500 / 25,500 / 0 | 240, 1.1102230246251565e-16 |

v3: **passed** (CPython 3.12.3 x86_64 vs Pyodide 314.0.7 in Node v24.21.0; [`native_gate_v3.json`](native_gate_v3.json)). v2: **failed**, as expected ([`native_gate_v2.json`](native_gate_v2.json)); its Fetch Rush hashes differ from tick 0 and its control maximum is M5's.

The v2 run is the control: the same cases, M5's numerics, M5's number.

## 5. Cost

Pyodide in Node, the same record (`browser_v3`), per model tick on the Depot, this
container ([`tick_cost.json`](tick_cost.json)):

| Hash | Median ms | p95 ms | Chain |
| --- | --- | --- | --- |
| v2 | 21.8 | 35.0 | `2700d00c39bf833b…` |
| v3 | 25.1 | 39.4 | `38ea10feb6de2229…` |

v3 / v2 median: ×1.15.

The pure-Python transcendentals cost time; most of it is `sin`/`cos` of LiDAR beam
directions, asked for three times a tick (walls, discs, boxes), so `numerics` keeps the
last 4,096 answers (pure functions: the same bits). Not a phone, not a browser:
G1.9 measures the game on the emulated phone.

## 6. Update isolation (CI: `lab_web in Chromium, Firefox and WebKit` job)

M5's review found an open build-A page claimed by build B's service worker and served
B's unversioned files (`openDocumentMixed: true`,
`docs/v2/data/m5/review/update-open-tab-ac3/checks.json`). Now:

- **Every URL is versioned by build ID or content hash.** Vite's files carry content
  hashes; everything else a page asks for is answered from *its* build: the service
  worker records each page's build (from the index it served it, and the page's
  `hello`) and serves it from that build's cache; the page's model worker loads Pyodide
  and the packs from `__b/<build>/…`, because a worker's requests carry no page.
- **"New version ready"** with **Save run** (downloads the game's record or the Arena's
  input log) and **Reload** — never an automatic reload; a run in progress is the
  player's.
- **Old caches go only when no page of that build is open** (checked on every page's
  hello and on activation); a cache still being filled by an install is left alone.

`lab_web/tools/update_isolation_check.mjs` (M5's probe, with assertions) serves a copy
of the built site as build A, opens a page, rebuilds in place as build B (A's files are
gone, as on Pages), lets B take over, and checks:

| Check | G1.8 worker | M5 worker (control) |
| --- | --- | --- |
| `openDocumentMixed_false` | pass | FAIL |
| `page_A_reads_A` | pass | FAIL |
| `new_version_notice` | pass | FAIL |
| `no_forced_reload` | pass | pass |
| `old_cache_kept_while_open` | pass | FAIL |
| `old_cache_deleted_once_closed` | pass | pass |
| `reload_consistent_B` | pass | FAIL |
| `model_worker_pinned` | pass | not run |
| `no_page_errors` | pass | pass |

[`update_isolation/checks.json`](update_isolation/checks.json), [`update_isolation_m5_control/checks.json`](update_isolation_m5_control/checks.json) (M5's `sw.template.js`, the same checks: mixed, as M5's review found).

Residual (stated, not tested): a page that loaded before any service worker controlled
it, and whose own build's worker never installed before a newer deploy, has no cache
of its own build to be served from; it shows "New version ready" like any other.
