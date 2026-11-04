# R2 · Bring Your Own Algorithm — status

Prompt: [`R2_PROMPT.md`](R2_PROMPT.md). Plan-change entry: [`../../STATUS.md`](../../STATUS.md) (2026-11-04).

## Now

- **State (2026-11-05): R2.8 Phone and Learn done** ([`data/r28/README.md`](data/r28/README.md)), committed before R2.7
  (whose Gazebo runs take hours): the Studio on the **emulated** phone in both orientations (real phone: not
  connected — plug it in when convenient); "Try it yourself" on Learn; [`API.md`](API.md). Gautham's leaderboard
  submission: [PR #31](https://github.com/GauthamCodes/coco-labs/pull/31) — **CI's sandboxed verify passed** (VERIFIED;
  public results byte-identical to the laptop's native and container runs); the `verified` label comes from the
  trusted writer once R2 is on main. R2.7's Gazebo + Nav2 validation is running.
- **State (2026-11-05): R2.6 Leaderboard built** ([`data/r26/README.md`](data/r26/README.md)): submission format,
  the sandboxed `pull_request` verifier (base branch's verifier, `--network none`, no secrets), the trusted
  `workflow_run` writer (validates the artifact as data, comments, labels), re-verification on every version change,
  held-out scenarios (with their stated no-secret limitation), the Leaderboard tab, built-in reference entries for the
  three planner boards. Gautham's submission (Lazy Theta*, depot-nav-100) verifies locally: 100/100 public, 20/20
  held-out, path 0.978 × grid-optimal. Its pull request: below.
- **State (2026-11-05): R2.3 Algorithm Studio and R2.5 Share links done** ([`data/r23/README.md`](data/r23/README.md),
  [`data/r25/README.md`](data/r25/README.md)): the Studio end to end in Chromium — the A* starter found and drawn
  (3,059 expansions), deterministic; Compare beside the built-in A*; pure pursuit drawn tick by tick; ROS 2 export; a
  code link shows the code and runs nothing until "Run this code"; the emulated phone in both orientations. A real bug
  found by the check and fixed (the editor could show other code than Run would run when a link loaded first).
  Screenshots in [`screens/r23/`](screens/r23/).
- **State (2026-11-05): R2.4 Compare, experiments and native done** ([`data/r24/README.md`](data/r24/README.md)):
  `coco experiment run --algorithm` (worker processes, `PYTHONHASHSEED=0`, the file exported beside the results,
  `verify` re-runs it); the Studio's Compare (yours beside any built-in, same scenario) and "Benchmark it" (a whole
  suite against built-ins in a pool of sandboxes, R1's statistics). **Parity: every starter template in CPython and
  Pyodide, 850 values, 0 differences**; added to CI (`lab.yml`).
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
  tree: **1298 passed, 0 failed**.
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
| R2.3 Algorithm Studio | done | [`data/r23/README.md`](data/r23/README.md), [`screens/r23/`](screens/r23/) |
| R2.4 Compare, experiments and native | done | [`data/r24/README.md`](data/r24/README.md), [`parity.json`](data/r24/parity.json) |
| R2.5 Share links | done | [`data/r25/README.md`](data/r25/README.md) |
| R2.6 Leaderboard | done; PR #31 verified in CI (label after R2 merges) | [`data/r26/README.md`](data/r26/README.md), [`leaderboard/`](../../../leaderboard/) |
| R2.7 Run in ROS 2 | | |
| R2.8 Phone and Learn | done (emulated phone) | [`data/r28/README.md`](data/r28/README.md), [`API.md`](API.md) |
| R2.9 Close | | |

## Questions for Gautham

1. **D\* Lite through the API** (R2.1): its path length and cost differ from the native values by ≤ 3e-15 relative
   because its native adapter sums with Python's compensated `sum()` while the search planners and the API add in order.
   Accept as recorded; or make the API's measurement compensated (the five search planners then differ by an ulp); or
   switch D\* Lite's adapter to sequential addition under a new experiment version? Nothing native changed meanwhile.
