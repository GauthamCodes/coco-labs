# Review of M2 (PR #21): independent reviewer session, 2026-10-10

README §9.9 review of **M2 · The whole loop**, by a session that did not
build M2. It was given the repository, `README.md`, the M2 report (PR #21's
body, `docs/STATUS.md`, `docs/v2/M2_RESULTS.md`) and the owner's review
prompt (M3 prompt, Part A), and treated every claim as a claim to verify.

**Where.** A fresh clone of `GauthamCodes/coco-labs` at
`~/review/coco-labs-m2`, branch `v2/m2-whole-loop`, head **`330df44`** (as
claimed). It had its own overlay `~/review/ws_m2` (built from the clone with
`scripts/build_overlay.sh`, 12 packages) and its own `npm ci`. A second
worktree of the clone at **`74f5170`** (`95187dd`'s parent) was used for the
deleted-test counts.

Borrowed read-only:
- Node 24.21.0 (`~/coco_v2_ws/node`)
- the test venv (`~/coco_labs_ws/test_venv`)
- the MoveIt prefix
- the Playwright browsers
- the WebKit libraries in `~/coco_lab_m1_ws/webkit_libs`
- M2's tag-built archive `~/coco_lab_m2_ws/v1_dist`, used only to demonstrate
  the defect below

ROS domain 86. No simulator, Isaac or robot batch was running; this was
checked before every heavy job. Fixes were committed from the M2 worktree as
`[M2-fix]` commits.

**Machine.** Rebooted at 08:58. NVIDIA kernel module and userspace are both
**580.178.04**, which ends the mismatch M2.11 found. Headless Chromium 156
with the harnesses' GPU flags renders WebGL 2 on
**`ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 4050 Laptop GPU/PCIe/SSE2,
OpenGL ES 3.2)`**, not SwiftShader (`docs/v2/data/m2/review/gpu/gpu_probe.json`).
Balanced power profile, on AC.

| Item | Verdict | Evidence |
|---|---|---|
| Head SHA | VERIFIED | `git rev-parse HEAD` in the fresh clone = `330df447f4e8…`. |
| Diff: what was deleted | VERIFIED | `git diff --name-status main...v2/m2-whole-loop`: **274 A, 69 D, 62 M**, 0 renamed. The 69 deletions are exactly `95187dd`'s (`git show --diff-filter=D`), and every one is named in its commit message (which also names 3 kept files it edited). All are under `lab_web/src`, `lab_web/test` and `lab_web/tools`; none is under `docs/`, a data or evidence directory, or a recording path. The only data-like file is the test vector `lab_web/test/golden/share_vectors.json`, which belonged to the deleted v1 share code. |
| `docs/RESULTS.md` append-only | VERIFIED | `main`'s copy (452,446 B) is an exact byte prefix of the branch's (455,814 B), checked with `cmp`; +43 lines, 0 removed. |
| Tests: 3,432 / 343 / 127 | VERIFIED | Fresh clone, clean overlay: packages **3,432 / 0 / 0** (`scripts/run_all_package_tests.sh`, 12 packages: coco_config 93, coco_sim 323, coco_mission 371, coco_web 863, gazebo_models 231, coco_rl 251, coco_perception 139, coco_moveit_config 12, custom_teleop 75, coco_lab 735, coco_lab_ros 121, coco_schemas 218). `lab_web` typecheck clean, vitest **343 / 0 / 0** (31 files). Build tools **127 / 0 / 0**. Generated TypeScript current. |
| vitest −116 comes only from deleted files | VERIFIED | Run at `74f5170`, the seven deleted files pass **119** tests: trace 47, lab 21, share 20, localise 10, mapview 9, moveview 9, searchview 3. The two changed files go from 11 to 14: `site.test.ts` 7 → 6, `landing.test.ts` 4 → 8. −119 − 1 + 4 = **−116**. |
| tools −46 comes only from deleted files | VERIFIED | At `74f5170` the tools suite collects 172, and the five deleted glue files pass **49** (glue 12, loc_glue 13, move_glue 12, map_glue 6, search_glue 6). Then: + `test_lab5_site.py` 3, + `test_missions.py` 1 (20 → 21), − `test_perf_conditions.py` 1 (parametrized over `perf/*.mjs`: two deleted, one added). That gives 126 at `95187dd`, and M2.11's `seek_check.mjs` brings it to **127**. |
| CI: every check on PR #21 passed, including the 22 URL forms | VERIFIED at `330df44` | `gh pr checks 21`: all 4 jobs pass; the Pages deploy is skipped (main only). In the browser job's log (job 114108065661), step 12 "Every v1 URL form resolves, 0 console errors (M2.10)" printed `{"ok":true,"forms":22,"failed":0}`. CI on the final head: see "After the fixes". |
| Old links: 22 v1 URL forms, 0 console errors | VERIFIED | Production build of the clone, served like Pages: **22 / 22** land where `landing.ts` routes them, with 0 console and 0 page errors. |
| `/v1/` serves the frozen v1 and each of its six views works | **FALSE** at `330df44`; fixed | The archive was built from tag `coco-lab-v1-final` (= `3571169`). That tag was cut in M0.2, **before** M0's public fixes, so it puts them back at `/v1/`. Opened directly, **6 / 6** archive views fail. Every view's Live tab reads plain "Live", undoing M0.6's "Live Stack (simulated)" (`dbf1f60`). The Search lab says "real robot" for the Gazebo stack. The Live view opens a WebSocket on load and logs `ERR_CONNECTION_REFUSED` (M0's quiet probe `40b6dc2` is missing). M2 did not check `v1/?view=live` (ADR 0003, `v1_links_check.mjs`: `not_checked`); its console check opened only the archive's front page. Evidence: `docs/v2/data/m2/review/links/tag_build.json`. **Fixed** under the owner's ruling (plan-change log, 2026-10-10): the archive is built from **`9f58b83`**, the M0 merge, which has the v1 views with M0's fixes and no M1 code. Result: 22 / 22 forms and **6 / 6 archive views**, 0 console and 0 page errors, no "real robot", every Live tab "Live Stack (simulated)" (`links/9f58b83_build.json`). `v1_links_check.mjs` now checks the six archive views, in CI too. |
| 0 console errors on all public pages | VERIFIED (with the `9f58b83` archive) | `console_check.mjs` over the same build: all **14** pages (the Arena and its four lenses, Learn and its six missions, Live, the v1 archive) show 0 console errors, 0 page errors and 0 sockets on load. Live recovers to "connected" with one socket when a stand-in stack appears (`docs/v2/data/m2/review/console/console_check.json`). |
| The 16 search runs replay byte for byte | VERIFIED | `coco_schemas/test/test_search_replay_v2.py` in the clone: 4 / 4. The test asserts 16 runs in the converted STACK file, 16 heads, 16 replayed with every field equal, and a flipped look caught. `convert_lab4.test.ts` (in the vitest run) rebuilds that `.mcap` byte for byte from the committed Lab 4 bundle. |
| 98 claims covered; every evidence reference resolves | VERIFIED, with a documentation defect fixed | `M2_CLAIMS_COVERAGE.md` has **98** rows. Resolved independently from the mission YAML (not the generator): **61** claims, every reference resolves (0 unresolved); labels TESTED 25, MEASURED 12, SIMULATION RESULT 12, SIMPLIFIED MODEL 8, UNRESOLVED 2, ASSUMPTION 2. **Defect:** the generated table cut its evidence column at 300 characters, so 5 references were truncated mid-name (e.g. `coco_lab/test/test_pro`). The check reads the YAML, so it was unaffected. Fixed and regenerated (`missions.py`). |
| The CI evidence check works | VERIFIED | Added an uncommitted throwaway claim to mission 1 and restored it with `git checkout`. With `evidence: []`, `missions.py` fails ("cites nothing"). With a reference to a non-existent RESULTS.md heading, `test_missions.py` fails 2 tests and `build_catalog.py` (which CI runs in both lab.yml jobs) exits 1. Weakness: `missions.py` run alone prints "1 evidence problems" but exits 0 (risk 6). |
| 10 claims against `docs/RESULTS.md` for meaning | 8 VERIFIED, 2 overstated; fixed | **Hold, including every negative and unresolved result:**<br>• `smac-agrees`: 36 / 36, NavFn +0.57 %<br>• `dstar-work`: 191 / 200; 3,209 vs 1,114 cells = 2.88× on the real costmap<br>• `kidnap`: 18 / 20 augmented, 13 / 20 at 5 %, 0 / 20 off, equal to `sketch_rates.json`<br>• `arena-kidnap-sketch`: 2 / 20, 0 / 20<br>• `arena-kidnap-closed-loop`: 0 / 20, labelled SIMPLIFIED MODEL and contrasted with Lab 2's open loop<br>• `kidnap-ab`: 2 / 10 vs 0 / 10, p = 0.24, **UNRESOLVED**<br>• `loop-backends`: **UNRESOLVED**, "NOT attributed"<br>• `head-on`: the actor "was a ghost"; nobody swerved<br>**Overstated:**<br>• `run15-quoted` quoted run 15's "No valid trajectories out of 819!" beside the reproductions' 3 / 3 and 5 / 5, but omitted RESULTS.md's "mechanism reproduced, its symptom not" (DWB scored 0 of 0 candidates, not 819). README §2 keeps "exact Run 15" unresolved.<br>• `hairpin` gave DWB's 0 / 5 without saying the stall is unattributed (README §2 "Unresolved").<br>Both reworded (mission 5). |
| Determinism: ≥ 25 sessions, 4 engines; 100-session evidence exists | VERIFIED | **Committed evidence:** `m211/determinism/` holds `sessions.json` (100 sessions × 150 ticks, from `--gen-seed 20261011` with loop, map, move and mission on) and the four `hashes_*.json.gz`, 100 sessions each: Chromium 156.0.8078.4, Firefox 157.0, WebKit 27.2, Pyodide 314.0.7 / Node 24.21.0. **Re-run here:** the first **25** of those sessions on the clone's production build, through each engine, gave 3,750 ticks per engine and **0 mismatched** across engines (digest `17208816cdd3`). Each engine also has **0** mismatches against M2's committed Pyodide hashes. WebKit ran on the NVIDIA EGL, not M2.11's Mesa workaround. `docs/v2/data/m2/review/determinism/`. |
| `FIDELITY_v1.md` regenerates from committed data | VERIFIED | `test_fidelity.py` (in the tools run) asserts the file equals `fidelity.report()` from `m29/fidelity_v1.json` and Lab 2's `fidelity.json`. Regenerated again after the wording fix. |
| Fidelity: LiDAR wording | Conflation found; fixed | The report's §1 table states Arena vs Gazebo (|e| median 2.2 mm; **86.7 %** within 5 cm) and keeps the 113,760-beam identity in a separate, labelled row ("against Lab 2's Sketch on the Nav2 map"). But its headline sentence said "The Arena's world is, to the LiDAR, the Stack's saved map … So its LiDAR gap is exactly the one Lab 2 measured", without saying that the identity is with the map, not with Gazebo's sensor. `M2_RESULTS.md`'s M2.9 row summarized it as "the Arena's LiDAR is beam-for-beam Lab 2's (|e| median 2.2 mm)", which joins the map identity to the Gazebo error and drops the 86.7 %. The LiDAR chip gave Gazebo error percentiles but not the within-5 cm figure. **Fixed:** the report, the chip, the M2.9 rows of `M2_RESULTS.md` and `STATUS.md`. |
| Fidelity: slip wording | Mild implication found; fixed | "Gazebo's wheels report more rotation than the body made" and the chip's "Gazebo's wheel odometry … over-counted turns 1.22–1.27×" measure against Gazebo's own ground truth. The report's preamble says no physical robot exists, but the sentences and the chip did not. **Fixed:** "against Gazebo's own ground truth (a simulator, not a physical robot)". The 1.29× is still labelled "a factor fitted on a recorded tour", and the square stays the independent row. |
| Post-reboot re-measurement (GPU, balanced, AC, n ≥ 10) | VERIFIED: every budget still met | NVIDIA **580.178.04**, balanced on AC, renderer `ANGLE (NVIDIA … RTX 4050 Laptop GPU …)` in every fps and latency run, and in a probe at the start and end of the session.<br>• **Fetch mission + stress:** 58–62 fps in every one of 200 s (10 × 20 s). Per-second p95 frame median 18.6 ms, range 16.9–33.0. M2 reported 17.2–20.6 from one run; here 43 of 200 seconds exceed 21 ms, clustered at seconds 12–14 and 18–19.<br>• **M1 stress scene:** 60–61 fps in every one of 100 s.<br>• **Goal after a planner change:** median **40.3 ms**, p95 65.6, max **66.8**, 25 / 25 under 100.<br>• **Seek:** max **35.4 ms** over 30 seeks in 3 recordings.<br>• **Emulated 4G (n = 10):** first visible computation median **3,201 ms** (2,969–3,222); live model ready median **8,062 ms** (7,836–8,129).<br>Appended to `docs/RESULTS.md` and `M2_RESULTS.md`. Evidence: `docs/v2/data/m2/review/remeasure/`. |
| The 5-minute recording with 1 of 4 fetches completed | VERIFIED honest where used; two rows completed | The recording is generated live by `seek_check.mjs` and is not saved. It is **not** attract mode: `build_attract.mjs` builds a separate scripted three-goal planner demo. It is not used as a showcase anywhere. `M2_RESULTS.md` "Found while measuring", `STATUS.md` and `RESULTS.md` state "only the first of four fetches completed". The responsiveness row of `M2_RESULTS.md` and ADR 0004's seek row quoted the seek time without that caveat; both now carry it. The "Python Arena, seed 1" reproduction of the stall has **no committed script or data** (NOT VERIFIED); M3.0's reset-home revisits it. **Also:** the fetch outcomes are not a fixed property of the recording. Each next fetch starts at the tick the page saw the previous one end (1688 or 1689), and DWA's stall is sensitive to it. The three review recordings completed red and green, red and green, and red and blue, against red alone in M2.11's. So "1 of 4" is one sample (`remeasure/seek/run_*`). |
| STATUS honesty: phone and usability pending Gautham | VERIFIED | The position table lists M1's phone performance, phone cold start and usability, and M2's phone and usability rows, as pending Gautham. `M2_RESULTS.md` marks both rows "Pending Gautham". Nothing unverified is marked met. |

