# Lab 5 demo video

Recorded in headless Firefox (viewport only) by
`lab_web/tools/browser/record_lab5_demo.py`, from the deployed public site,
with the same recorder as Labs 1–4. The captions are added by the recorder;
they are not part of the site. The D\* Lite run shown is computed in the
browser (Pyodide); its wait is CUT, and each cut is listed with its length in
`cuts_public.json`.

| | public site (the release asset) |
|---|---|
| site | `https://gauthamcodes.github.io/coco-labs/` (deployed from `0fef157`, Pages deployment 6916595601) |
| recorded | 2026-10-07, ~17:45 UTC, after `main` was fast-forwarded to `0fef157` |
| span / frames captured | 122.47 s / 4,298 |
| cuts | 7.32 s (Pyodide start-up + warm-up, before recording); 2.21 s at 97.2 s (coco_lab running the D\* Lite episode) |
| encoded | H.264, 1120 × 920, 123.5 s, 3,615,891 B |
| sha256 | `442cc010206399fcfc9c64314cd74f13c91e9a654032942775181182b4adb3cf` |
| console errors | 0 |
| on this machine | `~/coco_lab_runs/lab5/video_public/coco_lab5_demo.mp4` |

What it shows: the command chain (global planner → local controller →
smoother → collision monitor → arbiter); the frozen room path driven by DWB
(stalling before the hairpin), MPPI (cutting the corner) and RPP (closest to
the line); the measured table after a prediction; a person crossing the
apron and one walking down the path (nobody swerved); run 15's historical
log beside the mechanism reproduction and its verdict; the D\* Lite Sketch
playing, three obstacles painted and the episode recomputed by coco_lab in
the browser, with its per-replan work against A\* from scratch; the evidence
tab.

The file is not in git (3.6 MB). Like Labs 1–4's videos, it belongs to the
release, and publishing that release is the owner's call.
