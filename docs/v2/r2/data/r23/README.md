# R2.3 · Algorithm Studio — MODEL / TESTED (real Chromium, laptop; emulated phone)

Workbench → **Algorithm Studio** (`?view=workbench&tab=studio`; `lab_web/src/studio/`). Loaded only when its tab opens
(CodeMirror 6 is a separate lazy chunk, never title-critical).

| Feature | Where |
| --- | --- |
| CodeMirror 6 editor: Python syntax, line numbers, error markers (guard problems and tracebacks), completion for `coco_lab.api`'s types, `ctx` and message fields | `editor.ts` |
| Starters: planner A* (commented), greedy best-first, empty; controller pure pursuit, empty; localiser particle filter, empty; teaching "Write the heuristic", "Tune DWA" | `coco_lab/coco_lab/templates/` (the files parity CI runs), `templates.ts` |
| Run on one scenario of a COCO-Bench suite (Previous/Next), drawn as it streams: GAME (Night Shift) or SIM (RViz-style grid, TF axes, LaserScan); the algorithm's own `ctx.emit` thinking — expansions and pushes, candidate trajectories and the lookahead, the particle cloud; truth and belief; every view says MODEL · kinematic | `StudioView.tsx`, `sandbox_glue.py` |
| Compare: yours beside any built-in on the same scenario | "Compare with" |
| Benchmark it: a whole suite against chosen built-ins, R1's statistics | `sandbox_pool.ts`, R1's `Results` |
| Results (status, every MODEL metric, compute time labelled wall time on the named device), Console (stdout, traceback with line links), Validation (contract problems, clamps, the determinism check — each run twice, chains compared — per-call time, dropped events) | `StudioTab.tsx` |
| Saving: a local draft (the prefs module, `coco.prefs.v1.studio`; works without storage), download/upload `.py`, share link (R2.5), Export as ROS 2 package (R2.7), "What the sandbox blocks" (the lockdown's probes) | |

## End to end — [`../../screens/r23/studio_check.json`](../../screens/r23/studio_check.json) (`lab_web/tools/r2/studio_check.mjs`)

PASS, 2026-11-05: the A* starter on depot-nav-100 s001 — `found`, deterministic (identical hash chains), 3,059 expansions
drawn; validation report complete; Compare with the built-in A* — both `found`, drawn side by side; the pure-pursuit
starter — `succeeded`, drawn tick by tick with its candidate arc; Export as ROS 2 package — a zip with the file
unchanged; a share link in a fresh context — code shown, Run disabled, the sandbox not even started until "Run this
code"; Learn's two "Try it yourself" links; emulated Nothing Phone (1) landscape and portrait — the phone note shown,
Run reachable, no sideways scroll, the A* starter runs in landscape.

**A bug the check caught and fixed before commit:** when a code link was decoded before CodeMirror finished loading,
the editor was created with the default template while Run would have run the link's code. The editor is now created
from the current code (a ref set by every path that loads code). The check now asserts the shown code.

Screenshots (soft gate, for Gautham): [`../../screens/r23/`](../../screens/r23/) — desktop Studio (start, planner GAME and
SIM, Compare, controller, link consent, the heuristic starter), Leaderboard, Learn; emulated phone landscape and portrait
(Studio, a run, Leaderboard, Learn). Phone note: in landscape the drawing sits below the editor's fold (one scroll).
