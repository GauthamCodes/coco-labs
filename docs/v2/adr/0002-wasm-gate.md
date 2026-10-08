# ADR 0002 — The WebAssembly gate: port nothing (M1)

- **Status:** accepted, 2026-10-09 (M1.10)
- **Evidence class of every number here:** MODEL (the browser engine and
  Pyodide), measured on the development laptop (RTX 4050 laptop GPU,
  Chromium 156 headless through ANGLE unless stated) in its **power-saver**
  profile (`powerprofilesctl get`, governor `powersave`; recorded in the
  cold-start files). Phone numbers: **not measured** (Gautham, `?perf`).
- **Evidence:** `docs/v2/data/m1/` — `render/fps_stress_gpu_m110.json`,
  `responsiveness/responsiveness_gpu.json`, `timeline/timeline_check.json`,
  `coldstart/m110_*.json`, `determinism/determinism.json`; summarised in
  [`docs/v2/M1_RESULTS.md`](../M1_RESULTS.md).

## Context

The algorithms and the Arena model run in Python (`coco_lab`) inside
Pyodide, in a Web Worker. README §5 and M1_PROMPT M1.10 make WebAssembly a
**gate, not a plan**: "Port nothing unless a budget fails, and then only the
failing kernel, under trace-equivalence tests." CLAUDE.md's replaced
invariant says the same from the other side: any second implementation must
be trace-equivalent to the Python reference on the property-test corpus,
checked in CI. Porting has a standing cost — a second implementation to keep
equivalent forever — so it must buy a budget that would otherwise fail.

## The budgets (M1 B.4), measured on the final M1 build

| Budget | Measured | Verdict |
|---|---|---|
| Laptop: 60 fps with ~50,000 points, 20,000 segments, one grid texture | 60–61 fps every second for 10 s, p95 frame 17.3–17.9 ms | passes |
| First frontier node visible ≤ 100 ms after a goal click (warm) | median 40.4 ms, p95 70.8, max 71.5; 25 of 25 under 100 | passes |
| Seek < 100 ms | ≤ 0.6 ms in the browser on an 81,593-event search; < 100 ms on a 380k-event one (vitest) | passes |
| Laptop cold start < 10 s (self-hosted) | first visible computation 0.75 / 1.6 / 3.3 s (unthrottled / emulated Wi-Fi / emulated 4G); live model ready 5.0 / 6.6 / **10.8** s | passes for the first visible computation on every link; the live model on emulated 4G is over (see below) |
| Phone: 30 fps; first visible computation ≤ 10 s on mobile data | not measured | pending Gautham |

Two things decide whether any of this is a WebAssembly question:

1. **Where the time goes in the slowest number.** Of the live model's
   10.8 s on emulated 4G, **8.2 s** is Pyodide loading itself — downloading
   and compiling its own WebAssembly over a 9 Mbit/s, 170 ms link
   (`pyodide_module` 1,346 ms → `pyodide_ready` 9,539 ms, medians);
   `coco_lab`'s own start (unpack, World Spec, rasterise, first scan) is
   **1.2 s** on every link (medians 1,215–1,247 ms).
   Porting a `coco_lab` kernel to WebAssembly removes none of Pyodide's
   load and little of the rest. And the visitor is not waiting on it: the
   attract recording shows computation at 3.3 s on the same link.
2. **Model step cost is not near its budget.** The model steps at 10 Hz
   (100 ms); one tick costs 7.5 ms in Pyodide-in-Node, a 480-beam scan
   6.8 ms of it (M1.5, `docs/RESULTS.md`), and the responsiveness criterion
   passes with the search still in Python, because its events stream as it
   runs.

The one slow interaction measured — a goal clicked immediately after a
planner change (median 293 ms, max 4.0 s) — is a **queueing** problem: the
model re-plans the running goal synchronously before it sees the new one.
A faster kernel would shorten the wait without removing it; tick-budgeted,
cancellable planning removes it (`docs/IDEAS.md`, M2). It is not a B.4
budget.

## Decision

**Port nothing to WebAssembly in M1.** No agent-measured budget fails. The
gate stays shut until a measured budget fails — most likely the phone's, if
Gautham's `?perf` numbers miss 30 fps or 10 s — and then the procedure is:

1. Profile the failing budget on the device that fails it; name the kernel
   that dominates (renderer, model step, search, decode).
2. If it is a `coco_lab` kernel, port **that kernel only**, behind the same
   Python API, and add a CI test that its traces are identical to the Python
   reference's on the property-test corpus (`coco_lab/test/test_properties.py`)
   and its per-tick Arena hashes on the recorded sessions
   (`docs/v2/data/m1/determinism/`).
3. Re-measure the budget; keep the port only if it now passes.

B.6's early-decision trigger — the phone cannot plausibly reach 15 fps at
minimum detail — has not fired: the laptop renders at the display cap with
the stress load, and no phone number exists yet.

## Consequences

- One implementation of every algorithm (Python); determinism holds across
  Chromium, Firefox, WebKit and Pyodide-in-Node on 100 recorded sessions
  (15,000 ticks each, 0 differing), and CI keeps checking it.
- The phone numbers are the open risk. They are Gautham's to measure
  (`docs/v2/PHONE_MEASURE.md`); a miss reopens this gate with step 1 above.
