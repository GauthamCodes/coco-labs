# LinkedIn post (draft — publishing is Gautham's call)

Every number below is in the repository; the source is in brackets for checking before posting.

## Long version

I've been building COCO Lab: a robotics lab that runs entirely in the browser — and is honest
about what it is.

COCO is a ROS 2 robot I designed. In COCO Lab you can drive it, watch its planners and
controllers think, and run experiments. Under the game is a deterministic Python model of the
robot running in your browser (Pyodide). Every simulation tick is hashed, and the same run gives
the same hash chain in Chromium, Firefox, WebKit and natively — checked in CI on every change
[docs/v2/r2/data/r29/determinism_v2.json].

What's new:
🔹 COCO-Bench v1 — 12 frozen benchmark suites (450 scenarios) for planning, control,
localisation and a fetch task, with difficulty tiers and datasheets
[coco_lab/coco_lab/benchmarks/*.v1.json]
🔹 Bring your own algorithm — write a planner in Python against ROS 2-shaped messages, watch it
run in the browser, submit it to a leaderboard verified in a sandbox on held-out scenarios
🔹 The same file exports to a real ROS 2 node and runs with Nav2 in Gazebo

The result I'm proudest of is a failure: a Lazy Theta* planner whose paths in the browser model
are shorter than the grid-optimal length (median ratio 0.978, 100/100 found)
[docs/v2/r2/R2_RESULTS.md, leaderboard/results/depot-nav-100/theta_star/result.json] reached
0 of 5 goals under Nav2's controller in Gazebo [docs/v2/r2/data/r27/summary.json]. Benchmarks should show that, not hide it.

No physical robot — every result is labelled MODEL (browser) or STACK (ROS 2 in Gazebo).

Try it (no install): https://gauthamcodes.github.io/coco-labs/
Code: https://github.com/GauthamCodes/coco-labs

#ROS2 #Robotics #Navigation #Reproducibility #OpenSource

## Short version

COCO Lab: a ROS 2 robot you can drive, benchmark and program in your browser. Deterministic
(hash-verified across browsers), 12 benchmark suites, a sandboxed leaderboard, and your planner
exports to a real ROS 2 node for Gazebo + Nav2. Honest results included — a planner that wins in
the model and fails every drive in ROS 2. https://gauthamcodes.github.io/coco-labs/
