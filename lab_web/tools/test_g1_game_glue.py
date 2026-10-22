# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.6: the browser's game glue (arena_glue.py) in CPython.

A session played through the glue (setup inputs, driving, Grasp Assist,
queries between ticks) must keep a record that coco_lab.games.play()
replays to the SAME per-tick hash chain and scorecard; the read-only
queries (GRAB preview, AUTO goal, stars) must not change the model.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _glue():
    spec = importlib.util.spec_from_file_location('g1_test_glue', REPO / 'lab_web/src/arena/arena_glue.py')
    glue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(glue)
    return glue


def _step(glue, rows):
    glue.begin(json.dumps(rows))
    while not glue.advance(4096):
        pass
    tick, _ranges = glue.finish()
    return json.loads(tick)


def _depot():
    return (REPO / 'worlds/coco_depot_v1.json').read_text()


def test_the_depot_json_is_the_canonical_bytes_of_the_yaml():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(REPO / 'tools/g1/depot_json.py'), '--check'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize('hash_version', [1, 2, 3])
def test_a_played_fetch_rush_replays_to_the_same_chain(hash_version):
    from coco_lab import games
    glue = _glue()
    world, _occ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=hash_version)
    info = json.loads(world)['game']
    # G1.12: rules 3, the phone round by default -- its timer and orders, COCO kidnapped to its start zone
    rnd = games.round_for(1, rules=3, mode='phone')
    assert info['mode'] == 'phone'
    assert info['v3'] and info['seconds'] == rnd['timer_s'] and info['round']['orders'] == rnd['orders']
    assert info['setup'][0]['kind'] == 'kidnap' and info['setup'][0]['x'] == rnd['start'][0]
    t = _step(glue, info['setup'])
    assert t['game']['fetch']['orders'] == games.ROUND_MODES['phone']['orders'] == 2
    assert t['game']['fetch']['seconds'] == rnd['timer_s']
    assert t['game']['fetch']['order'] is not None
    a = glue._arena
    before = a.state_bytes(), a.state_hash()
    preview = json.loads(glue.game_op('preview'))
    goal = json.loads(glue.game_op('auto_goal'))
    stars = json.loads(glue.game_op('stars', None))
    ghost = json.loads(glue.game_op('ghost'))
    # G1.12: AUTO's search, run ahead between ticks (as the worker does when idle)
    while not glue.game_prefetch(5):
        pass
    ahead = a._ahead
    assert ahead is not None and ahead[1].result is not None
    assert (a.state_bytes(), a.state_hash()) == before, 'a query (or the prefetch) changed the model'
    assert ghost == {'order': 0, 'points': rnd['routes'][0]}, 'the ghost is the round\'s own route'
    assert isinstance(preview['rows'], list) and goal['why'] == 'pick' and stars['card']['game'] == 'fetch_rush'
    t = _step(glue, [{'kind': 'goal', 'x': goal['x'], 'y': goal['y']}])
    assert t['plans'] and a._ahead is None, 'the AUTO tick took the prefetched search over'
    assert t['plans'][0]['summary'] == ahead[1].result.trace.summary
    for k in range(30):
        _step(glue, [{'kind': 'teleop', 'linear': 0.3, 'angular': 0.4}] if k == 12 else [])
    _step(glue, [{'kind': 'stop'}])
    _step(glue, [{'kind': 'config', 'choice': 'assist.grasp=go'}])
    for _ in range(5):
        last = _step(glue, [])
    rec = json.loads(glue.game_op('record'))
    assert rec['record']['ticks'] == 39 and rec['record']['hash_version'] == hash_version
    assert rec['record']['rules'] == 3 and rec['record']['mode'] == 'phone'
    replay = games.play(json.loads(_depot()), rec['record'])
    assert replay['hash_chain'] == rec['hash_chain']
    assert replay['last_hash'] == rec['last_hash'] == last['hash']
    assert replay['scorecard'] == json.loads(glue.game_op('stars', None))['card']


def test_free_drive_on_the_depot_has_actors_and_assist_but_no_rules():
    glue = _glue()
    world, _ = glue.game_init(_depot(), 'free', 0, 1, lambda *_: None, hash_version=2)
    info = json.loads(world)['game']
    t = _step(glue, info['setup'])
    assert 'fetch' not in t['game'] and len(t['game']['actors']) == 4 and len(t['game']['objects']) == 18
    assert json.loads(glue.game_op('stars', None)) == {'card': None, 'stars': None, 'reference': None}


def test_free_drive_on_the_proving_ground_is_the_plain_arena():
    glue = _glue()
    spec = (REPO / 'worlds/coco_arena_v1.json').read_text()
    world, _ = glue.game_init(spec, 'free', 0, 1, lambda *_: None, hash_version=2)
    assert json.loads(world)['game'] == {'game': 'free', 'arg': 0, 'v3': False, 'mode': None, 'setup': []}
    t = _step(glue, [])
    assert t['game'] == {}
    glue2 = _glue()
    glue2.init(spec, 1, 'astar', lambda *_: None, hash_version=2)
    assert json.loads(glue2.step('[]')[0])['hash'] == t['hash'], 'the game shell changed the Arena'


@pytest.mark.parametrize('mode', ['phone', 'full'])
def test_stars_come_from_the_committed_reference(mode):
    """Rules 3: stars against the round's own reference (the bot's run, committed with the round)."""
    from coco_lab import games
    card = games.round_for(1, rules=3, mode=mode)['reference']['card']
    glue = _glue()
    world, _ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=3, mode=mode)
    _step(glue, json.loads(world)['game']['setup'])
    assert json.loads(glue.game_op('record'))['record']['mode'] == mode
    # whatever the page passes, a rules-3 game is scored against its round's reference
    got = json.loads(glue.game_op('stars', json.dumps({'net_deliveries': 99})))
    assert got['reference'] == card
    assert got['stars'] == games.stars(got['card'], card) == 0
