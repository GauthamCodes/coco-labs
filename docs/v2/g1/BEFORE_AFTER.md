# G1 · Game Look — before and after

Same harness (`lab_web/tools/g1/screens.mjs`), same three profiles: desktop 1440 × 900 and the
emulated Nothing Phone (1) in landscape (915 × 412) and portrait (412 × 915), DPR 2.625, 4× CPU
throttle. Rendered by this cloud container's software GPU (SwiftShader) every time — the
renderer is recorded in each `shots.json`.

- **Before**: G1.0, 2026-10-20, the build before G1 ([`screens/before/`](screens/before/)).
- **After G1.10**: 2026-10-21, G1.10's build ([`screens/after/`](screens/after/)).
- **After G1.11**: 2026-10-21, after Gautham's look notes — exposure and fill, COCO's rim
  light and LED glow, the thin ghost route with chevrons and a small pin, the stronger minimap —
  and Fetch Rush rules 2 (3 orders, the round's timer) ([`screens/after_g111/`](screens/after_g111/)).
- **After G1.12**: 2026-10-22, after Gautham's camera notes — the chase camera frames COCO in
  the upper-middle third on a 2.1 m boom (≥ 1.7 m, ≥ 1.2 m up), rises over walls instead of
  moving in, keeps both of COCO's shoulders in view; a softer headlight and bloom; COCO starts
  in the zone's roomiest spot facing the open aisle — and Fetch Rush rules 3's phone round
  (2 orders, 4:36) ([`screens/after_g112/`](screens/after_g112/)).

- **After G1.13 (laptop, NVIDIA)**: 2026-10-23, the head build on Gautham's laptop, rendered by
  the **NVIDIA GeForce RTX 4050 Laptop GPU** (driver 580.178.04; ANGLE on EGL), not SwiftShader —
  the same harness and profiles (`G1_GPU=nvidia`; renderer and machine in
  [`screens/after_g113_nvidia/shots.json`](screens/after_g113_nvidia/shots.json)). New since
  G1.12: COCO starts facing the clear heading nearest its first route (the ghost line leaves
  ahead, not behind), the phone round's timer is 4:33.5, and ordinary ticks are shown on a 0.1 s
  schedule. Phone portrait Play is the rotate card, as in every column (PLAY is not reachable).

**Screenshots catch regressions; Gautham judges the look.**

Play before is M5's Play (`?view=arena`, the planar Arena); Play after is G1's game: Play →
Fetch Rush → the Depot at medium, PLAY pressed (`?view=play&game=fetch_rush&world=depot&tier=medium`).

## Title

| Profile | Before | After G1.10 | After G1.11 | After G1.12 | After G1.13 (laptop, NVIDIA) |
| --- | --- | --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-title.png) | ![G1.10](screens/after/desktop-title.png) | ![G1.11](screens/after_g111/desktop-title.png) | ![G1.12](screens/after_g112/desktop-title.png) | ![G1.13](screens/after_g113_nvidia/desktop-title.png) |
| phone-landscape | ![before](screens/before/phone-landscape-title.png) | ![G1.10](screens/after/phone-landscape-title.png) | ![G1.11](screens/after_g111/phone-landscape-title.png) | ![G1.12](screens/after_g112/phone-landscape-title.png) | ![G1.13](screens/after_g113_nvidia/phone-landscape-title.png) |
| phone-portrait | ![before](screens/before/phone-portrait-title.png) | ![G1.10](screens/after/phone-portrait-title.png) | ![G1.11](screens/after_g111/phone-portrait-title.png) | ![G1.12](screens/after_g112/phone-portrait-title.png) | ![G1.13](screens/after_g113_nvidia/phone-portrait-title.png) |

## Play

