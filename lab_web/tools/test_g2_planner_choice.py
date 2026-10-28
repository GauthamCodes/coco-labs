# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
The AUTO planner choice (owner request, 2026-10-24; lab_web/src/game/planners.ts).

The page sends a non-A* planner as the run's first input ({kind: 'planner', choice}, the model's
own input; A* sends nothing). So a session played with another planner plans with it, keeps it
on its record, and coco_lab.games.play() replays that record to the same hash chain and card --
and an A* session is the one test_g1_game_glue.py already pins (no planner input at all).
"""
import json

import pytest
from test_g1_game_glue import _depot, _glue, _step

PLANNERS = ['dijkstra', 'greedy', 'weighted_astar', 'bfs']


@pytest.mark.parametrize('planner', PLANNERS)
def test_a_run_with_another_planner_plans_with_it_and_replays(planner):
    from coco_lab import games
    glue = _glue()
    world, _occ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=3)
    info = json.loads(world)['game']
    _step(glue, info['setup'] + [{'kind': 'planner', 'choice': planner}])
    assert glue._arena.planner == planner
    goal = json.loads(glue.game_op('auto_goal'))
    t = _step(glue, [{'kind': 'goal', 'x': goal['x'], 'y': goal['y']}])
    assert t['plans'] and all(p['planner'] == planner for p in t['plans'])
    for _ in range(25):
        last = _step(glue, [])
    rec = json.loads(glue.game_op('record'))
    assert {'tick': 0, 'kind': 'planner', 'choice': planner}.items() <= next(
        e for e in rec['record']['inputs'] if e['kind'] == 'planner').items()
    replay = games.play(json.loads(_depot()), rec['record'])
    assert replay['hash_chain'] == rec['hash_chain'] and replay['last_hash'] == last['hash']
    assert replay['scorecard'] == json.loads(glue.game_op('stars', None))['card']


def test_another_planner_is_a_different_run_from_a_star():
    hashes = {}
    for planner in ['astar', 'greedy']:
        glue = _glue()
        world, _occ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=3)
        info = json.loads(world)['game']
        _step(glue, info['setup'] + ([] if planner == 'astar' else [{'kind': 'planner', 'choice': planner}]))
        hashes[planner] = glue._arena.state_hash()
    assert hashes['astar'] != hashes['greedy'], 'the planner is part of the model state (and of its hash)'
