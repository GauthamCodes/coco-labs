# COCO Lab — session prompts

Paste **exactly one** fenced block per Claude Code session. `CLAUDE.md` is
read automatically, so don't paste it. The plan behind these blocks is
[`docs/ROADMAP.md`](ROADMAP.md).

**Order:** 0 → 1A → 1B → 1C → 1D → 1E → 1F, then optionally 1G. Each block
checks its precondition in `docs/SESSION_LOG.md` and stops if it isn't met.

## Before Phase 0

1. Save `ROADMAP.md` and `LAB_PHASES.md` in the **repo root**, untracked.
   Don't overwrite `docs/ROADMAP.md` yourself. Phase 0 archives the old one
   first, then moves these two into `docs/`.
2. Check that `gh auth status` works on this machine. Phase 0 pushes tags and
   may publish a release.
3. Start a fresh Claude Code session in the repo and paste the Phase 0 block.

## Standing approvals

| Action | Phase 0 | Phase 1 |
|---|---|---|
| Commit and push to the working branch | Pre-approved | Pre-approved (branch `lab1`) |
| Push to `main` | Ask first | Pre-approved **only** as a fast-forward from `lab1` with every test green |
| Force-push anything | Never | Never |
| Delete a remote branch | Ask first | Ask first |
| Rename or archive a repository | Ask first | Ask first |
| Publish a release or release asset | Ask first | Ask first |
| `git clean`, `git reset --hard`, force-removing a worktree | Never | Never |
| Edit user-owned files (`CLAUDE.md`, `AGENTS.md`, `.codex/`, `docs/agents/`, `docs/RSE_ASSIGNMENT_PLAN_V2.md`, the master context) | Additive only, diff shown first | Additive only, diff shown first |

## Resume after a cleared session

```
Resume after a cleared session. Read CLAUDE.md, docs/ROADMAP.md,
docs/LAB_PHASES.md and docs/SESSION_LOG.md. Reconstruct where we are:
the last completed block, what is measured, what is unverified, what is
waiting on me, and which block comes next. Report and wait. Do not start
work until I confirm. If your reconstruction disagrees with the latest
SESSION_LOG.md entry, say so first.
```

---

## Phase 0 — make the repo tell the truth (≈1 week)

