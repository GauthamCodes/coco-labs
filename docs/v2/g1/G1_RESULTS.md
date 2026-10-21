# G1 · Game Look — results

Every number here has its conditions and its evidence file. Environment for all of it:
the **cloud container** (Intel Xeon 2.1 GHz × 4, **no GPU**: Chromium renders with
SwiftShader on the CPU; no ROS, no `gz`, no phone). Anything that needs a real GPU, the
laptop or the Nothing Phone (1) is **pending**, never estimated. Prompt:
[`G1_PROMPT.md`](G1_PROMPT.md); running status: [`G1_STATUS.md`](G1_STATUS.md).

## Branch

- Branch `claude/serene-davinci-v9y796` (the prompt's `v2/g1-game-look`; this cloud session
  may push only to its designated branch). Draft PR
  [GauthamCodes/coco-labs#27](https://github.com/GauthamCodes/coco-labs/pull/27) into `main`;
  not merged, not deployed, no release.
- Start: `origin/v2/m5-focus` `ddc3718` (PR #25 open, not merged), then `origin/v2/m6-foundations`
  `984b2cf` merged once (`b9b42d4`, no conflicts). Neither has moved since (checked at
  G1.10), so no re-merge was needed. One commit per checkpoint `[G1.0]`…`[G1.10]`, plus
  evidence follow-ups within G1.8 and G1.10.

## Per checkpoint

| Checkpoint | What changed | Evidence | Class |
| --- | --- | --- | --- |
| G1.0 Baseline | Prompt, status, plan-change entry, README §7; suites; before screenshots | [`data/baseline/BASELINE.md`](data/baseline/BASELINE.md), [`screens/before/`](screens/before/) | TESTED |
| G1.1 Art direction | "Night Shift Depot" art direction; nine HUD/shell mockups; Chakra Petch + Inter (OFL-1.1, self-hosted) | [`ART_DIRECTION.md`](ART_DIRECTION.md), [`mockups/`](mockups/), [`ASSET_MANIFEST.md`](ASSET_MANIFEST.md) | CONCEPT (mockups) |
| G1.2 Game shell | Title hero, mode select, real-stage loading, tutorial, pause, settings, results (stars from `coco_lab.games.stars`), Recordings skin | [`screens/g12/`](screens/g12/); `test/g1_rules_view.test.ts`, `test/g1_honesty.test.ts`, `tools/test_g1_game_glue.py` | MODEL, TESTED |
| G1.3 HUD and controls | Floating joystick, GRAB/DROP/GO, AUTO, CAM, STOP (latched, hold-release), minimap + tactical map, toasts, haptics, keys, gamepad | [`data/g13/README.md`](data/g13/README.md) | TESTED (emulated) |
| G1.4 Cameras | Chase (spring, look-ahead, wall-aware boom), tactical, orbit; reduced-motion cuts | `test/g1_camera.test.ts` (20 paths + orbit + non-vacuity), [`screens/g14/`](screens/g14/) | TESTED |
| G1.5 New worlds | Depot from World Spec v3 kit parts; Proving Ground restyle; baked light; honesty test | [`data/g15/README.md`](data/g15/README.md), [`screens/g15/`](screens/g15/) | MODEL, TESTED |
| G1.6 Fetch Rush | Playable on the Depot through the page's own keys; Grasp Assist candidates; planner ghost; Compare on the Depot | [`data/g16/README.md`](data/g16/README.md) | MODEL, TESTED |
| G1.7 Vision, Compare | LiDAR fan, the model's costmap as a hologram, plan ribbon; Compare restyle (computation colours unchanged) | [`screens/g17/`](screens/g17/) | MODEL |
| G1.8 M5 carry-overs | State hash v3 (deterministic numerics), native-vs-Pyodide CI gate, update isolation | [`data/g18/README.md`](data/g18/README.md), [ADR 0010](../adr/0010-state-hash-v3.md) | MODEL, TESTED |
| G1.9 Performance | Emulated phone and desktop runs, 30-min soak, budgets | [`data/g19/README.md`](data/g19/README.md) | MODEL, emulated |
| G1.10 Close | After screenshots, before/after, every suite, corpora, this file | [`BEFORE_AFTER.md`](BEFORE_AFTER.md), [`data/g110/README.md`](data/g110/README.md) | TESTED |

## Tests (before → after)

Before = G1.0 baseline ([`data/baseline/BASELINE.md`](data/baseline/BASELINE.md)); after = G1.10
on the final source ([`data/g110/suites/`](data/g110/suites/)). Same container, same routes.

| Suite | Before (G1.0) | After (G1.10) |
| --- | --- | --- |
| `coco_lab` (CI route, plain venv) | 1006 passed / 0 failed / 2 skipped | **1026 passed / 0 failed / 2 skipped** (+20: `test_numerics_v3.py`) |
| `lab_web/tools` | 220 / 0 / 0 | **230 / 0 / 0** (+6 G1 game glue, +4 v3 parametrisations) |
| `lab_web` vitest | 493 passed (62 files) | **532 passed (65 files)** |
| typecheck, `build_catalog.py`, `arena-assets`, build, `check_dist` | ok; title JS 271,801 B gzip | ok; title JS **284,510 B** gzip (limit 350 kB) |
| v1 URL forms (`v1_links_check.mjs`) | — | **50 forms + 6 archive views, 0 failed** |
| Replays (`replay_check.mjs`) | — | **5 / 5 play to their end**, badges and results, 0 errors |
| Canvas screenshots (`screenshots.mjs check`) | — | **5 scenes, 0 differing pixels**; self-test detects a difference |
| v1 corpus (M1, Node) | — | 100 × 150 = 15,000 hashes, **0 mismatches** |
| v2 corpus (M5, Node + Chromium) | — | 15,000 ticks per engine, **0 mismatches** |
| `coco_schemas` `--check` | not run (no `protoc`) | **not run (no `protoc` here); CI runs it** |
| ROS packages (`run_all_package_tests.sh`) | not run (no ROS) | **not run (no ROS); pending laptop** |

The 2 coco_lab skips are both `test_worldgen.py::test_gz_sdf_check_passes_on_every_generated_world`
(`kit` and `v2`; no `gz` CLI). G1.0's baseline note called the second one "the
repository-checkout test"; the skip reason in both runs is the gz CLI (`-rs` output in
`data/g110/suites/coco_lab.log`).

CI on the branch: `lab_web` (with the native-vs-Pyodide gate), the three-browser job (with
update isolation and determinism in Chromium, Firefox, WebKit) and `build-and-test` green;
`coco_lab in a plain venv` red **only** on its no-skip guard (the 2 gz skips above).

## Hashes

- **v1 unchanged.** The M1 corpus (100 sessions × 150 ticks) replayed on Pyodide-in-Node at
  G1.10: 15,000 hashes, **0 mismatches** against the committed M1 reference
  ([`data/g110/determinism-v1/determinism.json`](data/g110/determinism-v1/determinism.json)).
  The coco_lab v1 golden traces pass.
- **v2 replayable.** The M5 v2 corpus (100 × 150) on Pyodide-in-Node and Chromium:
  15,000 ticks each, **0 mismatches** against M5's reference
  ([`data/g110/determinism-v2/determinism.json`](data/g110/determinism-v2/determinism.json)).
  Firefox and WebKit could not be driven here (installed builds do not match this
  Playwright; no downloads); CI's three-browser job runs them on every push (10 v1 + 3
  terrain sessions, green on this branch). **The full four-engine 100-session v2 run is
  pending: laptop.**
