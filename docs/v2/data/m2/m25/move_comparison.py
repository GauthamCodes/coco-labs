"""
Lab 5's scenarios in the Arena with the model controllers (M2.5; MODEL vs STACK).

    python3 docs/v2/data/m2/m25/move_comparison.py \
        --out docs/v2/data/m2/m25/move_comparison.json

For each of Lab 5's four scenarios (static_room = the hairpin, crossing,
oncoming = head-on, mislocalised = run 15's mechanism) and each model
controller (DWA, RPP, MPPI; coco_lab.control), runs seeds 1..5 through the
Arena (coco_lab.arena + coco_lab.move_arena): the robot at map (0, 0, 0),
the scenario's FROZEN Lab 5 path, its actors (WITH collision bodies),
until FollowPath's outcome or 300 s. Each run is scored with Lab 5's own
code and definitions -- coco_lab.movemetrics.evaluate, Lab 5's footprint
rectangle, Lab 5's obstacles (navigation_world.json in the map frame) --
over the window from the first command to the outcome.

The STACK side is read, not re-run: docs/data/lab5/results.json (54 runs
in Gazebo, 2026-10-07). Nothing in the model is fitted to it.
"""

import argparse
import json
import math
import os
import sys
import time

import yaml

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab import move_scenarios, movemetrics as mm  # noqa: E402
from coco_lab.arena import Arena, InputEvent  # noqa: E402
from coco_lab.move_arena import CODES  # noqa: E402

SCENARIOS = ['static_room', 'crossing', 'oncoming', 'mislocalised']
MODEL = {'dwa': 'DWB', 'rpp': 'RPP', 'mppi': 'MPPI'}
SEEDS = [1, 2, 3, 4, 5]
MAX_TICKS = 3000


def run(spec, boxes, scenario, ctrl, seed):
    cmds = []

    def fam(ch, tick, cols, sc):
        if ch == 'coco.control.local.command.v1' and cols:
            for t, v, w in zip(cols['t_world'], cols['v'], cols['w']):
                cmds.append((t, v, w))
    a = Arena(spec, seed, on_family=fam)
    a.step([InputEvent(0, 'config', choice=f'move.controller={ctrl}'),
            InputEvent(0, 'config', choice=f'move.scenario={scenario}')])
    m = a.subsystems['move']
    gt = [(a.t_world, *a.pose)]
    tracks = [[(a.t_world, ac.x, ac.y)] for ac in m.actors]
    t0 = time.time()
    while a.mode == 'goal' and a.tick < MAX_TICKS:
        a.step(())
        gt.append((a.t_world, *a.pose))
        for tr, ac in zip(tracks, m.actors):
            tr.append((a.t_world, ac.x, ac.y))
    outcome = m.outcome or ('timeout' if a.mode == 'goal' else 'none')
    t_end = gt[-1][0]
    t_start = cmds[0][0] if cmds else 0.0
    path = move_scenarios.PATHS[move_scenarios.SCENARIOS[scenario]['path']]
    actors = [{'radius': ac.r, 'track': tr} for ac, tr in zip(m.actors, tracks)]
    met = mm.evaluate(path, gt, (t_start, t_end), cmds, boxes, actors)
    return {'controller': ctrl, 'seed': seed, 'outcome': outcome,
            'error_code': CODES.get(outcome, 0), 'ticks': a.tick,
            'cycles': m.cycle, 'actor_held_ticks': [ac.held for ac in m.actors],
            'final_pose': [round(v, 4) for v in a.pose], 'metrics': met,
            'wall_s': round(time.time() - t0, 2)}


def dist(rows, f):
    return mm.distribution([f(r) for r in rows])


def summary(rows):
    ok = [r for r in rows if r['outcome'] == 'succeeded']
    outc = {}
    for r in rows:
        outc[r['outcome']] = outc.get(r['outcome'], 0) + 1
    return {
        'runs': len(rows), 'outcomes': outc,
        'identical_across_seeds': len({json.dumps(r['metrics'], sort_keys=True) for r in rows}) == 1,
        'tracking_mean_m': dist(rows, lambda r: r['metrics']['tracking_m']['mean']),
        'tracking_max_m': dist(rows, lambda r: r['metrics']['tracking_m']['max']),
        'time_s_succeeded': dist(ok, lambda r: r['metrics']['time_s']),
        'rms_linear_accel': dist(rows, lambda r: r['metrics']['smoothness']['rms_linear_accel']),
        'rms_angular_accel': dist(rows, lambda r: r['metrics']['smoothness']['rms_angular_accel']),
        'min_clearance_m': dist(rows, lambda r: r['metrics']['clearance']['min_m']),
        'min_clearance_actor_m': dist(rows, lambda r: r['metrics']['clearance']['actor']['min_m']),
        'contacts': sum(1 for r in rows if r['metrics']['clearance']['contact']),
        'actor_held_ticks': [sum(r['actor_held_ticks']) for r in rows],
    }


STACK_KEYS = ['runs', 'outcomes', 'error_codes', 'tracking_mean_m', 'tracking_max_m',
              'time_s_succeeded', 'rms_linear_accel', 'rms_angular_accel',
              'min_clearance_m', 'min_clearance_actor_m', 'contacts']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')) as f:
        spec = yaml.safe_load(f)
    with open(os.path.join(REPO, 'gazebo_models', 'config', 'navigation_world.json')) as f:
        world = json.load(f)
    boxes = mm.boxes_in_map(world['boxes'], world.get('world_to_map', [2.0, 0.0]))
    with open(os.path.join(REPO, 'docs', 'data', 'lab5', 'results.json')) as f:
        stack = json.load(f)
    out = {'tool': 'docs/v2/data/m2/m25/move_comparison.py', 'evidence': {'model': 'MODEL', 'stack': 'STACK'},
           'python': sys.version.split()[0], 'seeds': SEEDS, 'scenarios': {}}
    for sc in SCENARIOS:
        block = {'title': move_scenarios.SCENARIOS[sc]['title'], 'model': {}, 'stack': {}}
        for ctrl, stack_id in MODEL.items():
            rows = [run(spec, boxes, sc, ctrl, s) for s in SEEDS]
            block['model'][ctrl] = {'summary': summary(rows), 'runs': rows}
            sv = stack['scenarios'][sc]['controllers'][stack_id]
            block['stack'][stack_id] = {k: sv[k] for k in STACK_KEYS if k in sv}
            print(sc, ctrl, block['model'][ctrl]['summary']['outcomes'], '| STACK', stack_id,
                  sv['outcomes'], flush=True)
        out['scenarios'][sc] = block
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, default=lambda v: None if isinstance(v, float) and not math.isfinite(v) else v)
        f.write('\n')


if __name__ == '__main__':
    main()
