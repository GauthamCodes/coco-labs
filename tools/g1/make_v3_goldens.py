#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.8: write the state hash v3 goldens (new files; v1 and v2 goldens are never edited).

    tools/g1/make_v3_goldens.py [--check]

coco_lab/test/fixtures/v3/numerics_vectors.json: fixed inputs and the exact bits
coco_lab.numerics returns for each (any conforming platform must give the same).
coco_lab/test/fixtures/v3/state_hash_v3.json: runs under hash version 3 -- the
arena (teleop, a goal, the whole loop's localisation), the terrain world (a goal
up the ramp) and a Fetch Rush session on the Depot (the G1.6 browser record) --
each with its per-tick hash chain. --check regenerates and compares instead of
writing (exit 1 on a difference).
"""
import argparse
import hashlib
import json
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games, loc_arena, numerics  # noqa: E402,F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, InputEvent  # noqa: E402

OUT = os.path.join(REPO, 'coco_lab', 'test', 'fixtures', 'v3')
FUNCS = {'sin': 1, 'cos': 1, 'tan': 1, 'atan': 1, 'atan2': 2, 'acos': 1, 'exp': 1, 'log': 1,
         'hypot': 2}
EDGES = [0.0, -0.0, 1.0, -1.0, 0.5, -0.5, 3.141592653589793, 1.5707963267948966,
         0.7853981633974483, 2.356194490192345, 1e-300, 5e-324, 1e-8, 100.0, -100.0, 700.0, -700.0]


def world(name):
    with open(os.path.join(REPO, 'worlds', name)) as f:
        return json.load(f)


def vectors():
    r = random.Random(20261020)
    out = {}
    for name, n in FUNCS.items():
        f = getattr(numerics, name)
        rows = []
        cand = [(e,) for e in EDGES] if n == 1 else [(e, d) for e in EDGES[:9] for d in EDGES[:9]]
        for scale in (1.0, 10.0, 1000.0):
            cand += [tuple(r.uniform(-scale, scale) for _ in range(n)) for _ in range(40)]
        for args in cand:
            if name == 'acos':
                args = tuple(max(-1.0, min(1.0, a)) for a in args)
            if name == 'log':
                args = tuple(abs(a) or 1.0 for a in args)
            try:
                y = f(*args)
            except (ValueError, OverflowError) as e:
                y = type(e).__name__
            rows.append([[a.hex() for a in args], y.hex() if isinstance(y, float) else y])
        out[name] = rows
    return out


def run(spec, seed, inputs, ticks, game=None):
    a = Arena(spec, seed, hash_version=3)
    by = {}
    for e in inputs:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    rules = games._rules(game[0], game[1]) if game else None
    chain = hashlib.sha256()
    hashes = []
    for _ in range(ticks):
        t = a.step(by.get(a.tick, ()))
        if rules is not None:
            if not rules.started:
                rules.start(a)
            rules.observe(a, t)
        hashes.append(t.state_hash)
        chain.update(t.state_hash.encode())
    row = {'seed': seed, 'ticks': ticks, 'inputs': inputs, 'chain': chain.hexdigest(),
           'first_hash': hashes[0], 'last_hash': hashes[-1], 'final_pose': [v.hex() for v in a.pose]}
    if rules is not None:
        row['scorecard'] = games._card(rules, a)
    return row


def runs():
    rec = json.load(open(os.path.join(REPO, 'docs', 'v2', 'g1', 'data', 'g16', 'browser',
                                      'browser_record.json')))['record']
    return {
        'arena_teleop_goal': dict(world='coco_arena_v1.json', **run(world('coco_arena_v1.json'), 7, [
            {'tick': 0, 'kind': 'teleop', 'linear': 0.3, 'angular': 0.4},
            {'tick': 15, 'kind': 'stop'},
            {'tick': 16, 'kind': 'goal', 'x': 2.5, 'y': 2.0}], 120)),
        'arena_localise_mcl': dict(world='coco_arena_v1.json', **run(world('coco_arena_v1.json'), 1, [
            {'tick': 0, 'kind': 'config', 'choice': 'localise.filter=mcl'},
            {'tick': 1, 'kind': 'goal', 'x': -2.0, 'y': 2.0},
            {'tick': 40, 'kind': 'kidnap', 'x': 0.5, 'y': -1.0}], 100)),
        'terrain_goal': dict(world='coco_arena_v2.json', **run(world('coco_arena_v2.json'), 1, [
            {'tick': 0, 'kind': 'goal', 'x': 2.5, 'y': 2.0}], 150)),
        'depot_fetch_rush': dict(world='coco_depot_v1.json', game=[rec['game'], rec['arg']],
                                 **run(world('coco_depot_v1.json'), rec['seed'], rec['inputs'],
                                       rec['ticks'], (rec['game'], rec['arg']))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    data = {'numerics_vectors.json': {'about': 'G1.8: coco_lab.numerics, exact bits (float.hex)',
                                      'vectors': vectors()},
            'state_hash_v3.json': {'about': 'G1.8: state hash v3 runs, per-tick sha256 chain',
                                   'hash_version': 3, 'runs': runs()}}
    bad = 0
    for name, d in data.items():
        path = os.path.join(OUT, name)
        text = json.dumps(d, indent=1, sort_keys=True) + '\n'
        if a.check:
            same = open(path).read() == text
            print(name, 'identical' if same else 'DIFFERS')
            bad += not same
        else:
            os.makedirs(OUT, exist_ok=True)
            open(path, 'w').write(text)
            print('wrote', path)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