- **v3 introduced (why):** CPython and Pyodide link different `libm`s; a 1-ulp LiDAR range
  moved a costmap cell and M5's Compare arms diverged by 0.446011142799704 m. v3 = v2's
  snapshot under its own tag, computed with `coco_lab.numerics` (fdlibm in pure Python).
  New runs use v3; v1/v2 links replay as before.
- **CPython vs Pyodide, per family (v3, CI gate):** global planners 818,951 values
  identical; Fetch Rush 1,436 values (every tick's hash + scorecard) identical; control
  Compare 6,440 identical; localisation Compare 25,500 identical. Under v2 the same cases
  fail (the control): 1,063 control failures, max 0.446011142799704 m
  ([`data/g18/native_gate_v3.json`](data/g18/native_gate_v3.json),
  [`native_gate_v2.json`](data/g18/native_gate_v2.json)). A v3 Fetch Rush played in
  Chromium replays to the same chain in Pyodide-in-Node and CPython (1,423 ticks).
- **Cost of v3:** +15 % per model tick (Pyodide-in-Node, Depot, 25.1 vs 21.8 ms median;
  [`data/g18/tick_cost.json`](data/g18/tick_cost.json)).

## Update isolation

CI check `lab_web/tools/update_isolation_check.mjs` (three-browser job, green): an open
build-A page across a deploy of build B — `openDocumentMixed: false`, A reads A's bytes
(own fetch and the worker's build-pinned path), "New version ready" with Save run and
Reload, no forced reload, A's cache kept while open and deleted after, reload consistent
on B, the model worker pinned. M5's worker fails the same checks (the control)
([`data/g18/update_isolation/`](data/g18/update_isolation/checks.json)).

## Performance (cloud; emulated)

| | Emulated Nothing Phone (1), 4× CPU | Desktop 1440 × 900 |
| --- | --- | --- |
| Depot medium, 10 min: JS per frame median / p95 | 7.9 / 16.0 ms (budget 16.7) | 1.8 / 5.5 ms |
| Frames drawn per second median / min (**SwiftShader, not a GPU**) | 4.7 / 1.8 | 3.8 / 0.7 |
| Title visible | 3,061 ms | 790 ms |
| Mode select → PLAY ready | 8,346 ms | 4,886 ms |
| 30-min soak | 0 errors, **0 WebGL context losses** | — |

Title-critical JS 284,510 B gzip (limit 350 kB). Depot low 278,534 B / 14,399 tris / 57
draws; high 674,794 B / 29,999 / 98; Proving Ground low 186,603 B / 6,319 / 23; high
582,863 B / 21,907 / 55 — all within budget
([`data/g19/budgets.json`](data/g19/budgets.json)). Touch-to-motion (G1.3, same harness,
emulated profile, SwiftShader): G1 127.8 ms vs M5 320.2 ms median.

**60 fps at medium on a phone: not evaluable here; pending the laptop (real GPU, both
GPUs) and the real Nothing Phone (1) over USB/CDP, including a 10-minute heat run and the
default-tier choice.**

## Gautham, look at these

- Before/after: [`BEFORE_AFTER.md`](BEFORE_AFTER.md) (`screens/before/`, `screens/after/`).
- Mockups: `mockups/` (nine screens, 915 × 412 and 1440 × 900).
- Per checkpoint: `screens/g12/`, `screens/g14/`, `screens/g15/`, `screens/g17/`,
  `screens/g16-compare-depot.png`, `data/g16/results_run/results.png`.

## Laptop items pending

- Real-GPU fps on both GPUs (balanced, on AC, driver recorded); the Nothing Phone (1) over
  USB/CDP with a 10-minute heat run; the default tier.
- Touch-to-motion on the laptop GPU (G1 vs M5, `tools/g1/input_check.mjs --only-latency`).
- The four-engine (Node, Chromium, Firefox, WebKit) 100-session v2 corpus
  (`data/g110/rerun_determinism.py` with `G1_ENGINES=node,chromium,firefox,webkit`).
- ROS package suites (`scripts/run_all_package_tests.sh`) and `gz sdf -k` on the Depot SDFs.

## Questions for Gautham

- **CI `coco_lab in a plain venv (no ROS)` is red on this branch** only because two tests
  skip without the `gz` CLI (`test_worldgen.py::test_gz_sdf_check_passes_on_every_generated_world`,
  from M6F.2 via the `v2/m6-foundations` merge; that branch is red the same way). Install the
  gz CLI in that job, or run that test only where gz exists? (PR comment.)
- **Fetch Rush's next-order ghost** stalls a tick after each delivery (12.1 s CPython, 17.4 s
  Pyodide): compute it lazily, untraced searches, or WebAssembly? G1 left M6's rule as is.
- Fetch Rush's far first orders (M6F.6) — the game-design question stays open.
- Accept v3's +15 % model cost per tick?

## Next step

Gautham's look review (before/after and mockups), the laptop and phone items above, and
the decision on the gz CLI; then the M6 UI phase per README §7.
