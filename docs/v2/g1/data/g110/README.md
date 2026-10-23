# G1.10 — Close: suites, corpora, link and replay checks

Cloud container (Xeon 2.1 GHz × 4, SwiftShader, no GPU, no ROS, no `protoc`), the final G1
source. Results table: [`../../G1_RESULTS.md`](../../G1_RESULTS.md#tests-before--after).

- [`suites/`](suites/): coco_lab (`-rs`), lab_web/tools, vitest, typecheck, catalog, arena
  assets, build, `check_dist`, `v1_links_check`, `replay_check`, `screenshots check`, and
  the `coco_schemas --check` attempt (fails here: no `protoc`).
- [`determinism-v1/`](determinism-v1/): the M1 corpus (100 sessions × 150 ticks, hash v1)
  on Pyodide-in-Node vs the committed M1 reference: `determinism.json` pass, 0 mismatches.
- [`determinism-v2/`](determinism-v2/): the M5 v2 corpus (100 × 150) on Pyodide-in-Node and
  Chromium vs M5's reference: pass, 0 mismatches, 0 page errors. Runner:
  [`rerun_determinism.py`](rerun_determinism.py) (M5's review runner with portable paths).

**Conditions.** This container's Playwright (1.64) does not match its installed browsers.
Chromium ran through `G1_CHROMIUM` (determinism) or a scratch `PLAYWRIGHT_BROWSERS_PATH`
linking Playwright's expected path to the installed Chromium 141 (the v1, replay and
screenshot checks); nothing in the repository was changed for that. Firefox and WebKit
could not be driven (protocol mismatch, no downloads): CI's three-browser job covers them on
every push; **the four-engine 100-session v2 corpus is pending: laptop.** The frozen `/v1`
site was fetched and verified by `lab_web/tools/fetch_v1_site.sh` (v1-site `36e6500`, tree
`6857ff56…`, 84 files) before the URL check.
