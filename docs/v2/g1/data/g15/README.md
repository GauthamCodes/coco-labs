# G1.5 — New worlds: budgets, honesty, Gazebo outputs

## Budgets (G1 prompt §1.1), measured by `lab_web/tools/g1/budgets.mjs`

Raw: [`budgets.json`](budgets.json). Renderer: `ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)` (cloud container, software GL);
triangles and draw calls are three.js's own per-frame counters, the maximum over three
views (chase at the start, a 14 m orbit, a 30 m tactical view). Download = the world's own
assets as served gzip (canonical spec + baked light map + COCO's glTF for the tier). The
game's code chunks add 15,758 bytes gzip (GameApp-BRZ18QRe.js, post-D8WacuvZ.js); the title-critical
budget is check_dist's.

| World | Tier | Download (bytes, gzip) | Triangles | Draw calls | Budget (low ≤ 1.2 MB / 150k / 120; high ≤ 3 MB / 400k / 250) |
| --- | --- | --- | --- | --- | --- |
| depot | low | 278,534 | 14,399 | 60 | within |
| depot | medium | 278,534 | 14,411 | 58 | n/a (no stated budget) |
| depot | high | 674,794 | 29,999 | 105 | within |
| proving | low | 186,603 | 6,319 | 23 | within |
| proving | medium | 186,603 | 6,319 | 23 | n/a (no stated budget) |
| proving | high | 582,863 | 21,907 | 55 | within |

Textures are procedural on the device (0 bytes); see `../../ASSET_MANIFEST.md`.

## Decorative honesty

`lab_web/test/g1_honesty.test.ts`: every decorative part of the Depot and both Proving Ground
specs is `solid` inside a collision footprint, on a wall's face (≤ 5 cm), overhead (≥ 3.5 m),
a decal (≤ 2 cm on its surface) or outside the bounds; every footprint is drawn; every actor
part is inside its actor's collision box; the checker is shown to catch five kinds of
violation. The bake (`tools/g1/bake_worlds.mjs`) refuses a dishonest look.

## The Gazebo SDF still comes from the same spec, unchanged

No file under `coco_lab/`, `tools/m6/`, `gazebo_models/` or `worlds/*.yaml`, and neither
Proving Ground JSON, changed since the M6 merge (`git diff b9b42d4 --` those paths is
empty). `coco_lab/test/test_depot.py::test_the_committed_output_checksums_reproduce`
reproduces every committed output checksum (SDFs, Nav2 map, arena world): 35 passed in
`test_depot.py` + `test_worldgen.py`. **`gz sdf -k` was skipped (no `gz` in the cloud
container): pending, laptop.** G1's only new world file, `worlds/coco_depot_v1.json`, is
`coco_lab.worldspec.canonical_bytes` of the committed YAML, checked by
`tools/g1/depot_json.py --check` (run in `lab_web/tools/test_g1_game_glue.py`).
