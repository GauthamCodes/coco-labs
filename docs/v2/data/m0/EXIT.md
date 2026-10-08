# M0 exit checks (2026-10-08)

Run on the head of `v2/m0-transition` after M0.8 (`9480faa`), same
machine and conditions as `START_STATE.md` (idle, no simulator; the
overlay was synced from the worktree, which differed from `9480faa` only
by this directory and `lab_web/tools/perf/copycheck.mjs`, neither in a
ROS package).

## Tests (before → after)

| suite | before (`3571169`) | after (`9480faa`) | evidence |
|---|---|---|---|
| `scripts/run_all_package_tests.sh` | 3,081 / 0 / 0 | 3,081 / 0 / 0 (per package identical to before) | `packages_after.txt` |
| `lab_web` typecheck + vitest | 308 / 0 / 0 | 308 / 0 / 0 | `vitest_after.txt` |
| `lab_web/tools` | 117 / 0 / 0 | 117 / 0 / 0 | `tools_after.junit.xml` |

No count decreased; nothing deleted. `lab_web/test/live.test.ts` changed
three expected strings (M0.6 copy), not its number of tests.

## Every public view loads (local production build of the M0.8 tree)

`npm run build` (Node 24.21.0) after `build_catalog.py`; `check_dist`
failures none, `tree_sha256 27c2f0d9…53642`; served by `vite preview`;
Playwright Chromium 156.0.8078.4 headless, a fresh browser per view
(`exit/load.json`):

| view | console errors |
|---|---|
| `?view=plan` | 0 |
| `?view=localise` | 0 |
| `?view=map` | 0 |
| `?view=search` | 0 |
| `?view=move` | 0 |
| `?view=live` | 3 — all three the browser's network error for the coco.v1 socket to `ws://localhost:8080/ws` (connection refused: no local Stack running). The v1 build logged the same, plus once the remote `/healthz` host not resolving (`perf/baseline.json`, `load`: 3 errors; `fps` runs: 2–4). Behaviour unchanged by M0; parked in `docs/IDEAS.md`. |

## The honesty copy is on screen (`exit/copycheck.json`, screenshots)

At 1400 × 1000 and 390 × 844, in all six views: no visible "real robot"
text; "Live Stack (simulated)" in the navigation everywhere; the Live
view also shows "scheduled demo" and "full ROS 2 stack (simulated)"; the
Search Replay tab reads "The full ROS 2 stack (simulated) — Replay"; no
horizontal overflow at 390 px. Command:
`node tools/perf/copycheck.mjs --out ../docs/v2/data/m0/exit`.

## README is in place

`README.md` is byte-identical to `~/Downloads/README.md` (sha256
`4b003e50c28f8a217ce7315c2574cd123da959d2d61eeff92a4c053d451a2ab6`, `cmp`
clean).