## Claims in the M2 report that are false or overstated

1. **"Links: Every v1 URL form resolves with 0 console errors" / "Hygiene:
   0 console errors on all 14 public pages" (M2.10, M2.11).** True as
   measured, but the measurement left out the archive's own views. Opened
   directly, all six fail at `330df44`: plain "Live", "real robot" in Search,
   and a Live view that logs WebSocket errors. M2 retired the honest v1 views
   from `main` and replaced them at `/v1/` with the pre-M0 copy. ADR 0003
   recorded `v1/?view=live` as "not checked" instead of checking it. This is
   the substantive defect of this review, fixed under the owner's ruling.
2. **"the Arena's LiDAR is beam-for-beam Lab 2's (|e| median 2.2 mm)"
   (M2.9).** It joins two different comparisons: the identity is with the
   Nav2 map, while the 2.2 mm is against Gazebo's sensor. It also omits that
   86.7 % of beams fall within 5 cm. Corrected.
3. **Mission 5 `run15-quoted`** implied the reproductions reproduced run 15.
   They reproduced its mechanism, not its symptom. Corrected; "exact Run 15"
   stays unresolved.
4. **`M2_CLAIMS_COVERAGE.md`**: 5 evidence references were truncated by the
   generator. Only the document was affected, not the check.
