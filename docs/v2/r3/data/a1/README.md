# R3 Part A follow-ups to R2.7 — STACK (Gazebo Harmonic + Nav2 Jazzy, simulation; no physical robot)

Gautham's answers of 2026-11-06: **(2)** keep Lazy Theta\*'s 0/5 drives as a visible negative row and
re-run them recording the costmap cost along each path, to confirm or reject "its paths hug corners";
**(3)** report stock Nav2 and Nav2 with start/goal snapped to free cells, both labelled.

Raw runs (read-only evidence): `~/coco_lab_runs/r3/a1/`; checksums in
[`raw_checksums.sha256`](raw_checksums.sha256). Tooling: `tools/r2/ros2_bench.py` (`--costs`,
`--snap`), queue `tools/r3/ros2_queue_a1.sh`, summary `tools/r3/a1_costs.py` →
[`costs_summary.json`](costs_summary.json). One fresh headless simulator per session, never
`--fast`; every session on the **balanced** profile, **on AC**, clean tree (`session.json`).

## 1. The cost under the paths the controller received (answer 2)

Same five Depot drives as R2.7 (`docs/v2/r2/data/r27/depot5_drive.json`), NavigateToPose with Nav2's
Regulated Pure Pursuit, the planner swapped in. For every plan the controller received
(`/received_global_plan`, published at the controller's rate), the raw cost under each pose was read
from the live **local** costmap (the one RPP's collision check reads) and the global one. Cost ≥ 253 is
`INSCRIBED_INFLATED_OBSTACLE`: the robot's centre may not be there.

| planner | reached | share of received plans with ≥ 1 pose at cost ≥ 253 in the local costmap, per drivable scenario (s001 / s021 / s061 / s081) |
| --- | --- | --- |
| stock Nav2 (Smac 2D) | **3/5** | 0.000 / 0.000 / — (no plan: 208) / 0.079 |
| A\* starter (user node) | **4/5** | 0.026 / 0.000 / 0.101 / 0.078 |
| Lazy Theta\* (user node) | **0/5** | **0.450 / 0.411 / 0.773 / 0.293** |

s041 fails for all three (208, no plan: the live start in drive mode; R2.7's UNRESOLVED row, unchanged).
Theta\*'s four other drives abort with 104 (FollowPath failed), as in R2.7.

**Result: the explanation is supported.** On every drivable scenario, 29–77 % of the plans RPP
received from Lazy Theta\* put at least one pose in inscribed or lethal cost of the local costmap,
against 0–10 % for the two planners that reach their goals on the same scenarios. RPP's collision check
stops the robot when the path it projects enters such cost, which is consistent with the 104 aborts.
What is MEASURED is the cost under the received paths; that RPP's check is what stops each drive is
still INFERENCE (the check's own decisions were not logged). The Theta\* row stays visible as a
negative result.

*A possible reason (INFERENCE, not tested here)* why Theta\*'s paths enter that cost although the
planner checks every segment against the global costmap at planning time: its any-angle segments run
straight between corner vertices, and the local costmap (a rolling window with live LiDAR marks, odom
frame) does not match the global one exactly, so a segment that grazes inflation in one can cross the
inscribed band in the other.

## 2. Stock Nav2 and Nav2 with start and goal snapped (answer 3)

Pending: three planning sessions (`plan_snap1..3`), each request to stock Nav2 sent twice — as given
and with start and goal moved to the nearest free cell of the live global costmap (raw cost < 253,
breadth first, the rule COCO Lab and the exported node use) — beside the A\* starter.

## Notes

- 2026-11-07 ~08:40 IST: an edit to `tools/m6/m6f8_run.sh` (the runner the queue executes) was made
  while the A\* starter session was in its driver phase, and reverted to the exact committed bytes
  within about a minute; bash had not read past that point. The session completed normally (no error in
  `runner.log`, all five rows). Recorded for completeness.
