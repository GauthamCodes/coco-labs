# R6.B1 · Fidelity knobs

Branch `v2/r6-b1` (from main `f440e7e`). Evidence class: MODEL. Every knob is deterministic and seeded, and off
unless set.

## What existed (reused)

`arena.range_sigma` (Gaussian LiDAR range noise), `arena.slip=on` (the body turns `SLIP_TURN` = 56.2/72.5 of the
commanded turn: Lab 2's fit), `arena.odom_alphas` (odometry noise), the robot's acceleration limits (constants in
its `limits`), all set by `config` inputs — so they are in every run's input log.

## New knobs (`coco_lab/coco_lab/arena.py`, `config` keys)

| knob | what it does | range |
| --- | --- | --- |
| `arena.lidar_dropout=p` | each beam independently returns no echo, from its own seeded stream | 0 ≤ p < 1 |
| `arena.odom_preset=name` | wheel odometry over/under-reports the body's motion by **measured** factors (below) | a name |
| `arena.cmd_latency=k` | the drive command reaches the wheels k ticks late (a FIFO); **STOP still acts at once** and empties it | 0–50 ticks |
| `arena.linear_accel=a`, `arena.angular_accel=a` | override the robot's acceleration limits | 0.05–20 |

Odometry presets, each cited:

| preset | distance x | turn x | source |
| --- | --- | --- | --- |
| `stack_uncalibrated` | 0.9909 | 1.2029 | G2.9 derivation-4 gate, 40 recorded Gazebo + Nav2 runs, installed `wheel_separation_multiplier` 1.10 — `docs/v2/g2/data/g29/odom/turn_scale_d4_gate.json` |
| `stack_calibrated` | 0.9913 | 0.9986 | derivation 5, after the calibration (1.323) — `turn_scale_d5_gate.json` |
| `lab2_fit` | — | body turns 0.7752 of the command | today's `arena.slip=on` (`SLIP_TURN`, Lab 2's fit) |

## In experiments

A spec field `fidelity` (`coco_lab.experiments.fidelity_config`; control and localisation — the full-task family
runs whole game rounds and planning has no motion, so they refuse knobs in words). Given, it enters the spec (its
id changes), every run's descriptor (and so its chain) as tick-0 `arena.*` config inputs, the summary
(`fidelity`) and every row of `results.csv` (a `fidelity` column). Not given: every spec, id, chain, summary and CSV
is exactly as before.

## Off = byte-identical (the stop condition)

`state_v2.snapshot` hashes every Arena attribute (hash versions 2 and 3), so each knob's state is created only when
it is configured (as `plan_clearance` already is); the v1 byte layout appends a `fidelity` block only when a knob
is set. Checked: `test_numerics_v3` (20 v3 goldens), `test_state_hash_v2`, `test_golden_traces` (v1), unchanged —
50 golden/hash tests pass before and after; determinism digests unchanged (see the PR).

## Tests and evidence

- `coco_lab/test/test_r6_fidelity.py` (10): off = as before and on = deterministic; dropout removes ~p of echoes;
  latency delays the wheels and STOP still wins at once; acceleration sets the ramp (0.05 m/s after one tick at
  0.5 m/s²); the uncalibrated preset over-reports a pure turn by exactly 1.2029; out-of-range knobs are refused.
- `coco_lab/test/test_experiments.py` (+7): the knob changes the spec id and every chain, and shows in the
  summary and every CSV row; bad knobs refused in words; planning has no knobs.
- `lab_web/test/r6_fidelity.test.ts`: the builder's spec gains `fidelity` only when a knob is set; the words.
- Browser (`lab_web/tools/r6/fidelity_e2e.mjs`): Learn's note → its experiment link opens the Workbench with the
  knob in the builder → 20 runs → "Fidelity knobs on: command latency 5 ticks" on the results → a run opened in
  Compare names the knob. Chromium **PASS**; Firefox: the same up to the results note, its 20 runs not finished
  within 10 min while the laptop ran the MCL reference on 10 cores (rerun pending) — [data/b1/](data/b1/).

## Workbench, Compare, Learn

Builder: a "Fidelity" fieldset (control, localisation). Results: a note naming the knobs (these runs are not
comparable with runs without them). Compare: a replayed run names its knobs. Learn: a note under the course's
modules, with a one-click experiment (two controllers, commands 0.5 s late).
