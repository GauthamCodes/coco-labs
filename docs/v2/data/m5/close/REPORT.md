# M5.11 closure evidence

Evidence classes: MODEL and TESTED; real-GPU browser performance is MEASURED on the named laptop, never physical-robot HARDWARE. Phone profiles are explicitly emulated.

The acceptance matrix lives in [M5_RESULTS.md](../../../M5_RESULTS.md). Raw results are retained here, including failed diagnostics. Conditions/driver accompany measurements. No evidence, golden trace, tag, release or working URL was deleted; no merge/release/deployment is performed.

## Re-checkable evidence

- `v1-flat/checks.json`: 100 sessions / 15000 per-tick hashes match the M1 reference.
- `determinism-v2/determinism.json`: Chromium, Firefox, WebKit, Pyodide-in-Node each 100×150, all match pre-optimization M5.1. WebKit required the existing user-space GStreamer libraries via a workspace wrapper; initial loader failures retained.
- `links-verified.json`, `links-delta-verified.json`: 166+1 stored links pass their own hash/encoding versions.
- `urls/`, `replays/`, `canvases/`: 50 forms plus six archive checks, five replays and five pixel-identical canvas checks.
- `focus/`, `games-focus/`: all four profiles, counts including world/joystick, 24 game layouts.
- `accessibility-final/`: actual CSS text contrast in dark/light, native keyboard focusability, reduced motion; `keyboard-proof/`: actual world numeric goal and grid key path.
- `fps/`: physical RTX high / Intel medium Play and initial failed Compare performance; `fps-compare-optimized/`: physical Intel four-pane replay after byte-equivalent presentation optimization.
- `soak-final/`: over 30 minutes, 34 rounds, zero errors/context loss/long tasks while driving.
- `cache-race-fixed/`: deploy refresh, old-cache cleanup, offline title, disabled worker, default warm starts and zero third-party requests. Older failed timing/worker-race diagnostics retained.

## Diagnostic corrections

`startup-final/` was interrupted after its inaccessible-name selector used “Vision” instead of the button's full accessible name. `startup-selector-fixed/` completed, but intentionally waiting for interpreter warm-up plus capturing a title screenshot before entering Play added avoidable interaction delay. `startup-immediate/` uses immediate entry as soon as the real title is drawn, without inserting a screenshot or waiting for the worker. All runs retain their actual timing and transferred-resource records.

The colour(srgb) browser parser originally treated normalized channels as 0–255; corrected scaling passes the real computed CSS. The joystick latency harness originally matched both the visible joystick and a hidden menu continuation; it now selects the visible Play joystick. The keyboard path initially compared fresh canonical JSON to an older legacy link hash; final checks compare the saved canonical reference and retain independent CLI verification of the legacy form. No frozen hash was changed to make a test pass.

## Review and pending gates

Desktop, compact and both emulated Nothing Phone (1) orientations remain available for Gautham's visual review. Blank pre-design notes remain unchanged; no observations exist. No feedback invented. Real phone not connected; five-person usability is owner-owned and unfilled. Both gate public launch, not this PR.

Full file relocations and the only six cache removals are listed in [M5.2 MOVES](../agent-overhead/MOVES.md); no additional moves/removals in M5.11. ADRs 0008/0009 and the dated E1–E8/continuation log retain their scope. Mapping comparisons stay parked for M7; no new idea implemented. Original balanced power profile unchanged.

## Session report

