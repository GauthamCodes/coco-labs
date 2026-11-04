# R2 · Bring Your Own Algorithm — status

Prompt: [`R2_PROMPT.md`](R2_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-11-04).

## Now

- **State (2026-11-05): R2.2 Sandboxed worker done** ([`data/r22/README.md`](data/r22/README.md)): user code runs only
  in its own Pyodide worker, started from a `blob:` URL so it inherits the page's CSP (no eval/Function/dynamic
  import), locked down before any user code (network, storage, other contexts, devices; Python's `js` bridge),
  a 1 GiB memory ceiling on WebAssembly growth, a per-call time limit from the page (5 s control/localisation, 30 s
  planning; the worker is terminated and rebooted). **Escape tests pass in Chromium, Firefox and WebKit**: 19 hostile
  files (network, DOM, `import js`, infinite loop, memory blow-ups, huge outputs) all failed safely; the lockdown's 68
  probes all blocked. The Studio UI they run through is committed with it (R2.3 next).
- **State (2026-11-05): R2.1 API and security design done** ([`data/r21/README.md`](data/r21/README.md)):
  `coco_lab.api` (`coco.algorithm.v1`, ADR 0013), the guard (`coco_lab.user_code`), user runs in every family but
  full task, the built-ins wrapped behind the same signatures; ADR 0012 (threat model). Built-ins unchanged: 10%
  reference sample **197/197 match**; through the API every built-in reproduces its native results bit for bit
  except **D\* Lite's path length and cost (≤ 3e-15 relative: its native adapter sums with Python 3.12's compensated
  `sum()`)** — no native result, hash or golden changes; question for Gautham below. Full coco_lab suite on the R2
  tree: recorded with R2.2.
- **State (2026-11-04): R2.0 Baseline done** ([`data/r20/README.md`](data/r20/README.md)): main `4894c76`'s tree is R1's
  final tree byte for byte (`git diff 8b40a41 4894c76` empty), so R1.9's committed suites are its baseline; a re-run
  here gave coco_lab 1191 passed + 1 failure caused by an R2 file appearing in the tree mid-run (fixed in R2.1), and was
  stopped before steps that would have measured R2 work. Before screenshots = R1.9's after set (same tree), checksummed.

## Setup facts

- Base: `origin/main` `4894c76` (Merge PR #30, R1 · Research Workbench — merged 2026-11-04 16:21Z, so R2 branches from
  main, not from `v2/r1-workbench`). Branch `v2/r2-byoa`. Worktree `~/coco_labs_ws/worktrees/r2` (created with
  `git worktree add`; the session's own worktree tool accepts only `.claude/worktrees/` paths, so work happens there
  by absolute path).
- Test venv `~/coco_labs_ws/r1_venv` (Python 3.12.3, CI pins from `coco_lab/requirements-test.txt`), reused: it holds
  only pinned third-party packages; `coco_lab` is reinstalled into it from this tree by the suite runner.
  ROS overlay `~/coco_lab_r2_ws` (`scripts/build_overlay.sh`). Node 24.21.0 (`~/coco_v2_ws/node/...`).
- Laptop at start: power profile **power-saver, on battery (AC 0)**; ~9.1 GB disk free. No simulator running.
  Timing measurements only on balanced + AC (original profile restored afterwards).

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| R2.0 Baseline | done | [`data/r20/README.md`](data/r20/README.md) |
| R2.1 API and security design | done | [`data/r21/README.md`](data/r21/README.md), ADR [0012](../adr/0012-running-strangers-code.md), [0013](../adr/0013-algorithm-api-v1.md) |
| R2.2 Sandboxed worker | done | [`data/r22/README.md`](data/r22/README.md) |
| R2.3 Algorithm Studio | | |
| R2.4 Compare, experiments and native | | |
| R2.5 Share links | | |
| R2.6 Leaderboard | | |
| R2.7 Run in ROS 2 | | |
| R2.8 Phone and Learn | | |
| R2.9 Close | | |

## Questions for Gautham

1. **D\* Lite through the API** (R2.1): its path length and cost differ from the native values by ≤ 3e-15 relative
   because its native adapter sums with Python's compensated `sum()` while the search planners and the API add in order.
   Accept as recorded; or make the API's measurement compensated (the five search planners then differ by an ulp); or
   switch D\* Lite's adapter to sequential addition under a new experiment version? Nothing native changed meanwhile.
