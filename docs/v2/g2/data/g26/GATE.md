# G2.6 — the reliability gate: Gazebo + Nav2 on the Depot, 5 of 5

**STACK** (the full ROS 2 stack in Gazebo Harmonic, headless; never hardware). Laptop, ROS 2 Jazzy,
ROS domain 79, overlay `~/coco_lab_g2_ws`, one simulator at a time, a fresh simulator per run, never
`--fast`; raw runs (bags, logs) in `~/coco_lab_runs/g2/` (outside git), every run's legs, files'
checksums and bags' sha256 in [`gate.json`](gate.json).

**Route:** M6F.8's phone round (Fetch Rush rules 3 seed 1; the same round rules 4 draws at 22 m):
start (42.25, 8.45, 337.5°) → `obj_dock`'s pre-grasp pose → **Dock 1** → `obj_dispatch`'s pre-grasp
pose → `dispatch_drop`; `tools/m6/m6f8_nav.py --initial-pose` (AMCL seeded at the start, as M6F.8).

**Level:** derivation 2 (`tools/m6/gen_level.py --derivation 2`, [`DIAGNOSIS.md`](DIAGNOSIS.md)):
AMCL `update_min_d` / `update_min_a` 0.05 and `bad_crate` in the map. The Gazebo world is
byte-identical to M6F.8's; map sha256 `53c3bd6b953c…`, params `34024179104c…` — those of
[`coco_depot_v1_outputs_d2.json`](coco_depot_v1_outputs_d2.json).

## Before (M6F.8, derivation 1): 0 of 2

Leg 1 succeeded both times; Dock 1 aborted both times (205 START_OCCUPIED), legs 3–4 refused.

## After: 5 of 5 (`tools/g2/gate.sh … 5`) — 20 of 20 legs

| Run | obj_dock | Dock 1 | obj_dispatch | dispatch_drop | AMCL error at each leg's end (m) |
| --- | --- | --- | --- | --- | --- |
| 1 | ✓ 13.4 s | ✓ 65.2 s | ✓ 46.3 s | ✓ 32.4 s | 0.137 · 0.054 · 0.109 · 0.195 |
| 2 | ✓ 13.3 s | ✓ 69.7 s | ✓ 47.3 s | ✓ 41.5 s | 0.095 · 0.128 · 0.196 · 0.251 |
| 3 | ✓ 13.4 s | ✓ 58.5 s | ✓ 47.8 s | ✓ 37.6 s | 0.097 · 0.215 · 0.090 · 0.252 |
| 4 | ✓ 13.2 s | ✓ 59.3 s | ✓ 47.7 s | ✓ 32.1 s | 0.142 · 0.283 · 0.124 · 0.250 |
| 5 | ✓ 13.3 s | ✓ 65.0 s | ✓ 46.4 s | ✓ 32.4 s | 0.109 · 0.068 · 0.112 · 0.222 |

(sim time per leg.) AMCL still ends legs up to 0.28 m off the truth: the residual bias of DIAGNOSIS.md
is reduced, not removed, and it no longer stops the round. Five runs are not a rate.

**Also recorded:** a first form of derivation 2 (it also set `laser_min_range` and the costmaps'
`obstacle_min_range` to 0.65 m, on a reading later retracted) ran once, `gate_d2_1`: 4 of 4 legs
succeeded. It is not used: those settings discard real obstacles.
