# COCO Lab — status

Where the work stands. [`README.md`](../README.md) (the master plan) is the
authority; this file records position, open questions and plan changes
only. Read order for agents (README §9): `README.md`, this file,
`CLAUDE.md`, `PROJECT_STATE.md`.

## Position

| | |
|---|---|
| Repository | `GauthamCodes/coco-labs`; canonical checkout `~/coco_labs_ws/src/coco-labs` ([`v2/CHECKOUTS.md`](v2/CHECKOUTS.md)) |
| v1 | **Frozen** at tag `coco-lab-v1-final` = `3571169` |
| M0 | **Closed 2026-10-08**: PR #19 merged into `main` as `9f58b83` (merge commit, owner's one-off permission); independent review [`v2/data/m0/REVIEW_2026-10-08.md`](v2/data/m0/REVIEW_2026-10-08.md), its findings resolved below; public site after the Pages deploy: 0 console errors, 0 page errors in all six views, Live shows the offline state ([`v2/data/m0/exit/public_after_merge.json`](v2/data/m0/exit/public_after_merge.json)) |
| M1 | **Closed 2026-10-09 — agent-measurable criteria**: independent review [`v2/reviews/M1_REVIEW.md`](v2/reviews/M1_REVIEW.md) (MERGE AFTER FIXES, every fix done); PR #20 merged into `main` as **`0a2516a`** (merge commit, owner's one-off permission, branch kept); public site after the Pages deploy: bare URL opens the Arena, a goal click drew its search, all six v1 views 0 console / 0 page errors ([`v2/data/m1/exit/public_after_merge.json`](v2/data/m1/exit/public_after_merge.json)). **Still pending Gautham:** phone performance, phone cold start, usability |
| Branch | `v2/m2-whole-loop` (from `main` = `0a2516a`), worked in the worktree `.claude/worktrees/v2-m2-whole-loop`, overlay `~/coco_lab_m2_ws` |
| Milestone | **M2 · The whole loop** ([`v2/M2_PROMPT.md`](v2/M2_PROMPT.md)) |
| Checkpoint | **M2.11 done: every agent-measured M2 criterion met** ([`v2/M2_RESULTS.md`](v2/M2_RESULTS.md)). Next: the M2 pull request (not merged by the agent), Gautham's phone and usability rows, a fresh review session |
| Merge to `main` | M2 opens a PR when every agent-measurable B.3 criterion passes; it is **not** merged by the agent (the merge permission covered PR #20 only) |
| Pending Gautham | Phone baseline ([`v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md)); M1 **phone performance**, **phone cold start** ([`v2/PHONE_MEASURE.md`](v2/PHONE_MEASURE.md)) and **usability** ([`v2/USABILITY_TEST.md`](v2/USABILITY_TEST.md)); M2's phone and usability rows — never marked done by the agent |

## Checkpoint log

- **M0.1 Verify (2026-10-08).** `main` = `2b6f8ad`, `lab5` = `3571169`;
  `lab5` strictly ahead by 2 documentation-only commits. Tests at
  `3571169`: packages 3,081 / 0 / 0, `lab_web` vitest 308 / 0 / 0, build
  tools 117 / 0 / 0. Evidence: [`docs/v2/data/m0/START_STATE.md`](v2/data/m0/START_STATE.md).
- **M0.2 Freeze v1 (2026-10-08).** Annotated tag `coco-lab-v1-final` on
  `3571169`. All six releases exist and are published; five carry their
  demo video, `live-v1.0` has none by design. The three recordings
  `docs/RESULTS.md` cites by checksum resolve in `~/coco_lab_runs/`
  (3/3). Evidence: [`docs/v2/data/m0/FREEZE.md`](v2/data/m0/FREEZE.md).
- **M0.3 Baseline (2026-10-08).** Laptop, Playwright, local production
  build, 5 fresh browsers each: Pyodide cold first edit median 12,857 ms
  (6,567–42,882), warm edit median 1,445 ms (1,265–1,686), every playing
  view at 60 fps rAF with 0 long tasks; `dist/` 23,010,799 B, Pyodide
  6,358,909 B. Phone: method written, **not yet measured**. Evidence:
  [`docs/v2/BASELINE.md`](v2/BASELINE.md),
  [`docs/v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md), `docs/RESULTS.md`
  "COCO Lab v2 · M0 baseline".
- **M0.4 Install the plan (2026-10-08).** `README.md` = the master plan,
  byte-identical to the owner's file (sha256 `4b003e50…a2ab6`;
  replaced on 2026-10-08 by the gripper-corrected plan, sha256
  `23214733…175935c`, see the plan-change log). Archived
  to `docs/archive/v1/`: `README_v1.md`, `ROADMAP.md`, `LAB_PHASES.md`,
  `CLAUDE_v1_rules.md`. New: `docs/ROADMAP.md` (pointer + v1 history),
  this file, `docs/IDEAS.md`; `PROJECT_STATE.md` and `CLAUDE.md` updated.
- **M0.5 Remove (2026-10-08).** No code or config exists for Isaac inside
  COCO Lab, the VLM layer or browser policy training; **0 files deleted**.
  The robot project's design sections for the VLM layer and policy
  training are marked out of scope in place; the robot-stack Isaac adapter
  (`coco_sim`) and the Isaac evidence are kept (frozen package; evidence).
  Old themes rewritten in `docs/ROADMAP.md`. Evidence:
  [`docs/v2/data/m0/REMOVALS.md`](v2/data/m0/REMOVALS.md).
- **M0.6 Honesty fixes (2026-10-08, copy only).** Site: the Live tab, its
  header and its mode badge read "Live Stack (simulated)" (local /
  scheduled demo), with a line saying it is a scheduled demo of the
  simulated stack and that no physical robot exists; Lab 4's "The real
  robot (Replay)" tab reads "The full ROS 2 stack (simulated) — Replay";
  the Lab 4 demo recorder's caption likewise. Docs: `docs/live/LIVE.md`
  title and `PROJECT_STATE.md` reworded with the old text recorded;
  correction notes at the top of `docs/labs/LAB1_PLAN.md`,
  `LAB4_SEARCH.md`, `LAB5_MOVE.md` and `docs/releases/lab4-v1.0.md`
  (bodies untouched). No "two-finger" wording exists outside the archive
  and frozen code comments. `lab_web/test/live.test.ts` updated for the
  new label; vitest 308 / 0 / 0.
- **M0.7 Freeze the robot-stack packages (2026-10-08).** `FROZEN.md` in
  each of the nine: `coco_config`, `coco_mission`, `coco_moveit_config`,
  `coco_perception`, `coco_rl`, `coco_sim`, `coco_web`, `custom_teleop`,
  `gazebo_models` — kept, no new features, decision G3 pending; nothing
  deleted. `coco_lab`, `coco_lab_ros` and `lab_web` are COCO Lab's own and
  are not frozen. `coco_web`'s `platform_server` is unfrozen by plan at
  M4–M5 (README §4).
- **M0.8 Deprecation notes (2026-10-08).** [`docs/v2/DEPRECATIONS.md`](v2/DEPRECATIONS.md):
  Canvas 2D rendering → Three.js (M1); per-lab formats → one MCAP
  envelope (M1–M2); public Tailscale Live → cloud sessions (M5, gated);
  six views → one Arena app (end of M2); races → Sandbox compare; replays
  and exhibits → Case Files (M3). Each stays working until its
  replacement ships; nothing deleted. Banner in `lab_web/README.md`.
- **M0 exit checks (2026-10-08).** On `9480faa`: packages 3,081 / 0 / 0,
  vitest 308 / 0 / 0, tools 117 / 0 / 0 (equal to M0.1); production build
  clean; plan, localise, map, search, move load with 0 console errors;
  live logs only the refused-socket network errors it logged in v1 (no
  Stack running); honesty copy visible at 1400 and 390 px, no "real
  robot" on screen. Evidence: [`docs/v2/data/m0/EXIT.md`](v2/data/m0/EXIT.md).
  **M0 is not closed**: it closes after Gautham approves the merge and a
  fresh review session verifies the report (README §9.9).

- **Independent review (2026-10-08, README §9.9): done.** A fresh
  session that did not do the work checked PR #19 at `c70f447`; report
  saved verbatim as [`v2/data/m0/REVIEW_2026-10-08.md`](v2/data/m0/REVIEW_2026-10-08.md).
  Verdicts: tag, releases, README, archive, nothing deleted, RESULTS
  append-only, required files, baseline numbers (recomputed exactly),
  tests (3,081 / 308 / 117), CI, recordings (3/3), lab5 fast-forward and
  checkpoint discipline **VERIFIED**; views load **VERIFIED, Live
  excepted**; honesty copy **NOT VERIFIED (partly fixed)**.
  Recommendation: **MERGE AFTER FIXES**. What the "exit checks passed"
  line above used to claim was not true: Live still logged console
  errors, so README §7's "every current public view still loads with no
  console errors" was not met.
- **M0 review fixes (2026-10-08, `[M0-fix]` commits).** Each finding and
  how it was resolved:

  | Review finding | Resolution | Evidence |
  |---|---|---|
  | Exit criterion not met: Live logged `ws://localhost:8080` connection-refused errors | **A.2 quiet Live probe.** Measured first: in Chromium a fetch to a dead endpoint is itself a console error (refused port, unresolvable host, opaque `no-cors` alike), so the page now contacts only what was asked for: a `?live=` link, Connect or Watch (`/healthz` first, backoff 2 s doubling to 30 s, socket only after an answer), and the scheduled demo's endpoint only while a demo is on. All six views: **0 console errors, 0 page errors**; Live opens 0 sockets on load; recovery against a stand-in server connects with 1 socket | `v2/data/m0/exit/console_after_fix.json`, `probe_noise.json` |
  | STATUS.md said "exit checks passed" (overstated) | Replaced by the Checkpoint row above and this entry | this file |
  | "All four CI jobs passed" | Three passed; the Pages deploy is **skipped** on PR runs (it runs on `main` only) | PR #19 checks |
  | Correction notes claimed for the lab4 release notes, but only the repo copy was corrected; lab1-v1.0's "a real robot used" not mentioned; live-v1.0 title says "the real robot" | **A.4**: the three published texts edited, wording only, under a one-off owner permission; tags, targets, flags and assets re-read identical | `v2/data/m0/releases_before/`, `releases_after/`, `releases_diff.txt` |
  | `docs/RESULTS.md:8568` "The real robot chose…" has no note; `docs/history/ROADMAP_LAB_2026-09-28.md` has no header | **A.3**: appended dated correction note in RESULTS.md (line untouched); correction header on the roadmap (body untouched). Repo search: 68 hits, 0 needing a fix; rendered site shows no "real robot" | `v2/data/m0/exit/copycheck_after_fix.json` |
  | Gripper described two ways (plan: magnet only; robot-stack record: fingers and a magnet) | **A.1**: owner's corrected plan installed (plan-change log); four M0-written lines now say "two fingers and a magnet; the magnet holds the object" | README sha256 `23214733…175935c` |
  | "Two exit criteria aren't fully met" counted the phone baseline | The phone baseline is **not** an M0 exit criterion: M0.3 asks for the method and the script, which exist. The measurement itself is **pending Gautham** ([`v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md)) | — |
  | "Worktree clean" not checkable by the reviewer | The fix session ran `git status` before every commit in the same worktree; the remote branch head is the pushed end SHA | `git log` |
  | Merging lands lab5's two docs-only commits on `main` | Expected under M0.1; no action | START_STATE.md |
  | `~/coco_labs_ws/src/coco-labs` is a stale clone while `CLAUDE.md` and the scripts default to it | **Resolved by M1 step B.1**: that checkout is fast-forwarded to the merged `main` and becomes canonical (plan-change log, 2026-10-08) | `v2/CHECKOUTS.md` (M1) |

- **M0-close tests (2026-10-08).** On `33c11dc` (overlay `~/coco_v2_ws`,
  ROS domain 78): packages **3,081 / 0 / 0** (equal to M0.1; per package in
  [`v2/data/m0/exit/packages_after_fix.txt`](v2/data/m0/exit/packages_after_fix.txt)),
  `lab_web` typecheck clean and vitest **320 / 0 / 0** (308 unchanged + 12
  new in `test/live_gate.test.ts`), build tools **117 / 0 / 0**. The package
  run shared the machine with an orphaned e-Yantra `gz sim server` (owner's,
  about one core, not touched); nothing failed. PR #19 CI on `33c11dc`:
  `build-and-test` pass (collected 2,356 tests across 9 suites, 0
  failed), `coco_lab in a plain venv` pass, `lab_web` pass, Pages deploy
  skipped (PR run).

- **M0 closed (2026-10-08).** PR #19 merged at `9f58b83` (`gh pr merge
  --merge`, branch kept) after every M0-close condition held on the final
  head `21d94a8`: packages 3,081 / 0 / 0, vitest 320 / 0 / 0, tools
  117 / 0 / 0; CI `build-and-test`, `coco_lab in a plain venv`, `lab_web`
  pass (Pages deploy skipped on the PR run); 0 console errors in all six
  views; `README.md` byte-identical to the owner's file. The `main` run
  then deployed Pages (success), and the public site was checked:
  [`v2/data/m0/exit/public_after_merge.json`](v2/data/m0/exit/public_after_merge.json).

## M1 checkpoint log

- **B.1 Preflight (2026-10-08).** Canonical checkout
  `~/coco_labs_ws/src/coco-labs`: clean, `origin` = `GauthamCodes/coco-labs`,
  no local-only commits; `main` fast-forwarded `6249e7d` → `9f58b83`
  (contains the PR #19 merge; `coco-lab-v1-final` → `3571169`).
  [`v2/CHECKOUTS.md`](v2/CHECKOUTS.md) written. Overlay `~/coco_labs_ws`
  rebuilt from that checkout; M1 builds its worktree into
  `~/coco_lab_m1_ws`. **Incident:** the session first built into
  `~/coco_m1_ws`, which is the robot project's overlay (`~/coco-isaac-21`);
  with Gautham's approval it was restored the same day by re-running its
  recorded build, and no COCO Lab path remains in it (CHECKOUTS.md).
  **Toolchain:** Node 24.21.0 (`lab_web/.nvmrc`; binary from
  `~/coco_v2_ws/node`), npm lockfile (`npm ci`); Python 3.12.3 test venv
  `~/coco_labs_ws/test_venv` (system site packages: pytest 7.4.4,
  hypothesis 6.98.15, numpy 1.26.4, protobuf 4.21.12; `protoc` 3.21.12);
  Pyodide 314.0.7 (`site.config.ts`; Python 3.14.2 inside, whose lock lists
  protobuf 7.34.1, zstandard 0.25.0, numpy 2.4.6). **M1 baseline** on
  `9f58b83`: packages **3,081 / 0 / 0**, vitest **320 / 0 / 0**, tools
  **117 / 0 / 0**. Next: M1.1.

- **M1.1 `coco_schemas` (2026-10-08).** Transport settled first,
  measured: [ADR 0001](v2/adr/0001-event-transport.md) — Python emits
  columnar typed arrays, TypeScript encodes protobuf for storage
  (Pyodide-in-Node, 258,263 events: columnar 75.3 ms + 8.4 ms;
  protobuf-in-Python 92.2 + 4.4 ms and a 248 KB wheel; JS encode 41.1 ms,
  byte-identical; MODEL, laptop). New package `coco_schemas`: envelope
  (`Manifest`, `run_id`) and the nine families as 15 channels
  `coco.<family>.<name>.v1`, every batch carrying `seq`/`tick`/`t_world`;
  generated Python (protoc 3.21.12) and TypeScript (protoc-gen-es 2.15.0);
  within-major compatibility rules against `compat/v1.binpb`; lossless
  v1-trace converter (all 9 Lab 1 bundles incl. the 3 recorded full-stack
  runs, and 1,000 maps × 5 algorithms, byte-identical canonical JSON);
  MCAP + zstd container (`lab_web/src/schemas/mcap.ts`); Python ↔
  TypeScript byte and `run_id` parity vectors. CI: `coco_schemas` built
  and tested in `ci.yml` *(M1 review correction: built, but `colcon test` collected 0 of its tests until `[M1-fix]` `b3dc8a0`, so the claim was false through M1.10)*, TypeScript generation checked in `lab.yml`.
  Reference: [`v2/SCHEMAS.md`](v2/SCHEMAS.md). Tests: packages
  **3,169 / 0 / 0** (3,081 + 86 `coco_schemas` + 2 `gazebo_models`
  per-package checks), vitest **332 / 0 / 0** (+12), tools **117 / 0 / 0**.
  Stop condition "schemas cannot express a Lab 1 trace without loss": not
  hit. Next: M1.2.

- **M1.2 World Spec v1 (2026-10-08).** `worlds/coco_arena_v1.yaml`,
  generated by `worlds/tools/make_coco_arena_v1.py` from
  `gazebo_models/config/navigation_world.json`, `coco_config/robot.py`,
  `coco_lab/sketch.py`, `coco_web/safety.py` and `nav2_params.yaml` (each
  number from its source; `--check` in tests). `coco_lab/worldspec.py`
  (standard library only): strict v1 validator, canonical bytes (what
  `run_id` hashes), and the Arena generator. Evidence (tests,
  `coco_lab/test/test_worldspec.py`): the Arena world equals the Stack's
  saved map `coco_navigation.pgm` **cell for cell** (500 × 380, same
  resolution and origin), and all 70 boxes equal the Gazebo world's models
  in pose and size — the SDF is designed for, not built. Reference:
  [`v2/WORLD_SPEC.md`](v2/WORLD_SPEC.md). `coco_lab` gains a pinned test
  dependency, `pyyaml==6.0.1` (= apt python3-yaml). The dispatched `Lab`
  CI run on the M1.1 commit caught a stale generated TypeScript file
  (`scan_pb.ts`, a comment edited after generation); regenerated, and the
  local helper now runs the same check. Tests: packages **3,187 / 0 / 0**
  (`coco_lab` 604 → 622; `gazebo_models`' known `TestTheOldLoopIsDetected`
  node-creation flake errored once and passed 25/25 and 231/231 on re-run),
  vitest **332 / 0 / 0**, tools **117 / 0 / 0**. Next: M1.3.

- **M1.3 Arena model core (2026-10-08).** `coco_lab/arena.py`: the
  World Spec's world, Sketch's ray-caster and motion law, fixed
  `dt` = 0.1 s, accel-limited commands, teleop / goal / STOP / planner /
  reset as input events at the start of their tick, the five planners on
  the radius-inflated map, and a per-tick SHA-256 over a documented,
  quantized layout plus a run hash chain. `coco_lab/rng.py`: xoshiro256**
  seeded by SplitMix64, equal to the authors' reference C (gcc 13.3) on
  five seeds. Reference: [`v2/ARENA_MODEL.md`](v2/ARENA_MODEL.md).
  **LiDAR re-confirmed (MODEL vs STACK):** on Lab 2's 237 recorded poses
  the Arena gives **86.73 % of beams within 5 cm — identical to Lab 2**,
  and its ranges equal Lab 2's Sketch ranges on all 113,760 beams (the
  spec-generated world equals the saved map; same caster and LiDAR).
  Evidence: [`v2/data/m1/lidar/arena_lidar_fidelity.json`](v2/data/m1/lidar/arena_lidar_fidelity.json);
  appended to `docs/RESULTS.md`. The dispatched `Lab` CI run on the M1.2
  commit passed (run 37782383206). Tests: packages **3,214 / 0 / 0**
  (`coco_lab` 622 → 649), vitest **332 / 0 / 0**, tools **117 / 0 / 0**.
  Not claimed: native CPython and Pyodide hash equality (different `libm`);
  cross-browser equality is measured in M1.5/M1.10. Next: M1.4.

- **M1.4 Planners emit events (2026-10-08).** First, before
  `search.py` changed: Lab 1's traces frozen on the 1,000-map corpus of
  `test_all_five_agree_on_no_path` (all five algorithms per map, with the
  property's own heuristic, tie-break and weight; 5,000 searches, 1,950
  found) as map parameters plus each trace's sha256 —
  `coco_lab/test/golden_traces_v1.json.gz` (`e801785`), made at a commit
  whose search stack equals the tag `coco-lab-v1-final`. Then
  `coco_lab.search.search_events()`: a generator yielding each push /
  expand / relax / path event as the search makes it (validated at the
  call), with `search()` now its consumer; `coco_lab/events.py` turns rows
  into `SearchEventBatch` columns in batches (ADR 0001). **Golden traces:
  all 5,000 searches reproduce Lab 1 exactly** — same expansion order,
  g/h/f, parents, path, summary (sha256 of the canonical trace), through
  both `search_events` and `search` (`coco_lab/test/test_golden_traces.py`,
  in CI with `coco_lab`'s suite); the emitted columns encode to the same
  protobuf bytes as the converter's (`coco_schemas/test/test_columns.py`).
  D\* Lite's `plan.incremental` (optional) is not done. Tests: packages
  **3,230 / 0 / 0** (`coco_lab` 649 → 663, `coco_schemas` 86 → 88),
  vitest **332 / 0 / 0**, tools **117 / 0 / 0**. Next: M1.5.

- **M1.5 Worker runtime + cold start (2026-10-08).** `?view=arena` (code-
  split from the v1 labs): a Web Worker runs Pyodide + coco_lab +
  `lab_web/src/arena/arena_glue.py`; the Arena streams plan events WHILE it
  plans (`Arena(on_plan_batch=...)`, `coco_lab.search.collect`), posted as
  transferable typed-array batches (ADR 0001), then each tick with its
  ranges. Cold-start work, each measured before/after
  ([`v2/COLDSTART.md`](v2/COLDSTART.md)): Pyodide **self-hosted** from the
  pinned npm package; stdlib **trimmed** to the 142 files the Arena imports
  (2.55 → 0.78 MB, identical hashes); no micropip/wheel (a sha-checked
  `coco_lab.zip`); Arena world rasterised per rectangle (780.7 → 9.8 ms in
  Pyodide, identical output); the worker starts when the page opens.
  Laptop, n = 10, Pages-like gzip: **Arena ready 2,087 ms** (2,055–2,182)
  unthrottled, **3,605** on emulated Wi-Fi, **7,301** on emulated 4G;
  jsDelivr instead: 76,046 / 9,124 ms medians with 11 of 20 runs stalling
  (not attributed). Goal → first plan events 89–104 ms medians. `?perf`
  overlay (stage times, fps, event throughput, step cost) and
  [`v2/PHONE_MEASURE.md`](v2/PHONE_MEASURE.md) for Gautham. Console: 0
  errors in all seven views incl. `arena`, which makes 0 cross-origin
  requests. Appended to `docs/RESULTS.md`. Tests: packages
  **3,232 / 0 / 0**, vitest **336 / 0 / 0** (`arena_runtime.test.ts`: trimmed
  = full stdlib, hash for hash), tools **117 / 0 / 0**. Not yet: first
  VISIBLE computation (needs M1.6), attract-mode recording (M1.8), phone
  numbers (Gautham). Next: M1.6.

- **M1.6 Renderer (2026-10-08).** `lab_web/src/arena/render/`: Three.js
  0.186.0 on WebGL 2, beside React (React draws panels only); orthographic
  top-down with mouse, wheel and touch (pan, pinch) control. Layers:
  occupancy + closed set / expansion heatmap (two data textures, one
  shader), frontier (instanced), path, LiDAR fan (one merged line buffer),
  footprint, COCO's outline from the Gazebo chassis mesh (`base.stl` →
  convex hull at build time), truth as a dashed outline, goal, picked cell.
  Inspector: state, expansion order, g, h, f, parent, latest event, from
  coco_lab's events (`PlanStore`, 5 tests on a real search). Visual system
  v1, light and dark: [`v2/VISUAL_SYSTEM.md`](v2/VISUAL_SYSTEM.md). The
  plan reveals over about 90 frames; a goal steps the model at once. Laptop
  GPU (RTX 4050 via ANGLE/OpenGL ES 3.2, headless Chromium): Arena + 50,000
  points + 20,000 segments at **60–61 fps**, p95 frame 16.9–17.0 ms (10 s);
  on SwiftShader the same load is 1–2 fps, so fps numbers always name the
  renderer (`docs/v2/data/m1/render/`). Screens at 1280 light/dark and 390 px:
  0 console errors, no horizontal overflow, the inspector works
  (`render/shots/`); the `?perf` overlay no longer blocks taps on phones.
  Tests: packages **3,232 / 0 / 0**, vitest **341 / 0 / 0**, tools
  **117 / 0 / 0**. Next: M1.7.

- **M1.7 Timeline (2026-10-08).** `lab_web/src/arena/session.ts`
  (pure, tested): the world track keeps every tick the model reports (pose,
  ranges for the last 12,000, mode, hash, plans) and the computation track
  is the search planned at or before the shown tick, one keyframed
  `PlanStore` per search (a keyframe every 16,384 events). Play / pause /
  speed (0.25–4×) drive the WORLD clock (`frame()` says when a model step is
  due; pausing stops the simulation); history replays then rejoins live.
  `Timeline.tsx`: play, ±1 tick, speed, live, world and computation
  scrubbers, ±1 event. **Seek budget:** on a 380k-event search (Lab 1 arena
  size), every seek < 100 ms and equal to a fresh replay
  (`test/session.test.ts`); in the browser on a real 81,593-event Dijkstra,
  world and computation seeks took ≤ 2 ms
  (`docs/v2/data/m1/timeline/timeline_check.json` + screenshots).
  Tests: packages **3,232 / 0 / 0**, vitest **347 / 0 / 0** (+6), tools
  **117 / 0 / 0**. Next: M1.8.

- **M1.8 Experience (2026-10-08).** `?view=arena` now opens on a
  **recording** (attract mode): `tools/build_attract.mjs` runs the real
  coco_lab + `arena_glue.py` in Pyodide-in-Node at build time (three goals,
  astar / dijkstra / greedy) and writes `generated/arena/attract.mcap` with
  the site's own protobuf encoders (the first v2-container file the page
  reads; 688,717 B, byte-identical across two builds, sha256 d3d18d8e…). It plays while
  Pyodide loads, labelled a MODEL recording; the first click, key, joystick
  move or planner choice hands over to the live model. Also: keyboard teleop
  (W A S D / arrows, space = STOP), an on-screen joystick (mouse, pen,
  touch), side-by-side **compare** of two planners on the same map, start,
  goal and seed (the worker's `compare` changes no model state: same hash
  chain after, tested), an end-of-run card with expansions / path cost /
  path length and the heatmap switched on, and a **share link**
  (`?run=`: spec sha256, seed, input log, final tick and hash chain) that
  replays the run and says whether the chain matched, rather than claiming
  it. `WorldGrid` gained an additive `occupancy` field (11).
  **Browser check** (`tools/perf/experience_check.mjs`, Chromium + GPU,
  0 console errors, all 9 steps pass; `docs/v2/data/m1/experience/`):
  attract moving at 674 ms, first computation shown at 961 ms (live model
  not yet ready); click → live → arrival with totals; W held 1.2 s moved
  0.39 m; joystick drag moved 0.52 m; compare astar 3,904 vs bfs 37,324
  expansions, both path cost 175.18; a shared link replayed to the **same
  chain** at tick 404; a Pixel 7 tap gave a goal with no horizontal scroll.
  Fixed on the way: compare captured the planners chosen at first render,
  and side A's id (−1) collided with an empty PlanStore's; the phone stage
  letterboxed. Tests: packages **3,232 / 0 / 0**, vitest **357 / 0 / 0**
  (+10), tools **117 / 0 / 0**. Next: M1.9.

- **M1.9 Converters (2026-10-09).** All eleven Lab 1 bundles the site
  serves — the five teaching traces, the three arena/costmap traces and
  the **three recorded full-stack runs** (Phase 1C) — convert to v2 run
  files (`lab_web/src/convert/lab1.ts`; built by
  `tools/build_v2_runs.mjs` into `generated/v2/`) and play in the Arena
  viewer at `?view=arena&replay=<id>`, with the timeline and inspector.
  Recorded runs are labelled **STACK** (`TIER_STACK`): the robot is drawn
  where the stack believed it was (AMCL) with ground truth beside it,
  0.1 s of sim time per tick, the search at FollowPath acceptance, the
  arbiter / collision-monitor annotations on the timeline, and the run's
  measured results quoted from the bundle (never recomputed). Traces are
  MODEL (`TIER_TRACE`). No model worker starts for a replay. The old Lab 1
  view is unchanged and still reads the v1 bundles.
  **Lossless, checked strictly:** the v1 arrays are rebuilt from the v2
  CHANNELS alone and the v1 decoder must accept them with the original
  content hash — at every build (a failure stops the build) and in
  `test/convert_lab1.test.ts` (11/11; one flipped ground-truth bit is
  caught; byte-deterministic). Schema: new additive
  `coco.plan.path.poses.v1` / `PathBatch` for the stack's published
  `/lab/plan` (SCHEMAS.md, "Whole bundles"). **Browser check**
  (`tools/perf/replay_check.mjs`; `docs/v2/data/m1/replay/`): 3 STACK runs
  played to the end (760 / 777 / 670 ticks) and 2 traces (incl. the
  283,378-event arena benchmark) fully revealed, first frame 223–539 ms,
  0 workers, 0 console errors; all seven views 0 console errors
  (`console_check.json`). Tests: packages **3,235 / 0 / 0** (the first
  run had 2 `gazebo_models` live-graph tests error with rclpy
  `RCLError: error creating node`; M1.9 touches no ROS package and the
  re-run passed 231 / 0), vitest **374 / 0 / 0** (+17), tools
  **117 / 0 / 0**. Next: M1.10.

- **M1.10 Measure and decide (2026-10-09).** Every B.4 budget measured on
  the final build, laptop in its **power-saver** profile (recorded; M1.5's
  was not, so M1.5 → M1.10 timings are not a controlled comparison). Full
  table: [`v2/M1_RESULTS.md`](v2/M1_RESULTS.md); decision:
  [`v2/adr/0002-wasm-gate.md`](v2/adr/0002-wasm-gate.md) — **port nothing**.
  - **Determinism — met:** 100 recorded sessions (random goals, teleop,
    stops, planner switches) × 150 ticks in Chromium 156, Firefox 157,
    WebKit 27.2 (the site's own worker) and Pyodide-in-Node: 15,000 ticks
    each, **0 differing** (`v2/data/m1/determinism/`). WebKit runs here
    without sudo via `~/coco_lab_m1_ws/bin/webkit_run.sh` (four media
    libraries unpacked privately; nothing system-wide changed).
  - **Correctness — met:** 5,000/5,000 golden searches (1,000 maps).
  - **Laptop performance — met:** 60–61 fps, 50k points + 20k segments.
  - **Responsiveness — met:** warm goal click → first frame drawing that
    goal's search: median **40.4 ms**, max 71.5, 25/25 under 100; seek
    ≤ 0.6 ms. Two bugs found and fixed first: the timer stopped on the
    previous search (earlier "47–73 ms" timed first goals only), and the
    session hid a streaming search until it finished (honest measurement
    before the fix: median 414 ms, p95 2,690 ms). A vitest pins the fix.
  - **Laptop cold start — met for the first visible computation:** 754 /
    1,629 / 3,299 ms (unthrottled / emulated Wi-Fi / 4G, n = 10 each,
    self-hosted); live model ready 5,023 / 6,603 / **10,782** ms (4G over
    10 s). M0 baseline: 12,857 ms.
  - **Hygiene — met:** 0 console errors in all seven views and every
    harness; phone width checked; CI gains a `lab-web-browsers` job
    (determinism in 3 browsers, 5 screenshot scenes with a self-test) and
    a determinism vitest.
  - **Pending Gautham:** phone performance, phone cold start, usability.
  - Also: the `?perf` panel's stale "first frontier node shown" row
    replaced; landing route checked 9/9 (`v2/data/m1/landing/`); two
    findings parked for M2 (`docs/IDEAS.md`): a goal right after a planner
    change waits for the re-plan (median 293 ms, max 4.0 s); attract mode
    costs the live model's load 155–575 ms.
  - Tests: packages **3,235 / 0 / 0**, vitest **381 / 0 / 0** (+7), tools
    **117 / 0 / 0**.
  - **CI** (Lab run 37850645657 on `1abe73f`, all jobs green): the new
    browser job replayed 10 recorded sessions (1,500 ticks each) in
    Chromium, Firefox and WebKit on GitHub's runner — **0 mismatched**
    against the committed Pyodide-in-Node hashes — and all 5 screenshot
    scenes matched the laptop-made baselines **pixel for pixel** (self-test:
    two different scenes differ by 3.1 % of pixels, so the check can fail).
  - The re-runs on the final build replaced `v2/data/m1/timeline/`,
    `experience/` and `replay/`'s files in place; the files the M1.7–M1.9
    entries above quote are in git at `0f90e35` (M1.9) and its parents.

- **M1 independent review (2026-10-09, README §9.9).** A fresh session that
  did not build M1 reviewed PR #20 from a fresh clone (`~/review/coco-labs-m1`,
  head `4e06942`); report: [`v2/reviews/M1_REVIEW.md`](v2/reviews/M1_REVIEW.md).
  Verified: no deleted files, RESULTS.md append-only, suites 3,235 / 381 /
  117, golden traces 5,000/5,000, determinism re-run (25 sessions × 4
  engines, 0 mismatched, 0 against the committed hashes), both schema
  changes backward-compatible (an M1.1 reader parses M1.10 bytes), the
  responsiveness fix pinned by a test that fails without it, 0 console
  errors in all seven views, 14/14 URL forms. **Found:** CI's
  `build-and-test` failed on PR #20 — `coco_schemas` collected 0 tests
  under `colcon test` — so M1's "schema tests in CI" was false; fixed under
  a one-off owner permission (plan-change log). Overstated: "a new Pyodide
  in Node" per determinism session; "every v1 link 9/9" (3 of the 9 are
  Arena URLs). M1 budgets re-measured in the **balanced** profile on AC
  (owner's standard): warm goal → frontier median 42.9 ms; first visible
  computation 631 / 1,366 / 3,381 ms; live model ready 2,683 / 4,061 /
  8,191 ms (desktop / fast-4G / emulated 4G); power-saver rows kept
  (`v2/M1_RESULTS.md`, `docs/RESULTS.md`). `[M1-fix]` commits:
  `setup_webkit_libs.sh`, power state in every harness, `LANDING=arena|v1`,
  the plan-change log, the `coco_schemas` CI fix, this evidence.

## M2 checkpoint log

- **Part A closed (2026-10-09).** M1 reviewed, fixed and merged — see the
  M1 review entry above and the Position table. Public site check after
  the deploy (Chromium, headless): the bare URL opens the Arena, the live
  model became ready at 11.6 s over the real internet (the laptop was
  running the M2 baseline suites at the time; not a budget measurement), a
  real click at (6.0, 4.0) produced that goal's search, drawn 90.7 ms after
  the click; plan, live, localise, map, search and move open v1 with 0
  console errors, 0 page errors, 0 cross-origin requests
  ([`v2/data/m1/exit/public_after_merge.json`](v2/data/m1/exit/public_after_merge.json),
  harness `lab_web/tools/perf/public_check.mjs`).
- **B.1 Preflight (2026-10-09).** Canonical checkout clean, no local-only
  commits; `main` fast-forwarded `9f58b83` → `0a2516a`; branch
  `v2/m2-whole-loop` in worktree `.claude/worktrees/v2-m2-whole-loop`;
  overlay `~/coco_lab_m2_ws` (new; `ls -d` first). Part B of the prompt
  saved as [`v2/M2_PROMPT.md`](v2/M2_PROMPT.md). No phone results are
  recorded here by Gautham, so no M2.0b. **M2 baseline** on `0a2516a`:
  packages **3,235 / 0 / 0**, vitest **385 / 0 / 0**, build tools
  **134 / 0 / 0** (the run read 135: it included one parametrised case for
  the then-uncommitted `public_check.mjs`). Toolchain: Node 24.21.0,
  Python 3.12.3, pytest 7.4.4, hypothesis 6.98.15, numpy 1.26.4, protobuf
  4.21.12, protoc 3.21.12, Pyodide 314.0.7, ROS 2 Jazzy. Power state at
  the baseline: **power-saver, on battery** (AC unplugged, 66 %), load
  4.4 — tests only; no budget was measured in it
  (`~/coco_lab_m2_ws/logs/baseline_env.txt`). Next: M2.0.

- **M2.0 Carry-overs (2026-10-09).** Evidence: `v2/data/m2/m20/`.
  - **Cancellable planning (MODEL).** A tick's inputs are applied first and
    the tick plans once, on the state they leave; a step runs in slices,
    and an input that arrives while a step plans joins its tick (`amend`),
    cancelling the search in flight. The worker yields between slices of
    4,096 events, so the page's input lands within about a slice. M1's
    hash layout is unchanged: M1's 100 recorded sessions give **0
    differing** hashes old vs new (native, 15,000 ticks) and whole vs
    sliced-and-amended (916 ticks amended) (`arena_equivalence.json`), and
    Pyodide-in-Node reproduces M1's committed hashes **15,000 / 15,000**
    (`pyodide_vs_m1_hashes.json`). Measured (balanced, AC, GPU, real
    clicks, n = 25): **goal right after a planner change median 35.2 ms,
    p95 64.2, max 65.5, 25/25 under 100 ms** (target ≤ 100 / ≤ 500; M1:
    293 / 4,029 power-saver, 138.6 / 1,708 balanced); warm goals median
    40.7, max 58.5 — no regression (`responsiveness/`).
  - **Attract mode vs the live model (measured, n = 10, desktop / emulated
    4G):** `eager` first visible computation 610 / 3,371 ms, live model
    ready 2,597 / 8,130; `low` (low-priority fetch) 619 / 3,142 and
    2,608 / **7,895**; `after_pyodide` live ready 2,318 / 7,463 but first
    computation 1,995 / ~7,860 (only 2 of 10 4G runs recorded it);
    `after_live` live ready 2,332 / 7,486, first computation not
    measurable (the harness's goal takes over first). **Default: `low`**
    — the literal "delay until the live model has loaded" (`after_live`)
    saves ~640 ms of live-model-ready on 4G but moves the first visible
    computation to the live model's own (~7.5 s), and README §5.5 (the
    authority) has attract mode play *while* Pyodide loads (deviation,
    recorded). `coldstart/m20_*`.
  - **Live model ready ≤ 10 s on emulated 4G (Plan lens):** met, 7,895 ms
    with the default (balanced, AC).
  - **Every harness records power state:** done in the M1 review
    (`[M1-fix]` `2ad8ecf`).
  - **Lens modules lazy-loaded within 3 s of selection:** the lenses do
    not exist yet; the split loader comes with the lens registry (M2.2)
    and is measured in M2.11.
  - Tests: packages: `coco_lab` 665 → 670 (5 new arena tests); vitest
    385 / 0 / 0; tools 135 / 0 / 0.

- **M2.1 Schemas (2026-10-09).** Ten families, 26 channels, added within
  v1 (`coco_schemas/proto/coco/{estimate,localise,map,control,decide,
  mission,arm}/v1`, `sensor/v1/detect.proto`): estimate; localise.particles
  and localise.ekf; map.grid and map.slam; control.local (candidates,
  per-critic scores, rejection reasons, chosen command); decide.search
  (belief, expected cost per order, action, observation); mission.fsm;
  sensor.detect (abstract, detection probability with its label); arm
  (joints, two fingers, magnet, holding). All flat (repeated scalar
  columns + per-batch scalars), so `coco_lab/columns.py` declares each as
  a table without protobuf. Evidence: `test_compat.py` passes against the
  unchanged M1.1 baseline (additive); `test_columns_m2.py` holds every
  table to its descriptor and round-trips it; TypeScript's `encodeBatch`
  reproduces Python protobuf's bytes for all 18 batch messages
  (`coco_schemas/test/vectors/m2_batches.json`,
  `lab_web/test/schemas_m2.test.ts`, 19 tests). Reference:
  [`v2/SCHEMAS.md`](v2/SCHEMAS.md), "The whole loop's families". Tests:
  `coco_schemas` 91 → **209 / 0 / 0**. Next: M2.2 (lens framework).

- **M2.2 Lens framework (2026-10-09).** `lab_web/src/arena/lens/`:
  a registry of five lenses (Plan, Localise, Map, Move, Decide), each
  with its families, layers (role: computation / uncertainty / world;
  a palette colour; the level it appears at), Inspect charts and Python
  pack; a lens bar (lens tabs, **Watch / Explain / Inspect**, **Focus**);
  Explain: value labels under the mouse (per-lens hover functions; Plan's
  from the shown search) and captions at key events; Inspect: one
  inspector template per family, an event log and metric charts (charts
  only at Inspect or when a mission asks). A family store files every
  batch the model emits by channel and tick (timeline-seekable); the
  worker carries family batches (numeric columns transferred, strings and
  bools as JSON) and static headers. Drawing primitives
  (`render/lensLayers.ts`): instanced points, poses, translucent ellipses
  (an opaque one is refused), coloured line sets, polygons, a log-odds
  texture; Focus dims everything outside the lens (the robot and truth
  never). Palette and [`v2/VISUAL_SYSTEM.md`](v2/VISUAL_SYSTEM.md): a
  fixed colour per new layer, uncertainty translucent, truth an outline.
  Recorded runs open at Explain (their closed set is the content); the
  live arena at Watch. **Lazy Python packs** (the M2.0 carry-over):
  `coco_lab.zip` (core, Plan) 191 → **93 KB**; localise 22 KB, map 53 KB
  (requires localise), move 12 KB, decide 16 KB
  (`lab_web/tools/arena_packs.json`; the build refuses a cross-pack
  import); the trimmed stdlib gains `datetime` and `gzip` (+7.6 KB),
  which the packs need (`stdlib_usage.mjs` now imports every module any
  coco_lab source names). Measured in Chromium (unthrottled, laptop,
  power-saver at the time — not a budget run): a lens's pack ready
  **359–569 ms** after its selection, cold or warm cache (target ≤ 3 s;
  re-measured in M2.11); Watch shows ≤ 2 computation layers in every
  lens; hover label read on screen; Pixel 7: no horizontal scroll; 0
  console errors (`v2/data/m2/m22/lens_check.json`, screenshots); all
  seven views 0 console errors (`m22/console/`); the 5 CI screenshot
  scenes still match M1's baselines pixel for pixel. Tests:
  `lens_registry.test.ts` (9: the rules above), `arena_packs.test.ts` (3:
  every module of every pack imports in Pyodide on the trimmed stdlib).
  The lenses other than Plan show "arrives in M2.x" until their
  checkpoint lands. Suites: vitest **416 / 0 / 0** (385 + 19 + 9 + 3),
  build tools **136 / 0 / 0**; the browser-side algorithm guard
  (`test_tools.py`) holds (a drawing method named like a mapping step was
  renamed). Next: M2.3 (Localise lens).

- **M2.3 Localise lens (2026-10-09).** Evidence: `v2/data/m2/m23/`.
  - **The whole loop's core (MODEL, `coco_lab/arena.py`):** two input
    kinds, `kidnap` and `config` (`key=value`; additive in
    `coco.input.v1`, enum 6 and 7; share links append them, M1 links
    decode unchanged). From the first one: wheel odometry (Sketch's
    motion-model noise), the labelled **wheel-slip option**, and
    subsystems registered by their packs; the planner and the driver use
    the **belief**, never the truth. Without a loop input the state is
    M1's exactly. Documented in [`v2/ARENA_MODEL.md`](v2/ARENA_MODEL.md)
    "The whole loop", with the loop section of the hash layout.
  - **MCL and EKF, step-wise:** `localise.MCL` / `localise.EKF` are Lab 2's
    filters one update at a time; `run_mcl` / `run_ekf` now consume them —
    Lab 2's golden bundles and tests pass unchanged. `coco_lab/loc_arena.py`
    (localise pack) runs them in the Arena on the same odometry and scans
    (MCL and EKF on identical inputs), emitting particle sets, MCL's
    bookkeeping, the EKF's predict/update, every estimator's pose (MCL,
    EKF, dead reckoning) and the errors against the model's truth.
    A test replays the Arena's MCL inputs into a standalone `MCL` and gets
    the same estimates, draw for draw.
  - **Lens (browser):** particles (translucent, size by weight), estimates
    with 95 % ellipses, dead reckoning; controls for filter, particle
    count, injection, motion and sensor noise, slip (all `config` inputs,
    so they are in the run's log); **kidnap by dragging the robot**; error
    series at Inspect (`err_xy.mcl|ekf|odometry`, `n_eff`). Browser check
    (Chromium, `browser/localise_check.json`): the pack loads, the
    families stream, a drag kidnaps the robot exactly where it was dropped
    (error 0.06 → 4.45 m, injection off), 0 console errors. (Fixed on the
    way: a drag also panned the map, so the kidnap landed elsewhere.)
  - **Kidnapping, reproduced with the new engine (MODEL):** Lab 2's
    `sketch_rates.py`, now running on the step-wise MCL, gives **every
    per-seed result identical** to the committed Lab 2 file — kidnap off
    **0/20**, augmented **18/20**, fixed 13/20, EKF never; global 9/20;
    arena kidnap 0/20 vs 2/20 (`sketch_rates_new_engine.json`).
  - **New, closed loop (MODEL):** the same kind of kidnap in the Arena,
    where the robot drives on its belief: **0/20 recovered with injection
    off and 0/20 with augmented** (500 particles, 70 s); the lost robot
    drove into walls in 19/20 and 17/20 runs, and a stopped robot gives
    MCL no more updates (`arena_kidnap.json`). Lab 2's 18/20 was open
    loop (its Sketch driver followed the TRUE pose), in a teaching room;
    the difference is the loop, not the filter.
  - **Wheel slip vs the recorded Gazebo drives (MODEL vs STACK):** with
    slip on, the model's wheel odometry ends 17.14 m / 3.14 rad from its
    truth on tour 1 (Gazebo: 17.24 m / 2.69 rad) and 2.10 m / 3.05 rad on
    the square (Gazebo 2.30 / 2.45), and the model's truth ends 0.26 m
    from Gazebo's on the square (2.08 m with slip off) — but on tour 2
    (Gazebo 2.60 m) it ends 16.3 m off and its truth 17.0 m from
    Gazebo's (1.8 m off). Gazebo's two tours drifted 17.2 m and 2.6 m:
    no single ratio fits both. **Slip stays OFF by default**
    (`slip_fidelity.json`).
  - **Determinism:** 10 whole-loop sessions (range noise, MCL/EKF/both
    with random knobs, slip, 7 kidnaps) × 150 ticks in Pyodide-in-Node,
    Chromium, Firefox and WebKit: **1,500 ticks each, 0 mismatched**
    (`determinism_loop/`); the harness gained `make --loop 1` and loads
    every pack.
  - Tests: packages **3,371 / 0 / 0** (corrected at M2.6 from 3,375, a sum slip; `coco_lab` 670 → 681:
    `test_loc_arena.py` 11; `coco_schemas` 209 → 211), vitest **417 / 0 / 0**,
    build tools **137 / 0 / 0**. Next: M2.4 (Map lens).

- **M2.4 Map lens (2026-10-09).** Evidence: `v2/data/m2/m24/`.
  - **Lab 3's algorithms, step-wise and live (MODEL):** `fastslam.FastSlam`
    and `posegraph.PoseGraph` are Lab 3's SLAMs one update at a time;
    `run_fastslam` / `run_pose_graph` now consume them (Lab 3's tests and
    bundles pass unchanged). `coco_lab/map_arena.py` (map pack) runs
    occupancy mapping (from true poses, dead reckoning or the belief),
    EKF-SLAM, FastSLAM and the pose graph in the Arena on its odometry and
    LiDAR at Lab 3's update rule, on a 0.10 m grid; `config` keys
    `map.algorithm|poses|fastslam.particles|pose_graph.loop_closure`.
    Tests: known-pose mapping gives the grid Lab 3's `OccupancyGrid` gives
    on the same scans; FastSLAM gives the standalone class's estimates draw
    for draw. Documented in [`v2/ARENA_MODEL.md`](v2/ARENA_MODEL.md) "The
    map subsystem", with its hash section.
  - **EKF-SLAM's landmark sensor is labelled IDEALISED** in the data
    (`coco.map.slam.header.v1` `sensor_label`: "... COCO has none") and on
    screen (controls and hover).
  - **Loop closure before and after:** at each closure the graph goes out
    twice, `raw` and `optimised`, each with its χ² (tested: after ≤
    before); the lens keeps the last closure's before-graph, faint.
  - **ATE and F1** (`mapeval`, as Lab 3 scores) every 10 updates, as
    metrics charted at Inspect.
  - **The map-the-arena scenario in the new engine (MODEL;
    `map_arena_scenario.json`):** Lab 3's scenario (start, six waypoints,
    seed 21, alphas 0.02, range σ 0.02 m) through Lab 3's engine and
    through the Arena. Lab 3 → Arena: known poses F1 **0.694 → 0.755**;
    dead reckoning ATE 1.795 → 0.708 m, F1 0.236 → 0.208; FastSLAM ATE
    0.380 → 0.190 m, F1 0.427 → 0.374; pose graph ATE **1.722 → 0.119 m**,
    F1 **0.218 → 0.642** (3 loop closures in the Arena run). The engines do
    not drive the same path — Sketch drives straight lines by the TRUE
    pose, the Arena plans each leg and drives it by its belief — so these
    are side by side, not expected equal; the pose graph's difference is
    **not attributed** (Lab 3's closure count on this drive was not
    extracted). The Arena scores F1 without moving the map by the ATE
    alignment; Lab 3 moves it.
  - **Lens (browser, `browser/map_check.json`):** the built map (log-odds,
    unknown veiled so the world shows faintly beneath), the SLAM
    trajectory, landmarks with 95 % ellipses, FastSLAM particles, the pose
    graph with loop edges in their own colour and the before-graph;
    controls as `config` inputs. Chromium: the map's header arrived
    877 ms after selecting the lens (power-saver, battery); a 2 m square driven by clicks closed
    **3 loops**, drawn before and after; EKF-SLAM's IDEALISED label
    visible; **0 console errors, 0 three.js warnings**.
  - **Two renderer defects found and fixed on the way.** (1) M1's planned
    path line was updated with `setFromPoints` on a reused geometry, which
    in three r186 only overwrites in place: **every replanned path after
    the first was drawn cut to the first path's length or with its old
    tail** (three.js warned; nothing failed). Now a new geometry each time
    (`setLinePoints`, tested, including a test that the old way truncates).
    (2) `LensLayers.applyOpacity` reset `transparent` from opacity alone,
    so a texture's own alpha was ignored and the built map drew unknown
    cells opaque black over the whole world (tested).
  - **Determinism with mapping on:** 10 sessions × 150 ticks
    (`determinism.mjs make --loop 1 --map 1`; every algorithm drawn: pose
    graph 4, EKF-SLAM 3, occupancy 2, FastSLAM 1) × Pyodide-in-Node,
    Chromium, Firefox, WebKit: **0 mismatched of 1,500 ticks each**
    (`determinism_map/`); native CPython 3.12.3 against the Pyodide hashes:
    **0 of 1,500** (`determinism_map/cpython.json`).
  - Tests: packages **3,387 / 0 / 0** (corrected at M2.6 from 3,391; `coco_lab` 681 → 697:
    `test_map_arena.py` 16), vitest **424 / 0 / 0** (+7: `lens_layers`,
    `renderer_path`), build tools **138 / 0 / 0**. (The first vitest run
    failed `site.test.ts` on a `__pycache__` the CPython check wrote under
    `lab_web/src`; removed, and the check no longer writes bytecode.) Next:
    M2.5 (Move lens).

- **M2.5 Move lens (2026-10-09).** Evidence: `v2/data/m2/m25/`; write-up
  [`v2/M2_MOVE_COMPARISON.md`](v2/M2_MOVE_COMPARISON.md).
  - **Three teaching controllers (MODEL, `coco_lab/control.py`):** a DWA
    sampler after DWB (DWB's critics and scales; 11 × 21 samples, not 819),
    regulated pure pursuit (Lab 5's RPP parameters, collision detection on
    the arc), a small MPPI (Lab 5's horizon, noise, temperature and critic
    weights; 128 samples, not 2,000). Each sees a 3 × 3 m local window at
    0.05 m around the BELIEVED pose, marked from the current scan and
    inflated as the mission's local costmap is (inscribed 0.255 m, tested),
    and emits `control.local` with per-critic scores and rejection reasons.
    Every simplification is listed in the module docstring.
  - **The move subsystem (`coco_lab/move_arena.py`, move pack):**
    `move.controller|scenario|belief_offset`; Nav2's FollowPath outcomes
    and codes (103/104/105). Three additive core hooks in `arena.py`
    (`command`, `discs`, `world_step`); with none provided every existing
    hash is unchanged. **Arena actors have collision bodies** (the LiDAR
    sees them, the robot cannot drive into one, an actor waits for the
    robot), unlike Lab 5's visual-only Gazebo actors; said wherever the two
    are compared.
  - **Lab 5's scenarios rebuilt from their definitions:**
    `coco_lab/move_scenarios.py`, generated from `coco_lab_ros/config/`
    (the frozen paths and `lab5_scenarios.json`), pinned to them by a test.
  - **Model vs STACK (`move_comparison.json`, 5 seeds × 3 controllers × 4
    scenarios; Lab 5's metrics code and obstacles):** the outcome and code
    agree in **9 of 9** cells of the hairpin, the crossing and run 15 —
    including DWB's hairpin failure (DWA: 5 × 105, DWB: 5 × 105), a
    coincidence of outcome whose mechanism was not examined. The head-on
    scenario **differs**: the model's DWA and MPPI fail (104) where the
    stack's DWB and MPPI "succeeded" by passing through the person (contact
    5/5 each); RPP fails (104) in both. The model tracks tighter (0.020–
    0.043 m vs 0.049–0.143 m) and its MPPI is slower (86 vs 52 s on the
    hairpin); neither gap is attributed.
  - **Run 15 in the model (MODEL; STACK 9/9 beside it):** belief 3.4 m
    north of the truth; the whole path outside the window around the
    belief; every controller fails INVALID_PATH in its first cycle with 0
    candidates, 15 of 15 runs (Lab 5: 9 of 9, code 103, 0 of 0 candidates).
  - **Lens (browser, `browser/move_check.json`, Chromium):** candidates
    shaded by cost, rejected ones, the chosen trajectory, the lookahead,
    the local window, the given path, the actors' bodies; controller and
    scenario pickers as `config` inputs. Run 15 from the picker for each
    controller: one `invalid_path` cycle with 0 candidates, belief–truth
    gap 3.4 m; the crossing with DWA succeeded with candidates, the chosen
    trajectory and the actor drawn; 0 console errors, 0 three.js warnings.
  - **Cost per tick (CPython, crossing):** DWA 23.6 ms, RPP 12.7 ms, MPPI
    32.5 ms (MPPI's normals now come two per 64-bit draw; it was 50.5 ms),
    of which the M1 scan is about 10 ms. Browser budgets: M2.11.
  - **Determinism with local control on:** 10 sessions (every controller
    and scenario drawn) × Pyodide-in-Node, Chromium, Firefox, WebKit:
    **0 of 1,500 ticks mismatched each**; CPython vs Pyodide **0 of 1,500**
    (`determinism_move/`).
  - Tests: packages **3,409 / 0 / 0** (corrected at M2.6 from 3,413; `coco_lab` 697 → 719:
    `test_move_arena.py` 22), vitest **424 / 0 / 0**, build tools
    **139 / 0 / 0**. Next: M2.6 (Decide lens and the fetch mission).

- **M2.6 Decide lens and the fetch mission (2026-10-09).** Evidence:
  `v2/data/m2/m26/`. Documented in [`v2/ARENA_MODEL.md`](v2/ARENA_MODEL.md)
  "The mission subsystem".
  - **The fetch (MODEL, `coco_lab/mission_arena.py`, decide pack):**
    localise → choose a bay → plan → local control → detect → grasp →
    return, each step done by the pack that owns it (`mission.fsm`
    transitions carry the event and the reason in words).
  - **Lab 4's Bayesian bay search:** the problem is Lab 4's exactly
    (`coco_lab/fetch_problem.py`, generated from
    `build_search.arena_problem()`; a tools test pins it); uniform prior,
    **d = 0.9 labelled ASSUMPTION** in the data and on screen, Bayes on a
    miss, the expected cost of every order of the bays left and the chosen
    bay at each decision (tested against `regionsearch` choice by choice).
  - **`sensor.detect`:** abstract colour detection from the bay the robot
    is TRULY at (within 0.6 m of its pre-ramp pose), never a false
    positive, at the world's rate `mission.detect` (default 0.9). Across
    the matrix below, looks at the true bay found the target 30 times and
    missed 4.
  - **The arm (`coco_lab/arm.py`):** `arm_ik.py`'s geometry (a test pins
    every constant), `pick_place.py`'s verified joint poses interpolated;
    two fingers and a magnet, **the magnet holds**. Side-view inset drawn
    from the model's batches (`coco.arm.v1` gained `elbow_x`/`elbow_z`,
    fields 13–14, additive; the page computes no kinematics).
  - **SIMPLIFIED, said on screen:** the Arena is flat, so the ramp climb is
    not modelled; survey and grasp happen at the pre-ramp pose. Recovery
    after a controller gives up: back up 0.30 m and re-plan, at most 3 —
    after Nav2's BackUp, without its costmap clearing, spin or wait.
  - **Core:** `arena.plan_clearance` (hashed only when set) — the mission and
    the local controllers plan at 0.40 m, because M1's 0.22 m paths left no
    margin (measured: DWA refused its first leg; a 0.19 m MCL error put the
    robot against a box); `Arena.request_goal`; the localiser's
    `quality()`.
  - **Fetch matrix (MODEL, `fetch_matrix.json`, 4 colours × 2 seeds):**
    no localiser **6/8**, MCL **8/8**, MCL + RPP **4/8**, MCL + MPPI
    **7/8**, MCL + DWA **4/8**. Every "target not found" (4) is the camera
    missing the true bay at d < 1; every MCL + RPP/DWA navigation failure
    (7) is NO_VALID_CONTROL on the leg after Bay 4, where three backups did
    not help — **not attributed**. RPP needed 34 recoveries across its 8
    runs. Not a rate for the robot.
  - **Whole-loop visibility (MODEL):** told it is 4 m south of the truth,
    the robot drives to where it believes Bay 3 is; the camera sees Bay 4;
    the miss is booked against Bay 3 (P 0.25 → 0.03), then it drives into
    what it believed was clear and the leg fails (no progress) — 3 of 4
    colours; yellow, whose target IS in Bay 4, was fetched. Tested, and
    seen in the browser with the true error (4.00 m) shown beside the
    robot's own view.
  - **Lens (browser, `browser/mission_check.json`, Chromium):** bays filled
    by belief, the chosen bay, every look; the mission panel (state and
    reason, the belief table with d's label, true error vs the robot's
    σ, the arm inset); controls as `config` inputs, a config for a pack not
    yet loaded now waits for it. A red fetch with the target in Bay 3:
    localise → … → done, `fetch`, the inset "magnet on, holding the
    target"; then the 4 m mislocalisation: the miss booked against Bay 3
    while the camera saw Bay 4. 0 console errors, 0 three.js warnings.
  - **Determinism with the mission:** 10 sessions × 300 ticks × 4 engines,
    **0 of 3,000 ticks mismatched each**; CPython vs Pyodide **0 of 3,000**
    (`determinism_mission/`). (The session generator's kidnap spot
    (12, 5.5) lay inside a box; replaced by (10, 3). No committed session
    had drawn it — checked.)
  - Tests: packages **3,425 / 0 / 0** (`coco_lab` 719 → 735:
    `test_mission_arena.py`), vitest **424 / 0 / 0**, build tools
    **142 / 0 / 0** (+3: `test_fetch_problem.py` 2, the conditions check
    of `mission_check.mjs` 1). The package totals recorded at M2.3, M2.4
    and M2.5 were each 4 too high (a sum slip; the per-package counts were
    right) — corrected above, re-added from the logs. Next: M2.7
    (converters).

- **M2.7 Converters (2026-10-09).** Evidence: `v2/data/m2/m27/`; documented
  in [`v2/SCHEMAS.md`](v2/SCHEMAS.md) "Labs 2–5, without loss".
  - **Labs 2–5 convert losslessly into the whole loop's families**
    (`lab_web/src/convert/lab2.ts`, `lab3.ts`, `lab4.ts`, `lab5.ts`,
    `lab5replan.ts`): every array rebuilt from the CHANNELS alone and
    accepted by the lab's own v1 decoder, which re-checks the content hash;
    an unknown array is refused, never dropped; every channel is the
    registry's (tested). Round trips, all exact: Lab 2's 5 bundles, Lab 3's 5
    (the recorded tour as STACK, its slam_toolbox / Cartographer runs
    labelled STACK, coco_lab's MODEL), Lab 4's 2, Lab 5's 4 drive bundles
    (54 runs, one v2 run per drive) and 4 replanning bundles.
  - **The 16 searches recorded on the full stack replay byte for byte
    through the new pipeline** (hard requirement): converted to
    `p05_matrix.mcap` (the vitest test requires that exact file), then
    `coco_schemas/test/test_search_replay_v2.py` takes each search's looks
    off the CONVERTED observation channel alone, `replay_search` chooses
    every bay again, and the re-encoded channels equal the file's messages
    byte for byte — 16 of 16; one flipped look is caught.
  - **Lab 5's Nav2 candidate overlays play as STACK**: the build converts
    every drive, drawn on Nav2's saved map, into `generated/v2/lab5_*.mcap`
    (54 runs, listed in the viewer); `?view=arena&replay=<id>` plays it
    through the Move lens — Nav2's own candidates and chosen trajectory,
    nothing computed, Lab 5's measured outcome on the card. Browser check
    (`browser/stack_drive_check.json`, Chromium, `lab5_static_room_dwb_1`):
    header STACK, Nav2's candidates and its chosen trajectory drawn, the
    card "follow_failed (code 105) · tracking error mean 0.141 m", 0
    console errors, 0 three.js warnings.
  - **Additive schema changes within v1** (no renumbering, nothing removed):
    `coco.truth.actors.v1` (`ActorPoseBatch`), D* Lite's event kinds and
    `rhs` / `round`, `ScanBatch.ranges_f64`, `MapGridSnapshotBatch.cells_u8`.
    `test_columns.py` now names the two D*-only fields A*'s emitter never
    fills.
  - The other converted runs (Labs 2, 3, 4 and Lab 5's replanning) are
    verified by tests and not yet served: their lenses replay them at M2.8
    / M2.10 or the v1 links forward to `/v1/`.
  - Tests: packages **3,432 / 0 / 0** (`coco_schemas` 211 → 218:
    `test_search_replay_v2.py` 4, the new channel and the D*-only field
    check), vitest **450 / 0 / 0** (+26: the five converter test files),
    build tools **143 / 0 / 0** (+1: the conditions check of
    `stack_drive_check.mjs`). Next: M2.8 (Learn missions).
- **M2.8 Learn missions 1–6 (2026-10-10).** Evidence: `v2/data/m2/m28/`;
  coverage table [`v2/M2_CLAIMS_COVERAGE.md`](v2/M2_CLAIMS_COVERAGE.md).
  - **Six missions as data** (`lab_web/missions/NN-<id>.yaml`, schema
    `coco.mission.v1`): find a path, what if the world changes, where am I,
    build a map, avoid things, where to look. Each has the seven beats in
    order — hook, predict, reveal, manipulate ("Try it"), explain, check
    against the Stack, challenge (a stub until M3) — and **61 claims**, each
    with a learner label and evidence references.
  - **The evidence check** (`lab_web/tools/missions.py`, CI test
    `lab_web/tools/test_missions.py`, 20 tests): a reference is
    `docs/RESULTS.md "<heading prefix>"` resolving to **exactly one**
    heading, a committed file, or `file::function` (the function must
    exist). Any claim with no evidence, an unresolvable reference, an
    unknown label, or a claim no beat shows fails. `build_catalog.py`
    refuses to write the site if any fails; `build_v2_runs.mjs` refuses a
    replay link to a run it did not build. Every beat's Arena `cfg` lines
    are applied to the Python Arena in the test (an unknown key raises).
  - **Coverage: 98 of 98 v1 claims** (`v2/data/m2/m28/v1_claims.json`:
    every `cite`/`cites`/`citation` object of the v1 site data and every
    `className="cite"` element of the v1 views, made by `v1_claims.py`),
    including the negative and unresolved results (the AMCL kidnap A/B
    p = 0.24, the backends' loop closure making maps worse, DWB's 0/5
    hairpin, D* Lite doing more work on Experiment C, run 15). Each number
    a mission quotes was re-read from its committed source in this session.
  - **Two v1 citations did not resolve as written**, found by the check:
    v1 cited `"A — SmacPlanner2D and the evidence for it"` (the heading is
    `A\* — SmacPlanner2D, and the evidence for it`) and `"Global
    relocalization converges to an unplannable pose on this map"`, which is
    a bold paragraph, not a heading — the mission cites its enclosing
    heading, "What the recovery cannot fix, and why". A test pins the second.
  - **The player** (`?view=learn[&mission=<id>&beat=<n>]`, its own
    code-split app, 6.18 kB): predict-then-reveal (evidence hidden until an
    answer is committed; the options lock; a wrong answer is told the right
    one), each claim with its label, the label's meaning and links to its
    committed evidence, a link to the mission's v1 page. A beat opens the
    Arena with `lens`, `level`, `replay` and the new `cfg` lines; the Arena
    applies exactly those settings in place of the lens's defaults, its
    controls start from them, and "← Back to the mission" returns to the
    beat. Browser check (`browser/learn_check.json`, Chromium): all 6
    missions × 7 beats, all 61 claims shown with a label and ≥ 1 evidence
    link, 0 console errors; the Map beat's four settings applied exactly
    and shown on its controls; the Stack beat plays `lab5_static_room_dwb_1`
    as STACK; mission list and a beat at 390 px: 0 px sideways overflow.
  - **Fixed on the way**: a mission's settings were overridden by the lens
    defaults and the controls showed their own defaults rather than what
    the model was told (both measured in the browser check before the fix);
    the Move caption printed the Lab 5 converter's record marker ("Controller:
    eval.") on every recorded cycle — it now says "Nav2 scored N candidates
    this cycle; M were valid" (test `captions.test.ts`).
  - **Label vocabulary — a deviation for Gautham to rule on**: missions use
    README's MEASURED, ASSUMPTION, SIMPLIFIED MODEL, SIMULATION RESULT,
    INFERENCE, plus UNRESOLVED (the evidence class, for the unresolved
    results the prompt requires) and **TESTED** (a property test proves it)
    for the theorem-like claims none of README's labels fits. REAL ROBOT
    RESULT is never used (a test forbids it).
  - Not done here: the converted Labs 2–4 runs and Lab 5's replanning are
    still not served in the viewer (Mission 6's Stack beat shows the Phase 5
    matrix as cited claims, not a replay); the challenge beats are stubs.
  - Tests: packages **3,432 / 0 / 0** (unchanged), vitest **458 / 0 / 0**
    (+8: `learn.test.ts` 6, `captions.test.ts` 2; the landing test covers
    `?view=learn`), build tools **164 / 0 / 0** (+21: `test_missions.py`
    20, the conditions check of `learn_check.mjs`). Next: M2.9 (fidelity
    report v1).
- **M2.9 Fidelity report v1 (2026-10-10).** Report
  [`v2/FIDELITY_v1.md`](v2/FIDELITY_v1.md), GENERATED by
  `lab_web/tools/fidelity.py` from `v2/data/m2/m29/fidelity_v1.json`
  (made by `v2/data/m2/m29/arena_fidelity.py`); a test fails if it is stale.
  - **Method (inputs held fixed):** the ARENA (MODEL) measured against Lab
    2's two recorded Gazebo fidelity sessions (`~/coco_lab_runs/lab2/
    fidelity_1`, `fidelity_s1`; STACK) with Lab 2's own loaders and
    statistics imported unchanged; controller tracking re-tabulated from
    M2.5 (a test checks every row equals M2.5's JSON).
  - **LiDAR:** 237 of 240 scans, 111,804 beams both returned: |e| median
    2.2 mm, 95th percentile 9.3 cm, 99th 1.43 m. **The Arena's world casts
    exactly like the Stack's saved map — 113,760 of 113,760 beams identical
    to Lab 2's Sketch on the Nav2 map** — so its LiDAR gap is Lab 2's, not a
    new one. Lab 2's class split cannot locate the large errors (111,786 of
    111,804 beams end in OCCUPIED cells); the report says so and cites Lab
    2's own finding about the bays' 3D ramps as Lab 2's, not as re-measured.
  - **Odometry, straight and turning, slip off and on** (200 noise seeds):
    straight 6.4 m — Gazebo 0.000 m, Arena median 0.21 m either way (its
    noise is direction-blind). Square 15.4 m / 11.0 rad — Gazebo 2.298 m;
    Arena slip off 0.286 m, slip on 2.091 m. Yaw over-count (wheel rotation
    / true rotation): Gazebo 1.223× (square), 1.270× and 1.269× (tours);
    Arena slip off 1.000×, slip on 1.290×. **The slip factor was fitted on a
    recorded tour**, so the tour rows are not independent; the square is.
    Gazebo's own two runs of the same tour ended 17.24 m and 2.59 m off —
    one run is not a rate. Lab 2's driver steered on ground truth, so body
    motion under the same commands is compared on the square only (Arena
    body 2.08 m from Gazebo's with slip off, 0.26 m with slip on).
  - **Controller tracking:** on the hairpin and the crossing the model's
    mean tracking error is 0.020–0.043 m against the stack's 0.049–0.143 m;
    outcomes agree there and in run 15, differ head-on by construction.
  - **"Model gap" chips** (`lab_web/src/learn/gaps.tsx`): each lens declares
    the gaps its lessons depend on (`registry.ts` `gaps`: Plan none;
    Localise, Map LiDAR + odometry; Move LiDAR + controllers; Decide all
    three) and missions 3–6 declare theirs (1 and 2 plan on the true map:
    none). A chip opens to its text, rendered at build into
    `generated/fidelity.json` from the committed JSON (never typed), and
    links to the report's section. Browser check
    (`v2/data/m2/m29/browser/learn_check.json`): no chip on missions 1–2,
    the right chips on 3–6 and on the Map lens, the LiDAR chip opens to
    "median 2.2 mm", 0 console errors, 0 px overflow at 390 px.
  - Tests: packages **3,432 / 0 / 0** (unchanged), vitest **459 / 0 / 0**
    (+1: the registry's gaps), build tools **172 / 0 / 0** (+8:
    `test_fidelity.py`). Next: M2.10 (retire the v1 views).
- **M2.10 Retire the v1 lab views (2026-10-10).** Decision record
  [`v2/adr/0003-v1-archive.md`](v2/adr/0003-v1-archive.md); evidence
  `v2/data/m2/m210/`.
  - **`/v1/` is the frozen v1 build, made from its tag at deploy time**
    (`lab_web/tools/build_v1_archive.sh`): a depth-1 clone of
    `coco-lab-v1-final` (refused unless it is `3571169`), the tag's OWN
    `build_catalog.py`, `npm ci` and `vite build` at `/coco-labs/v1/`, the
    tag's own dist check, copied into the Pages artifact. Measured locally:
    108 s, 23 MB, 78 files. Two builds differ only in `created_utc` in 13
    bundle manifests (excluded from every content hash by design;
    `v1_archive_build.json`). Not stored anywhere new — options B (commit the
    built files) and C (a release asset) are recorded in the ADR.
  - **Routing** (`lab_web/src/landing.ts`, `test/landing.test.ts`): a bare
    `?view=plan|localise|map|search|move` goes to its Learn mission;
    `?view=live` stays in `main` (until M5), now as its own page
    (`src/ui/LiveApp.tsx`, the same `LiveView`); a Lab 1 bundle or share link
    naming a bundle unchanged opens its converted run in the Arena
    (`?view=arena&replay=<id>`); everything else a v1 page understood — share
    links with settings or map edits, deep links into a lab, `?view=exhibit`,
    unknown bundles — goes to `v1/` with its query intact. Missions link to
    their v1 page in the archive (`v1/?view=…`; a test enforces it).
  - **Every v1 URL form resolves with 0 console errors** (B.3 "Links"):
    `v1_links_check.mjs`, 22 forms, Chromium, the built site served with the
    archive at `v1/` — 22 of 22 (`browser/v1_links_check.json`); it now runs
    in CI's browser job. The Learn check passes on the same build
    (`browser/learn_check.json`).
  - **The removal preconditions held before any code was removed:** the URL
    test above, `M2_CLAIMS_COVERAGE.md` complete (98 of 98), the 16 searches
    replaying byte for byte (`coco_schemas/test/test_search_replay_v2.py`).
  - **Removed (69 files, listed in the commit):** the v1 lab view code — 52
    files under `lab_web/src` (`ui/` except `LiveView.tsx` and `style.css`,
    `lab/`, `trace/`, v1 `render/`, the `loc|map|move|search` view and
    catalog modules, `model/mode.ts`, and the v1 recompute worker
    `worker/`); the 7 vitest files that tested them and the share-link
    golden vectors; the 5 Python glue tests of the removed worker,
    `make_share_vectors.py`, `time_glue_cpython.py`; and two v1-only
    harnesses, `perf/baseline.mjs` (M0's v1 timings) and
    `perf/landing_check.mjs` (superseded by `v1_links_check.mjs`). Their
    committed evidence stays, reproducible from the tag. The site data the
    v1 views read is still built: the converters and the missions read it.
    Lab 5's three site-data tests moved to `test_lab5_site.py`.
  - CI (`lab.yml`): the `lab-web` job builds the archive into the Pages
    artifact (timeout 20 → 30 min); the browser job builds it and runs the
    URL forms. `check_dist` no longer requires v1's worker chunk.
  - Tests: packages **3,432 / 0 / 0** (unchanged); vitest **343 / 0 / 0**
    (−116, all from listed deletions: `trace` 47, `lab` 21, `share` 20,
    `localise` 10, `mapview` 9, `moveview` 9, `searchview` 3, `site` −1 (the
    worker-glue check); `landing` +4, 4 → 8; counted by running each file at
    `74f5170`); build tools **126 / 0 / 0** (−46: the glue tests `test_glue`
    12, `test_loc_glue` 13, `test_move_glue` 12, `test_map_glue` 6,
    `test_search_glue` 6; `test_lab5_site` +3, `test_missions` +1, the
    harness conditions check −1). Next: M2.11 (measure and decide).
- **M2.11 Measure and decide (2026-10-10).** Results
  [`v2/M2_RESULTS.md`](v2/M2_RESULTS.md) (appended to `docs/RESULTS.md`);
  evidence `v2/data/m2/m211/`; decision record
  [`v2/adr/0004-wasm-gate-m2.md`](v2/adr/0004-wasm-gate-m2.md).
  - **Every agent-measured B.3 criterion is met** (balanced, on AC, the
    final M2 build): determinism 4 engines × 100 sessions × 150 ticks, 0
    differing (digest `6713478e0ec2…`); 60–61 fps on the fetch mission with
    every lens's default layers plus the M2 stress (2,000 particles, 1,000 ×
    56-step rollouts, a full grid, rebuilt at 10 Hz); goal after a planner
    change median 43.7 ms, max 66.5; seek on a 5-minute fetch recording max
    33.1 ms to the redrawn frame; emulated 4G first visible computation
    median 3,005 ms and live model ready median 7,870 ms (max 8,158); lenses
    ready ≤ 205 ms warm; 22 / 22 v1 URL forms; 0 console errors on 14 pages.
  - New harness pieces: `?stress=m2` (`src/arena/stress.ts`) and
    `?layers=all` in the Arena; `render_fps.mjs --scene m2`;
    `seek_check.mjs`; `console_check.mjs` covers M2's pages.
  - **No WebAssembly port** (ADR 0004): nothing fails a budget.
  - `PHONE_MEASURE.md` has an M2 section (the fetch mission and lenses);
    `USABILITY_TEST_M2.md` is the script and table for missions 1, 3 and 5.
    Both stay **pending Gautham**.
  - **Found:** unattended upgrades moved the NVIDIA userspace libraries to
    580.178.04 at 06:18 with the kernel module still 580.173.02 — NVIDIA EGL
    fails until the machine is **rebooted** (owner action). All timings were
    written by 05:58; the WebKit determinism leg was re-run with Mesa EGL.
    In the seek recording 1 of 4 fetches completed: later fetches inherit the
    pose where DWA stalled (reproduced in Python; M2.6's DWA weakness, parked
    in IDEAS). Fixed: the mission state label ("Go To_bay").
  - **CI on PR #21 caught a defect in `build_v1_archive.sh`:** given a
    RELATIVE output path (as `lab.yml` passes it), the copy landed inside the
    tag's clone, so the Pages artifact had no `v1/` and 10 of the 22 URL
    forms failed in CI with 404s (locally the path was always absolute). The
    script now resolves its paths first and refuses to finish without
    `OUT/index.html`; re-checked locally with CI's relative path.
  - **CI green on PR #21** at `0687c4f` (`lab.yml` run 38015704616: every
    job; the archive in the Pages artifact; 22 / 22 URL forms in CI). The PR
    is open and **not merged** (the agent's merge permission covered PR #20
    only).
  - Tests: packages **3,432 / 0 / 0**, vitest **343 / 0 / 0**, build tools
    **127 / 0 / 0** (+1: the conditions check of `seek_check.mjs`). Next:
    the pull request into `main` (not merged by the agent), Gautham's phone
    and usability rows, and a fresh review session.

## Capabilities (README §2), with evidence class

Classes as README §3 defines them: MODEL, STACK, REMOTE, HARDWARE (none
exist), UNRESOLVED, CONCEPT.

| Capability / result | Class | Caveat | Evidence |
|---|---|---|---|
| Smac and `coco_lab` find the same optimal cost on 36/36 pairs | STACK + MODEL | — | `docs/RESULTS.md` Phase 1C; `docs/data/lab1c/conformance/` |
| Sketch LiDAR against Gazebo: 86.7% of beams within 5 cm | MODEL vs STACK | Turns diverge (no wheel slip) | `docs/labs/LAB2_LOCALISE.md`; `docs/data/lab2/fidelity/` |
| Kidnapping, model: 18/20 with injection vs 0/20 without | MODEL | — | `docs/labs/LAB2_LOCALISE.md` |
| Kidnapping, Stack: 2/10 vs 0/10 (Fisher p = 0.237) | UNRESOLVED | — | `docs/data/lab2/kidnap_ab.json` |
| Loop closure damaged maps on both real SLAM backends | STACK | Cause unattributed | `docs/labs/LAB3_MAP.md` |
| Search: 14/16 complete, 39/39 looks correct | STACK | All 16 replay byte for byte through `coco_lab` | `docs/labs/LAB4_SEARCH.md` |
| Lab 5: 54 runs, 0 void | STACK | DWB 0/5 at the hairpin; nobody swerved head-on | `docs/labs/LAB5_MOVE.md` |
| Run 15 mechanism reproduced 9/9 | STACK | Exact "0 of 819" not reproduced | `docs/labs/LAB5_MOVE.md` |
| D\* Lite less work than A\* in 191/200 teaching worlds | MODEL | 2.9× *more* work on one real costmap | `docs/RESULTS.md` Phase 6 |
| Latched STOP; drive command p50 4.6 ms; STOP 6.2 ms | STACK | Local network | `docs/live/LIVE.md` |
| Phone on mobile data drove the robot; RTT about 282–293 ms; disconnect stop about 0.54 s | REMOTE | Robot simulated | `docs/live/PART_C_REPORT.md` |
| v1 site baseline (cold start, warm edit, frame rate, sizes) — laptop | MODEL | Phone not yet measured | `docs/v2/BASELINE.md` |
| The Arena: identical per-tick hashes in Chromium, Firefox, WebKit and Pyodide-in-Node (100 sessions, 15,000 ticks each) | MODEL | Laptop; not yet on a phone | `docs/v2/data/m1/determinism/` |
| The Arena: 60 fps at 50k points + 20k segments; goal → computation on screen in 40 ms median (warm); first visible computation 0.75–3.3 s cold | MODEL | Laptop, power-saver; phone pending Gautham | `docs/v2/M1_RESULTS.md` |
| Lab 1's three recorded full-stack runs played in the Arena viewer | STACK | Played, not re-measured | `docs/v2/data/m1/replay/` |

**Unresolved, kept labelled** (README §2): DWB's hairpin stall; why no
controller swerved; D\* Lite's extra work on the real costmap; loop-closure
damage; exact Run 15; recovery from confident AMCL divergence; the
collision-monitor residual; untested remote behaviours (phone STOP, second
spectator, mid-mission preemption, remote mission completion, idle and
session caps, the cause of the disconnect, the stale Nav2 "executing"
label).

## Open questions (README §8) and the defaults in force

| ID | Decision | Default until Gautham decides |
|---|---|---|
| G1 | Primary audience | Learners first |
| G2 | Priority against the robot project and job hunt | Not an agent decision; agents respect announced robot batch windows |
| G3 | Canonical robot stack | The robot repo is canonical; `coco-labs` robot packages are frozen, not deleted |
| G4 | Monthly cloud budget | Zero; no cloud resources are created before M4 and an explicit budget |
| G5 | Will a physical robot exist within a year? | Assume no; no "real robot" wording anywhere |
| G6 | License and outside contributions | Unchanged from the current repo |

## Plan-change log

Changes to `README.md` happen only at a milestone boundary, by Gautham,
as a dated entry here (README §0).

| Date | Change | Reason | By |
|---|---|---|---|
| 2026-10-08 | **Live console errors are fixed, not waived.** The quiet Live probe moves from `docs/IDEAS.md` into M0 (fix A.2), so the M0 exit criterion "no console errors in any view" is met before merging. | Independent review 2026-10-08: the criterion was not met and STATUS.md overstated it. | Gautham (M0-close / M1 prompt §0.1) |
| 2026-10-08 | **Gripper wording corrected.** README §2 correction 2 and M0.6 now read "two fingers and a magnet; the magnet does the holding". README sha256 `4b003e50…a2ab6` → `23214733…175935c`. | The robot-stack record (RESULTS "The magnet fires before the fingers close") shows fingers *and* a magnet; "magnet, not two-finger" was wrong. Raised by the review. | Gautham (prompt §0.2) |
| 2026-10-08 | **One-off permission to edit three published release texts** (`live-v1.0`, `lab1-v1.0`, `lab4-v1.0`): wording only, never assets, tags or targets. | Their "real robot" wording describes the Gazebo stack; agents otherwise never edit releases. | Gautham (prompt §0.3) |
| 2026-10-08 | **One-off permission to merge PR #19** once the fixes are pushed, CI is green and the M0-close conditions hold. Merging deploys Pages. | Closes M0 (README §9.9 review done). | Gautham (prompt §0.4) |
| 2026-10-08 | **Canonical checkout from M1 on is `~/coco_labs_ws/src/coco-labs`**, fast-forwarded to the merged `main`. `~/ros2_ws(personal)` and its worktrees are left untouched and no longer used for COCO Lab. | `CLAUDE.md` and the scripts already default to that path; the review flagged the stale clone as a risk of building the wrong tree. | Gautham (prompt §0.5) |
| 2026-10-09 | **Measurement conditions.** The standard is the **balanced** power profile **on AC power**. An agent may `powerprofilesctl set balanced` before measuring and must restore the original profile afterwards. Every harness records the power profile, AC or battery, CPU governor and load average next to its results (`lab_web/tools/perf/conditions.mjs`). Power-saver numbers already measured are **kept** as a worst-case row, never deleted or replaced. "Laptop cold start" = time to **first visible computation** (README's definition; M1 met it). "Live model ready" is reported separately as a secondary metric; in M2 it becomes a budget: **≤ 10 s on emulated 4G for the Plan lens**, because the new lenses need the live model. | M1.10 measured in power-saver without a stated standard; M1.5 recorded no profile, so the two were not comparable. | Gautham (M1-review / M2 prompt §0.1) |
| 2026-10-09 | **WebKit libraries stay private** in `~/coco_lab_m1_ws/webkit_libs` (four `.deb`s unpacked with `dpkg -x`); no sudo, nothing installed system-wide. `lab_web/tools/setup_webkit_libs.sh` re-creates them from pinned versions with sha256 checksums; documented in `docs/v2/CHECKOUTS.md`. | Cross-browser determinism needs WebKit; the host lacks four of its media libraries and agents do not use sudo. | Gautham (prompt §0.2) |
| 2026-10-09 | **One-off permission to merge PR #20** (M1), only under the M1-review conditions (prompt A.5: recommendation MERGE, or MERGE AFTER FIXES with every fix done; the three suites pass; every CI check on PR #20 passes after the last push; 0 console errors in all views of a production build). Merge commit, no squash or rebase, branch kept. Merging deploys Pages and makes the Arena the bare URL's landing page — expected. A build-time switch (`LANDING=arena\|v1`, default `arena`, `lab_web/site.config.ts`) lets the landing page be reverted in one commit if the phone results are bad. | Closes M1's agent-measurable part after an independent review (README §9.9). | Gautham (prompt §0.3) |
| 2026-10-09 | **"Retiring the v1 lab views" (M2) means:** their code is removed from `main` while a **frozen build of v1**, built from the tag `coco-lab-v1-final`, is served at **`/v1/`**. Every old URL (`?view=…`, `?bundle=…`, `?v=…`) keeps working, by redirecting either to `/v1/` or to its v2 equivalent. Removing working public views is otherwise forbidden; this is how M2 retires them without breaking a link. | README §7 M2 exit criterion "the old per-lab views are retired; their release tags remain", reconciled with "never break a public URL". | Gautham (prompt §0.4) |
| 2026-10-09 | **One-off permission for one fix outside the M1 review's allowed list:** `coco_schemas/setup.py` gains `tests_require=['pytest']`, so CI's `build-and-test` actually runs the `coco_schemas` suite (it collected 0 tests and failed on PR #20). Then merge PR #20 under the A.5 conditions. | The review found the schema and compatibility tests had never run in CI (M1's "schema tests in CI" was false); the fix is test discovery only, no behaviour change. | Gautham (answer to the reviewer's question, 2026-10-09) |
