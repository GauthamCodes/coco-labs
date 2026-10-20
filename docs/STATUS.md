# COCO Lab — current status

## Position

- Independent review of `fe9d544` integrated: PR #26 merged as `d8b6d4c` after exact review-head `a81f8f4` passed Lab run [39438277138](https://github.com/GauthamCodes/coco-labs/actions/runs/39438277138); all three jobs green, deploy skipped.

- 2026-10-20 closure attempt: **M5 remains open** at the owner-requested non-tie report stop. [Diagnosis/report](v2/data/m5/closure-20261020/REPORT.md): DWA costmap rasterization divergence, not a near-tie; no model/hash/golden change.
- Manual Pages gate implemented in `51c2216`; push/main cannot deploy (truth-table regression passed). Public site stays M4 until Gautham confirms manual deployment after real-phone and five-person gates. No deployment triggered.
- Open-page policy/probe regression, native parity CI, final-head dual-GPU soaks and full rerun remain pending. Historical measurements below are superseded as closure-head attestations.

- Branch `v2/m5-focus`; original implementation `00a42aa`, review product source `f22f729`, deploy gate `51c2216`; closure is report-only pending the explicit non-tie follow-up.
- M5.0–M5.11 implemented and measured; [PR #25](https://github.com/GauthamCodes/coco-labs/pull/25) open, unmerged.
- Original PR #25 CI failure (bytecode audit) is fixed by merged review. Updated PR #25 CI must be confirmed after push.
- **Not ready:** open-tab version mixing and native parity remain unresolved. Main merging no longer deploys; real-phone and owner usability gates remain open. PR #25 unmerged; no release/deployment performed.
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
- [Focus](v2/data/m5/close/focus/focus.json): 7 desktop /7 compact /8 emulated landscape /1 portrait controls originally; review adds reachable portrait STOP (2 controls), no page scroll; 24 game layouts checked.
- [Cold starts](v2/data/m5/close/startup-immediate/checks.json): desktop title <=2028.2000000029802 ms, live/3D <=9786.999755859375 ms; emulated title <=2616.7999999970198 ms.
- Emulated phone live model misses 10 s in 2/3 runs (max 10161.39990234375 ms); visible computation max 10236.60009765625 ms. Not relabelled passed.
- [Warm default world](v2/data/m5/close/cache-race-fixed/checks.json): 2680.5 /2620.5 /2694.199951171875 ms desktop/landscape/portrait, all <=3 s. Optional terrain warm diagnostics exceed 3 s and remain visible.
- [Final JS inventory](v2/data/m5/close/dist-close.txt): app+worker 271628 gzip bytes; interpreter adds 268476, total 540104. App-only check passes CI; owner decision 1 applies the ≤350000 budget to title-critical app+worker: met. Review critical bytes 271801; interpreter 268476 stays gated behind title interactivity.
- [GPU Play](v2/data/m5/close/fps/checks.json): nominal 60 fps RTX high/Intel medium; raw interval medians 59.96230940521038 /60.01500375153408.
- [Final Intel four-pane Compare](v2/data/m5/close/fps-final/checks.json): median 60.02508511003504 fps (initial 11.516654854743376 failure retained); pixels match retained reference.
- [30-minute hygiene](v2/data/m5/close/soak-final/soak3d_nvidia.json): 30.162183333333335 minutes, zero errors/context loss/driving long tasks.
- [Accessibility](v2/data/m5/close/accessibility-final/checks.json): twelve dark/light pages, AA text checks, focusability/reduced motion pass; [actual keyboard goal/grid proof](v2/data/m5/close/keyboard-proof/checks.json).
- Measurements: balanced on AC, original balanced unchanged; RTX 4050 driver 580.178.04; Intel RPL-P through Vulkan/Mesa 25.2.8. Raw start/end conditions include load/renderer. No robot batch active.
- [ADR 0008](v2/adr/0008-state-hash-v2.md) defines v2; [ADR 0009](v2/adr/0009-v2-encoding-cache.md) preserves its bytes while reducing encoding overhead.

## Independent review — 2026-10-20

- [Review-fix PR #26](https://github.com/GauthamCodes/coco-labs/pull/26) targets M5, open/unmerged; final product fixes `f22f729`.
- [Full findings and 15-row claims audit](v2/reviews/M5_REVIEW.md); [review screenshots](v2/data/m5/review/SCREENSHOTS.md). Historical performance numbers above are not exact-head attestations.
- Fresh reviewer runs: 3569 package, 493 web and 219 tool tests pass; schema/typecheck, two byte-identical builds and dist checks pass. [Build identity](v2/data/m5/review/BUILD.json).
- Fresh v1: 100×150=15000 hashes, zero hash/chain differences. Four-engine v2: each 100×150, zero hash/chain differences or page errors. CLI links: 153 distinct queries, all pass. Corrected verifier no longer substitutes saved Node output or ignores chain/page errors.
- Fixed title idle/input ordering, dialog/portrait and secondary-touch STOP, Settings navigation, and bytecode source audit. Preload attempt duplicated WASM/stdlib and regressed cold starts; removed, evidence retained. Streaming already native and execution verified.
- Final balanced/AC desktop live ms: 9997.8 /9828.4 /9845.3. Emulated phone: 10106.3 /10030.5 /9964.7; accepted near-miss, not Phone completion. [Raw runs](v2/data/m5/review/startup-final-ac/checks.json).
- [Open-tab A/B test](v2/data/m5/review/update-open-tab-ac3/checks.json) proves an A document receives B static bytes; hard reload passes. Update policy needs Gautham. Prefs-only storage and default-off counter pass source review.
- Native CPython vs browser continuous Compare is not byte-identical; see review report. Global algorithms match native events; seven inflation cells match independently computed Nav2 costs.
- Code-shape leftovers: sceneCore 941 lines, Renderer 957. Trial M6 merge has no conflict files; temporary worktree removed and real M6 worktree untouched.

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

| Date | Change | Reason / scope | By |
| --- | --- | --- | --- |
| 2026-10-20 | Merge only PR #26 into v2/m5-focus with a merge commit after exact-head CI passes; no force-push. PR #25 remains Gautham's merge. | One-time review integration permission; no other PR merge authorized. | Gautham |
| 2026-10-20 | Main push builds/tests; Pages only through manual **Deploy site** with required `DEPLOY` confirmation. Public site stays M4 until owner runs it after real-phone and five-person usability passes. | Separate merge from publication; agent must not deploy. README §9 updated. | Gautham |
| 2026-10-20 | Pin every runtime/data/asset URL by build or content hash; waiting update offers Save run and Reload; no automatic/mid-run reload; retain old caches until no page of their build is open. | Prevent mixed builds without losing runs; update-open-tab-ac3 must report false and enter CI. Supersedes old activation cleanup rule. | Gautham |
| 2026-10-20 | Four-engine contract stays Pyodide; native CPython must meet explicit per-family tolerances. Trace first differing tick; deterministic tie fix requires new hash version and untouched old goldens. For a non-tie, report and stop without guessing a fix. | Research exports and native verification require portability. Non-tie stop reached: DWA obstacle cost differs by 22, changing selection at tick 47. | Gautham |
| 2026-10-20 | Split sceneCore.ts (941 lines) and Renderer.ts (957) as the first task of M6's UI phase; portrait Compare horizontal result scroller accepted. | Keep decomposition outside M5. Recorded in README M6; no M6 worktree edits. | Gautham |
| 2026-10-20 | Final closure requires fresh 30-minute Play soaks on both GPUs at recorded final SHA, all review checks rerun, retained/superseded earlier evidence, push and green PR #25 CI; real phone measured if ADB sees it. | Exact-head evidence; phone absent today. Deferred at explicit non-tie report stop. | Gautham |

The owner approved E1–E8 by issuing the M5 prompt. Decision wording and rationale follow README §8 and its referenced architecture; M6+ items are recorded only, never implemented in M5.

| Date | Change | Reason | By |
| --- | --- | --- | --- |
| 2026-10-19 | Review decision 1: ≤350 kB gzip covers title-critical app plus worker (271628 bytes at fe9d544); interpreter (268476 bytes) is background work only after title interactivity, at idle or first input. | Keep the title responsive; review adds an explicit paint/idle-or-input gate. | Gautham (review prompt) |
| 2026-10-19 | Review decision 2: 9.94–10.16 s emulated phone cold start is an accepted emulated near-miss; real Nothing Phone (1) decides Phone. | Try WASM/stdlib preload, streaming compilation and earliest safe worker fetch once; retain all three remeasurement results. | Gautham (review prompt) |
| 2026-10-19 | Review decision 3: warm-start budget covers the default world; optional terrain starts over 3 s are accepted diagnostics. | Retain optional-world numbers without treating them as default-world failures. | Gautham (review prompt) |
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

At the explicit non-tie report stop: obtain Gautham's direction for the
LiDAR-to-costmap native/Pyodide discrepancy, then implement the open-page policy,
add regression gates and finish exact-final-head soaks and the full review rerun.
PR #25 remains Gautham's merge. Public M4 stays until owner-confirmed manual
Deploy site after real-phone and five-person usability passes. Never deploy.