5. **"Reproduced in the Python Arena (seed 1)"** (M2_RESULTS, "Found while
   measuring"): no committed script or data backs it. Not verified; not
   relied on.

## Fixes made (`[M2-fix]`, all on `v2/m2-whole-loop`)

- `013a0d6`:
  - README copied from the owner's file. §3 now lists the learner labels
    TESTED and UNRESOLVED; sha256 `20376086…911e86`, checked with `cmp`.
  - `CLAUDE.md`'s label list updated.
  - The parked labels idea and the M2 report's "deviation" marked as ruled.
  - Six dated plan-change-log entries.
- `22be3dc`:
  - `/v1/` is built from `9f58b83`: `build_v1_archive.sh`, `lab.yml`
    comments, and an amendment to ADR 0003.
  - `v1_links_check.mjs` also checks the six archive views.
  - The fidelity and claim wording fixes above; `FIDELITY_v1.md` and
    `M2_CLAIMS_COVERAGE.md` regenerated.
  - Evidence `docs/v2/data/m2/review/`.
- Later commits (listed under "After the fixes"):
  - the seek rows' 1-of-4 caveat
  - this report
  - the re-measurement data appended to `docs/RESULTS.md` and
    `M2_RESULTS.md`

## Risks

1. **The archive is built at deploy time**, so it can break as the toolchain
   ages. Owner decision: it becomes a built artifact on `v1-site` in M3.0.
2. **CI does not check M2's determinism claim.** It replays M1's first 10
   sessions, not M2's 100 whole-loop sessions (localisation, mapping,
   controllers, fetch). A change that breaks whole-loop determinism would
   pass CI.
