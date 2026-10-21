#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.11: Fetch Rush rules 2 -- the level's precomputed rounds.

    tools/g1/make_fetch_rush_rounds.py [--seeds 1-6] [--out PATH]
    tools/g1/make_fetch_rush_rounds.py --check [--seeds 1,2]

Writes ``coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.json``:

- ``trips[frm][oid][drop]``: the planned round trip (m) from ``frm`` -- a start zone's
  start point, or a drop zone's centre -- to the object's best pre-grasp pose (A* over
  Grasp Assist's approach poses, ``games.best_approach``), then to the drop zone's
  centre (``games.plan_length``): M6F.6's ghost, measured from where an order begins.
- per seed: ``games.draw_round`` over that table (budget ``games.ROUND_BUDGET_M``,
  ``games.ROUND_ORDERS`` orders), the start pose, each order's ghost length and its
  route (the A* cells, for drawing), and the reference bot's run of the round:
  ``reference_time_s`` (its time for the round's deliveries), ``timer_s`` =
  that x ``games.ROUND_TIMER_FACTOR``, and its record and scorecard under that timer
  (the stars' reference).

Nothing here runs while a game is played: the rules read the file. ``--check``
recomputes the given seeds' trips and draws from the committed table and compares
(the full table takes ~10 minutes; the CI test checks a sample).
"""
import argparse
import hashlib
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab import games, loc_arena  # noqa: E402,F401 -- loc_arena: the subsystem
from coco_lab import worldspec_v3 as v3  # noqa: E402
from coco_lab.arena import Arena, InputEvent, PLANNERS  # noqa: E402
from coco_lab.numerics import math  # noqa: E402
from coco_lab.search import search  # noqa: E402
from coco_lab.sketch import _nearest_free  # noqa: E402

LEVEL = 'coco_depot_v1'
OUT = os.path.join(REPO, 'coco_lab', 'coco_lab', 'levels', f'{LEVEL}.fetch_rush.json')
#: the bot's first run plays to the deliveries with this much time (under the link limit)
PROVISIONAL_S = 1100.0
HV = 3


def arena(spec):
    a = Arena(spec, 1, hash_version=HV)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1)])
    return a


def centre(a, zid):
    r = games.zone_rect(a.spec, zid)
    return ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)


def start_points(a):
    """A start zone's start point: the plan grid's free cell nearest the zone's centre."""
    out = {}
    for z in a.spec['kit']:
        if z.get('kind') == 'zone' and z['role'] == 'region' and z['id'] not in games.ROUND_NO_START:
            cell = _nearest_free(a.grid, a.plan_map.cell_at(*centre(a, z['id'])))
            out[z['id']] = tuple(a.plan_map.cell_centre(cell[0], cell[1]))
    return out


def route(a, frm, to):
    """The A* route's cells as map points, straight runs merged (for drawing only)."""
    s = _nearest_free(a.grid, a.plan_map.cell_at(*frm))
    t = _nearest_free(a.grid, a.plan_map.cell_at(*to))
    r = search(a.grid, s, t, **PLANNERS['astar'])
    pts = [tuple(a.plan_map.cell_centre(c[0], c[1])) for c in r.path]
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        d0 = (pts[i][0] - keep[-1][0], pts[i][1] - keep[-1][1])
        d1 = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if abs(d0[0] * d1[1] - d0[1] * d1[0]) > 1e-9:
            keep.append(pts[i])
    keep.append(pts[-1])
    return [[round(x, 3), round(y, 3)] for x, y in keep]


def trips_from(a, assist, pool, drops, frm):
    """Return ``{oid: {drop: trip}}`` and ``{oid: approach pose}`` from point ``frm``."""
    trips, poses = {}, {}
    for oid in pool:
        ba = games.best_approach(a, assist, oid, frm)
        if ba is None:
            continue
        poses[oid] = [ba[0][0], ba[0][1], ba[0][2]]
        trips[oid] = {}
        for d in drops:
            back = games.plan_length(a, ba[0][:2], centre(a, d))
            if back is not None:
                trips[oid][d] = ba[1] + back
    return trips, poses


def replay(spec, record, rules):
    """games.play's loop with an explicit rules object (the round is not on disk yet)."""
    a = Arena(spec, record['seed'], hash_version=record.get('hash_version', 1))
    by = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    chain, last = hashlib.sha256(), ''
    for _ in range(record['ticks']):
        t = a.step(by.get(a.tick, ()))
        if not rules.started:
            rules.start(a)
        rules.observe(a, t)
        last = t.state_hash
        chain.update(last.encode())
    return {'scorecard': rules.scorecard(), 'hash_chain': chain.hexdigest(), 'last_hash': last}


def seeds_arg(text):
    if '-' in text:
        lo, hi = map(int, text.split('-'))
        return list(range(lo, hi + 1))
    return [int(x) for x in text.split(',')]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seeds', default='1-6')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--check', action='store_true')
    o = ap.parse_args()
    spec = json.load(open(os.path.join(REPO, 'worlds', f'{LEVEL}.json')))
    spec_sha = hashlib.sha256(open(os.path.join(REPO, 'worlds', f'{LEVEL}.json'), 'rb').read()).hexdigest()
    a = arena(spec)
    assist = a.subsystems['assist']
    pool = games.pickable(a, assist)
    drops = sorted(z['id'] for z in v3.zones(a.spec, 'drop'))
    starts = start_points(a)
    seeds = seeds_arg(o.seeds)
    if o.check:
        doc = json.load(open(o.out))
        bad = []
        if doc['spec_sha256'] != spec_sha:
            bad.append('spec changed')
        for sd in seeds:
            rnd = doc['rounds'][str(sd)]
            if games.draw_round(sd, doc['trips'])['orders'] != rnd['orders']:
                bad.append(f'seed {sd}: draw')
            frm = starts[rnd['region']]
            for (oid, drop), g in zip(rnd['orders'], rnd['ghost_m']):
                t, _ = trips_from(a, assist, [oid], [drop], frm)
                if abs(t[oid][drop] - g) > 1e-9:
                    bad.append(f'seed {sd}: {oid}->{drop} {t[oid][drop]} != {g}')
                frm = centre(a, drop)
        print('identical' if not bad else 'DIFFERS: ' + '; '.join(bad))
        return 1 if bad else 0

    t0 = time.time()
    trips, approach = {}, {}
    froms = dict(starts, **{d: centre(a, d) for d in drops})
    for f, p in sorted(froms.items()):
        trips[f], approach[f] = trips_from(a, assist, pool, drops, p)
        print(f'trips from {f}: {time.time() - t0:.0f} s', flush=True)
    rounds = {}
    for sd in seeds:
        drawn = games.draw_round(sd, trips)
        sx, sy = starts[drawn['region']]
        first = approach[drawn['region']][drawn['orders'][0][0]]
        rnd = {'region': drawn['region'], 'orders': drawn['orders'],
               'start': [sx, sy, math.atan2(first[1] - sy, first[0] - sx)],
               'ghost_m': [], 'routes': []}
        frm = drawn['region']
        for oid, drop in drawn['orders']:
            rnd['ghost_m'].append(trips[frm][oid][drop])
            ap = approach[frm][oid]
            rnd['routes'].append(route(a, froms[frm], ap[:2]) + route(a, ap[:2], centre(a, drop))[1:])
            frm = drop
        # the reference bot plays the round (time to spare), then under the derived timer
        rules = games.FetchRushRound(sd, rnd, seconds=PROVISIONAL_S)
        rec, res = games.bot_fetch_rush(spec, sd, rules=rules, hash_version=HV)
        card = res['scorecard']
        if card['deliveries'] < games.ROUND_ORDERS:
            rnd.update(reference_time_s=None, timer_s=None,
                       reference={'note': f"the bot delivered {card['deliveries']} of "
                                          f"{games.ROUND_ORDERS}", 'card': card})
            print(f'seed {sd}: bot delivered {card["deliveries"]}; no timer', flush=True)
        else:
            t_ref = card['delivered'][-1]['t']
            rnd['reference_time_s'] = t_ref
            rnd['timer_s'] = round(t_ref * games.ROUND_TIMER_FACTOR, 1)
            final = replay(spec, rec, games.FetchRushRound(sd, rnd))
            rnd['reference'] = {'record': rec, 'card': final['scorecard'],
                                'hash_chain': final['hash_chain']}
            print(f"seed {sd}: {rnd['region']} {rnd['orders']} ref {t_ref:.1f} s "
                  f"timer {rnd['timer_s']} s ({time.time() - t0:.0f} s)", flush=True)
        rounds[str(sd)] = rnd
    doc = {'about': 'G1.11: Fetch Rush rules 2 rounds for the level (tools/g1/make_fetch_rush_rounds.py)',
           'level': LEVEL, 'spec_sha256': spec_sha, 'rules': games.FETCH_RUSH_RULES,
           'budget_m': games.ROUND_BUDGET_M, 'orders': games.ROUND_ORDERS,
           'timer_factor': games.ROUND_TIMER_FACTOR, 'hash_version': HV,
           'starts': {k: list(v) for k, v in starts.items()},
           'trips': trips, 'approach': approach, 'rounds': rounds}
    os.makedirs(os.path.dirname(o.out), exist_ok=True)
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write('\n')
    print('wrote', o.out, f'{time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
