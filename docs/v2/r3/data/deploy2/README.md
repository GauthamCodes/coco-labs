# Deploy 2 (R3): COCO-Bench v1, the Model vs ROS 2 tab, Leaderboard v1 and the paper's link live — TESTED on the public site

- Merged to main: **PR #36** "R3 · COCO-Bench v1 and the paper" as `62096d1` (merge commit; branch kept), after CI on
  the exact head `8e2a075` was all green (runs 42565958474, 42565958405, 42565958393), the local close passed
  ([`../r39/README.md`](../r39/README.md)) and a self-review was posted on the PR. No stop condition fired.
- Deploy: `gh workflow run lab.yml --ref main -f confirmation=DEPLOY` → run **42571842915** on `62096d1`,
  2026-11-09; every job green, "Deploy site" success ([`deploy.log`](deploy.log)).
- Laptop on AC, balanced profile; headless Chromium, software GL.

| check | result |
| --- | --- |
| live smoke ([`smoke.json`](smoke.json), `lab_web/tools/r3/live_smoke.mjs`) | **PASS**: a tab opened *before* the deploy finished showed **"New version ready"** and was not reloaded; title, Play (COCO moves under AUTO), Compare, a Workbench experiment (digest `d4d0646135b6bd5a…`, the same as deploy 1), the Studio A\* starter (found), the Leaderboard (Theta\* listed), Learn; 0 page errors |
| R3 surfaces on the live site ([`screens.json`](screens.json), [`screens/`](screens/), `lab_web/tools/r3/screens.mjs`) | **PASS**: control and localisation boards, a Contacts column on every control board, tiers and the Submit guide, the Model vs ROS 2 tables, the Reproduce link; no sideways page scroll on the emulated phone either way; 0 page errors |
| **"Reproduce this paper"** ([`reproduce.json`](reproduce.json), `lab_web/tools/r3/reproduce_check.mjs`) | **Reproduced exactly**: About's link carries the committed digest `e32dc88b…`; opening it re-ran all 600 runs in the browser in 172 s and the page's own check said "every run's status, hash chain and counts match the link"; 0 page errors |

The real phone: not connected — pending.
