# G1 · Game Look — status

Prompt: [`G1_PROMPT.md`](G1_PROMPT.md). Art direction: [`ART_DIRECTION.md`](ART_DIRECTION.md).

## Now

- **Current checkpoint:** G1.11 Gautham's follow-up — done in the cloud (Fetch Rush rules 2, no planning in play, look polish, gz marker, v3 cost); results in [`G1_RESULTS.md`](G1_RESULTS.md); laptop and phone items pending.
- **Next step:** Gautham's look review of G1.11 ([`BEFORE_AFTER.md`](BEFORE_AFTER.md), column "After G1.11") and the Fetch Rush timers (8–9½ min by the decision's formula); then the laptop and phone items below; then the M6 UI phase (README §7).

## Setup facts

- PR #25 is **open, not merged** → branched from `origin/v2/m5-focus` (`ddc3718`), then
  merged `origin/v2/m6-foundations` (`984b2cf`) once (merge commit `b9b42d4`, no conflicts).
- Branch: the session's designated branch **`claude/serene-davinci-v9y796`** (this cloud
  session may only push there). The prompt names `v2/g1-game-look`; Gautham can rename the
  branch or open the PR from it as he prefers. No force-push; nothing merged into main.
- Environment: cloud container (Xeon 2.1 GHz × 4, SwiftShader, no GPU, no ROS, no phone).

## Gautham's decisions, 2026-10-21 (G1.11)

Recorded in `docs/STATUS.md`'s plan-change log, with the 2026-10-18 Fetch Rush decision.

1. **gz tests:** a `gz` pytest marker on the M6F.2 test; the plain-venv CI job runs `-m "not gz"`
   (green, zero skips); the gz tests are a laptop item; gz is not installed in CI.
2. **Hash v3's ~15 % cost is accepted;** profile once, take a cheap win that leaves hashes unchanged.
3. **The Fetch Rush ghost freeze is a blocker:** play never pauses for planning; reference routes
   precomputed; no frame over 50 ms and no "clock waits" banner in normal play; before/after timings.
4. **Fetch Rush follows the 2026-10-18 decision:** orders drawn so each planned round trip fits a
   budget, rounds start inside one zone, timer = the reference bot's time for 3 deliveries × 1.5.
