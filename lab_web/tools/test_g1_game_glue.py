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
    assert info['v3'] and info['seconds'] == games.FETCH_RUSH_SECONDS
    t = _step(glue, info['setup'])
    assert t['game']['fetch']['order'] is not None
    a = glue._arena
    before = a.state_bytes(), a.state_hash()
    preview = json.loads(glue.game_op('preview'))
    goal = json.loads(glue.game_op('auto_goal'))
    stars = json.loads(glue.game_op('stars', None))
    ghost = json.loads(glue.game_op('ghost'))
    assert (a.state_bytes(), a.state_hash()) == before, 'a query changed the model'
    assert ghost['order'] == 0 and len(ghost['points']) > 10
    assert isinstance(preview['rows'], list) and goal['why'] == 'pick' and stars['card']['game'] == 'fetch_rush'
    _step(glue, [{'kind': 'goal', 'x': goal['x'], 'y': goal['y']}])
    for k in range(30):
        _step(glue, [{'kind': 'teleop', 'linear': 0.3, 'angular': 0.4}] if k == 12 else [])
    _step(glue, [{'kind': 'stop'}])
    _step(glue, [{'kind': 'config', 'choice': 'assist.grasp=go'}])
    for _ in range(5):
        last = _step(glue, [])
    rec = json.loads(glue.game_op('record'))
    assert rec['record']['ticks'] == 39 and rec['record']['hash_version'] == hash_version
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
    assert json.loads(world)['game'] == {'game': 'free', 'arg': 0, 'v3': False, 'setup': []}
    t = _step(glue, [])
    assert t['game'] == {}
    glue2 = _glue()
    glue2.init(spec, 1, 'astar', lambda *_: None, hash_version=2)
    assert json.loads(glue2.step('[]')[0])['hash'] == t['hash'], 'the game shell changed the Arena'


def test_stars_come_from_the_committed_reference():
    from coco_lab import games
    ref = json.loads((REPO / 'docs/v2/m6/data/games_reference.json').read_text())
    run = next(r for r in ref['runs'] if r['name'] == 'fetch_rush_seed_1')
    card = run['result']['scorecard']
    glue = _glue()
    world, _ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=2)
    _step(glue, json.loads(world)['game']['setup'])
    got = json.loads(glue.game_op('stars', json.dumps(card)))
    assert got['stars'] == games.stars(got['card'], card) == 0
