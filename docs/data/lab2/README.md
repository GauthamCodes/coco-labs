# Phase 3 (Lab 2, Localise) evidence — `docs/data/lab2/`

The tools and the committed results of COCO Lab Phase 3. The results are in
[`docs/RESULTS.md`](../../RESULTS.md) "COCO Lab Phase 3 — Localise" and the
lab write-up is [`docs/labs/LAB2_LOCALISE.md`](../../labs/LAB2_LOCALISE.md).

## Files

| file | what |
|---|---|
| `lab2_run.sh` | one session on a FRESH headless simulator: `fidelity` (scans at 40 seeded poses, then the straight, square and tour drives) or `kidnap ARM TARGET` (the recovery_alpha A/B). Modelled on `lab1c_run.sh`: refuses if anything is up, kills only its own process groups, then `ros_clean.sh` |
| `lab2_probe.py` | the live probe: teleports with `gz service .../set_pose`, drives through `/cmd_vel_teleop` (an arbiter input) with `coco_lab.sketch.drive_command` — the SAME control law Sketch uses — and logs truth, odometry, IMU, scans and `/amcl_pose` |
| `lab2_batch.sh` | runs sessions one after another, each on a fresh simulator, waiting for a quiet machine and retrying a refused session |
| `tour_route.txt` | the 121 m tour: waypoints coco_lab's own A* found on the arena map inflated by 0.45 m |
| `an_fidelity.py` → `fidelity/fidelity.json` | Sketch vs Gazebo at identical poses (range error per beam) and odometry drift on the same commands |
| `sketch_rates.py` → `sketch_rates.json` | Sketch outcome counts over 20 filter seeds per setting (Sketch, not the robot) |
| `an_kidnap.py` → `kidnap_ab.json` | the real-stack kidnap A/B: AMCL `recovery_alpha_*` 0/0 (as shipped) vs 0.001/0.1 |
| `rl_replay.sh` | replays a session's wheel odometry and gyro into robot_localization's `ekf_node`, offline |
| `an_ekf.py` → `ekf_drift.json` | wheel odometry vs the EKF on identical recorded drives |
| `amcl_replay.py` → `an_amcl.py` → `amcl_odom.json` | AMCL on wheel odometry vs AMCL on the EKF, offline, on identical recorded scans |

Large artifacts — the rosbag2 directories (≈ 120 MB per fidelity session),
the per-session logs and the probe's JSON lines — live under
`~/coco_lab_runs/lab2/`, outside git. The committed JSON files above carry
every number the docs quote, the command that made them and the sessions
they came from.

## Reproduce

Build a COCO-only overlay of this repository (CLAUDE.md "Environment"). On
this machine the worktree's path contains parentheses, which colcon and gz
do not quote, so Phase 3 (like Phase 2) built from a COPY:
`rsync` the checkout to `~/coco_loc_ws/src/coco-labs/`, then
`scripts/build_overlay.sh ~/coco_loc_ws`, and `export
COCO_WS=~/coco_loc_ws`. The copy's `LAB_SOURCE.txt` records the commit it
was made from; the runner writes it into each session's `meta.json`
(`source_copy_of`).

Nothing else may be running. ROS domain 66 by default.

```bash
R=~/coco_lab_runs/lab2
docs/data/lab2/lab2_run.sh fidelity $R/fidelity_1              # seed 0
FIDELITY_SEED=1 docs/data/lab2/lab2_run.sh fidelity $R/fidelity_s1
python3 docs/data/lab2/an_fidelity.py $R/fidelity_1 $R/fidelity_s1 \
    --out docs/data/lab2/fidelity/fidelity.json

docs/data/lab2/lab2_batch.sh $R kidnap:shipped:K1 kidnap:recovery:K1 \
    kidnap:recovery:K2 kidnap:shipped:K2 kidnap:shipped:K3 kidnap:recovery:K3 \
    kidnap:recovery:K4 kidnap:shipped:K4 kidnap:shipped:K5 kidnap:recovery:K5
python3 docs/data/lab2/an_kidnap.py $R --out docs/data/lab2/kidnap_ab.json

docs/data/lab2/rl_replay.sh $R/fidelity_s1/bag $R/rl1x_fidelity_s1 1
docs/data/lab2/rl_replay.sh $R/fidelity_1/bag  $R/rl1x_fidelity_1 1
python3 docs/data/lab2/an_ekf.py $R/fidelity_s1:$R/rl1x_fidelity_s1 \
    $R/fidelity_1:$R/rl1x_fidelity_1 --out docs/data/lab2/ekf_drift.json

python3 docs/data/lab2/sketch_rates.py --seeds 20 --out docs/data/lab2/sketch_rates.json
```

`an_ekf.py` and `amcl_replay.py` need the ROS environment (rosbag2_py);
`an_fidelity.py`, `an_kidnap.py` and `sketch_rates.py` need only coco_lab.

## Sessions that did not count

`kidnap_shipped_K1.void1` and `kidnap_recovery_K1.void1` ran before the
probe subscribed to AMCL's latched pose (transient local): it never saw
`/amcl_pose` at the stationary spawn and reported "AMCL never localised".
They are kept and counted as VOID, not as failures to recover; both
targets were re-run.
