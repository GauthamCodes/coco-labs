# COCO Lab — current status

## Position

- Branch `v2/m5-focus`; implementation/tested code SHA `00a42aa` (M5.11).
- M5.0–M5.11 implemented and measured; PR submission in progress.
- No merge, release or deployment. Public launch remains gated by unresolved budgets, real-phone pass, owner usability and independent review.
- Master plan revision 3 sha256 `b6289ef9882cb864387fe6d1815fe17beec1cd49931c238748c5ca6f3c6fc663`.
- Authority/rules: [README](../README.md), [AGENTS](../AGENTS.md), [M5 prompt](v2/M5_PROMPT.md), [owner amendments](v2/M5_CONTINUATION.md).
- [Acceptance matrix](v2/M5_RESULTS.md), [closure evidence/report](v2/data/m5/close/REPORT.md), [full history](v2/STATUS_HISTORY.md).

## Checkpoints and evidence

| Checkpoint | Change / evidence | Class |
| --- | --- | --- |
| M5.0 | [Pinned baseline](v2/data/m5/setup/BASELINE.md); revision 3 installed byte-for-byte; E1–E8 recorded. | TESTED |
| M5.1 | [Defect regressions](v2/data/m5/defects/): shared link bounds, v2 hash, race locks, real robot mesh, floor picking; frozen v1 intact; source-repro job documented/disabled. | MODEL / TESTED |
| M5.2 | [Full moves/cache list](v2/data/m5/agent-overhead/MOVES.md); AGENTS 178 lines, short STATUS, archived history/lore, five RL scripts moved. Only six tracked root test-cache files removed; physical copies retained. | TESTED |
| M5.3 | [Scene core/lazy shells](v2/data/m5/code-shape/REPORT.md); separate hashed Three.js chunk; unchanged behavior proved. | MODEL / TESTED |
| M5.4 | [Night Shift](v2/data/m5/design-system/REPORT.md): tokens/themes, licensed fonts/icons, real references/CVD simulations. | TESTED presentation |
| M5.5 | [Three-door shell](v2/data/m5/app-shell/REPORT.md), warm interpreter, About/Settings, old routes preserved. | MODEL / TESTED |
| M5.6 | [Focused Play](v2/data/m5/play/REPORT.md): HUD, follow camera, walls/scan, cards/score/replay/tutorial and phone controls. | MODEL / TESTED |
| M5.7 | [Compare](v2/data/m5/compare/REPORT.md): one-context 2/4 panes, layers, existing three algorithm families, twelve evidence-linked tours. Mapping comparisons parked for M7; Inspect lessons retained. | MODEL / TESTED; original STACK claims retained |
| M5.8 | [Recordings library](v2/data/m5/recordings/REPORT.md): 100 Case Files +65 converted representations; all 165 searchable/filterable; failures retained. | STACK / MODEL / TESTED |
| M5.9 | [Static caching and disabled counter](v2/data/m5/caching/REPORT.md), own install icons/manifest; no personal data cached or account created. | TESTED |
| M5.10 | [Launch drafts/local demo](v2/data/m5/launch/REPORT.md): 80.001 s local silent demo, release draft, owner usability protocol, phone guide. Nothing published. | TESTED presentation; original STACK recording |
| M5.11 | [Final results](v2/M5_RESULTS.md): visible-computation/keyboard/AA fixes, worker-update race, byte-identical Compare rendering optimization, measurement/PR closure. | MODEL / TESTED / MEASURED laptop; explicitly emulated phone |

## Verification and measured limits

