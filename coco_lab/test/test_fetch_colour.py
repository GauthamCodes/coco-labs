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

"""
Fetch by colour (owner request 2026-10-24): four rods, COCO fetches the chosen colour.

The level ``worlds/coco_depot_colours_v1.json`` is the Depot plus a row of four rods (the
catalog's Stack targets); the rounds file ``levels/coco_depot_colours_v1.fetch_colour.json`` is
written by ``tools/g2/make_fetch_colour_rounds.py``. The Depot, its rounds and every hash made
on it must stay byte-identical.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from coco_lab import games, loc_arena  # noqa: F401 -- loc_arena: the subsystem
from coco_lab import worldspec_v3 as v3
from coco_lab.arena import Arena, ArenaError, InputEvent
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / 'worlds' / 'coco_depot_colours_v1.json'
SPEC = json.loads(SPEC_PATH.read_text())
DEPOT = json.loads((REPO / 'worlds' / 'coco_depot_v1.json').read_text())
DOC = json.loads(games.colour_rounds_file().read_text())

#: sha256 of the Depot's files as they were before Fetch by colour existed (c695cd5)
UNCHANGED = {
    'worlds/coco_depot_v1.json':
        '11b39c5aa9e5c1530d50babd582a8d08e0858e8605ebb9fe82fa80504b9c7e04',
    'worlds/coco_depot_v1.yaml':
        '663884e5c7a46be6c7a38657dd38ef000856c0da6ab44edf07186a1f2fade140',
    'coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.json':
        '55c0fbec906677cccaae845720735a0fe40039614499a008cb54c2c08293466f',
    'coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r3.json':
        '55139f5e8f98e56fc6a0480eb1d7895db5f1237fe5c319f4f9d61cf19e8962f4',
    'coco_lab/coco_lab/levels/coco_depot_v1.fetch_rush.r4.json':
        '7f3dbf653dc352b6f868142af85b9eb570bebf794025db13777b72fbb411b332',
}
ITEMS = {'red': ('can_small', 0.020), 'green': ('bottle_steel', 0.024),
         'blue': ('canister', 0.028), 'yellow': ('can_large', 0.032)}


@pytest.mark.parametrize('path', sorted(UNCHANGED))
def test_the_depot_and_its_rounds_are_byte_identical(path):
    assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == UNCHANGED[path]


def test_the_level_is_generated_and_canonical():
    for cmd in (['worlds/tools/make_coco_depot_v1.py', '--check'],
                ['worlds/tools/make_coco_depot_v1.py', '--check', '--variant', 'colours'],
                ['tools/g1/depot_json.py', '--check'],
                ['tools/g1/depot_json.py', '--check', '--variant', 'colours']):
        r = subprocess.run([sys.executable, str(REPO / cmd[0])] + cmd[1:],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


def test_the_level_is_the_depot_plus_four_rods():
    raw = yaml.safe_load((REPO / 'worlds' / 'coco_depot_colours_v1.yaml').read_text())
    v3.normalize_v3(raw)                # the World Spec v3 checks, _check_object included
    assert SPEC['id'] == games.FETCH_COLOUR_LEVEL and DEPOT['id'] == 'coco_depot_v1'
    rods = {k['id']: k for k in SPEC['kit'] if k['id'].startswith('rod_')}
    assert sorted(rods) == sorted(games.FETCH_COLOUR_RODS.values())
    same = [k for k in SPEC['kit'] if not k['id'].startswith('rod_')]
    assert same == DEPOT['kit'], 'everything but the rods is the Depot'
    for key in DEPOT:
        if key not in ('id', 'title', 'sources', 'kit'):
            assert SPEC[key] == DEPOT[key], key
    cat = {c['id']: c for c in SPEC['catalog']}
    xs = []
    for colour, (item, d) in ITEMS.items():
        rod = rods[games.FETCH_COLOUR_RODS[colour]]
        c = cat[rod['item']]
        assert rod['item'] == item and c['colour'] == colour and c['diameter'] == d
        assert c['height'] == 0.158 and rod['support'] == 'floor' and rod['at'][1] == 8.0
        xs.append(rod['at'][0])
    assert xs == [20.0, 21.0, 22.0, 23.0], 'one row, 1 m apart, red to yellow'


def test_every_rod_is_pickable_with_free_approaches():
    a = Arena(SPEC, 1, hash_version=3)
    a.step([InputEvent(**e) for e in games.setup_inputs('fetch_colour', 'red', 1)])
    assist = a.subsystems['assist']
    pick = games.pickable(a, assist)
    for oid in games.FETCH_COLOUR_RODS.values():
        assert oid in pick
        assert len(assist.approach_poses(a, assist.objects[oid])) == 16


def test_the_rounds_are_for_this_level_and_these_rules():
    assert DOC['spec_sha256'] == hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert DOC['level'] == games.FETCH_COLOUR_LEVEL and DOC['rules'] == games.FETCH_COLOUR_RULES
    assert DOC['actor_rules'] == games.FETCH_COLOUR_ACTOR_RULES[DOC['rules']]
    assert DOC['timer_factor'] == games.ROUND_TIMER_FACTOR == 1.5
    assert DOC['colours'] == list(games.FETCH_COLOURS) == ['red', 'green', 'blue', 'yellow']
    assert DOC['drop'] == games.FETCH_COLOUR_DROP == 'dispatch_drop'
    for colour, rnd in DOC['rounds'].items():
        assert rnd['orders'] == [[games.FETCH_COLOUR_RODS[colour], 'dispatch_drop']]
        assert rnd['timer_s'] == round(rnd['reference_time_s'] * 1.5, 1)
        assert rnd['start'][:2] == [23.0, 6.0]


def test_setup_uses_fetch_rush_actor_setup_and_the_rounds_start():
    rnd = DOC['rounds']['blue']
    got = games.setup_inputs('fetch_colour', 'blue', 1)
    assert got[1:] == games.fetch_actor_inputs(games.FETCH_COLOUR_ACTOR_RULES[1])
    assert got[0] == {'tick': 0, 'kind': 'kidnap', 'x': rnd['start'][0], 'y': rnd['start'][1],
                      'theta': rnd['start'][2], 'has_theta': True}
    # Fetch Rush's own set-up is what it always was
    assert games.setup_inputs('fetch_rush', 1, 1) == [
        {'tick': 0, 'kind': 'config', 'choice': 'actors.on=1'},
        {'tick': 0, 'kind': 'config', 'choice': 'assist.target=any'}]


@pytest.mark.parametrize('colour', games.FETCH_COLOURS)
def test_the_reference_delivers_the_chosen_rod_and_replays(colour):
    ref = DOC['rounds'][colour]['reference']
    rec = ref['record']
    assert rec['game'] == 'fetch_colour' and rec['arg'] == colour and rec['rules'] == 1
    assert rec['level'] == games.FETCH_COLOUR_LEVEL and rec['hash_version'] == 3
    got = games.play(SPEC, rec)
    assert got['hash_chain'] == ref['hash_chain'] and got['scorecard'] == ref['card']
    card = got['scorecard']
    assert card['game'] == 'fetch_colour' and card['colour'] == colour
    assert card['deliveries'] == 1 and card['contacts'] == 0
    assert card['delivered'][0]['object'] == games.FETCH_COLOUR_RODS[colour]
    assert games.stars(card, ref['card']) == 3
    assert games.verify(SPEC, rec, got)


def test_the_reference_bot_reproduces_its_record():
    rec, res = games.bot_fetch_colour(SPEC, 'yellow', rules=games.FetchColour(
        'yellow', seconds=games.colour_round('yellow')['timer_s']))
    ref = DOC['rounds']['yellow']['reference']
    assert rec == ref['record'] and res['hash_chain'] == ref['hash_chain']


def test_a_record_must_play_on_its_level_and_colour():
    rec = DOC['rounds']['red']['reference']['record']
    with pytest.raises(ArenaError):
        games.play(DEPOT, rec)
    with pytest.raises(ArenaError):
        games.FetchColour('purple')


def test_stars_compare_against_the_colour_reference():
    ref = DOC['rounds']['green']['reference']['card']
    assert games.stars(dict(ref, deliveries=0, net_deliveries=0), ref) == 0
    assert games.stars(dict(ref, time_used=ref['time_used'] + 1), ref) == 2
    assert games.stars(dict(ref, contacts=1, net_deliveries=0), ref) == 1