| Profile | Before | After G1.10 | After G1.11 | After G1.12 | After G1.13 (laptop, NVIDIA) |
| --- | --- | --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/desktop-play.png) | ![G1.11](screens/after_g111/desktop-play.png) | ![G1.12](screens/after_g112/desktop-play.png) | ![G1.13](screens/after_g113_nvidia/desktop-play.png) |
| phone-landscape | ![before](screens/before/phone-landscape-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/phone-landscape-play.png) | ![G1.11](screens/after_g111/phone-landscape-play.png) | ![G1.12](screens/after_g112/phone-landscape-play.png) | ![G1.13](screens/after_g113_nvidia/phone-landscape-play.png) |
| phone-portrait | ![before](screens/before/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.click: Timeout 30000ms exceeded.* | ![G1.11](screens/after_g111/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.click: Timeout 30000ms exceeded.* | ![G1.12](screens/after_g112/phone-portrait-play.png) — *not ready: the rotate card (by design)* | ![G1.13](screens/after_g113_nvidia/phone-portrait-play.png) |

## Compare

| Profile | Before | After G1.10 | After G1.11 | After G1.12 | After G1.13 (laptop, NVIDIA) |
| --- | --- | --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-compare.png) | ![G1.10](screens/after/desktop-compare.png) | ![G1.11](screens/after_g111/desktop-compare.png) | ![G1.12](screens/after_g112/desktop-compare.png) | ![G1.13](screens/after_g113_nvidia/desktop-compare.png) |
| phone-landscape | ![before](screens/before/phone-landscape-compare.png) | ![G1.10](screens/after/phone-landscape-compare.png) | ![G1.11](screens/after_g111/phone-landscape-compare.png) | ![G1.12](screens/after_g112/phone-landscape-compare.png) | ![G1.13](screens/after_g113_nvidia/phone-landscape-compare.png) |
| phone-portrait | ![before](screens/before/phone-portrait-compare.png) | ![G1.10](screens/after/phone-portrait-compare.png) | ![G1.11](screens/after_g111/phone-portrait-compare.png) | ![G1.12](screens/after_g112/phone-portrait-compare.png) | ![G1.13](screens/after_g113_nvidia/phone-portrait-compare.png) |

## Recordings (Research)

| Profile | Before | After G1.10 | After G1.11 | After G1.12 | After G1.13 (laptop, NVIDIA) |
| --- | --- | --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-recordings.png) | ![G1.10](screens/after/desktop-recordings.png) | ![G1.11](screens/after_g111/desktop-recordings.png) | ![G1.12](screens/after_g112/desktop-recordings.png) | ![G1.13](screens/after_g113_nvidia/desktop-recordings.png) |
| phone-landscape | ![before](screens/before/phone-landscape-recordings.png) | ![G1.10](screens/after/phone-landscape-recordings.png) | ![G1.11](screens/after_g111/phone-landscape-recordings.png) | ![G1.12](screens/after_g112/phone-landscape-recordings.png) | ![G1.13](screens/after_g113_nvidia/phone-landscape-recordings.png) |
| phone-portrait | ![before](screens/before/phone-portrait-recordings.png) | ![G1.10](screens/after/phone-portrait-recordings.png) | ![G1.11](screens/after_g111/phone-portrait-recordings.png) | ![G1.12](screens/after_g112/phone-portrait-recordings.png) | ![G1.13](screens/after_g113_nvidia/phone-portrait-recordings.png) |

## Notes on readiness

- **Before, Play did not report ready** in any profile (180 s timeout): on SwiftShader, M5's
  Play 3D scene never signalled `data-scene-ready` (recorded at G1.0). The before images are
  what the page showed at the timeout.
- **After, phone portrait Play shows "Rotate your phone"** (G1.2's design: the game plays in
  landscape; STOP stays reachable). There is no PLAY to press, so the harness reports it not
  ready; that card is the intended screen.
- G1.11's Play starts in the round's start zone (shift 1: the Loading dock), facing its first
  object; there the headlight lights the pallet stack beside COCO. Every other after shot
  reported ready with no console or page errors.
- G1.12's Play starts at the Loading dock's roomiest spot (1.5 m clear of the forklift lanes),
  facing the open aisle (west); the phone round's first ghost route leaves behind COCO, so the
  player turns first (a question for Gautham in G1_STATUS). COCO's projected box overlaps no HUD
  element at 20 scripted poses, phone landscape and desktop (`lab_web/tools/g1/chase_hud_check.mjs`,
  a CI step; `data/g112/chase_hud.json`).
