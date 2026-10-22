#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.13: choose the Fetch Rush phone-round budget (Gautham, 2026-10-22).

    tools/g1/sweep_phone_budget.py --trips-cache PATH [--from 22] [--to M] [--out JSON]

The decision: the smallest budget, from 22 m up (whole metres), that gives at least 3
distinct rounds with every timer <= 5:00; if none does, 22 m. Per budget (every whole metre
up to the table's longest trip, beyond which the draws cannot change):

1. the draws (``games.draw_round``, attempt 0, seeds 1-6) and their planned lengths;
2. ``make_fetch_rush_rounds_r3.make_round`` -- the generator's own draw, reference bot,
   rejection and timer -- per seed, the longest planned round first; the budget fails at
   the first timer over 5:00 (the remaining seeds are not needed and not played), else
   when its accepted rounds are fewer than 3 distinct.

A seed's accepted round is cached by (seed, its attempt-0 draw), so a budget that draws
what an earlier one drew reuses that result (same seed, same round, same start: the same
deterministic run; a round redrawn after a rejection is reused only at its own budget). It stops at the first budget that qualifies.
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fetch_rush_rounds_r3 as r3  # noqa: E402
from coco_lab import games, numerics  # noqa: E402
from coco_lab import worldspec_v3 as v3  # noqa: E402

MIN_ROUNDS = 3
MAX_TIMER_S = 300.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--trips-cache', required=True)
    ap.add_argument('--from', dest='lo', type=int, default=22)
    ap.add_argument('--to', dest='hi', type=int)
    ap.add_argument('--out')
    o = ap.parse_args()
    spec = json.load(open(os.path.join(r3.REPO, 'worlds', f'{r3.LEVEL}.json')))
    a = r3.arena(spec)
    assist = a.subsystems['assist']
    pool = games.pickable(a, assist)
    drops = sorted(z['id'] for z in v3.zones(a.spec, 'drop'))
    starts = r3.start_points(a)
    rects = r3.lanes(a)
    trips, _, routes = r3.load_trips(a, assist, pool, drops, starts, rects, o.trips_cache)
    longest = max(v for f in trips.values() for d in f.values() for v in d.values())
    hi = o.hi if o.hi is not None else int(math.ceil(longest))
    played, rows, chosen = {}, [], None
    t0 = time.time()
    for b in range(o.lo, hi + 1):
        m = {'orders': 2, 'budget_m': float(b)}
        drawn = {sd: games.draw_round(sd, trips, m['budget_m'], 2, 0) for sd in SEEDS}
        plan = {sd: _planned(trips, d) for sd, d in drawn.items()}
        row = {'budget_m': b, 'drawn_distinct': len({_key(d) for d in drawn.values()}),
               'planned_m': {sd: round(v, 1) for sd, v in plan.items()}, 'seeds': {}}
        ok = True
        for sd in sorted(SEEDS, key=lambda s: (-plan[s], s)):
            k = (sd, _key(drawn[sd]))
            if k in played and played[k]['rejected'] and played[k]['budget_m'] != b:
                del played[k]   # a redrawn round depends on the budget: play it again
            if k not in played:
                rnd = r3.make_round(spec, a, starts, trips, routes, rects, 'phone', m, sd)
                played[k] = {'region': rnd['region'], 'orders': rnd['orders'],
                             'attempt': rnd['attempt'], 'start': rnd['start'],
                             'ghost_m': rnd['ghost_m'], 'rejected': len(rnd['rejected']),
                             'reference_time_s': rnd['reference_time_s'],
                             'timer_s': rnd['timer_s'], 'budget_m': b}
                print(f"  {b} m seed {sd}: {rnd['region']} {rnd['orders']} timer "
                      f"{rnd['timer_s']} s ({time.time() - t0:.0f} s)", flush=True)
            row['seeds'][sd] = played[k]
            if played[k]['timer_s'] > MAX_TIMER_S:
                ok = False
                row['failed_on'] = f"seed {sd}: timer {played[k]['timer_s']} s > {MAX_TIMER_S:.0f} s"
                break
        accepted = {_key(r) for r in row['seeds'].values()}
        if ok:
            row['distinct_rounds'] = len(accepted)
            ok = len(accepted) >= MIN_ROUNDS
            if not ok:
                row['failed_on'] = f'{len(accepted)} distinct round(s) < {MIN_ROUNDS}'
        row['max_timer_s'] = max(r['timer_s'] for r in row['seeds'].values())
        row['qualifies'] = ok
        rows.append(row)
        print(f"{b} m: drawn {row['drawn_distinct']} distinct; "
              f"{'QUALIFIES' if ok else row['failed_on']}", flush=True)
        if ok:
            chosen = b
            break
    doc = {'about': 'G1.13: phone-round budget sweep (tools/g1/sweep_phone_budget.py)',
           'rule': f'smallest whole-metre budget from {o.lo} m with >= {MIN_ROUNDS} distinct '
                   f'rounds (seeds 1-6) and every timer <= {MAX_TIMER_S:.0f} s; else 22 m',
           'swept_to_m': hi, 'longest_trip_m': round(longest, 2),
           'chosen_budget_m': chosen if chosen is not None else 22,
           'qualified': chosen is not None, 'budgets': rows}
    if o.out:
        with open(o.out, 'w') as f:
            json.dump(doc, f, indent=1, sort_keys=True)
            f.write('\n')
    print('chosen', doc['chosen_budget_m'], 'qualified', doc['qualified'])
    return 0


SEEDS = range(1, 7)


def _key(d):
    return json.dumps([d['region'], d['orders']])


def _planned(trips, d):
    frm, total = d['region'], 0.0
    for oid, drop in d['orders']:
        total += trips[frm][oid][drop]
        frm = drop
    return total


if __name__ == '__main__':
    with numerics.version(r3.HV):
        code = main()
    sys.exit(code)
