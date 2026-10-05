**Try it:** https://gauthamcodes.github.io/coco-labs/?view=map

COCO Lab's third lab, **Map**: where are the walls? A robot that knew where
it was could simply draw what its LiDAR sees; it cannot know where it is
without a map. Lab 3 walks from occupancy mapping with known poses to SLAM —
EKF-SLAM, FastSLAM and a pose graph — on the SAME world each time, then puts
COCO's real recorded drive through slam_toolbox and Cartographer. Every run
is computed by `coco_lab` (Python, in your browser via Pyodide); the page
never maps. Write-up, every claim's evidence and the limitations:
[`docs/labs/LAB3_MAP.md`](https://github.com/GauthamCodes/coco-labs/blob/lab3-v1.0/docs/labs/LAB3_MAP.md).

### In the lab

- **Sketch, labelled as a model**, with Sketch's measured fidelity against
  Gazebo beside it.
- **Six runs on one world:** known poses, odometry only, EKF-SLAM (on an
  IDEALISED landmark sensor — labelled wherever it appears), FastSLAM, the
  pose graph with and without loop closure.
- **Scenes:** closing the loop (a ring room), the featureless corridor,
  landmarks vs scans.
- **Drive it yourself:** click waypoints; coco_lab's own A* (Lab 1) plans
  the way round walls; change the noise, particles and seeds.
- **Views:** the map as it was at each moment, the final map against the
  truth (right / not there / missed), the LiDAR at the belief, particles,
  landmarks with 2σ ellipses, the pose graph and its loop closures, compare
  (one map per algorithm), predict-then-reveal on loop closure.
- **The challenge — map the arena:** your drive, a fixed seed and noise,
  score = round(100 x F1) of the map, computed by coco_lab, with the best
  map your drive allows beside it.
- **Replay:** COCO's real 121 m tour, recorded on the real stack in Gazebo,
  with slam_toolbox's, Cartographer's and coco_lab's maps on identical scans.

### Measured (details in `docs/RESULTS.md` "COCO Lab Phase 4")

Final trajectory error (ATE, after one rigid 2D alignment) and map F1 at
0.10 m against the ground-truth raster, on COCO's two recorded 121 m tours
(`s1_tour` / `1_tour`) — all (measured), `docs/data/lab3/results.json`:

| run | `s1_tour` ATE / F1 | `1_tour` ATE / F1 |
|---|---|---|
| wheel odometry alone | 6.281 m / — | 7.317 m / — |
| coco_lab known poses (the ceiling) | 0.000 m / 0.937 | 0.000 m / 0.938 |
| coco_lab pose graph | 0.267 m / 0.664 | 0.758 m / 0.220 |
| coco_lab pose graph, loop closure off | 0.443 m / 0.492 | 0.708 m / 0.265 |
| coco_lab FastSLAM, calibrated model, seeds 0–4 | 0.120–0.236 m / 0.636–0.810 | 0.087–0.533 m / 0.382–0.848 |
| coco_lab EKF-SLAM, IDEALISED landmarks | 0.321 m / 0.655 | 0.269 m / 0.721 |
| slam_toolbox, project config (3 rounds) | 0.103–0.104 m / 0.933 | 0.793–0.794 m / 0.399–0.400 |
| slam_toolbox, loop closing off (3 rounds) | 0.076–0.078 m / 0.923–0.928 | 0.107 m / 0.897 |
| Cartographer, released 2D config (2 rounds) | 0.813–0.814 m / 0.192–0.193 | 0.665–0.687 m / 0.170–0.180 |
| Cartographer, global SLAM off (2 rounds) | 0.059–0.063 m / 0.882–0.889 | 0.044–0.075 m / 0.909–0.915 |

- **Loop closure hurt both real backends here** — reproduced across rounds
  and loads, **not attributed**. coco_lab's 13 loop closures were all TRUE
  (within 2 cm / 0.011 rad of the true relative pose).
- **The motion model decides FastSLAM**: with COCO's AMCL alphas it lost
  both tours on every seed (0.885–1.300 m).
- Two drives and five seeds are a spread, not a rate.

### Tests

`scripts/run_all_package_tests.sh`: **2,848 passed, 0 failed, 0 skipped**
(coco_lab 416 → 492). `lab_web`: vitest **275**, tools pytest **95**; `tsc`,
`vite build` and `check_dist` clean.

### Known limitations

- **No physical robot.** The real-drive results are the real stack in
  Gazebo (noiseless LiDAR).
- **Why the backends' loop closure hurt is not attributed.** Reproduced in
  three rounds; one hypothesis (odometry) tested and rejected.
- **Small samples:** two drives, five FastSLAM seeds; the Sketch counts are
  20 worlds per scene and are Sketch.
- EKF-SLAM's landmark sensor is idealised; on the recorded drive its
  observations are synthesised from the truth.
- coco_lab's SLAMs use 60 of COCO's 480 beams; the backends use 480.
- Measured in headless Firefox on one machine; a real phone, Safari and
  Chrome are not measured.

### The video

`coco_lab3_demo.mp4` (attached): recorded from the public site after
deployment, headless Firefox, viewport only, 122.3 s, 0 console errors.
Captions are added by the recorder. Three cuts, each listed with its length
in `docs/data/lab3/video/cuts_public.json`: the one-time Pyodide start-up
and a warm-up run (19.41 s), coco_lab rerunning the corridor world
(14.32 s), and mapping the challenge drive (3.44 s). sha256
`0d9648909acb6365bb29856489062c339ef473a9203db7c6d69f7f03f19c4e66`.
