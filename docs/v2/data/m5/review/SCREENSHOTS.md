# Independent review screenshots — 2026-10-20

Actual laptop Chromium; phone dimensions/touch/CPU/network are **emulated**.
Compared by eye with [original closure captures](../close/SCREENSHOTS.md).
Corrected completed navigation evidence: browser-ac-debug/checks.json (first
three viewports), browser-portrait-ac/checks.json (portrait). Earlier failed
harness attempts are retained and superseded, not acceptance results.

| Viewport | My Play | Compare | Recordings / issue |
| --- | --- | --- | --- |
| 1440×900 | [Play](browser-ac-debug/desktop-play.png) | [4 panes](compare-layouts-ac/desktop-4.png) | [Library](browser-ac-debug/desktop-recordings.png); Settings persistence and dialog STOP fixed. |
| 844×390 | [Play](browser-ac-debug/compact-play.png) | [4 panes](compare-layouts-ac/compact-4.png) | [Library](browser-ac-debug/compact-recordings.png); no Play scroll, 7 controls. |
| Emulated phone 915×412 | [Play](browser-ac-debug/nothing-landscape-play.png) | [4 panes](compare-layouts-ac/nothing-landscape-4.png) | [Library](browser-ac-debug/nothing-landscape-recordings.png); [safe insets](browser-ac-debug/nothing-landscape-play-safe-insets.png), 8 controls. Secondary-touch STOP fixed. |
| Emulated phone 412×915 | [Rotate card + STOP](browser-portrait-ac/nothing-portrait-play.png) | [4 panes](compare-layouts-ac/nothing-portrait-4.png) | [Library](browser-portrait-ac/nothing-portrait-recordings.png); 2 controls; metrics scroll internally across panes. |

[Held W / STOP](stop-driving-fixed-desktop.png) and [two fingers / STOP](stop-driving-fixed-two-fingers.png)
show the corrected latched stop. Fullscreen/orientation APIs were deliberately
denied; synthetic safe insets were applied (landscape left44/bottom16,
portrait top44/bottom16). This is not evidence of physical Android behavior.
The original capture's portrait card had no reachable STOP. The review adds it.
No owner aesthetic approval is inferred.