- Milestone/checkpoints: M5.0–M5.10 implemented previously; M5.11 final implementation code is `50817a3`, measurement evidence complete; [PR #25](https://github.com/GauthamCodes/coco-labs/pull/25) open and unmerged. Session began at `bf3fb3e`, branch `v2/m5-focus`, canonical checkout.
- Gautham notes: found blank, preserved; no pre-design observations, waived gate. N1/N2 design inputs addressed through current phone layouts; no phone measurement invented.
- Changes/evidence/classes: keyboard/contrast/visible-computation fixes, worker-update race and Compare pixel-preserving performance fix; MODEL/TESTED, MEASURED laptop and explicitly emulated phone evidence. Scientific Stack/Remote classes retained.
- Tests: setup baseline packages/web/tools 3523/436/192. Final web 493 (62 files), tools 209, focused harness-condition checks 56; typecheck/build/dist pass. Final package rerun: 3569 pass across all 12 packages; final web rerun remains 493 /62 files.
- Acceptance: each README row is explicitly classified in M5_RESULTS, including total-JavaScript and emulated-startup misses. Owner usability pending; real-phone row pending USB.
- Screenshots: [review index](SCREENSHOTS.md), plus retained checkpoint indices. No feedback recorded.
- Moves/removals: none this session; complete milestone list in M5.2 MOVES. Only six root test-cache files removed from Git, physical files retained.
- Decisions: ADRs 0008 and 0009; approved E1–E8 and five continuation entries dated 2026-10-14 retained. No new owner decision inferred.
- Deviations: no scope/order extension. Missing USB phone leaves real measurements pending. Source v1 reproduction documented/disabled per allowed fallback. Mapping comparison parked for M7 as allowed. Strict all-JavaScript payload remains over budget.
- Ideas: only existing mapping-comparison M7 item; none newly added. Stop condition: none.
- Questions: one existing USB connection request, no implementation input required. Next: review the open PR/CI and resolve the recorded acceptance limits before public launch. Public launch still requires owner gates and review of open budgets.
- Phone defaults: provisional 60 fps (optional 120), automatic tier starting medium/DPR 1.5, low 1/high 2. Emulation cannot decide real heat limits; no device connected.

Final phone emulation: 600.225 seconds / 594 samples; first-minute median 60 fps; ten-minute median 60, minimum 58, p05 60; 20 touch trials median 82.90000000596046 ms; no errors, losses or reloads. Package validation ran at nice 15 restricted to cores 8–11 during the phone run; after completion the package runner/model test was permitted cores 0–7. This is not an isolated physical-phone benchmark or a heat measurement.

The final Compare cache also tracks emitted costmap-batch revision, independently of the trace cursor, so newly received costs invalidate the static colour buffer. The stronger byte-oracle corpus draws high PRNG bits to vary all trace states rather than relying on correlated low bits. Typecheck and all three pixel tests pass after this review.

## Final candidate confirmation (`00a42aa`)

Final web rerun: 493 tests /62 files pass (`vitest-close.txt`); all 12 package suites 3569 pass (`packages-final.txt`); tools 209 pass (`tools.txt`), harness conditions 56 pass. Typecheck/build/dist/licences pass. Final Compare browser check: eight layouts, one context each, zero errors (`compare-final/checks.json`); actual Intel four-pane top-down replay median 60.02508511003504 fps, minimum 59.42198613471046 (`fps-final/checks.json`). Original before/after optimization timings remain preserved.

Desktop Chrome CDP reports no manifest or installability errors (`installability.json`), after installing the static service worker on localhost. This is not an actual Android installation claim. Both emulated orientations and actual low/high GPU results remain separate. Final title app/worker size is 271628 gzip bytes, interpreter JavaScript adds 268476; total 540104 remains over the strict full-JavaScript budget.

No stop condition fired. Source fixes committed as `50817a3` and `00a42aa`; measurements on the first candidate remain labelled by their captured build, with final Compare and bundle checks after cost-batch invalidation. Later patch is view-only; no model/determinism bytes changed.

## Submission

Branch pushed; [PR #25](https://github.com/GauthamCodes/coco-labs/pull/25) open into main, not merged. Implementation `00a42aa`, evidence `6d984fd`; this documentation follow-up records submission. Remote CI jobs were running/queued, not claimed green. Local suites and all measured limits remain as recorded. No release, publication, owner-row completion or protected deletion. End-of-session repository must be clean and synchronized after this documentation commit; exact final SHA is in the user report/Git history.
