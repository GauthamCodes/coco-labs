# Deploy 1 (R3 Part A): R2 + the Theta\* entry live — TESTED on the public site

- Merged to main: PR #32 (R2) `5df4427`, #33 `90c3dce`, #34 `bbc94ca`, #35 `56e9318`, #31 (Gautham's
  Lazy Theta\*) `adde736`.
- Deploy: `gh workflow run lab.yml --ref main -f confirmation=DEPLOY` → run **42356268133** on `adde736`,
  2026-11-07; every job green, "Deploy site" success.
- Live smoke test: `lab_web/tools/r3/live_smoke.mjs https://gauthamcodes.github.io/coco-labs/` (headless
  Chromium, software GL, laptop on AC/balanced while the R3.2 baselines ran on 10 cores).

| attempt | result | notes |
| --- | --- | --- |
| 1 ([`smoke.json`](smoke.json)) | the open tab (opened before the deploy finished) showed **"New version ready"** and was **not reloaded**; title, Play, Compare, Workbench, Leaderboard (Theta\* listed), Learn ok, 0 page errors; **Studio FAIL** | the script read the Studio's results table while its status still said "running…" (a script defect, not the site) |
| 2 ([`attempt2/`](attempt2/smoke.json)) | Studio ok ("found ✓"); then a screenshot of the busy page timed out | a screenshot is evidence, not a site function: made non-fatal |
| 3 ([`attempt3/`](attempt3/smoke.json)) | **PASS**: title, Play (COCO moves under AUTO), Compare, a Workbench experiment (digest `d4d0646135b6bd5a…`, the same in all three attempts), the Studio A\* starter (found), the Leaderboard (Theta\* listed), Learn; 0 page errors | |

The real phone (A3.4): not connected (`adb devices` empty) — pending, connect the Nothing Phone (1) over USB.
