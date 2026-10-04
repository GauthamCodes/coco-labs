**Try it:** https://gauthamcodes.github.io/coco-labs/?view=localise

COCO Lab's second lab, **Localise**: where am I? A robot never knows; it
believes. Lab 2 puts a particle filter (MCL, with nav2_amcl's likelihood
field, score and injection) and an EKF side by side on the SAME inputs,
then breaks them the ways COCO's real localisation has broken. Every run
is computed by `coco_lab` (Python, in your browser via Pyodide); the page
never filters. Write-up, every claim's evidence and the limitations:
[`docs/labs/LAB2_LOCALISE.md`](https://github.com/GauthamCodes/coco-labs/blob/lab2-v1.0/docs/labs/LAB2_LOCALISE.md).

### In the lab

- **Sketch, labelled as a model.** coco_lab's 2D differential-drive and
  ray-cast LiDAR world, with its measured fidelity against Gazebo shown
  beside the mode.
- **Five scenes:** tracking a known start, the kidnapped robot, global
  localisation, perceptual aliasing (the twins room), a kidnap in COCO's
  arena.
- **Controls:** particle count, motion and sensor noise, injection (off as
  COCO ships, augmented MCL with AMCL's alphas, or a fixed share), known or
  unknown start, the kidnap's time and target (click the map), seeds. Each
  change reruns coco_lab in the browser.
- **Views:** belief vs truth (hide the truth to see only what the robot
  knows), weighted particles, the scan placed at the belief or the truth, a
  race (one map per filter), the error plot, and predict-then-reveal, whose
  reveal quotes the 20-seed Sketch count beside the one run.
- **Exhibits: four times COCO's real localisation failed**, each labelled
  and cited, with Phase 3's real-stack results beside them.

### Measured (details in `docs/RESULTS.md` "COCO Lab Phase 3")

| | result |
|---|---|
| Sketch LiDAR vs Gazebo, 237 identical poses | **86.7 %** of 111,804 beams within 5 cm; median \|error\| 2.2 mm |
| Sketch odometry vs Gazebo | exact on straights (Gazebo 0.000 m); wrong on turns (skid-steer) |
| Sketch kidnap, 20 filter seeds | injection off **0 / 20**, augmented **18 / 20**, EKF never |
| real stack: kidnap A/B, 10 fresh simulators per arm | AMCL as shipped **0 of 10** recovered; `recovery_alpha` 0.001 / 0.1 **2 of 10**. One-sided Fisher p = 0.237 (derived): **not resolved** |
| real stack: robot_localization (wheel pose differential + gyro), identical recorded drives | square 2.30 → **0.065 m**; 120 m tours' worst error 21.6 → **0.21 m** and 33.6 → **0.24 m** (upper bound: noiseless sim gyro) |
| AMCL on each odometry, offline, identical scans | in the fully mapped arena AMCL absorbs the drift (means within 0.02 m); the EKF lowers the tours' worst error 0.41 → 0.20 m and 0.30 → 0.22 m |
| wheel topic | 1 publisher (`cmd_vel_arbiter`) in every watch sample (4,344 in the A/B) |

**On the public site** (headless Firefox 157, deployed from `4405065`): 0
console errors; cold in-browser run 11.35 s, warm 3.05 s; Pyodide gives
the same outcomes as CPython (not the same bits, so browser runs are
labelled); no horizontal scroll at 390 × 844; Lab 1's smoke 11 of 11.

### Tests

`run_all_package_tests.sh` **2,772 passed, 0 failed, 0 skipped** (coco_lab
416, coco_lab_ros 86; the Phase 2 baseline was 2,691); lab_web vitest
**257**, tools **86**; `tsc`, build and `check_dist` clean. CI on `main`
at `4405065` (the code): `CI` (run 37219611482, 2,273 tests) and `Lab`
with the Pages deploy (run 37219611486) green. At this tag's commit
`4b675c1` (docs only on top): `Lab` with the deploy green (run
37221184498); `CI` run 37221184465 failed its first attempt on
`gazebo_models` `test_the_relay_output_is_restamped_and_unaltered`
(`assert 9 >= 10`, the load-sensitive test recorded in `CLAUDE.md`) and
passed on re-run.

### Known limitations

- **No real-phone test.** Phone width was checked in headless Firefox
  only.
- **No real IMU.** Gazebo's gyro is noiseless; the robot_localization
  improvement is an upper bound.
- **No live robot_localization → AMCL integration.** Measured offline and
  observe-only live; the controller's odometry TF was not changed, and the
  mission is untouched.
- **Run 15 not reproduced.** Its unmapped-corridor case is not tested; the
  EKF result is measured on Phase 3 drives in the mapped arena.
- **Small real-stack samples.** Every real-stack count is n ≤ 10: counts,
  not rates. The A/B used one rotation-only recovery behaviour and five
  targets.
- Sketch is 2D: beams near the bays' 3D ramps and platforms disagree by up
  to metres (p99 1.43 m). Its odometry noise does not model skid-steer's
  turning error.
- Measured in headless Firefox on one machine; a headed browser, Safari and
  Chrome are not measured. The first run pays Pyodide's start-up.

### The video

`coco_lab2_demo.mp4`: 91.76 s, 1120 × 920, H.264, recorded **from the
public site** by `lab_web/tools/browser/record_lab2_demo.py`. It captures
the headless browser's viewport only, at real pacing. **One cut:** the
one-time Pyodide start-up and a warm-up run (10.56 s) happened before
recording began. The captions were added by the recorder; they are not
part of the site. sha256 `b13aa1feb3f90cc4ff1a25ad2111aeef7c23c8ce47e541cbff15ca687429b648`.
