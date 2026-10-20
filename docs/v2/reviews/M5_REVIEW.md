# Independent M5 review

Reviewed PR #25, `v2/m5-focus`, `fe9d544faafa13f0bebe226cd0233d0dbde4a03a`.
Review worktree: `/home/gautham/coco_labs_ws/worktrees/m5-review`, branch `v2/m5-review`.
Started 2026-10-19; resumed on balanced/AC 2026-10-20 after low battery.
No milestone merge, release, deployment, evidence deletion or M6-worktree modification.

## Verdict

**Not ready to merge:** an already-open document can mix deployment versions.
The real-phone and five-person usability rows also remain open, and merging #25
publishes v2 to the public site. Small review fixes are isolated in the review-fix PR.
Completed reviewer reruns and measured-artifact identity are recorded below.

## Findings

| Priority | Finding | Disposition / evidence |
| --- | --- | --- |
| P1 | An open build-A document can be claimed by worker B and receive B's unversioned static data. The hard-reload test does not cover this state. | **Unfixed.** [Actual A/B observations](../data/m5/review/update-open-tab-ac3/checks.json): `openDocumentMixed: true`, `hardReloadConsistent: true`. The probe is a static JSON asset, representing the same versioning issue as unversioned runtime/data URLs. This proves mixed versions, not an observed wrong planner result. Choose a policy for running/unsaved sessions, then pin assets per document or coordinate an update. A forced reload would change active-run behavior. |
| P1 | PR #25's site-build CI fails because the source audit reads imported Python bytecode, whose embedded checkout filename contains `coco-labs`. | Fixed by auditing text sources. [Original CI failure](../data/m5/review/ci-original.log); [focused tests](../data/m5/review/focused-web.log). |
| P1 | Determinism's `--ref` silently replaces a fresh Node run; its pass expression ignores final-chain differences and browser page errors. | Fixed. [Original false-pass reproductions](../data/m5/review/determinism-verdict-before.json), [four regression tests](../data/m5/review/determinism-verdict-tests.log). The retained original closure Node output independently matches its saved reference: [100 sessions /15000 hashes, zero hash/chain differences](../data/m5/review/previous-node-independent-comparison.json). This is a verifier defect, not evidence that those saved hashes differ. |
| P1 | The title calls warm-up inside the first-render callback, before that frame is presented, without the owner-required idle/first-input gate. | Fixed: readiness, a frame yield, then idle or first input. Without idle support, wait for input. The preload attempt regressed startup through duplicate requests and was removed; native streaming remains. [Startup rationale and pinned native streaming loader](../data/m5/review/STARTUP.md). |
| P1 | STOP is hidden by the portrait card and blocked by the keyboard handler while a dialog/control has focus. | Fixed: reachable STOP in portrait, Settings and game menu; STOP binding precedes modal/control guards. Worker acknowledgements, zero velocity and latched state are checked in the viewport evidence. |
| P1 | Secondary-finger STOP is missed while the first finger holds the joystick. | Fixed with pointer-down STOP and suppression of the subsequent click so it cannot release the latch. [Before](../data/m5/review/stop-driving-phone-diagnostic.json), [after](../data/m5/review/stop-driving-fixed.json): recorded STOP, zero velocity, latch retained. |
| P2 | Navigating from Settings to Compare leaves the modal open over the destination. | Fixed: close Settings on navigation. [Reproduced obstruction](../data/m5/review/desktop-compare-settings-stuck.png), [typecheck](../data/m5/review/typecheck-navigation.log). |
| P2 | M5.3 moved substantial code rather than finishing its decomposition. | Reported, not refactored: `sceneCore.ts` 941 lines, `render/Renderer.ts` 957. [Inventory](../data/m5/review/code-shape.json). No tracked `node_modules`, RL root-script leftovers or remaining source TODO/FIXME claims found. Corrected the stale four-mode comment in ModeNav. |
| P2 | Deployment is automatic on main and does not depend on the browser job. | `.github/workflows/lab.yml:225–244`: push to main, `needs: [coco-lab-venv, lab-web]`, `actions/deploy-pages@v5`. No release or announcement step gates publication. Workflow left unchanged. |

## Claims audit: all 15 README §7 rows and every acceptance “Met”

