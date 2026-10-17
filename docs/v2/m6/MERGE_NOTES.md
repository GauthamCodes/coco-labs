# M6 foundations — merge notes

Branch `v2/m6-foundations` (worktree `~/coco_labs_ws/worktrees/m6-foundations`), built in
parallel with M5 under `docs/v2/m6/PARALLEL_PROMPT.md`. It branched from the **local**
`v2/m5-focus` at `0254dea` ([M5.7]), because `origin/v2/m5-focus` did not exist. Merge
**after M5 merges**, into `main`; never into `v2/m5-focus`.

## Files changed that this branch did not create

Only registration lines:

| File | Change | M5 touched it? |
|---|---|---|
| `coco_lab/coco_lab/worldspec.py` | `SPEC_VERSION_V3`, `TERRAIN_SPEC_VERSIONS`; `normalize` hands a v3 spec to `worldspec_v3` before any v1/v2 code; `arena_map`'s terrain check `in TERRAIN_SPEC_VERSIONS` | no (to `0254dea`) |
| `coco_lab/coco_lab/arena.py` | the worldspec import line; `Arena.__init__`'s terrain check `in TERRAIN_SPEC_VERSIONS`; the legacy gated grasp refuses on a v3 level (4 lines) | **yes** (12 lines) |
| `coco_schemas/coco_schemas/channels.py` | three `manip.grasp` channels; `M6_FAMILIES`; `FAMILIES` gains it | **yes** (`costmap.layers`, `M5_FAMILIES`) |

Everything else is new: `coco_lab/coco_lab/{worldspec_v3,worldgen,grasp_assist,games,ros_shapes}.py`;
`coco_lab/test/{test_worldspec_v3,test_worldgen,test_depot,test_grasp_assist,test_games,test_ros_shapes}.py`
and `coco_lab/test/fixtures/m6f/`; `coco_lab_ros/test/test_m6f_{constants,manip_schema,ros_shapes}.py`;
`coco_schemas/proto/coco/manip/v1/grasp.proto` and its generated Python
(`coco_schemas/coco_schemas/gen/coco/manip/`) and TypeScript
(`lab_web/src/schemas/gen/coco/manip/v1/grasp_pb.ts`); `worlds/coco_depot_v1.yaml`,
`worlds/tools/make_coco_depot_v1.py`; `tools/m6/`; `docs/v2/m6/`; `docs/v2/adr/0100-*`.

## Expected conflicts with M5, and how to resolve them

- `coco_lab/coco_lab/arena.py`: textual only if M5 edits the same lines (the import of
  `worldspec` names, `self.terrain = ...`, the `grasp` input branch). Keep both sides.
- `coco_schemas/coco_schemas/channels.py`: the `FAMILIES = ...` line. Resolve to
  `M1_FAMILIES + M2_FAMILIES + M5_FAMILIES + M6_FAMILIES`, keeping every channel.
- `lab_web/src/schemas/gen/`: no existing generated index or barrel changed;
  `python3 coco_schemas/scripts/generate.py --lang ts --check` must pass after the merge.
- Deliberately **not** changed: `coco_lab/coco_lab/columns.py` (its `TABLES` are enumerated
  by `coco_schemas/test/test_columns_m2.py` and the committed vectors). Grasp Assist keeps
  its own tables (`grasp_assist.TABLES`), held to the proto by
  `coco_lab_ros/test/test_m6f_manip_schema.py`. After the merge, moving them into
  `columns.TABLES` (and regenerating the M2/M5 vectors) is an option for the M6 UI phase.
- `docs/STATUS.md`: copy the plan-change entry from `PARALLEL_STATUS.md`.
  `docs/RESULTS.md`: append `docs/v2/m6/RESULTS_M6_FOUNDATIONS.md`.
- Hash v2 (ADR 0008) commits to the canonical spec: no v1 or v2 link changes (tested), and
  v3 levels have their own hashes.

## What the M6 UI phase still needs

- **Depot rendering and streaming:** glTF/scene build for the Depot from
  `worldgen.arena_world` (the 3D asset pipeline, ADR 0006), zone streaming, the first-scene
  budget (5 MB compressed), 60 fps on the RTX 4050 and the integrated GPU.
- **Grasp Assist visuals:** the G button, the outlines, the reach envelope on the floor
  (from `coco.manip.grasp.envelope.v1`), the ranking on hover, the ghost arm, the refusal
  reasons, the "MODEL · MoveIt-style" badge; the TS lens for `manip.grasp`.
- **The game HUDs:** Fetch Rush's orders, timer, deliveries and path efficiency;
  Rush Hour's clearance, contacts, jerk under the fragile-cargo rule (labelled a rule) and
  the assist in use; stars from `games.stars`.
- **The ROS graph panel:** drawn from `docs/v2/m6/data/ros_graph.json` /
  `ros_shapes.ros_graph()`, with the shapes of `ros_shapes`.
- **coco verify and link wiring in the browser** for game records (`games.verify` is the
  Python side; the browser and `coco verify` CLI must replay the same record, in all four
  engines).
- **The actors in the browser model** (`actors` subsystem) and in Gazebo (a driver moving
  the collision-bodied models from `actors.json`).
- **MoveIt ghosts:** recorded MoveIt picks in the Depot (Stack), converted to ghosts.
- **Pending heavy items from this branch:** M6F.4 (Depot planning benchmark) and M6F.8
  (Gazebo + Nav2 validation; plan in `docs/v2/m6/M6F8_PLAN.md`).
