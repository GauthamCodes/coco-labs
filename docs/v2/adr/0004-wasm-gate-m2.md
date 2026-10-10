# ADR 0004 — The WebAssembly gate at M2: port nothing again

- **Status:** accepted, 2026-10-10 (M2.11). Supersedes nothing; ADR 0002
  (M1) stands and this repeats its test on M2's heavier model.
- **Evidence class of every number here:** MODEL (the browser and Pyodide),
  measured on the development laptop (i5-13420H, RTX 4050 laptop GPU,
  Chromium headless through ANGLE) in the **balanced** profile **on AC**, the
  owner's measurement standard (each harness records profile, AC state,
  governor and load). Phone: **not measured** (Gautham).
- **Evidence:** `docs/v2/data/m2/m211/` — summarised in
  [`docs/v2/M2_RESULTS.md`](../M2_RESULTS.md).

## Context

README §5 and the M2 prompt (M2.11) keep WebAssembly a gate: "port only a
kernel that fails a budget, under trace-equivalence tests". M2 added the
whole loop to the Python model: MCL and EKF localisation, four SLAM
algorithms, three local controllers (MPPI the heaviest: 128 rollouts × 28
steps per tick) and the fetch mission. If any of them pushed a laptop budget
over, this is where it would show.

## The budgets, measured on the final M2 build

| Budget (M2 B.3, agent rows) | Measured | Verdict |
|---|---|---|
| 60 fps: fetch mission, all lenses' default layers, + 2,000 particles, 1,000 × 56-step rollouts, a full grid (rebuilt at 10 Hz) | median 61, minimum 60 fps over 20 s | passes |
| Goal after a planner change: median ≤ 100 ms, max ≤ 500 ms | median 43.7, max 66.5 ms, 25/25 < 100 | passes |
| Seek ≤ 100 ms on a 5-minute fetch-mission recording | max 33.1 ms to the redrawn frame (call ≤ 0.3 ms), 10 seeks over 3,022 ticks (a recording in which 1 of 4 fetches completed; M2_RESULTS "Found while measuring") | passes |
| First visible computation ≤ 10 s, emulated 4G | median 3,005 ms (2,956–3,246), n = 10 | passes |
| Live model ready ≤ 10 s (Plan lens), emulated 4G | median 7,870 ms (7,837–8,158), n = 10 | passes |
| Other lenses ready within 3 s of selection, warm cache | slowest pack 205 ms (cold 207 ms) | passes |

## Decision

**Port nothing.** No budget fails, so no kernel qualifies. The model step
with every subsystem on took a median of 34.1 ms per 100 ms tick over 520
ticks in the measured stress run (the `?perf` panel's `step`, in the
committed screenshot `render/fps_m2_gpu.png`), so
the model has headroom at real time; it is the renderer's budget, not the
model's, that the stress scene exercises, and it holds 60 fps.

## Consequences

- No second implementation exists, so no trace-equivalence test is added.
- The question is re-asked at M3 with Gautham's phone numbers: a phone is
  the likeliest place for the model step to stop fitting in 100 ms.
