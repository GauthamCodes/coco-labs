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

## G1.11 — Gautham's follow-up (2026-10-21)

Decisions: [`G1_STATUS.md`](G1_STATUS.md#gauthams-decisions-2026-10-21-g111), `docs/STATUS.md`'s
plan-change log. Evidence: [`data/g111/README.md`](data/g111/README.md).

| Decision | What changed | Measured |
| --- | --- | --- |
| 1. gz tests | `@pytest.mark.gz` on the M6F.2 gz test; plain-venv CI `-m "not gz"` | that job: 0 skips (2 deselected); gz tests → laptop |
| 2. v3 cost | each LiDAR beam's direction computed once a tick (was 3×): same bits | v3/v2 per tick 1.15 → **1.10** (Pyodide-in-Node, same run); all goldens identical |
| 3. Ghost freeze | Fetch Rush rules 2 read a precomputed round; nothing planned in play; shaders precompiled | worst model-tick gap **25.8 s → 0.96 s**; banner 2× (26.8 s) → **never**; frames > 50 ms 1 → **0** (max 18.9 ms); worker tick max 2,184 → 76 ms |
| 4. 2026-10-18 decision | a start zone, 3 orders each ≤ 32 m planned round trip, timer = reference × 1.5 | timers **491.7 / 495.8 / 577.2 / 506.5 s** (shifts 1/3/5/6); seeds 2, 4: reference bot stopped in the forklift lane → no timer, not offered ([`GAMES.md`](../m6/GAMES.md)) |
| 5. Look | exposure + fill, COCO rim light / body / LED glow, thin ghost route + chevrons + small pin, minimap contrast + targets + off-map arrows | [`BEFORE_AFTER.md`](BEFORE_AFTER.md) "After G1.11" — Gautham judges |

Tests after G1.11 (this container, the final source):

| Suite | G1.10 close | G1.11 close |
| --- | --- | --- |
| coco_lab (plain venv) | 1,026 passed | **1,037 passed**, 2 deselected (`gz`, laptop) |
| lab_web/tools | 230 passed | **230 passed** |
| vitest | 532 passed | **532 passed** |
| typecheck, build, check_dist, v1 links (50 + 6) | pass | **pass** |
| native vs Pyodide gate (v3) | every family exact | **every family exact** |

Log: [`data/g111/suites.txt`](data/g111/suites.txt); CI run 39635640420 green on `dfdf4e6`.

**A fix found at close.** `numerics.use()` was sticky: a hash-v3 call left the fdlibm functions
in force for whatever ran next in the process. In CI, Lab 5's libm-era movebundle replay ran
after the game glue's v3 tests and failed its committed metrics (`DWB_3 metrics differ`). The
mode is now scoped (`numerics.version` / `in_run`): the Arena's entry points, the game rules,
Compare, the glue's worker calls and the tools each run in their own run's version and put back
the caller's. v3 goldens, the rounds' reference replay and the native gate are unchanged
([ADR 0010](../adr/0010-state-hash-v3.md), amended).

Hashes: v1, v2 and v3 goldens unchanged by G1.11 (the scan change is value-identical; checked
by the coco_lab goldens and `tools/g1/make_v3_goldens.py --check`). Fetch Rush rules 1 records
(M6F.6's references) still verify; rules-2 records carry `rules: 2` and replay to the committed
reference card and chain (`test_the_reference_record_replays_to_its_card`).

## G1.12 — Gautham's decisions (2026-10-22)

Decisions: [`G1_STATUS.md`](G1_STATUS.md#gauthams-decisions-2026-10-22-g112), `docs/STATUS.md`'s
plan-change log. Evidence: [`data/g112/README.md`](data/g112/README.md).

| Decision | What changed | Measured |
| --- | --- | --- |
| 1. Phone rounds | Fetch Rush rules 3: `phone` (default, 2 orders) and `full` (Full shift, 3 orders, 32 m); start at the zone's roomiest cell facing the open aisle | **16 m is infeasible** with the lanes kept out (no 2-order round below 21.4 m, [`phone_budget.json`](data/g112/phone_budget.json)): phone budget **provisional 22 m**, one round, reference 183.9 s → timer **275.9 s (4:35.9)**; Full shift timers **475.7–577.5 s** ([`GAMES.md`](../m6/GAMES.md)) |
| 2. Lanes; reject unfinished | trips count only if A*'s route keeps out of `zone_forklift_lanes`; the bot's run rejects a round (redraw) if it fails a delivery or stands in a lane | no draw rejected: every round 0 contacts, all orders delivered |
| 3. AUTO never pauses | `Arena.prefetch`: AUTO's search run between ticks in ≤ 4 ms slices, taken over by the AUTO tick (same plan, hashes unchanged — tested) | AUTO tick's worker step **452 → ≤ 101 ms** (one machine, back to back); the ≤ 100 ms tick-gap target is **not shown in this container** (tick arrivals p95 300–450 ms without AUTO) → laptop |
| 4. Chase camera | 2.1 m boom (≥ 1.7 m, ≥ 1.2 m up); COCO at 40 % down; rises over walls; COCO's shoulders kept in view; softer headlight and bloom | HUD overlap **0 / 40** poses (phone landscape + desktop; CI step); 25 vitest camera checks |

Tests after G1.12 ([`data/g112/suites.txt`](data/g112/suites.txt)): coco_lab **1,057** passed
(2 `gz` deselected; G1.11 1,037), lab_web/tools **231** (230), vitest **535** (532); typecheck,
build, `check_dist`, v1 links (50 + 6) pass. Hashes: v1, v2, v3 goldens unchanged; rules 1 and 2
records still verify; rules-3 references replay to their committed cards and chains.

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
