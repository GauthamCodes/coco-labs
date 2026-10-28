#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.1: choose the Fetch Rush rules-4 phone-round budget (Gautham, 2026-10-23).

    tools/g2/sweep_phone_budget_r4.py --trips-cache PATH [--from 22] [--to M]
                                      [--max-timer 300] [--out JSON]

The decision: with the crossing rule (routes cross the forklift lane only at a marked
crossing), the smallest budget giving at least 3 distinct rounds with timers <= 5:00, or
<= 6:00 if 5:00 is impossible. This is G1.13's sweep (``tools/g1/sweep_phone_budget.py``:
whole metres from 22 m, seeds 1-6, attempt-0 draws, "distinct" = distinct (start zone,
orders) among the accepted rounds, a budget fails at the first timer over the limit) with
rules 4's trip table and generator (``make_fetch_rush_rounds_r4``). Run it with
``--max-timer 300``; only when no budget qualifies, again with ``--max-timer 360``.
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fetch_rush_rounds_r4 as r4  # noqa: E402
from coco_lab import games, numerics  # noqa: E402

MIN_ROUNDS = 3
SEEDS = range(1, 7)


def _key(d):
    return json.dumps([d['region'], d['orders']])


def _planned(trips, d):
    frm, total = d['region'], 0.0
    for oid, drop in d['orders']:
        total += trips[frm][oid][drop]
        frm = drop
    return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--trips-cache', required=True)
    ap.add_argument('--from', dest='lo', type=int, default=22)
    ap.add_argument('--to', dest='hi', type=int)
    ap.add_argument('--max-timer', type=float, default=300.0)
    ap.add_argument('--out')
    o = ap.parse_args()
    spec = json.load(open(os.path.join(r4.REPO, 'worlds', f'{r4.LEVEL}.json')))
    a, starts, approach, trips, routes, vias, rects, bands, windows = r4.setup(spec, o.trips_cache)
    longest = max(v for f in trips.values() for d in f.values() for v in d.values())
    hi = o.hi if o.hi is not None else int(math.ceil(longest))
    played, rows, chosen = {}, [], None
    t0 = time.time()
    for b in range(o.lo, hi + 1):
        m = {'orders': 2, 'budget_m': float(b)}
        try:
            drawn = {sd: games.draw_round(sd, trips, m['budget_m'], 2, 0) for sd in SEEDS}
        except games.ArenaError as e:
            rows.append({'budget_m': b, 'qualifies': False, 'failed_on': str(e)})
            print(f'{b} m: {e}', flush=True)
            continue
        plan = {sd: _planned(trips, d) for sd, d in drawn.items()}
        row = {'budget_m': b, 'drawn_distinct': len({_key(d) for d in drawn.values()}),
               'planned_m': {sd: round(v, 1) for sd, v in plan.items()}, 'seeds': {}}
        ok = True
        for sd in sorted(SEEDS, key=lambda s: (-plan[s], s)):
            k = (sd, _key(drawn[sd]))
            if k in played and played[k]['rejected'] and played[k]['budget_m'] != b:
                del played[k]   # a redrawn round depends on the budget: play it again
            if k not in played:
                rnd = r4.make_round(spec, a, starts, approach, trips, routes, vias, rects, bands,
                                    'phone', m, sd)
                played[k] = {'region': rnd['region'], 'orders': rnd['orders'],
                             'attempt': rnd['attempt'], 'start': rnd['start'],
                             'ghost_m': rnd['ghost_m'], 'rejected': len(rnd['rejected']),
                             'rejections': [r['why'] for r in rnd['rejected']],
                             'reference_time_s': rnd['reference_time_s'],
                             'timer_s': rnd['timer_s'], 'budget_m': b}
                print(f"  {b} m seed {sd}: {rnd['region']} {rnd['orders']} timer "
                      f"{rnd['timer_s']} s ({time.time() - t0:.0f} s)", flush=True)
            row['seeds'][sd] = played[k]
            if played[k]['timer_s'] > o.max_timer:
                ok = False
                row['failed_on'] = f"seed {sd}: timer {played[k]['timer_s']} s > {o.max_timer:.0f} s"
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
    doc = {'about': 'G2.1: rules-4 phone-round budget sweep (tools/g2/sweep_phone_budget_r4.py)',
           'rule': f'smallest whole-metre budget from {o.lo} m with >= {MIN_ROUNDS} distinct '
                   f'rounds (seeds 1-6) and every timer <= {o.max_timer:.0f} s, routes crossing '
                   f'the forklift lane only at a marked crossing',
           'max_timer_s': o.max_timer, 'swept_to_m': hi, 'longest_trip_m': round(longest, 2),
           'chosen_budget_m': chosen, 'qualified': chosen is not None,
           'crossings': [list(r) for r in games.crossings(a.spec)],
           'crossing_bands': [list(x) for x in games.crossing_bands(a.spec)],
           'crossing_windows': windows, 'open_bands': [list(x) for x in bands], 'budgets': rows,
           'seconds': round(time.time() - t0, 1)}
    if o.out:
        with open(o.out, 'w') as f:
            json.dump(doc, f, indent=1, sort_keys=True)
            f.write('\n')
    print('chosen', doc['chosen_budget_m'], 'qualified', doc['qualified'])
    return 0


if __name__ == '__main__':
    with numerics.version(r4.HV):
        code = main()
    sys.exit(code)
