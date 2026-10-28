# G2.6 — the reliability gate: Gazebo + Nav2 on the Depot, 5 of 5

**STACK** (the full ROS 2 stack in Gazebo Harmonic, headless; never hardware). Laptop, ROS 2 Jazzy,
ROS domain 79, overlay `~/coco_lab_g2_ws`, one simulator at a time, a fresh simulator per run, never
`--fast`; raw runs (bags, logs) in `~/coco_lab_runs/g2/` (outside git), every run's legs, files'
checksums and bags' sha256 in [`gate.json`](gate.json).

**Route:** M6F.8's phone round (Fetch Rush rules 3 seed 1; rules 4 drew it at the provisional 22 m
budget, not at the final 26 m — the final phone rounds' runs are below, "Race Nav2 ghosts"):
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

## Race Nav2 ghosts: the final rules-4 phone rounds (26 m), one recorded run each

`tools/g2/record_ghosts.sh` on the same setup (derivation 2, fresh simulator per run, `--initial-pose`):
one run per distinct phone round, converted by `tools/g2/make_ghost.py` into
`lab_web/public/stack/ghosts/` (truth poses, driving legs only) and indexed by `tools/g2/ghost_index.py`
(sha256 and bytes per file; `lab_web/tools/test_g2_ghosts.py` checks them). **16 of 16 legs succeeded**
(one run per round: not a rate; the 5-of-5 gate above is on M6F.8's Dock 1 round).

| Recorded seed | Seeds sharing it | Start zone | Legs | Legs (sim time) | AMCL error at each leg's end (m) | Driving | File (sha256, bytes) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | workshop | 4/4 | obj_maze_2 155.1 s · dispatch_drop 158.8 s · obj_dispatch 24.4 s · dock_1 50.0 s | 0.058 · 0.141 · 0.073 · 0.241 | 388.3 s | `r4_phone_seed1.json` (`f0f2ccd600d4…`, 110,609) |
| 2 | 2, 4, 5 | loading dock | 4/4 | obj_dock 13.4 s · dock_2 57.8 s · obj_dispatch 58.0 s · dispatch_drop 37.1 s | 0.134 · 0.023 · 0.159 · 0.197 | 166.3 s | `r4_phone_seed2.json` (`9afd627d83ac…`, 48,204) |
| 3 | 3 | workshop | 4/4 | obj_maze_2 177.8 s · dispatch_drop 178.1 s · obj_dispatch 24.4 s · dispatch_drop 31.4 s | 0.076 · 0.189 · 0.064 · 0.200 | 411.7 s | `r4_phone_seed3.json` (`227d6ee2e9b5…`, 113,084) |
| 6 | 6 | workshop | 4/4 | obj_maze_2 88.6 s · dispatch_drop 172.9 s · obj_dispatch 24.0 s · dock_2 61.9 s | 0.043 · 0.165 · 0.112 · 0.155 | 347.4 s | `r4_phone_seed6.json` (`5f548d4e31ad…`, 96,493) |
