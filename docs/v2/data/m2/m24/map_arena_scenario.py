"""
Lab 3's map-the-arena scenario, in Lab 3's engine and in the Arena (M2.4; MODEL).

    python3 docs/v2/data/m2/m24/map_arena_scenario.py \
        --out docs/v2/data/m2/m24/map_arena_scenario.json

The scenario (coco_lab.map_teaching.arena_scenario): COCO's arena at 0.10 m,
start (0, 0, 0), the default loop of six waypoints round the north half,
seed 21, Sketch's default noise (odometry alphas 0.02, range sigma 0.02 m).

- **Lab 3's engine**: exactly what the site's challenge bundle computes
  (lab_web/tools/build_map.py challenge_entry): mapworld.from_sketch ->
  slambundle.SlamBundle.compute, scored by slambundle.score_trace (ATE of
  the final trajectory, aligned for SLAMs; F1 of the final map).
- **The Arena (new engine)**: the same start, waypoints (as successive
  goals), seed and noise, through coco_lab.arena + the map subsystem
  (coco_lab.map_arena): occupancy with true poses ('known'), with dead
  reckoning ('odometry'), FastSLAM (20 particles), pose graph (loop closure
  on). Scored by ArenaMapper.scores() (ATE, aligned for SLAMs; F1 of the
  map at 0.10 m, NOT moved by the alignment).

The two engines do not drive the same path: Sketch follows straight lines
between the clicks by the TRUE pose; the Arena plans each leg on the
inflated grid and drives it by its belief. The numbers are compared side
by side, not expected to be equal.
"""

import argparse
import json
import os
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.join(REPO, 'lab_web', 'tools'))

from coco_lab import bundle, map_teaching, mapworld, slambundle  # noqa: E402
from coco_lab.arena import Arena, InputEvent  # noqa: E402
import coco_lab.loc_arena  # noqa: E402,F401
import coco_lab.map_arena  # noqa: E402,F401
from coco_lab.sketch import SketchMap  # noqa: E402
import build_localise  # noqa: E402

RUNS = {'known': ('occupancy', 'truth'), 'odometry': ('occupancy', 'odometry'),
        'fastslam': ('fastslam', None), 'pose_graph': ('pose_graph', None)}


def lab3():
    m = build_localise.arena_map()
    base = map_teaching.arena_scenario()
    scale = map_teaching.ARENA_NOISE_SCALE
    sc = map_teaching.scenario_for(base, SketchMap(m), base.route, scale, base.seed)
    world = mapworld.from_sketch(m, sc, mapworld.LandmarkSpec(min_separation=2.0, max_count=64))
    prov = bundle.make_provenance('sketch', seed=sc.seed, tool='m24 scenario')
    sb = slambundle.SlamBundle.compute(m, world, map_teaching.run_specs(scale=scale, ids=tuple(RUNS)), prov)
    out = {}
    for rid, tr in sb.runs:
        s = tr.summary
        out[rid] = {'ate_final_rmse_m': s['ate_final']['rmse'], 'f1': s['map']['f1'],
                    'precision': s['map']['precision'], 'recall': s['map']['recall'],
                    'updates': len(tr.columns['row'])}
    return out, world.status


def arena(spec, run_id):
    alg, poses = RUNS[run_id]
    a = Arena(spec, map_teaching.ARENA_SEED)
    route = list(map_teaching.ARENA_ROUTE)
    first = [InputEvent(0, 'config', choice='arena.range_sigma=0.02'),
             InputEvent(0, 'config', choice='arena.odom_alphas=0.02,0.02,0.02,0.02')]
    if poses:
        first.append(InputEvent(0, 'config', choice=f'map.poses={poses}'))
    first += [InputEvent(0, 'config', choice=f'map.algorithm={alg}'),
              InputEvent(0, 'goal', x=route[0][0], y=route[0][1])]
    nxt, pending, ticks = 1, first, 0
    t0 = time.time()
    while ticks < 6000:
        t = a.step([e for e in pending if e.tick == a.tick])
        ticks += 1
        if t.mode == 'idle':
            if nxt >= len(route):
                break
            pending = [InputEvent(a.tick, 'goal', x=route[nxt][0], y=route[nxt][1])]
            nxt += 1
    m = a.subsystems['map']
    sc = m.scores()
    loops = len(m.engine.loop_events) if alg == 'pose_graph' else None
    return {'ate_rmse_m': sc['ate'], 'f1': sc['f1'], 'precision': sc['precision'],
            'recall': sc['recall'], 'updates': m.updates, 'ticks': ticks,
            'waypoints_reached': nxt if nxt < len(route) else len(route),
            'loop_closures': loops, 'seconds': round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    spec = yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')))
    v1, status = lab3()
    new = {rid: arena(spec, rid) for rid in RUNS}
    doc = {'tool': 'docs/v2/data/m2/m24/map_arena_scenario.py', 'evidence': 'MODEL',
           'scenario': {'start': list(map_teaching.ARENA_START), 'route': map_teaching.ARENA_ROUTE,
                        'seed': map_teaching.ARENA_SEED, 'odom_alphas': [0.02] * 4, 'range_sigma': 0.02},
           'lab3_engine': {'drive_status': status, 'runs': v1}, 'arena_engine': new,
           'python': sys.version.split()[0]}
    with open(args.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    for rid in RUNS:
        print(rid, 'Lab3', {k: round(v, 3) if isinstance(v, float) else v for k, v in v1[rid].items()})
        print(rid, 'Arena', {k: round(v, 3) if isinstance(v, float) else v for k, v in new[rid].items()})


if __name__ == '__main__':
    main()
