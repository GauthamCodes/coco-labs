# R2 · Before and after (for Gautham's review — a soft gate)

Before: main `4894c76` (= R1's final tree; R1.9's committed after-screenshots, checksummed in
[`data/r20/before_screens.sha256`](data/r20/before_screens.sha256)). After: the R2 branch at R2.9
([`screens/r29/`](screens/r29/), the final tree `7eaa7b6`; checksums in
[`data/r29/after_screens.sha256`](data/r29/after_screens.sha256)). Desktop 1440×1000 and the **emulated** Nothing Phone (1) (412×915, DPR 2.625;
never the real phone, which was not connected).

| Surface | Before (R1.9) | After (R2) | What changed |
| --- | --- | --- | --- |
| Workbench | [desktop](../r1/screens/after/desktop-workbench.png) · [landscape](../r1/screens/after/phone-landscape-workbench.png) · [portrait](../r1/screens/after/phone-portrait-workbench.png) | [Studio](screens/r29/desktop-studio-start.png) · [planner GAME](screens/r29/desktop-studio-planner-game.png) · [SIM](screens/r29/desktop-studio-planner-sim.png) · [Compare](screens/r29/desktop-studio-compare.png) · [controller](screens/r29/desktop-studio-controller.png) · [link consent](screens/r29/desktop-studio-link-consent.png) · [teaching starter](screens/r29/desktop-studio-teach.png) · [Leaderboard](screens/r29/desktop-leaderboard.png) · phone Studio [landscape](screens/r29/phone-landscape-studio.png), [run](screens/r29/phone-landscape-studio-run.png), [portrait](screens/r29/phone-portrait-studio.png) · phone Leaderboard [landscape](screens/r29/phone-landscape-leaderboard.png), [portrait](screens/r29/phone-portrait-leaderboard.png) | two new tabs: **Algorithm Studio** (first) and **Leaderboard** |
| Compare | [desktop](../r1/screens/after/desktop-compare.png) · [landscape](../r1/screens/after/phone-landscape-compare.png) · [portrait](../r1/screens/after/phone-portrait-compare.png) | unchanged page; your algorithm beside a built-in lives in the Studio ([Compare](screens/r29/desktop-studio-compare.png)) | — |
| Learn | [desktop](../r1/screens/after/desktop-learn.png) · [landscape](../r1/screens/after/phone-landscape-learn.png) · [portrait](../r1/screens/after/phone-portrait-learn.png) | [desktop](screens/r29/desktop-learn.png) · [landscape](screens/r29/phone-landscape-learn.png) · [portrait](screens/r29/phone-portrait-learn.png) | "Try it yourself" beside missions 1 (find a path → write the heuristic) and 5 (avoid things → tune DWA) |

## Looks to judge

1. The Studio on a phone in landscape: editor and view side by side; the drawing sits one scroll below the
   fold. Acceptable for reading, running and comparing (stated in the page), or should the view come first?
2. GAME vs SIM drawing of a run: the 2D top-down view (not the 3D Play renderer). Is a 3D view of user runs
   wanted (R3/R4)?
3. The Leaderboard table width on a phone (it scrolls sideways inside its card).

## Found by the close-out audit and fixed

- The Studio on the **light theme**: the editor's syntax colours were the dark theme's (1.1–1.9:1 contrast on the
  light editor, 92 text nodes). Now light-theme colours of 5.2–14.9:1; the accessibility audit passes on all 24 pages
  ([`data/r29/README.md`](data/r29/README.md)). The screenshots above are the default (dark) theme.
