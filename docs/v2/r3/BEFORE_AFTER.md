# R3 · Before and after (for Gautham's review — a soft gate)

Before: main at R2's merge (R2.9's committed after-screenshots, [`../r2/screens/r29/`](../r2/screens/r29/)). After:
the R3 branch's final tree `a4b3d95` ([`screens/r39/`](screens/r39/); checksums in
[`data/r39/after_screens.sha256`](data/r39/after_screens.sha256)). Desktop 1440×1000 and the **emulated** Nothing
Phone (1) (412×915, DPR 2.625; never the real phone, which was not connected).

| Surface | Before (R2) | After (R3) | What changed |
| --- | --- | --- | --- |
| Leaderboard | [desktop](../r2/screens/r29/desktop-leaderboard.png) · [landscape](../r2/screens/r29/phone-landscape-leaderboard.png) · [portrait](../r2/screens/r29/phone-portrait-leaderboard.png) | [desktop](screens/r39/desktop-leaderboard.png) · [landscape](screens/r39/phone-landscape-leaderboard.png) · [portrait](screens/r39/phone-portrait-leaderboard.png) | v1 boards for every suite and family (control and localisation are new), success per tier, **Contacts** beside success on control boards, a Submit guide, the Waypoint driver described as a plan reference |
| Model vs ROS 2 (new tab) | — | [desktop](screens/r39/desktop-model-vs-ros2.png) · [landscape](screens/r39/phone-landscape-model-vs-ros2.png) · [portrait](screens/r39/phone-portrait-model-vs-ros2.png) | the browser model against Nav2 in Gazebo on the same scenarios: confusion tables, agreement, ratios; paired runs downloadable |
| About | — | [desktop](screens/r39/desktop-about.png) · [landscape](screens/r39/phone-landscape-about.png) · [portrait](screens/r39/phone-portrait-about.png) | "Cite" (BibTeX, author Gautham, no affiliation) and "Reproduce this paper" (one link to the depot-nav-100 planning baseline) |

## Looks to judge

1. The Model vs ROS 2 tab is one long page of tables (9 of them, one per suite and family). Enough as is, or group by family behind tabs?
2. The Leaderboard's control boards rank the Waypoint driver first (it never fails: it is a plan reference without a
   local collision check, as its description says). Keep it ranked, or show it outside the ranking?
3. The Leaderboard tables still scroll sideways inside their cards on a phone (unchanged from R2).
