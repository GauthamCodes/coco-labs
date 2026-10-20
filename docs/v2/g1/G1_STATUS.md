# G1 · Game Look — status

Prompt: [`G1_PROMPT.md`](G1_PROMPT.md). Art direction: [`ART_DIRECTION.md`](ART_DIRECTION.md).

## Now

- **Current checkpoint:** G1.4 Cameras — done.
- **Next step:** G1.5 new worlds: tier budgets measured, SDF unchanged check, Proving Ground restyle review.

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

## Gautham: look at these

- Before screenshots: `docs/v2/g1/screens/before/*.png`.
- **Mockups (G1.1)**, each at 915 × 412 and 1440 × 900: `docs/v2/g1/mockups/` — `play-fetch` (Fetch Rush HUD, GRAB ring filling), `play-fetch-keys` (desktop key hints), `play-free` (Free Drive, Vision on, GO), `play-refused` (greyed GRAB "Too wide", AUTO on, contact flash, forklift toast), `title`, `loading` (real stages), `modes`, `pause`, `results` (values: the Fetch Rush seed-1 reference card). The 3D backdrop is a hand-drawn SVG stand-in, not the renderer.

- **G1.2 shell** (cloud SwiftShader renders): `docs/v2/g1/screens/g12/` — title (desktop, phone landscape), mode select, loading, pause (STOP stays on top), Recordings, portrait rotate card.

- **G1.4 cameras**: `docs/v2/g1/screens/g14/` — chase, tactical (desktop and phone landscape), orbit.

## Laptop items pending

- Touch-to-motion on the laptop GPU (G1 vs M5, `tools/g1/input_check.mjs --only-latency`).

- ROS package suites (`scripts/run_all_package_tests.sh`): not runnable in the cloud.
- Anything needing a real GPU, `gz`, the Nothing Phone (1) over USB.

## Deviations so far

- **Branch name**: `claude/serene-davinci-v9y796` instead of `v2/g1-game-look` (cloud session restriction).
- **KTX2**: textures are procedural on the device (0 bytes) and light maps are small PNGs; no KTX2 encoder in the pinned toolchain (`ASSET_MANIFEST.md`).
- **Code landing order**: the Play HUD, session, cameras and Depot builder modules were written together and land with G1.2's commit; G1.3–G1.6 add their tests, evidence and fixes.

## Questions for Gautham

- Fetch Rush's first orders can be far (M6F.6 found seed 3's first ghost path 77.9 m, ~260 s at the 0.3 m/s autonomous limit). G1 plays the rules as committed; the game-design question in `docs/v2/m6/PARALLEL_STATUS.md` stays open.
