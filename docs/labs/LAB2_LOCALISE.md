# Lab 2 — Localise

> **Try it:** <https://gauthamcodes.github.io/coco-labs/?view=localise>
> (once `lab2` is on `main`; until then, build `lab_web` locally:
> `lab_web/README.md`). Branch `lab2`; Phase 3 of `docs/ROADMAP.md`.

Labels used here, as everywhere in this repository: **(measured)** was
produced by a run in Phase 3 and is recorded with its command, sample count
and evidence path; **(derived)** was computed from recorded evidence;
**historical** is an earlier, documented result kept as it was;
**unverified** was not observed. **Sketch** results are measurements of
coco_lab's MODEL, not of the robot, and are always called Sketch.

## 1. What the lab teaches

Where am I? A robot never knows; it believes. Lab 2 puts a learner in front
of two ways to believe — a cloud of guesses and a single Gaussian — on the
SAME inputs, then breaks them in the ways COCO's real localisation has
broken.

| scene (Sketch) | what to watch | what decides it |
|---|---|---|
| Tracking a known start | the particle cloud and the EKF ellipse stay small | both filters told the start, like `/initialpose` |
| The kidnapped robot | at t = 40 s the robot is carried 9.2 m; odometry is not told | particle injection (AMCL's `recovery_alpha_*`) or not |
| Global localisation | nobody says where it starts | particles cover the room; the EKF has to start somewhere |
| Perceptual aliasing (twins room) | the room is the same room turned 180° | two poses see identical scans |
| A kidnap in COCO's arena | the arena's four near-identical bays | the real-stack A/B's target K1 |

**Controls**, each explained on the page: particle count; motion noise
(the world's odometry noise AND the filters' motion model); sensor noise
(range sigma; the filters never assume less than AMCL's 0.2 m); injection
(off as COCO ships, augmented MCL with AMCL's alphas, or a fixed share);
start (known or unknown); kidnap (on/off, time, and WHERE — click the map);
the world seed and the filter seed. Changing any of them reruns coco_lab
in the browser (Pyodide): one new Sketch world, then every filter on it.

**Views:** belief vs truth (hide the truth to see only what the robot
knows); particles weighted by their weight; the measured scan placed at the
BELIEF (endpoints off the walls means lost) or at the truth; a race (one
map per filter, synchronised); the position-error plot over time with the
0.5 m line and the kidnap marked; and predict-then-reveal, whose reveal
quotes the 20-seed Sketch count beside the one run ("one run is not a
rate").

**Exhibits — COCO's real localisation failures**, each with its label and
evidence (§3).

## 2. Modes, as labelled on screen (rule 4)

- **Sketch — coco_lab's 2D model, not the robot** (a catalog bundle) and
  **Sketch — computed in your browser by coco_lab; a model, not the
  robot** (a Pyodide rerun). Beside it, always: how close Sketch is to the
  real stack (§4.1), with the evidence path.
- The **exhibits** are **historical** real-stack results and Phase 3
  **(measured)** real-stack results, each labelled.
- Nothing in Lab 2 is presented as a live robot or a recording of one.

## 3. Claims and their evidence

| claim on the page | evidence |
|---|---|
| MCL with injection recovers the landmarks kidnap; with it off it does not; the EKF cannot | `coco_lab/test/test_localise.py::test_injection_is_what_recovers_a_kidnap`, `::test_the_ekf_cannot_recover_a_kidnap_or_start_globally`; Sketch counts `docs/data/lab2/sketch_rates.json` |
| the robot is carried 9.2 m | `coco_lab/test/test_sketch.py::test_the_kidnap_scene_carries_the_robot_across_the_room` |
| MCL converges from a uniform cloud on a map with unique features | `test_localise.py::test_mcl_converges_from_a_uniform_cloud_on_unique_features` (≥ 7 of 10 seeds) |
| the twins room is symmetric; MCL sometimes picks the twin | `test_sketch.py::test_the_twins_room_is_symmetric_to_the_ray_caster`, `test_localise.py::test_the_twins_room_aliases` |
| every filter in a race read the same world | `test_localise.py::test_the_world_never_depends_on_the_filter`, `::test_the_filters_never_read_the_truth`; `test_locbundle.py::test_every_run_reads_the_same_world` |
| the EKF is a Kalman filter | `test_kalman.py` (closed-form posteriors, Riccati fixed point) |
| Sketch's LiDAR is COCO's | `coco_lab_ros/test/test_sketch_constants.py` |
| injection off: AMCL cannot leave a confident wrong pose | historical, `docs/RESULTS.md` "What the recovery cannot fix, and why"; Phase 3 A/B (§4.3) |
| global relocalisation converged inside the ramp | historical, `docs/RESULTS.md` C2-M5.1 and `docs/data/c2m51_planner_after_recovery.txt` |
| AMCL's covariance moved the wrong way | historical, `docs/RESULTS.md` C2-M5.0, series from `docs/data/c2m5_diverged1.csv` with C2-M5.0's own definitions; the build refuses unless it reproduces the published row |
| run 15's 3.4 m | historical, `docs/RESULTS.md` "The one failure: run 15" |

Every figure an exhibit prints is checked against its source at site build
(`lab_web/tools/build_localise.py`: `_in_doc`, the covariance row check),
and every cited test must exist (`lab_web/tools/test_tools.py`).

## 4. Measured numbers, and how to reproduce them

Full tables, commands, sample counts and provenance: `docs/RESULTS.md`
"COCO Lab Phase 3 — Localise". Reproduction: `docs/data/lab2/README.md`.

### 4.1 Sketch fidelity against Gazebo (measured; 2 fresh simulators)

| | |
|---|---|
| range error at identical poses | 237 scans, 111,804 beams with a return in both: median e = Gazebo − Sketch **+0.2 mm**, p05 −19.3 mm, p95 +80.5 mm; \|e\| median 2.2 mm, p99 1.43 m |
| beams within 1 / 5 / 10 cm | 74.8 / **86.7** / 95.5 % |
| where Sketch is worst | beams that meet the bays' 3D ramps and platforms, which the 2D map does not hold |
| odometry, straight 6.4 m (×2) | Gazebo 0.000 m; Sketch (default noise, 200 seeds) median 0.21 m |
| odometry, square 15.4 m / 11 rad | Gazebo 2.30 m, 2.45 rad; Sketch median 0.29 m |
| odometry, tour 120 m / 56 rad (×2) | Gazebo 17.2 m and 2.6 m; Sketch median 5.6 and 6.1 m |

Sketch's wheels never slip; COCO's skid-steer odometry is exact along the
body and wrong at turning (its wheel yaw rate integrates to 72.5 rad where
the gyro and the truth give 56.3 / 56.2 rad). The default noise is
direction-blind, so it is wrong in both directions — that gap is the
lesson the label points to, not a defect tuned away.

### 4.2 Sketch outcome counts (measured, Sketch; 20 filter seeds)

Kidnap (9.2 m): injection off **0 / 20**, augmented **18 / 20**, fixed
5 % **13 / 20**, EKF never. Global start: 300 particles 9 / 20, 1,000
particles 15 / 20, EKF never. Twins: 13 / 20 right, 5 / 20 the twin.
Arena kidnap: off 0 / 20, augmented 2 / 20.

### 4.3 The real stack (measured)

| | result |
|---|---|
| kidnap A/B, 10 fresh simulators per arm | `recovery_alpha` 0 / 0 (shipped): **0 of 10** recovered; 0.001 / 0.1: **2 of 10** (6.5 s, 36.0 s). One-sided Fisher p = 0.237 (derived): **not resolved** |
| robot_localization (wheel pose differential + gyro), identical recorded drives | square 2.30 → **0.065 m**; tours (worst error) 21.6 → **0.21 m** and 33.6 → **0.24 m**; straights 0.000 → 0.02–0.03 m |
| the first EKF configuration (wheel twist + gyro) | straights 0.12 m: the controller's twist integrates 1.9 % more distance than its pose (measured); not adopted |
| AMCL on each odometry, offline, identical scans | in the fully mapped arena AMCL absorbs the drift: means within 0.02 m either way; the EKF lowers the tours' worst error 0.41 → 0.20 m and 0.30 → 0.22 m. Run 15's unmapped-corridor case is not tested |
| wheel topic | 1 publisher (`cmd_vel_arbiter`) in every watch sample of every session (4,344 in the A/B) |

### 4.4 The site (measured, headless Firefox, local build)

Cold in-browser run (Pyodide start + one world + three filters) 9.6 s,
warm 3.6 s; 0 console errors; no Pyodide request before the first run; no
horizontal overflow at 390 × 844; Lab 2 is loaded only when opened (Lab
1's main bundle 108 KB gzipped, Lab 2's chunk 14 KB). In-browser runs give
the SAME outcomes as CPython's but not the same bits (mean errors differ by
1e-8 to 2e-4 m), so they are labelled as browser runs. Lab 1's browser
scenarios showed no regression (warm edit 1.36–1.48 s; a share link
reproduces its exact trace).

### 4.5 Tests

`run_all_package_tests.sh` **2,772 / 0 / 0** (coco_lab 416, coco_lab_ros 86; baseline 2,691); lab_web vitest 257, tools 86; tsc, build, check_dist clean. Details: `docs/RESULTS.md` "COCO Lab Phase 3" >
"Tests".

## 5. Not verified

- **The public site.** Lab 2 is on branch `lab2`; it is not on `main`, so
  not deployed. Everything in 4.4 is the local production build.
- **A real phone.** Phone width was checked in headless Firefox only.
- **A real IMU.** Gazebo's gyro is noiseless; the robot_localization
  improvement is an upper bound.
- **robot_localization feeding AMCL live.** Only offline (4.3) and
  observe-only live; the controller's odometry TF was not changed.
- **Recovery with motion other than rotation.** The A/B rotated in place;
  driving might help or hurt injection.
- **Rates.** Every real-stack count above is a count (n ≤ 10), not a rate.

## 6. Known limitations

- Sketch is 2D. The saved map's bays are "unknown" cells and Gazebo's
  ramps and platforms are 3D, so beams near the bays disagree by up to
  metres (p99 1.43 m).
- Sketch's odometry noise is the odometry motion model's four alphas: it
  does not model skid-steer's systematic turning error, measured at about
  29 % of yaw rate on the tour.
- MCL uses a fixed particle count (AMCL adapts it with KLD sampling) and
  the textbook odometry model; its score and injection are AMCL's.
- The EKF updates on raw ranges with numerical Jacobians and a χ² gate; a
  Gaussian cannot hold two hypotheses, which is the lesson, but it also
  means its numbers say nothing about a landmark-based EKF.
- Loc bundles are 0.5–4.2 MB (f32 particles); they are fetched only when a
  scene is opened.
- The real-stack A/B used one rotation-only recovery behaviour and five
  targets; it does not establish what recovery rate injection gives.