- Setup packages/web/tools: 3523 /436 /192 passed. Closure web 493 (62 files), tools 209, focused harness-condition tests 56; typecheck/build/dist/licence checks pass.
- [Final package run](v2/data/m5/close/packages-final.txt): 3569 across all 12 packages pass; no Python model change since M5.9.
- [V1 flat](v2/data/m5/close/v1-flat/checks.json): all 15000 M1 hashes unchanged; golden fixtures untouched.
- [V2](v2/data/m5/close/determinism-v2/determinism.json): four engines ×100 sessions ×150 ticks, zero differences against saved M5.1.
- [166 stored links](v2/data/m5/close/links-verified.json) +[one delta](v2/data/m5/close/links-delta-verified.json) verify their own versions.
- [URLs](v2/data/m5/close/urls/v1_links_check.json): 50 forms +six archive views, zero console errors; five replay and five pixel-identical canvas checks pass.
- [Focus](v2/data/m5/close/focus/focus.json): 7 desktop /7 compact /8 emulated landscape /1 portrait controls, no page scroll; 24 game layouts checked.
- [Cold starts](v2/data/m5/close/startup-immediate/checks.json): desktop title <=2028.2000000029802 ms, live/3D <=9786.999755859375 ms; emulated title <=2616.7999999970198 ms.
- Emulated phone live model misses 10 s in 2/3 runs (max 10161.39990234375 ms); visible computation max 10236.60009765625 ms. Not relabelled passed.
- [Warm default world](v2/data/m5/close/cache-race-fixed/checks.json): 2680.5 /2620.5 /2694.199951171875 ms desktop/landscape/portrait, all <=3 s. Optional terrain warm diagnostics exceed 3 s and remain visible.
- [Final JS inventory](v2/data/m5/close/dist-close.txt): app+worker 271628 gzip bytes; interpreter adds 268476, total 540104. App-only check passes CI; strict all-JavaScript 350000 budget NOT MET, no waiver inferred.
- [GPU Play](v2/data/m5/close/fps/checks.json): nominal 60 fps RTX high/Intel medium; raw interval medians 59.96230940521038 /60.01500375153408.
- [Final Intel four-pane Compare](v2/data/m5/close/fps-final/checks.json): median 60.02508511003504 fps (initial 11.516654854743376 failure retained); pixels match retained reference.
- [30-minute hygiene](v2/data/m5/close/soak-final/soak3d_nvidia.json): 30.162183333333335 minutes, zero errors/context loss/driving long tasks.
- [Accessibility](v2/data/m5/close/accessibility-final/checks.json): twelve dark/light pages, AA text checks, focusability/reduced motion pass; [actual keyboard goal/grid proof](v2/data/m5/close/keyboard-proof/checks.json).
- Measurements: balanced on AC, original balanced unchanged; RTX 4050 driver 580.178.04; Intel RPL-P through Vulkan/Mesa 25.2.8. Raw start/end conditions include load/renderer. No robot batch active.
- [ADR 0008](v2/adr/0008-state-hash-v2.md) defines v2; [ADR 0009](v2/adr/0009-v2-encoding-cache.md) preserves its bytes while reducing encoding overhead.

## Owner rows, phone and design inputs

- [Notes](v2/usability/2026-10-pre-m5.md) found blank and unchanged; [N1/N2 inputs](v2/M5_DESIGN_INPUTS.md) addressed without invented observations. Pre-design prerequisite waived.
- Nothing Phone (1), recorded by Gautham; [hardware facts](v2/PHONE_PROFILE.md) remain assumptions until measured.
- [Latest ADB check](v2/data/m5/phone/ADB_CHECK_M511_2026-10-19.txt): no device. Real Phone criterion agent-owned, pending: connect phone over USB with debugging enabled.
- [Emulated Nothing Phone (1)](v2/data/m5/close/phone-ten-minutes-visible/checks.json): 600.225 s, median 60/minimum 58 fps, 20 touch trials median 82.90000000596046 ms, zero errors/loss/reload. CPU 4× proxy, laptop GPU, package regression background load disclosed; no thermal inference.
- Emulation never satisfies Phone. Provisional defaults 60 fps (optional 120), auto starting medium/DPR 1.5, low 1/high 2; real ten-minute heat run finalizes them.
- Five-person usability remains Gautham-owned, pending, public-launch gate only. Older M4 owner rows remain unmeasured. No owner row marked done.

## Screenshots awaiting Gautham

