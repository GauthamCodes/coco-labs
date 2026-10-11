# Review of M3 (PR #22): independent reviewer session, 2026-10-11

README §9.10 review of **M3 · Play and Case Files**, by a session that did
not build M3. It was given the repository, `README.md` (revision 2, the
owner's file at `~/Downloads/README.md`), the M3 report (PR #22's body,
`docs/STATUS.md`, `docs/v2/M3_RESULTS.md`) and the owner's prompt for this
session (Part A), and treated every claim as a claim to verify.

**Where.** A fresh clone of `GauthamCodes/coco-labs` at
`~/review/coco-labs-m3`, branch `v2/m3-play-casefiles`, head **`7052aa8`**
(as claimed). Its own overlay `~/review/ws_m3` (`scripts/build_overlay.sh`,
12 packages) and its own `npm ci`; its own production build with `/v1/`,
served like Pages on 127.0.0.1:4224. Helpers in `~/review/bin_m3`; the
scripts that produced this review's evidence are committed in
`docs/v2/data/m3/review/scripts/`.

Borrowed read-only: Node 24.21.0 (`~/coco_v2_ws/node`), the test venv
(`~/coco_labs_ws/test_venv`), the MoveIt prefix, the Playwright browsers,
`~/coco_lab_m1_ws/bin/webkit_run.sh`, and the raw recordings in
`~/coco_lab_runs/` (read, never written). ROS domain 88. No simulator,
Isaac or robot-project batch ran at any point (checked before every heavy
job). Fixes were committed from the M3 worktree as `[M3-fix]` commits.

**Machine.** NVIDIA kernel module and userspace both **580.178.04**.
Headless Chromium 156 with the harnesses' GPU flags renders WebGL 2 on
**`ANGLE (NVIDIA Corporation, NVIDIA GeForce RTX 4050 Laptop GPU/PCIe/SSE2,
OpenGL ES 3.2)`**, not software (`docs/v2/data/m3/review/gpu/gpu_probe.json`).
Balanced profile. **AC power came and went during the session**; every
timed number below was taken on AC (each harness records it), and the
correctness checks that ran on battery say so.

**Leftover M3-session processes (permission 3).** Found:
- `m39_when_ac.sh` (PIDs 152338/152339), a waiter that would have started
  M3.9's full re-measurement the moment AC returned, concurrently with this
  review's. **Stopped** (`kill` by PID). It had not run again: its only
  output is the 12:36 partial M3_RESULTS already reports.
- `serve_dist.mjs` on :4214 (PIDs 10965/10966), the M3 worktree's static
  server: idle, so **not stopped**; this review used it to serve the
  worktree's D6 builds.
Nothing of the robot project was touched.

