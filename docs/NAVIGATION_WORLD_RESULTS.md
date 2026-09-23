# Larger-world validation record

Status: **in progress; not all colours verified on final geometry**.

Starting commit: d317d85ee6f1575c2620f4e467d7e322d0310bc0.
Evidence directories are under /tmp/coco-large on the validation host.
Only simulation was used; no physical robot was commanded.

## Completed checks

FACT: fresh overlay builds succeeded for coco_config, gazebo_models and
coco_mission. The overlay is /home/gautham/coco_navigation_overlay.
FACT: 252 coco_config/gazebo_models tests and 311 coco_mission tests passed
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
The final gui:=true launch still needs a fresh-run check.

## Mission evidence before the latest corrections

| Run | Geometry | Outcome |
|---|---|---|
| red-v6 | c81d78b | COMPLETE/fetch; attached, lifted, returned, detached and placed; final home error 0.083 m; one localization recovery |
| final-green | c81d78b | Grasped and descended; ABORT/LOCALIZATION_RECOVERY_TIMEOUT on return; rod held |
| final-blue | c81d78b | Grasped and descended; ABORT/LOCALIZATION_RECOVERY_TIMEOUT on return; rod held |
| final-yellow | c81d78b | Grasped and descended; recovered localization, then ABORT/RETURN_FAILED; rod held |
| green-v7 | c6910cb | Invalid startup: combined Gazebo GUI/server never exposed world services or LiDAR; no mission started |
| green-v7-server | 51df96d | Interrupted after outbound controller progress failure; not a completed mission |

FACT: the green-v7-server captured global path went through world X=1.3 around
the approach wall tip and onto the low physical wedge before doubling back
to goal (0.5,-2). Its actual pose stalled near (0.38,-0.93), while localization
error was about 0.066 m. Flat-ground scan-to-map median residual was 0 m,
90th percentile 0.05 m in those samples.

Corrections under test:
- Shorten downhill run from 2.0 to 1.5 m, retaining rise and existing exit goal;
  the foot is now X=6.0, providing flat travel before the unchanged arrival gate.
- Extend approach walls to X=1.8, past the mapped ramp silhouette, to close
  the demonstrated low-ramp shortcut.
- Start Gazebo server and GUI client separately for gui:=true; a manual separate
  client connected successfully to the same server that published sensors.

HYPOTHESIS: additional flat runout improves localization before return.
This has not yet been established by a completed mission on this geometry.

Earlier development attempts red-v2/v3/v4 aborted outbound; red-v5 grasped but
failed to return. An initial stale-overlay attempt was discarded before
mission start. These attempts are not counted as successful validation.

No Nav2, safety-chain, executive, perception, grasp or depth-fusion runtime
parameters were changed to obtain a pass.
