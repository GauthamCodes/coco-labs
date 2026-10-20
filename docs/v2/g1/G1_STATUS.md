# G1 · Game Look — status

Prompt: [`G1_PROMPT.md`](G1_PROMPT.md). Art direction: [`ART_DIRECTION.md`](ART_DIRECTION.md).

## Now

- **Current checkpoint:** G1.6 Fetch Rush playable — done (CPython/Pyodide parity FAILS as diagnosed; G1.8 fixes it).
- **Next step:** G1.7 Robot vision (holographic costmap layers) and the Compare restyle (incl. the Depot backdrop).

## Setup facts

- PR #25 is **open, not merged** → branched from `origin/v2/m5-focus` (`ddc3718`), then
  merged `origin/v2/m6-foundations` (`984b2cf`) once (merge commit `b9b42d4`, no conflicts).
- Branch: the session's designated branch **`claude/serene-davinci-v9y796`** (this cloud
  session may only push there). The prompt names `v2/g1-game-look`; Gautham can rename the
  branch or open the PR from it as he prefers. No force-push; nothing merged into main.
- Environment: cloud container (Xeon 2.1 GHz × 4, SwiftShader, no GPU, no ROS, no phone).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| G1.0 Baseline | done | [`data/baseline/BASELINE.md`](data/baseline/BASELINE.md), [`screens/before/`](screens/before/) |
| G1.1 Art direction, mockups | done | [`ART_DIRECTION.md`](ART_DIRECTION.md), [`mockups/`](mockups/) (HTML in `mockups/src/`, rendered by `lab_web/tools/g1/render_mockups.mjs`); Chakra Petch + Inter added to `docs/v2/DESIGN_ASSETS.json` (OFL-1.1, self-hosted) |
| G1.2 Game shell | done | Title (3D hero of COCO in the Depot, PLAY, Compare/Research/Learn, ⓘ), mode select (`?view=play`), loading screen driven by the worker's real marks, first-run tutorial, pause, settings, results (stars from `coco_lab.games.stars` against the committed reference), Recordings in the game's skin; worker `game` boot + pack; glue `game_init`/`game_op`; [`screens/g12/`](screens/g12/); tests `test/g1_rules_view.test.ts`, `test/g1_honesty.test.ts`, `tools/test_g1_game_glue.py`; [`ASSET_MANIFEST.md`](ASSET_MANIFEST.md). Suites: vitest 509/0, tools 226/0, typecheck, build, dist (title JS 281,319 B gzip) |
| G1.3 Play HUD, controls | done | [`data/g13/README.md`](data/g13/README.md): touch drive, second-finger STOP, hold-to-release, nudge, minimap goal, mocked gamepad, keyboard-only playthrough all pass against the model's own ticks; touch-to-motion G1 127.8 ms vs M5 320.2 ms median (cloud SwiftShader, emulated profile, same harness). Lambert shading below high, headlight spot high-only, medium 1.25× pixels |
| G1.4 Cameras | done | Chase (spring-damped, look-ahead, a boom that shortens with a face-distance pad and swings up toward top-down when there is no room, never into a wall), tactical (roof and fixtures hidden above them), orbit (drag/pinch/wheel), 0.4 s blends, straight cuts under reduced motion. `test/g1_camera.test.ts`: 20 scripted paths (walls, corners, reversing into a wall, spinning beside it, maze, aisles, office entrance, dock corner, Proving Ground) — no frame with the camera inside a solid or a solid between it and COCO; a non-vacuity check that the pull-in engages. [`screens/g14/`](screens/g14/) |
| G1.5 New worlds | done | Depot from World Spec v3 (kit parts, procedural textures, baked AO + light pools, instanced props, decals, actors on their bodies), Proving Ground "test lab" restyle; every world × tier within budget (Depot low 278,534 B / 14,399 tris / 60 draws; high 674,794 B / 29,999 / 105); honesty test; generated SDF/map/world unchanged (checksums reproduce); orbit now pulls in at walls too. [`data/g15/README.md`](data/g15/README.md), [`screens/g15/`](screens/g15/) |
| G1.6 Fetch Rush playable | done | Played through the page's own keys in Chromium: 1 delivery, 0 contacts, 141.4 s, ★★☆ from `coco_lab.games.stars` vs the reference (136.7 s); GRAB/DROP from Grasp Assist's own candidates; arm joints follow `coco.arm.state.v1`; candidates ringed in Robot vision; planner ghost (Settings); results → Compare on the Depot. Browser Pyodide = Pyodide-in-Node exactly; **CPython differs from tick 0** (2/480 LiDAR ranges differ in the last bit; hash v2 encodes them) — not hidden, G1.8. Found: the next order's ghost search stalls a tick (12.1 s CPython, 17.4 s Pyodide-in-Node). [`data/g16/README.md`](data/g16/README.md) |

