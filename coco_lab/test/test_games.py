# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Fetch Rush and Rush Hour, model side (M6F.6; docs/v2/m6/GAMES.md)."""

import copy
import json
import math
import os

from coco_lab import games
from coco_lab import worldspec_v3 as v3
from coco_lab.arena import Arena, InputEvent
from coco_lab.link_bounds import LIMITS
import pytest
import yaml

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_depot_v1.yaml'), encoding='utf-8') as _f:
    DEPOT = yaml.safe_load(_f)
with open(os.path.join(REPO, 'docs', 'v2', 'm6', 'data', 'games_reference.json'),
          encoding='utf-8') as _f:
    REF = {r['name']: r for r in json.load(_f)['runs']}
N = v3.normalize(DEPOT)


def _setup(game, arg, seed=1):
    a = Arena(DEPOT, seed)
    a.step([InputEvent(**dict(e, tick=0)) for e in games.setup_inputs(game, arg)])
    return a


# -- the actors, solid in the model ----------------------------------------------------

@pytest.mark.parametrize('actor', v3.elements(N, 'actor'), ids=lambda a: a['id'])
def test_the_discs_cover_the_actors_box(actor):
    for t in (0.0, 3.3, 17.0):
        discs = games.actor_discs(actor, t)
        x, y, yaw = v3.actor_pose(actor, t)
        c, s = math.cos(yaw), math.sin(yaw)
        hl, hw = actor['footprint'][0] / 2, actor['footprint'][1] / 2
        for i in range(11):
            for j in range(11):
                u, w = -hl + 2 * hl * i / 10, -hw + 2 * hw * j / 10
                px, py = x + c * u - s * w, y + s * u + c * w
                assert any(math.hypot(px - dx, py - dy) <= r + 1e-9 for dx, dy, r in discs)


def test_actors_are_solid_and_seen_by_the_lidar():
    a = _setup('fetch_rush', 1)
    assert 'actors' in a.subsystems and len(a.discs()) == 2 + 2 + 1 + 1
    fork = v3.elements(N, 'actor')[0]
    t = a.t_world
    x, y, _ = v3.actor_pose(fork, t)
    a.pose = (x, y - 2.0, math.pi / 2)                  # 2 m south, facing it
    a.ranges = a._scan()
    ahead = min(range(len(a.angles)), key=lambda k: abs(a.angles[k]))
    assert a.ranges[ahead] < 2.0                        # the LiDAR meets the forklift
    act = a.subsystems['actors']
    want = 2.0 - 0.6 - a.radius
    assert act.clearance(x, y - 2.0, a.radius) == pytest.approx(want, abs=0.05)


def test_the_box_distance_is_zero_inside_and_exact_outside():
    fork = v3.elements(N, 'actor')[0]
    x, y, _ = v3.actor_pose(fork, 0.0)
    assert games.box_distance(x, y, fork, 0.0) == 0.0
    assert games.box_distance(x, y + 1.6, fork, 0.0) == pytest.approx(1.0)


# -- Fetch Rush ----------------------------------------------------------------------

def test_orders_are_seeded_pickable_and_go_to_drop_zones():
    def orders(seed):
        a = _setup('fetch_rush', seed)
        g = games.FetchRush(seed)
        g.start(a)
        return g.orders, games.pickable(a, a.subsystems['assist'])
    o1, pool = orders(1)
    assert orders(1)[0] == o1 and orders(3)[0] != o1
    assert sorted(oid for oid, _ in o1) == pool and 'bad_blocked' not in pool
    assert {d for _, d in o1} <= {z['id'] for z in v3.zones(N, 'drop')}
    assert len(pool) == 10


def test_the_game_lasts_three_minutes():
    assert games.FETCH_RUSH_SECONDS == 180.0
    r = REF['fetch_rush_seed_3']
    assert r['record']['ticks'] == 1801 and r['result']['scorecard']['deliveries'] == 0


# -- the references reproduce -----------------------------------------------------------

@pytest.mark.parametrize('name', ['fetch_rush_seed_1', 'rush_hour_aisle_to_dispatch'])
def test_reference_records_reproduce_their_results(name):
    r = REF[name]
    assert games.verify(DEPOT, r['record'], r['result'])


def test_the_references_are_clean_runs():
    fr = REF['fetch_rush_seed_1']['result']['scorecard']
    assert fr['deliveries'] == 1 and fr['contacts'] == 0
    d = fr['delivered'][0]
    assert d['ghost'] / d['driven'] == pytest.approx(fr['path_efficiency'])
    rh = REF['rush_hour_aisle_to_dispatch']['result']['scorecard']
    assert rh['delivered'] and rh['contacts'] == 0 and rh['min_clearance'] > 0
    assert rh['fragile_cargo'] == 'game rule, not physics'


def test_a_tampered_claim_does_not_verify():
    r = REF['rush_hour_aisle_to_dispatch']
    claim = copy.deepcopy(r['result'])
    claim['scorecard']['time'] -= 1.0
    assert not games.verify(DEPOT, r['record'], claim)


@pytest.mark.parametrize('bad', [
    lambda rec: rec.update(inputs=[{'tick': 3, 'kind': 'stop'}, {'tick': 2, 'kind': 'stop'}]),
    lambda rec: rec.update(inputs=[{'tick': LIMITS['first_tick'] + 1, 'kind': 'stop'}]),
    lambda rec: rec.update(inputs=[{'tick': 0, 'kind': 'stop'}] * (LIMITS['inputs'] + 1)),
    lambda rec: rec.update(ticks=LIMITS['ticks'] + 1),
    lambda rec: rec.update(game='tetris'),
])
def test_records_outside_the_link_limits_are_refused_before_any_replay(bad):
    rec = copy.deepcopy(REF['rush_hour_aisle_to_dispatch']['record'])
    bad(rec)
    with pytest.raises(ValueError):
        games.verify(DEPOT, rec, {})


# -- stars, from the reference ------------------------------------------------------------

def test_stars_come_from_the_reference():
    fr = REF['fetch_rush_seed_1']['result']['scorecard']
    assert games.stars(fr, fr) == 3
    slower = dict(fr, time_used=fr['time_used'] + 10)
    assert games.stars(slower, fr) == 2
    bumped = dict(fr, contacts=1, net_deliveries=0)
    assert games.stars(bumped, fr) == 1
    assert games.stars(dict(fr, deliveries=0, net_deliveries=0), fr) == 0
    rh = REF['rush_hour_aisle_to_dispatch']['result']['scorecard']
    assert games.stars(rh, rh) == 3
    assert games.stars(dict(rh, jerk_rms=rh['jerk_rms'] * 2), rh) == 2
    assert games.stars(dict(rh, contacts=1), rh) == 1
    assert games.stars(dict(rh, delivered=False), rh) == 0


def test_a_game_is_only_spec_seed_and_inputs():
    # the rules observe; they add nothing to the model: the hash chain is the Arena's
    r = REF['rush_hour_aisle_to_dispatch']
    a = Arena(DEPOT, r['record']['seed'])
    by = {}
    for e in r['record']['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    last = None
    for _ in range(r['record']['ticks']):
        last = a.step(by.get(a.tick, ())).state_hash
    assert last == r['result']['last_hash']
