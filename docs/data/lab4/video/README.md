# Lab 4 demo video

Recorded in headless Firefox (viewport only) by
`lab_web/tools/browser/record_lab4_demo.py`, from the deployed public site,
with the same recorder as Labs 1–3. The captions are added by the recorder;
they are not part of the site. Every coco_lab run shown is computed in the
browser (Pyodide). The waits for those runs are CUT, and each cut is listed
with its length in `cuts_public.json`.

| | public site (the release asset) |
|---|---|
| site | `https://gauthamcodes.github.io/coco-labs/` (deployed from `0cb5588`, Pages deployment 6894319926) |
| recorded | 2026-10-06, ~20:25 UTC, after `main` was fast-forwarded to `0cb5588` |
| span / frames captured | 95.83 s / 1,795 (18.73 fps) |
| cuts | 10.61 s (Pyodide start-up + warm-up, before recording); 4.90 s at 23.49 s (coco_lab running both searches) |
| encoded | H.264, 1120 × 920, 30 fps, 96.9 s, 2,505,787 B |
| sha256 | `979ee7d57ca367f6fb3ff89a2d88ebf5607cba7c8b76e840c1316b862ea97ed8` |
| console errors | 0 |
| on this machine | `~/coco_lab_runs/lab4/video_public/coco_lab4_demo.mp4` |

What it shows: the robot told only "red"; coco_lab's plan before any look;
a learner's order (Bay 1 → 4), the prediction, the target placed in Bay 1;
the reveal (the robot's order cheaper on average — 30.4 m against 32.3 m
expected — and, on that one placement, the learner's order cheaper: 12.7 m
against 48.3 m driven); the robot's negative search, belief moving after
each miss; the Gazebo Replay of A1 (told "red", three empty bays, found in
the fourth) with its state machine in simulator seconds and the truth
toggle; the evidence tab with the matrix.

**Recorded before one cosmetic fix.** The matrix in the video shows
`COMPLETE (--)` (the executive's "no reason" placeholder) and
`COMPLETE (LOCALIZATION_DEGRADED)`; the site was then changed to say
`COMPLETE` and `COMPLETE (after a relocalisation)` (`3529f8b`). The
numbers are the same.

The file is not in git (2.5 MB). Like Labs 1–3's videos, it belongs to the
release, and publishing that release is the owner's call.