5. **Look polish:** exposure and fill; COCO readable (rim light, brighter body, LED from the chase
   camera); the ghost route as a thin glowing line with chevrons, a small pin; a stronger minimap
   with the order's targets marked; after screenshots re-captured.

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
| G1.7 Robot vision, Compare | done | Vision: LiDAR as a faint cyan fan with bright hit points; the model's own costmap (`costmap_view`, every 4 s while on) as a hologram — lethal red cross-hatch, inscribed yellow stripes, inflation cyan fading with cost, a faint scanline (shape carries meaning); the plan as a magenta ribbon; Grasp Assist candidates ✓/✕. Compare: game type, cyan-edged panes, results strip, scanline overlay (chrome only; M5's CVD-tested computation colours untouched); Depot backdrop removed. Vitest incl. M5's compare_loop / comparison_pixels / pane_layout: pass. [`screens/g17/`](screens/g17/) |
| G1.8 M5 carry-overs | done | **Hash v3** (ADR 0010): every transcendental from `coco_lab.numerics` (fdlibm in pure Python), so CPython = Pyodide bit for bit; v1/v2 unchanged (every old golden passes; coco_lab 1006 → 1026 passed, 2 skipped = the gz CLI test, as at baseline); new v3 goldens (`coco_lab/test/fixtures/v3/`); new runs (Arena page, game, Compare) use v3. **Native-vs-Pyodide CI gate** (`lab_web/tools/g1/native_gate.mjs`): under v3 every compared value identical; under v2 the same cases fail with M5's 0.446011142799704 m (the control). Browser → Pyodide-in-Node → CPython replay of a v3 Fetch Rush session: identical chain. Cost +15 % per model tick (Pyodide-in-Node). **Update isolation**: per-build caches, page→build map, build-pinned worker URLs (`__b/<build>/`), "New version ready" (Save run, Reload; never automatic), old caches deleted only when no page of that build is open; CI check `tools/update_isolation_check.mjs`: `openDocumentMixed: false` and 8 more checks pass; M5's worker fails them (the control). [`data/g18/README.md`](data/g18/README.md) |
| G1.9 Performance | done (cloud) | Emulated Nothing Phone (1), Depot medium, 10 min: JS per frame median 7.9 ms, p95 16.0 ms (budget 16.7); drawn 4.7 fps median **on SwiftShader (software GPU), not a phone number**; desktop 10 min JS 1.8 / 5.5 ms; 30-min emulated soak: 0 errors, **0 WebGL context losses**; title JS 284,510 B gzip; every world × tier within budget. **60 fps not evaluable without a GPU — pending laptop and real phone.** [`data/g19/README.md`](data/g19/README.md) |
| G1.10 Close | done | After screenshots ([`BEFORE_AFTER.md`](BEFORE_AFTER.md)); coco_lab 1026/0/2, tools 230/0, vitest 532/0, typecheck, build, dist; v1 corpus 15,000 hashes and v2 corpus (Node + Chromium) 15,000 ticks each, 0 mismatches; 50 v1 URL forms + 6 archive views, 5 replays, 5 canvas scenes pass. [`G1_RESULTS.md`](G1_RESULTS.md), [`data/g110/README.md`](data/g110/README.md) |
| G1.11 Gautham's follow-up | done | (1) `gz` marker, CI `-m "not gz"`: 0 skips. (2) LiDAR beam directions computed once a tick (same bits; goldens unchanged): v3/v2 per-tick cost 1.15 → **1.10**. (3) Fetch Rush rules 2 plan nothing in play: worst model-tick gap **25.8 s → 0.96 s**, "clock waits" banner 2× (26.8 s) → **never**, frames over 50 ms 1 → **0** (max 18.9 ms), 3/3 delivered in 358.2 s. (4) The decision implemented: a start zone, 3 orders within a 32 m planned round trip, timer = reference × 1.5 → **491.7 / 495.8 / 577.2 / 506.5 s** (shifts 1/3/5/6); seeds 2 and 4: the reference bot stopped in the forklift lane (0 delivered) → no timer, not offered. (5) Look polish; after shots `screens/after_g111/`. Found at close: hash v3's numerics mode was sticky (a v3 call left it on; CI's Lab 5 replay failed after the v3 glue tests) → now scoped per call, hashes unchanged (ADR 0010 amended). Suites: coco_lab 1,037 (+2 `gz` deselected), tools 230, vitest 532, native gate exact; CI green on `dfdf4e6` ([`data/g111/suites.txt`](data/g111/suites.txt)). [`data/g111/README.md`](data/g111/README.md), [`docs/v2/m6/GAMES.md`](../m6/GAMES.md) |

## Gautham: look at these

- **G1.11 look**: [`BEFORE_AFTER.md`](BEFORE_AFTER.md) column "After G1.11" (`screens/after_g111/`): brighter hall, COCO's rim light and LED glow, the thin ghost route with chevrons, the minimap. Shift 1 starts facing a pallet stack, which the headlight lights.

- **Before / after (G1.10)**: [`BEFORE_AFTER.md`](BEFORE_AFTER.md) — `screens/before/` vs `screens/after/`.

- Before screenshots: `docs/v2/g1/screens/before/*.png`.
- **Mockups (G1.1)**, each at 915 × 412 and 1440 × 900: `docs/v2/g1/mockups/` — `play-fetch` (Fetch Rush HUD, GRAB ring filling), `play-fetch-keys` (desktop key hints), `play-free` (Free Drive, Vision on, GO), `play-refused` (greyed GRAB "Too wide", AUTO on, contact flash, forklift toast), `title`, `loading` (real stages), `modes`, `pause`, `results` (values: the Fetch Rush seed-1 reference card). The 3D backdrop is a hand-drawn SVG stand-in, not the renderer.

- **G1.2 shell** (cloud SwiftShader renders): `docs/v2/g1/screens/g12/` — title (desktop, phone landscape), mode select, loading, pause (STOP stays on top), Recordings, portrait rotate card.

- **G1.4 cameras**: `docs/v2/g1/screens/g14/` — chase, tactical (desktop and phone landscape), orbit.

- **G1.5 worlds**: `docs/v2/g1/screens/g15/` — Depot overview (high, low), Depot aisle (phone, medium), Proving Ground chase and orbit.

- **G1.6**: `docs/v2/g1/data/g16/results_run/results.png` (★★☆ results), `browser/after.png`, `docs/v2/g1/screens/g16-compare-depot.png`.

- **G1.7**: `docs/v2/g1/screens/g17/` — Vision chase and tactical, Compare desktop (arena and Depot) and phone landscape.

## Laptop items pending

- **G1.11**: the `gz`-marked tests (`pytest -m gz`, `test_worldgen.py` gz sdf checks on the generated worlds).

- **G1.9**: real-GPU fps on both GPUs; the Nothing Phone (1) over USB/CDP with a 10-minute heat run; the default tier.
- **G1.10**: the four-engine (Node, Chromium, Firefox, WebKit) 100-session v2 corpus (`data/g110/rerun_determinism.py`, `G1_ENGINES=node,chromium,firefox,webkit`).

- Touch-to-motion on the laptop GPU (G1 vs M5, `tools/g1/input_check.mjs --only-latency`).

- ROS package suites (`scripts/run_all_package_tests.sh`): not runnable in the cloud.
- Anything needing a real GPU, `gz`, the Nothing Phone (1) over USB.
- `gz sdf -k` on the Depot SDFs (unchanged since M6F.3, where it was Valid).

## Deviations so far

- **Branch name**: `claude/serene-davinci-v9y796` instead of `v2/g1-game-look` (cloud session restriction).
- **KTX2**: textures are procedural on the device (0 bytes) and light maps are small PNGs; no KTX2 encoder in the pinned toolchain (`ASSET_MANIFEST.md`).
- **Code landing order**: the Play HUD, session, cameras and Depot builder modules were written together and land with G1.2's commit; G1.3–G1.6 add their tests, evidence and fixes.

## Questions for Gautham

- ~~CI `coco_lab in a plain venv` red on the gz skips~~ — decided 2026-10-21: `gz` marker, `-m "not gz"` (G1.11).
- ~~Accept hash v3's +15 %?~~ — accepted 2026-10-21; now 1.10× after G1.11's hash-neutral speed-up.
- **Fetch Rush timers are 8:11–9:37** by the decision's formula (the reference needs 328–385 s for 3 budgeted orders at 0.3 m/s): keep, or fewer orders / objects nearer the docks for a shorter game?
- **Seeds 2 and 4** (the High-bay round crossing the forklift lane) have no reference time because M6F.6's bot stops in the lane: teach the bot the Rush Hour staging crossing, or keep excluding such rounds?
- **AUTO's route planning** still pauses the model 0.8–1.0 s per press on this machine (the Arena's own planner, as for a tapped goal; below the banner): time-slice it (M6 UI phase)?

- ~~Fetch Rush's next-order ghost is slow~~ — fixed in G1.11 (rules 2 precompute it). Was: (M6 rule `FetchRush._new_order`: up to 17 fully traced A* searches on the Depot): measured 12.1 s CPython, 17.4 s in a Pyodide tick. Model time waits (scores stay fair) and the HUD says so, but the screen pauses after each delivery. Options: compute the ghost lazily at the end, untraced searches with a test that results are identical, or M6F.4's WebAssembly gate. G1 left the rule unchanged.

- ~~Fetch Rush's first orders can be far~~ — answered by the 2026-10-18 decision, implemented in G1.11. Was: (M6F.6 found seed 3's first ghost path 77.9 m, ~260 s at the 0.3 m/s autonomous limit). G1 plays the rules as committed; the game-design question in `docs/v2/m6/PARALLEL_STATUS.md` stays open.
