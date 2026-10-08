# COCO Lab v2 — event schemas (`coco_schemas`)

The reference for README §5.2's trace system as built in M1.1. The
`.proto` files in [`coco_schemas/proto/`](../../coco_schemas/proto/) are
normative; this page explains them.

## Layout

| Piece | Where |
|---|---|
| `.proto` sources | `coco_schemas/proto/coco/<family>/v<major>/*.proto` |
| Generated Python | `coco_schemas/coco_schemas/gen/` (protoc 3.21.12; imports rewritten under `coco_schemas.gen`) |
| Generated TypeScript | `lab_web/src/schemas/gen/` (`@bufbuild/protoc-gen-es` 2.15.0, runtime `@bufbuild/protobuf` 2.15.0) |
| Channel registry | `coco_schemas/coco_schemas/channels.py` |
| v1 trace converter (lossless) | `coco_schemas/coco_schemas/trace_v1.py` |
| Run identity | `coco_schemas/coco_schemas/runid.py`, `lab_web/src/schemas/runid.ts` |
| Compatibility rules + baseline | `coco_schemas/coco_schemas/compat.py`, `coco_schemas/compat/v1.binpb` |
| Columnar emitter (Python, no protobuf) | `coco_lab/coco_lab/events.py` (`SearchEventColumns`, `stream`), fed by `coco_lab.search.search_events` (M1.4); bytes pinned by `coco_schemas/test/test_columns.py` |
| Columnar fast encoder | `lab_web/src/schemas/columns.ts` |
| Container (MCAP + zstd) | `lab_web/src/schemas/mcap.ts` |
| Cross-language vectors | `coco_schemas/test/vectors/` (written by `coco_schemas/scripts/make_vectors.py`) |

Regenerate after editing a `.proto`:

```bash
python3 coco_schemas/scripts/generate.py          # Python + TypeScript
python3 coco_schemas/scripts/generate.py --check  # what CI runs
```

## Channels

Named `coco.<family>.<name>.v<major>`. The major in the name is the
major of the message's protobuf package (`coco.plan.v1`); a test holds
them together. **Stream** channels carry `*Batch` messages; **static**
channels carry one record.

| Channel | Message | Kind | What |
|---|---|---|---|
| `coco.envelope.manifest.v1` | `coco.envelope.v1.Manifest` | static | the run's envelope (below) |
| `coco.world.grid.v1` | `coco.world.v1.WorldGrid` | static | occupancy grid (+ optional cost layer) |
| `coco.world.geometry.v1` | `coco.world.v1.WorldGeometry` | static | named shapes: walls, obstacles, bays, zones (M1.2) |
| `coco.robot.params.v1` | `coco.robot.v1.RobotParams` | static | wheel radius and separation, limits, footprint, LiDAR mount |
| `coco.robot.state.v1` | `coco.robot.v1.RobotStateBatch` | stream | pose the model/stack believes, commanded v and ω |
| `coco.truth.pose.v1` | `coco.truth.v1.TruthPoseBatch` | stream | ground truth: the ONE source (README §3 invariant 4), display only |
| `coco.sensor.scan.lidar.v1` | `coco.sensor.v1.ScanBatch` | stream | 2D LiDAR; scans concatenated, `count[k]` beams each; no return = +inf |
| `coco.plan.search.header.v1` | `coco.plan.v1.SearchHeader` | static | algorithm, heuristic, weight, tie-break, start, goal, graph params |
| `coco.plan.search.events.v1` | `coco.plan.v1.SearchEventBatch` | stream | push / expand / relax / path, with g, h, f and parent |
| `coco.plan.search.summary.v1` | `coco.plan.v1.SearchSummary` | static | status, expansions, pushes, relaxes, path cost / length / steps |
| `coco.plan.incremental.header.v1` | `coco.plan.v1.IncrementalHeader` | static | D\* Lite run description |
| `coco.plan.incremental.events.v1` | `coco.plan.v1.IncrementalEventBatch` | stream | expand / raise / update / change / path / move, g and rhs, round |
| `coco.input.events.v1` | `coco.input.v1.InputEventBatch` | stream | goals, teleop, STOP, planner choice, reset: applied at the start of `tick` |
| `coco.metrics.values.v1` | `coco.metrics.v1.MetricBatch` | stream | named numbers with units |
| `coco.annotation.text.v1` | `coco.annotation.v1.AnnotationBatch` | stream | text at a moment, optionally a place |

## The three clocks

Every event carries `t_world` (simulation seconds), `tick` (control cycle)
and `seq` (computation step) — README §5.2. In every `*Batch`, fields 1–3
are `seq` (uint64), `tick` (uint64), `t_world` (double), all repeated, one
value per row (a test enforces it for every stream channel). A search runs
inside one tick, so its rows share `tick` and `t_world` and `seq` orders
them. Per-batch scalars (e.g. `search_id`) come after the columns.

## Columnar, end to end (ADR 0001)