| Item | Verdict | Evidence |
|---|---|---|
| Head SHA | VERIFIED | `git rev-parse HEAD` in the fresh clone = `7052aa88d0a7…`. |
| Diff: what was deleted | VERIFIED | `git diff --name-status main...v2/m3-play-casefiles`: **243 A, 40 M, 0 D**, 0 renamed. Nothing deleted, so no evidence deleted. |
| `docs/RESULTS.md` append-only | VERIFIED | `main`'s copy (460,055 B) is an exact byte prefix of the branch's (470,349 B). |
| Tests: 3,498 / 396 / 168 | VERIFIED | Fresh clone, clean overlay: packages **3,498 / 0 / 0** (12 packages; coco_moveit_config's 7 pick-pose tests skip without the MoveIt prefix in the overlay, a known invocation fact, and pass 12 / 12 with it). `lab_web` typecheck clean, vitest **396 / 0 / 0** (37 files). Build tools **168 / 0 / 0**. Generated TypeScript current. `suites_review.txt`. |
| CI on PR #22 | VERIFIED at `7052aa8` | `gh pr checks 22`: `build-and-test`, `coco_lab in a plain venv`, `lab_web`, `lab_web in Chromium, Firefox and WebKit` pass; the Pages deploy is skipped (main only). |
| 100 Case Files, 41.5 MB | VERIFIED | 100 `.mcap` files, **41,486,529 B**, the largest `lab2_rl_fidelity_1_tour` 2,780,072 B. |
| Each cites a source-bag checksum that matches | VERIFIED, **73 / 73** recomputed (the prompt asked for ≥ 20) | Each lab's definition re-implemented independently (`scripts/checksums.py`) and recomputed from `~/coco_lab_runs/`: Lab 1's directory hash 3 / 3, Lab 4's `_sha_dir` 16 / 16, Lab 5's `bag_0.mcap` 54 / 54. Each equals both the index and the committed file that cites it (`checksums.json`). **Also:** every Case File's own embedded manifest (inside its zstd chunks) cites every file of its source bag(s) by the sha256 that file has on disk today: **100 / 100** (`embedded.json`). |
| The CI evidence check covers Case File text | VERIFIED | Mutations in a scratch clone, never committed (`mutations.json`): an explanation sentence with no evidence fails `build_catalog.py` ("explain[0] cites nothing"); with an evidence reference to a non-existent RESULTS.md heading it fails ("0 headings begin with that text"); the unmodified and restored copies pass. |
| Mission 7's scrub ticks derive from the recordings; the CI check exists | VERIFIED | Moving the hook beat's tick from 128 to 129 fails the build: "tick 129 is not lab5_mislocalised_dwb_1's refusal moment, tick 128". `casefile_moments.test.ts` (in vitest) re-derives `moments.json` from the committed Case Files. |
| Every star threshold equals a reference algorithm's result | VERIFIED for four challenges, **overstated** for the fifth; corrected | Recomputed independently (`scripts/thresholds.py`): my own Dijkstra gives all 3 Beat-the-planner optima; my own permutation costing and nearest-first / most-likely-first policies give all 4 Search-the-bays optima and both policy ratios: **7 / 7 levels** equal to `levels.json`. The Case File detective's stars are stated bands (2, 1, 0.5 s) around a rule's exact answer — CHALLENGES.md's detective section said so, but its header and M3_RESULTS said "every star threshold" is a reference algorithm's result. Corrected (`bc905b6`). |
| Scores never reward luck; Search the bays scored in expectation | VERIFIED | `play._score_bays` scores `regionsearch.plan_cost(...)['expected']` over the prior; no RNG is reachable from it (`run_search`'s `random.Random` is not called by the scorer). The score ratio is "never the sampled outcome". |
| ≥ 25 challenge links reproduce in Chromium, Firefox and WebKit; `coco verify` | VERIFIED, **25 / 25** in each | A stratified sample of M3.6's committed submissions (5 per challenge, `subs25.json`), scored fresh in Chromium on the review build: **25 / 25 result hashes equal M3.6's committed hashes**. Every link reproduced exactly with 0 errors in **Chromium 156 25 / 25, Firefox 157 25 / 25, WebKit 27.2 25 / 25**; `coco verify` (Pyodide 314.0.7 / Node 24.21.0) **25 / 25** (`repro25/`). |
| The level-hash fix covers every place a float is serialised | VERIFIED; **test was missing, added** | Every hash a link or `coco verify` compares goes through `play.canonical` (`_plain`), except the World Spec hash, which goes through `worldspec.canonical_bytes`, whose `normalize` casts every number with `float()` — so it is JS-safe too. The existing test covered the first level of three challenges. Added `test_every_float_that_reaches_a_hash_survives_javascript` (`a67b02a`): all 16 level hashes, the World Spec hash and one result per challenge after a JavaScript round trip. It fails on the first level hash with `_plain` disabled. |
| 1.3e-8 m is the worst CPython–Pyodide ATE difference across all reference answers | **FALSE**; the tolerance is sound; corrected | Scored all 24 map drives (M3.6's 20 submissions and the 4 reference drives) in CPython and in Pyodide-in-Node (`map_engines.json`). Over the 20 submissions the worst is 1.3e-8 m (as M3 said). Over the **reference drives it is 1.55e-7 m** — on Forty metres' tour, whose ATE **is** the three-star threshold — and distance differs by 1.0e-6 m. F1 and the scored tick are identical in all 24; stars agree 24 / 24. Without the tolerance, the reference drive would miss its own third star in Pyodide; with `MAP_ATE_EPS` = 1 µm it earns it with a 6.5× margin (not the ~77× the docs implied). **Can the tolerance hide a real disagreement?** It applies only to ATE at the three-star boundary, never to F1 or the tick; it lets a drive whose ATE is at most 1 µm worse than the reference tour's take that star, against ATEs of 0.15–0.87 m; and CI's `play_reference_check.mjs` replays every reference under Pyodide. Docs corrected (`bc905b6`). |
| Pose-graph long tour (F1 0.316 vs 0.580) labelled UNRESOLVED wherever a learner can see it | NOT VERIFIED as asked: **a learner could not see it at all**; fixed | No page showed it, while mission 4 invites learners to switch the Arena to the pose graph and says loop closure "nearly always helped". Added as an UNRESOLVED claim on that beat (`04ba7a8`). **Also:** its only evidence is prose (RESULTS.md M3.5, IDEAS.md): no committed data file or script reproduces the 0.316. |
| The evidence badge in every mode | VERIFIED | `modes_check.mjs` on the review build: **23 / 23** pages — the four modes at 1280 × 900 and 390 × 844, the badge visible in the viewport, the comparison drawn with one header, 0 console errors (`views/modes_check.json`; run on battery, a correctness check). |
| The narrowed storage guard | VERIFIED | `src/` uses `localStorage` in exactly one file, `src/play/best.ts`, three times, each inside `try`; no cookie, `sessionStorage`, IndexedDB or beacon anywhere. `site.test.ts` and `check_dist.mjs` enforce it (one `setItem` in the build, in the chunk with the `coco.play.best.v1.` key). |
| The outstanding re-measurement on AC (n ≥ 10) | VERIFIED: every budget met | On AC, balanced, ANGLE on the RTX 4050 (probed at start and end; `remeasure/`):<br>• **M1 stress scene:** 60–61 fps in every one of 100 s (10 × 10 s).<br>• **Goal after a planner change:** median **48.9 ms**, p95 63.9, max **67.7**, 25 / 25 under 100 ms. The harness first timed out on the second goal: M3.7's taller page scrolls when a planner button is clicked, and the harness's goal point fell outside the canvas. Harness fixed (`ff05403`); the product was not at fault.<br>• **Seek, 5-minute fetch recording:** max **35.1 ms** over 30 seeks in 3 recordings. Fetch outcomes: red done / green done / blue under way, twice; red **failed** / green done / blue under way once.<br>• **Cold start, emulated 4G, n = 10:** first visible computation median **3,140 ms** (2,984–3,253); live model ready median **7,997 ms** (7,818–8,148).<br>**Against the background job:** it never ran again (stopped before AC returned). Its only output, M3.9's 8 M2-scene runs (58–61 fps), covers a different scene; nothing to compare. |
| D6: Case File first frame ≤ 2 s on emulated 4G, 100 / 100 | **MET after the fix** (was 97 / 100) | See "The D6 change" below. 100 / 100 within 2 s, worst **1,828 ms**, median 745 ms; 0 console errors (`d6/casefile_check_4g.json`). |
| All 22 old URL forms and `/v1/` resolve with 0 console errors | VERIFIED | `v1_links_check.mjs`: **22 / 22** forms and `/v1/`'s **6 / 6** views, 0 console and 0 page errors, no "real robot". `console_check.mjs`: every public view 0 console errors, 0 page errors, 0 sockets on load (`views/`; run on battery). |

## The D6 change (A.3)

The owner's decision D6: Case File scans load after the first frame. Two
layouts were built for all 100 Case Files, both lossless, and measured on
the same 12 Case Files (the three that missed plus nine across every lab),
emulated 4G, three interleaved rounds, on AC:

| | M3 one file | Split (two files) | **Ordered** (one file, scans last) |
|---|---|---|---|
| First frame, worst | 3,240 ms | 1,907 ms | **1,805 ms** |
| First frame, median | 1,225 ms | 915 ms | **884 ms** |
| Scans ready, worst | — | 3,229 ms | **3,008 ms** |
| All 100, bytes | 41,486,529 | 41,351,787 | **41,230,918** |

Per file it was mixed: split was faster on both Lab 3 tours and Lab 5's
MPPI static room, ordered on the worst file and the Lab 2 kidnaps. Ordered
was chosen for the worst case, the median, the scans and the size, and
because it keeps ADR 0005's one file and one sha256 per Case File. The
split code was removed. ADR 0005 is amended with these numbers
(`d6/layout_compare.json`).

**Lossless, in CI.** `lab_web/casefiles/lossless.json` holds each M3
file's sha256 and content digest (every message's bytes, log time, publish
time and sequence, per channel, with the schemas). `casefile_layout.test.ts`
requires every Case File to hold exactly that content, its scans last, the
sha256 its index names, and a manifest citing its source bag by sha256.
The layout tool and `pack_casefiles.mjs` refuse a file whose digest
differs. `casefile_replay.test.ts` shows that once the scans arrive, every
tick shows exactly the scan it showed in M3. The rewritten files are
byte-identical to the ones measured.

**All 100, ordered build, emulated 4G, on AC:** **100 / 100** within 2 s;
worst 1,828 ms (the robot_localization tour, 3,244 ms at M3.9), median
745 ms, p90 905 ms; scans attached by 3,013 ms at worst; seek ≤ 35.2 ms;
0 console errors. Unthrottled: worst 220 ms.

## Claims in the M3 report that are false or overstated

1. **"CPython and Pyodide differ by up to 1.3e-8 m in ATE"** (M3_RESULTS,
   CHALLENGES.md, `play.py`). True for the 20 submitted drives; **false
   for the reference drives**, which set the thresholds: 1.55e-7 m on the
   very drive whose ATE is the three-star threshold. The 1 µm tolerance
   still covers it, with a 6.5× margin rather than the ~77× implied.
   Corrected.
2. **"Every star threshold [is] a reference algorithm's result on the
   level"** (M3_RESULTS, CHALLENGES.md's header). Overstated: the Case File
   detective's stars are stated bands around a rule's exact answer, as its
   own section said. Corrected.
3. **"The pose graph's long-tour result is reported"** (implied by
   README §2's list): it was reported in docs only; no learner could see it,
   while mission 4 invites learners to use the pose graph. Now an UNRESOLVED
   claim in mission 4. Its only evidence is prose (RESULTS.md M3.5): no
   committed data or script reproduces 0.316.
4. **The level-hash fix's test** covered 3 of 16 levels and no World Spec
   hash. Not a false claim, but the fix was not proven where it was said
   to apply; the missing test is added.
5. **"Regressions: … every M2 budget still met"** could not be claimed at
   M3.9 (AC lost); M3_RESULTS said so honestly. Completed here, all met.

## Fixes made (`[M3-fix]`, all on `v2/m3-play-casefiles`)

- `a67b02a` the float-serialisation test (all 16 levels, the World Spec
  hash, one result per challenge).
- `04ba7a8` mission 4: the Arena pose graph's long-tour result, UNRESOLVED.
- `bc905b6` the two overstated Play claims corrected; `map_engines.json`.
- `137a386` **D6**: the ordered layout, its loader, the lossless record and
  test, ADR 0005 amended, CASEFILES.md and IDEAS.md.
- `ff05403` the goal-latency harness scrolls the canvas into view.
- The commit adding this report, the review evidence
  (`docs/v2/data/m3/review/`) and the appended results.

## Risks

1. **The worst Case File has 0.17 s of margin.** The robot_localization
   tour's first frame is 1,828 ms against 2,000. A longer recording, or a
   heavier first-frame channel (its 9,339 estimate messages are most of
   its first part), would cross the budget; M4.7's 3D reconversion must
   re-measure it.
2. **The map challenge's three-star tolerance has a 6.5× margin**, not 77×.
   A Pyodide or CPython upgrade that moves the reference tour's ATE by more
   than 1 µm would cost that drive its own third star; CI's
   `play_reference_check.mjs` would catch it.
3. **The fetch sequence in the seek recording is not one fixed outcome**
   (one red fetch failed in three recordings). Not used as a showcase.
4. **The 0.316 pose-graph result has no committed data or script**, only
   prose; it is labelled UNRESOLVED and must not be cited as MEASURED.
5. **Harnesses outside the repository.** The M3 builder's
   `~/coco_lab_m3_ws/bin/*` and this review's `~/review/bin_m3/*`; the
   review's own scripts are committed under `review/scripts/`.
6. **Power.** AC came and went twice during M3 and this review; the
   harnesses now abort when AC drops, but an unattended run can stall.

## Recommendation

**MERGE AFTER FIXES — every fix is done.**

M3's engineering claims hold under independent checking: the suites, the
100 Case Files and all 73 cited checksums (recomputed, not sampled), the
CI evidence check, mission 7's derived ticks, the challenge thresholds,
luck-free scoring, 25 links in three browsers plus `coco verify`, the
storage guard, every old URL, and every M2 budget re-measured on AC. Two
claims were overstated and one unresolved result was invisible to
learners; all corrected. The one failed criterion, the Case File first
frame, is met 100 / 100 after the owner's D6 change.

The phone baseline, M1–M3's phone rows and the usability test remain
**pending Gautham** (decision D5: usability is consolidated into M4).
