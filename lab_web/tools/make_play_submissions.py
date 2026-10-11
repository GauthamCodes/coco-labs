#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Generate Play submissions for verification (M3.6): 20 per challenge, 100 in all.

    python3 lab_web/tools/make_play_submissions.py OUT.json [--seed 20261011]

A fixed-seed generator draws a spread of inputs per challenge -- the
reference answer, perturbed answers, random answers and some that break a
rule (scored ``valid: False``, which must reproduce too):

- beat-the-planner: A*'s path, with random out-and-back detours; the
  greedy and weighted-A* paths; a path cut short;
- next-node: per expansion, A*'s cell or a random open cell;
- search-the-bays: random orders, and one that repeats a bay;
- map-the-arena: the level's config, then random goals at random ticks,
  scored at a random tick (both levels);
- case-file-detective: a tick near the divergence, sometimes far, sometimes
  outside the Case File.

Only the INPUTS are written: the scores are what the browser computes
(tools/perf/play_verify.mjs) and what ``coco verify`` recomputes.
"""

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'coco_lab'))

from coco_lab import play  # noqa: E402
from coco_lab.search import collect, search_events  # noqa: E402

LEVELS = os.path.join(HERE, '..', 'play', 'levels.json')
PER = 20


def beat(rng, levels, lv):
    v = play.view(levels, 'beat-the-planner', lv['id'])
    grid, m = play.parse_grid(lv['grid'])
    kind = rng.choice(['optimal', 'detour', 'detour', 'greedy', 'weighted', 'short'])
    if kind in ('greedy', 'weighted'):
        alg, w = ('greedy', None) if kind == 'greedy' else ('weighted_astar', lv['weight'])
        return [list(c) for c in collect(search_events(grid, m['S'], m['G'], alg, 'octile', w)).path]
    path = [tuple(c) for c in v['optimal_path']]
    if kind == 'short':
        return [list(c) for c in path[:max(1, len(path) - 1 - rng.randrange(1, 4))]]
    if kind == 'detour':
        for _ in range(rng.randrange(1, 4)):
            i = rng.randrange(len(path))
            n = rng.choice(list(grid.neighbours(path[i])))
            path[i + 1:i + 1] = [n, path[i]]
    return [list(c) for c in path]


def next_node(rng, levels, lv):
    frames = play.next_node_frames(lv)
    p = rng.random()
    return [fr['expanded'] if rng.random() < p else list(rng.choice(fr['open'])[:2]) for fr in frames]


def bays(rng, levels, lv):
    n = len(lv['problem']['regions'])
    order = list(range(n))
    rng.shuffle(order)
    if rng.random() < 0.1:
        order[-1] = order[0]
    return order


def map_drive(rng, levels, lv):
    log = [{'tick': 0, 'kind': 'config', 'choice': c} for c in lv['config']]
    t = 0
    for _ in range(rng.randrange(1, 5)):
        t += rng.randrange(1, 300)
        # a free spot the reference drives use (goals the Arena accepts)
        x, y = rng.choice([g for d in lv['drives'].values() for g in d['goals']])
        log.append({'tick': t, 'kind': 'goal', 'x': x + rng.uniform(-0.3, 0.3), 'y': y + rng.uniform(-0.3, 0.3)})
    return {'ticks': t + rng.randrange(50, 600), 'log': log}


def detective(rng, levels, lv):
    m = lv['moment']['tick']
    u = rng.random()
    if u < 0.1:
        return [lv['ticks'] + rng.randrange(1, 50)]
    spread = 8 if u < 0.6 else 60
    return [max(1, min(lv['ticks'], m + rng.randrange(-spread, spread + 1)))]


MAKE = {'beat-the-planner': beat, 'next-node': next_node, 'search-the-bays': bays,
        'map-the-arena': map_drive, 'case-file-detective': detective}


def main():
    out = sys.argv[1]
    seed = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 20261011
    with open(LEVELS, encoding='utf-8') as f:
        levels = json.load(f)
    rng = random.Random(seed)
    subs = []
    for cid in play.CHALLENGES:
        lvs = levels['challenges'][cid]['levels']
        for k in range(PER):
            lv = lvs[k % len(lvs)]
            subs.append({'v': 1, 'challenge': cid, 'level': lv['id'], 'level_hash': play.level_hash(lv),
                         'inputs': MAKE[cid](rng, levels, lv)})
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'what': 'Play submissions for verification (M3.6): inputs only',
                   'tool': 'lab_web/tools/make_play_submissions.py', 'seed': seed, 'submissions': subs}, f, indent=1)
        f.write('\n')
    print(f'{len(subs)} submissions -> {out}')


if __name__ == '__main__':
    main()
