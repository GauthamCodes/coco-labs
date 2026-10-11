# M3 results: Play and Case Files

M3 (the M3 prompt, `docs/v2/M3_PROMPT.md`) did eight things:

- made the v1 site a verified built artifact;
- converted the full stack's recordings into **Case Files** with an adapter,
  and showed each beside the Arena model;
- wrote mission 7, "Why did the robot fail?", on those recordings;
- built **Play**: five challenges scored by robotics metrics;
- proved every score can be re-computed anywhere (`coco verify`);
- made one app of four modes: Learn, Play, Sandbox, Case Files;
- drafted the launch;
- measured all of the above.

**Evidence class.** MODEL (the Arena, coco_lab and the browser) unless
marked STACK (the full ROS 2 stack in Gazebo, recorded). No physical robot
exists.

**Measurement standard:** the balanced profile on AC. Every harness records
the profile, AC state, governor and load in its JSON. Laptop: i5-13420H,
12 threads, RTX 4050 laptop GPU, NVIDIA 580.178.04. Headless Chromium 156
through ANGLE on the GPU unless stated; Firefox 157 and WebKit 27.2 where
named. Measured 2026-10-10 and 2026-10-11 on the M3 branch; files are under
`docs/v2/data/m3/`.

## Acceptance criteria (M3 B.3)