```
Phase 0 — make the repo tell the truth. Cold start.

Read, in this order: CLAUDE.md; the COCO 2.0 master context (find it —
probably under docs/agents/ or the repo root — and tell me the path);
ROADMAP.md and LAB_PHASES.md (untracked, in the repo root);
PROJECT_STATE.md; HOW_TO_RUN.md; docs/SESSION_LOG.md.

The standing-approvals table in LAB_PHASES.md governs this session. In
short: ask before anything public or irreversible; never git clean,
reset --hard, force-push, or force-remove a worktree; user-owned files get
additive edits only, with the diff shown first.

STEP 0 — reconstruct and report before changing anything:
- git worktree list, local branches, and what is checked out
- local main vs origin/main vs p03c-consolidation: ahead/behind counts and
  merge-bases
- whether the 24x18 arena, EpisodeSpec and platform_server exist on each
- every remote branch: tip, merged into main or not, used by an active
  worktree or not
- per-package test counts on p03c-consolidation, on a clean ROS graph as
  HOW_TO_RUN.md describes
If this disagrees with the master context — main is not b15d445,
p03c-consolidation is missing, the tests are not 1,966 passing — STOP and
tell me.

PART A — land the consolidation on main
A1. Propose how main comes to contain p03c-consolidation. Fast-forward if
    possible. If main and origin/main have diverged, report and stop.
A2. After my approval: merge, re-run every package's tests, and push main
    with no force. Report per-package counts, marked (measured).

PART B — install the roadmap
B1. git mv docs/ROADMAP.md docs/history/ROADMAP_COCO2.md, with the content
    unchanged. Then move ROADMAP.md to docs/ROADMAP.md and LAB_PHASES.md to
    docs/LAB_PHASES.md, and add both.
B2. In the master context, add a dated banner at the top of §45 (the
    priority order): "Superseded on 2026-09-28 by docs/ROADMAP.md. The
    order below is kept as history; everything else in this document
    still holds." Change nothing else. Show me the diff.
B3. Append the section between the markers below to CLAUDE.md, and to
    AGENTS.md if it mirrors CLAUDE.md. Show me the diff.

----- BEGIN CLAUDE.md ADDENDUM -----
## COCO Lab direction (added 2026-09-28)

COCO is becoming COCO Lab (working title): an interactive, browser-based
robotics curriculum running on this ROS 2 stack. Plan: docs/ROADMAP.md.
Session prompts: docs/LAB_PHASES.md. The master context's §45 priority
order is superseded; everything else in it still holds.

Platform rules, in addition to everything above:
1. coco_lab never imports rclpy. A test enforces it.
2. The browser never names a topic, and never commands the robot except
   through coco.v1 intents added additively.
3. No new wheel publisher. Lab planners move the robot only via Nav2
   FollowPath, through the existing command chain into cmd_vel_arbiter.
4. Every mode is labelled on screen: Replay (recorded real run,
   provenance shown), Sketch (browser model, measured fidelity shown),
   Live (local stack).
5. Every claim shown to a learner is backed by a property test or a
   (measured) result, and cites it. Theorems are tested as properties,
   not asserted.
6. Comparisons hold inputs fixed: map, start, goal, recording, seed.
7. Trace and bundle schemas are versioned; breaking changes bump the
   major version.
8. The TypeScript UI never re-implements an algorithm. It renders traces
   and asks coco_lab.
9. No new lab starts until the previous one has a public URL, a video and
   a write-up. A lab's first version ships at most five algorithms.
----- END CLAUDE.md ADDENDUM -----

PART C — the collision-monitor loop (PROJECT_STATE known limitation 0)
C1. Measure on the consolidated main first: publishers and subscribers on
    /cmd_vel_nav; during an injected SLOWDOWN, the collision monitor's
    output rate against the wheel-command rate, and wheel speed against
    the gated cap. Reuse the harness behind the original measurement if it
    exists. P03C's single-publisher invariant checks the controller topic,
    not this loop, so don't treat it as evidence either way.
C2. If the defect is confirmed, apply the fix PROJECT_STATE describes: give
    cmd_vel_relay its own output topic and point the arbiter's nav input at
    it. This is pre-approved as a measured defect. If it needs any change
    to cmd_vel_arbiter.py's code, rather than its parameters or remaps,
    STOP and show me why first.
C3. Re-measure:
    - publishers on the arbiter's nav input (target: exactly one, the relay)
    - wheel speed during an injected SLOWDOWN against the cap, reported as
      a distribution, not just the maximum
    - the four FIXED cases of the P03C matrix, a fresh simulator each,
      beside their pre-fix results
    Write a comparability statement: post-fix results are a new series,
    and the v1 19/20 and the P03C 13/13 were measured with the loop in
    place.
C4. Update known limitation 0 in PROJECT_STATE.md with the outcome, keeping
    the original text below it as history.

PART D — make the public face honest
D1. PROJECT_STATE.md: replace "FROZEN / RELEASE READY" with ACTIVE —
    building COCO Lab, linking docs/ROADMAP.md. Keep every measured result
    and every known limitation.
D2. README.md: add the banner between the markers below at the very top,
    and correct the planner claim. The README credits A* with a path 6.2%
    shorter than "the Dijkstra it replaced", but the measured comparison
    was SmacPlanner2D vs NavFn. With admissible heuristics and identical
    costs, A* and Dijkstra return equal-cost paths, so the gap comes from
    the planners' implementations; DESIGN_DECISIONS.md already records
    NavFn's calcPath mechanism. Reword it to say exactly that, keep the
    numbers, and note that Lab 1 will show it. Make the same correction
    wherever the claim appears in docs/RESULTS.md. In docs/history/, add a
    note rather than editing the archived table.

----- BEGIN README BANNER -----
> **Status — September 2026.** COCO is becoming **COCO Lab**: an
> interactive, browser-based robotics curriculum that runs on this real
> ROS 2 / Nav2 stack. Everything below remains accurate and measured.
> Plan: [docs/ROADMAP.md](docs/ROADMAP.md).
----- END README BANNER -----

D3. Branch hygiene: for every remote branch except main, create an
    annotated tag archive/<branch> at its exact tip, and push the tags.
    Give me a table: branch, tip, tag, merged into main, active worktree,
    proposed action. STOP before deleting any remote branch. Never touch
    local worktrees.
D4. The fetch video lives in a release on coco-robot-ros2. Prepare (a) the
    same video as a release asset on this repo, and (b) a pointer README
    for coco-robot-ros2 followed by its archival. STOP for my approval
    before publishing or archiving anything.
D5. Naming: "COCO" alone loses to the MS COCO dataset in search. Propose
    five names for the platform, check each is free as a repository name
    under GauthamCodes, and STOP. I'll choose. The rename happens only
    after I approve, and GitHub redirects the old URL.

Checkpoint docs/SESSION_LOG.md before the final commit. Deliverables:
consolidation on main with per-package test counts; the roadmap installed
and the old one archived; the CLAUDE.md addendum; the collision-monitor
loop measured, fixed and re-measured with a comparability statement; an
honest PROJECT_STATE.md and README.md; branches tagged; and a plain list of
every decision still waiting on me.
```

