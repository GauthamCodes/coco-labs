# Milestone 0A — does the collision monitor's gating reach the wheels?

Measured 2026-09-28 (UTC) on the consolidated main, merge commit `232454d`,
overlay `~/coco_p0merge_ws` built from that tree, `ROS_DOMAIN_ID=77`, one
fresh simulator per run. Full traces are in `~/coco_nav_runs/m0a/<run>/`;
this directory keeps the summaries.

## The question

`PROJECT_STATE.md` known limitation 0 (C2-M5.0) says: `/cmd_vel_nav` had 7
publishers and 2 subscribers, the relay fed the collision monitor's output
back into the smoother's input, and during a SLOWDOWN capped at 0.090 m/s the
wheels reached 0.300 m/s on 84.2 % of one run's slowdown samples.

The fix is **6503cd5** (C2-NAV.42): `cmd_vel_relay` publishes its own topic,
`/cmd_vel_gated`, and `cmd_vel_arbiter` reads that. c8a8206 (C2-NAV.43) is
the results commit that integrated it. Both are ancestors of `232454d`, so
nothing was re-applied. This directory measures whether the fix works.

## Method

`m0a_cmdpath_run.sh` brings up topology B the way `nav_tour_run.sh` does
(sim → `arbiter.launch.py initial_mode:=nav` → `nav.launch.py arbiter:=true`)
in the **frozen `coco_world.world`**, the world every historical STOP-probe
number was measured in. It reads the live graph (`topology_live.txt`), then
runs one of three modes:

| mode | what drives | what it asks |
|---|---|---|
| `slowdown` | a static side wall is spawned with its face 0.32 m to the robot's left (inside `PolygonSlow`'s ±0.40 m square, outside `PolygonStop`'s 0.25 m circle, out of the path). A stand-in controller (`m0a_slowdown_drive.py`) holds **raw 0.30 m/s** on `/cmd_vel_nav` for 10 s of sim time. | Is the wheel held to `slowdown_ratio` × command = **0.090 m/s**? |
| `control` | the same drive, **no wall** | Is the 0.090 attributable to SLOWDOWN? |
| `stop` | `c2nav42_cmdpath.py stop`, unchanged: turn to the west wall, then hold raw 0.30 m/s | Historical comparability with C2-NAV.42/43/47 |

The recorder is `c2nav42_cmdpath.py`, unchanged, with metrics imported from
`c2nav41_topology.py`. Rates come from `ros2 topic hz` during the drive.
`m0a_cmdpath_analyse.py` computes the SLOWDOWN distributions, with TOL
0.005 m/s.

## Results (measured)

**Topology, every run:**
- `/cmd_vel_nav`: publishers `controller_server` and `behavior_server` only; subscriber `velocity_smoother` only.
- `/cmd_vel_smoothed` → `collision_monitor`.
- `/cmd_vel`: `collision_monitor` (+ an inert `docking_server`) → `cmd_vel_relay`.
- **`/cmd_vel_gated`: exactly one publisher (`cmd_vel_relay`) and one subscriber (`cmd_vel_arbiter`).**
- **Wheel topic: exactly one publisher (`cmd_vel_arbiter`).**
- The relay no longer publishes on `/cmd_vel_nav`, so the loop is gone.

**Injected SLOWDOWN** (`slowdown_r01`, `r02`, `r04`; r03 is VOID, see below):

| run | monitor Hz | relay Hz | wheel Hz | SLOWDOWN rows | wheel m/s p50 / p90 / p99 / max | rows over cap | wheel msgs = latest gated |
|---|---|---|---|---|---|---|---|
| r01 | 20.02 | 20.01 | 25.97 | 100 | 0.090 / 0.090 / 0.090 / 0.090 | 0 | 278 / 278 |
| r02 | 19.98 | 19.98 | 20.00 | 100 | 0.090 / 0.090 / 0.090 / 0.090 | 0 | 213 / 213 |
| r04 | 20.00 | 19.98 | 19.70 | 100 | 0.090 / 0.090 / 0.090 / 0.090 | 0 | 204 / 204 |
| **pooled** | | | | **300** | **0.090 / 0.090 / 0.090 / 0.090** | **0 (0.0 %)** | **695 / 695** |

- The cap is 0.3 × 0.30 = 0.090 m/s (`slowdown_ratio` read back live: 0.3).
- Monitor authority: 0 of 388 / 387 / 388 samples exceeded.
- Bypass rows: 0.
- No wheel message in any drive window was above the latest monitor command.
- **Wheel Hz above relay Hz is by design, not a second source.** `cmd_vel_arbiter` forwards on arrival, and its 20 Hz steady-clock watchdog re-emits the *latest* command whenever the gap exceeds 50 ms. Every wheel message equalled the latest gated command. Before the fix, the excess was 10.15–10.77 Hz of raw controller commands.

**Control** (`control_r01`, no wall):
- 0 SLOWDOWN rows.
- The wheel followed the raw command: p50 = max = **0.300 m/s** over 273 messages.
- The 0.090 above is the SLOWDOWN gate.

