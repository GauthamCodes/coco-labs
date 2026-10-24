#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.1: Fetch Rush rules 4 -- rules 3's rounds, crossing the forklift lane only at a marked crossing.

    tools/g2/make_fetch_rush_rounds_r4.py [--seeds 1-6] [--out PATH] [--trips-cache PATH]
                                          [--phone-budget M]

Writes ``coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r4.json``; rules 3's file
(``tools/g1/make_fetch_rush_rounds_r3.py``'s) is left as it is, so rules-3 records replay on it.
Gautham's decisions (2026-10-23, G2 prompt §1; planning answer 2026-10-24):

- the round lanes are rules 3's (``games.ROUND_LANES``: the east-west forklift lane zone).
  A route may enter them ONLY inside a marked crossing (``games.crossings``: where a walker's
  lane crosses the lane zone, painted with hazard stripes over the zone's full depth), and
  only with COCO's whole footprint on the stripes (``games.crossing_bands``: the crossing
  narrowed by the robot radius); every stretch of a route inside the lane zone must cross it
  (come in on one side, leave on the other), never run along it.
- ``trips[frm][oid][drop]``: as rules 3's, but each route is A* on the Arena's plan grid with
  every lane cell outside the bands blocked (``games.lane_grid``), so the shortest route that
  keeps the rule is the one drawn.
- each accepted round also keeps, per order, the pre-grasp pose its route was planned to
  (``pick``) and the crossing mouths of its two legs (``via``): the reference bot (rules 4)
  drives through those, so it keeps the rule too. A round is REJECTED when the bot does not
  deliver every order, or when the robot (truth pose) ever stands in a lane outside a band or
  leaves a crossing on the side it came in; the seed then draws again, as in rules 3.
- G2.1, measured: a crossing is OPEN only if some start time lets a straight crossing at the
  auto speed touch no actor (``games.crossing_windows``, the actors' own schedules). On the
  Depot both marked crossings are the walkers' paths, paced end to end, and neither has such a
  start time (written into the file: ``crossing_windows``), so both are closed: no route crosses
  the lane, and the rule is kept by never crossing. A crossing that opens (a changed world)
  is used by the routes and driven by the bot through its mouths.
- per mode (``games.ROUND_MODES_R4``) and seed: draw, place the start (rules 3's way), play,
  timer = reference time x ``games.ROUND_TIMER_FACTOR``, reference record, card, hash chain.
"""
import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.join(REPO, 'tools', 'g1'))
from coco_lab import games, loc_arena, numerics  # noqa: E402,F401 -- loc_arena: the subsystem
from coco_lab import worldspec_v3 as v3  # noqa: E402
from coco_lab.arena import Arena, InputEvent, PLANNERS  # noqa: E402
from coco_lab.search import search  # noqa: E402
from coco_lab.sketch import _nearest_free  # noqa: E402
import make_fetch_rush_rounds_r3 as r3  # noqa: E402
from make_fetch_rush_rounds import arena, centre, replay, seeds_arg  # noqa: E402

LEVEL = 'coco_depot_v1'
RULES = 4
OUT = str(games.rounds_file(LEVEL, RULES))
HV = r3.HV
MAX_ATTEMPTS = r3.MAX_ATTEMPTS
PROVISIONAL_S = r3.PROVISIONAL_S


def path(a, g, frm, to):
    """A*'s route on the lane-masked plan grid ``g``: ``(length m, cell centres)``, or None."""
    s = _nearest_free(g, a.plan_map.cell_at(*frm))
    t = _nearest_free(g, a.plan_map.cell_at(*to))
    if s is None or t is None:
        return None
    r = search(g, s, t, **PLANNERS['astar'])
    if not r.found:
        return None
    return (r.cost * a.plan_map.resolution,
            [tuple(a.plan_map.cell_centre(c[0], c[1])) for c in r.path])


def crossing_runs(cells, rects):
    """
    The route's stretches inside the lanes: ``[(i, j, rect)]``, cells ``i..j`` inside ``rect``
    (``cells[i - 1]`` and ``cells[j + 1]`` are the mouths outside it, when they exist).
    """
    runs, i = [], 0
    while i < len(cells):
        rect = next((r for r in rects if games.in_rect(cells[i], r)), None)
        if rect is None:
            i += 1
            continue
        j = i
        while j + 1 < len(cells) and games.in_rect(cells[j + 1], rect):
            j += 1
        runs.append((i, j, rect))
        i = j + 1
    return runs


def crosses(cells, rects, bands):
    """
    Whether every stretch of ``cells`` inside a lane is a crossing: each cell on a band, and
    the stretch comes in on one side of the lane and leaves on the other. Returns
    ``(ok, mouths)`` -- mouths: per stretch, the cell before and the cell after it, each moved
    across onto the crossing band's centre line.
    """
    mouths = []
    for i, j, rect in crossing_runs(cells, rects):
        if i == 0 or j == len(cells) - 1:
            return False, []           # a route that starts or ends inside a lane
        if not all(any(games.in_rect(c, b) for b in bands) for c in cells[i:j + 1]):
            return False, []
        a, b = cells[i - 1], cells[j + 1]
        if games.lane_side(a, rect) == games.lane_side(b, rect):
            return False, []           # in and out on the same side: along, not across
        # the bot's goals: the mouths, moved onto the band's centre line (its waypoint
        # follower then stays on the stripes however it turns into the crossing)
        band = next(b for b in bands if games.in_rect(cells[i], b))
        mouths.append([games.on_band_centre(a, band, rect), games.on_band_centre(b, band, rect)])
    return True, mouths


def trips_from(a, g, assist, pool, drops, frm, rects, bands):
    """
    ``({oid: {drop: m}}, {oid: pose}, {(oid, drop): route}, {(oid, drop): [via there, via back]})``
    from ``frm``, every route keeping the crossing rule.
    """
    trips, poses, routes, vias = {}, {}, {}, {}
    for oid in pool:
        best = None
        for p in assist.approach_poses(a, assist.objects[oid]):
            got = path(a, g, frm, (p[0], p[1]))
            if got is None:
                continue
            ok, mouths = crosses(got[1], rects, bands)
            if not ok:
                continue
            if best is None or got[0] < best[1] - 1e-12:
                best = (p, got[0], got[1], mouths)
        if best is None:
            continue
        p, there, cells, there_via = best
        poses[oid] = [p[0], p[1], p[2]]
        trips[oid] = {}
        for d in drops:
            back = path(a, g, p[:2], centre(a, d))
            if back is None:
                continue
            ok, back_via = crosses(back[1], rects, bands)
            if not ok:
                continue
            trips[oid][d] = there + back[0]
            routes[(oid, d)] = r3.merged(cells) + r3.merged(back[1])[1:]
            vias[(oid, d)] = [[pt for m in there_via for pt in m], [pt for m in back_via for pt in m]]
        if not trips[oid]:
            del trips[oid]
    return trips, poses, routes, vias


def load_trips(a, g, assist, pool, drops, starts, rects, bands, cache=None, t0=None):
    """The rule-keeping trip table from every start and drop (``cache``: reuse or write it)."""
    t0 = time.time() if t0 is None else t0
    froms = dict(starts, **{d: centre(a, d) for d in drops})
    c = json.load(open(cache)) if cache and os.path.exists(cache) else {}
    trips, approach, routes, vias = {}, {}, {}, {}
    for f, p in sorted(froms.items()):
        if c.get('points', {}).get(f) == list(p):
            trips[f], approach[f] = c['trips'][f], c['approach'][f]
            routes[f] = {tuple(k.split('|')): v for k, v in c['routes'][f].items()}
            vias[f] = {tuple(k.split('|')): v for k, v in c['vias'][f].items()}
            continue
        trips[f], approach[f], routes[f], vias[f] = trips_from(a, g, assist, pool, drops, p,
                                                               rects, bands)
        print(f'trips from {f}: {sum(len(v) for v in trips[f].values())} '
              f'({time.time() - t0:.0f} s)', flush=True)
    if cache:
        json.dump({'points': {f: list(p) for f, p in froms.items()}, 'trips': trips,
                   'approach': approach,
                   'routes': {f: {'|'.join(k): v for k, v in r.items()} for f, r in routes.items()},
                   'vias': {f: {'|'.join(k): v for k, v in r.items()} for f, r in vias.items()}},
                  open(cache, 'w'))
    return trips, approach, routes, vias


def lane_violation(spec, record, rects, bands):
    """Why the robot's run (truth pose, every tick) breaks the crossing rule, or None."""
    a = Arena(spec, record['seed'], hash_version=record.get('hash_version', 1))
    by = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    inside, came_from, last_out = None, None, None
    for _ in range(record['ticks']):
        a.step(by.get(a.tick, ()))
        xy = a.pose[:2]
        rect = next((r for r in rects if games.in_rect(xy, r)), None)
        if rect is not None:
            if not any(games.in_rect(xy, b) for b in bands):
                return f'stood in the lane off a crossing at ({xy[0]:.2f}, {xy[1]:.2f})'
            if inside is None:
                inside, came_from = rect, games.lane_side(last_out, rect) if last_out else None
        else:
            if inside is not None and came_from is not None \
                    and games.lane_side(xy, inside) == came_from:
                return f'left a crossing on the side it came in at ({xy[0]:.2f}, {xy[1]:.2f})'
            inside = None
            last_out = xy
    return None


def make_round(spec, a, starts, approach, trips, routes, vias, rects, bands, mode, m, sd):
    """
    One seed's accepted round in ``mode`` (``m``: orders, budget): rules 3's draw, start and
    reference, with the rules-4 bot (through each order's crossing mouths) and the crossing
    rule as the rejection test.
    """
    rejected = []
    for attempt in range(MAX_ATTEMPTS):
        drawn = games.draw_round(sd, trips, m['budget_m'], m['orders'], attempt)
        sx, sy = starts[drawn['region']]
        rnd = {'region': drawn['region'], 'orders': drawn['orders'], 'attempt': attempt,
               'start': None, 'ghost_m': [], 'routes': [], 'pick': [], 'via': []}
        frm = drawn['region']
        for oid, drop in drawn['orders']:
            rnd['ghost_m'].append(trips[frm][oid][drop])
            rnd['routes'].append(routes[frm][(oid, drop)])
            rnd['pick'].append(approach[frm][oid])
            rnd['via'].append(vias[frm][(oid, drop)])
            frm = drop
        rnd['start'] = [sx, sy, r3.facing(a, sx, sy, rnd['routes'][0])]
        rules = games.FetchRushRound(sd, rnd, seconds=PROVISIONAL_S, rules=RULES, mode=mode)
        rec, res = games.bot_fetch_rush(spec, sd, rules=rules, hash_version=HV)
        card = res['scorecard']
        why = None
        if card['deliveries'] < m['orders']:
            why = f"the bot delivered {card['deliveries']} of {m['orders']}"
        else:
            why = lane_violation(spec, rec, rects, bands)
            why = None if why is None else f'the bot {why}'
        if why:
            rejected.append({'attempt': attempt, 'region': rnd['region'],
                             'orders': rnd['orders'], 'why': why})
            print(f'{mode} seed {sd} attempt {attempt}: rejected ({why})', flush=True)
            continue
        t_ref = card['delivered'][-1]['t']
        rnd['reference_time_s'] = t_ref
        rnd['timer_s'] = round(t_ref * games.ROUND_TIMER_FACTOR, 1)
        final = replay(spec, rec, games.FetchRushRound(sd, rnd, rules=RULES, mode=mode))
        rnd['reference'] = {'record': rec, 'card': final['scorecard'],
                            'hash_chain': final['hash_chain']}
        rnd['rejected'] = rejected
        return rnd
    raise SystemExit(f'{mode} seed {sd}: no accepted round in {MAX_ATTEMPTS} draws')


def setup(spec, cache=None):
    """Everything a round needs: ``(a, starts, approach, trips, routes, vias, rects, bands)``."""
    a = arena(spec)
    assist = a.subsystems['assist']
    pool = games.pickable(a, assist)
    drops = sorted(z['id'] for z in v3.zones(a.spec, 'drop'))
    starts = r3.start_points(a)
    rects = r3.lanes(a)
    windows = games.crossing_windows(a)
    bands = [tuple(w['band']) for w in windows if w['open']]   # the crossings a route may use
    g = games.lane_grid(a, bands=bands)
    trips, approach, routes, vias = load_trips(a, g, assist, pool, drops, starts, rects, bands,
                                               cache)
    return a, starts, approach, trips, routes, vias, rects, bands, windows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seeds', default='1-6')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--trips-cache', help='reuse (or write) the trip table here (it takes minutes)')
    ap.add_argument('--modes', default=','.join(sorted(games.ROUND_MODES_R4)))
    o = ap.parse_args()
    spec_path = os.path.join(REPO, 'worlds', f'{LEVEL}.json')
    spec = json.load(open(spec_path))
    spec_sha = hashlib.sha256(open(spec_path, 'rb').read()).hexdigest()
    t0 = time.time()
    a, starts, approach, trips, routes, vias, rects, bands, windows = setup(spec, o.trips_cache)
    out = {}
    for mode, m in sorted(games.ROUND_MODES_R4.items()):
        if mode not in o.modes.split(','):
            continue
        out[mode] = {}
        for sd in seeds_arg(o.seeds):
            rnd = make_round(spec, a, starts, approach, trips, routes, vias, rects, bands,
                             mode, m, sd)
            out[mode][str(sd)] = rnd
            print(f"{mode} seed {sd}: {rnd['region']} {rnd['orders']} ghost "
                  f"{[round(x, 1) for x in rnd['ghost_m']]} ref {rnd['reference_time_s']:.1f} s "
                  f"timer {rnd['timer_s']} s ({time.time() - t0:.0f} s)", flush=True)
    doc = {'about': 'G2.1: Fetch Rush rules 4 rounds (tools/g2/make_fetch_rush_rounds_r4.py)',
           'level': LEVEL, 'spec_sha256': spec_sha, 'rules': RULES,
           'modes': games.ROUND_MODES_R4, 'default_mode': games.ROUND_MODE_DEFAULT,
           'timer_factor': games.ROUND_TIMER_FACTOR, 'hash_version': HV,
           'lanes': list(games.ROUND_LANES),
           'crossings': [list(r) for r in games.crossings(a.spec)],
           'crossing_bands': [list(b) for b in games.crossing_bands(a.spec)],
           'crossing_windows': windows,
           'starts': {k: list(v) for k, v in starts.items()},
           'trips': trips, 'approach': approach, 'rounds': out}
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write('\n')
    print('wrote', o.out, f'{time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    with numerics.version(HV):
        code = main()
    sys.exit(code)