---

## Phase 1 — Lab 1: Plan (≈3 weeks, six sessions)

### 1A — the core and its proofs

```
Phase 1A — the coco_lab core and its proofs.
Precondition: docs/SESSION_LOG.md shows Phase 0 complete (consolidation on
main, roadmap installed). If not, stop and tell me.
Work on branch lab1. Read docs/ROADMAP.md §3, §5 (Lab 1) and §8 first.

1. Create package coco_lab. Pure Python, NO rclpy, standard-library-only
   runtime. It must build with colcon AND install with pip in a plain venv
   with no ROS on the path. Add a test asserting it imports with rclpy
   absent from sys.modules (the mujoco_env pattern).

2. Algorithms operate on a generic graph interface: neighbours(state),
   edge cost, heuristic. The grid is one implementation. Design it so a
   (cell, heading) state space plugs in without touching the algorithms;
   1B needs that, and so will Hybrid A* later.

3. Grid model: occupancy plus an optional cost layer; 4- and
   8-connectivity; move costs 1 and sqrt(2); a declared, documented cost
   function for cost-aware traversal (1C compares it with SmacPlanner2D's).

4. Algorithms, five and only five: BFS, Dijkstra, A*, greedy best-first,
   weighted A* (f = g + w*h, w >= 0). Heuristics: zero, Manhattan,
   Euclidean, octile. Tie-breaking: one explicit, documented policy, plus
   one alternative behind a toggle. Everything deterministic.

5. A function that reports whether a heuristic is admissible and
   consistent for a given move model and cost function. The UI badge comes
   from this, so test it, including the case where octile overestimates
   because diagonal moves cost 1.

6. Trace schema v1: events push, expand, relax, path, each carrying cell,
   g, h and parent; columnar; versioned. Plus a summary: expansions, path
   cost, path length, status (found / no path). Document it in
   docs/labs/TRACE_SCHEMA.md.

7. Property tests with hypothesis, at least 1,000 seeded random maps per
   property, varying size, density, connectivity and move model:
   - A* cost == Dijkstra cost, with an admissible heuristic
   - A*'s expanded set is a subset of Dijkstra's up to ties, with a
     consistent heuristic; define "up to ties" precisely in the test
   - weighted A* cost <= w x optimal, for w >= 1 and an admissible
     heuristic
   - w = 0 reproduces Dijkstra's cost
   - BFS is optimal under unit edge costs
   - greedy best-first cost >= optimal always, and strictly worse on a
     committed counterexample map, so "greedy can be suboptimal" is tested
     rather than asserted
   - all five agree on no-path cases
   Oracle: networkx shortest-path cost on the identical graph. Agreement
   must be exact, within float tolerance, for every optimal algorithm.

8. hypothesis and networkx are test-only dependencies: pin them and
   declare them properly. Verify the rosdep keys exist rather than
   assuming they do.

Report the property list, maps per property, suite runtime, and every
failure with its cause. Write the counts to docs/RESULTS.md marked
(measured). No web code and no ROS code this session. Checkpoint
SESSION_LOG.md, commit, and stop.
```

