# Lab 3 — Map

> **Try it:** <https://gauthamcodes.github.io/coco-labs/?view=map>
> PLACEHOLDER-DEPLOY. Phase 4 of `docs/ROADMAP.md`.

Labels used here, as everywhere in this repository: **(measured)** was
produced by a run in Phase 4 and is recorded with its command, sample count
and evidence path; **(derived)** was computed from recorded evidence;
**historical** is an earlier, documented result kept as it was;
**unverified** was not observed. **Sketch** results are measurements of
coco_lab's MODEL, not of the robot, and are always called Sketch.

## 1. What the lab teaches

Where are the walls? A robot that knew where it was could simply draw what
its LiDAR sees. It does not know where it is — and it cannot find out without
a map. Lab 3 walks from the easy half of that problem to the whole of it, on
the SAME world each time:

| run (coco_lab) | what it is | what it shows |
|---|---|---|
| Known poses | log-odds occupancy mapping at the TRUE poses | the map localisation-solved would give: the ceiling |
| Odometry only | the same mapping at the dead-reckoned poses | the bent, smeared map a robot that trusts its wheels draws — why SLAM exists |
| EKF-SLAM | one Gaussian over the pose and every landmark, on an **IDEALISED** landmark sensor | correlations: re-seeing a landmark corrects the robot AND the others |
| FastSLAM | a particle filter over trajectories, each particle with its own grid map (Rao-Blackwellised) | the past is revised by choosing which history survives; the motion model decides it |
| Pose graph | scan matching between poses, loop closure, a Gauss-Newton optimiser over the whole graph | closing a loop pulls the whole map straight — when the loop is recognised |
| Pose graph, loop closure off | the same, never closing | the loop-closure effect, isolated |

