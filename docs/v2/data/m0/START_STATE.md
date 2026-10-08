# M0.1 — starting state (recorded 2026-10-08, before any change)

Evidence class of everything below: STACK-independent repository facts,
re-checkable with git; test counts are MODEL/website/tool test runs on this
machine (laptop, see conditions).

## Repository

- Remote `labs` = `https://github.com/GauthamCodes/coco-labs.git` (the
  COCO Lab repository; see "Where the work happened" below).
- `main` (coco-labs, `labs/main`) = `2b6f8ad8665dfe88d33b3e5c4c58bb519411c008`
- `lab5` (local and `labs/lab5`) = `35711693d11da99218fa85050db60c6e10462bd2`
- `lab5` is strictly ahead of `main` by 2 commits, `main` is its ancestor,
  0 commits on `main` not in `lab5`. The 2 commits touch documentation only:

```
 PROJECT_STATE.md    |  4 ++--
 docs/ROADMAP.md     |  9 ++++++---
 docs/SESSION_LOG.md | 48 ++++++++++++++++++++++++++++++++++++++++++++++++
 3 files changed, 56 insertions(+), 5 deletions(-)
```

- Working tree of the `lab5` worktree (`git status`):

```
On branch lab5
Untracked files:
	AGENTS.md

nothing added to commit but untracked files present
```

  `AGENTS.md` is an untracked copy of `CLAUDE.md` dated 2026-10-01 (only
  its first line differs). It is not a tracked change and was left
  untouched; M0 was done in a fresh worktree (`v2/m0-transition` from
  `3571169`) whose tree is clean.

- `git log --oneline -15` at `3571169`:

```
3571169 Lab 5 released: lab5-v1.0 published (owner-approved 2026-10-08), verified
be8969a SESSION_LOG: Phase 6 complete; lab5-v1.0 tag local + draft release
2b6f8ad SESSION_LOG: Phase 6 deployed and verified; release gate
063ff30 Phase 6 (Lab 5): deployed from 0fef157, verified on the public site, video, status
0fef157 Release notes: lab5-v1.0 (draft)
3e4c484 lab_web: catalog 1.5 pin and a Lab 5 catalog test (CI caught the stale 1.4 pin)
58f5591 Experiment C bundle regenerated at a clean commit (e5913c8); docs quote its hash
e5913c8 Lab 5 evidence regenerated from a clean tree (59a65b6): drive bundles record their commit, not dirty
59a65b6 PROJECT_STATE: Phase 6 row (implemented, tested, measured on lab5)
699e090 LAB5_MOVE §4.7: full test totals (3,081 / 0 / 0)
8cc8e61 SESSION_LOG: Phase 6 checkpoint (matrix, Experiment C, page); Lab 5 demo recorder
5cd039d Lab 5: write-up, RESULTS Phase 6, evidence README, ROADMAP/PROJECT_STATE, tables tool, browser-algorithm guard
89c69b1 Lab 5 evidence: the 54-run matrix as drive bundles, Experiment C, Sketch work statistics
4cb984f Lab 5: Experiment C capture (parked person, costmap snapshots, D* Lite on them), browser checks, glue tests
39ab63c Lab 5: bundle formats, decoders, the Move page, worker glue, site build
```

## Where the work happened

The repository whose `origin` is `GauthamCodes/coco-labs`,
`~/coco_labs_ws/src/coco-labs`, is a stale clone: its `main` is
`6249e7d` and it has no `lab2`…`lab5` branches. Every COCO Lab phase
since Lab 2 was built in the worktree `.claude/worktrees/lab1` of the old
checkout `~/ros2_ws(personal)/src/coco-robot-ros2`, whose remote `labs`
is `GauthamCodes/coco-labs` (SESSION_LOG, Phases 3–6). M0 continues
there, in a sibling worktree `.claude/worktrees/v2-m0`, and pushes to
`labs`. The local branch named `main` in that checkout is the robot
project's trunk (`9ee4a52`), not coco-labs `main`, so it was NOT moved:
the "local fast-forward" of coco-labs `main` is realised as
`v2/m0-transition` starting at `3571169` (= `main` fast-forwarded to
`lab5`) and the tag `coco-lab-v1-final` on `3571169`. The remote `main`
moves only when the owner merges the M0 pull request.

## Tests, clean build of `3571169`

Conditions: laptop (i5-13420H, 12 threads, 15 GiB RAM, Ubuntu 24.04),
no simulator or ROS process running (`ps aux` checked), load average
1.3–1.9, ROS_DOMAIN_ID 78, copy overlay `~/coco_v2_ws` built with
`scripts/build_overlay.sh` from an rsync of the worktree.

| suite | passed | failed | skipped | evidence |
|---|---|---|---|---|
| `scripts/run_all_package_tests.sh` (11 packages) | 3,081 | 0 | 0 | `packages_before.txt` |
| `lab_web` typecheck + vitest (17 files) | 308 | 0 | 0 | `vitest_before.txt` |
| `lab_web/tools` (build-tool tests) | 117 | 0 | 0 | `tools_before.junit.xml` |

Per package: coco_config 93, coco_sim 323, coco_mission 371, coco_web 863,
gazebo_models 229, coco_rl 251, coco_perception 139, coco_moveit_config
12, custom_teleop 75, coco_lab 604, coco_lab_ros 121.

Node for `lab_web`: 24.21.0 (`.nvmrc`), from the official tarball, sha256
checked against `SHASUMS256.txt`, installed under `~/coco_v2_ws/node`
(the machine's own Node is 20.20.2). Production build `tree_sha256`
`81254cdeeca3e3f91b4ed06f33b613352d7d03046f1ce18e956ef0be269abb52`,
`check_dist` failures: none.
