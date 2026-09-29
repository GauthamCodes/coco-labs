# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Phase 1B-4: the ISRO controlled experiment.

Every model searches the SAME seeded 30 x 30 map, start and goal, with the
simulator's move set (8 directions in its order, corner cutting allowed,
as its ``neighbors`` does), so any difference between models is the
model's.

M1   historical   the verbatim ``astar`` / ``dijkstra`` (coco_lab.isro),
                  TURN_PENALTY 0.1: cell-only state
M1b  hypothesis b  coco_lab A* (octile) vs Dijkstra on a grid whose
                  diagonals cost 1 -- the "octile overestimates" variant.
                  The source does NOT do this (its diagonals cost sqrt 2);
                  it is run because the roadmap asked for it
M2   heading      coco_lab A* (octile) / Dijkstra on HeadingGrid, penalty
                  0.1: the (cell, heading) state space, optimal
M3   ablation     M1 and M2 with the penalty 0.0

Every returned path is priced by ONE cost function, HeadingGrid.path_cost
at penalty 0.1 (the simulator's model), whatever model produced it.
``steps`` is the simulator's logged metric, len(smooth_path(path)). Time
is the search call alone (perf_counter, instruments off), per call, on
this machine; it is excluded from the determinism hash.

Usage (from the repository root, no ROS needed)::

    python3 docs/data/lab1b/isro_experiment.py --out docs/data/lab1b/isro_experiment.json
    python3 docs/data/lab1b/isro_experiment.py --find-trap
"""

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab.heading import GOAL, HeadingGrid  # noqa: E402
from coco_lab.isro import historical  # noqa: E402
from coco_lab.maps import LabMap  # noqa: E402
from coco_lab.search import search  # noqa: E402

PENALTY = 0.1
SIDE = 30
DENSITIES = (0.0, 0.1, 0.2, 0.3)
REL_TOL = 1e-9


def draw_map(seed, side, density, short):
    """Return (map, start, goal) for one seed; goal within 6 if short."""
    rng = random.Random(seed)
    blocked = [rng.random() < density for _ in range(side * side)]
    free = [i for i, b in enumerate(blocked) if not b]
    while True:
        s = rng.randrange(side * side)
        if short:
            r, c = divmod(s, side)
            g = (min(side - 1, max(0, r + rng.randint(-6, 6))),
                 min(side - 1, max(0, c + rng.randint(-6, 6))))
            g = g[0] * side + g[1]
        else:
            g = rng.randrange(side * side)
        if s != g:
            break
    blocked[s] = blocked[g] = False
    del free
    m = LabMap(side, side, bytes(blocked), map_id=f'isro1b/{seed}')
    return m, divmod(s, side), divmod(g, side)


def timed_search(graph, s, g, algorithm, heuristic='zero'):
    t0 = time.perf_counter()
    r = search(graph, s, g, algorithm, heuristic)
    return r, time.perf_counter() - t0


def geometric(cells):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(cells, cells[1:]))


def turns(cells):
    dirs = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(cells, cells[1:])]
    return sum(1 for a, b in zip(dirs, dirs[1:]) if a != b)


def one_case(seed, density, short):
    m, s, g = draw_map(seed, SIDE, density, short)
    price = HeadingGrid.from_map(m, s, g, PENALTY, True)
    out = {'seed': seed, 'density': density, 'short': short,
           'start': list(s), 'goal': list(g)}

    for penalty, tag in ((PENALTY, 'M1'), (0.0, 'M3h')):
        for alg in ('astar', 'dijkstra'):
            r = historical.run(m, s, g, alg, turn_penalty=penalty,
                               timed=True)
            rec = {'found': r.found}
            if r.found:
                rec.update(cost=price.path_cost(r.path),
                           geometric=geometric(r.path),
                           turns=turns(r.path), steps=r.smoothed_steps,
                           source_length=r.source_metrics['length'],
                           source_turns=r.source_metrics['turns'])
            rec.update(expansions=r.expansions,
                       distinct=r.distinct_expanded, pushes=r.pushes,
                       seconds=r.seconds)
            out[f'{tag}_{alg}'] = rec

    for penalty, tag in ((PENALTY, 'M2'), (0.0, 'M3c')):
        hg = HeadingGrid.from_map(m, s, g, penalty, True)
        for alg, h in (('astar', 'octile'), ('dijkstra', 'zero')):
            r, sec = timed_search(hg, hg.start_state(s), hg.goal_state(g),
                                  alg, h)
            rec = {'found': r.found}
            if r.found:
                cells = [st[:2] for st in r.path if st[2] != GOAL]
                rec.update(cost=price.path_cost(cells),
                           model_cost=r.cost, geometric=geometric(cells),
                           turns=turns(cells))
            rec.update(expansions=r.trace.summary['expansions'],
                       pushes=r.trace.summary['pushes'], seconds=sec)
            out[f'{tag}_{alg}'] = rec

    grid1 = m.to_grid(connectivity=8, diagonal_cost=1.0,
                      corner_cutting=True)
    for alg, h in (('astar', 'octile'), ('dijkstra', 'zero')):
        r = search(grid1, s, g, alg, h)
        rec = {'found': r.found}
        if r.found:
            rec.update(model_cost=r.cost, cost=price.path_cost(r.path),
                       geometric=geometric(r.path))
        out[f'M1b_{alg}'] = rec
    return out


def pct(a, b):
    return 100.0 * (a - b) / b if b else 0.0


def summarise(cases):
    found = [c for c in cases if c['M2_dijkstra']['found']]
    s = {'maps': len(cases), 'maps_with_path': len(found),
         'maps_without_path': len(cases) - len(found)}
    agree = all(c['M1_astar']['found'] == c['M2_dijkstra']['found']
                == c['M1_dijkstra']['found'] for c in cases)
    s['found_agrees_across_models'] = agree

    def close(a, b):
        return abs(a - b) <= REL_TOL * max(1.0, abs(a), abs(b))

    def gap_stats(key_a, key_b, field='cost'):
        gaps = [pct(c[key_a][field], c[key_b][field]) for c in found]
        diff = [x for x in gaps if abs(x) > 1e-7]
        return {
            'differ': len(diff), 'of': len(gaps),
            'a_higher': sum(1 for x in diff if x > 0),
            'a_lower': sum(1 for x in diff if x < 0),
            'mean_pct': statistics.fmean(gaps) if gaps else None,
            'mean_pct_where_differ': statistics.fmean(diff) if diff
            else None,
            'max_pct': max(gaps) if gaps else None,
            'min_pct': min(gaps) if gaps else None,
        }

    s['M1_astar_vs_M1_dijkstra_cost'] = gap_stats('M1_astar',
                                                  'M1_dijkstra')
    s['M1_astar_vs_optimum'] = gap_stats('M1_astar', 'M2_dijkstra')
    s['M1_dijkstra_vs_optimum'] = gap_stats('M1_dijkstra', 'M2_dijkstra')
    s['M2_astar_vs_M2_dijkstra'] = gap_stats('M2_astar', 'M2_dijkstra',
                                             'model_cost')
    s['M2_model_cost_equals_priced_cost'] = all(
        close(c['M2_dijkstra']['model_cost'], c['M2_dijkstra']['cost'])
        for c in found)
    s['M3_historical_astar_vs_M3_heading_geometric'] = gap_stats(
        'M3h_astar', 'M3c_dijkstra', 'geometric')
    s['M3_historical_dijkstra_vs_M3_heading_geometric'] = gap_stats(
        'M3h_dijkstra', 'M3c_dijkstra', 'geometric')
    s['M1b_astar_vs_M1b_dijkstra_model_cost'] = gap_stats(
        'M1b_astar', 'M1b_dijkstra', 'model_cost')
    s['M1b_astar_vs_M1b_dijkstra_geometric'] = gap_stats(
        'M1b_astar', 'M1b_dijkstra', 'geometric')

    for tag in ('M1', 'M3h'):
        both = [c for c in found if c[f'{tag}_astar']['steps'] is not None
                and c[f'{tag}_dijkstra']['steps'] is not None]
        a = [c[f'{tag}_astar']['steps'] for c in both]
        d = [c[f'{tag}_dijkstra']['steps'] for c in both]
        s[f'{tag}_smoothing_never_returns'] = {
            alg: sum(1 for c in found if c[f'{tag}_{alg}']['steps'] is None)
            for alg in ('astar', 'dijkstra')}
        s[f'{tag}_dijkstra_smoothing_never_returns_by_density'] = {
            str(dens): [sum(1 for c in found if c['density'] == dens
                            and c[f'{tag}_dijkstra']['steps'] is None),
                        sum(1 for c in found if c['density'] == dens)]
            for dens in DENSITIES}
        s[f'{tag}_smoothed_steps'] = {
            'maps_both_smoothable': len(both),
            'astar_mean': statistics.fmean(a) if a else None,
            'dijkstra_mean': statistics.fmean(d) if d else None,
            'ratio_of_means': (statistics.fmean(a) / statistics.fmean(d))
            if a else None,
            'maps_astar_more': sum(1 for x, y in zip(a, d) if x > y),
            'maps_astar_fewer': sum(1 for x, y in zip(a, d) if x < y),
        }
        ta = [c[f'{tag}_astar']['seconds'] for c in cases]
        td = [c[f'{tag}_dijkstra']['seconds'] for c in cases]
        s[f'{tag}_time_UNHASHED'] = {
            'astar_mean_ms': 1e3 * statistics.fmean(ta),
            'dijkstra_mean_ms': 1e3 * statistics.fmean(td),
            'ratio_of_means_dijkstra_over_astar':
                statistics.fmean(td) / statistics.fmean(ta),
            'ratio_of_medians_dijkstra_over_astar':
                statistics.median(td) / statistics.median(ta),
        }
        s[f'{tag}_expansions'] = {
            'astar_mean': statistics.fmean(
                c[f'{tag}_astar']['expansions'] for c in cases),
            'dijkstra_mean': statistics.fmean(
                c[f'{tag}_dijkstra']['expansions'] for c in cases),
            'astar_reexpansions_total': sum(
                c[f'{tag}_astar']['expansions']
                - c[f'{tag}_astar']['distinct'] for c in cases),
            'dijkstra_stale_pops_total': sum(
                c[f'{tag}_dijkstra']['expansions']
                - c[f'{tag}_dijkstra']['distinct'] for c in cases),
        }
    return s


def strip_time(obj):
    if isinstance(obj, dict):
        return {k: strip_time(v) for k, v in obj.items()
                if k != 'seconds' and not k.endswith('_UNHASHED')}
    if isinstance(obj, list):
        return [strip_time(v) for v in obj]
    return obj


def run_experiment(per_density, short_maps):
    regimes = {}
    for label, short, counts in (('long', False, per_density),
                                 ('short', True, short_maps)):
        cases = []
        for di, density in enumerate(DENSITIES):
            n = counts if not short else counts // len(DENSITIES)
            for k in range(n):
                seed = (1 if short else 0) * 10 ** 6 + di * 10 ** 5 + k
                cases.append(one_case(seed, density, short))
        regimes[label] = {'summary': summarise(cases), 'cases': cases}
    return regimes


def find_trap(side=20, tries=20000):
    """Search seeded 20x20 maps for the smallest cell-only failure."""
    best = None
    for seed in range(tries):
        rng = random.Random(10 ** 7 + seed)
        density = rng.choice((0.05, 0.1, 0.15, 0.2, 0.25))
        m, s, g = draw_map(10 ** 7 + seed, side, density, False)
        price = HeadingGrid.from_map(m, s, g, PENALTY, True)
        h = historical.run(m, s, g, 'dijkstra', instrument=False)
        if not h.found:
            continue
        opt = search(price, price.start_state(s), price.goal_state(g),
                     'dijkstra').cost
        gap = price.path_cost(h.path) - opt
        if gap > 1e-9:
            obstacles = m.count(1)
            key = (obstacles, -gap)
            if best is None or key < best[0]:
                best = (key, seed, m, s, g, gap, opt)
    if best is None:
        print('no trap found')
        return
    _, seed, m, s, g, gap, opt = best
    rows = [list(r) for r in m.to_ascii().split('\n')]
    rows[s[0]][s[1]] = 'S'
    rows[g[0]][g[1]] = 'G'
    print(f'seed {10 ** 7 + seed}: {m.count(1)} obstacles, optimum {opt!r},'
          f' historical Dijkstra worse by {gap!r}')
    print('\n'.join(''.join(r) for r in rows))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out')
    ap.add_argument('--per-density', type=int, default=300)
    ap.add_argument('--short-maps', type=int, default=600)
    ap.add_argument('--with-cases', action='store_true',
                    help='also write every case (about 5 MB); the committed '
                         'file is summaries only, and the deterministic '
                         'hash covers the cases either way')
    ap.add_argument('--find-trap', action='store_true')
    ap.add_argument('--tries', type=int, default=20000)
    args = ap.parse_args(argv)
    if args.find_trap:
        find_trap(tries=args.tries)
        return
    t0 = time.time()
    regimes = run_experiment(args.per_density, args.short_maps)
    hashed = json.dumps(strip_time(regimes), sort_keys=True,
                        separators=(',', ':'))
    result = {
        'description': __doc__.split('\n')[1],
        'penalty': PENALTY, 'side': SIDE, 'densities': list(DENSITIES),
        'deterministic_sha256': hashlib.sha256(hashed.encode()).hexdigest(),
        'wall_seconds_UNHASHED': time.time() - t0,
        'long': regimes['long']['summary'],
        'short': regimes['short']['summary'],
    }
    if args.with_cases:
        result['cases'] = {k: v['cases'] for k, v in regimes.items()}
    text = json.dumps(result, indent=1, sort_keys=True)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')
    print(json.dumps({k: result[k] for k in ('deterministic_sha256',
                                              'wall_seconds_UNHASHED',
                                              'long', 'short')},
                     indent=1, sort_keys=True))


if __name__ == '__main__':
    main()