**STOP probe** (`stop_r01`):
- `stop_held: false`, and the monitor never entered STOP (0 STOP rows).
- **FootprintApproach** (363 APPROACH rows) brought the robot to rest 0.264 m from the wall face (x = −3.6356).
- The wheels read **0.0000 m/s for the last 6 s**, and ≤ 0.01 m/s on 299 of 397 rows, while the raw command held 0.30 m/s for the whole 39.7 s budget.
- Monitor authority: 0 of 512 exceeded. Bypass rows: 0.
- C2-NAV.47's run of the same probe hit STOP (69 rows) and stopped at 0.249 m.
- UNVERIFIED explanation: C2-NAV.48 raised `local_costmap.robot_radius` 0.20 → 0.25, which enlarges the footprint APPROACH projects, so the robot now halts before reaching the 0.25 m STOP circle.

**Four FIXED P03C cases** (`p03c_episode_run.sh`, fresh sim each, command path recorded over the whole mission):

| run | outcome | sim s | runner checks | home error m | target (bay) -> end | nav-owned rows over monitor | gated_zero_moving | bypass rows = raw controller | STOP rows (driven) | historical P03C (dfcbc4b): outcome / home error / recoveries |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed_red | complete / fetch | 186.3 | 17 PASS / 0 FAIL | 0.103 | bay_1 (4.05, -6.0) -> (-1.765, 0.026) | 0 / 852 | 17 (2.00 %) | 0 of 77 | 0 (0) | COMPLETE/fetch / 0.087 / 0 |
| fixed_green | complete / fetch | 163.8 | 17 PASS / 0 FAIL | 0.075 | bay_2 (4.05, -2.0) -> (-1.919, -0.015) | 0 / 570 | 1 (0.18 %) | 0 of 77 | 0 (0) | COMPLETE/fetch / 0.124 / 0 |
| fixed_blue | complete / fetch | 152.3 | 17 PASS / 0 FAIL | 0.108 | bay_3 (4.05, 2.0) -> (-1.921, 0.152) | 0 / 533 | 9 (1.69 %) | 0 of 77 | 0 (0) | COMPLETE/fetch / 0.013 / 1 |
| fixed_yellow | complete / fetch | 176.2 | 17 PASS / 0 FAIL | 0.129 | bay_4 (4.05, 6.0) -> (-1.794, 0.042) | 0 / 769 | 11 (1.43 %) | 0 of 76 | 0 (0) | COMPLETE/fetch / 0.176 / 0 |

**4 / 4 COMPLETE/fetch** on `232454d`. Each target physically ended at home (x ≈ −1.8 to −1.9). Over the rows Nav2 owns, the wheels never exceeded the monitor (0 of 2,724 pooled). `gated_zero_moving` (38 rows pooled, 1.39 %) is the already-documented short-streak residual (0.088–2.92 %, not attributed). The missions exercised LIMIT (20–29 rows each) and one APPROACH row, and **no SLOWDOWN**: the SLOWDOWN answer comes from the injection runs above, not from these. The historical column is from `~/coco_runs_p03c/*/report.json`. It is a separate series and a different harness version, and the home error there was computed by `navigation_world_report.py`, not by this script.

## Comparability

These are a **new measurement series**. They are not a before/after of the
same runs.

- **v1 19/20 fetch** and **C2-M5.0's 84.2 %** were measured with the `/cmd_vel_nav` loop in place.
- **The P03C 13/13 was NOT measured with the loop.** 6503cd5 is an ancestor of the commit those runs recorded (`dfcbc4b`). They are post-fix results from a different harness version (report via `navigation_world_report.py`, runs at `~/coco_runs_p03c`), on an uncommitted working tree that later became 917bc59.
- The FIXED rows above are a third series: the committed merge `232454d`, the merged tree's own runner.
- The SLOWDOWN injection is new in this milestone. There is no historical run of the same injection to compare against.

## VOID

- **`slowdown_r03`:** its stack was killed at 19:27 UTC by `ros_clean.sh`, run from a stale r01 runner's EXIT trap. `VOID.txt`. Not a result. Replaced by `slowdown_r04`.
- **`slowdown_r01`'s `ros_clean.log`** was overwritten by that same event. See `NOTE_ros_clean_log.txt`. Its measurement files predate it.

## Reproduce

```bash
export COCO_WS=$HOME/coco_p0merge_ws ROS_DOMAIN_ID=77
bash scripts/build_overlay.sh "$COCO_WS"
ln -s "<ws>/moveit_prefix" "$COCO_WS/moveit_prefix"
bash docs/data/m0a_cmdpath_run.sh "$PWD" ~/coco_nav_runs/m0a/slowdown_rNN slowdown
bash docs/data/m0a_cmdpath_run.sh "$PWD" ~/coco_nav_runs/m0a/control_rNN control
bash docs/data/m0a_cmdpath_run.sh "$PWD" ~/coco_nav_runs/m0a/stop_rNN stop
python3 docs/data/m0a_cmdpath_analyse.py ~/coco_nav_runs/m0a/slowdown_r0{1,2,4}
bash docs/data/p03c_episode_run.sh ~/coco_nav_runs/m0a/fixed_red fixed 0 red
```