Of 15 rows: **6 confirmed**, **6 corrected/qualified** (Focus, Title, Cold, JavaScript, Determinism, Accessibility), **1 unsupported as an exact-head claim** (Hygiene), **2 pending** (Phone, Usability). Original Hygiene evidence itself is present. Every cited file exists. [Targeted evidence inventory](../data/m5/review/evidence-audit.json)
and [extracted numbers](../data/m5/review/numeric-claims.json) retain the source
commit references and conditions. Scripted `passed` fields were not treated as
performance-budget verdicts. Original numeric observations match the report.

| Row | Audit / qualification |
| --- | --- |
| Focus | Original evidence confirms 7/7/8/1 and all 24 game layouts at ≤8, without scroll. Review adds portrait STOP, making that count 2. |
| Title | Original desktop 2002.1–2028.2 ms and emulated landscape 2214.6–2616.8 ms are present. New startup code requires the new runs below. |
| Cold | Original desktop 9606–9787 ms; emulated landscape 9942.7–10161.4 ms. The two >10 s runs were disclosed. Owner accepts this emulated near-miss; it is not a real-phone pass. |
| Warm | Default 2680.5 /2620.5 /2694.2 ms are present. Optional terrain 3132.5 /3752.7 /3223.4 ms remain diagnostics under decision 3. The same file's old-cache snapshot still lists A and B; do not interpret it as universal deploy consistency. |
| JavaScript | Original title-critical app+worker 271628 gzip bytes and interpreter 268476 are present. Under decision 1, the critical budget is met; the combined 540104 diagnostic is not the budget. Review bundle inventory is separate. |
| Frame rate | Named actual-GPU Play samples and corrected Intel Compare samples match their claims, balanced/AC. The final-candidate Compare evidence is `fps-final/checks.json`, median 60.02508511003504. Earlier Play samples are historical, not a new measurement of review code. |
| Determinism | Original 15000 v1 hashes, 4×100×150 v2 records and 166+1 verification observations exist. Verifier weaknesses are fixed; fresh reviewer results appear below. |
| Defects | Bounded-link/huge-first-tick regressions, v1/v2 coverage, race locks, applied floor-pick tests, CAD-first load and disabled/explained v1 source-repro workflow are present. The 100/100 ≤2 s Case File check explicitly shares the browser HTTP cache. |
| Links | 50 URL forms, six archive views, five replays and five zero-difference canvas captures exist. The URL JSON has `conditions: null`; it is functional evidence, not timing evidence. |
| Claims | Seven missions plus five story tours retain references; 165 library representations are supported by source/build checks. They are not 165 independent experiments. |
| Agent files | AGENTS is 178 lines; STATUS is below 200. Moves and six cache-only removals match the relocation evidence. `docs/RESULTS.md` has 25 added, zero removed lines over main in the original PR. |
| Accessibility | Scripted dark/light contrast, native focusability, actual grid/goal keyboard tests and CVD captures are present. These do not establish a formal accessibility audit or cover the STOP/navigation gaps found here. |
| Hygiene | The 30.162183333333335-minute, 34-round, zero-error/context-loss/driving-long-task result is present. It precedes the final candidate and review fixes; it is historical evidence, not an exact-head soak of this review branch. |
| Phone | Still pending. Latest reviewer ADB list is empty. Emulated results cannot satisfy this row. |
| Usability | Still pending Gautham. The protocol is unfilled; no owner observation or completion was invented. |

Freshness: closure evidence was committed after implementation, but several raw
runs predate the final cost-cache patch; M5_RESULTS acknowledges that boundary.
The raw startup, FPS and soak JSON do not all embed an exact source SHA. Do not
upgrade historical measurements into an exact-head performance attestation.
The reviewer measurements below identify the built artifact separately.

## Verification and measurements

[BUILD.json](../data/m5/review/BUILD.json) pins source SHA256s and the measured
build: title-critical gzip **271801 bytes**, interpreter **268476 bytes**. Two
clean production builds are byte-identical. Schema generation, typecheck, dist
and licence checks pass. Frozen v1: **84 files**, tree
`6857ff56a2646c0772a2b7780e50f2e1eb910ae289ae3a222fdab6ee9b2bde2b`.

