# ADR 0001 — How events cross from Python (Pyodide) to JavaScript

- **Status:** accepted, 2026-10-08 (M1.1)
- **Evidence class of every number here:** MODEL (the browser engine,
  Pyodide-in-Node), measured on the development laptop.
- **Evidence:** [`docs/v2/data/m1/transport/bench_220.json`](../data/m1/transport/bench_220.json),
  [`bench_400.json`](../data/m1/transport/bench_400.json); the harness is
  `lab_web/tools/perf/transport_bench.mjs`.

## Context

README §5.2 makes protobuf the storage schema for every event family
(`coco_schemas`), with generated Python and TypeScript. The algorithms run
in Python inside Pyodide, in a Web Worker; the renderer and the recorder
run in JavaScript. M1_PROMPT M1.1 asks to settle, before writing schemas,
whether Python should emit protobuf directly (if the runtime exists in
Pyodide and is fast), or emit columnar typed-array batches that TypeScript
encodes for storage — and to measure both if both are possible.

Two facts bear on it before any timing:

1. **Protobuf exists in Pyodide 314.0.7**: `protobuf` 7.34.1, a compiled
   wasm wheel (`upb` backend), 247,991 bytes downloaded (measured,
   `curl` of the pinned CDN file).
2. **`coco_lab` has no runtime dependencies, and a test asserts it**
   (`coco_lab/test/test_dependencies.py`: `install_requires=[]`, no runtime
   `depend` in `package.xml`). That is what lets the same package run in
   Pyodide, a plain venv (CI) and colcon unchanged. Emitting protobuf from
   Python would make `protobuf` a runtime dependency of the algorithms.

## What was measured

One real `coco_lab` trace — Dijkstra on a seeded grid (20 % blocked,
`random.Random(7)`, 8-connected, corner to corner), run inside Pyodide —
moved into JavaScript four ways. Columns: the v1 trace's ten
(`kind,row,col,sub,g,h,f,parent_row,parent_col,parent_sub`) plus the three
clocks every v2 event carries (`seq,tick,t_world`). Median of 7 after one
warm-up; Node v24.21.0, Pyodide 314.0.7, Intel i5-13420H (12 threads),
load average 2.5–2.7.

| Variant | 78,298 events (220²) | 258,263 events (400²) | Bytes (400²) |
|---|---|---|---|
| **A** Python `array` per column → `getBuffer()` → copied, transferable typed array | 21.4 ms Python + 3.0 ms to JS | 75.3 + 8.4 ms | 19,627,988 (raw) |
| **B** protobuf in Python, one message of packed columns, `SerializeToString` → JS | 26.3 + 0.7 ms | 92.2 + 4.4 ms | 11,791,140 |
| **C** protobuf in Python, one sub-message per event | 185.2 + 1.1 ms | 606.0 + 3.5 ms | 9,207,407 |
| **D** JavaScript encodes A's arrays into B's packed protobuf (`@bufbuild/protobuf` 2.15.0 `BinaryWriter`) | 13.1 ms | 41.1 ms | 11,791,140 — **byte-identical to B** (checked every run) |
| *the search itself, for scale* | *358 ms* | *1,284.7 ms* | |

Loading protobuf in Pyodide: `loadPackage('protobuf')` 120–130 ms with the
wheel already in Node's package cache, 5,533 ms on the first, uncached
fetch (one run, network-dependent); `import google.protobuf` 201–209 ms.
Loading Pyodide itself: 1,420–1,434 ms.

## Decision

**A + D. Python emits columnar typed-array batches; TypeScript encodes
protobuf for storage.**

- `coco_lab` stays dependency-free. Its event batches are columns of
  Python `array.array` (`'i'`, `'q'`/`'Q'`, `'d'`), one batch per family
  per emission, described by the same field names and numbers as the
  `.proto` message. The worker posts them as transferable `ArrayBuffer`s.
- `coco_schemas` owns the `.proto` files. TypeScript (`@bufbuild/protobuf`)
  encodes the columns into those messages when a run is stored (MCAP,
  zstd). Python generated code exists for tools and tests outside the
  browser; the browser never loads Pyodide's `protobuf` package.
- **Batches are columnar on the wire too** (packed repeated fields, one
  message per batch), never one message per event: C is 8× slower in
  Python than B for no gain the renderer can use.
- **Fidelity check (CI):** for a batch, the TypeScript encoding of the
  columns must equal the Python protobuf encoding of the same columns,
  byte for byte — exactly what D-vs-B already shows here. That ties the
  hand-written columnar emitter to the schema.

## Why not B

B is as fast as A, but it buys nothing the worker needs (the renderer
wants typed arrays, not protobuf), costs a 248 KB download plus about 0.2 s
of import on the cold-start path that M1 must cut (B.2: the M0 cold first
edit is already 12.9 s median against a 10 s phone target), and breaks a
tested invariant of `coco_lab`. If protobuf were ever needed inside the
worker, D shows TypeScript can produce the identical bytes in about half
the time Python takes.

## Consequences

- All of A's Python time above is converting the lists the v1
  `TraceBuilder` keeps into `array`s after the search. M1.4's generator API
  can append to `array`s as it goes, which may remove most of that cost.
  Not claimed until measured.
- Raw columnar bytes (A) are larger than protobuf (varints); that matters
  only for storage, which is protobuf + zstd.
- 64-bit integers cross as `BigUint64Array`; M1.1 keeps `seq` and `tick`
  as `uint64` in the schema but the browser may narrow them to `uint32`
  columns where a batch fits (a schema-level note, decided in SCHEMAS.md).