## Gautham: look at these

- Before screenshots: `docs/v2/g1/screens/before/*.png`.
- **Mockups (G1.1)**, each at 915 × 412 and 1440 × 900: `docs/v2/g1/mockups/` — `play-fetch` (Fetch Rush HUD, GRAB ring filling), `play-fetch-keys` (desktop key hints), `play-free` (Free Drive, Vision on, GO), `play-refused` (greyed GRAB "Too wide", AUTO on, contact flash, forklift toast), `title`, `loading` (real stages), `modes`, `pause`, `results` (values: the Fetch Rush seed-1 reference card). The 3D backdrop is a hand-drawn SVG stand-in, not the renderer.

- **G1.2 shell** (cloud SwiftShader renders): `docs/v2/g1/screens/g12/` — title (desktop, phone landscape), mode select, loading, pause (STOP stays on top), Recordings, portrait rotate card.

- **G1.4 cameras**: `docs/v2/g1/screens/g14/` — chase, tactical (desktop and phone landscape), orbit.

- **G1.5 worlds**: `docs/v2/g1/screens/g15/` — Depot overview (high, low), Depot aisle (phone, medium), Proving Ground chase and orbit.

- **G1.6**: `docs/v2/g1/data/g16/results_run/results.png` (★★☆ results), `browser/after.png`, `docs/v2/g1/screens/g16-compare-depot.png`.

## Laptop items pending

- Touch-to-motion on the laptop GPU (G1 vs M5, `tools/g1/input_check.mjs --only-latency`).

- ROS package suites (`scripts/run_all_package_tests.sh`): not runnable in the cloud.
- Anything needing a real GPU, `gz`, the Nothing Phone (1) over USB.
- `gz sdf -k` on the Depot SDFs (unchanged since M6F.3, where it was Valid).

## Deviations so far

- **Branch name**: `claude/serene-davinci-v9y796` instead of `v2/g1-game-look` (cloud session restriction).
- **KTX2**: textures are procedural on the device (0 bytes) and light maps are small PNGs; no KTX2 encoder in the pinned toolchain (`ASSET_MANIFEST.md`).
- **Code landing order**: the Play HUD, session, cameras and Depot builder modules were written together and land with G1.2's commit; G1.3–G1.6 add their tests, evidence and fixes.

## Questions for Gautham

- **Fetch Rush's next-order ghost is slow** (M6 rule `FetchRush._new_order`: up to 17 fully traced A* searches on the Depot): measured 12.1 s CPython, 17.4 s in a Pyodide tick. Model time waits (scores stay fair) and the HUD says so, but the screen pauses after each delivery. Options: compute the ghost lazily at the end, untraced searches with a test that results are identical, or M6F.4's WebAssembly gate. G1 left the rule unchanged.

- Fetch Rush's first orders can be far (M6F.6 found seed 3's first ghost path 77.9 m, ~260 s at the 0.3 m/s autonomous limit). G1 plays the rules as committed; the game-design question in `docs/v2/m6/PARALLEL_STATUS.md` stays open.
