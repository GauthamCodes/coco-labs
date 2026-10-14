# M5.0 baseline — 2026-10-14

Source: `6c286b7c51c9b550bfb90cdf96e2f53ba3b31cf2` (M4 merge), canonical checkout, branch `v2/m5-focus`. No product code changed during setup. Evidence class: MODEL (automated regression checks; no performance budget claimed).

## Conditions and commands

`conditions.json` records the device, AC state, balanced profile and NVIDIA driver 580.178.04. The original profile was balanced and was not changed. The process check found no simulator or robot-project batch. Node 24.21.0 matches `lab_web/.nvmrc`; npm 11.19.0; Python 3.12.3 uses `~/coco_labs_ws/test_venv`.

The canonical overlay predates M3 and has no installed `coco_schemas`. Source paths below make the tests consume this checkout's schema and library. The venv's networkx 2.8.8 is placed first by the package runner when `COCO_TEST_PYTHON` is unset.

```bash
export PATH=/home/gautham/coco_v2_ws/node/node-v24.21.0-linux-x64/bin:$PATH
export PYTHONPATH=/home/gautham/coco_labs_ws/src/coco-labs/coco_schemas:/home/gautham/coco_labs_ws/src/coco-labs/coco_schemas/coco_schemas/gen:/home/gautham/coco_labs_ws/src/coco-labs/coco_lab:/home/gautham/coco_labs_ws/src/coco-labs/coco_config
NODE_OPTIONS=--test-reporter=tap ROS_DOMAIN_ID=78 scripts/run_all_package_tests.sh
PYTHONDONTWRITEBYTECODE=1 /home/gautham/coco_labs_ws/test_venv/bin/python -P -m pytest -q -p no:cacheprovider lab_web/tools
PYTHONDONTWRITEBYTECODE=1 /home/gautham/coco_labs_ws/test_venv/bin/python lab_web/tools/build_catalog.py
cd lab_web
npm ci
npm run arena-assets
npm run typecheck
npm test
```

Catalog generation and arena asset generation must be sequential: the catalog builder recreates generated output. Running them together caused the initial attract build to lose its source zip; the sequential retry passed. No recorded evidence was removed.

## Results

- Package suite: 3523 passed, 0 failed, 0 skipped across all 12 packages (`packages-pinned.txt`).
- Web: typecheck passed (`typecheck.txt`); vitest 436 passed, 0 failed, 0 skipped, 46 files (`vitest-ready.txt`).
- Build tools: 192 passed, 0 failed, 0 skipped (`tools.txt`).

Initial attempts are retained: web tests before runtime asset generation failed (`vitest.txt`); package baseline without TAP reporting/source schema paths failed (`packages.txt`), and its explicit interpreter override let user-site networkx 3.6.1 precede the venv pin. The same web code passes with generated assets. The frame decoder's three Node tests passed in the failed Python wrapper: its assertion expects TAP text, while Node emitted its spec reporter. Explicit TAP passes (`coco_web-tap.txt`). Adapter tests pass with source schema paths (`adapter-source-path.txt`, 145 passed). No assertions or product code were changed to obtain a pass.

No M5 performance measurement, GPU comparison, phone result or usability score is claimed. The pre-M5 notes are an unfilled template; Nothing Phone (1) is recorded by Gautham in the session, with all result fields pending.