### 1B — bundles, maps and the ISRO reconstruction

```
Phase 1B — bundles, maps, and the ISRO reconstruction.
Precondition: SESSION_LOG.md shows 1A complete. Branch lab1.

1. Bundle format v1 inside coco_lab: manifest.json plus little-endian
   typed arrays, optionally gzipped. The manifest carries the schema
   version and provenance: source kind (glass-box | recorded-run |
   sketch), coco_lab version, git commit and dirty flag, seed, EpisodeSpec
   hash where applicable, creation time in UTC, and for recorded runs the
   rosbag2 file hash and sim-time range. Round-trip tests. Commit a small
   golden-fixture set, because 1D's TypeScript decoder is tested against
   it. Document it in docs/labs/BUNDLE_FORMAT.md.

2. Map exporters:
   (a) the arena's saved Nav2 map (pgm + yaml)
   (b) a ground-truth occupancy map rasterised from the parameters that
       generate the arena, at the same resolution and origin; if the arena
       is not parameter-generated, rasterise it from its SDF and say so
   (c) a few 20x20 teaching grids
   Report cell-level precision and recall of occupied cells for (a)
   against (b). It is the first honest map-quality number, and Lab 3
   reuses it.

3. Resolution: measure bundle size and coco_lab compute time for a
   full-arena Dijkstra trace at the native map resolution and at 0.10 m.
   Recommend an edit-mode resolution with the numbers. If they are close,
   report rather than choose.

4. The ISRO reconstruction for the A* exhibit. My ISRO pathfinding
   simulator (Python/Pygame, 30x30 grid, 8-directional movement,
   Euclidean and octile heuristics, turn penalty 0.1) reported A* 5x
   faster than Dijkstra but with 4% longer paths. With an admissible
   heuristic on a correctly modelled graph, that gap should be zero. Test
   two hypotheses:
   (a) the search state is the cell alone, while the turn penalty makes
       cost depend on the incoming heading
   (b) an octile heuristic overestimates for the move costs actually used
       (for example, diagonals costing 1)
   Implement both faulty variants and the correct (cell, heading) state
   space. Measure A*-vs-Dijkstra cost gaps over seeded maps, and report
   which, if either, reproduces a gap of that size and direction.
   Ask me for the ISRO source first. If I provide it, diagnose the actual
   cause from the code. If not, label the result a reconstruction, never a
   diagnosis.

Write every number to RESULTS.md marked (measured). Checkpoint, commit,
stop.
```

### 1C — the real-stack hook, conformance and three real runs

