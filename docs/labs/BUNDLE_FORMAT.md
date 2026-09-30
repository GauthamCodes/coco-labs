# Bundle format v1

A **bundle** is one search run, packaged so that it can be saved, moved,
checked, drawn and (for glass-box runs) replayed without ROS and without
trusting whoever produced it.

- Schema name: `coco_lab.bundle`
- Versions: `"1.0"`, and `"1.1"` (Phase 1C, additive: the recorded-run
  streams, below). The writer emits `"1.0"` for every bundle without a
  recording, byte-for-byte as before, and `"1.1"` only for a recorded-run
  bundle that carries one.
- Reference implementation: `coco_lab/coco_lab/bundle.py`
- Pinned by: `coco_lab/test/test_bundle.py::test_the_doc_matches_the_implementation`
- Golden fixtures: `coco_lab/test/fixtures/bundles/`. Phase 1D's TypeScript
  decoder is tested against these bytes. `test_bundle.py` regenerates them
  and requires byte equality, so they cannot drift from the writer.

It carries the trace of [`TRACE_SCHEMA.md`](TRACE_SCHEMA.md) (unchanged, v1)
and the map of [`MAP_FORMAT.md`](MAP_FORMAT.md) (v1, embedded).

## Layout

A bundle is a **directory** holding exactly two files, with fixed names:

| file | content |
|---|---|
| `manifest.json` | canonical JSON (sorted keys, no whitespace, UTF-8, no NaN/Infinity) |
| `arrays.bin` **or** `arrays.bin.gz` | the typed arrays, concatenated; gzipped with `mtime` 0 when `encoding.compression` is `gzip` |

The manifest never names a file. A bundle therefore cannot direct a read or a
write anywhere:
- `write_bundle(bundle, out_dir)` writes those two names inside the directory
  its caller chose, and refuses to overwrite an existing bundle there.
- `load_bundle(dir)` reads those two names and nothing else.

## Manifest

| field | type | meaning |
|---|---|---|
| `schema` | string | always `coco_lab.bundle` |
| `version` | string | `"MAJOR.MINOR"`, currently `"1.0"` |
| `provenance` | object | where the run came from (below) |
| `run` | object | every input of the search (below) |
| `map` | object | the embedded map's `id`, `content_hash`, `width`, `height`, `cost_layer`, `geo`, `meta`. Its layers are arrays |
| `trace` | object | the trace's `header` and `summary`, exactly as `TRACE_SCHEMA.md` defines them. Its event columns are arrays |
| `arrays` | list | one entry per array, in file order: `{name, dtype, count, offset, byte_length}` |
| `encoding` | object | `{byte_order: "little", compression: "none" \| "gzip"}` |
| `content_hash` | string | `sha256:<hex>`, defined below |

### `provenance`

| field | type | meaning |
|---|---|---|
| `source_kind` | string | `glass-box` (`coco_lab` ran the search itself; every input is recorded), `recorded-run` (a planner on the live stack, recorded with rosbag2), or `sketch` (made in the browser) |
| `coco_lab_version` | string | `coco_lab.__version__` of the writer |
| `git_commit` | string or null | 40-hex SHA of the writer's work tree, or null when unknown. Never guessed |
| `git_dirty` | bool or null | whether that tree had uncommitted changes. Null exactly when `git_commit` is null |
| `created_utc` | string | `YYYY-MM-DDTHH:MM:SSZ` |
| `seed` | int or null | the seed that produced the inputs, where one did |
| `episode_spec_hash` | string or null | the EpisodeSpec's hash, where the run came from an episode (Phase 1C onward) |
| `rosbag` | object or null | `{sha256, sim_time_start, sim_time_end}`. **Required** for a `recorded-run`, refused otherwise |
| `tool` | string or null | the program that wrote the bundle |

### `run`

| field | type | meaning |
|---|---|---|
| `algorithm`, `heuristic`, `weight`, `tie_break` | as in the trace header | must equal the trace header's values |
| `start`, `goal` | `[row, col]` | cells on the embedded map |
| `graph` | object | the searched graph's `describe()` block; must equal the trace header's `graph` |
| `model` | object | the move model, i.e. the keyword arguments that rebuild the graph from the map. For `grid`: any of `connectivity`, `diagonal_cost`, `corner_cutting`, `cost_weight`, `cost_scale`, `unknown`. For `heading_grid`: any of `turn_penalty`, `corner_cutting`, `unknown`. Other keys are refused |
| `map_hash` | string | the embedded map's `content_hash` |

### Arrays

