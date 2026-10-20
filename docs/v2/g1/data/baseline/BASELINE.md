# G1.0 baseline (2026-10-20)

Tree: `b9b42d4` = `origin/v2/m5-focus` (`ddc3718`; PR #25 open, not merged) with
`origin/v2/m6-foundations` (`984b2cf`) merged (no conflicts). Development branch:
`claude/serene-davinci-v9y796` (the session's designated branch; the prompt's name
`v2/g1-game-look` is noted in `G1_STATUS.md`).

**Environment: cloud container**, not the laptop. Intel Xeon @ 2.10 GHz, 4 vCPUs, 15 GB;
no GPU (Chromium renders with SwiftShader, `ANGLE (Google, Vulkan 1.3.0 (SwiftShader
Device (Subzero)))`); no ROS 2, no Gazebo, no `gz`, no protoc, no phone. Python 3.12.3
venv with `coco_lab/requirements-test.txt` pinned versions (as CI's `coco_lab in a
plain venv`); Node 24.21.0 (`lab_web/.nvmrc`, official tarball, sha256 checked).

| Suite | Result | Log |
| --- | --- | --- |
| `coco_lab` (CI route: plain venv, the three ament linters ignored) | 1006 passed, 0 failed, 2 skipped (the `gz` CLI test; the repository-checkout test) | `coco_lab.txt` |
| `lab_web/tools` (build-tool tests) | 220 passed, 0 failed, 0 skipped | `tools.txt` |
| `build_catalog.py` | ok | — |
| `npm run typecheck` | ok | — |
| `npm run arena-assets` | ok | — |
| `lab_web` vitest | 493 passed (62 files), 0 failed | `vitest.txt` |
| `npm run build`, `check_dist.mjs` | ok; title-critical app+worker 271801 gzip bytes | `dist.txt` |
| ROS packages (`scripts/run_all_package_tests.sh`: coco_config, coco_schemas, coco_lab_ros, coco_sim, coco_web, …) | **not run: no ROS 2 / protoc in the cloud container — pending: laptop** | — |

Before screenshots: `docs/v2/g1/screens/before/` (`shots.json` records the renderer and
per-shot readiness). On SwiftShader the M5 Play 3D scene did not report ready within
180 s, so the "play" shots show M5 Play's top-down presentation; this is the cloud's
software renderer, not a phone or laptop result.