```
Phase 1C — the real-stack hook, conformance, and three real runs.
Precondition: SESSION_LOG.md shows 1B complete. Branch lab1.
The simulator rules in CLAUDE.md apply: a fresh simulator per run,
headless, never --fast, kill by process name.

1. New package coco_lab_ros (depends on coco_lab, rclpy, nav2_msgs). A
   planner node that:
   - snapshots /global_costmap/costmap per request and stores it with the
     trace
   - plans from the robot's AMCL belief (map -> base_footprint)
   - runs the requested coco_lab algorithm
   - publishes or writes the trace
   - sends the path to controller_server's FollowPath action
   It never publishes velocity. Verify at runtime and in a test: exactly
   one publisher on the controller topic (the arbiter), and no publisher
   added to the arbiter's inputs.

2. A launch file and a lab-only Nav2 parameter overlay; the mission's
   nav2_params stays untouched. Use the lightest bringup that gives
   Gazebo + Nav2 + the arbiter with the mission executive not driving,
   set the arbiter mode through the existing path, and state what you
   used.

3. Conformance vs SmacPlanner2D. First read its source for the
   traversal-cost model, and state how coco_lab's declared cost function
   differs. Then, over at least 50 seeded start/goal pairs in the arena,
   get Smac's path via ComputePathToPose on the same costmap snapshot, and
   compare length and cost under the declared cost function. Report the
   gap distribution with Smac's smoothing as configured, and again with
   smoothing disabled if the overlay allows it cleanly. Do not tune
   coco_lab to match.

4. The NavFn half of the exhibit. On the same pairs (or a stated subset),
   get NavFn paths with use_astar false and true via the overlay, and
   compare them with Smac and with coco_lab's optimal. Reproduce or refute
   the M3 figure (3.165 m vs 3.373 m, 6.2%). If the M3 goal doesn't exist
   in this world, say so and use the fresh pairs.

5. Three real runs, same start and goal, driven by coco_lab A*, Dijkstra
   and greedy best-first through FollowPath. Record with rosbag2:
   ground-truth pose, AMCL pose, TF, the planned path, the trace, wheel
   commands and the costmap snapshot. Export each to a bundle. Report
   tracking error (ground truth vs path), duration, recoveries and the
   arbiter trace.

Everything goes into RESULTS.md marked (measured). Checkpoint, commit,
stop.
```

### 1D — the web app skeleton, measured

```
Phase 1D — the web app skeleton, measured.
Precondition: SESSION_LOG.md shows 1C complete. Branch lab1.

1. New directory lab_web/. It is not a ROS package, so add COLCON_IGNORE.
   Use Vite + TypeScript, React for the shell, and HTML Canvas 2D for maps
   and traces. No analytics, no cookies, and no third-party calls except
   the pinned Pyodide CDN.

2. A TypeScript bundle decoder, tested against 1B's golden fixtures. This
   is the cross-language pattern coco_web already uses in
   frame_decode.test.js. Both sides must agree exactly on every fixture.

3. Trace player: play, pause, step, scrub and speed controls; keyboard
   (space, arrow keys); open, closed and path overlays in a
   colourblind-safe palette (Okabe–Ito or equivalent); hover shows g, h
   and f. Respect prefers-reduced-motion.

4. Pyodide in a Web Worker, lazy-loaded only when a user edits a map. It
   installs coco_lab from a pure-Python wheel that CI builds and the site
   serves. Pin the Pyodide version; look up the current release rather
   than guessing.

5. Measure on this laptop and report, marked (measured). These are
   targets, not promises:
   - playback of a full-arena Dijkstra trace: >= 60 fps
   - edit -> first frame with Pyodide warm: <= 1.5 s
   - Pyodide cold load time
   - initial page weight excluding Pyodide
   If a target is missed, bring me options with numbers and stop. Don't
   pick one silently.

6. CI (GitHub Actions): coco_lab tests in a plain venv with no ROS, the
   TypeScript tests, the site build, and a Pages deploy from main. I'll
   enable Pages (source: GitHub Actions); tell me when you need it. Set
   Vite's base path for the repository name, and if Phase 0's rename
   hasn't happened yet, ask me.

7. Replay must work at phone width; editing can be desktop-first. Say how
   you checked.

Checkpoint, commit, stop.
```

### 1E — Lab 1's content