| name | dtype | count |
|---|---|---|
| `trace.kind` | `u8` | events |
| `trace.row`, `trace.col`, `trace.sub` | `i32` | events |
| `trace.g`, `trace.h`, `trace.f` | `f64` | events |
| `trace.parent_row`, `trace.parent_col`, `trace.parent_sub` | `i32` | events |
| `map.occupancy` | `u8` | width x height, row-major, 0 free / 1 occupied / 2 unknown |
| `map.cost` | `f64` | width x height; present exactly when `map.cost_layer` is true |

- The order is exactly the order above.
- Arrays are contiguous: each `offset` is the previous array's end, starting
  at 0.
- `byte_length = count x size(dtype)`, where `u8` is 1 byte, `i32` is 4 and
  `f64` is 8.
- Every array is little-endian.
- `f64` keeps a trace's `g`, `h` and `f` exact, with no rounding in transit.

## Version 1.1: the recording (recorded-run only)

Added in Phase 1C (owner decision D-5) so a bundle exported from a rosbag
can carry what was recorded around the search. Pinned by
`coco_lab/test/test_bundle_recording.py`; golden fixture
`recorded_run_synthetic_1_1` (synthetic streams, marked so in its `meta`; it
is not evidence of any run).

A 1.1 manifest may hold one more top-level field, `recording`, allowed only
when `provenance.source_kind` is `recorded-run`:

| field | type | meaning |
|---|---|---|
| `groups` | object | one entry per stream PRESENT: `{frame, source, count}` -- the frame its poses are in, the topic it came from, its sample count |
| `missing` | list | every stream NOT captured. Each of the four groups is in exactly one of `groups` and `missing`: a missing stream is named, never zero-filled or silently absent |
| `run_id` | string | the run's id |
| `meta` | object | anything else the exporter records (result, timeline, hashes) |

Each present group adds `f64` arrays after the map's, in this order:

| group | arrays (all `f64`, one value per sample) |
|---|---|
| `gt` | `recording.gt.t`, `recording.gt.x`, `recording.gt.y`, `recording.gt.yaw` -- ground-truth pose |
| `amcl` | `recording.amcl.t`, `recording.amcl.x`, `recording.amcl.y`, `recording.amcl.yaw` -- the localisation belief |
| `plan` | `recording.plan.x`, `recording.plan.y`, `recording.plan.yaw` -- the path handed to the controller |
| `cmd` | `recording.cmd.t`, `recording.cmd.v`, `recording.cmd.w` -- wheel commands: linear x (m/s), angular z (rad/s) |

`t` is seconds on the recording's clock and never decreases; every value is
finite; every column of a group has the group's `count`. The checks refuse
a recording on anything but a recorded-run, a recording under version
`"1.0"`, recording arrays without the block, and every violation above.

**Compatibility.** Every 1.0 bundle is a valid 1.1 bundle, and a 1.1
reader reads it unchanged. The reverse does not hold for a bundle WITH a
recording: a 1.0 reader's array table is exact, so it refuses one, with an
error rather than a misreading. A 1.1 bundle without a recording is
written as `"1.0"` and is readable by both.

## `content_hash`

The SHA-256 of:

1. the canonical JSON of the manifest with three fields removed:
   `content_hash`, `encoding` and `provenance.created_utc`;
2. then one newline byte;
3. then the **uncompressed** array bytes.

So two bundles of one run, made at different times, or one gzipped and one
not, have the same `content_hash`. Anything else that differs, including
one bit of one array, changes it.

## Checks on load

`load_bundle` treats a bundle as untrusted. It refuses, and never repairs:

- **Size bounds, before allocating:**
  - the manifest is at most 1 MiB;
  - the arrays are at most 256 MiB in all, and gzip is decompressed with a
    bound, so a gzip bomb stops at the declared size plus one byte;
  - the map is at most 16,000,000 cells;
  - there are at most 50,000,000 events;
  - JSON nesting is at most 32 deep.
- **Only JSON and fixed-width numbers are parsed.** No pickle, and nothing
  is executed.
- **Structure:**
  - the schema must match, and an unknown MAJOR is refused;
  - the required fields must be present and of the right type;
  - the array table must be exactly the list above, contiguous, with
    consistent lengths;
  - the data length must be exact, so truncation and padding are both
    refused;
  - `content_hash` must match;
  - `g`, `h` and `f` must be finite.
- **Map:** it must pass `MAP_FORMAT.md`'s validation, and its hash must
  equal both `map.content_hash` and `run.map_hash`.
- **Trace:** it must pass `Trace.validate()` (`TRACE_SCHEMA.md`'s
  invariants).
