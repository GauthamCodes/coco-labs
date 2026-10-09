# Arena cold start (M1.5)

M1's target: first visible computation within 10 s of opening the URL on
a phone over mobile data. M0 measured the v1 path at a **12.9 s median**
(6.6–42.9 s, laptop, live CDN), dominated by the CDN download. Every number
here is **MODEL, measured on the development laptop** (i5-13420H, headless
Chromium 156, Playwright); the phone is Gautham's to measure
([PHONE_MEASURE.md](PHONE_MEASURE.md)).

## What changed

| Change | Effect (measured) |
|---|---|
| **Pyodide self-hosted** from the pinned npm package (`generated/pyodide/`), same origin as the page | no connection to a CDN; stable timings (below) |
| **Trimmed stdlib**: `python_stdlib.zip` reduced to the 142 files the Arena path imports (`lab_web/tools/arena_stdlib.txt`, measured by `tools/perf/stdlib_usage.mjs`) | 2,545,637 → 775,763 B; Arena ready −421 ms on Wi-Fi, −1,647 ms on 4G (n = 10 each) |
| **No micropip, no wheel**: `coco_lab` is a 191,750 B zip of its sources, sha256-checked and unpacked into Pyodide's file system | one request and an install step fewer |
| **Arena world rasterised per rectangle**, not per cell × rectangle (identical output, tested) | `arena_map` 780.7 → 9.8 ms, Arena init 1,036.8 → 274.5 ms (Pyodide-in-Node); state hash unchanged |
| **The worker starts when the page opens** (README §5.5), code-split from the v1 labs | Pyodide loads while the visitor watches; the Arena never downloads v1 code |

The trimmed stdlib changes nothing the Arena does: the same session gives
identical per-tick hashes, hash chain, plans and streamed batches on the
trimmed and the full stdlib (`lab_web/test/arena_runtime.test.ts`, CI).

## Results (n = 10 fresh browsers each, median and range)

Served by `lab_web/tools/perf/serve_dist.mjs`, which gzips like GitHub
Pages (Pages serves `application/wasm` gzip-encoded: measured on a
Pages-hosted 325 KB `.wasm`, 2026-10-08). Throttling is Chromium's network
emulation on the page (it reaches the worker's downloads too: unthrottled
2.1 s vs uncompressed-4G 12.7 s, so it applies). Profiles: **Wi-Fi** 30 /
15 Mbit/s, 20 ms; **4G** 9 / 1.5 Mbit/s, 170 ms. "Arena ready" = Pyodide,
coco_lab and the World built, in ms since navigation.

| Pyodide source | Link | Arena ready | Pyodide ready | Bytes (page + worker) |
|---|---|---|---|---|
| self-hosted, trimmed | none (loopback) | **2,087** (2,055–2,182) | 1,556 (1,515–1,638) | 4,944,244 |
| self-hosted, trimmed | Wi-Fi | **3,605** (3,569–3,669) | 3,062 (3,025–3,121) | 4,944,244 |
| self-hosted, trimmed | 4G | **7,301** (7,185–7,411) | 6,769 (6,727–6,830) | 4,944,244 |
| self-hosted, full stdlib | Wi-Fi | 4,026 (3,987–4,137) | | |
| self-hosted, full stdlib | 4G | 8,948 (8,892–9,046) | | |
| jsDelivr CDN (v1's way), full stdlib | Wi-Fi + the real internet | 76,046 (4,484–90,958) | 75,507 (3,915–90,403) | 6,515,377 |
| jsDelivr CDN (v1's way), full stdlib | 4G + the real internet | 9,124 (8,734–80,346) | 8,580 (8,190–79,809) | 6,514,922 |

**Goal to first plan events** (warm, after Arena ready): median 89–104 ms
in every configuration (range 68–133 ms). This includes waiting for the
next 100 ms tick, because a goal is applied at the start of a tick; the
visible-frontier criterion is measured with the renderer (M1.6/M1.10).

Console errors: **0** in all 70 runs.

Evidence: `docs/v2/data/m1/coldstart/m15_*.json` (every run's marks,
bytes by host, errors); stage timings inside Pyodide:
`arena_node_before.json`, `arena_node_after_raster.json`.

## What these numbers do and do not say

- **Not the phone.** Laptop CPU, emulated links. The 4G profile is a fair
  mobile link, not a measurement of one; Gautham's phone run decides the
  criterion.
- **Not yet "first visible computation".** "Arena ready" means the model
  can compute; drawing it is M1.6, and attract mode (M1.8) shows a
  precomputed recording before that. The cold-start criterion is closed in
  M1.10 with the renderer in place.
- **The CDN rows are not a controlled comparison.** In 11 of 20 CDN runs
  Pyodide took over 20 s to become ready: a download from jsDelivr stalled (Pyodide's module
  arrived in 0.4–1.9 s every time); the stalls are not attributed. They
  match M0's wide CDN range (6.6–42.9 s) and are why self-hosting matters:
  every self-hosted range lies within −1.6 % to +4.6 % of its median.
- **`dist/` grows** by the self-hosted Pyodide (11,761,333 B on disk). The
  Arena page transfers 4,944,244 B in total (page, worker, Pyodide,
  coco_lab, spec), gzip-encoded where Pages would encode. The v1 labs' bundles (≈ 21 MB of M0's 23 MB)
  are untouched and are never fetched by the Arena.
