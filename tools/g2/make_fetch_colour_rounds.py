#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Fetch by colour (owner request 2026-10-24): the four colours' rounds and reference runs.

    tools/g2/make_fetch_colour_rounds.py [--check] [--out PATH]

Writes ``coco_lab/coco_lab/levels/coco_depot_colours_v1.fetch_colour.json`` (one command; re-run
it after a change to the rules -- e.g. adopting Fetch Rush rules 5's actors through
``games.FETCH_COLOUR_ACTOR_RULES`` -- and commit the file). ``--check`` regenerates and exits 1
if the committed file differs. Per colour (``games.FETCH_COLOURS``), on
``worlds/coco_depot_colours_v1.json`` (the Depot plus a row of four rods):

- the order: the colour's rod (``games.FETCH_COLOUR_RODS``) to Dispatch
  (``games.FETCH_COLOUR_DROP``);
- the start: COCO's start pad (the level's ``start`` x, y), facing the row (north, pi/2), so the
  four rods are in view when the round begins; the same start for every colour;
- the pick: the rod's free pre-grasp pose nearest the start by plan (``games.best_approach``);
- the ghost: A*'s route on the Arena's plan grid from the start to the pick, then to Dispatch's
  centre (``ghost_m`` its length; ``routes`` the cells, straight runs merged, for drawing);
- the reference: ``games.bot_fetch_colour`` plays it (the planner plus Grasp Assist, yielding to
  the actors) with time to spare; its delivery time x ``games.ROUND_TIMER_FACTOR`` (Fetch Rush's
  1.5), rounded to 0.1 s, is the timer; its record, card and hash chain under that timer are the
  stars' reference. A colour the bot does not deliver stops the generator (no timer is invented).
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
from coco_lab.numerics import math  # noqa: E402
from make_fetch_rush_rounds import arena, centre, replay  # noqa: E402
import make_fetch_rush_rounds_r3 as r3  # noqa: E402

LEVEL = games.FETCH_COLOUR_LEVEL
RULES = games.FETCH_COLOUR_RULES
OUT = str(games.colour_rounds_file(LEVEL))
HV = 3
#: the bot's first run plays to the delivery with this much time (under the link tick limit)
PROVISIONAL_S = 600.0
#: the start faces the row of rods (north)
START_HEADING = math.pi / 2


def make_round(spec, a, colour):
    """One colour's round: order, start, pick, ghost, the reference run and its timer."""
    assist = a.subsystems['assist']
    oid, drop = games.FETCH_COLOUR_RODS[colour], games.FETCH_COLOUR_DROP
    dx, dy = a.spec['world_to_map']
    sx, sy = spec['start']['x'] + dx, spec['start']['y'] + dy
    pick, there = games.best_approach(a, assist, oid, (sx, sy))
    leg1 = r3.path(a, (sx, sy), pick[:2])
    leg2 = r3.path(a, pick[:2], centre(a, drop))
    assert abs(leg1[0] - there) < 1e-9, 'best_approach and the drawn route disagree'
    lanes = r3.lanes(a)
    if any(r3.in_lanes(c, lanes) for c in leg1[1] + leg2[1]):
        raise SystemExit(f'{colour}: the planned route enters the forklift lane')
    o = assist.objects[oid]
    rnd = {'region': 'start_pad', 'colour': colour, 'object': oid, 'item': o['item'],
           'diameter': o['diameter'], 'orders': [[oid, drop]], 'attempt': 0,
           'start': [sx, sy, START_HEADING], 'ghost_m': [leg1[0] + leg2[0]],
           'routes': [r3.merged(leg1[1]) + r3.merged(leg2[1])[1:]],
           'pick': [[pick[0], pick[1], pick[2]]], 'via': [[[], []]]}
    rules = games.FetchColour(colour, rnd, seconds=PROVISIONAL_S)
    rec, res = games.bot_fetch_colour(spec, colour, rules=rules, hash_version=HV)
    card = res['scorecard']
    if card['deliveries'] < 1:
        raise SystemExit(f'{colour}: the reference bot did not deliver the rod; no timer')
    if r3.drove_into_lanes(spec, rec, lanes):
        raise SystemExit(f'{colour}: the reference bot stood in the forklift lane')
    t_ref = card['delivered'][-1]['t']
    rnd['reference_time_s'] = t_ref
    rnd['timer_s'] = round(t_ref * games.ROUND_TIMER_FACTOR, 1)
    final = replay(spec, rec, games.FetchColour(colour, rnd))
    rnd['reference'] = {'record': rec, 'card': final['scorecard'],
                        'hash_chain': final['hash_chain']}
    return rnd


def build(spec_path):
    """Build the rounds document for every colour."""
    spec = json.load(open(spec_path))
    spec_sha = hashlib.sha256(open(spec_path, 'rb').read()).hexdigest()
    a = arena(spec)
    t0 = time.time()
    rounds = {}
    for colour in games.FETCH_COLOURS:
        rnd = make_round(spec, a, colour)
        rounds[colour] = rnd
        c = rnd['reference']['card']
        print(f"{colour}: {rnd['object']} ghost {rnd['ghost_m'][0]:.2f} m, reference "
              f"{rnd['reference_time_s']:.1f} s ({c['contacts']} contacts, path efficiency "
              f"{c['path_efficiency']:.3f}), timer {rnd['timer_s']} s ({time.time() - t0:.0f} s)",
              flush=True)
    return {'about': 'Fetch by colour rounds (owner request 2026-10-24; '
                     'tools/g2/make_fetch_colour_rounds.py)',
            'level': LEVEL, 'spec_sha256': spec_sha, 'rules': RULES,
            'actor_rules': games.FETCH_COLOUR_ACTOR_RULES[RULES],
            'colours': list(games.FETCH_COLOURS), 'drop': games.FETCH_COLOUR_DROP,
            'timer_factor': games.ROUND_TIMER_FACTOR, 'hash_version': HV,
            'evidence': 'MODEL', 'rounds': rounds}


def dumps(doc) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--check', action='store_true')
    o = ap.parse_args()
    text = dumps(build(os.path.join(REPO, 'worlds', f'{LEVEL}.json')))
    if o.check:
        same = open(o.out).read() == text
        print(os.path.basename(o.out), 'current' if same else 'DIFFERS: regenerate')
        return 0 if same else 1
    with open(o.out, 'w') as f:
        f.write(text)
    print('wrote', o.out)
    return 0


if __name__ == '__main__':
    with numerics.version(HV):
        code = main()
    sys.exit(code)
