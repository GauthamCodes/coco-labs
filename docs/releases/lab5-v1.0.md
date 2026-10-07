**Try it:** https://gauthamcodes.github.io/coco-labs/?view=move

COCO Lab's fifth lab, **Move**: why the trajectory a robot drives is not the
path it was given. A global planner draws a line once; ten times a second a
local controller turns it into a speed and a turn rate — with the robot's
limits, from where the robot *believes* it is, around whatever is in the way.
Write-up, every claim's evidence and the limitations:
[`docs/labs/LAB5_MOVE.md`](https://github.com/GauthamCodes/coco-labs/blob/lab5-v1.0/docs/labs/LAB5_MOVE.md).

### In the lab

- **Same path, three controllers (Replay):** one global path, computed once
  by Nav2's SmacPlanner2D and frozen in a file, driven by DWB, MPPI and
  Regulated Pure Pursuit on the same robot with the same limits. Every run's
  trajectory, the candidates each controller scored (as Nav2 itself
  published them — DWB's rejected ones in red), its chosen trajectory, where
  the robot believed it was, the collision monitor, the closest approach.
  Predict, then see the measured table.
- **People on the apron (Replay):** a person crosses in front of the robot,
  or walks straight down its path.
- **Run 15: "0 of 819":** the historical log of COCO's one failed fetch,
  quoted verbatim, beside a reproduction of its mechanism — labelled as not
  being run 15.
- **When the map is wrong (D\* Lite, Sketch):** paint obstacles the robot's
  map lacks; coco_lab (in your browser, via Pyodide) drives the episode, D\*
  Lite repairing the plan and A\* searching again from scratch beside it.
- **What is proven:** every claim with its test or measurement.

### Measured (details in `docs/RESULTS.md` "COCO Lab Phase 6")

54 Gazebo runs, a fresh simulator each, never `--fast`, 0 void, every runner
check passing (the arbiter the wheel topic's only publisher throughout) —
`docs/data/lab5/`:

- **Around a wall end into a room:** DWB 0 of 5 (stuck before the hairpin),
  MPPI 5 of 5 (cutting the corner), RPP 5 of 5 (closest to the line).
- **A person crossing:** 15 of 15 reached the goal without contact.
- **A person walking down the path:** nobody swerved. In 15 of 15 runs the
  robot stopped in the person's way and the person — a moving obstacle with
  no collision geometry that never stops — walked into it.
- **Run 15's mechanism, not its symptom:** told it stood 3.4 m from the
  truth, all three controllers refused the path in their first control cycle
  (`INVALID_PATH`; the path lay outside the local costmap) — 9 of 9. DWB
  scored 0 candidates, not run 15's 819.
- **D\* Lite:** the same cost as A\* from scratch after every change (tested
  on 1,000 seeded maps); less total work in 191 of 200 seeded worlds — but
  2.9× MORE on Nav2's own costmap when a person stopped on the apron.
- 5 runs per controller is a distribution, not a rate. Several observations
  are recorded but not attributed (LAB5_MOVE.md §5).

### Tests

`run_all_package_tests.sh` 3,081 passed, 0 failed, 0 skipped (coco_lab 604,
coco_lab_ros 121; every other package unchanged); lab_web vitest 308, tools
117; CI green.

### Demo video

`coco_lab5_demo.mp4` (attached): recorded in headless Firefox from the
public site, browser only; coco_lab's computing waits cut and listed
(`docs/data/lab5/video/`).
