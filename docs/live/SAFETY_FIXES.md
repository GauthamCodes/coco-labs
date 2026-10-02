# Phase 2 · safety fixes before Part B (2026-10-02)

The owner's decisions 1 and 2 on the Part A audit, plus localisation at
startup.
- Code: f1600b2 (latched STOP), 6c1653f (executive mode), 54133fe
  (localised before motion).
- `main` was fast-forwarded 6249e7d..54133fe after CI and Lab went green
  on 54133fe (CI: **2035 tests, 0 failures**).
- Evidence: `docs/data/live/safety/`. Each run directory holds gzipped
  `ws.jsonl` and `ros.jsonl` (plus launch or container logs); the scripts
  are in `scripts/`.

All runs used a fresh simulator, `mission.launch.py`, headless,
`ROS_DOMAIN_ID=62`, quiet machine, overlay `~/coco_live_ws` built from
`live`. Every number is **(measured)**, and one run per row is not a rate.

## STOP during each mission stage

The page's STOP sequence: `stop`, 3 × zero `drive`, `set_mode stop`.

| stage | run | z at STOP (m) | moving cmds in the 1 s before | wheel cmd zero | body at rest | moving cmds, zero → +10 s | speed at +10 s | modes after STOP | mission | latched at +10 s |
|---|---|---|---|---|---|---|---|---|---|---|
| Nav2 leg | `stop_nav` (red) | 0.00 | 20 | 3.6 ms | 166 ms | **0** | 0.0 | `idle` only | RECOVERY +14 ms → ABORT +1.82 s | yes, 0 violations |
| climb, foot | `stop_climb2` (yellow) | 0.04 | 18 | 1.4 ms | 225 ms | **0** | 0.0 | `idle` only | RECOVERY +56 ms → ABORT +1.95 s | yes, 0 |
| climb, mid-ramp | `stop_climb3` (green) | 0.42 | 17 | 5.8 ms | 221 ms | **0** | 0.0 | `idle` only | RECOVERY +18 ms → ABORT +1.92 s | yes, 0 |
| platform approach | `stop_approach` (blue) | 0.65 | 20 | 2.9 ms | 141 ms | **0** | 0.0 | `idle` only | RECOVERY +68 ms → ABORT +1.77 s | yes, 0 |
| grasp | `stop_grasp` (red) | 0.65 | 0 (arm working, wheels idle) | 1.6 ms | 63 ms | **0** | 0.0 | `idle` only | RECOVERY +88 ms → ABORT +1.79 s | yes, 0 |
| descent with the object | `stop_descend` (yellow) | 0.60 | 20 | 3.1 ms | 156 ms | **0** | 0.0 | `idle` only | RECOVERY +98 ms → ABORT +1.80 s | yes, 0 |

- **Column definitions.** "Wheel cmd zero" is the first zero on
  `/diff_drive_controller/cmd_vel` after `stop` left the client. "Body at
  rest" is ground truth |v| < 0.02 m/s and |ω| < 0.05 rad/s, held 0.5 s.
- **What happened after STOP.** Nothing re-asserted a moving mode: the only
  values on `/mission/mode` were the server's and the executive's `idle`.
  The executive fell silent after ABORT. The arbiter read `mode=idle
  active=none` at +10 s, and there was 1 wheel publisher in every sample.
- **Part A, before the fix.** The same STOP left the wheels moving again
  at 723 ms, with 152 moving commands in 7.7 s.
- **`stop_climb` (excluded).** STOP fired 3 s into CLIMB, before
  ramp_driver had started driving (z 0.0, 0 moving commands before). It is
  kept in the evidence; `stop_climb2` and `stop_climb3` repeat it with the
  probe waiting for `rl` on the wheels first.
- **Grasp: not measured.** Whether the arm stops mid-grasp; only the
  wheels were.

### On the ramp: the robot holds position

Ground truth, from STOP:

| run | z (m) | STOP → +1 s (stopping distance) | +1 s → +10 s |
|---|---|---|---|
| `stop_climb2` | 0.042 | 32.4 mm | ≤ 0.001 mm |
| `stop_climb3` | 0.418 | 28.1 mm | ≤ 0.001 mm |
| `stop_descend` | 0.601 | 6.0 mm | ≤ 0.001 mm |

The robot was climbing at about 0.39 m/s. No roll-back was measurable over
10 s. This is in simulation (Gazebo contact model), not a statement about
hardware.

## Nav2 mode with no mission

`set_mode auto` then `nav_goal` to each candidate whose 0.45 m
neighbourhood is free on the map. Two candidates were rejected as not
free. "Arrived" means the belief pose was within 0.3 m.

| | goals | arrived | Nav2 cmds → wheels, per goal | arrival time | end error (belief) | first `/plan` after the goal |
|---|---|---|---|---|---|---|
| native (`nav_native`) | 7 | **7** | 63–462 → 63–464 moving | 2.9–20.1 s | 0.044–0.227 m | 4–872 ms |
| Docker compose (`nav_docker`, image 7d664d5fe79f) | 7 | **7** | 77–492 → 83–576 moving | 3.5–24.2 s | 0.062–0.230 m | 3–979 ms |

- **Before the fix (Part A):** 499 Nav2 commands, 0 at the wheels.
- **Plan timing is not a clean measurement.** The "first `/plan`" column
  includes 1 Hz replans of the previous goal. Part B measures goal → plan
  properly.
- The container recorder logged more wheel commands than Nav2 commands
  because the arbiter's 20 Hz watchdog fills gaps.

## Regression: one full fetch

`fetch_native` (blue):
- **COMPLETE**, `result=fetch`, 178.7 s wall from `mission start`, all 16
  nominal states.
- One RECOVERY → RELOCALIZE on RETURN_HOME (`LOCALIZATION_DEGRADED`), then
  resumed and completed.
- 1 wheel publisher throughout.

## Localised before motion

Seconds from the client connecting (after `/healthz` 200) to
`robot.localised: true`:
- **0.05–0.11 s** in all 9 native runs;
- **0.06 s** in Docker.

Part A: never, in 400 s at rest.

**Cause:** AMCL publishes `/amcl_pose` TRANSIENT_LOCAL, and the platform
subscribed VOLATILE. **Fix:** the latched QoS, plus one
`request_nomotion_update` (std_srvs/Empty, Jazzy). Live: a fresh pose
(stamp 28 s) followed a call at sim t = 27 s.
