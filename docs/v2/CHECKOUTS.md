# Checkouts: which tree is COCO Lab's

Recorded 2026-10-08 (M1 step B.1), under the owner's plan change of the
same date (`docs/STATUS.md`, plan-change log).

| Checkout | Role |
|---|---|
| `~/coco_labs_ws/src/coco-labs` | **Canonical.** A clone of `GauthamCodes/coco-labs` (`origin`). Its `main` was fast-forwarded to the merged `main` (`9f58b83`, PR #19's merge commit) on 2026-10-08; it had no uncommitted changes and no local-only commits beforehand. `CLAUDE.md`, `setup_env.sh` and `scripts/` already default to `~/coco_labs_ws`. The overlay `~/coco_labs_ws/install` is rebuilt from this tree (`scripts/build_overlay.sh`). |
| `~/coco_labs_ws/src/coco-labs/.claude/worktrees/<name>` | Agent worktrees of the canonical checkout, one per milestone branch (M1: `v2-m1-arena-core` on branch `v2/m1-arena-core`; M2: `v2-m2-whole-loop` on `v2/m2-whole-loop`). Each builds into its own overlay (M1: `~/coco_lab_m1_ws`; M2: `~/coco_lab_m2_ws`; `scripts/build_overlay.sh <overlay>`), so the default overlay never points into a worktree that may be removed. Ignored by git (`.gitignore`: `.claude/worktrees/`). |
| `~/ros2_ws(personal)/src/coco-robot-ros2` and its worktrees | **Legacy. Not used for COCO Lab.** It is the COCO robot project's checkout, with `coco-labs` added as the remote `labs`; its local `main` is the robot trunk. Labs 2–5 and M0 were developed in its worktrees (`.claude/worktrees/lab1`, `v2-m0`), so it holds that local history. Left untouched. |
| `~/coco_m1_ws` | **Not COCO Lab's.** The robot project's overlay for `~/coco-isaac-21` (its own M1 numbering). On 2026-10-08 the M1 session built COCO Lab into it by mistake; with the owner's approval it was restored the same day by re-running its recorded build. COCO Lab directories are prefixed `coco_lab_`. |
| `~/coco_v2_ws` | M0's copy-based overlay (the `(personal)` path broke colcon and gz quoting). Kept for its Node 24.21.0 toolchain, which M1's helpers reuse. |

## Private toolchain pieces (no sudo, nothing system-wide)

| Piece | Where | How to re-create |
|---|---|---|
| Node 24.21.0 (`lab_web/.nvmrc`) | `~/coco_v2_ws/node/node-v24.21.0-linux-x64/bin` | the official tarball for 24.21.0, unpacked there (the machine's own Node is a different major) |
| Playwright browsers (Chromium 1248, Firefox 1555, WebKit 2370) | `~/.cache/ms-playwright/` | `cd lab_web && npx playwright install chromium firefox webkit` (no `--with-deps`: that needs sudo) |
| **WebKit's four media libraries** (`libavif16`, `libgav1-1`, `libyuv0`, `libgstreamer-plugins-bad1.0-0`) | `~/coco_lab_m1_ws/webkit_libs/{debs,root}` | **`lab_web/tools/setup_webkit_libs.sh [DEST]`**: fetches the four `.deb`s at pinned versions (`apt-get download`, no root; Launchpad as a fallback), refuses any whose sha256 differs from the pinned one, unpacks them with `dpkg -x` into `DEST/root` and writes the launcher `DEST/webkit_run.sh`. Re-running is safe. Checked 2026-10-09: from an empty directory it re-created a tree identical (`diff -r`) to M1's. Use: `LD_LIBRARY_PATH=DEST/root/usr/lib/x86_64-linux-gnu node tools/perf/determinism.mjs webkit --webkit-exe DEST/webkit_run.sh …` |
| Python test venv | `~/coco_labs_ws/test_venv` (system site packages) | see `docs/STATUS.md`, M1 B.1 |

The owner's decision of 2026-10-09 (`docs/STATUS.md`, plan-change log):
keep the WebKit libraries private in `~/coco_lab_m1_ws/webkit_libs`; no
sudo, nothing installed system-wide.

## Why

- One tree, one overlay: the review of M0 (2026-10-08) flagged that
  `~/coco_labs_ws/src/coco-labs` was a stale clone (`main` = `6249e7d`)
  while `CLAUDE.md` and the scripts defaulted to it, so a session could
  build and test the wrong tree.
- The legacy checkout's path contains parentheses, which broke colcon,
  CMake and gz quoting (hence M0's copy-overlay workaround), and its
  `main` is a different repository's trunk, which made every git command
  there a hazard for COCO Lab.
- Nothing is deleted: the legacy checkout keeps the local history of Labs
  2–5 and M0; everything COCO Lab needs is on `GauthamCodes/coco-labs`.
