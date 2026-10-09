# Review of M1 (PR #20): independent reviewer session, 2026-10-09

README §9.9 review of **M1 · Glass-box Arena core**, by a session that did
not build M1, given the repository, `README.md`, the M1 report (PR #20's
body, `docs/STATUS.md`, `docs/v2/M1_RESULTS.md`) and the owner's review
prompt. Every claim was treated as a claim to verify.

**Where.** A fresh clone of `GauthamCodes/coco-labs` at
`~/review/coco-labs-m1`, branch `v2/m1-arena-core`, head **`4e06942`** (as
claimed), with its own overlay `~/review/ws_m1` (built from the clone,
`scripts/build_overlay.sh`, 12 packages) and `npm ci` in the clone. Borrowed
read-only: Node 24.21.0 (`~/coco_v2_ws/node`), the test venv
(`~/coco_labs_ws/test_venv`), the MoveIt prefix, the Playwright browsers,
the WebKit libraries in `~/coco_lab_m1_ws/webkit_libs`. ROS domain 83. No
simulator, Isaac or robot batch was running (checked before every heavy
job). Fixes were committed from the M1 worktree as `[M1-fix]` commits and
pulled into the clone before re-checking.

| Item | Verdict | Evidence |
|---|---|---|
| Head SHA | VERIFIED | `git rev-parse HEAD` in the fresh clone = `4e06942ccbe3…`. |
| Diff: nothing deleted | VERIFIED | `git diff --name-status main...v2/m1-arena-core`: 250 files, 232 added, 18 modified, **0 deleted**, 0 renamed; +20,072 / −60. |
| `docs/RESULTS.md` append-only | VERIFIED | `main`'s copy (443,945 B) is an exact byte prefix of the branch's (450,186 B), checked with `cmp`. |
| Every removed line accounted for | VERIFIED | The 60 removed lines: `search.py` (22) — `search()` body moved into the `search_events()` generator, `search()` now consumes it; `lab_maps.py` (9) — the generator body moved into `build_case()`, `assume(goal != start)` became `return None` + `assume(case is not None)`, the `event()` calls moved with it (same corpus; the goldens are its proof); `main.tsx` (7) — the Arena routing; `STATUS.md` (7) and `PROJECT_STATE.md` (4) — M0 → M1 position rows; `package.json` (4) and `package-lock.json` (1) — `dev` / `build` now build the Arena assets first, and two lines gained a trailing comma for new entries (`three`, protobuf, MCAP, Pyodide); `ci.yml` (2) — `coco_schemas` added to both package lists; `check_dist.mjs` (2) — the pinned-Pyodide check now searches every page chunk instead of `index-*.js` only (the page is code-split), plus new self-hosted-Pyodide and worker checks; `console_check.mjs` (1) — `arena` added to the views; `requirements-test.txt` (1) — a comment re-wrapped to name the pinned `pyyaml`. |
| Tests: 3,235 / 381 / 117 | VERIFIED | Fresh clone, clean overlay: packages **3,235 / 0 / 0** (`scripts/run_all_package_tests.sh`); `lab_web` typecheck clean, vitest **381 / 0 / 0** (25 files); build tools **117 / 0 / 0**; generated TypeScript current. |
| Where the 154 new package tests come from | VERIFIED | 3,235 − 3,081: `coco_schemas` **+91** (new package), `coco_lab` 604 → 665 (**+61**: arena, rng, worldspec, events, golden traces), `gazebo_models` 229 → 231 (**+2**, per-package build checks). |
| Where the 73 new vitest tests come from | VERIFIED | 381 − 308 (v1 final): **12** are M0's `live_gate.test.ts`, already on `main` (M1's own baseline was 320); **61** are M1's seven new files — `arena_determinism` 6, `arena_runtime` 4, `arena_share` 10, `convert_lab1` 17, `plan_store` 5, `schemas` 12, `session` 7 (run with a JSON reporter). |
| CI: all checks on PR #20 passed | **FALSE** at `4e06942`; fixed | `gh pr checks 20`: `build-and-test` **failed** (run 37852064107): `colcon test` ran `coco_schemas` through unittest — `setup.py` declared no pytest — found **0 tests** and exited 5. The M1 report's "all jobs green" cited only the `Lab` workflow run. Reproduced locally (0 tests, exit 5); with `tests_require=['pytest']` 91 / 0 / 0. Fixed in `[M1-fix]` `b3dc8a0` under the owner's one-off permission (STATUS plan-change log, 2026-10-09); CI on the final head: see "After the fixes" below. |
| Golden traces on the 1,000-map corpus | VERIFIED | `test_golden_traces.py` in the clone: 14 / 14 (all 5,000 searches in 10 blocks; the file asserts 1,000 maps × 5 algorithms). The goldens were frozen at `e801785`, whose `coco_lab` package differs from `coco-lab-v1-final` only by three new files (arena, rng, worldspec) — `search.py` identical — so they are v1's traces. CI's plain-venv job ran them (662 `coco_lab` tests, 0 skipped). |
| Determinism: re-run ≥ 25 sessions, 4 engines | VERIFIED | The first **25** of the committed sessions, production build: Pyodide-in-Node, Chromium 156, Firefox 157, WebKit 27.2 — 3,750 ticks each, **0 mismatched** across engines (digest `3c061fa4a253`) and **0** against the committed Pyodide hashes. `docs/v2/data/m1/review/determinism_rerun/`. |
| Determinism: 100-session evidence agrees with the report | VERIFIED, one overstatement | Recomputed from the committed `hashes_*.json.gz`: 100 sessions × 150 ticks per engine, 0 mismatched, 100/100 chains equal, 15,000 distinct hashes per engine, digest `0e43a0b5d6b9…` in all four; inputs 416 goals / 337 teleop / 84 planner / 79 stop — all as claimed. **Overstated:** "each session a fresh model (a new Pyodide in Node…)" — the Node harness reuses one Pyodide and reloads the module per session (its own comment says so); browsers do start a new worker per session. |
| Schemas: two additive changes backward-compatible | VERIFIED | `compat/v1.binpb` is unchanged since M1.1, so `test_compat.py` checks M1.10 against the original baseline: passes. An M1.1-generated reader (`git archive 6cf6b05`) parses an M1.10 `WorldGrid` with `occupancy` and re-encodes it byte-identically (unknown field kept); `coco.plan.path.poses.v1` is a new (16th) channel no M1.1 reader subscribes to. |
| Schemas: documented in `SCHEMAS.md` | VERIFIED | Lines 40 (`occupancy`, field 11, M1.8, additive) and 53, 138 (`coco.plan.path.poses.v1`, M1.9, additive). |
| Schemas: the CI check would catch an incompatible change | **FALSE** at `4e06942`; true after the fix | Throwaway local edits (not committed, file restored, `git status` clean): retyping `WorldGrid.resolution` double → float, and deleting it — `test_compat.py` **fails** for both. But CI never ran `test_compat.py` (the `coco_schemas` row above), so CI would **not** have caught it until `b3dc8a0`. |
| Responsiveness: the two fixes are real | VERIFIED | `session.ts` shows the search being computed for the tick in progress (`head + 1`) live; `perf.ts` ignores frames of the search shown at the click. The session fix is pinned: reverting that one line makes `session.test.ts` fail (1 failed, 6 passed); restored, 7/7. The timer fix in `perf.ts` has **no unit test** (only the harness exercises it). |
| Responsiveness: median ~40 ms warm, reproduced | VERIFIED | Balanced, GPU, real mouse clicks, n = 25: median **42.9 ms**, p95 61.9, max 63.2, **25/25** under 100 ms (first goal 45.9 ms). |
| Budgets re-measured, balanced on AC, n ≥ 10 | DONE | fps 60–61 in all 100 samples (10 runs), p95 frame 16.8–17.6 ms; seek max 0.7 ms (70 seeks); first visible computation **631 / 1,366 / 3,381 ms**; live model ready **2,683 / 4,061 / 8,191 ms** (desktop / fast-4G = M1's "Wi-Fi" profile / emulated 4G, n = 10 each). Appended to `docs/RESULTS.md` and `docs/v2/M1_RESULTS.md`; power-saver rows kept. `docs/v2/data/m1/balanced/`. |
| v1 links open v1 | VERIFIED, after widening the check | M1's `landing_check` had 9 cases, but **3 are Arena URLs** and it never opened `?view=localise|map|search` or a bare `?v=`. Widened to 14 (every v1 form): **14/14**, 0 errors (`landing/landing_check_review.json`). |
| Six v1 views + `?view=arena`, production build, 0 console errors | VERIFIED | `console_check.mjs` on the fixed production build: plan, live, localise, map, search, move, arena — **0 console errors, 0 page errors**, 0 WebSockets on load, 0 cross-origin requests (`review/views/console_check.json`). |
| Landing: bare URL opens the Arena; visible v1 link | VERIFIED | Bare URL → Arena; its "v1 labs" link (`data-testid=v1-labs-link`) opens v1 (landing check). |
| STATUS.md honesty | VERIFIED, with two false claims corrected | Phone fps, phone cold start and usability are listed **pending Gautham**; both parked items (replan latency after a planner change; attract mode slowing the model load) are in `docs/IDEAS.md` and STATUS. False: M1.1's "coco_schemas built and tested in ci.yml" and M1_RESULTS's Hygiene "CI: schema tests (coco_schemas)" — corrected in place with a dated note. |
| Phone instructions | VERIFIED | `PHONE_MEASURE.md` and `USABILITY_TEST.md` exist, are step by step with a results table, and need no tools beyond a phone. The `?perf` panel's "first computation shown" reads a real number (643 ms in a headless check) — the phone cold-start number. |
| Checkpoint discipline (also checked) | VERIFIED | 15 commits, each prefixed `[M1.x]`; STATUS.md updated at every checkpoint. |

## Claims in the M1 report that are false or overstated

1. **"CI (… all jobs green)" / "schema tests in CI".** False. The `Lab`
   workflow was green; the `CI` workflow's `build-and-test` failed on PR #20,
   and `coco_schemas`' 91 tests — the schema compatibility check among them —
   had never run in CI. M1.1's "coco_schemas built and tested in ci.yml" was
   false from M1.1 on. *Fixed* (`b3dc8a0`).
2. **"Each session a fresh model (a new Pyodide in Node…)".** Overstated: one
   Pyodide per run, module reloaded per session. The determinism result
   stands (the browsers, which are the cross-engine comparison, do start a
   fresh worker per session). *Corrected in `M1_RESULTS.md`.*
3. **"Every v1 link … still opens v1 (9/9)".** Overstated: 3 of the 9 cases
   are Arena URLs; three v1 views and a bare `?v=` were never opened. True
   once checked (14/14). *Corrected; the check is widened.*
4. **"A vitest pins the fix"** (responsiveness). True for the session fix;
   the timer fix in `perf.ts` is pinned by no unit test.

Everything else in the report matched what I measured: the head SHA, the
counts, the determinism evidence, the golden traces, the schema changes,
the seek times, 0 console errors, the landing page, the pending-Gautham
items and the parked ideas.

## Fixes made (`[M1-fix]`, all on `v2/m1-arena-core`)

| Commit | Fix | Category (prompt A.3) |
|---|---|---|
| `d53a360` | `lab_web/tools/setup_webkit_libs.sh` — the four WebKit libraries from pinned, sha256-checked packages; documented in `CHECKOUTS.md`. Re-created a tree identical to M1's from scratch | setup_webkit_libs.sh |
| `2ad8ecf` | `lab_web/tools/perf/conditions.mjs`; every perf harness records power profile, AC/battery, governor and load; a static test keeps it so | harness power state |
| `6fbbd78` | `LANDING=arena\|v1` build-time switch (default `arena`, `site.config.ts`), pure `chooseApp()` + 4 tests; landing check widened to 14 URL forms | landing switch; regenerable evidence |
| `4b4bef8` | Plan-change log: the owner's four decisions of 2026-10-09 | plan-change log |
| `b3dc8a0` | `coco_schemas/setup.py` declares pytest, so `colcon test` runs its 91 tests in CI | **outside A.3's list — the owner's one-off permission** (asked and granted during the review) |
| (this commit) | This report; balanced re-measurement and review evidence; STATUS / M1_RESULTS corrections; RESULTS append | documentation; evidence |

## Risks

- **Phone results are unknown.** Merging makes the Arena the public
  landing page before anyone has measured it on a phone. Mitigated by
  `LANDING=v1` (one commit) — but nothing measures the phone except
  Gautham.
- **Power profile.** M1.10's numbers were power-saver; the balanced numbers
  are better on every cold-start row (live model on 4G 10.8 s → 8.2 s).
  A phone is slower than either; the 4G live-model budget M2 adopts
  (≤ 10 s) is met on the laptop only in balanced mode.
- **A goal right after a planner change still queues** (balanced: median
  139 ms, max 1.7 s). Parked for M2.0, not an M1 criterion.
- **The `perf.ts` timer fix has no unit test**; a regression would show only
  in the responsiveness harness.
- **CI had a silent gap for a whole milestone.** The `CI` workflow runs only
  on pull requests, and M1's single PR run was its first; the M1 agent
  dispatched only the `Lab` workflow during development. M2 should look at
  both workflows before claiming CI green.
- Determinism is laptop-only (no phone engine); unchanged from M1's own
  caveat.

## Recommendation

**MERGE AFTER FIXES** — every fix is done (table above). Merge only when
the A.5 conditions hold on the final head; the result is recorded below.

## After the fixes (final head)

Recorded in `docs/STATUS.md` (M1 review entry and the M2 branch's first
commit) once the final CI run and suites complete.
