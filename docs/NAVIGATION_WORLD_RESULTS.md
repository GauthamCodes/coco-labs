# Larger-world validation record

Status: **in progress; green-v10 running, remaining fresh colours queued on success**.

Starting commit: d317d85ee6f1575c2620f4e467d7e322d0310bc0.
Evidence directories are under /tmp/coco-large on the validation host.
Only simulation was used; no physical robot was commanded.

## Completed checks

FACT: fresh overlay builds succeeded for coco_config, gazebo_models and
coco_mission. The overlay is /home/gautham/coco_navigation_overlay.
FACT: after restoring the original downhill grade and matching the mapped-ground
predicate to all four bays, all three packages built and all 565 tests passed.
Earlier, 252 coco_config/gazebo_models tests and 311 coco_mission tests passed
after adding downhill runout. The later approach-wall regression test and
RViz/geometry set passed 26 tests.
FACT: earlier unchanged perception tests passed 136 tests; approach tests
passed 28 tests.

FACT: actual navigation messages were received from /plan and /local_plan
(nav_msgs/msg/Path, frames map and odom). The controller publisher is
controller_server; planner_server and route_server both advertise /plan.
Configured BT and action logs use ComputePathToPose with GridBased.
No fake paths or additional publishers were introduced.

FACT: RViz autolaunched and rendered map, costmaps, robot, TF, scan and
footprint during green-v7-server. Window-only captures are in that directory.
A separate Gazebo client rendered the larger world during that attempt.
FACT: green-v8 used the corrected gui:=true launch: LiDAR appeared in 9 s,
all Nav2 lifecycle nodes became active, and its automatic GUI rendered the world.

## Mission evidence before the latest corrections

| Run | Geometry | Outcome |
|---|---|---|
| red-v6 | c81d78b | COMPLETE/fetch; attached, lifted, returned, detached and placed; final home error 0.083 m; one localization recovery |
| final-green | c81d78b | Grasped and descended; ABORT/LOCALIZATION_RECOVERY_TIMEOUT on return; rod held |
| final-blue | c81d78b | Grasped and descended; ABORT/LOCALIZATION_RECOVERY_TIMEOUT on return; rod held |
| final-yellow | c81d78b | Grasped and descended; recovered localization, then ABORT/RETURN_FAILED; rod held |
| green-v7 | c6910cb | Invalid startup: combined Gazebo GUI/server never exposed world services or LiDAR; no mission started |
| green-v7-server | 51df96d | Interrupted after outbound controller progress failure; not a completed mission |
| green-v8 | 5eea088 | Interrupted after repeated entrance-turn progress failures and a completed Nav2 recovery spin; no grasp |
| green-v9 | 88058bc | Reached and physically grasped green; DESCENT_TIMEOUT at X=4.49, with forward command and no translation at the platform edge |

FACT: the green-v7-server captured global path went through world X=1.3 around
the approach wall tip and onto the low physical wedge before doubling back
to goal (0.5,-2). Its actual pose stalled near (0.38,-0.93), while localization
error was about 0.066 m. Flat-ground scan-to-map median residual was 0 m,
90th percentile 0.05 m in those samples.

Corrections under test:
- The 1.5 m downhill run caused a descent hang-up in green-v9 and was removed.
  Restore the original 2 m / 18-degree wedges and shorten the trailing platform
  from 1.5 to 1.2 m; far foot X=6.2, target X=4.05 and all mission goals unchanged.
- Correct the mapped-ground predicate: the old Y=0 wedge exclusion did not
  represent the four relocated bays. It now derives centres from TARGETS;
  thresholds, recovery logic and routing are unchanged.
- Extend approach walls to X=1.8, past the mapped ramp silhouette, to close
  the demonstrated low-ramp shortcut.
- Open corridor mouths from X=-2.5 to X=-1.0 after repeated entrance-turn
  progress failures; keep 1.2 m clearance and the closed low-ramp shortcut.
- Start Gazebo server and GUI client separately for gui:=true; a manual separate
  client connected successfully to the same server that published sensors.

HYPOTHESIS: additional flat runout improves localization before return.
This has not yet been established by a completed mission on this geometry.

Earlier development attempts red-v2/v3/v4 aborted outbound; red-v5 grasped but
failed to return. An initial stale-overlay attempt was discarded before
mission start. These attempts are not counted as successful validation.

No Nav2, command safety-chain, executive, perception, grasp or depth-fusion
runtime parameters were changed. The localization-health terrain predicate was
updated solely to match the actual bay geometry; its thresholds are unchanged.
