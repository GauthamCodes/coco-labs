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
    # G1.12: the current rules (G2.1: rules 4), the phone round by default -- its timer and
    # orders, COCO kidnapped to its start zone
    R = games.FETCH_RUSH_RULES
    rnd = games.round_for(1, rules=R, mode='phone')
    assert info['mode'] == 'phone'
    assert info['v3'] and info['seconds'] == rnd['timer_s'] and info['round']['orders'] == rnd['orders']
    assert info['setup'][0]['kind'] == 'kidnap' and info['setup'][0]['x'] == rnd['start'][0]
    t = _step(glue, info['setup'])
    assert t['game']['fetch']['orders'] == games.round_modes(R)['phone']['orders'] == 2
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
    assert rec['record']['rules'] == R and rec['record']['mode'] == 'phone'
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
    info = json.loads(world)['game']
    # G2.2: the ROS-shaped model's constants ride along (additive, labelled MODEL)
    assert info.pop('ros')['graph']['evidence'] == 'MODEL'
    assert info == {'game': 'free', 'arg': 0, 'v3': False, 'mode': None, 'setup': []}
    t = _step(glue, [])
    assert t['game'] == {}
    glue2 = _glue()
    glue2.init(spec, 1, 'astar', lambda *_: None, hash_version=2)
    assert json.loads(glue2.step('[]')[0])['hash'] == t['hash'], 'the game shell changed the Arena'


@pytest.mark.parametrize('mode', ['phone', 'full'])
def test_stars_come_from_the_committed_reference(mode):
    """Rules 3 and 4: stars against the round's own reference (the bot's run, committed with the round)."""
    from coco_lab import games
    card = games.round_for(1, rules=games.FETCH_RUSH_RULES, mode=mode)['reference']['card']
    glue = _glue()
    world, _ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=3, mode=mode)
    _step(glue, json.loads(world)['game']['setup'])
    assert json.loads(glue.game_op('record'))['record']['mode'] == mode
    # whatever the page passes, a rules-3/4 game is scored against its round's reference
    got = json.loads(glue.game_op('stars', json.dumps({'net_deliveries': 99})))
    assert got['reference'] == card
    assert got['stars'] == games.stars(got['card'], card) == 0


def test_robot_vision_costmap_delta_views_rebuild_the_full_costmap():
    """
    G1.13: Play's Robot vision asks for delta views (changed cells only, from a cached
    static map). Applied in order over an empty grid -- as the page's hologram does -- they
    must give exactly build_layers' combined costs at each view, and never change the model.
    """
    from coco_lab import numerics
    from coco_lab.costmap import build_layers, InflationParams, scan_obstacle_cells
    glue = _glue()
    got = []
    world, _occ = glue.game_init(_depot(), 'fetch_rush', 1, 1, lambda *_: None, hash_version=3,
                                 post_family=lambda num, meta: got.append((num, json.loads(meta))))
    info = json.loads(world)['game']
    assert glue._costmap['static'] is not None, 'the static costmap is built while the page loads'
    _step(glue, info['setup'])
    a = glue._arena
    grid = bytearray(a.lab_map.width * a.lab_map.height)
    sizes = []
    for k in range(4):
        got.clear()
        before = a.state_bytes(), a.state_hash()
        glue.costmap_view(True)
        assert (a.state_bytes(), a.state_hash()) == before, 'the costmap view changed the model'
        n = 0
        for num, meta in got:
            if meta.get('channel') == 'coco.costmap.layers.cells.v1':
                rows, cols, cost = num['row'], num['col'], num['combined_cost']
                for r, c, v in zip(rows, cols, cost):
                    grid[int(r) * a.lab_map.width + int(c)] = int(v)
                n += len(rows)
        sizes.append(n)
        m, li = a.lab_map, a.lidar
        params = InflationParams(robot_radius=a.radius, inflation_radius=max(0.5, a.radius))
        with numerics.version(3):   # the Arena's numerics, as the glue's calls run in (rays and costs)
            hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles, li.mount, li.range_min, li.range_max)
            want = build_layers(m.width, m.height, m.resolution, [v != 0 for v in m.occupancy], hits, params)
        assert bytes(grid) == want.combined, f'view {k}: the hologram differs from build_layers'
        for _ in range(15):
            _step(glue, [{'kind': 'teleop', 'linear': 0.3, 'angular': 0.5}])
    assert sizes[0] > 10000 and all(s < sizes[0] / 20 for s in sizes[1:]), f'later views send only changes: {sizes}'
