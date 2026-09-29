# Trace schema v1

A **trace** records what a `coco_lab` search did, event by event. The
browser's trace player renders it, and a ROS node stores one beside the path
it planned. The web UI never re-runs the algorithm (platform rule 8); it
reads the trace.

- Schema name: `coco_lab.trace`
- Current version `"1.0"`
- Reference implementation: `coco_lab/coco_lab/trace.py`
- Pinned by: `coco_lab/test/test_trace.py::test_the_doc_matches_the_implementation`.
  If this document and the code disagree, that test fails.

## Shape

A trace is one JSON object with three members:

```json
{
  "header":  { "...": "what was searched, and how" },
  "events":  { "kind": [0, 1, 0, "..."], "row": ["..."], "...": ["..."] },
  "summary": { "status": "found", "expansions": 8, "...": "..." }
}
```

`events` is **columnar**: each column is one array, all columns have the same
length, and row `i` across the columns is event `i`. Events are listed in the
order they happened. Canonical JSON (`Trace.to_json`) sorts keys, has no
whitespace, and never contains `NaN` or `Infinity`. A missing value is `null`.

## Header

| field | type | meaning |
|---|---|---|
| `schema` | string | always `coco_lab.trace` |
| `version` | string | `"MAJOR.MINOR"`, currently `"1.0"` |
| `algorithm` | string | `bfs`, `dijkstra`, `astar`, `greedy` or `weighted_astar` |
| `heuristic` | string | `zero`, `manhattan`, `euclidean` or `octile` |
| `weight` | number or null | `w` for `weighted_astar`; `null` for the other four |
| `tie_break` | string | `low_h` (default) or `fifo`; see `coco_lab/search.py` |
| `start`, `goal` | `[row, col, sub]` | where the start and goal are drawn |
| `graph` | object | the graph's parameters. For a grid: `kind: "grid"`, `width`, `height`, `connectivity`, `diagonal_cost`, `corner_cutting`, `cost_layer`, `cost_weight`, `cost_scale`. Any other graph gives at least `kind`. |

## Event columns

| column | type | meaning |
|---|---|---|
| `kind` | int | event code (table below) |
| `row` | int | the state's row |
| `col` | int | the state's column |
| `sub` | int | the sub-state within the cell: `0` on a plain grid, a heading index in a *(cell, heading)* space |
| `g` | float | cost from the start to this state, along its current parent chain |
| `h` | float | the chosen heuristic's value at this state. It is recorded even for BFS and Dijkstra, which ignore it, so a learner can still see it |
| `f` | float | the queue priority actually used: `g` (Dijkstra), `g + h` (A\*), `h` (greedy), `g + w*h` (weighted A\*), or the depth in moves (BFS) |
| `parent_row` | int | the parent's row, or `-1` if there is no parent (the start) |
| `parent_col` | int | the parent's column, or `-1` |
| `parent_sub` | int | the parent's sub-state, or `-1` |

`(row, col, sub)` is the graph's `locate(state)`. A state is identified by
that triple, so two events with the same triple refer to the same state.

## Event kinds

| code | kind | when |
|---|---|---|
| 0 | `push` | a state enters the open list for the first time |
| 1 | `expand` | a state is popped and closed. The goal's `expand` is the last one, because the goal test runs on expansion |
| 2 | `relax` | a cheaper path reaches a state that is still open. `g` and the parent are the new ones, and the state is re-queued at the new `f`. BFS never relaxes |
| 3 | `path` | one event per state on the final path, from start to goal, emitted after the search ends. `f` equals `g` here |

Invariants, all checked by `Trace.validate()`:

- a state is `expand`ed at most once (closed states are never reopened), and
  `push`ed at most once;
- `summary.expansions`, `summary.pushes` and `summary.relaxes` equal the counts
  of those event kinds;
- a found trace has exactly `path_steps + 1` `path` events;
- a `no_path` trace has none.

## Summary

| field | type | meaning |
|---|---|---|
| `status` | string | `found` or `no_path` |
| `expansions` | int | number of `expand` events |
| `pushes` | int | number of `push` events |
| `relaxes` | int | number of `relax` events |
| `path_cost` | float or null | sum of edge costs along the path, under the graph's declared cost function |
| `path_length` | float or null | geometric length of the path in cell units: the sum of `hypot(drow, dcol)` over consecutive path states. A turn in place has length 0. It is independent of the cost layer and of `diagonal_cost` |
| `path_steps` | int or null | number of edges on the path |

The three `path_*` fields are `null` exactly when `status` is `no_path`.

## Versioning

This is the rule `coco.v1` already uses:

- **Additive changes bump MINOR:** a new column, event kind, header field or
  summary field. A reader of the same MAJOR must ignore what it does not know.
- **Changes of meaning bump MAJOR,** and a reader refuses a MAJOR it does not
  speak. `Trace.from_dict` does exactly that.

Bundles (Phase 1B, `docs/labs/BUNDLE_FORMAT.md`) will carry traces as
little-endian typed arrays under the same column names. This JSON form is the
reference that the bundle encoding round-trips against.
