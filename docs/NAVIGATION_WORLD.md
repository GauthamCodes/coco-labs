# Larger navigation world

The default `full_world_robo.launch.py` world is `coco_navigation.world`.
Its wall centre lines bound x = -8..16 m and y = -9..9 m: 24 × 18 m.
The frozen `coco_world.world` is retained unchanged. The new world is a
static environment; there is no moving-obstacle implementation.

## Run

Source the workspace overlay built from this checkout in each terminal.
Then use the existing workflow:

```bash
ros2 launch gazebo_models full_world_robo.launch.py traverse:=true gui:=true
ros2 launch coco_mission mission.launch.py rviz:=true target_colour:=red
ros2 service call /mission/start std_srvs/srv/Trigger "{}"
```

Restart the simulator before every mission, including a change of colour.
The existing DetachableJoint limitation still applies. Other colours are
`green`, `blue`, and `yellow`.

## Geometry and map

`gazebo_models/config/navigation_world.json` defines the static boxes and
bay footprints. Regenerate both artifacts from the repository after sourcing
the built environment:

```bash
python3 gazebo_models/scripts/gen_navigation_world.py
```

The generator preserves the frozen world's simulator systems and lighting.
It writes `worlds/coco_navigation.world` and `maps/coco_navigation.{pgm,yaml}`.
The map is 500 × 380 cells at 0.05 m/cell, covering 25 × 19 m including the
border, with origin (-6.5, -9.5). Map X is world X + 2 m, preserving the
mission's existing coordinate convention and AMCL initial pose (0, 0, 0).

Ramps are represented by their intersection with the flat-ground LiDAR
plane. Its height comes from `coco_config`, as does the nominal ramp angle.
Side guards prevent a planned shortcut across the low ends of the wedges.
This map is for the nominal 18-degree mission configuration. A different
`ramp_angle` needs a corresponding map; curriculum experiments are separate.

The layout includes long approach and east corridors, 1.4 m clear passages
between guarded bays, offset walls, T and cross junctions, west rooms,
an eastern dead-end room, an open central area, and an eastern obstacle
cluster. Home, all pre-ramp poses, all descent exits, and representative room
points are connected with 0.30 m centre clearance in the static-map test.
This is an offline geometric check, not a substitute for mission testing.

## Target bays

The shared target table remains in `coco_config/coco_config/robot.py`.
Each rod has its own identical +X-facing ramp/platform/down-ramp assembly.

| Colour | World X | World Y |
|---|---:|---:|
| red | 4.05 | -6.0 |
| green | 4.05 | -2.0 |
| blue | 4.05 | 2.0 |
| yellow | 4.05 | 6.0 |

Each bay retains foot X=1.0, summit X=3.0, platform length 1.5 m,
width 2.5 m, and far foot X=6.5. Rod dimensions, colours, mass, inertia
calculation, model IDs and magnet bindings are unchanged. The mission's
pre-ramp X=0.5, climb goal and descent goal remain unchanged. Colour-to-lane
lookup supplies the new Y coordinates; no executive state transitions,
perception logic, grasp implementation or command routing was changed.

## RViz

`mission.launch.py` already conditionally starts RViz for `rviz:=true`.
The default mission view now uses WORLD, NAVIGATION, ROBOT, SENSORS and
MISSION groups. Both costmaps, TF, the robot, scan and footprint are enabled.
The camera is centred on the larger map. Paths retain one live message each.

| Display | Topic | Message |
|---|---|---|
| Map | `/map` | `nav_msgs/msg/OccupancyGrid` |
| Global Costmap | `/global_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` |
| Local Costmap | `/local_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` |
| Global Planner Path | `/plan` | `nav_msgs/msg/Path` |
| Local Controller Trajectory (DWB) | `/local_plan` | `nav_msgs/msg/Path` |
| Robot Footprint | `/local_costmap/published_footprint` | `geometry_msgs/msg/PolygonStamped` |
| LaserScan | `/scan` | `sensor_msgs/msg/LaserScan` |

The global planner remains `nav2_smac_planner::SmacPlanner2D` (`GridBased`),
with NavFn still registered for existing comparison tools. The controller
remains `dwb_core::DWBLocalPlanner`. No path is synthesized for RViz.
`navigation_world_observe.py` can match message publisher GIDs to actual
publishing nodes, rather than just listing advertised publishers.

## Future dynamic obstacles

`config/dynamic_obstacles.example.yaml` is a disabled, unconsumed example
with ID, dimensions, initial pose, velocity, enable flags and motion pattern.
It documents straight, waypoint, oscillating, crossing and circular patterns.
There is no node, plugin or runtime behavior behind that proposal yet.

## Verification

`docs/data/navigation_world_run.sh OUTPUT_DIR COLOUR` reuses the existing
fresh-simulator mission runner, arrival gates, command-chain checks and
recorders. It enables RViz and verifies changed-package source paths before
launching. `COCO_TEST_GUI=false` selects server-only Gazebo for repeated runs.
The runner's bring-up checks passing is **not** a successful mission: inspect
`final_state.txt`, transition history, grasp outcomes and ground-truth traces.

A read-only observer can be started before calling `/mission/start`:

```bash
python3 docs/data/navigation_world_observe.py --out /tmp/navigation-evidence.json
```

On this machine validation uses a fresh `coco_navigation_overlay` over the
existing dependency build. Reusing the old build directory initially retained
Gazebo launch-file symlinks to another worktree despite a successful build.
That attempt was discarded. Verify resolved source paths when using overlays.
