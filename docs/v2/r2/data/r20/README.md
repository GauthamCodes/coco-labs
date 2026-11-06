# R2.0 · Baseline

Base: `origin/main` `4894c76` (Merge PR #30, R1 · Research Workbench). Branch `v2/r2-byoa`, worktree
`~/coco_labs_ws/worktrees/r2`. Machine: i5-13420H, 12 cores, 15 GB, RTX 4050 (driver 580.178.04); at the start
**power-saver on battery**, on AC from 17:06Z (power-saver kept: no timing is measured in R2.0). Node 24.21.0;
Python 3.12.3 (`~/coco_labs_ws/r1_venv`, CI pins); ROS overlay `~/coco_lab_r2_ws` built clean (12 packages).
No simulator running; no phone attached (`adb devices`: empty).

## The tree is R1's final tree, byte for byte

`git diff 8b40a41 4894c76` is **empty**: main after the merge holds exactly the tree R1.9 tested
(`8b40a41`). R1.9's committed results are therefore this tree's baseline, measured on this laptop:
[`../../../r1/R1_RESULTS.md`](../../../r1/R1_RESULTS.md) "Tests and determinism" — coco_lab 1192 passed (plain venv),
gz 2, lab_web/tools 248, vitest 631 (83 files), all 12 packages (coco_lab 1197 after its lint fix), native gate
exact, determinism v1/v2/v3 0 differences, R1 parity 4,269 values 0 differences, browser checks pass; Play fps
desktop 60.07, emulated phone 60.02.

## The re-run here (2026-11-04, `tools/g2/suites.sh`): what counts and what does not

[`suites_summary.txt`](suites_summary.txt), logs in [`suites/`](suites/).

| Step | Ran on | Result |
| --- | --- | --- |
| venv install | the pristine tree (copied at 17:06Z) | ok |
| coco_lab (plain venv) | the pristine installed copy; test files read from the tree | **1191 passed, 1 failed**, 2 deselected (71 min) |
| coco_lab gz | — | 3 collection errors: R2's new test files (`test_api.py`, `test_exp_user.py`, `test_user_code.py`) were in the tree but their modules were not in the pristine install |
| everything after | — | **stopped** at lab_web/tools: R2.1–R2.2 work had begun in the tree, so these steps would no longer measure the baseline (and would have rebuilt `dist/` under the R2.2 browser tests) |

The one failure is **not a baseline failure**: `test_numerics_v3.py::test_no_pow_operator_on_floats_in_the_model`
reads every `coco_lab/*.py` *from the tree* and flagged `user_code.py:106` — R2.1's new file using `**` on its
integer branch. Fixed in R2.1 (`pow()` for integers, exact); the test then passes (20/20). The run was started
before any R2 code existed; the R2 files appeared in the tree while it ran. Lesson recorded: never edit a tree a
suite is reading.

Every suite runs on the R2 tree at R2.9 (and focused suites at each checkpoint).

## Before screenshots

Main's tree is R1's final tree, so R1.9's committed *after* screenshots are R2's *before* (same pixels a fresh capture
of this tree would give; desktop and both **emulated** Nothing Phone (1) orientations — no real phone attached):

| Surface | Desktop | Phone landscape (emulated) | Phone portrait (emulated) |
| --- | --- | --- | --- |
| Workbench | [`desktop-workbench.png`](../../../r1/screens/after/desktop-workbench.png) `fc1f68f5…` | [`phone-landscape-workbench.png`](../../../r1/screens/after/phone-landscape-workbench.png) `0daa6582…` | [`phone-portrait-workbench.png`](../../../r1/screens/after/phone-portrait-workbench.png) `9bdba4e3…` |
| Compare | [`desktop-compare.png`](../../../r1/screens/after/desktop-compare.png) `6362da1a…` | [`phone-landscape-compare.png`](../../../r1/screens/after/phone-landscape-compare.png) `65d704d2…` | [`phone-portrait-compare.png`](../../../r1/screens/after/phone-portrait-compare.png) `22e0c9b1…` |
| Learn | [`desktop-learn.png`](../../../r1/screens/after/desktop-learn.png) `31a5092e…` | [`phone-landscape-learn.png`](../../../r1/screens/after/phone-landscape-learn.png) `84ae8820…` | [`phone-portrait-learn.png`](../../../r1/screens/after/phone-portrait-learn.png) `7da750da…` |

(sha256 prefixes; full digests in [`before_screens.sha256`](before_screens.sha256).)
