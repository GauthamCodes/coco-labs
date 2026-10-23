# G1 asset manifest (integrity rule 8)

Every asset G1 ships, its licence, source and checksum. **No third-party art is used.**

| Asset | Kind | Licence | Source | Checksum |
| --- | --- | --- | --- | --- |
| Chakra Petch 500/700 (latin) | font | OFL-1.1 | `@fontsource/chakra-petch` 5.3.0, self-hosted | `docs/v2/DESIGN_ASSETS.json` |
| Inter variable (latin, latin-ext) | font | OFL-1.1 | `@fontsource-variable/inter` 5.3.0, self-hosted | `docs/v2/DESIGN_ASSETS.json` |
| Depot and Proving Ground geometry | procedural | Apache-2.0 (own work) | generated from the World Spec at load (`lab_web/src/game/world/describe.ts`, `build3d.ts`) | the World Spec bytes (`worlds/*.json`, sha256 in `public/generated/arena/manifest.json`) |
| Surface textures (concrete, panels, fence, racks, cartons, wrap, chevrons, EXIT) | procedural | Apache-2.0 (own work) | drawn on the device from a seed (`lab_web/src/game/world/textures.ts`); nothing downloaded | code only |
| Floor light maps (`depot`, `proving_v1`, `proving_v2`) | baked at build time | Apache-2.0 (own work) | `lab_web/tools/g1/bake_worlds.mjs` | `public/generated/g1/manifest.json` (sha256 per PNG) |
| Forklift and walker | procedural low-poly | Apache-2.0 (own work) | `describe.actorLook`, inside each actor's collision box | code only |
| COCO | glTF from the URDF | Gautham's own CAD | `public/assets3d/robot_{low,high}.glb` | `docs/v2/ASSETS.md` |
| Mode-card art (`public/g1/modes.svg`) | vector | Apache-2.0 (own work) | the G1.1 mockup backdrop | git |
| Sounds | synthesised | Apache-2.0 (own work) | WebAudio at run time (`lab_web/src/game/sound.ts`); no files | code only |

Deviation (recorded for Gautham): the brief asks for KTX2 textures. G1's textures are
procedural on the device (zero download bytes) and its light maps are small PNGs
(119 kB Depot, 41 kB each Proving Ground); no KTX2 encoder is part of the pinned
toolchain, and none was needed to meet the download budget.
