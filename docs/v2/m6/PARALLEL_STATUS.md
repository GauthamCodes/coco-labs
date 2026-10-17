# M6 foundations — parallel status

The short status for branch `v2/m6-foundations` (worktree
`~/coco_labs_ws/worktrees/m6-foundations`), built in parallel with Codex's M5
under `PARALLEL_PROMPT.md`. `docs/STATUS.md` is **not** edited on this branch;
the entries below are copied into it at merge.

## Current checkpoint and next step

- **Done:** M6F.0 Setup; M6F.1 World Spec v3; M6F.2 Generators.
- **Next:** M6F.3 The COCO Depot level.

## Setup facts (M6F.0, 2026-10-17)

- Branch `v2/m6-foundations` was created from the **local** `v2/m5-focus` at
  `0254dea` ("[M5.7] Support four planners in the shared Compare worker").
  `origin/v2/m5-focus` **does not exist**: Codex has not pushed M5, so the
  prompt's `origin/v2/m5-focus` could not be used (deviation, recorded).
  Picking up newer M5 work means `git merge v2/m5-focus` (the local ref,
  read-only for Codex) or `origin/v2/m5-focus` once it exists.
- Python environment: `~/coco_labs_ws/worktrees/m6-venv` (Python 3.12.3,
  `--system-site-packages --without-pip`, made like `~/coco_labs_ws/test_venv`,
  with that venv's pinned hypothesis 6.98.15, networkx 2.8.8 and
  sortedcontainers 2.4.0 copied in). PYTHONPATH points at this worktree's
  `coco_schemas`, `coco_schemas/coco_schemas/gen`, `coco_lab`, `coco_config`
  and `/opt/ros/jazzy/lib/python3.12/site-packages` (the ament linters).
- Baseline, on the untouched branch at `0254dea`, under `nice -n 19` with
  Codex active (load average 4.2 on 12 cores):
  - `coco_lab`: **824 passed**, 0 failed, 0 skipped (290.7 s)
  - `coco_schemas`: **232 passed**, 0 failed, 0 skipped (6.5 s)
- Machine at setup: AC online, profile `balanced`, NVIDIA driver 580.178.04
  (RTX 4050 Laptop GPU), `gz` CLI present (`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`).
  Codex was running (`codex resume`, PID 18281, plus the Codex desktop app).
  No Gazebo, Isaac or ROS 2 process was running.

## M6F.1 — World Spec v3 (2026-10-17)

- `coco_lab/coco_lab/worldspec_v3.py`: the kit (wall, door, rack with aisles,
  bench, pallet, box, ramp, platform, zone, object, actor), its validator and its
  lowering onto v2's `boxes`/`elevation`; `from_v2`. Docs `docs/v2/m6/WORLD_SPEC_V3.md`,
  decision `docs/v2/adr/0100-world-spec-v3-level-kit.md`. Evidence class MODEL.
- v1/v2 unchanged, proved by `coco_lab/test/test_worldspec_v3.py` against
  `coco_lab/test/fixtures/m6f/prechange_v1v2.json` (made at `0d1f37f`, committed in
  `1e7b7f2` before any v3 code) and the first 10 committed M1 determinism sessions
  (`docs/v2/data/m1/determinism/`, Pyodide hashes): canonical bytes, maps and every
  per-tick hash identical. Every existing golden-trace and hash test passed unedited.
- Tests: `coco_lab` 895 passed / 0 failed / 0 skipped (824 before), nice 19,
  Codex running (`codex resume`), 381.6 s.

## M6F.2 — Generators (2026-10-17)

- `coco_lab/coco_lab/worldgen.py` (stdlib only): the Arena model world at any
  resolution (`arena_world`, `arena_world_json`), the Gazebo SDF world
  (`sdf_world`: template-kept physics/systems/lights; static boxes; STL wedges;
  platforms; dynamic objects; actors as models **with collision bodies**, kinematic,
  plus `actors.json`), standalone spawnable objects (`object_sdf`), the Nav2 map
  (`nav2_map`, `gen_navigation_world.py`'s rules). `tools/m6/gen_level.py` writes all
  of it plus `nav2_params.yaml` derived from `gazebo_models/config/nav2_params.yaml`
  (untouched; 3 keys changed, listed in `params_derivation.json`), runs `gz sdf -k`,
  and records checksums.
- Proving Ground (`docs/v2/m6/PROVING_GROUND.md`): the Nav2 PGM for the v1 and v2
  arena specs is byte-identical to `gazebo_models/maps/coco_navigation.pgm`; the YAML
  differs only in the image name; all 70 boxes and every non-model world element are
  identical to `coco_navigation.world`; the 12 ramp/platform models match the launch
  file's spawns (names differ; rise differs by 3.4e-13 m) and the wedge mesh equals
  `ramp_wedge_18.stl`'s vertices to 6 decimals; `gz sdf -k`: Valid. Checksums:
  `docs/v2/m6/data/coco_arena_v2_outputs.json`. Evidence class MODEL.
- Tests: `coco_lab/test/test_worldgen.py` (19), incl. the SDF round trip, PGM vs the
  model's occupancy, YAML origin/resolution, and `gz sdf -k` (gz present).

## Plan-change entries to copy into docs/STATUS.md at merge

- **2026-10-17 — M6 foundations start in parallel with M5 (Gautham).** By
  issuing `docs/v2/m6/PARALLEL_PROMPT.md`, Gautham authorised one plan change:
  M6's foundations (World Spec v3 and the level kit, the generators, the Depot
  level, the Depot planning benchmark, Grasp Assist on the model side, the
  Fetch Rush and Rush Hour rules engines, the ROS-shaped message model, and
  the Gazebo/Nav2 validation) start now on branch `v2/m6-foundations`,
  without any user interface, in parallel with M5. They merge only after M5
  merges.

## Known merge points with M5

(Files outside this branch's own new files that this branch changes, or that
M5 is likely to change too. Updated at every checkpoint.)

- `coco_lab/coco_lab/worldspec.py` (M6F.1): `SPEC_VERSION_V3`,
  `TERRAIN_SPEC_VERSIONS`, the v3 hand-off at the top of `normalize`, and
  `arena_map`'s terrain check (`in TERRAIN_SPEC_VERSIONS`). M5 (to `0254dea`) has not
  touched this file.
- `coco_lab/coco_lab/arena.py` (M6F.1): the worldspec import line, the terrain check
  in `Arena.__init__` (`in TERRAIN_SPEC_VERSIONS`), and a 4-line refusal of the legacy
  gated grasp on a v3 level. **M5 has edited this file** (12 lines at `0254dea`), so a
  textual conflict is possible; both edits are small and independent.

## Pending heavy items

(Heavy jobs wait for an idle machine: Codex not running, no robot batch, AC.)

- none yet
