# ADR 0006 — The 3D asset pipeline: standard-library Python, then meshoptimizer

- **Status:** accepted, 2026-10-11 (M4.2).
- **Evidence class:** MODEL (the tooling; the browser). The sources are the
  frozen Gazebo world and robot description (STACK's own files).
- **Evidence:** `lab_web/public/assets3d/manifest.json` and
  [`ASSETS.md`](../ASSETS.md); `lab_web/test/assets3d.test.ts` (regenerates
  every file and compares bytes); `lab_web/tools/test_assets3d.py`.

## Context

README §5.4 and §7 M4.2: COCO's Gazebo arena (SDF) and robot (URDF, the
Fusion 360 CAD's STL meshes) converted offline to glTF; meshopt geometry and
KTX2 textures; levels of detail (about 20k triangles near the camera, well
under 5k for phones); a manifest with every file's source, licence, checksum
and size; size budgets in CI (first scene 5 MB or less, robot 1.5 MB or
less). The prompt: "Prefer tools that run headless in CI and are pinned."

Constraints found in M4.1:
- CI's tool job runs a plain venv with **no numpy** and **no ROS**, and fails
  on any skipped test; the robot's xacro needs ROS to expand.
- M4.1's rough conversion (numpy, vertex clustering) starved small parts and
  could not run in CI.

## Options

| | Pipeline | For | Against |
|---|---|---|---|
| **A. stdlib Python + `meshoptimizer`** (chosen) | Python (standard library) parses the SDF and the URDF, reads and welds the STLs, writes full-resolution source GLBs; a Node script simplifies with meshoptimizer's simplifier, computes crease-aware normals, and writes `EXT_meshopt_compression` itself | One pinned dependency (`meshoptimizer` 1.2.0, WebAssembly, no dependencies of its own); runs headless in CI; byte-identical output (checked); the same library three.js's decoder comes from | We write the GLB and the extension's layout ourselves (a small, specified format) |
| B. `@gltf-transform` 4.5.0 (CLI or library) + meshoptimizer | The standard glTF toolkit | Mature; many transforms | Installing it pulled **`sharp` and 30 platform builds of libvips** (via `ndarray-pixels`, for textures we do not have) into `lab_web`'s dev dependencies — measured on install, then removed |
| C. Blender, headless | Full DCC | Can do anything | Large, hard to pin in CI, nondeterministic exports |
| D. Keep M4.1's clustering | No new dependency | — | numpy; poor quality (the chassis fell to 56 triangles); no compression |

## Decision

**A.**

1. `convert_world.py` — `gazebo_models/worlds/coco_navigation.world`
   (checked to be the world the recordings ran, sha256 `cbe9415a…`) plus
   the `traverse:=true` bays from `coco_config.robot` → `arena_src.glb`
   (flat normals) and `arena.json` (every footprint: the reference for the
   World Spec agreement check, ADR 0007).
2. `convert_robot.py` — the committed, expanded
   `lab_web/tools/assets/coco_robo2.urdf` (made by `--from-xacro` where ROS
   is installed; its first line records the xacro's sha256, and a test fails
   if the xacro changes) and the STLs → `robot_src.glb` at full resolution,
   the joint hierarchy kept (`joint:` / `q:` / `link:` nodes; axes and limits
   in `extras`).
3. `compress.mjs` — per level of detail, the triangle budget is shared by
   water-filling (small meshes keep every triangle, the large share the
   rest), each mesh simplified by meshoptimizer; normals smooth with a 40°
   crease; vertices reordered; every buffer view meshopt-encoded (codec
   version 0) with a data-less fallback buffer, the extension required.
4. `build_assets.mjs` — runs 1–3, writes `public/assets3d/manifest.json`
   and `docs/v2/ASSETS.md`; `--check` regenerates in a temporary directory
   and fails unless every committed file is byte-identical and within budget.

**Textures:** none. Every material is a constant colour from the SDF and
the URDF, so KTX2 has nothing to encode; README §5.3's small environment
map can be generated in the page (three.js's `RoomEnvironment`), which is
not a file. If a texture is ever added, KTX2 (`toktx`, pinned) joins step 3
and this ADR is amended.

**Licences:** every asset is made from COCO's own files: Gautham's CAD and
Gazebo world, Apache-2.0 like the repository. There are no third-party
assets (README §3 integrity rule 8).

## Measured (2026-10-11, M4.2)

| Asset | Source | Served (meshopt) | Triangles |
|---|---|---|---|
| `arena.glb` | 66,008 B | **27,640 B** | 964 |
| `robot_high.glb` | 6,394,360 B (all levels' source) | **540,152 B** | 20,000 (wheels 87,790 → 3,582 each; every other mesh whole) |
| `robot_low.glb` | — | **143,892 B** | 4,412 (budget 4,500) |

First scene: **567,792 B** on a desktop (arena + high robot), **171,532 B**
on a phone (arena + low robot), against 5 MB; the robot 540,152 B against
1.5 MB. M4.1's uncompressed first scene was 917,188 B. Two runs gave
byte-identical files; the whole pipeline runs in under a second.

## Consequences

- One small GLB writer in Python and one encoder in Node to maintain; both
  are tested by regenerating the committed files byte for byte.
- `meshoptimizer` is pinned in `lab_web/package.json`; a version change
  changes the bytes, and the regeneration test says so.