- **3569 package tests across 12 packages**, **493 web tests /62 files**, **219 tool tests** pass independently. Logs: [packages](../data/m5/review/packages-final.log), [web](../data/m5/review/web-final.log), [tools](../data/m5/review/tools-final.log).
- [v1](../data/m5/review/ac/determinism-v1/determinism.json): **100 sessions ×150 =15000 hashes**, zero tick/chain differences.
- [v2](../data/m5/review/ac/determinism-v2/determinism.json): **Chromium, Firefox, WebKit and Pyodide-in-Node**, each **100×150**, zero tick/chain differences, zero page errors. Fresh Node output is compared, not replaced. These correctness jobs used parallel shards; their durations are not performance measurements.
- [CLI query verification](../data/m5/review/links-verified-ac.json): **153 distinct queries, 153 pass**, deduplicated from 315 cited occurrences. This differs from the report's occurrence counts without discarding any unique query.
- [Old URLs](../data/m5/review/urls-final/v1_links_check.json): **50 forms +6 frozen archive views**, zero failures/errors. [Replays](../data/m5/review/replays-final/replay_check.json): **5 pass**. [Canvas comparison](../data/m5/review/canvases-final/screenshots.json): **5 pass, zero differing pixels**. URL JSON has `conditions:null`; it is functional evidence, not a timing measurement.
- [Warm/default and cache](../data/m5/review/cache-final/checks.json): **2695.1 /2807.1 /2806.9 ms** desktop/emulated landscape/emulated portrait, all ≤3 s; hard reload/offline title/SW-disabled routes pass, zero errors or third-party requests, personal URLs excluded.
- [Fresh actual-GPU FPS](../data/m5/review/fps-review/checks.json), balanced/AC, uncontended: RTX high Play **60.076460950218895**, Intel medium Play **60.114764550587104**, Intel automatic four-pane Compare **60.00358230334103** median interval-normalized fps, zero errors/context loss. Samples fluctuate around the 60 Hz cap; this is not an every-interval minimum claim.
- [Title ordering](../data/m5/review/title-idle-final.json): ready before worker; no worker until first input when idle API is absent; native streaming succeeds; one WASM and one stdlib request.
- [Cold](../data/m5/review/startup-final-ac/checks.json), balanced/AC and uncontended: desktop title **2030.7 /1960.2 /1953.1 ms**, live **9997.8 /9828.4 /9845.3 ms**. Emulated Nothing Phone (1) landscape title **2172.8 /2202.0 /2186.4 ms**, live **10106.3 /10030.5 /9964.7 ms**. Desktop budget passes; emulated 2/3 misses remain disclosed.

Original, interrupted and faulty reviewer harness attempts are retained; only
explicitly completed corrected runs are used. The initial observer could not
JSON-encode BigInt columns, installed a fullscreen stub before a document root
existed, and could miss a brief STOP-source sample. Those were harness defects.
Corrected capture converts numeric columns, patches the prototype, records
worker STOP receipts and uses the actual Settings route.

## Visual review

My [screenshot index](../data/m5/review/SCREENSHOTS.md) links all four viewports,
with comparison against the original closure screenshots. Navigation title →
Play → Compare → Recordings → title completed at **1440×900, 844×390, emulated
Nothing Phone (1) 915×412 and 412×915**. Play has no page scroll; always-visible
controls are **7 /7 /8 /2**. Both two- and four-pane Compare pass eight layout
checks with one WebGL context. Recordings shows 165 representations.

Desktop/compact: Settings blocked navigation until the review fix; modal STOP
also required the fix. Landscape phone: the secondary-touch STOP bug was found
and fixed. Portrait: the rotate card originally hid STOP; it now contains one.
Fullscreen/orientation-denial paths and synthetic safe-area insets were tested;
these are emulation checks, not physical notch/OS verification. The portrait
Compare result cards use an internal horizontal scroller: not all pane metrics
are visible simultaneously. This is a usability observation, not page overflow.
No additional visual blocker appeared in my captures. Owner aesthetic feedback
is still absent. No fresh 30-minute soak was performed after these review fixes.

## Compare correctness

[Native event diff](../data/m5/review/browser-families-ac/reference-diff.json):
all six global algorithms dispatch the named algorithm and match headless
`coco_lab` exactly for the captured world/seed. Two panes: A* **4158** events,
Dijkstra **27781**; four panes add Greedy **3041**, Weighted A* **2567**.
BFS and the D* Lite adapter were checked separately. Labels are not merely
repeated screenshots of one algorithm.

