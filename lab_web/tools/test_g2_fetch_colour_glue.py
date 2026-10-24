# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Fetch by colour (owner request 2026-10-24) through the browser's game glue, in CPython.

A session played through the glue must keep a record that coco_lab.games.play() replays to
the SAME hash chain and scorecard; AUTO goes to the chosen rod and then to Dispatch; the HUD
block names the colour; the queries change nothing in the model.
"""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LEVEL = REPO / 'worlds/coco_depot_colours_v1.json'


def _glue():
    spec = importlib.util.spec_from_file_location('g2_colour_glue', REPO / 'lab_web/src/arena/arena_glue.py')
    glue = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(glue)
    return glue


def _step(glue, rows):
    glue.begin(json.dumps(rows))
    while not glue.advance(4096):
        pass
    tick, _ranges = glue.finish()
    return json.loads(tick)


def test_fetch_colour_needs_its_own_level():
    glue = _glue()
    with pytest.raises(ValueError):
        glue.game_init((REPO / 'worlds/coco_depot_v1.json').read_text(), 'fetch_colour', 'red', 1, lambda *_: None)


def test_a_short_session_names_the_colour_and_replays():
    from coco_lab import games
    glue = _glue()
    world, _ = glue.game_init(LEVEL.read_text(), 'fetch_colour', 'green', 1, lambda *_: None, hash_version=3)
    info = json.loads(world)['game']
    rnd = games.colour_round('green')
    assert info['colour'] == {'colour': 'green', 'object': 'rod_green', 'item': 'bottle_steel', 'diameter': 0.024,
                              'drop': 'dispatch_drop', 'drop_label': 'Dispatch'}
    assert info['seconds'] == rnd['timer_s'] and info['round']['orders'] == [['rod_green', 'dispatch_drop']]
    assert info['setup'][0]['kind'] == 'kidnap' and info['setup'][1:] == games.fetch_actor_inputs(4)
    t = _step(glue, info['setup'])
    assert t['game']['fetch']['colour'] == 'green' and t['game']['fetch']['order'] == ['rod_green', 'dispatch_drop']
    a = glue._arena
    before = a.state_bytes(), a.state_hash()
    goal = json.loads(glue.game_op('auto_goal'))
    ghost = json.loads(glue.game_op('ghost'))
    stars = json.loads(glue.game_op('stars', None))
    json.loads(glue.game_op('preview'))
    assert (a.state_bytes(), a.state_hash()) == before, 'a query changed the model'
    assert goal['why'] == 'pick' and goal['object'] == 'rod_green'
    assert ghost == {'order': 0, 'points': rnd['routes'][0]}
    assert stars['card']['game'] == 'fetch_colour' and stars['reference'] == rnd['reference']['card']
    _step(glue, [{'kind': 'goal', 'x': goal['x'], 'y': goal['y']}])
    for _ in range(20):
        last = _step(glue, [])
    rec = json.loads(glue.game_op('record'))
    assert rec['record']['game'] == 'fetch_colour' and rec['record']['arg'] == 'green'
    assert rec['record']['rules'] == 1 and rec['record']['level'] == 'coco_depot_colours_v1'
    replay = games.play(json.loads(LEVEL.read_text()), rec['record'])
    assert replay['hash_chain'] == rec['hash_chain'] and replay['last_hash'] == last['hash']
    assert replay['scorecard'] == json.loads(glue.game_op('stars', None))['card']


def test_the_reference_played_through_the_glue_is_the_reference():
    """The yellow reference's inputs, fed tick by tick through the glue: same chain, same card, 3 stars."""
    from coco_lab import games
    ref = games.colour_round('yellow')['reference']
    glue = _glue()
    world, _ = glue.game_init(LEVEL.read_text(), 'fetch_colour', 'yellow', 1, lambda *_: None, hash_version=3)
    by = {}
    for e in ref['record']['inputs']:
        by.setdefault(e['tick'], []).append({k: v for k, v in e.items() if k != 'tick'})
    for k in range(ref['record']['ticks']):
        last = _step(glue, by.get(k, []))
    assert last['game']['fetch']['deliveries'] == 1
    rec = json.loads(glue.game_op('record'))
    assert rec['hash_chain'] == ref['hash_chain']
    out = json.loads(glue.game_op('stars', None))
    assert out['card'] == ref['card'] and out['stars'] == 3
    assert out['card']['delivered'][0]['object'] == 'rod_yellow'