```
Phase 1E — Lab 1's content.
Precondition: SESSION_LOG.md shows 1D complete and the site deploying.
Branch lab1.

Must-haves, in this order:

1. Settings panel: the five algorithms; the heuristic picker with the
   admissibility and consistency badge taken from coco_lab, not
   recomputed in TypeScript; 4/8-connectivity; a tie-breaking toggle; a
   weighted-A* slider from 0 to 5 with the suboptimality bound shown live.

2. Map ladder: teaching grid -> arena occupancy -> inflated costmap with
   the robot's footprint swept along the path. Footprint dimensions come
   from coco_config, not from constants in the UI.

3. Race mode: two to four algorithms on identical inputs, a synchronised
   step counter, and a final table of expansions, cost, length and gap to
   optimal.

4. Predict-then-reveal: before a run, ask one question ("which expands
   fewer cells?"); the reveal shows the measured answer.

5. Paint obstacles and recompute through the Pyodide worker. A blocked
   start or goal is rejected with a clear message.

6. Share links: the URL encodes seed, edits and settings compactly, and
   opening it reproduces the exact trace. Test the round trip.

7. One break-the-planner challenge, verified automatically: "paint a map
   where greedy best-first's path costs at least twice the optimum."

8. "Driven by COCO": the three real runs from 1C replayed with ground
   truth, AMCL belief and the planned path overlaid, a tracking-error
   plot, and provenance (commit, seed, bundle hash). Label it Replay —
   recorded real run.

9. The exhibit, "The A* myth, twice":
   (a) same costs, same answer: A* vs Dijkstra, live
   (b) COCO's 6.2%: Smac vs NavFn vs coco_lab's optimal, from 1C, with the
       calcPath mechanism
   (c) the ISRO 4%: from 1B, labelled a diagnosis or a reconstruction as
       appropriate
   Every claim on the page cites its evidence: a test name or a RESULTS.md
   anchor.

Nice-to-haves, only once every must-have works and is measured:
beat-the-planner (draw your own path), one to three stars, a daily seed.
Otherwise log them in docs/ROADMAP.md as Lab 1.1.

Do not add a sixth algorithm. Checkpoint, commit, stop.
```

### 1F — ship Lab 1

```
Phase 1F — ship Lab 1.
Precondition: SESSION_LOG.md shows 1E complete. Branch lab1.

1. Write docs/labs/LAB1_PLAN.md: what the lab teaches, how each claim is
   backed, every (measured) number with its reproduction command, what
   remains unverified, and known limitations.

2. README.md: a "Try it" link to the public URL at the very top, a short
   Lab 1 section, and the corrected planner claim linked to the exhibit.
   Don't rewrite the rest.

3. Demo video, 60–90 s, of the web app rather than Gazebo: race mode, a
   painted map, the exhibit, and a real-run replay. Record only the
   browser window region, take a probe frame first, and delete probes
   afterwards, following the same rules as the M6 video. Keep it out of
   git; release asset only.

4. Tag lab1-v1.0 and draft a release with the video and notes listing the
   measured results and known limitations. STOP for my approval before
   publishing.

5. Final checks, reported: the public URL loads on a phone; a share link
   round-trips; CI is green on main; per-package test counts.

6. Update the status line in docs/ROADMAP.md, and checkpoint
   SESSION_LOG.md.

Phase 1 is then done. Don't start Phase 2. Its prompt gets written from
docs/ROADMAP.md §5–6 when I'm ready.
```

### 1G — optional learning check

```
Phase 1G (optional) — a learning check.
Precondition: 1F released.

Build a short before-and-after quiz page into the site: six
multiple-choice questions on Lab 1's concepts, covering
- admissibility
- why A* and Dijkstra return equal costs
- what weighting trades away
- when greedy fails
- expansions vs path quality
- why the robot's path differs from the grid path

No names, no accounts, no personal data. Answers stay in the browser, and
each participant exports a small anonymous file that they choose to send
me. Write a one-page protocol covering the consent line, timing, and how
results are aggregated. I'll run it with about ten classmates. Afterwards,
report the scores in RESULTS.md with small-sample caveats, marked
(measured). Checkpoint and stop.
```