- **Run:** a known algorithm and tie-break; a weight exactly for
  `weighted_astar`; `start` and `goal` as `[row, col]`; a known graph kind;
  no unknown model keys; agreement with the trace header.
- **Trace on the rebuilt graph:** the graph is rebuilt from the embedded map
  and `run.model`, and must `describe()` exactly as the header says. Then:
  - `start` and `goal` must be in bounds and free;
  - every event must be in bounds;
  - the first push must be the start;
  - a relax or expand must be of a state already pushed and not yet closed;
  - the parent of a push or relax must already be expanded;
  - the path must begin at the start, move only between neighbours, carry
    `g` equal to its running edge-cost sum, and end at the goal;
  - `summary.path_cost` must equal the path's cost recomputed on the map,
    within 1e-9 relative.

A MINOR version, and fields the reader does not know, are accepted and
ignored.

## Replay

`replay(bundle)` reruns a **glass-box** bundle's search: it rebuilds the
graph from the embedded map and `run`, then compares the new trace with the
stored one event by event. It returns `reproduced: true` only on exact
equality, and otherwise the first divergence. Any other `source_kind` is
refused outright, not reported as "not reproduced", because such a bundle
does not record every input of its search.

## What a bundle does not claim

- A `recorded-run` bundle is a record, not a reproduction. Its trace came from
  a live costmap at one instant, and the rosbag is the evidence.
- `git_commit` null means unknown. A bundle written outside a git tree says
  so rather than guessing.

## Versioning

The rule is the same as the trace's:

- an additive field or array bumps MINOR. Readers of the same MAJOR ignore
  manifest FIELDS they do not know; the ARRAY table stays exact, so an
  array added by a later MINOR is refused by an earlier reader (as 1.1's
  recording arrays are by a 1.0 reader) rather than ignored;
- a change of meaning bumps MAJOR, and a reader refuses a MAJOR it does not
  speak.

## Readers

(Added in Phase 1D, 2026-09-30. Additive: nothing above changed.)

Two readers exist. **`coco_lab.bundle.load_bundle`** (Python) is the
reference and runs every check above. **`lab_web/src/bundle/`**
(TypeScript, the browser) runs the **structural** checks only, in Python's
order and with the same bounds. It ports `parse_manifest`, `decode` up to
construction, the provenance, trace, run and recording checks, and the
map's construction checks and hash. It also requires every event and
`start`/`goal` to be in bounds, because its renderer indexes cells with them.

It does **not** run *Trace on the rebuilt graph* beyond those bounds, because that
needs the graph's neighbour and cost functions, which are algorithm code
the browser must not re-implement. The browser therefore draws a bundle
only when `coco_lab` has validated those exact bytes: its `content_hash`
is in the site's catalog (`lab_web/tools/build_catalog.py` runs
`load_bundle`, and `replay` for glass-box bundles, on every bundle it
serves), or the Pyodide worker just wrote it with `write_bundle`. Anything
else is refused as `catalog_mismatch`.

Reproducing `content_hash` in a language other than Python needs care. The
hashed bytes are Python's `json.dumps(sort_keys=True, separators=(',',
':'), allow_nan=False)` with `ensure_ascii`, applied to the PARSED manifest:
- an integer keeps its exact digits (`-0` becomes `0`);
- a float is written as Python's `repr` (`252.0`, `1e-05`, `1e+16`);
- keys sort by Unicode code point, not UTF-16 code unit;
- every character outside ASCII `' '..'~'` is written `\uXXXX` in lowercase
  hex, including DEL, with an astral character written as its surrogate pair.

A JavaScript `JSON.parse` + `JSON.stringify` round trip gets several of
these wrong. The map hash's geo line likewise uses Python `repr` floats.
The TypeScript reader is tested against 1,217 seeded JSON texts, 4,000
float reprs, all six golden fixtures and the three 1C bundles, and a
48-case invalid corpus (`lab_web/test/`, regenerated by
`lab_web/tools/make_expectations.py`).

The TypeScript reader is stricter than Python in a few documented places,
never looser:
- it refuses duplicate JSON keys (Python keeps the last);
- it refuses `NaN`/`Infinity` literals (Python accepts them where it does
  not hash);
- it refuses non-ASCII digits in `version`;
- it refuses a `map.meta` that is not an object.

A server that sends `arrays.bin.gz` with `Content-Encoding: gzip` makes the
browser inflate it first. The TypeScript reader then finds no gzip magic
and refuses rather than guessing. Vite's dev and preview servers do this
(measured), and `lab_web/vite.config.ts` serves `.gz` as plain bytes.