A batch is **one message of packed columns**, never one message per
event. In the browser, Python emits `array.array` columns with the proto
field names; the worker posts them as transferable buffers; TypeScript
encodes them (`columns.ts`, driven by the generated descriptor) only when a
run is stored. Pyodide never loads protobuf. The TypeScript bytes equal
Python protobuf's `SerializeToString()` of the same message, byte for byte
(`lab_web/test/schemas.test.ts`, against `search_batch.binpb`).

64-bit columns (`seq`, `tick`) are `BigUint64Array` in the browser.

## The envelope and `run_id`

`Manifest` carries `run_id`, the canonical spec bytes and their sha256,
the seed, the tier (`ARENA`, `STACK`, or `TRACE` for a bare algorithm
trace), the evidence class (`MODEL`, `STACK`, `REMOTE`, `HARDWARE`,
`UNRESOLVED`, `CONCEPT`; README §3), the engines with exact versions or
SHAs, the channel list, provenance (created, tool, git SHA and dirty flag,
source, note) and `coco_schemas`' version.

```
spec_sha256 = sha256(spec bytes)                                   hex
identity    = {"engines": [[name, version], ...] sorted by code point,
               "seed": <integer, 0 <= seed < 2^64>,
               "spec_sha256": spec_sha256}
run_id      = sha256("coco.run_id.v1\n" + canonical_json(identity))  hex
```

`canonical_json` is Python's `json.dumps(sort_keys=True,
separators=(',', ':'), ensure_ascii=True)` — the same canonical form as
`coco_lab.bundle.canonical_json` and `lab_web/src/bundle/canonical.ts`. The
seed is written as an exact decimal integer (TypeScript keeps it a
`bigint`). Same spec bytes, seed and engines give the same `run_id` in
Python and TypeScript; `coco_schemas/test/vectors/run_id.json` pins both.
What makes spec bytes canonical is the spec's own definition (the World
Spec's, M1.2).

## Lab 1 traces, without loss

`trace_v1.search_from_v1` maps a v1 trace (`coco_lab.trace`) onto
header + events + summary, and `search_to_v1` maps it back. Lossless is
tested strictly — equal dict AND identical canonical JSON (1 stays 1,
1.0 stays 1.0, `None` stays `None`) after a real protobuf
serialize/parse — on every Lab 1 bundle in the repository (the six
`coco_lab` fixtures and the three recorded full-stack runs in
`docs/data/lab1c/bundles/`) and on 1,000 seeded maps × 5 algorithms. How:

- the open-ended `graph` dict is `Params`, an ordered list of typed
  scalars (bool / int / double / string kept apart);
- `weight` and the summary's path fields are proto3 `optional`, so "absent"
  (`None`) and `0` differ;
- event kinds are v1's codes + 1 (0 is `UNSPECIFIED` in proto3);
- any v1 header or summary field the schema does not carry is **refused**,
  never dropped.

D\* Lite's columns map the same way; v1 wrote infinity as `-1`, v2 writes
IEEE `+inf` (tested both ways).

## Compatibility within a major

`coco_schemas/compat.py` compares the schemas against the committed
baseline `compat/v1.binpb` (CI runs it in `coco_schemas`' tests). Allowed:
new packages, messages, enums, fields, enum values. Refused: removing,
renaming, renumbering or retyping a field, changing its label or
`optional`-ness, removing a message or enum, changing an enum value's
number — unless the field's number AND name are reserved. A breaking
change needs a new major package (`coco.<family>.v2`) and a converter
(README §3 invariant 5). The baseline is written once per major
(`generate.py --write-baseline`) and never edited afterwards.

## Container: MCAP + zstd

`lab_web/src/schemas/mcap.ts`:

- profile `coco`; the manifest is the first message (log time 0) and the
  metadata record `coco` repeats its `run_id`;
- each channel's MCAP schema is its message's protobuf `FileDescriptorSet`
  (encoding `protobuf`), so generic MCAP tools decode it;
- log time = `t_world` in integer nanoseconds; `sequence` = the batch's
  first `seq`;
- chunks are zstd-compressed when a compressor is injected (Node's built-in
  `zlib.zstdCompressSync` in build tools); reading uses `fzstd` (pure JS).

Arena-model replays need not be stored as MCAP at all: spec + seed + input
log re-simulates them (README §5.2).

## CI checks

| Check | Where |
|---|---|
| Generated Python is current | `coco_schemas/test/test_generated.py` (CI workflow, colcon) |
| Generated TypeScript is current | `lab.yml`, `generate.py --lang ts --check` |
| Within-major compatibility | `coco_schemas/test/test_compat.py` |
| Channel names, clocks, families | `coco_schemas/test/test_channels.py` |
| Lab 1 traces without loss | `coco_schemas/test/test_trace_v1.py` |
| Python ↔ TypeScript bytes and run_id | `lab_web/test/schemas.test.ts` |
