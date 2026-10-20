# The generators on the Proving Ground (M6F.2)

The COCO arena (`worlds/coco_arena_v2.yaml`, World Spec v2) run through the M6
generators (`coco_lab/coco_lab/worldgen.py`, `tools/m6/gen_level.py`), and the
outputs compared with what the Stack actually runs: the world file
`gazebo_models/worlds/coco_navigation.world` (made from
`gazebo_models/config/navigation_world.json` by `gen_navigation_world.py`), the ramp
spawns of `gazebo_models/launch/full_world_robo.launch.py` (`traverse:=true`;
converted in `lab_web/public/assets3d/arena.json`), the wedge mesh
`gazebo_models/meshes/ramp_wedge_18.stl`, and the saved map
`gazebo_models/maps/coco_navigation.{pgm,yaml}`.

Evidence class MODEL (a comparison of files; nothing was run in Gazebo here).
Every row is a test in `coco_lab/test/test_worldgen.py`. Output checksums:
`docs/v2/m6/data/coco_arena_v2_outputs.json`.

## Result

| Output | Compared with | Result |
|---|---|---|
| Nav2 map PGM (v1 spec and v2 spec) | `coco_navigation.pgm` | **byte-identical** |
| Nav2 map YAML | `coco_navigation.yaml` | **byte-identical** when the image is named `coco_navigation.pgm`; `gen_level.py` names it after the level (`image: coco_arena_v2.pgm`), the only difference |
| SDF: the 70 boxes | the 70 models of `coco_navigation.world` | **identical**: names, poses, sizes, `static`, collision and visual geometry |
| SDF: everything that is not a model | the same file | **identical**: physics (DART), gravity, the five systems, both lights, the scene, the ground plane (kept from the template; it already covers the bounds) |
| SDF: the 8 wedges and 4 platforms | the launch file's spawns (`arena.json`) | **same geometry, different packaging** (below) |
| Wedge mesh | `ramp_wedge_18.stl` | the same 8 triangles; vertex sets equal to 6 decimals (float32 STL) |
| `gz sdf -k` on the generated world | — | `Valid.` (gz CLI from ROS 2 Jazzy's `gz_tools_vendor`) |
| Nav2 params | `gazebo_models/config/nav2_params.yaml` (never edited) | three keys set by derivation; for this arena two of them come out equal to the original (`amcl.initial_pose` = (0, 0, 0, 0); `global_costmap.resolution` = 0.05) and one differs: `map_server.yaml_filename` `map.yaml` → `coco_arena_v2.yaml` |

## The differences, honestly

1. **Where the ramps live.** The Stack's world file has no ramps: the launch file
   spawns them at run time (`traverse:=true`), one `ramp.sdf` per wedge with a
   `package://gazebo_models/meshes/ramp_wedge_18.stl` URI, plus a platform box per bay.
   The generated world carries the 8 wedges and 4 platforms **in the world file**, as
   static models, each wedge with its own STL at a relative path
   (`meshes/<id>.stl`). A level must be one self-contained world (invariant 12), so
   this is by design; it does mean the generated v2 world plus the launch file's
   `traverse:=true` would spawn the bays **twice**. Launching a generated world uses
   `traverse:=false` (M6F.8).
2. **Names.** Generated models are named by the spec's ids (`bay1_up`,
   `bay1_platform`, `bay1_down` … `bay4_*`); the launch file names them by colour
   (`ramp_up_red`, `ramp_platform_red`, `ramp_down_red` …).
3. **Rise.** The v2 spec stores the ramp rise as `0.649839392466` (12 decimals); the
   launch file computes `2·tan 18° = 0.6498393924658126`. The difference is
   3.4 × 10⁻¹³ m. Foot, yaw, run, width and platform size agree to 1 × 10⁻⁹ m or exactly.
4. **Not generated.** The robot and the four fetch targets: the Stack spawns both
   from the launch file (the targets from the EpisodeSpec); a generated world
   contains neither. M6F.8 spawns COCO into the generated Depot.
5. **The Nav2 map is the 2D scan's view, not the model's drive map.** On a terrain
   world the two differ, by design, inside each elevated solid's footprint: the Nav2
   map holds the scan-height silhouette (occupied rim, unknown inside: Nav2 never
   plans onto a platform), the model's drive map holds the ledges and lets the robot
   drive up the ramp. Everywhere else they are the same map, cell for cell (tested on
   the kit level at 0.1 m and 0.05 m).