3. **M2's measurement and determinism helpers are outside the repo**
   (`~/coco_lab_m2_ws/bin/m211_measure.sh`, `det_loop.sh`,
   `webkit_mesa.sh`). M2_RESULTS "Reproduce" lists the underlying commands,
   but reproducing the exact run needs those scripts.
4. **`seek_check.mjs` and `coldstart.mjs` record no renderer string**, so
   their GPU claim rests on the launch flags. This review recorded the
   renderer with a separate probe at the start and end of its measurement
   session.
5. **The fetch mission inherits a stalled pose**: 1 of 4 fetches in the seek
   recording. M3.0's "reset home" addresses it.
6. **`missions.py` exits 0 on an unresolved reference.** The CI path
   (`build_catalog.py`, `test_missions.py`) fails correctly, but the script
   alone looks green.

## Recommendation

**MERGE AFTER FIXES — every fix is done.**

M2's engineering claims hold up under independent re-measurement:
- the three suites, with the deleted tests accounted for one by one
- determinism across four engines
- the 16 byte-for-byte replays
- 98 / 98 claims with resolving evidence
- every agent budget, re-measured on the GPU after the reboot

The one substantive defect was the `/v1/` archive putting back the pre-M0
public copy and a noisy Live view. It is fixed under the owner's ruling and
now checked in CI. The wording conflations and the two overstated mission
claims are corrected.

The phone and usability rows for M1 and M2 remain **pending Gautham** and
are not affected by this merge.

## After the fixes (final head)

See the final-head row below, filled in after the last push.
