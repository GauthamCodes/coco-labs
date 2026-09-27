# Larger-world validation record

Status: **implemented; all four colours completed fresh autonomous fetches on the
final runtime revision 474601a1663830c965044e271c4a86a1282d2736**.

Starting commit: d317d85ee6f1575c2620f4e467d7e322d0310bc0.
Only simulation was used; no physical robot was commanded.

## Final mission evidence

FACT: every run left home, passed the existing arrival/climb gates, detected its
selected target, physically lifted it, descended, returned home, detached the
magnet, placed the rod standing on the floor, and reached COMPLETE/fetch.

| Colour | Lift | Home arrival error | Localization recoveries | Wall time | Gazebo GUI |
|---|---:|---:|---:|---:|---|
| red | 35.8 mm | 0.095 m | 0 | 589.9 s | on |
| green | 35.9 mm | 0.060 m | 1 | 495.8 s | off |
| blue | 36.3 mm | 0.085 m | 1 | 463.8 s | off |
| yellow | 35.1 mm | 0.133 m | 0 | 497.2 s | off |

FACT: all four final placement checks measured the rod centre at Z=0.0790 m.
Green and blue pre-ramp arrivals were 0.355 m and 0.321 m from their goals:
accepted and logged by the existing 0.50 m consistency band. That gate was
not weakened. All home arrivals were inside the original 0.25 m tolerance.

FACT: green and blue recovered once near home, then completed. Their final
reason field retains LOCALIZATION_DEGRADED despite COMPLETE/fetch.
Red and yellow needed no recovery. These four runs are not a reliability rate.

The archived [results](data/navigation_world_final/results.json) identify the
original per-node logs and their hashes. Executive and grasp logs preserve
the physical lift, ground-truth home arrival, magnet detachment, standing
placement measurement, and terminal verification. Nav2, RViz and simulator
logs preserve distinct process instances for every fresh run.

### Evidence retained after host restart

The machine rebooted after the queued matrix finished, clearing /tmp/coco-large.
Persistent per-node logs in ~/.ros/log survived and were copied unchanged into
data/navigation_world_final. The earlier compact development-run summaries
were already saved and are retained in data/navigation_world_development_runs.json.
Raw temporary topic captures, runner logs and screenshots did not survive.
Their live inspection is recorded here; they are not presented as archived files.
Future run outputs should use ~/coco_navigation_validation rather than /tmp.

## Build, tests and visualization

FACT: coco_config, gazebo_models and coco_mission were built in the fresh
/home/gautham/coco_navigation_overlay, using the existing dependency underlay.
Only affected packages were built. Final build/test output is archived alongside
the mission logs. An initial final test run had 729 passes and one message-count
failure (9 received, 10 required) in the unchanged live wiring test; its isolated
25-test module passed without changes. FACT: the final full-suite confirmation passed **730 tests in 21.76 s**;
see [tests-final.txt](data/navigation_world_final/tests-final.txt).

FACT: actual navigation messages were received on /plan and /local_plan
(nav_msgs/msg/Path, frames map and odom). controller_server publishes the local
path. planner_server and route_server both advertise /plan; the configured BT
and mission logs use ComputePathToPose with GridBased/SmacPlanner2D.
The DWB controller and Nav2 parameters were not replaced or tuned.

FACT: RViz started automatically and its grouped displays were inspected during
real outbound and return navigation. Both actual paths, map, global/local
costmaps, robot, TF, scan and footprint were enabled. Archived RViz logs from
each final mission show the 500 x 380 map/global costmap and 60 x 60 local map.
The corrected gui:=true workflow was exercised by the final red mission.
Earlier direct inspection confirmed the larger Gazebo world rendered.

FACT: deterministic generation, static box/map agreement, full rod support and
nonintersection, unknown ramp interiors, blocked low-ramp shortcuts, and
0.30 m-clear connectivity to every approach/exit and representative rooms pass.
The map is 500 x 380 at 0.05 m, origin (-6.5,-9.5), with world-to-map X offset +2.
Live flat-ground scan/map checks observed median residual 0 m and 90th percentile
0.05 m in sampled approach sections. Pitched-ramp residuals are not treated
as a flat-map consistency check.

OBSERVATION: no final simulator crash or controller progress failure was observed.
Archived final Nav2 logs contain zero controller progress-failure or control-loop
rate warnings. No controlled before/after performance benchmark was performed;
wall times above include the longer routes and manipulation sequence. No
speculative performance optimization was applied.

## Corrections and scope

The larger world retains the original planner/controller and command safety chain.
The only localization runtime change is the terrain predicate: four relocated
ramp bays replace the obsolete single Y=0 exclusion. It now derives bay centres
from the same TARGETS table used for spawning. Thresholds and recovery behavior
are unchanged. Executive transitions, grasp, perception and depth fusion are
unchanged. Dynamic obstacles are configuration-only and disabled.

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
| green-v10 | eb42581 | Grasped, descended to X=6.65 and began returning; ABORT/LOCALIZATION_RECOVERY_TIMEOUT; queued colours stopped |

FACT: the green-v7-server captured global path went through world X=1.3 around
the approach wall tip and onto the low physical wedge before doubling back
to goal (0.5,-2). Its actual pose stalled near (0.38,-0.93), while localization
error was about 0.066 m. Flat-ground scan-to-map median residual was 0 m,
90th percentile 0.05 m in those samples.

Corrections retained in the final implementation:
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

FACT: green-v10 cleared descent on the restored grade, but still failed return
localization. Its recovery spin could not regain a usable fix within the unchanged
timeout. Extra runout alone did not establish a completed fetch.

OBSERVATION: after enlarging the asymmetric bay pilasters and adding distinct
exit columns, all four fresh missions completed. HYPOTHESIS: stronger nearby
longitudinal scan features reduced the ramp-related pose drift. This was not a
controlled statistical comparison, and green/blue still needed recovery near home.

Earlier development attempts red-v2/v3/v4 aborted outbound; red-v5 grasped but
failed to return. An initial stale-overlay attempt was discarded before
mission start. These attempts are not counted as successful validation.

No Nav2, command safety-chain, executive, perception, grasp or depth-fusion
runtime parameters were changed. The localization-health terrain predicate was
updated solely to match the actual bay geometry; its thresholds are unchanged.
