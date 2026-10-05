# Phase 4 (Lab 3, Map) evidence — `docs/data/lab3/`

The tools and the committed results of COCO Lab Phase 4. The results are in
[`docs/RESULTS.md`](../../RESULTS.md) "COCO Lab Phase 4 — Map" and the lab
write-up is [`docs/labs/LAB3_MAP.md`](../../labs/LAB3_MAP.md).

## What was measured, on what

**No new simulator run was needed.** Lab 2 recorded, each on a FRESH
simulator, the same commanded 121 m tour twice (`fidelity_1`,
`fidelity_s1`, `docs/data/lab2/`). Phase 4 cuts those tours out of their
bags and replays them, unchanged, into every SLAM: identical scans,
identical wheel odometry, the simulator's truth kept aside for scoring.

| file | what |
|---|---|
| `make_drive.py` | cuts one drive out of a Lab 2 session: a derived rosbag2 (the drive's window only; AMCL's `map -> odom` DROPPED, everything else byte for byte, QoS copied) and `drive.json.gz` for coco_lab (per scan: stamp, 480 ranges, wheel odometry and truth interpolated at the scan stamp; truth in the map frame = world + (2, 0)) |
| `slam_replay.sh` | one backend x arm on one drive: plays the derived bag at 1.0x requested (`--clock 100`, /scan /tf /tf_static and the wheel odometry only), runs the backend online, records it with `slam_record.py`. Refuses if another SLAM or recorder is running |
| `slam_record.py` | logs every `map -> odom` the backend publishes and its last `/map` |
| `cartographer/coco_2d.lua` | Cartographer's RELEASED 2D configuration (`revo_lds.lua`, cartographer_ros 2.0.9003) with only COCO's frames, odometry on, and COCO's LiDAR range limits changed; `coco_2d_no_loop.lua` turns global SLAM off the documented way |
| `lab3_batch.sh` | every backend x arm on both drives, one at a time; an existing run directory is skipped |
| `an_backend.py` | scores one backend run: ONLINE belief at each scan (its latest `map -> odom` composed with the recorded wheel odometry) vs truth after one rigid 2D alignment; its final map moved by that alignment onto Phase 1B's ground-truth raster and scored at 0.10 m (`coco_lab.mapeval`) |
| `an_coco.py` | coco_lab's runs on the same drive: known poses, odometry, pose graph with/without loop closure, EKF-SLAM (IDEALISED landmarks synthesised from the truth), FastSLAM over 5 seeds; with the calibrated motion model and COCO's own AMCL alphas |
| `calib_icp.py` → `calib_icp_square.json`, `calib_icp_sketch.json` | the scan match's one-measurement sigma, measured on data no claim uses: Lab 2's square drive (recorded LiDAR), Lab 2's twins room (Sketch) |
| `make_replay_bundle.py` → `replay/` | one recorded drive with coco_lab's runs and the backends' runs, as a map bundle the site serves (and replays at build) |
| `sketch_counts.py` → `sketch_counts.json` | the Sketch scenes over 20 worlds each (Sketch, not the robot) |
| `an_results.py` → `results.json` | every real-drive number in one file, with each backend run's machine load |
| `lab3_common.py` | drives, the ground truth (Phase 1B's `arena_maps.py ground_truth`), ROS maps |
| `browser/report_local.json` | `lab_web/tools/browser/check.py <local vite preview> smoke mapping mapping_phone localise`, before deployment |
| `public/report.json` | the same checks against the PUBLIC site, deployed from `ee9bd65` (2026-10-05) |
| `video/` | the demo video's provenance (`cuts_public.json`, `README.md`); the file itself is a release asset, not in git |

Large artifacts — the derived bags (95 MB each), backend logs and records —
live under `~/coco_lab_runs/lab3*/`, outside git. Every number the docs quote
is in a committed JSON file here, with the command that made it.

## Cartographer on this machine

Not installed, and there is no sudo here. The RELEASED Jazzy debs are used
from a user-space prefix, the same pattern as `moveit_prefix`:

```bash
P=~/coco_labs_ws/cartographer_prefix; mkdir -p $P/debs && cd $P/debs
apt-get download ros-jazzy-cartographer ros-jazzy-cartographer-ros \
    ros-jazzy-cartographer-ros-msgs liblua5.2-0
for d in *.deb; do dpkg -x "$d" ../root; done
sha256sum *.deb > ../debs.sha256
```

Versions: `ros-jazzy-cartographer` 2.0.9004, `ros-jazzy-cartographer-ros`
2.0.9003, `liblua5.2-0` 5.2.4 (hashes in `debs.sha256`). Every shared library
resolves (`ldd`: none missing). Cartographer resolves `include` files against
its compiled-in share path, which a prefix does not have, so
`slam_replay.sh` stages the released `configuration_files/*.lua` verbatim
beside ours for each run.

## Reproduce

```bash
R=~/coco_lab_runs/lab3
# the drives (ROS environment: rosbag2_py)
python3 docs/data/lab3/make_drive.py ~/coco_lab_runs/lab2/fidelity_s1 tour $R/drives/s1_tour
python3 docs/data/lab3/make_drive.py ~/coco_lab_runs/lab2/fidelity_1  tour $R/drives/1_tour
python3 docs/data/lab3/make_drive.py ~/coco_lab_runs/lab2/fidelity_s1 square $R/drives_calib/s1_square
# every backend x arm, one at a time (ROS domain 67)
docs/data/lab3/lab3_batch.sh $R
# coco_lab on the same drives (no ROS)
cd docs/data/lab3
python3 calib_icp.py $R/drives_calib/s1_square --out calib_icp_square.json
python3 calib_icp.py --sketch --out calib_icp_sketch.json
python3 an_coco.py $R/drives/s1_tour --out $R/coco_final_s1_tour.json
python3 an_coco.py $R/drives/1_tour  --out $R/coco_final_1_tour.json
python3 sketch_counts.py --out sketch_counts.json
python3 an_results.py --drives $R/drives --round r1=$R --round r2=${R}_r2 \
    --round r3=${R}_r3 --coco s1_tour=$R/coco_final_s1_tour.json \
    --coco 1_tour=$R/coco_final_1_tour.json --out results.json
python3 make_replay_bundle.py $R/drives/s1_tour replay/s1_tour \
    ${R}_r3/backends/s1_tour_{slam_toolbox,cartographer}_{loop,noloop}
```
