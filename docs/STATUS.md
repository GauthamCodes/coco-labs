# COCO Lab — current status

## Position

- Branch: `v2/m5-focus`; checked implementation SHA: `eb5edbc`.
- M5 · Focus and polish: M5.0–M5.3 complete; next checkpoint M5.4 Night Shift.
- M5.4–M5.11 remain. No PR, merge or release yet. Independent milestone review remains required.
- Master plan revision 3, copied byte-for-byte; sha256 `b6289ef9882cb864387fe6d1815fe17beec1cd49931c238748c5ca6f3c6fc663`.
- Canonical agent rules: [AGENTS.md](../AGENTS.md). Historical status: [STATUS_HISTORY.md](v2/STATUS_HISTORY.md).
- Prompts: [M5](v2/M5_PROMPT.md), [owner amendments](v2/M5_CONTINUATION.md).

## Evidence and tests

- Setup: [baseline](v2/data/m5/setup/BASELINE.md): packages 3523, web 436, tools 192 passed.
- M5.1: packages 3534, web 456, tools 193 passed; typecheck passed.
- [Defect evidence](v2/data/m5/defects/): shared link bounds, 137/137 committed Play links verify;
  v1 flat 15000 hashes unchanged; v2 four engines ×100 sessions, zero differences.
- [ADR 0008](v2/adr/0008-state-hash-v2.md): mutable behavioural state coverage and version compatibility.
- Emulated 4G Case Files: 100/100 real mesh first frames <=2 s; max 1871.39990234375 ms.
  [Data](v2/data/m5/defects/casefile-first-frame/first-frame.json), balanced on AC, NVIDIA 580.178.04.
- [V1 workflow](v2/data/m5/defects/V1_WORKFLOW.md): source reproduction disabled; frozen archive unchanged.
- M5.2: packages 3534, web 456, tools 195 passed; typecheck passed.
  [Moves and checks](v2/data/m5/agent-overhead/MOVES.md), [packages](v2/data/m5/agent-overhead/packages-clean.txt),
  [web](v2/data/m5/agent-overhead/vitest.txt), [tools](v2/data/m5/agent-overhead/tools-clean.txt).
- AGENTS 178 lines; STATUS below 200; all prior history retained. Only six root cache files untracked.
- M5.3 baseline: five pixel-identical canvas tests, five recording replays, 22 URL forms and six archive views pass.
  [Baseline artifacts](v2/data/m5/code-shape/before/).

- M5.3: scene core + original presentation + three lazy shells; one Three.js engine chunk.
  [Report](v2/data/m5/code-shape/REPORT.md): suites 3534 / 456 / 195 pass; typecheck and build pass.
  Final five pixel-identical scenes, five replays, 22 URL forms + six archive views, 137 links all pass.
  [Final bundle inventory](v2/data/m5/code-shape/final/bundles.json); no behaviour or model change.

## Owner rows, phone and design inputs

- Notes found: [committed blank template](v2/usability/2026-10-pre-m5.md), unchanged.
- [Design inputs](v2/M5_DESIGN_INPUTS.md): no pre-design observations exist; prerequisite explicitly waived.
- Target Nothing Phone (1), recorded by Gautham. [Profile](v2/PHONE_PROFILE.md): hardware facts assumed until measured.
- Real Phone criterion is agent-owned and pending: connect phone over USB with debugging enabled.
  [ADB check](v2/data/m5/phone/ADB_CHECK_M51.txt): no device connected.
- Emulator is labelled emulated Nothing Phone (1); CPU 4× proxy, viewport/DPR shared harness.
  It cannot satisfy the real Phone row. Provisional cap 60 fps, optional 120; automatic tier/DPR pending heat run.
- Five-person usability remains Gautham-owned, pending, a public-launch gate only.
- Older M4 owner phone/usability rows remain unmeasured; no owner row marked done.

## Screenshots awaiting Gautham

- [Desktop race](v2/data/m5/screens/defects/race-desktop.png).
- [Emulated phone landscape](v2/data/m5/screens/defects/race-nothing-landscape.png).
- [Emulated phone portrait](v2/data/m5/screens/defects/race-nothing-portrait.png).
- No recorded feedback yet; continue without waiting.

## Open questions

G1 learners first; G2 priority/batch windows owner-controlled; G3 robot repository canonical;
G4 cloud budget zero; G5 assume no physical robot; G6 licensing/contributions unchanged.
No implementation question blocks progress. Phone connection reminder is added once at M5.4.

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

M5.4 Night Shift: one token source, dark/light themes, licensed self-hosted fonts/icons,
colour-blind checks and real title/Play/Compare reference screens at desktop and phone sizes.
Add the phone connection question once at this first look-changing checkpoint; never wait.
No stop condition hit; no new parked idea. Phone absent; provisional settings unchanged.
M5 remains open; public launch still waits for phone pass and Gautham's usability gate.
