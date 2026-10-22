# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.12: Fetch Rush rules 3 -- phone rounds and the Full shift (Gautham, 2026-10-22).

The rounds file (``coco_lab/levels/coco_depot_v1.fetch_rush.r3.json``) is written by
``tools/g1/make_fetch_rush_rounds_r3.py``; these tests check it against the level and
the decisions: per mode, the orders and budget; no planned route enters the forklift
lanes; every round on file was finished by the reference bot (a round it could not
finish was rejected at generation, never offered); timer = reference x 1.5.
"""
import hashlib
import json
from pathlib import Path

from coco_lab import games, loc_arena  # noqa: F401 -- loc_arena: the subsystem
from coco_lab.arena import Arena, ArenaError, InputEvent
import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / 'worlds' / 'coco_depot_v1.json'
SPEC = json.loads(SPEC_PATH.read_text())
DOC = games.load_rounds(rules=3)
ROUNDS = [(mode, seed) for mode in sorted(DOC['rounds'])
          for seed in sorted(DOC['rounds'][mode], key=int)]


def test_the_rounds_are_for_this_level_and_these_rules():
    assert DOC['spec_sha256'] == hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert DOC['rules'] == games.FETCH_RUSH_RULES == 3
    assert DOC['modes'] == games.ROUND_MODES
    # the decision's 16 m admits no lane-free 2-order round on the Depot
    # (docs/v2/g1/data/g112/phone_budget.json)
    assert games.ROUND_MODES['phone'] == {'orders': 2, 'budget_m': 22.0}
    assert games.ROUND_MODES['full'] == {'orders': 3, 'budget_m': 32.0}
    assert DOC['default_mode'] == games.ROUND_MODE_DEFAULT == 'phone'
    assert DOC['timer_factor'] == games.ROUND_TIMER_FACTOR == 1.5
    assert DOC['lanes'] == list(games.ROUND_LANES)
    # every shift is offered in both modes
    assert {m: sorted(DOC['rounds'][m], key=int) for m in DOC['rounds']} == \
        {'full': ['1', '2', '3', '4', '5', '6'], 'phone': ['1', '2', '3', '4', '5', '6']}


def _lanes():
    return [games.zone_rect(SPEC_V3, z) for z in games.ROUND_LANES]


SPEC_V3 = Arena(SPEC, 1).spec      # normalized (map frame), as the rules see it


def _inside(p, rects, pad=0.0):
    return any(r[0] - pad <= p[0] <= r[1] + pad and r[2] - pad <= p[1] <= r[3] + pad
               for r in rects)


@pytest.mark.parametrize('mode,seed', ROUNDS)
def test_each_round_keeps_the_decisions(mode, seed):
    m = games.ROUND_MODES[mode]
    rnd = DOC['rounds'][mode][seed]
    # the draw: seeded, from the lane-free trip table, at the attempt that was accepted
    drawn = games.draw_round(int(seed), DOC['trips'], m['budget_m'], m['orders'], rnd['attempt'])
    assert drawn == \
        {'region': rnd['region'], 'orders': rnd['orders']}
    assert [r['attempt'] for r in rnd['rejected']] == list(range(rnd['attempt']))
    assert rnd['region'].startswith('zone_') and rnd['region'] not in games.ROUND_NO_START
    assert rnd['start'][:2] == DOC['starts'][rnd['region']][:2]
    assert len(rnd['orders']) == m['orders'] and len({o for o, _ in rnd['orders']}) == m['orders']
    frm = rnd['region']
    for (oid, drop), ghost, route in zip(rnd['orders'], rnd['ghost_m'], rnd['routes']):
        assert ghost == DOC['trips'][frm][oid][drop] <= m['budget_m']
        assert len(route) >= 2
        frm = drop
    # no planned route enters a forklift lane (points and every 5 cm along each segment)
    rects = _lanes()
    for route in rnd['routes']:
        for (x0, y0), (x1, y1) in zip(route, route[1:]):
            n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / 0.05))
            assert not any(_inside((x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n), rects)
                           for k in range(n + 1)), f'{mode} {seed}: a route crosses a lane'
    # the reference bot finished it; the timer is its time x 1.5
    card = rnd['reference']['card']
    assert card['deliveries'] == m['orders'] and card['rules'] == 3 and card['mode'] == mode
    assert rnd['timer_s'] == round(rnd['reference_time_s'] * games.ROUND_TIMER_FACTOR, 1)
    assert card['timer'] == rnd['timer_s']
    assert card['delivered'][-1]['t'] == rnd['reference_time_s']
    rec = rnd['reference']['record']
    assert rec['rules'] == 3 and rec['mode'] == mode and rec['hash_version'] == 3


def test_round_for_and_the_modes():
    assert games.round_for(3, rules=3) == DOC['rounds']['phone']['3']
    assert games.round_for(3, rules=3, mode='full') == DOC['rounds']['full']['3']
    with pytest.raises(ArenaError, match='modes'):
        games.round_for(1, rules=3, mode='marathon')
    with pytest.raises(ArenaError, match='rounds for seeds'):
        games.round_for(99, rules=3)
    r = games._rules('fetch_rush', 2, 3)
    assert isinstance(r, games.FetchRushRound) and r.mode == 'phone' and r.rules == 3
    assert r.seconds == DOC['rounds']['phone']['2']['timer_s']


@pytest.mark.parametrize('mode', ['phone', 'full'])
def test_the_reference_record_replays_to_its_card(mode):
    rnd = games.round_for(1, rules=3, mode=mode)
    got = games.play(SPEC, rnd['reference']['record'])
    assert got['scorecard'] == rnd['reference']['card']
    assert got['hash_chain'] == rnd['reference']['hash_chain']


def test_playing_a_phone_round_never_plans(monkeypatch):
    def no(*a, **k):
        raise AssertionError('a planner search ran during play')
    rnd = games.round_for(1, rules=3)
    rules = games.FetchRushRound(1, rnd, rules=3, mode='phone')
    a = Arena(SPEC, 1, hash_version=3)
    monkeypatch.setattr(games, 'plan_length', no)
    monkeypatch.setattr(games, 'best_approach', no)
    monkeypatch.setattr(games, 'search', no)
    setup = [InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1, 3, mode='phone')]
    for k in range(20):
        t = a.step(setup if k == 0 else ())
        if not rules.started:
            rules.start(a)
        rules.observe(a, t)
    assert rules.current() == tuple(rnd['orders'][0]) and rules.ghost == rnd['ghost_m'][0]
    assert abs(a.pose[2] - rnd['start'][2]) < 1e-9, 'COCO starts facing the open aisle'