- [Final review index](v2/data/m5/close/SCREENSHOTS.md): desktop/compact Play, both emulated phone orientations, keyboard goals/grid and four-pane Compare.
- [Night Shift/CVD](v2/data/m5/screens/reference/README.md), [app shell](v2/data/m5/screens/app-shell/README.md), [Play](v2/data/m5/screens/play/README.md), [Compare](v2/data/m5/screens/compare/README.md), [Recordings](v2/data/m5/screens/recordings/README.md).
- All previous references retained. No owner feedback recorded; review is a soft gate.

## Open questions

G1 learners first; G2 priority/batch windows owner-controlled; G3 robot repository canonical;
G4 cloud budget zero; G5 assume no physical robot; G6 licensing/contributions unchanged.
Plug in the Nothing Phone (1) with USB debugging on when convenient; the agent measures it automatically.

### M5 approved plan-change log

The owner approved E1–E8 by issuing the M5 prompt. Decision wording and rationale follow README §8 and its referenced architecture; M6+ items are recorded only, never implemented in M5.

| Date | Change | Reason | By |
| --- | --- | --- | --- |
| 2026-10-14 | E1: Play, Compare, Research; title and About replace the four-mode navigation. | Three purposes, three modes; focus the existing dashboard surface. | Gautham (M5 prompt) |
| 2026-10-14 | E2: Depot from World Spec v3; browser, Gazebo SDF and Nav2 map; arena retained as Proving Ground (M6). | Author worlds once and retain the reference for existing recordings. | Gautham (M5 prompt) |
| 2026-10-14 | E3: ROS-shaped model, graph panel, Gazebo worlds, ROS ghosts; own-ROS bridge M7; invariant 2 narrowed to control boundary. | Make “ROS 2 at its core” concrete without per-player cloud cost; keep Stack control behind coco.v1. | Gautham (M5 prompt) |
| 2026-10-14 | E4: glass-box MoveIt-style Grasp Assist in the model, explicitly badged (M6). | Show the manipulation decisions honestly within the kinematic model. | Gautham (M5 prompt) |
| 2026-10-14 | E5: public v2.0 after M5 and owner gates; Depot games as v2.1. | Polish and launch what exists before adding worlds and games. | Gautham (M5 prompt) |
| 2026-10-14 | E6: service-worker static asset cache allowed. | Cache app, Pyodide and assets for returning visitors; never personal data. | Gautham (M5 prompt) |
| 2026-10-14 | E7: one cookieless aggregate counter allowed, off until owner configures it. | Aggregate visits without personal data, fingerprinting or per-user tracking. | Gautham (M5 prompt) |
| 2026-10-14 | E8: slim/archive agent files; AGENTS.md canonical; nothing deleted except committed test cache. | Reduce startup overhead while preserving history and engineering rules. | Gautham (M5 prompt) |


## M5 continuation decisions — 2026-10-14

| Date | Change | Reason / scope | By |
| --- | --- | --- | --- |
| 2026-10-14 | Pre-design phone/three-person prerequisite explicitly waived. | No waiting for observations; implement M5.1–M5.11. The blank committed template stays unchanged. | Gautham (continuation prompt) |
| 2026-10-14 | Nothing Phone (1) is the primary phone design target; other phones remain supported. | Landscape Play, safe areas, thumb controls, portrait Compare/Research; hardware facts assumed until measured. | Gautham |
| 2026-10-14 | M5 Phone criterion moves from Gautham to agent. | Measure real USB-debugging phone with CDP when connected; emulated Nothing Phone (1) checks always, labelled emulated and insufficient alone to meet Phone. If absent: pending, connect phone over USB. | Gautham |
| 2026-10-14 | Five-person usability remains Gautham-owned, public-launch gate only. | Does not block implementation or pull request. | Gautham |
| 2026-10-14 | Add 60 fps phone cap (optional 120), tier pixel-ratio cap, installable manifest and haptics. | Ten-minute real-phone heat run determines defaults; unsupported APIs fail silently. Add phone connection question once at M5.4 without waiting. | Gautham |


## Next step

Commit M5.11 evidence, push `v2/m5-focus` and open the PR into main. Never merge it or create/edit releases.
Independent review and the explicit open performance/phone/usability items precede public launch. No stop condition hit; no new parked idea.
