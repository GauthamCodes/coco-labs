# COCO Lab — status

Where the work stands. `README.md` (the master plan) is the authority; this
file records position only.

| | |
|---|---|
| Branch | `v2/m0-transition` (from `3571169`, coco-labs `main` fast-forwarded to `lab5`) |
| Milestone | **M0 · Transition** |
| Checkpoint | M0.3 Baseline — done |

## Checkpoint log

- **M0.1 Verify (2026-10-08).** `main` = `2b6f8ad`, `lab5` = `3571169`;
  `lab5` strictly ahead by 2 documentation-only commits. Tests at
  `3571169`: packages 3,081 / 0 / 0, `lab_web` vitest 308 / 0 / 0, build
  tools 117 / 0 / 0. Evidence: [`docs/v2/data/m0/START_STATE.md`](v2/data/m0/START_STATE.md).
- **M0.2 Freeze v1 (2026-10-08).** Annotated tag `coco-lab-v1-final` on
  `3571169`. All six releases exist and are published; five carry their
  demo video, `live-v1.0` has none by design. The three recordings
  `docs/RESULTS.md` cites by checksum resolve in `~/coco_lab_runs/`
  (3/3). Evidence: [`docs/v2/data/m0/FREEZE.md`](v2/data/m0/FREEZE.md).
- **M0.3 Baseline (2026-10-08).** Laptop, Playwright, local production
  build, 5 fresh browsers each: Pyodide cold first edit median 12,857 ms
  (6,567–42,882), warm edit median 1,445 ms (1,265–1,686), every playing
  view at 60 fps rAF with 0 long tasks; `dist/` 23,010,799 B, Pyodide
  6,358,909 B. Phone: method written, **not yet measured**. Evidence:
  [`docs/v2/BASELINE.md`](v2/BASELINE.md),
  [`docs/v2/PHONE_BASELINE.md`](v2/PHONE_BASELINE.md), `docs/RESULTS.md`
  "COCO Lab v2 · M0 baseline".
