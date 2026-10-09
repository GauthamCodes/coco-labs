# World Spec v1 (`coco.world_spec.v1`)

One versioned YAML describes a world and its robot (README §5.1); every
simulator tier is generated from it. M1.2 builds the spec, its validator
and the **Arena** generator. Gazebo SDF generation is designed for (every
3D quantity it needs is carried and checked) but **not built** in M1.

| Piece | Where |
|---|---|
| The COCO arena | [`worlds/coco_arena_v1.yaml`](../../worlds/coco_arena_v1.yaml) |
| How it is made | [`worlds/tools/make_coco_arena_v1.py`](../../worlds/tools/make_coco_arena_v1.py) (`--check` in CI) |
| Validator, canonical form, Arena generator | [`coco_lab/coco_lab/worldspec.py`](../../coco_lab/coco_lab/worldspec.py) (standard library only; runs in Pyodide) |
| Tests | `coco_lab/test/test_worldspec.py` |

## Where the numbers come from

`worlds/coco_arena_v1.yaml` is **generated**, never hand-edited; each
number is read from the file that defines it for the full ROS 2 stack
(simulated), and a test fails if the YAML drifts from them:

| Spec field | Source |
|---|---|
| `bounds`, `boxes` (70: walls, obstacles, landmarks, bay guards), `world_to_map`, `arena.resolution`, `ramps` (feet, run, platform, width, centres) | `gazebo_models/config/navigation_world.json` |
| `ramps.angle_deg`, `robot.wheel_radius`, `wheel_separation`, `ground_clearance`, `lidar.mount`, `limits.linear_accel` / `angular_accel`, `start` | `coco_config/coco_config/robot.py` |
| `robot.lidar` beams and range, `robot.radius` | `coco_lab/coco_lab/sketch.py` (`COCO_LIDAR`, `ROBOT_RADIUS`; pinned to the xacro by `coco_lab_ros/test/test_sketch_constants.py`) |
| `limits.teleop_linear` / `teleop_angular` | `coco_web/coco_web/safety.py` (what a browser may ask for) |
| `limits.auto_linear` / `auto_angular`, `arena.dt` | `gazebo_models/config/nav2_params.yaml` (`FollowPath` limits; `controller_frequency` 10 Hz → `dt` 0.1 s) |

## Fields

All lengths in metres, angles in radians unless named `_deg`.

```yaml
spec_version: coco.world_spec.v1   # a reader refuses any other
id, title                           # names
sources: {name: path, ...}          # optional provenance (strings)
notes: text                         # optional
frame: world                        # v1 geometry is in the Gazebo world frame
world_to_map: [dx, dy]              # map = world + (dx, dy)
bounds: {x_min, x_max, y_min, y_max}
boxes:                              # static, axis-aligned
  - {id, kind: wall|obstacle|landmark|guard, center: [x, y], size: [sx, sy],
     z: centre height, height: sz}  # z, height: for the SDF
ramps: {angle_deg, foot_x, run, platform_length, width, centres_y: [...]}
robot:
  wheel_radius, wheel_separation, radius   # radius: the collision circle
  ground_clearance                          # base_link above the ground
  limits: {teleop_linear, teleop_angular, auto_linear, auto_angular,
           linear_accel, angular_accel}
  lidar: {mount: [x, y, z above base_link], samples, angle_min, angle_max,
          range_min, range_max}
start: {x, y, theta}                # world frame
arena: {resolution, margin, dt, unknown: blocked}
```

**Strict.** An unknown key, a missing key, a wrong type (a `bool` is not a
number), a duplicate box id, an empty or inverted bound, a non-positive
size, a ramp at 90° or more — each is **refused** with the path of the
offending field. v1 never ignores what it does not define.

## Canonical form and identity

`normalize(spec)` validates and returns the canonical form: numbers are
floats except declared integers (`lidar.samples`), keys are the fixed v1
set, lists keep their order. `canonical_bytes(spec)` is Python's canonical
JSON of that form (sorted keys, no spaces, ASCII). Writing `4` or `4.0` in
the YAML gives the same bytes; moving a box by 1 mm does not. These are the
bytes `run_id` hashes (`coco_schemas.runid`, [SCHEMAS.md](SCHEMAS.md));
the Manifest's `spec_format` is `coco.world_spec.v1+json`.

## The Arena world

`arena_map(spec)` rasterises the world into the `LabMap` the Arena model
drives in, **in the map frame**, by the rules
`gazebo_models/scripts/gen_navigation_world.py` uses for the Stack's saved
map:

1. a cell inside `bounds` is free; the `margin` around them is unknown;
2. a ramp is its footprint at the LiDAR **scan height**
   (`ground_clearance + lidar.mount.z` = 0.2135 m for COCO), inset from
   each foot by `scan_height / tan(angle)`: occupied on its one-cell rim,
   unknown inside — a flat beam sees the silhouette, not the interior;
3. every cell a box's rectangle touches (grown by half a cell) is occupied.

Unknown is non-traversable (`arena.unknown: blocked`, as Nav2 runs with
`allow_unknown: false`).

**Tested:** the Arena world generated from `coco_arena_v1.yaml` equals
`gazebo_models/maps/coco_navigation.pgm` **cell for cell** (500 × 380
cells), with the same resolution and origin; and every box equals the
Gazebo world's model of the same name, pose and size included
(`gazebo_models/worlds/coco_navigation.world`).

## Gazebo SDF: designed for, not built

What an SDF generator needs and the spec already carries: each box's
`z` and `height` (its 3D centre and size, tested equal to the SDF), the ramp
grade `angle_deg` with the bay dimensions (the Stack's ramps are meshes,
`meshes/ramp_wedge_18.stl`), and `start` (the spawn pose). What it does not
carry yet, recorded so nothing is assumed: materials, lights, physics and
plugin settings (the generator keeps `coco_world.world`'s), and the target
cylinders (episode-specific; `coco_sim`'s EpisodeSpec owns them). Building
the generator, and switching the Stack to it, is outside M1 (README §6).
