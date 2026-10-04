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

PENDING — filled from `docs/RESULTS.md` "COCO Lab Phase 3 — Localise" at
the end of the session.

## 5. Not verified

PENDING

## 6. Known limitations

PENDING
