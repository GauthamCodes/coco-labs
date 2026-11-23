# R4 · deploy (2026-11-11)

PR #39 "R4 · Learn Course" merged as `5a9f54d` under the gate (exact head `309150a`: all five CI jobs green; self-review
on the PR). Deployed by `gh workflow run lab.yml --ref main -f confirmation=DEPLOY`: run 42893898506, success.

Live smoke on https://gauthamcodes.github.io/coco-labs/ (laptop, Chromium via Playwright):

| check | result | file |
| --- | --- | --- |
| R3's smoke: title, Play (AUTO moves), Compare, Workbench experiment, Studio A* starter, Leaderboard (Theta* listed), Learn (now the course), no page errors | **PASS** | [smoke/](smoke/) |
| a code exercise passed ON THE LIVE SITE: "Write A*'s heuristic" and "Write Nav2's inflation cost", the reference files typed into the editor and checked; each grade's digest equals the native grade's | **PASS** (2/2, digests equal) | [live_course.json](live_course.json) |
| one full Explorer lesson by taps (predict → observe → explain → try: the tune exercise graded in the page → check → In real ROS 2) on the EMULATED Nothing Phone (1), landscape, 4x CPU | **PASS** (6/6) | [live_phone_explorer.json](live_phone_explorer.json) |