| scene (Sketch) | what to watch |
|---|---|
| Closing the loop (a ring room) | the pose graph with and without loop closure; "new world" shows it does not always recognise the start |
| The featureless corridor | 18 m of smooth wall: every SLAM drifts along it; scans pin the robot sideways only |
| Landmarks vs scans (Lab 2's room) | the idealised landmark EKF against the LiDAR SLAMs, on one drive |
| Map the arena (challenge) | the learner's own drive of COCO's arena, scored |
| COCO's real tour (Replay) | a drive recorded on the real stack in Gazebo, replayed into slam_toolbox, Cartographer and coco_lab |

**Controls:** click waypoints to drive (coco_lab's own A* plans the way round
walls); odometry noise; FastSLAM particles; world and FastSLAM seeds; which
run's map and belief to look at; compare (one map per algorithm); show the
truth, the map at that moment, the final map against the truth, the LiDAR at
the belief, particles, landmarks with 2σ ellipses, the pose graph and its
loop closures, the final trajectory. Every rerun is coco_lab in the browser
(Pyodide): one new Sketch world, every algorithm on it.

## 2. Modes, as labelled on screen (rule 4)

- **Sketch — coco_lab's 2D model, not the robot** (a catalog bundle) and
  **Sketch — computed in your browser by coco_lab; a model, not the robot**
  (a Pyodide rerun), with Sketch's measured fidelity against Gazebo beside it
  (Lab 2's measurement: the same model).
- **Replay — a recorded run of the real stack in Gazebo**: the recorded
  tour, with the bag's hash and sim-time range in its provenance.
- The landmark sensor is labelled **IDEALISED** wherever EKF-SLAM appears.
  On the recorded drive its observations are SYNTHESISED from the
  simulator's truth.
- Nothing in Lab 3 is presented as a live robot.

## 3. Claims and their evidence

| claim on the page | evidence |
|---|---|
| log-odds mapping with the true poses draws the walls where they are | `coco_lab/test/test_occgrid.py::test_known_poses_on_a_noise_free_world_reproduce_the_walls`; the update itself `::test_one_beam_adds_l_occ_at_its_end_and_l_free_on_the_way`, `::test_without_the_clamp_the_order_of_scans_does_not_matter` |
| odometry-only mapping is the same mapping with other poses | `test_occgrid.py::test_odometry_mapping_is_the_same_mapping_with_other_poses`, `::test_dead_reckoning_is_exact_composition` |
| EKF-SLAM is a Kalman filter: in the linear case it IS the exact Gaussian posterior | `test_ekfslam.py::test_the_linear_case_equals_the_exact_gaussian_posterior`, `::test_the_update_equals_the_generic_kalman_update`, `::test_prediction_moves_the_pose_and_leaves_the_landmarks_alone` |
| a landmark's uncertainty only shrinks | `test_ekfslam.py::test_landmark_uncertainty_never_grows` |
| the landmark sensor is idealised (identity known, line of sight) | `test_ekfslam.py::test_the_sensor_is_idealised_known_ids_and_line_of_sight`; labelled on the page (`lab_web/test/mapview.test.ts`) |
| FastSLAM: seeded, weights normalised, resampling only below the Neff threshold, the final trajectory is one particle's ancestry | `test_fastslam.py` (all), with `::test_the_final_trajectory_is_one_particles_ancestry` |
| the SLAMs never read the truth | `test_fastslam.py::test_the_slams_cannot_read_the_truth` |
| the optimiser solves known graphs exactly; chi-squared never rises; CG with the chain preconditioner equals a dense solve | `test_posegraph.py::test_a_consistent_graph_is_solved_exactly_from_a_bad_start`, `::test_the_linear_case_is_the_least_squares_solution`, `::test_chi2_never_rises_on_noisy_squares`, `::test_pcg_solves_a_chain_with_loops_like_a_dense_solve`, `::test_the_jacobians_are_the_errors_derivatives` |
| a corridor gives the scan match nothing along its axis | `test_posegraph.py::test_a_corridor_constrains_nothing_along_its_axis`, `test_map_teaching.py::test_a_scan_mid_corridor_cannot_see_how_far_along_it_is`, `::test_the_corridor_is_two_straight_featureless_walls` |
| loop closure usually closes the loop room, and when it does it helps | `test_posegraph.py::test_loop_closure_usually_closes_the_loop_room` (20 worlds); counts `docs/data/lab3/sketch_counts.json` |
| the challenge score is round(100 x F1), and F1 is defined as stated | `test_mapeval.py` (all); `lab_web/test/mapview.test.ts` "the challenge score is the documented computation" |
| a click behind a wall is driven round it; one inside a wall is refused | `test_map_teaching.py::test_a_click_behind_a_wall_is_driven_around_it`, `::test_an_unreachable_click_is_refused`; `lab_web/tools/test_map_glue.py` |
| every map bundle the site serves was replayed and re-scored byte for byte | `slambundle.replay_check` at site build; `lab_web/tools/test_tools.py::test_the_catalog_serves_lab3_validated_and_replayed` |
| the browser draws, coco_lab maps | `lab_web/tools/test_tools.py::test_lab_web_src_has_no_search_implementation` (patterns for occupancy mapping, scan matching, graph optimisation, mapping metrics) |
| the real-drive numbers | (measured) `docs/data/lab3/results.json`, `docs/RESULTS.md` "COCO Lab Phase 4" |

## 4. Measured numbers, and how to reproduce them

Full tables, commands, sample counts and provenance: `docs/RESULTS.md`
"COCO Lab Phase 4 — Map". Reproduction: `docs/data/lab3/README.md`. Every
real-drive number is in `docs/data/lab3/results.json`.

### 4.1 The real backends on identical recorded drives (measured)

Two tours of the arena, each recorded on a fresh simulator in Lab 2, replayed
unchanged into each backend (1.0x requested, online), loop closure on and
off. Scored by coco_lab's definitions: online trajectory error after one
rigid alignment; the final map against Phase 1B's ground-truth raster at
0.10 m (map F1).

| backend | drive | round r1: ATE / F1 (load) | round r2: ATE / F1 (load) | round sync: ATE / F1 (load) |
|---|---|---|---|---|
| slam_toolbox (project config) | `s1_tour` | 0.103 m / 0.933 (6.06) | 0.104 m / 0.933 (19.67) | 0.104 m / 0.933 (5.24) |
| slam_toolbox (project config) | `1_tour` | 0.793 m / 0.400 (24.73) | 0.794 m / 0.399 (30.62) | 0.793 m / 0.400 (1.53) |
| slam_toolbox, loop closing off | `s1_tour` | 0.078 m / 0.928 (7.76) | 0.076 m / 0.923 (32.63) | 0.078 m / 0.928 (1.59) |
| slam_toolbox, loop closing off | `1_tour` | 0.107 m / 0.897 (1.79) | 0.107 m / 0.897 (24.20) | 0.107 m / 0.897 (3.78) |
| Cartographer (released 2D config) | `s1_tour` | 0.814 m / 0.192 (13.68) | 0.813 m / 0.193 (9.36) | — |
| Cartographer (released 2D config) | `1_tour` | 0.687 m / 0.170 (1.64) | 0.665 m / 0.180 (37.48) | — |
| Cartographer, global SLAM off | `s1_tour` | 0.063 m / 0.882 (26.19) | 0.059 m / 0.889 (2.05) | — |
| Cartographer, global SLAM off | `1_tour` | 0.044 m / 0.915 (2.42) | 0.075 m / 0.909 (18.35) | — |

ATE = the backend's ONLINE belief at every scan (its latest `map -> odom`
composed with the recorded wheel odometry) after one rigid 2D alignment;
F1 = its final map, moved by that alignment, against the ground truth at
0.10 m. In brackets: the 1-minute load average at the end of the run (other
sessions' simulators shared the machine).

- **The numbers do not depend on the load**: two async rounds and slam_toolbox's
  synchronous node (every scan processed) agree to about three decimals at
  loads from 1.5 to 37.
- **Loop closure HURT here.** Cartographer's released configuration with
  global SLAM on drew sheared, rotated maps on both tours (F1 0.17–0.19);
  with global SLAM off it mapped them well (F1 0.88–0.92, ATE 0.04–0.08 m).
  slam_toolbox's loop closing was harmless on `s1_tour` and wrecked
  `1_tour` (F1 0.40 against 0.90 off), identically in all three rounds.
  **Measured and reproduced; not attributed**: their pose graphs are not
  recorded, so their closures cannot be checked against the truth the way
  coco_lab's were (§4.2).
- **One hypothesis tested and REJECTED** (a diagnostic, one run, not a comparison arm): that Cartographer's global optimisation is pulled off by the skid-steer wheel odometry. With odometry OFF and global SLAM on (`cartographer/coco_2d_loop_noodom.lua`) the `s1_tour` map was worse still: ATE 3.371 m, F1 0.117 (load 2.4; `diagnostic_cartographer_loop_noodom.json`).
- Wheel odometry alone: 6.281 m (`s1_tour`) and 7.317 m (`1_tour`), aligned.
- The page's Replay carries round 1's `s1_tour` runs and scores them by the
  same code at the drive's 627 UPDATE rows (where coco_lab's runs have a
  pose) rather than at all 4,405 scans, so its trajectory errors differ in
  the second decimal (slam_toolbox 0.096 m there, 0.103 m here); the maps
  and F1 are the same computation.

### 4.2 coco_lab on the same drives (measured)

| run | `s1_tour` ATE / F1 | `1_tour` ATE / F1 |
|---|---|---|
| known poses (the ceiling) | 0.000 m / 0.937 | 0.000 m / 0.938 |
| odometry only | 6.260 m / 0.101 | 7.126 m / 0.072 |
| pose graph | 0.267 m / 0.664 | 0.758 m / 0.220 |
| pose graph, loop closure off | 0.443 m / 0.492 | 0.708 m / 0.265 |
| FastSLAM, calibrated motion model, 5 seeds | 0.120–0.236 m / 0.636–0.810 | 0.087–0.533 m / 0.382–0.848 |
| FastSLAM, COCO's AMCL alphas, 5 seeds | 0.885–1.034 m / 0.188–0.410 | 0.944–1.300 m / 0.110–0.334 |
| EKF-SLAM, IDEALISED landmarks | 0.321 m / 0.655 | 0.269 m / 0.721 |

coco_lab's pose graph closed 9 loops on `s1_tour` and 4 on `1_tour`; all 13
were TRUE (within 2 cm and 0.011 rad of the true relative pose,
`loops.json`). On `1_tour` it never recognised its start, so the big loop
stayed open.

### 4.3 Sketch over 20 worlds per scene (measured, Sketch)

`docs/data/lab3/sketch_counts.py` at `d9cffb9` (clean): each scene's drive and noise (x3), world seeds 0–19, FastSLAM seed 0. Median [p10–p90] final trajectory error (m) and map F1.

| run | loop room | corridor | landmarks room |
|---|---|---|---|
| known poses | 0.00 [0.00–0.00] m · F1 0.99 | 0.00 [0.00–0.00] m · F1 0.97 | 0.00 [0.00–0.00] m · F1 0.99 |
| odometry only | 1.68 [1.11–3.10] m · F1 0.33 | 3.08 [1.94–5.16] m · F1 0.37 | 1.73 [1.07–2.81] m · F1 0.30 |
| EKF-SLAM (idealised) | 0.29 [0.12–0.39] m · F1 0.79 | 1.10 [0.53–2.74] m · F1 0.58 | 0.09 [0.05–0.19] m · F1 0.96 |
| FastSLAM (20 particles) | 0.18 [0.12–0.28] m · F1 0.88 | 1.70 [1.34–1.94] m · F1 0.48 | 0.15 [0.11–0.18] m · F1 0.92 |
| pose graph | 0.22 [0.12–0.37] m · F1 0.81 | 0.90 [0.49–1.59] m · F1 0.42 | 0.11 [0.06–0.28] m · F1 0.92 |
| pose graph, loop closure off | 0.75 [0.49–0.99] m · F1 0.47 | 0.99 [0.62–1.59] m · F1 0.38 | 0.75 [0.39–1.33] m · F1 0.47 |

Loop closure found / lowered the pose graph's final error: loop room **19 / 19** of 20; landmarks room **20 / 19**; corridor **14 / 6** — in the corridor a closure at the end does not tell the graph how long the corridor was.

### 4.4 The site (measured, headless Firefox)

Local production build (`vite preview`, headless Firefox 157, load 2.1–2.3;
`docs/data/lab3/browser/report_local.json`):

| | |
|---|---|
| console errors | **0** (Lab 3 desktop and phone, Lab 2, Lab 1's smoke) |
| first coco_lab run (Pyodide start-up + the loop room's world + 6 algorithms) | 13.9 s |
| warm runs | a new world 8.1 s; a clicked one-waypoint drive 3.1 s; the challenge 3.1 s |
| Pyodide vs CPython | the same outcomes, not the same bits (final ATEs differ in the 6th decimal) — browser runs are labelled as such |
| before the first run | no Pyodide request |
| phone, 390 × 844 | no horizontal overflow on Sketch, the challenge or Replay |
| Lab 3's chunk | loaded only when opened (`MapLab-*.js`, 15 KB gzipped) |
| regressions | Lab 2: cold 8.8 s, warm 3.1 s, same outcomes as CPython, 4 exhibits; Lab 1's smoke 11 of 11 |

PLACEHOLDER-PUBLIC

### 4.5 Tests

`COCO_WS=~/coco_map_ws ROS_DOMAIN_ID=77 scripts/run_all_package_tests.sh`
(a copy overlay of 2c0ad65; the worktree's path has parentheses) on a clean
graph, load 1.4–2.8: **2,848 passed, 0 failed, 0 skipped** (Phase 3 closed
at 2,772).

| package | Phase 3 | now |
|---|---|---|
| coco_config | 93 | 93 |
| coco_sim | 280 | 280 |
| coco_mission | 344 | 344 |
| coco_web | 857 | 857 |
| gazebo_models | 229 | 229 |
| coco_rl | 241 | 241 |
| coco_perception | 139 | 139 |
| coco_moveit_config | 12 | 12 |
| custom_teleop | 75 | 75 |
| coco_lab | 416 | **492** |
| coco_lab_ros | 86 | 86 |

`lab_web`: vitest 257 → **275**; tools pytest 86 → **95** (103 s); `tsc`,
`vite build` and `check_dist` clean. The first full run of the phase (at
d41f350) failed one coco_lab test, `test_flake8` (three findings), fixed in
60e8fbf. Two `lab_web` catalog tests that check only Lab 1 now build the
catalog without Lab 3's block (`with_map=False`), which its own test builds
and checks — no assertion removed.

## 5. Not verified

- **A real robot.** Everything real here was recorded on the real stack in
  GAZEBO; no physical robot exists. Gazebo's LiDAR has no noise, which is
  why its calibrated scan sigma (3.5 mm) is half Sketch's.
- **Why the backends' loop closure hurt.** Measured, reproduced in more than
  one round, NOT attributed (§4.1). coco_lab's closures were checked against
  the truth; the backends' were not, because their pose graphs are not
  recorded.
- **Rates.** Two drives, five FastSLAM seeds: spreads and counts, not
  rates. The Sketch counts are 20 worlds per scene and are Sketch.
- **A real phone, Safari, Chrome.** Phone width was checked in headless
  Firefox only.
- **Real-time slam_toolbox under a quiet machine.** Every async run ran with
  other sessions' simulators loading the machine (load averages are in
  `results.json`); the synchronous round removes load from the result.

## 6. Known limitations

- Sketch is 2D: the arena's ramps and platforms are 3D in Gazebo and walls
  in Sketch; Sketch's wheels never slip.
- EKF-SLAM's landmark sensor is idealised (known identity, no false or
  missed detections); on the recorded drive its observations are
  synthesised from the truth.
- FastSLAM samples from odometry only (GMapping's improved proposal is not
  reproduced; a greedy version was tried and removed), uses a fixed
  particle count, and copies a whole grid on resampling: it is the slowest
  run in the browser.
- The pose graph's front end matches each scan to the previous one (no
  submaps), loop closure needs ICP to converge from the belief, so a robot
  that is lost by more than about the matcher's window never recognises
  where it has been (the loop room: 1 world of 20 never closed its loop, Sketch).
- coco_lab's SLAMs use 60 of COCO's 480 beams; the ROS backends use all
  480. The comparison holds the scans, odometry and drive fixed, not the
  beam count.
- Maps are scored against Phase 1B's ground-truth raster at LiDAR height;
  the bays' 3D ramps make even the known-pose map's F1 0.937, not 1.
- Map bundles are 0.5–0.7 MB (Sketch) and larger for the recorded tour;
  each is fetched only when its scene is opened.

