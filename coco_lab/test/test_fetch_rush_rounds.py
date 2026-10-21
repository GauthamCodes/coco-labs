# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.11: Fetch Rush rules 2 -- budgeted rounds, precomputed, nothing planned in play.

The rounds file (``coco_lab/levels/coco_depot_v1.fetch_rush.json``) is written by
``tools/g1/make_fetch_rush_rounds.py``; these tests check it against the level and the
rules (Gautham's 2026-10-18 decision), and that playing a round never searches.
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
DOC = games.load_rounds()
ROUNDS = DOC['rounds']


def test_the_rounds_are_for_this_level():
    assert DOC['spec_sha256'] == hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert DOC['rules'] == games.FETCH_RUSH_RULES == 2
    assert DOC['budget_m'] == games.ROUND_BUDGET_M
    assert DOC['orders'] == games.ROUND_ORDERS
    assert DOC['timer_factor'] == games.ROUND_TIMER_FACTOR


PLAYABLE = sorted((k for k, r in ROUNDS.items() if r['timer_s'] is not None), key=int)
#: seeds 2 and 4 drew the same round, which the reference bot could not finish (it stopped in
#: the forklift lane); kept on file with that result, refused as a game (no timer)
UNFINISHED = sorted((k for k, r in ROUNDS.items() if r['timer_s'] is None), key=int)


def test_which_rounds_are_playable():
    assert PLAYABLE == ['1', '3', '5', '6'] and UNFINISHED == ['2', '4']
    for k in UNFINISHED:
        assert ROUNDS[k]['reference']['card']['deliveries'] < games.ROUND_ORDERS
        with pytest.raises(ArenaError, match='no timer'):
            games.round_for(int(k))


@pytest.mark.parametrize('seed', PLAYABLE)
def test_each_round_is_the_draw_and_keeps_the_decision(seed):
    rnd = ROUNDS[seed]
    assert games.draw_round(int(seed), DOC['trips']) == {'region': rnd['region'],
                                                        'orders': rnd['orders']}
    # starts inside one zone, never in the forklift lanes
    assert rnd['region'].startswith('zone_') and rnd['region'] not in games.ROUND_NO_START
    assert rnd['start'][:2] == DOC['starts'][rnd['region']][:2]
    # ROUND_ORDERS orders, distinct objects, each planned round trip within the budget
    assert len(rnd['orders']) == games.ROUND_ORDERS
    assert len({o for o, _ in rnd['orders']}) == games.ROUND_ORDERS
    frm = rnd['region']
    for (oid, drop), ghost, route in zip(rnd['orders'], rnd['ghost_m'], rnd['routes']):
        assert ghost == DOC['trips'][frm][oid][drop] <= games.ROUND_BUDGET_M
        assert len(route) >= 2
        frm = drop
    # the timer is the reference bot's time for the deliveries x 1.5
    assert rnd['reference_time_s'] is not None, 'the reference bot did not finish this round'
    assert rnd['timer_s'] == round(rnd['reference_time_s'] * games.ROUND_TIMER_FACTOR, 1)
    card = rnd['reference']['card']
    assert card['deliveries'] == games.ROUND_ORDERS and card['rules'] == 2
    assert card['timer'] == rnd['timer_s']
    assert card['delivered'][-1]['t'] == rnd['reference_time_s']


def test_a_seed_without_a_round_is_refused():
    with pytest.raises(ArenaError, match='rounds for seeds'):
        games.round_for(999)


def test_rules_1_are_unchanged():
    r = games._rules('fetch_rush', 1)
    assert type(r) is games.FetchRush and r.seconds == games.FETCH_RUSH_SECONDS == 180.0
    assert 'kidnap' not in [e['kind'] for e in games.setup_inputs('fetch_rush', 1)]


def test_playing_a_round_never_plans(monkeypatch):
    """No A* (and no pre-grasp search) runs while a rules-2 game is played: the freeze is gone."""
    def no(*a, **k):
        raise AssertionError('a planner search ran during play')
    rnd = games.round_for(1)
    rules = games.FetchRushRound(1, rnd)
    a = Arena(SPEC, 1, hash_version=3)
    monkeypatch.setattr(games, 'plan_length', no)
    monkeypatch.setattr(games, 'best_approach', no)
    monkeypatch.setattr(games, 'search', no)
    setup = [InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1, 2)]
    for k in range(40):
        t = a.step(setup if k == 0 else ())
        if not rules.started:
            rules.start(a)
        rules.observe(a, t)
    assert rules.current() == tuple(rnd['orders'][0]) and rules.ghost == rnd['ghost_m'][0]
    assert abs(a.pose[0] - rnd['start'][0]) < 1e-9 and abs(a.pose[1] - rnd['start'][1]) < 1e-9


def test_the_reference_record_replays_to_its_card():
    """games.play on the committed reference record (rules 2, hash v3) gives the committed card."""
    rnd = games.round_for(1)
    rec = rnd['reference']['record']
    assert rec['rules'] == 2 and rec['hash_version'] == 3
    got = games.play(SPEC, rec)
    assert got['scorecard'] == rnd['reference']['card']
    assert got['hash_chain'] == rnd['reference']['hash_chain']


def test_a_sample_trip_recomputes():
    """The table is the planner's: seed 1's first order, recomputed (the full table is the tool's)."""
    rnd = games.round_for(1)
    a = Arena(SPEC, 1, hash_version=3)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_rush', 1)])
    assist = a.subsystems['assist']
    oid, drop = rnd['orders'][0]
    ba = games.best_approach(a, assist, oid, tuple(DOC['starts'][rnd['region']][:2]))
    r = games.zone_rect(a.spec, drop)
    back = games.plan_length(a, ba[0][:2], ((r[0] + r[1]) / 2, (r[2] + r[3]) / 2))
    assert ba[1] + back == rnd['ghost_m'][0]