| Area | Criterion | Result | Evidence |
|---|---|---|---|
| Evidence | Every Case File and mission-7 claim has a resolving evidence reference; the CI check covers them | **Met.** `casefiles.py` checks every explanation sentence's label and evidence, keeps every unresolved question UNRESOLVED, resolves every RESULTS link, and matches the inventory to the committed data. `missions.py` checks mission 7's 8 claims and requires every Case File link's tick to be its derived moment. `build_catalog.py` runs both, so CI does: CI run 38121419092 was green | `lab_web/tools/casefiles.py`, `missions.py`; `test_casefiles.py`, `test_missions.py`; `test/casefile_moments.test.ts` |
| Adapter | Round-trip and fixture tests pass; every converted Case File cites its source bag checksum | **Met.** The adapter's fixture and round-trip tests (`coco_lab_ros` 143 / 0 / 0) and `mcap_write`'s (`coco_schemas` 223 / 0 / 0) pass. All 100 Case File manifests cite every source file by sha256. Every committed citation was checked by its lab's own definition, 73 of 73; the nine rebuilt in M3.4 were re-checked, 9 / 9 | `docs/v2/data/m3/m33/build.json`, `m34/build.json`; `docs/v2/ADAPTER.md`; ADR 0005 |
| Reproducibility | 100/100 challenge links reproduce exactly across Chromium, Firefox and WebKit; `coco verify` matches 100/100 scores | **Met.** 100 generated submissions, 20 per challenge, 93 valid and 7 breaking a rule on purpose, scored by Chromium's page. Every link, opened fresh, said "Reproduced exactly", with the same result hash: **Chromium 100 / 100, Firefox 100 / 100, WebKit 100 / 100**, 0 console errors. **`coco verify` 100 / 100** in Node, and 100 / 100 again on CI's runner | `docs/v2/data/m3/m36/` (`summary.json`, `links.json`, `reproduce_*.json`, `verify_node.json`) |
| Case File loading | Each Case File within budget; first frame ≤ 2 s and seek ≤ 100 ms on emulated 4G after the app is loaded | **Storage met; first frame NOT met for 3 of 100; seek met.** Storage: 41,486,529 B in all (budget 150 MB), the largest 2.78 MB (budget 20 MB). First frame on emulated 4G (9 Mbit/s, 170 ms), all 100: median **772 ms**, p90 1,548 ms, max **3,244 ms**. **97 of 100 within 2 s.** Over it: the robot_localization tour (2.78 MB, 3,244 ms) and both Lab 3 tours (1.9 MB, 2,371 and 2,362 ms). Seek, 10 per Case File: max **43.3 ms**. 0 console errors | `docs/v2/data/m3/m39/casefile_check_4g.json` |
| Regressions | All M2 budgets still met: fps, latency, cold start, the 16 replays, the 22 URL forms | **Partly re-measured: the laptop lost AC power** at 12:45 during the run. **fps, the M2 scene** (fetch mission, every lens's layers, M2 stress), 8 runs × 20 s, all on AC: **58–61 fps in every one of 160 seconds**; per-second p95 frame median 18.5 ms (17.0–33.1), 54 of 160 s above 21 ms (M2 review: 43 of 200). The 9th run ended on battery and is excluded. **The 16 replays:** 16 / 16 byte for byte (`coco_schemas`, in the suites). **The 22 URL forms:** 22 / 22, plus 6 / 6 `/v1/` views. **Not yet re-measured on AC:** M1's stress scene, goal latency after a planner change, seek on the 5-minute fetch recording, and cold start (4G and unthrottled) | `data/m3/m39/fps/` (runs 1-8 on AC; 9 ended on battery), `m39/remeasure_partial.log`; `m37/v1_links_check.json` |
| Hygiene | 0 console errors in all modes; phone width checked; suites and CI green | **Met.** 0 console and 0 page errors on all 21 views: the four modes, the Play and Case File pages, Live, `/v1/`. Phone width, 390 px: 11 pages across the four modes, no horizontal scroll, badge visible; with the comparison's single-header check, 23 / 23. Suites: packages **3,498 / 0 / 0**, vitest **396 / 0 / 0**, build tools **168 / 0 / 0**. CI green on the branch (run 38121419092, `27e1b8a`) | `m37/modes_check.json`, `m37/console_check.json`, `m37/phone/` |
| Phone cold start | A cold visitor sees computation within 10 s on a mid-range phone over mobile data | **Pending Gautham** (`docs/v2/PHONE_MEASURE.md`, section "M3") | — |
| Usability | 5 people complete one challenge, open one Case File and explain mission 7's failure, unaided | **Pending Gautham** (`docs/v2/USABILITY_TEST_M3.md`) | — |

## What M3 built, and what it measured on the way

- **The v1 site is a built artifact (M3.0):**
  - orphan branch `v1-site` at a pinned commit, Pyodide self-hosted;
  - the deploy verifies `SHA256SUMS` and the tree hash and builds nothing;
  - a weekly CI rebuild compares the content hashes.
- **Every fetch after the first starts from home (M3.0).** This fixed the
  M2 seek recording's stall. A latent `loc_arena.on_reset` bug was fixed
  with it: the filters restarted at the old belief.
- **Case Files (M3.3):**
  - 100 STACK recordings, each opened beside the Arena model on the same
    scenario;
  - every explanation sentence carries a label and evidence;
  - every unresolved question is kept UNRESOLVED.

  **A defect found by measuring:** the Localise lens knew only the model's
  estimator names, so a Case File's AMCL was never drawn, and a seek took
  574 ms. Estimates are now indexed by estimator, and the same seek takes
  31.8 ms.
- **Mission 7 (M3.4):** its scrub targets are derived from the recordings
  by a stated rule, never typed. Lab 4's B2 recorded no belief, so its
  Case File marks only where the mission gave up, and the mission says so.
- **Play (M3.5):** five challenges, 16 levels, every star threshold a
  reference algorithm's result on the level (`docs/v2/CHALLENGES.md`).
  Luck is designed out:
  - **Next node:** ties on (f, h) count, since insertion order can't be
    seen.
  - **Search the bays:** scored on the expected cost under the prior.
  - **Map the arena:** the drive is re-simulated from its input log.
- **`coco verify` (M3.6):** one scorer, `coco_lab/coco_lab/play.py`, in
  the page, in Node and in CPython.
- **One app, four modes (M3.7):** the evidence badge is in every mode, and
  Learn now has one per beat.

## Found while measuring

- **Level hashes changed through JavaScript (M3.6, fixed).** The page sends
  the levels through JavaScript, where `2.0` becomes `2`. So 80 of 100
  browser submissions named a level hash Node did not recognise. The
  canonical form now writes integral floats as ints.
- **CPython and Pyodide differ in the last digits of map metrics (M3.6,
  measured).** CPython reproduced 94 of 100 result hashes. The 6 were map
  drives: the same F1 and scored tick, ATE up to 1.3e-8 m apart, distance
  up to 1.7e-7 m. The thresholds come from CPython, so ATE is compared
  within 1 µm, and CI replays every reference under Pyodide: 18 of 18 earn
  exactly their stars.
- **The map meter never updated (M3.5, fixed).** Its interval depended on a
  getter recreated at every Arena render.
- **The Case Files comparison's panes drew the mode header again (M3.7,
  found in M3.8's demo frames, fixed).**
- **The Arena's pose-graph mapping (not investigated).** A 40 m tour mapped
  worse than a 20 m out-and-back: F1 0.316 vs 0.580. Parked in
  `docs/IDEAS.md`.
- **The first-frame miss is transfer-bound.** It costs about 0.6 s plus
  0.93 s per MB on emulated 4G, and scans are 44–69 % of the three long
  tours' bytes. The lossless fix is to load the scans after the first frame
  (`docs/IDEAS.md`). It changes ADR 0005's one-file format, so it is
  Gautham's decision, not taken here.

## Deviations

- **Two privacy guards were narrowed, not removed.** The M3 prompt requires
  local personal bests, so `check_dist.mjs` and `test/site.test.ts` now
  allow exactly one `localStorage` writer, `src/play/best.ts`, with every
  use inside `try`. Cookies, sessionStorage, IndexedDB and analytics are
  still refused.
- **The Case Files are committed under `lab_web/casefiles/`**, not
  `docs/v2/casefiles/` (ADR 0005).
- **Not attributed:** the browser's seek recording completes its first red
  fetch while the Python Arena with seed 1 stalls (M3.0).
