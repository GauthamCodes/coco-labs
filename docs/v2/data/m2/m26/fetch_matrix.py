"""
The Arena's fetch mission, measured (M2.6; MODEL).

    python3 docs/v2/data/m2/m26/fetch_matrix.py --out docs/v2/data/m2/m26/fetch_matrix.json

Every colour (target at its layout bay) x five configurations x seeds 1-2:

- ``plain``: no localiser (the belief is the truth), M1's waypoint driver;
- ``mcl``: MCL (500 particles, range noise 0.02 m), M1's driver;
- ``mcl+rpp`` / ``mcl+mppi`` / ``mcl+dwa``: MCL and that local controller.

And the whole loop degraded on purpose: ``mislocalised`` -- no localiser,
the robot told it is 4 m south of the truth (``move.belief_offset``),
every colour, seed 1.

Per run: the mission's result, its transitions (event and reason), the bays
it surveyed, how many recoveries, ticks and simulated seconds, and the
largest true localisation error. Run on CPython; the Arena is
deterministic, so a run is reproduced by its colour, configuration and
seed. Nothing here is a rate for the real robot.
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

from coco_lab.arena import Arena, InputEvent  # noqa: E402
import coco_lab.loc_arena  # noqa: E402,F401
import coco_lab.mission_arena  # noqa: E402,F401
import coco_lab.move_arena  # noqa: E402,F401

COLOURS = ['red', 'green', 'blue', 'yellow']
MCL = ['arena.range_sigma=0.02', 'localise.filter=mcl']
CONFIGS = {
    'plain': [],
    'mcl': MCL,
    'mcl+rpp': MCL + ['move.controller=rpp'],
    'mcl+mppi': MCL + ['move.controller=mppi'],
    'mcl+dwa': MCL + ['move.controller=dwa'],
}
SEEDS = [1, 2]
MAX_TICKS = 6000


def run(spec, colour, cfg, seed):
    trans = []

    def fam(ch, tick, cols, sc):
        if ch == 'coco.mission.fsm.transition.v1' and cols:
            for f, t, e, r in zip(cols['from_state'], cols['to_state'], cols['event'], cols['reason']):
                trans.append({'tick': tick, 'from': f, 'to': t, 'event': e, 'reason': r})
    a = Arena(spec, seed, on_family=fam)
    a.step([InputEvent(0, 'config', choice=c) for c in cfg] +
           [InputEvent(0, 'config', choice=f'mission.start={colour}')])
    m = a.subsystems['mission']
    worst = 0.0
    t0 = time.time()
    while m.state not in ('done', 'failed') and a.tick < MAX_TICKS:
        a.step(())
        b = a.belief()
        worst = max(worst, math.hypot(b[0] - a.pose[0], b[1] - a.pose[1]))
    surveyed = [t['reason'] for t in trans if t['event'] in ('miss', 'target_detected')]
    return {'colour': colour, 'seed': seed, 'result': m.result or m.state,
            'state': m.state, 'surveys': len(surveyed),
            'recoveries': sum(1 for t in trans if t['event'] == 'controller_failed'),
            'ticks': a.tick, 't_sim_s': round(a.t_world, 1),
            'max_true_loc_error_m': round(worst, 4),
            'final_bay_belief': [round(p, 4) for p in m.bay_belief],
            'transitions': trans, 'wall_s': round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')) as f:
        spec = yaml.safe_load(f)
    out = {'tool': 'docs/v2/data/m2/m26/fetch_matrix.py', 'evidence': 'MODEL',
           'python': sys.version.split()[0], 'seeds': SEEDS, 'configs': CONFIGS, 'runs': {}}
    for name, cfg in CONFIGS.items():
        rows = [run(spec, c, cfg, s) for c in COLOURS for s in SEEDS]
        out['runs'][name] = rows
        print(name, sum(r['result'] == 'fetch' for r in rows), '/', len(rows),
              [r['result'][:40] for r in rows if r['result'] != 'fetch'], flush=True)
    rows = [run(spec, c, ['move.belief_offset=0.0,-4.0,0.0'], 1) for c in COLOURS]
    out['runs']['mislocalised'] = rows
    print('mislocalised', sum(r['result'] == 'fetch' for r in rows), '/', len(rows), flush=True)
    with open(args.out, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main()
