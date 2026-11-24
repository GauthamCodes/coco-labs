# R4 Part A · deploys and live smoke (2026-11-22 to 2026-11-24)

| what | result | evidence |
| --- | --- | --- |
| PR #38 (Theta\* v1 claim) | merged `4d52d63` (exact head `242c5ab` all green; local verify VERIFIED) | PR #38 self-review |
| deploy of `4d52d63` | run 45055100174 success; live smoke **PASS** 9/9; live board: Theta\* held-out 20/20, secret held-out 20/20 | [`../deploy_a1/`](../deploy_a1/) |
| PR #42 (Gazebo repeats 2-3, paper macros) | merged `129ee48` (exact head `05ca436` all green; local suites green, determinism Chromium + Firefox = Pyodide reference, WebKit in CI) | PR #42 self-review |
| deploy of `129ee48` | run 45295291339 success; live smoke **PASS** 9/9 (an open tab showed "New version ready" without a reload; title, Play AUTO moves, Compare, Workbench digest, Studio A\* found, Leaderboard with Theta\*, Learn, 0 page errors) | [`smoke.json`](smoke.json), [`smoke.log`](smoke.log) |
| live data | `generated/r3/gap.json`: 3 repeats for every control/localisation kind; DWB agreement 37/70, MPPI 39/70 | |

Laptop (i5-13420H), AC, balanced; Chromium via Playwright 1.64 (browsers reinstalled 2026-11-22/24: a disk cleanup had
removed them, so the first smoke attempt on 2026-11-22 failed before reaching the site).
