# Lab 3 demo video

Recorded in headless Firefox (viewport only) by
`lab_web/tools/browser/record_lab3_demo.py`, from the deployed public site,
with the same recorder as Labs 1 and 2. The captions are added by the
recorder; they are not part of the site. Every coco_lab run shown is
computed in the browser (Pyodide). The waits for those runs are CUT, and each
cut is listed with its length in `cuts_public.json`.

| | public site (the release asset) |
|---|---|
| site | `https://gauthamcodes.github.io/coco-labs/` (deployed from `ee9bd65`, Pages deployment 6864344558) |
| recorded | 2026-10-05, after `main` was fast-forwarded to `ee9bd65` |
| span / frames captured | 121.26 s / 3,593 (29.63 fps) |
| cuts | 19.41 s (Pyodide start-up + warm-up, before recording); 14.32 s at 49.99 s (coco_lab rerunning the corridor world); 3.44 s at 66.74 s (mapping the challenge drive) |
| encoded | H.264, 1120 × 920, 30 fps, 122.3 s, 5,268,119 B |
| sha256 | `0d9648909acb6365bb29856489062c339ef473a9203db7c6d69f7f03f19c4e66` |
| console errors | 0 |
| on this machine | `~/coco_lab_runs/lab3/video_public/coco_lab3_demo.mp4` |

**A first recording was discarded.** It was made from the same deployment
minutes earlier, and its in-run cuts were stamped with the monotonic clock
instead of video time (`at_video_s` 78581.53). Lab 3 is the first demo to
cut in mid-recording, so no earlier `cuts.json` was affected. The fix is in
`record_demo.py`'s `Recorder.cut`, and the video above was re-recorded with it.

The file is not in git (5.3 MB). Like Labs 1 and 2's videos, it belongs to
the release, and publishing that release is the owner's call.
