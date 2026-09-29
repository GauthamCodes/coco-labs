# Map schema v1

A **map** is what a `coco_lab` run searches: dimensions, one occupancy value
per cell, an optional cost layer, and optional placement in a metric frame.
Traces point into it, bundles embed it, and the browser draws it.

- Schema name: `coco_lab.map`
- Current version `"1.0"`
- Reference implementation: `coco_lab/coco_lab/maps.py`
- Pinned by: `coco_lab/test/test_maps.py::test_the_doc_matches_the_implementation`.
  If this document and the code disagree, that test fails.

## A map is data, not a graph

The move model is **not** part of the map. How a robot may move over the map
is a **run input**, given when the map is turned into a searchable graph
(`LabMap.to_grid`) and recorded in the trace header and the bundle:

- 4 or 8 neighbours;
- the diagonal cost;
- the corner rule;
- `cost_weight` and `cost_scale`;
- whether unknown cells are passable (`unknown`: `blocked`, the default, or
  `free`).

A comparison can therefore hold the map fixed while it changes only the
model. This is the rule the pasted Phase 1B brief asks for, and the reason
a fixture's `run` block is a separate field.

## Coordinates

- A cell is `(row, col)`. **Row 0 is the TOP row.** Storage is row-major.
- This is the image convention of a PGM file and of Nav2's map_server, and
  the one `coco_lab.grid.Grid` already uses.
- With placement, `resolution` is metres per cell and `origin` is the frame
  coordinates of the map's **bottom-left corner**. The yaw is always 0. The
  centre of cell `(row, col)` is:

```
x = origin_x + (col + 0.5) * resolution
y = origin_y + (height - 1 - row + 0.5) * resolution
```

  So `y` grows upward while `row` grows downward.
- `LabMap.cell_at(x, y)` is the inverse, and returns `None` outside the map.

## JSON form

One object:

| field | type | meaning |
|---|---|---|
| `schema` | string | always `coco_lab.map` |
| `version` | string | `"MAJOR.MINOR"`, currently `"1.0"` |
| `id` | string | a name. It is not identity: two maps may share an id, and one map may be renamed |
| `width`, `height` | int | cells, each 1..16384, at most 16,000,000 cells in all |
| `rows` | list of strings | `height` strings of `width` characters, top row first, one character per cell (table below) |
| `cost` | list of numbers or null | the cost layer, row-major, finite and >= 0. How it prices a move is the grid's declared cost function (`coco_lab/grid.py`), set by run inputs |
| `geo` | object or null | `{resolution, origin: [x, y], frame}`: placement, or null for an abstract teaching grid |
| `meta` | object | free-form description. It never changes a search or a drawing, and it is not hashed |
| `content_hash` | string | `sha256:<hex>`, defined below. It is optional on input; if present it must match |

Cell characters:

| char | value | meaning |
|---|---|---|
| `.` | 0 | free |
| `#` | 1 | occupied |
| `?` | 2 | unknown |

Canonical JSON (`LabMap.to_json`) sorts keys, has no whitespace, and never
contains `NaN` or `Infinity`.

## Identity: `content_hash`

`content_hash` is the SHA-256 of these bytes, in order:

1. the ASCII line `coco_lab.map/1 <width> <height>` and a newline;
2. the occupancy, one byte per cell (0, 1 or 2), row-major;
3. either the line `cost` followed by the cost layer as little-endian
   IEEE-754 float64, or the line `nocost`;
4. either the line `geo <resolution> <ox> <oy> <frame>`, each float written
   with Python's `repr` (the shortest string that round-trips), or the line
   `nogeo`.

It covers everything that changes what the map *is*, and excludes `id` and
`meta`. A bundle records it. A replay that finds a different hash is showing
a different map, and it says so instead of drawing it.

## Validation

`LabMap.from_dict` refuses:

- any other `schema`;
- a MAJOR version other than 1;
- wrong dimensions or out-of-range dimensions;
- rows of the wrong count or length, or containing any character outside
  `.#?`;
- a non-finite or negative cost;
- `resolution` without `origin`, or the reverse;
- a `frame` without placement;
- a non-object `meta`;
- a `content_hash` that does not match.

It never repairs. A MINOR version it does not know, and fields it does not
know, are accepted and ignored.

## Conversions

### Nav2 saved map (`from_nav2`, `load_nav2`, `to_nav2`)

This converts a map_server **saved map** (pgm + yaml), not a costmap.

- **yaml:** only the map_server keys are accepted: `image`, `mode`,
  `resolution`, `origin`, `negate`, `occupied_thresh`, `free_thresh`.
  - It must be flat `key: value` lines. Anything else is refused. This is
    not a YAML parser, and it does not guess.
  - `mode` must be trinary.
  - The origin's yaw must be 0. A rotated map is refused.
- **pgm:** P5 or P2, with `maxval` <= 255, and at most 64 MiB.
- **Pixel rule** (map_server's trinary rule):
  - `occ = (255 - p)/255`, or `p/255` when `negate` is set;
  - `occ > occupied_thresh` is occupied;
  - `occ < free_thresh` is free;
  - anything else is unknown.
- `to_nav2` writes 254/0/205 (map_saver's values). It refuses a map with a
  cost layer, which a saved map cannot hold.

### Downsampling (`downsample(factor)`)

- Each `factor x factor` block becomes one cell. It is occupied if any cell
  in the block is occupied, else unknown if any is unknown, else free.
- This is conservative: a coarse free cell is free at full resolution.
- The cost is the block's maximum.
- Blocks are anchored at the bottom-left, so `origin` does not move.

### Rasterising (`Raster`)

`Raster` paints axis-aligned rectangles, in order, under one of two declared
rules:

- `centre`: a cell is covered if its centre lies in the closed rectangle.
  This is the ground-truth rule used for evaluation.
- `overlap`: a cell is covered if its square overlaps the rectangle with
  positive area. This is the rule `gazebo_models/scripts/gen_navigation_world.py`
  uses for boxes, and a test pins the equivalence.

## Teaching fixtures (`coco_lab/teaching.py`)

There are nine 20 x 20 fixtures. `turn_trap` is searched on the heading
space; the other eight on a grid. Each carries a `purpose`, a `claim` and a
`run` move model. `test/test_teaching.py` checks every claim against the
algorithms and a networkx oracle, and `test/test_isro.py` checks
`turn_trap`'s:

| fixture | claim |
|---|---|
| `open` | every optimal algorithm agrees; A* expands under a fifth of Dijkstra's states |
| `corridor` | all five algorithms return the same path |
| `wall_one_gap` | A* is optimal, but expands over half as many states as Dijkstra |
| `two_routes` | the optimum takes the cheaper route below the block |
| `greedy_trap` | greedy is strictly costlier than the optimum; A* is optimal |
| `diagonal_leak` | the corner rule decides whether a diagonal wall is a wall; 4-connectivity costs more |
| `no_path` | all five report `no_path` |
| `cost_field` | with the cost layer the optimum detours through a cheap gap |
| `turn_trap` | with a turn penalty, the ISRO simulator's cell-only search is 0.1 costlier than the (cell, heading) optimum (`test_isro.py`) |

## What this is not

A teaching grid is not a ROS `OccupancyGrid` and not a Nav2 costmap. Nav2's
costmaps inflate obstacles, and SmacPlanner2D prices cells its own way.
Phase 1C compares the two; nothing here claims they are the same.

## Versioning

The rule is the same as the trace's:

- an additive field bumps MINOR, and readers of the same MAJOR ignore what
  they do not know;
- a change of meaning bumps MAJOR, and a reader refuses a MAJOR it does not
  speak.
