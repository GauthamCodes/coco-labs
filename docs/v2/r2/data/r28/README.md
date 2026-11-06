# R2.8 · Phone and Learn — TESTED (emulated phone; the real phone was not connected)

## Phone

`adb devices` (the workspace's adb, 2026-11-04 and 2026-11-05): **no device**. Every phone result here is the
**emulated** Nothing Phone (1) (`lab_web/tools/phone/nothing-phone-1.mjs`: 412×915 / 915×412, DPR 2.625, touch, Android
UA) and never counts as the phone. Pending: plug the Nothing Phone (1) in with USB debugging; the agent measures it.

From `studio_check.mjs` ([`../../screens/r23/studio_check.json`](../../screens/r23/studio_check.json)):

| Check | Landscape | Portrait |
| --- | --- | --- |
| The Studio loads; the note "On a phone the editor is basic: reading, running and comparing work fully, but for long edits upload a .py file or use a laptop" is shown | yes | yes |
| Run reachable (48 px target), no sideways page scroll | yes (overflow 0) | yes (overflow 0) |
| The A* starter runs in the sandbox (2 sandboxes at most on phones in experiments) | **found**, deterministic | — |

Layout: in landscape the editor and the view sit side by side; the drawing is one scroll below the editor's top (listed
for Gautham's review in [`../../BEFORE_AFTER.md`](../../BEFORE_AFTER.md)). Editing long code on a phone is basic and the page
says so instead of hiding it.

## Learn

The two teaching starters appear on the Learn page as **"Try it yourself"** beside their missions
(`lab_web/src/learn/LearnPage.tsx`, `MISSION_STARTERS`): mission 1 *Find a path* → "Write A*'s heuristic yourself"
(`teach_heuristic`), mission 5 *Avoid things* → "Tune DWA's critic weights" (`teach_tune_dwa`); each opens the Studio
with that starter (`?view=workbench&tab=studio&template=…`). Checked by `studio_check.mjs` (both links present).

## API reference

[`../../API.md`](../../API.md): the three contracts, every type (ROS 2 message shapes), `ctx`, validation, the `ctx.emit`
event kinds and how each is drawn, what a file may import (the guard), determinism, worked examples (a planner, a
controller), experiments, the leaderboard, ROS 2. Linked from the Studio ("API reference").
