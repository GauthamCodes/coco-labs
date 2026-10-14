# M5.2 relocation evidence · 2026-10-14

Evidence class: TESTED (repository structure); historical MODEL/STACK/REMOTE claims retain their classes.

## Moved with git mv

- CLAUDE.md → docs/archive/robot_stack/CLAUDE_robot_stack.md (byte-identical to 1d9fbdb).
- PROJECT_STATE.md → docs/archive/robot_stack/PROJECT_STATE_full.md (Markdown targets repaired for new depth; claim text retained).
- docs/STATUS.md → docs/v2/STATUS_HISTORY.md (relative Markdown targets repaired; historical claims retained).
- train_curriculum.sh → coco_rl/scripts/train_curriculum.sh.
- train_curriculum.sh.next → coco_rl/scripts/train_curriculum.sh.next.
- resume_curriculum.sh → coco_rl/scripts/resume_curriculum.sh.
- overnight_chain.sh → coco_rl/scripts/overnight_chain.sh.
- watch_training.py → coco_rl/scripts/watch_training.py.

New small pointer pages replace root CLAUDE and PROJECT_STATE. AGENTS has 178 lines; STATUS has 81 lines at structural check. Bash root discovery traverses ../..; login hook and resume invocation follow new paths. Bash syntax checks and Python AST parsing pass; no training/simulator is run.

Active references repaired in docs/RUNNING.md, docs/DESIGN_DECISIONS.md, coco_rl/policies/README.md and coco_rl/coco_rl/evaluate.py. Repository search found no test, Dockerfile or CI reference to these root scripts. Immutable milestone prompts and archived lore preserve historical filenames. RESULTS receives an appended relocation note. setup_env.sh and verify_all.sh are not RL-only and remain at root.

## Untracked cache only (physical files retained)

- node_modules/.vite/vitest/CACHEDIR.TAG
- node_modules/.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json
- node_modules/.vitest-cache/0382dc3d4c2c421d6ae017243937f71c7f530f05
- node_modules/.vitest-cache/6de35c4680b8b8b214c771fc93422bea8e7ead66
- node_modules/.vitest-cache/CACHEDIR.TAG
- node_modules/.vitest-cache/_metadata.json

## Verification

- Archived CLAUDE compared byte-for-byte with git show 1d9fbdb:CLAUDE.md.
- PROJECT_STATE and prior STATUS compare identically after replacing only Markdown link targets with placeholders; no claim text changed.
- Six cached files still exist physically, are absent from the index and covered by /node_modules/.
- Bash -n passes moved shell scripts and touched comment-only runner files; watch_training.py parses with Python ast.
- Active agent-rule comment references in scripts/run_all_package_tests.sh and scripts/live_check/run_b.sh now point to AGENTS.md.
- Two late M5.1 harnesses recorded conditions but failed the strict source-format check. Import/output formatting now matches its start/end convention; original data unchanged. conditions-recheck.txt: 44 passed; tools-clean.txt: 195 passed.
- The first package run passed all 3534 tests but its runner exited 2 after a comment edit while executing. This operational mistake is retained in packages.txt; the clean rerun passed all 12 packages (3534 tests), packages-clean.txt.
- Before M5.3: five canvas scenes have zero differing pixels; five recording replays pass; all 22 URL forms and six archive views pass with zero console errors. The first URL attempt lacked local /v1; pinned deploy archive was verified/copied unchanged, and the clean run passes. No old URL loses a home.
- Conditions: balanced, AC online, NVIDIA RTX 4050 driver 580.178.04; no robot/simulator batch active. Browser correctness checks are not frame-rate measurements. Real phone not connected (adb.txt).