Continuous control/localisation dispatch is correct, but **native CPython 3.12
and browser Pyodide Python 3.14 are not byte-equivalent**:
[raw diff and magnitude](../data/m5/review/browser-families-ac/reference-diff-magnitude.json).
Each family has **240/240 hash differences**. Localisation has 1176 numeric
differences, maximum **1.1102230246251565e-16**; control has 3153 numeric
differences, maximum **0.446011142799704** in a chosen-trajectory Y coordinate.
There are zero other nonnumeric/status differences. The interpreter/libm
boundary is a hypothesis, not a proven cause; this larger numerical question
is reported without changing models or goldens. The four-engine contract above
uses Pyodide throughout and passes. Native equivalence of continuous families
must not be claimed from that contract. [Independent headless Pyodide check](../data/m5/review/browser-families-ac/loop-pyodide-reference.json) **does exactly match all 8 continuous panes ×60 ticks**, excluding only `compute_ms`. Thus dispatch/reference behavior agrees within the shipped runtime; native portability is the unresolved boundary.

[Seven independently calculated Nav2 cells](../data/m5/review/browser/costmap-hand-check.json)
pass: obstacle cost254; inscribed distances .2/.25 m cost253; .3 m cost152;
.35 m cost92; .5 m cost20; .55 m outside inflation cost0. Calculation uses the
Nav2 exponential formula and brute-force obstacle distances, not the model's
costmap routine.

## Cache, privacy and code shape

Only static allowlisted assets enter the cache. Personal query URLs are excluded;
no third-party requests occur by default. The aggregate counter is unconfigured
and off. Production local storage access goes through `prefs.ts` and handles
failure. The review harness uses direct localStorage only to inject a test
sentinel. None of this fixes the open-document deployment mixing finding.

No tracked node_modules cache or moved RL root-script clutter remains. The
941-line scene core and 957-line Renderer still exceed the intended 600-line
split. No source TODO/FIXME claims were found. This decomposition is reported
rather than expanded into a broad review refactor.

## Decisions 1–3

All three owner decisions are in STATUS's plan-change log dated **2026-10-19**.
WASM/stdlib preload was tried once, measured, and removed after duplicate transfers regressed startup. The pinned Pyodide/Emscripten runtime already
uses streaming compilation with ArrayBuffer fallback; no replacement interpreter
loader was introduced. Interpreter warm-up is gated by title readiness and
idle/first input. Optional-world warm starts remain diagnostic, with no hidden
failure deletion. The failed attempt added 4,384,106 transfer bytes; desktop
live readiness was 13147.7 /13193.2 /13278.9 ms and emulated phone
13397.1 /13387.9 /13535.9 ms. All original attempt evidence is retained. The real phone remains the Phone row's deciding device.

## Merge readiness and next step

PR #25 CI: **fail**, original site-build audit job; other checks pass.
Review branch remote Lab runs [39287336347](https://github.com/GauthamCodes/coco-labs/actions/runs/39287336347) and [39350686634](https://github.com/GauthamCodes/coco-labs/actions/runs/39350686634) pass all three test jobs; deploy skipped. The latter tested `9819448`; final pointer/idle/preload rollback changes have the local checks above, not a claimed remote run at a different head.

Original PR #25 is textually mergeable into main. Original PR #24 head `984b2cf`
accepts a trial merge of `origin/v2/m5-focus` without conflict files; the temporary
worktree was aborted and removed. This is textual compatibility, not M6 acceptance.
[Original-head trial](../data/m5/review/m6-trial-merge.log). A second trial with all review fixes at `29690ee` also has **no conflict files**: [review-tip trial](../data/m5/review/m6-review-tip-trial.log). Both throwaway worktrees were removed.

**Merging PR #25 publishes v2 to the public site**, once the main build passes.
First merge the review-fix PR into M5, resolve the live-update consistency policy,
finish real-phone/usability launch gates, rerun #25's checks, then merge #25 only
by Gautham. Refresh and retest #24 against main afterwards. Do not merge #24 first.

Questions for Gautham: is native CPython continuous-family equivalence required beyond the existing four-Pyodide-engine contract? Should an update wait for the current run, or offer export
and reload? Connect the real phone for automatic USB/CDP measurement and complete
the existing five-person protocol before publication. None of those rows is done.

## Evidence handling

Large raw event/costmap captures remain physically intact. Lossless `.json.gz`
twins and [SHA256 inventory](../data/m5/review/compressed-evidence.json) are committed;
the reference readers accept either form. Interrupted and failed attempts are
retained and explicitly superseded. No generated Case File or history file was
read wholesale. No fixture/golden or algorithm implementation changed.
