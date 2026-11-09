# LinkedIn post (draft — publishing is Gautham's call)

Every number below is in the repository; the source is in brackets for checking before posting
(remove the brackets when posting). Author: Gautham (no affiliation).

## Long version

I've been building COCO Lab: a robotics lab that runs entirely in the browser — and is honest
about what it is.

COCO is a ROS 2 robot I designed. In COCO Lab you can drive it, watch its planners and
controllers think, and run experiments. Under the game is a deterministic Python model of the
robot running in your browser (Pyodide). Every simulation tick is hashed, and the same run gives
the same hash chain in Chromium, Firefox, WebKit and natively — checked in CI on every change
[docs/v2/r2/data/r29/determinism_v2.json].

What's new (live now [docs/v2/r3/data/deploy1/README.md]):
🔹 Bring your own algorithm — write a planner, controller or localiser in Python against ROS
2-shaped messages, watch it think in the browser, and submit it to a leaderboard that re-runs it
in a sandbox on public and held-out scenarios
🔹 The first community entry is on the board: a Lazy Theta* planner, verified — 100/100 public
scenarios, held-out 20/20 [leaderboard/results/depot-nav-100/theta_star/result.json]
🔹 The same file exports to a real ROS 2 node and runs with Nav2 in Gazebo
🔹 Coming next: COCO-Bench v1 — 12 frozen suites (450 scenarios) for planning, control,
localisation and a fetch task, with difficulty tiers, datasheets, and held-out scenarios drawn
from a secret the submitted code never sees [coco_lab/coco_lab/benchmarks/*.v1.json,
docs/v2/adr/0014-held-out-secret-salt.md]

The result I'm proudest of is a failure. That Lazy Theta* planner finds paths shorter than the
grid-optimal length in the browser model (median ratio 0.978)
[leaderboard/results/depot-nav-100/theta_star/result.json] — and reached 0 of 5 goals under
Nav2's controller in Gazebo [docs/v2/r3/data/a1/costs_summary.json]. Recording the costmap under
every path the controller received showed why: 29–77 % of Theta*'s paths put the robot's centre
in inscribed or lethal cost, against at most 10 % for the planners that reached their goals
[docs/v2/r3/data/a1/README.md]. Benchmarks should show that, not hide it.

Another honest finding: stock Nav2 found 42 of 60 paths where my exported A* found 60 — not a
better planner, a convention. With the start and goal snapped to free space, as COCO Lab does,
Nav2 found 60 of 60 too [docs/v2/r3/data/a1/snap_summary.json].

No physical robot — every result is labelled MODEL (browser) or STACK (ROS 2 in Gazebo,
a simulation).

Try it (no install): https://gauthamcodes.github.io/coco-labs/
Code: https://github.com/GauthamCodes/coco-labs

#ROS2 #Robotics #Navigation #Reproducibility #OpenSource

## Short version

COCO Lab: a ROS 2 robot you can drive, benchmark and program in your browser. Deterministic
(hash-verified across browsers), a sandboxed verified leaderboard, and your planner exports to a
real ROS 2 node for Gazebo + Nav2. Honest results included — a planner that wins in the model and
fails every drive in ROS 2, and why. https://gauthamcodes.github.io/coco-labs/

(Before posting: if R3 is not yet deployed, keep COCO-Bench v1 under "coming next", as above.)
