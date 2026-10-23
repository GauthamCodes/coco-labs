# M5.4 Night Shift references · awaiting Gautham's review

These are browser renders of the existing arena and COCO CAD mesh, with real
Python planner results and an existing recorded MODEL demo. No drawn mock scene,
new world, made-up trajectory or experimental result is used.

| Viewport / device | Title | Play HUD | Compare, two panes |
| --- | --- | --- | --- |
| Desktop 1440 × 900 CSS px | [Title](final/desktop-title.png) | [Play](final/desktop-play.png) | [Compare](final/desktop-compare.png) |
| Compact 844 × 390 CSS px | [Title](final/compact-title.png) | [Play](final/compact-play.png) | [Compare](final/compact-compare.png) |
| Emulated Nothing Phone (1), 915 × 412 | [Title](final/nothing-landscape-title.png) | [Play](final/nothing-landscape-play.png) | [Compare](final/nothing-landscape-compare.png) |
| Emulated Nothing Phone (1), 412 × 915 | [Title](final/nothing-portrait-title.png) | [Rotate card](final/nothing-portrait-play.png) | [Stacked Compare](final/nothing-portrait-compare.png) |

Phone: shared Playwright profile, DPR 2.625, touch/mobile, CPU throttled 4× as a
proxy. Screenshots use CSS pixels. Local assets are unthrottled for these layout
checks; these are not cold-start, phone frame-rate or heat measurements.
`final/references.json` records actual viewports, renderer, GL context counts, console
errors, power, AC and driver. No real phone is connected (`../../phone/ADB_CHECK_M54.txt`).

Colour-vision simulation: [protanopia](final/desktop-compare-protanopia.png),
[deuteranopia](final/desktop-compare-deuteranopia.png). [Light Compare](desktop-compare-light.png).
Both-theme labelled palette sheets (`palette-*.png`) include all six computation
roles and redundant shapes. See [method and limits](../../design-system/COLOUR_REVIEW.md).
Simulation is not a human usability result.

The root captures and `initial/`, `first-refinement/`, `second-refinement/`,
`third-refinement/` and `fourth-refinement/` retain earlier visual iterations.
`final/` is the canonical capture set for the checkpoint. The initial font-CSP error is fixed by emitting local hashed font
files; no CSP widening was needed. Prior deterministic canvas baselines remain
under `../pre-night-shift/`; their model recordings and hashes are unchanged.

The reference query (`?reference=title|play|compare`) is diagnostic in M5.4.
M5.5 migrates the actual title/routes; M5.6 completes Play's camera/scan/game UI;
M5.7 completes the Compare workspace. Review is a soft gate; implementation
continues without waiting, and recorded feedback is applied next checkpoint.
