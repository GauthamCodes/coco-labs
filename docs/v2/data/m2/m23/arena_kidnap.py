"""
A kidnap in the Arena, closed loop (M2.3; MODEL).

    python3 docs/v2/data/m2/m23/arena_kidnap.py --seeds 20 \
        --out docs/v2/data/m2/m23/arena_kidnap.json

COCO's arena (the World Spec), the Arena's own engine: wheel odometry with
Sketch's default noise, LiDAR range noise 0.02 m, MCL with 500 particles
(Lab 2's arena setting), a patrol of four goals the robot plans and drives
to FROM ITS BELIEF. At tick 120 the robot is carried to a pose ~9 m away
(the filter is not told). Recovery uses Lab 2's definition (coco_lab.localise
OK_XY / OK_YAW held for OK_HOLD updates) on the error the subsystem emits.
Arms: injection none (COCO's AMCL) vs augmented. Seeds vary the Arena seed,
so the odometry noise, range noise and filter draws all vary.

Not Lab 2's experiment: Lab 2's Sketch driver followed the TRUE pose (open
loop), in a teaching room. Here a lost robot keeps driving on its wrong
belief -- the whole loop -- and may stop against a wall, which ends its
filter updates (MCL updates only when odometry moves).
"""

import argparse
import json
import math
import os
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab.arena import Arena, InputEvent  # noqa: E402
import coco_lab.loc_arena  # noqa: E402,F401
from coco_lab.localise import OK_HOLD, OK_XY, OK_YAW  # noqa: E402

GOALS = [(6.0, 4.0), (2.5, 2.0), (0.5, -2.5), (12.0, 5.5)]
KIDNAP_TICK = 120
KIDNAP_TO = (9.0, -4.0, 1.2)
TICKS = 700


def run(spec, seed, injection):
    errs = []

    def fam(ch, tick, cols, sc):
        if ch == 'coco.metrics.values.v1':
            got = dict(zip(cols['name'], cols['value']))
            if 'err_xy.mcl' in got:
                errs.append((tick, got['err_xy.mcl'], got['err_yaw.mcl']))
    a = Arena(spec, seed, on_family=fam)
    first = [InputEvent(0, 'config', choice='arena.range_sigma=0.02'),
             InputEvent(0, 'config', choice='localise.mcl.particles=500'),
             InputEvent(0, 'config', choice=f'localise.mcl.injection={injection}'),
             InputEvent(0, 'config', choice='localise.filter=mcl')]
    g = 0
    ins = first + [InputEvent(0, 'goal', x=GOALS[0][0], y=GOALS[0][1])]
    blocked_after = 0
    for k in range(TICKS):
        ev = [e for e in ins if e.tick == k]
        if k == KIDNAP_TICK:
            ev.append(InputEvent(k, 'kidnap', x=KIDNAP_TO[0], y=KIDNAP_TO[1],
                                 theta=KIDNAP_TO[2], has_theta=True))
        t = a.step(ev)
        if k > KIDNAP_TICK and t.blocked:
            blocked_after += 1
        if t.mode == 'idle' or t.arrived:
            g = (g + 1) % len(GOALS)
            ins.append(InputEvent(a.tick, 'goal', x=GOALS[g][0], y=GOALS[g][1]))
    after = [e for e in errs if e[0] > KIDNAP_TICK]
    ok = [e[1] < OK_XY and e[2] < OK_YAW for e in after]
    rec = None
    for i in range(len(ok) - OK_HOLD + 1):
        if all(ok[i:i + OK_HOLD]):
            rec = after[i][0]
            break
    return {'seed': seed, 'recovered': rec is not None,
            'recovery_s': None if rec is None else round((rec - KIDNAP_TICK) * a.dt, 1),
            'updates_after_kidnap': len(after),
            'err_just_after_m': round(after[0][1], 3) if after else None,
            'final_err_m': round(errs[-1][1], 3) if errs else None,
            'blocked_ticks_after_kidnap': blocked_after}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=20)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    spec = yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')))
    t0 = time.time()
    arms = {}
    for inj in ('none', 'augmented'):
        runs = [run(spec, s, inj) for s in range(a.seeds)]
        arms[inj] = {'recovered': sum(r['recovered'] for r in runs), 'n': len(runs), 'runs': runs}
        print(inj, f"{arms[inj]['recovered']}/{len(runs)}", flush=True)
    doc = {'tool': 'docs/v2/data/m2/m23/arena_kidnap.py', 'evidence': 'MODEL (the Arena, closed loop)',
           'world': 'worlds/coco_arena_v1.yaml', 'particles': 500, 'kidnap_tick': KIDNAP_TICK,
           'kidnap_to': KIDNAP_TO, 'ticks': TICKS, 'goals': GOALS,
           'definition': {'ok_xy_m': OK_XY, 'ok_yaw_rad': OK_YAW, 'hold_updates': OK_HOLD},
           'seconds': round(time.time() - t0, 1), 'python': sys.version.split()[0], 'arms': arms}
    with open(a.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main()
