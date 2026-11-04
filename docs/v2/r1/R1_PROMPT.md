# R1 · Research Workbench — the prompt (Gautham, 2026-10-31)

Saved verbatim as §0 asks. Planning answers given on 2026-10-31 are in [R1_STATUS.md](R1_STATUS.md).

---

You are building R1 · Research Workbench for COCO Lab (repo GauthamCodes/coco-labs, live at https://gauthamcodes.github.io/coco-labs/).

Why: G1 and G2 made Play a polished game with a ROS 2 identity, but the research side is read-only.

Research is a library of 165 recordings you can watch but not experiment with.
Compare runs one start, one goal and one seed on the old arena, which is an anecdote, not evidence.

Gautham wants COCO Lab to serve learning and research, not just entertainment. R1 turns Research into a working lab, and the game stays the front door.

The idea to build on: the model gives exactly the same result on every run and every browser (hash-verified), and real Gazebo + Nav2 recordings validate it. So any experiment can be shared as a link and reproduced exactly by anyone, with no install. R1 makes that the headline feature.

0. Setup and rules
Branch and paperwork.
git fetch origin; create a worktree ~/coco_labs_ws/worktrees/r1 on a new branch v2/r1-workbench from origin/main.
Save this prompt as docs/v2/r1/R1_PROMPT.md and keep progress in docs/v2/r1/R1_STATUS.md.
Add a dated (2026-10-31) plan-change entry to docs/STATUS.md, and add the R track to README §7: R1 Workbench, R2 Bring your own algorithm, R3 COCO-Bench and the paper, R4 Learn course, R5 World editor, Run it in ROS 2 and Live ROS 2 in Docker, R6 fidelity knobs, more algorithms and multi-robot.
Commit [R1.n] per checkpoint and push.
Read first: README.md, AGENTS.md, docs/STATUS.md, docs/v2/g2/G2_RESULTS.md, docs/v2/m6/GAMES.md, and the Compare and Research sources (lab_web/src/compare/, lab_web/src/arena/Compare*.tsx, lab_web/src/research/). Also read docs/M7_DESIGN.md and docs/M7_PHASES.md, if they describe experiments.
All the earlier rules hold:
The model and the truth:
Rendering never changes the model. Hashes are versioned.
Evidence labels (MODEL, STACK and so on) are truthful.
Never invent numbers. Timing numbers state their device and conditions; counts (expansions, path length, success) need no device.
Git and evidence:
Never merge, deploy or release.
No destructive git commands. Never delete evidence.
Machine and phone:
Balanced profile on AC.
The real phone, if connected: restore its settings afterwards, and black out the status bar in screenshots.
Statistics must be honest. Every aggregate shows N. Use medians and interquartile ranges for skewed metrics. Report success rates with Wilson 95% intervals. Use paired tests (Wilcoxon signed-rank) when two algorithms ran on the same scenarios, and say "no significant difference" plainly when that's the result. Don't present p-values without effect sizes. No cherry-picking: every run in an experiment is shown or exported, including failures and timeouts.
1. What to build
1.1 Experiments, a new top-level tab (Research becomes "Workbench")

Title-screen doors become Play · Learn · Workbench, given equal weight, and the top bar gets Workbench with tabs: Experiments · Benchmarks · Recordings (today's library, unchanged) · Datasets.

The experiment builder is a form, plus a JSON or YAML file you can edit directly:

World: the Proving Ground arena, the Depot, the Depot with colour rods, plus any World Spec v3 level in the repo.
Family:
global planning (all existing planners)
local control (the existing controllers)
localisation (the existing methods)
full task: Fetch Rush or Fetch by colour, with the reference bot driven by a chosen planner
Algorithms: one or more, each with its parameters (inflation radius, cost scaling, robot radius, heuristic weight, controller gains, and whatever each algorithm exposes).
Scenarios:
N seeded start/goal pairs, sampled in free space with a minimum separation, or restricted to chosen zones
or a named benchmark suite (§1.3)
or hand-placed pairs
Parameter sweep (optional): one or two parameters over ranges. One parameter gives a line plot with bands; two give a heatmap.
Metrics:
success / no path / timeout
path length, path cost, expansions, compute time
minimum and mean clearance, smoothness (total heading change)
for full tasks: time to complete, contacts, deliveries
for localisation: error over time and convergence time

Running:

The runs execute in a pool of Pyodide web workers (as many as the device has cores, capped), with a progress bar, pause and cancel, and an estimated time left.
Results stream into the table as they finish. Partial results are kept if the experiment is cancelled.
Phones can run small experiments; warn above a size threshold.

Results view:

A table, sortable and filterable, one row per run, with a link that replays that run in Compare.
Summary per algorithm: N, success rate with its 95% interval, median and IQR for each metric.
Plots: box plots per metric, a success-rate bar with intervals, scatter of expansions against path length, and line or heatmap plots for sweeps.
Paired comparison, when algorithms share scenarios: per-scenario differences, Wilcoxon p-value, and an effect size.
A "failures" filter, which opens the failed run in Compare at the step where it failed.
1.2 Reproducible, shareable experiments
An experiment is a small spec: world, family, algorithms, parameters, scenario generator and seed, metrics, and the model and hash versions.
"Copy link" encodes the spec in the URL; if it's too long, use a compressed fragment.
Opening the link rebuilds the same experiment. Re-running it must reproduce every count metric exactly (timings vary by device and are labelled). Add a "Verify" button that re-runs a random 10% and checks the per-run hash chains match.
Python side, for parity: coco_lab gets an experiments module plus a CLI, coco experiment run spec.json --out dir/, that runs the same spec natively and produces the same results. CI checks native-vs-browser parity on a small spec.
1.3 Benchmarks: first suites ("COCO-Bench v0", a draft for R3)

Each suite is versioned, with a fixed scenario list, a fixed metric set, and a README stating what it tests:

arena-nav-50: 50 start/goal pairs on the Proving Ground.
depot-nav-100: 100 pairs across the Depot's six zones, stratified by zone.
depot-narrow-30: pairs that must pass the workshop maze or the rack aisles.
colour-fetch-4: the four rods, full task.

Each suite page shows its description, a map of all its scenarios, and reference results for every built-in algorithm, computed and committed. Where a scenario has a Gazebo + Nav2 recording, link it.

1.4 Datasets and exports
Every experiment exports:
results.csv (one row per run)
summary.json
spec.json
manifest.json (versions, hashes, checksums, device and conditions)
optionally, each run's MCAP trace
A ready Jupyter notebook, docs/v2/r1/notebooks/analyse_experiment.ipynb, that loads an export and reproduces the summary plots with pandas and matplotlib. Add an "Open in Colab" link.
The Datasets tab lists downloadable committed datasets: the benchmark reference results, and the paired model-vs-Gazebo runs that exist.
1.5 Compare upgrades
Compare works on every world, including the Depot, not just the old arena.
Scenario picker: a random seeded pair, a pair from a benchmark suite, or a hand-placed pair. Next and previous buttons step through a suite's scenarios with the panes in sync.
"Turn this into an experiment" opens the builder pre-filled with the current panes and parameters.
1.6 Learn gets its own page

The Learn door opens a proper Learn page: the seven missions as cards, and each mission links to a pre-made experiment, for example "Is A* always faster than Dijkstra? Run it on 50 scenarios." Keep the existing tours as they are; don't build the graded course yet (that's R4).

2. Checkpoints (in this order; commit and push each)
R1.0 Baseline

Set up, build, run all suites. Take before screenshots: title, Compare, Research, Learn, at desktop and emulated phone.

R1.1 Model side
coco_lab.experiments: the spec schema, scenario generators, metrics, a runner, stats (Wilson intervals, Wilcoxon, effect size, written with the standard library or numpy only), and the CLI.
Unit tests, plus a golden experiment.
R1.2 Worker pool

Browser runner with a worker pool, progress, cancel, and streaming results. Native-vs-browser parity test on a small spec.

R1.3 Builder and results

The experiment builder and results view: table, summary, plots, paired comparison and the failure drill-down. Accessible, colour-blind safe, and usable on a phone in landscape.

R1.4 Links and verification

Shareable links and the Verify button. An end-to-end test: build an experiment → copy the link → open it in a fresh browser context → the results are identical.

R1.5 Benchmarks

The four suites with reference results, and a Gazebo link wherever a recording exists.

R1.6 Exports and notebook

The exports, the notebook (run it once in CI or locally and commit its output), and the Datasets tab.

R1.7 Compare and navigation

Compare on every world with the scenario picker and the experiment hand-off; Workbench navigation; the title with three equal doors; the Learn page.

R1.8 Performance
Laptop: a 4-algorithm × 100-scenario Depot experiment, timed on the real GPU and CPU.
Phone: a small 2 × 20 experiment on the real Nothing Phone (1) if connected, otherwise emulated.
Play must be unaffected: run Play's frame-rate check again.
R1.9 Close

After screenshots, docs/v2/r1/BEFORE_AFTER.md, all suites, v1/v2/v3 determinism, R1_RESULTS.md. Then open a PR "R1 · Research Workbench" into main, ready for review. Don't merge.

3. Stop and report if
Any model or golden hash changes.
Browser and native results disagree on a count metric.
A statistic can't be computed honestly for some metric (say why, and don't fake it).
Play's frame rate gets worse.
4. Final report
Checkpoints done (R1.x):
Branch, SHAs, pushed, clean:
Experiments: families supported, max size tested, worker count, runtime (device)
Reproducibility: link → identical counts? Verify result; native-vs-browser parity
Benchmarks: suites, scenario counts, reference results summary
Exports and notebook: files, notebook run result
Compare/Learn/navigation changes:
Performance: laptop, phone, Play fps unchanged?
Tests and determinism:
Screenshots: BEFORE_AFTER.md
Questions for Gautham:
Next step (R2 · bring your own algorithm):
