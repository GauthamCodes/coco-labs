#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.12: Fetch Rush rules 3 -- the level's precomputed rounds, phone and full shift.

    tools/g1/make_fetch_rush_rounds_r3.py [--seeds 1-6] [--out PATH]

Writes ``coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r3.json`` (rules 2's file,
``make_fetch_rush_rounds.py``'s, is left as it is: rules-2 records replay on it).
Gautham's 2026-10-22 decisions:

- ``trips[frm][oid][drop]``: the planned round trip (m) from ``frm`` (a start zone's
  start point, or a drop zone's centre) to the object's nearest pre-grasp pose BY A
  ROUTE THAT KEEPS OUT OF THE FORKLIFT LANES, then to the drop zone's centre, also
  outside them. A route is A*'s cells on the Arena's plan grid (what AUTO and the
  reference bot drive); one with a cell centre inside a lane zone (``ROUND_LANES``)
  does not count, so an order that cannot be reached without the lanes is never
  drawn.
- per mode (``games.ROUND_MODES``: phone = 2 orders within 16 m, full = 3 within
  32 m) and seed: ``games.draw_round`` over that table, then the reference bot plays
  it. A round is REJECTED when the bot does not deliver every order, or when the
  robot ever stands inside a lane; the seed then draws again (``attempt`` 1, 2, ...)
  until one is accepted. Rejected draws are listed (``rejected``), never offered.
- each accepted round: the start pose (the zone's roomiest free cell, facing the open
  aisle: the free direction with the longest clear run on the plan grid), each order's ghost length and route,
  ``reference_time_s``, ``timer_s`` = that x ``games.ROUND_TIMER_FACTOR``, and the
  reference record, card and hash chain under that timer.
"""
import argparse
import hashlib
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coco_lab import games, loc_arena, numerics  # noqa: E402,F401 -- loc_arena: the subsystem
from coco_lab import worldspec_v3 as v3  # noqa: E402
from coco_lab.arena import PLANNERS  # noqa: E402
from coco_lab.numerics import math  # noqa: E402
from coco_lab.search import search  # noqa: E402
from coco_lab.sketch import _nearest_free  # noqa: E402
from make_fetch_rush_rounds import arena, centre, replay, seeds_arg  # noqa: E402

LEVEL = 'coco_depot_v1'
OUT = str(games.rounds_file(LEVEL, 3))
PROVISIONAL_S = 1100.0
HV = 3
MAX_ATTEMPTS = 40
#: a start point keeps this far (m) from the forklift lanes (an actor passing close at tick 0)
LANE_CLEAR = 1.5


def lanes(a):
    return [games.zone_rect(a.spec, z) for z in games.ROUND_LANES]


def in_lanes(xy, rects) -> bool:
    return any(r[0] <= xy[0] <= r[1] and r[2] <= xy[1] <= r[3] for r in rects)


def in_lanes_pad(xy, rects, pad) -> bool:
    return any(r[0] - pad <= xy[0] <= r[1] + pad and r[2] - pad <= xy[1] <= r[3] + pad for r in rects)


def path(a, frm, to):
    """A*'s route on the plan grid: ``(length m, cell centres)``, or None."""
    s = _nearest_free(a.grid, a.plan_map.cell_at(*frm))
    t = _nearest_free(a.grid, a.plan_map.cell_at(*to))
    if s is None or t is None:
        return None
    r = search(a.grid, s, t, **PLANNERS['astar'])
    if not r.found:
        return None
    return (r.cost * a.plan_map.resolution,
            [tuple(a.plan_map.cell_centre(c[0], c[1])) for c in r.path])


def merged(pts):
    """Straight runs merged (for drawing)."""
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        d0 = (pts[i][0] - keep[-1][0], pts[i][1] - keep[-1][1])
        d1 = (pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        if abs(d0[0] * d1[1] - d0[1] * d1[0]) > 1e-9:
            keep.append(pts[i])
    keep.append(pts[-1])
    return [[round(x, 3), round(y, 3)] for x, y in keep]


def trips_from(a, assist, pool, drops, frm, rects):
    """``({oid: {drop: m}}, {oid: pose}, {(oid, drop): route})`` from ``frm``, lanes kept out."""
    trips, poses, routes = {}, {}, {}
    for oid in pool:
        best = None
        for p in assist.approach_poses(a, assist.objects[oid]):
            got = path(a, frm, (p[0], p[1]))
            if got is None or any(in_lanes(c, rects) for c in got[1]):
                continue
            if best is None or got[0] < best[1] - 1e-12:
                best = (p, got[0], got[1])
        if best is None:
            continue
        p, there, cells = best
        poses[oid] = [p[0], p[1], p[2]]
        trips[oid] = {}
        for d in drops:
            back = path(a, p[:2], centre(a, d))
            if back is None or any(in_lanes(c, rects) for c in back[1]):
                continue
            trips[oid][d] = there + back[0]
            routes[(oid, d)] = merged(cells) + merged(back[1])[1:]
        if not trips[oid]:
            del trips[oid]
    return trips, poses, routes


def start_points(a):
    """
    A start zone's start point (G1.12): the free plan-grid cell inside the zone, at least
    LANE_CLEAR from the forklift lanes, with the most room around it (8-connected distance to the nearest blocked cell; ties: nearest the zone's
    centre), so COCO -- and the chase camera behind it -- never starts hugging a stack or a wall.
    """
    from collections import deque
    g = a.grid
    w, h = g.width, g.height
    dist = [-1] * (w * h)
    q = deque()
    for i in range(w * h):
        if g.is_blocked((i // w, i % w)):
            dist[i] = 0
            q.append(i)
    while q:
        i = q.popleft()
        r, c = divmod(i, w)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and dist[rr * w + cc] < 0:
                    dist[rr * w + cc] = dist[i] + 1
                    q.append(rr * w + cc)
    out = {}
    rects = lanes(a)
    for z in a.spec['kit']:
        if z.get('kind') != 'zone' or z['role'] != 'region' or z['id'] in games.ROUND_NO_START:
            continue
        x0, x1, y0, y1 = games.zone_rect(a.spec, z['id'])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        best = None
        for i, d in enumerate(dist):
            if d <= 0:
                continue
            x, y = a.plan_map.cell_centre(i // w, i % w)
            if not (x0 <= x <= x1 and y0 <= y <= y1) or in_lanes_pad((x, y), rects, LANE_CLEAR):
                continue
            key = (-d, (x - cx) ** 2 + (y - cy) ** 2)
            if best is None or key < best[0]:
                best = (key, (x, y))
        if best is not None:
            out[z['id']] = best[1]
    return out


def facing(a, sx, sy):
    """The heading of the longest clear run from the start (16 directions, plan grid)."""
    best = None
    for k in range(16):
        th = k * math.pi / 8
        d = 0.0
        while d < 30.0:
            c = a.plan_map.cell_at(sx + (d + 0.1) * math.cos(th), sy + (d + 0.1) * math.sin(th))
            if c is None or a.grid.is_blocked(c):
                break
            d += 0.1
        if best is None or d > best[1] + 1e-9:
            best = (th, d)
    return best[0]


def drove_into_lanes(spec, record, rects) -> bool:
    """Whether the robot (truth pose) ever stands inside a lane in the record."""
    from coco_lab.arena import Arena, InputEvent
    a = Arena(spec, record['seed'], hash_version=record.get('hash_version', 1))
    by = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    for _ in range(record['ticks']):
        a.step(by.get(a.tick, ()))
        if in_lanes(a.pose[:2], rects):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--seeds', default='1-6')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--trips-cache', help='reuse (or write) the trip table here (it takes ~7 min)')
    ap.add_argument('--modes', default=','.join(sorted(games.ROUND_MODES)))
    o = ap.parse_args()
    spec_path = os.path.join(REPO, 'worlds', f'{LEVEL}.json')
    spec = json.load(open(spec_path))
    spec_sha = hashlib.sha256(open(spec_path, 'rb').read()).hexdigest()
    a = arena(spec)
    assist = a.subsystems['assist']
    pool = games.pickable(a, assist)
    drops = sorted(z['id'] for z in v3.zones(a.spec, 'drop'))
    starts = start_points(a)
    rects = lanes(a)
    t0 = time.time()
    froms = dict(starts, **{d: centre(a, d) for d in drops})
    c = json.load(open(o.trips_cache)) if o.trips_cache and os.path.exists(o.trips_cache) else {}
    trips, approach, routes = {}, {}, {}
    for f, p in sorted(froms.items()):
        if c.get('points', {}).get(f) == list(p):   # the cache, where its point is this one
            trips[f], approach[f] = c['trips'][f], c['approach'][f]
            routes[f] = {tuple(k.split('|')): v for k, v in c['routes'][f].items()}
            continue
        trips[f], approach[f], routes[f] = trips_from(a, assist, pool, drops, p, rects)
        print(f'trips from {f}: {sum(len(v) for v in trips[f].values())} '
              f'({time.time() - t0:.0f} s)', flush=True)
    if o.trips_cache:
        json.dump({'points': {f: list(p) for f, p in froms.items()}, 'trips': trips,
                   'approach': approach,
                   'routes': {f: {'|'.join(k): v for k, v in r.items()}
                              for f, r in routes.items()}},
                  open(o.trips_cache, 'w'))
    out = {}
    for mode, m in sorted(games.ROUND_MODES.items()):
        if mode not in o.modes.split(','):
            continue
        out[mode] = {}
        for sd in seeds_arg(o.seeds):
            rejected = []
            for attempt in range(MAX_ATTEMPTS):
                drawn = games.draw_round(sd, trips, m['budget_m'], m['orders'], attempt)
                sx, sy = starts[drawn['region']]
                rnd = {'region': drawn['region'], 'orders': drawn['orders'], 'attempt': attempt,
                       'start': [sx, sy, facing(a, sx, sy)], 'ghost_m': [], 'routes': []}
                frm = drawn['region']
                for oid, drop in drawn['orders']:
                    rnd['ghost_m'].append(trips[frm][oid][drop])
                    rnd['routes'].append(routes[frm][(oid, drop)])
                    frm = drop
                rules = games.FetchRushRound(sd, rnd, seconds=PROVISIONAL_S, rules=3, mode=mode)
                rec, res = games.bot_fetch_rush(spec, sd, rules=rules, hash_version=HV)
                card = res['scorecard']
                why = None
                if card['deliveries'] < m['orders']:
                    why = f"the bot delivered {card['deliveries']} of {m['orders']}"
                elif drove_into_lanes(spec, rec, rects):
                    why = 'the bot drove into a forklift lane'
                if why:
                    rejected.append({'attempt': attempt, 'region': rnd['region'],
                                     'orders': rnd['orders'], 'why': why})
                    print(f'{mode} seed {sd} attempt {attempt}: rejected ({why})', flush=True)
                    continue
                t_ref = card['delivered'][-1]['t']
                rnd['reference_time_s'] = t_ref
                rnd['timer_s'] = round(t_ref * games.ROUND_TIMER_FACTOR, 1)
                final = replay(spec, rec, games.FetchRushRound(sd, rnd, rules=3, mode=mode))
                rnd['reference'] = {'record': rec, 'card': final['scorecard'],
                                    'hash_chain': final['hash_chain']}
                rnd['rejected'] = rejected
                out[mode][str(sd)] = rnd
                print(f"{mode} seed {sd}: {rnd['region']} {rnd['orders']} ghost "
                      f"{[round(g, 1) for g in rnd['ghost_m']]} ref {t_ref:.1f} s timer "
                      f"{rnd['timer_s']} s ({time.time() - t0:.0f} s)", flush=True)
                break
            else:
                raise SystemExit(f'{mode} seed {sd}: no accepted round in {MAX_ATTEMPTS} draws')
    doc = {'about': 'G1.12: Fetch Rush rules 3 rounds (tools/g1/make_fetch_rush_rounds_r3.py)',
           'level': LEVEL, 'spec_sha256': spec_sha, 'rules': 3,
           'modes': games.ROUND_MODES, 'default_mode': games.ROUND_MODE_DEFAULT,
           'timer_factor': games.ROUND_TIMER_FACTOR, 'hash_version': HV,
           'lanes': list(games.ROUND_LANES),
           'starts': {k: list(v) for k, v in starts.items()},
           'trips': trips, 'approach': approach, 'rounds': out}
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write('\n')
    print('wrote', o.out, f'{time.time() - t0:.0f} s')
    return 0


if __name__ == '__main__':
    with numerics.version(HV):   # the routes' searches run outside the Arena's own calls
        code = main()
    sys.exit(code)
