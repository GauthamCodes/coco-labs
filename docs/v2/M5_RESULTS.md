# M5 · Focus and polish — acceptance results

Status: M5.0–M5.11 implementation and measurement evidence on `v2/m5-focus`; [PR #25](https://github.com/GauthamCodes/coco-labs/pull/25) is open and unmerged; remote CI was running/queued at submission. Implementation code `00a42aa`. No merge, release or public launch is authorized by this report. Owner usability and real-phone gates remain open.

## Conditions and interpretation

Measurements name the actual device and include start/end conditions in the raw JSON. Laptop: Intel Core i5-13420H, RTX 4050 / NVIDIA 580.178.04; Intel RPL-P integrated GPU through ANGLE Vulkan, Mesa 25.2.8-0ubuntu0.24.04.2. Balanced profile on AC; original profile balanced, unchanged. No robot/simulator batch was active. Software-rendered results are never substituted for physical-GPU results.

“Emulated Nothing Phone (1)” means Chrome Android UA, 412×915 portrait / 915×412 landscape, DPR 2.625, touch/mobile, CPU 4× proxy, and emulated 4G for starts. It uses the laptop GPU, does not emulate the Adreno or phone thermals, and cannot satisfy the real Phone criterion. Hardware facts in [PHONE_PROFILE.md](PHONE_PROFILE.md) remain assumptions.

## README §7 acceptance matrix

| Area | Result | Evidence and limits |
| --- | --- | --- |
| Focus | Met | [Final layout check](data/m5/close/focus/focus.json): 7 desktop, 7 compact (844×390), 8 emulated phone landscape, 1 portrait controls; canvas/joystick included; no page scroll. [24 game layouts](data/m5/close/games-focus/decisions-focus.json). |
| Title screen | Met | [Six fresh-context runs](data/m5/close/startup-immediate/checks.json): desktop 2002.0999999940395–2028.2000000029802 ms; emulated phone landscape 2214.5999999940395–2616.7999999970198 ms. |
| Cold start | Met on laptop; emulated phone live-model budget not met in 2/3 runs | [Cold starts](data/m5/close/startup-immediate/checks.json): desktop live model/3D interactive 9606–9786.999755859375 ms. Emulated landscape live model 9942.699951171875–10161.39990234375 ms; all 3D interactive under 12 s. No interpreter-only readiness substitution. |
| Warm start | Met for default world | [Corrected deploy/cache check](data/m5/close/cache-race-fixed/checks.json): default model ready 2680.5 ms desktop, 2620.5 ms emulated phone landscape, 2694.199951171875 ms portrait. Optional terrain diagnostics exceed the budget and remain visible below. |
| JavaScript | App-only budget met; total including background interpreter NOT MET | [Final CI dist inventory](data/m5/close/dist-close.txt): title app plus worker 271628 gzip bytes, separate Three.js chunk. Interpreter JavaScript adds 268476 bytes, giving 540104 total while warming on title. The strict all-JavaScript reading exceeds 350000; no waiver inferred. |
| Frame rate | Met at nominal 60 fps Play; Compare exceeds 30 | [Actual GPU Play samples](data/m5/close/fps/checks.json): RTX high median interval-normalized 59.96230940521038 fps, Intel medium 60.01500375153408 fps; both median submitted-frame count 60. [Intel four-pane top-down replay after fix](data/m5/close/fps-compare-optimized/checks.json): median 60.019707963969246, minimum 59.30253142164696 fps, automatic tier high. These are sampled rates around a 60 Hz cap, not claims every arbitrary interval contains exactly 60 frames. |
| Determinism | Met | [v1 comparison](data/m5/close/v1-flat/checks.json): all 15000 saved M1 hashes unchanged. [v2 comparison](data/m5/close/determinism-v2/determinism.json): 100 sessions ×150 ticks on each of Chromium, Firefox, WebKit and Pyodide-in-Node; zero differences against the pre-optimization M5.1 reference. [166 stored links](data/m5/close/links-verified.json) and [one later delta](data/m5/close/links-delta-verified.json) verify under their own versions. Golden fixtures untouched; package suites cover them. |
| Defects | Met | [M5.1 evidence](data/m5/defects/): bounded fields and huge-first-tick regression, state-hash v2 coverage/compatibility, race locks, real mesh first, perspective floor picking, documented disabled source-repro workflow. Frozen v1 deployment remains intact. |
| Links | Met | [50 forms + six archive checks](data/m5/close/urls/v1_links_check.json), zero console errors; [five replay checks](data/m5/close/replays/replay_check.json), [five identical canvas checks](data/m5/close/canvases/screenshots.json). |
| Claims | Met | Build-tool claims checks pass; twelve tours retain committed references; all 165 recording representations preserve source/evidence class, including failure and unresolved outcomes. See [Compare](data/m5/compare/REPORT.md) and [Recordings](data/m5/recordings/REPORT.md). |
| Agent files | Met | AGENTS 178 lines, STATUS below 200. [Full relocation/cache list](data/m5/agent-overhead/MOVES.md); no evidence removed. |
| Accessibility | Met in scripted checks; visual review pending Gautham | [Twelve dark/light pages](data/m5/close/accessibility-final/checks.json): text contrast checks and native focusability pass, reduced motion honoured. [Actual keyboard goal/grid tests](data/m5/close/keyboard-proof/checks.json). Computation colours retain their fixed meanings; [colour-vision reference captures](data/m5/screens/reference/README.md) show protanopia/deuteranopia, with outlines/difference patterns carrying additional meaning. No claim of a formal independent accessibility audit. |
| Hygiene | Met | [30.162183333333335-minute actual-GPU Play session](data/m5/close/soak-final/soak3d_nvidia.json): 34 rounds, zero console errors, zero context loss, zero driving long tasks. Later optimization affects only Compare presentation. |
| Phone | Pending: connect real phone over USB | No device in latest ADB list. Emulation is recorded separately and cannot mark this row met. Agent owns automatic USB/CDP measurement, per owner amendment. |
| Usability | Pending Gautham; public-launch gate only | [Unfilled five-person protocol](USABILITY_TEST_M5.md). No owner-owned row marked done. Implementation/PR may proceed under the explicit waiver. |

## Changes made during closure

- Corrected visible-computation instrumentation: off overlays and the portrait rotate card never produce a false first-computation mark. Selecting a visible scan does.
- Completed keyboard access: focused world/joystick, numeric goal alternative, arrow-key grid cursor/selection, preserved Tab autonomy binding without trapping normal focus navigation, and keyboard cost lookup in Compare.
- Added theme-specific AA text-role colours while preserving computation meanings. Actual browser checks cover both themes.
- Fixed a worker-update race: a retired service worker cannot recreate its old static cache after activation cleanup. Deploy A/B, offline reload, disabled-worker use and zero default third-party requests pass.
- Optimized Compare presentation: a shared static costmap colour buffer, fixed palette and trace-dependent invalidation replace repeated per-pane static work. A retained M5.7 implementation is the byte oracle across all 256 costs, both themes, narrow grids, trace states and difference patterns. No planner, model, event, hash or scientific claim changes.

## Retained failures and measurement boundaries

The initial Intel four-pane replay measured median 11.516654854743376 fps; it failed the budget. Its [raw data](data/m5/close/fps/checks.json) remain alongside the corrected run. Functional `passed` fields in browser harnesses do not by themselves declare a performance budget met.

The optional World Spec v2 warm-start diagnostics were 3132.5 ms desktop, 3752.7 ms landscape and 3223.4 ms portrait, above 3 s. The acceptance run uses the shipped default World Spec v1 and constructs the live model fully; optional terrain misses are not relabelled as passing. Earlier concurrent-load diagnostics are retained.

An old-worker cleanup race, an ambiguous hidden joystick selector, a colour(srgb) parser scaling error and comparison against the wrong historical grid hash caused earlier checks to fail. Corrected checks and original outputs are retained under [close/](data/m5/close/). The fresh canonical grid hash matches the saved M5.6 canonical reference; its older legacy link continues to verify with its own encoding/version. No v1 hash or golden changed.

## Checkpoints, tests and review

Baseline: packages 3523 / web 436 / tools 192. Closure packages 3569 across all 12 suites, web 493 /62 files, tools 209, focused harness-condition tests 56 pass. Typecheck, build, dist and licence checks pass. [Final package log](data/m5/close/packages-final.txt), [web log](data/m5/close/vitest-close.txt), [tools log](data/m5/close/tools.txt). Python model code has not changed since M5.9. ADR [0008](adr/0008-state-hash-v2.md) defines v2; [0009](adr/0009-v2-encoding-cache.md) preserves its bytes while reducing encoding work.

All checkpoint reports and screenshots remain linked from STATUS/history. Screenshots require Gautham's aesthetic review; no feedback has been invented. Blank pre-design notes are preserved; no observations existed, and the owner waived that prerequisite on 2026-10-14. Mapping comparisons alone are parked for M7 in IDEAS; existing lessons remain available. No new world, mini-game, cloud or experiment builder was added.

## Cold-start and JavaScript boundaries

The immediate-entry protocol starts at navigation, waits only for the actual title mesh, then chooses Play → Free roam → Vision as soon as available. All six runs completed with zero console errors and zero third-party requests. Desktop first visible computation was 9673.60009765625–9862.60009765625 ms. Emulated phone first visible computation was 10026.89990234375–10236.60009765625 ms, above 10 s; this is a recorded emulation miss, not a real-phone pass.

`check_dist.mjs` now enforces the 350000-byte app-only title import closure in CI and reports interpreter JavaScript separately. This does not silently redefine README's budget: including all JavaScript warmed behind the title gives 540104 bytes and remains an open performance limitation. WASM, stdlib, wheel and mesh bytes are additional resources; request size/timing records are committed. No account, cloud execution or new algorithm was introduced to disguise startup costs.

## Emulated phone sustained rendering and latency

[Emulated Nothing Phone (1), terrain world, 600.225-second run](data/m5/close/phone-ten-minutes-visible/checks.json): 594 samples; first-minute median/minimum 60/60 submitted fps; ten-minute median 60, minimum 58, p05 60. Zero context loss, reloads or console errors. Automatic tier selected high (DPR 2) on the laptop GPU. Twenty touch-to-motion trials: median 82.90000000596046 ms, minimum 53.599999994039536 ms, maximum 252 ms. These are emulated results, not phone measurements or a heat test.

A low-priority package regression run shared the laptop during the emulation; its CPU affinity was restricted to cores 8–11 until the phone run finished. The raw start/end conditions include load. The control was held on the visible joystick; this is sustained rendering/stability evidence, not a claim about uninterrupted physical travel. Provisional phone defaults remain unchanged pending the real USB heat run.

Final candidate `00a42aa`: [eight Compare layouts](data/m5/close/compare-final/checks.json) pass with one context and no errors; [Intel four-pane replay](data/m5/close/fps-final/checks.json) median 60.02508511003504 fps, minimum 59.42198613471046. [Desktop Chrome installability](data/m5/close/installability.json) reports zero manifest/installability errors; actual Android installation remains unmeasured. Earlier cold/warm and Play-soak data are from the preceding candidate; the final patch adds only Compare cost-batch cache invalidation.
