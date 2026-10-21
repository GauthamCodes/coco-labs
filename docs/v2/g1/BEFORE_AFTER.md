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

**Screenshots catch regressions; Gautham judges the look.**

Play before is M5's Play (`?view=arena`, the planar Arena); Play after is G1's game: Play →
Fetch Rush → the Depot at medium, PLAY pressed (`?view=play&game=fetch_rush&world=depot&tier=medium`).

## Title

| Profile | Before | After G1.10 | After G1.11 |
| --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-title.png) | ![G1.10](screens/after/desktop-title.png) | ![G1.11](screens/after_g111/desktop-title.png) |
| phone-landscape | ![before](screens/before/phone-landscape-title.png) | ![G1.10](screens/after/phone-landscape-title.png) | ![G1.11](screens/after_g111/phone-landscape-title.png) |
| phone-portrait | ![before](screens/before/phone-portrait-title.png) | ![G1.10](screens/after/phone-portrait-title.png) | ![G1.11](screens/after_g111/phone-portrait-title.png) |

## Play

| Profile | Before | After G1.10 | After G1.11 |
| --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/desktop-play.png) | ![G1.11](screens/after_g111/desktop-play.png) |
| phone-landscape | ![before](screens/before/phone-landscape-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/phone-landscape-play.png) | ![G1.11](screens/after_g111/phone-landscape-play.png) |
| phone-portrait | ![before](screens/before/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.waitForSelector: Timeout 180000ms exceeded.* | ![G1.10](screens/after/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.click: Timeout 30000ms exceeded.* | ![G1.11](screens/after_g111/phone-portrait-play.png) — *not ready: not ready: TimeoutError: page.click: Timeout 30000ms exceeded.* |

## Compare

| Profile | Before | After G1.10 | After G1.11 |
| --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-compare.png) | ![G1.10](screens/after/desktop-compare.png) | ![G1.11](screens/after_g111/desktop-compare.png) |
| phone-landscape | ![before](screens/before/phone-landscape-compare.png) | ![G1.10](screens/after/phone-landscape-compare.png) | ![G1.11](screens/after_g111/phone-landscape-compare.png) |
| phone-portrait | ![before](screens/before/phone-portrait-compare.png) | ![G1.10](screens/after/phone-portrait-compare.png) | ![G1.11](screens/after_g111/phone-portrait-compare.png) |

## Recordings (Research)

| Profile | Before | After G1.10 | After G1.11 |
| --- | --- | --- | --- |
| desktop | ![before](screens/before/desktop-recordings.png) | ![G1.10](screens/after/desktop-recordings.png) | ![G1.11](screens/after_g111/desktop-recordings.png) |
| phone-landscape | ![before](screens/before/phone-landscape-recordings.png) | ![G1.10](screens/after/phone-landscape-recordings.png) | ![G1.11](screens/after_g111/phone-landscape-recordings.png) |
| phone-portrait | ![before](screens/before/phone-portrait-recordings.png) | ![G1.10](screens/after/phone-portrait-recordings.png) | ![G1.11](screens/after_g111/phone-portrait-recordings.png) |

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
