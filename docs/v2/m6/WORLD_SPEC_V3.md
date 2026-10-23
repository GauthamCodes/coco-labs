# World Spec v3 — the level kit

`spec_version: coco.world_spec.v3` (M6F.1). Decision: ADR 0100
(`docs/v2/adr/0100-world-spec-v3-level-kit.md`). Code: `coco_lab/coco_lab/worldspec_v3.py`.
Tests: `coco_lab/test/test_worldspec_v3.py`. v1 and v2 are described in
`docs/v2/WORLD_SPEC.md` and are unchanged.

A v3 level is a list of typed **kit elements** plus an object **catalog**. The reader
validates it and **lowers** it onto v2's primitives (`boxes`, `elevation`), which every
existing consumer already reads. All coordinates are metres in the Gazebo **world**
frame; the Arena drives in the map frame (`world + world_to_map`).

## Top level

| Key | Required | Meaning |
|---|---|---|
| `spec_version` | yes | `coco.world_spec.v3` |
| `id`, `title` | yes | non-empty strings |
| `frame` | yes | `world` |
| `world_to_map` | yes | `[dx, dy]`, map = world + this |
| `bounds` | yes | `{x_min, x_max, y_min, y_max}`; free floor inside, unknown outside |
| `robot` | yes | exactly v1/v2's robot block (wheels, radius, limits, LiDAR) |
| `start` | yes | `{x, y, theta}`, world frame |
| `arena` | yes | `{resolution, margin, dt, unknown: blocked}`; the game uses 0.1 m |
| `kit` | yes | non-empty list of kit elements (below), ids unique |
| `catalog` | no | object types (below) |
| `sources`, `notes` | no | provenance strings |
| `boxes`, `elevation` | derived | written by the reader; if given, must equal what the kit lowers to |

Unknown keys are refused, never ignored (as in v1).

## Kit elements

| `kind` | Fields | Lowers to |
|---|---|---|
| `wall` | `from`, `to` (axis-aligned), `thickness`, `height` | one `wall` box per solid stretch between its doors (`<id>` or `<id>#<n>`) |
| `door` | `wall` (a wall's id), `at` (centre, metres from the wall's `from`), `width` | an opening: nothing |
| `rack` | `center`, `size` `[x, y]`, `height`, `shelves` (ascending heights below the top), `aisle` (clear width), `aisles` (sides of `+x -x +y -y` that must stay clear) | an `obstacle` box |
| `bench` | `center`, `size`, `height` | an `obstacle` box |
| `pallet` | `center`, `size`, `height` (loaded height) | an `obstacle` box |
| `box` | `center`, `size`, `height`, optional `role` (`wall obstacle landmark guard`, default `obstacle`) | a box of that kind (for v2 worlds written as kits) |
| `ramp` | `foot` (midpoint of the foot edge), `yaw` (0 or π), `run`, `rise`, `width`, optional `onto` (a platform's id) | a `wedge` |
| `platform` | `center`, `size` `[x, y]`, `top` | a `platform` (a mezzanine deck) |
| `zone` | `role` (`dock drop pickup start region`), `center`, `size`, optional `label` | nothing (game and UI regions) |
| `object` | `item` (catalog id), `at`, optional `support` (`floor`, or a bench, rack, pallet, box or platform id; default `floor`), `shelf` (rack shelf index), `yaw` | nothing in the map; a spawnable model in Gazebo |
| `actor` | `actor` (`forklift walker`), `path` (≥ 2 points), `mode` (`loop pingpong`), `speed`, `footprint` `[length, width]`, `height`, optional `phase` (metres along the path at t = 0) | nothing in the static map; a moving model **with a collision body** in Gazebo |

Every solid stands on the floor: its box's `z` is `height / 2`.

## Catalog items

`{id, label, shape: cylinder | box, magnetic, colour, mass}` (mass in kg, for Gazebo's dynamics) plus `diameter` and `height`
(cylinder) or `size: [x, y, z]` (box), optional `notes`. Whether an item can be picked
is decided by Grasp Assist (M6F.5) from the robot's own constants, never written in the
catalog.

## Validation (each refusal names its reason)

| Rule | Why |
|---|---|
| A solid's `height` must exceed the LiDAR beam height (`ground_clearance + lidar.mount[2]`, 0.2135 m for COCO) | the Stack's 2D scan would never see it; the model's map would hold it |
| Door and rack-aisle widths ≥ `2 × (robot.radius + arena.resolution)` (0.64 m at 0.1 m) | the plan map inflates by the radius and the rasteriser can grow a solid by one cell |
| A door lies within its wall; doors on one wall do not overlap | |
| No solid or elevated solid stands in a rack's declared aisle strip | the aisle is the rack's whole point |
| A ramp's yaw is 0 or π | `coco_lab.terrain` follows axis-aligned wedges only |
| A ramp `onto` a platform rises to its top and its crest meets the platform's edge | no step at the crest |
| Every solid lies within the bounds plus the margin | |
| An object's item is in the catalog; on the floor it is inside the bounds and in no solid; on a support it is within that support's footprint; on a rack it names a shelf | |
| An actor's path is inside the bounds and its footprint, swept every 0.05 m along the lane (closing the loop for `loop`), touches no solid | otherwise it would drive through a wall in the model and collide in Gazebo |

## Reading a canonical v3 spec

`worldspec_v3.objects(spec)` (resolved catalog fields and support height `z`),
`elements(spec, kind)`, `zones(spec, role)`, `actor_pose(actor, t)` and
`actor_corners(actor, t)` (kinematic: the actor moves at `speed` from `phase` metres
in; `loop` closes back to the first point, `pingpong` walks back), `passable_width(spec)`,
`static_rects(spec)`, and `from_v2(spec)` (any v2 world written as kit elements).

## Compatibility

- v1 and v2 specs are handed to the v1/v2 reader untouched; their canonical bytes,
  maps and per-tick hashes are pinned in `coco_lab/test/fixtures/m6f/prechange_v1v2.json`
  (made before v3 existed) and replayed in the tests.
- The Arena runs a v3 level with terrain (v3 is in `TERRAIN_SPEC_VERSIONS`). Its legacy
  gated grasp refuses on v3; Grasp Assist (M6F.5) is the v3 pick.
- Hash v2 (ADR 0008) commits to the canonical spec, so v3 levels get their own hashes;
  hash v1 of `from_v2(v2)` equals v2's tick for tick.
