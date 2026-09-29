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

"""Map schema v1: validation, identity, conversions and conventions."""

import json
import os
import re

from coco_lab import maps
from coco_lab.maps import (FREE, LabMap, MapError, OCCUPIED, Raster,
                           UNKNOWN)
from coco_lab.search import search
from hypothesis import given, settings, strategies as st
import pytest

DOC = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'labs',
                   'MAP_FORMAT.md')

SMALL = """
    S.#
    .?.
    ..G
"""


def small(**kwargs):
    return LabMap.from_ascii(SMALL, map_id='small', **kwargs)


# -- validation ------------------------------------------------------------

@pytest.mark.parametrize('width,height', [
    (0, 3), (3, 0), (-1, 3), (2.0, 3), (True, 3), (maps.MAX_SIDE + 1, 1),
    (maps.MAX_SIDE, maps.MAX_SIDE)])
def test_bad_dimensions_are_refused(width, height):
    with pytest.raises(MapError):
        LabMap(width, height, b'')


def test_occupancy_length_and_values_are_checked():
    with pytest.raises(MapError, match='cells'):
        LabMap(2, 2, b'\x00' * 3)
    with pytest.raises(MapError, match='0, 1 or 2'):
        LabMap(2, 2, b'\x00\x00\x00\x03')
    with pytest.raises(MapError, match='0, 1 or 2'):
        LabMap(2, 2, [0, 0, 0, 300])


@pytest.mark.parametrize('bad', [-1.0, float('nan'), float('inf'), 'x'])
def test_cost_must_be_finite_and_non_negative(bad):
    with pytest.raises(MapError, match='cost'):
        LabMap(2, 1, b'\x00\x00', cost=[0.0, bad])


def test_geo_comes_as_a_pair_and_must_be_finite():
    with pytest.raises(MapError, match='together'):
        LabMap(1, 1, b'\x00', resolution=0.05)
    with pytest.raises(MapError, match='resolution'):
        LabMap(1, 1, b'\x00', resolution=0.0, origin=(0, 0))
    with pytest.raises(MapError, match='origin'):
        LabMap(1, 1, b'\x00', resolution=1.0, origin=(0, float('nan')))
    with pytest.raises(MapError, match='frame'):
        LabMap(1, 1, b'\x00', frame='map')


def test_at_refuses_out_of_bounds():
    m, _ = small()
    assert m.at((0, 2)) == OCCUPIED and m.at((1, 1)) == UNKNOWN
    for cell in ((-1, 0), (0, 3), (3, 0)):
        with pytest.raises(MapError):
            m.at(cell)


# -- coordinates -----------------------------------------------------------

def test_row_zero_is_the_top_and_y_grows_upward():
    m = LabMap(3, 2, b'\x00' * 6, resolution=0.5, origin=(10.0, 20.0),
               frame='map')
    # Bottom-left cell is (row 1, col 0); its centre is half a cell in.
    assert m.cell_centre(1, 0) == (10.25, 20.25)
    assert m.cell_centre(0, 0) == (10.25, 20.75)
    assert m.cell_centre(0, 2) == (11.25, 20.75)
    for r in range(2):
        for c in range(3):
            assert m.cell_at(*m.cell_centre(r, c)) == (r, c)
    assert m.cell_at(9.99, 20.1) is None
    assert m.cell_at(10.1, 21.01) is None


def test_ascii_marks_and_characters():
    m, marks = small()
    assert marks == {'S': (0, 0), 'G': (2, 2)}
    assert m.to_ascii() == '..#\n.?.\n...'
    assert (m.count(FREE), m.count(OCCUPIED), m.count(UNKNOWN)) == (7, 1, 1)


# -- identity --------------------------------------------------------------

def test_content_hash_is_stable_and_pinned():
    m, _ = small()
    assert m.content_hash() == small()[0].content_hash()
    # Pinned: the hashed bytes are defined in the docstring and the doc,
    # and a TypeScript reader must be able to recompute this value.
    assert m.content_hash() == (
        'sha256:' + __import__('hashlib').sha256(
            b'coco_lab.map/1 3 3\n' + bytes([0, 0, 1, 0, 2, 0, 0, 0, 0])
            + b'nocost\nnogeo\n').hexdigest())


def test_content_hash_ignores_id_and_meta_but_nothing_else():
    m, _ = small()
    base = m.content_hash()
    renamed = LabMap(3, 3, m.occupancy, map_id='other', meta={'a': 1})
    assert renamed.content_hash() == base
    variants = [
        LabMap(3, 3, b'\x01' + m.occupancy[1:]),
        LabMap(3, 3, m.occupancy[:2] + b'\x00' + m.occupancy[3:]),
        LabMap(9, 1, m.occupancy),
        LabMap(3, 3, m.occupancy, cost=[0.0] * 9),
        LabMap(3, 3, m.occupancy, resolution=1.0, origin=(0, 0)),
        LabMap(3, 3, m.occupancy, resolution=1.0, origin=(0, 0),
               frame='map'),
    ]
    hashes = {v.content_hash() for v in variants}
    assert base not in hashes and len(hashes) == len(variants)


# -- serialisation ---------------------------------------------------------

def geo_map():
    return LabMap(4, 2, bytes([0, 1, 2, 0, 0, 0, 1, 0]),
                  cost=[0.0, 1.5, 0.0, 252.0, 0.1, 0.0, 0.0, 3.0],
                  map_id='g', resolution=0.05, origin=(-6.5, -9.5),
                  frame='map', meta={'source': 'test'})


def test_json_round_trip_is_exact_and_canonical():
    m = geo_map()
    text = m.to_json()
    back = LabMap.from_json(text)
    assert back == m and back.cost == m.cost
    assert back.to_json() == text
    assert text == json.dumps(json.loads(text), sort_keys=True,
                              separators=(',', ':'))


def test_a_tampered_map_is_refused_not_repaired():
    d = json.loads(geo_map().to_json())
    d['rows'][0] = '####'
    with pytest.raises(MapError, match='content_hash'):
        LabMap.from_dict(d)
    del d['content_hash']
    assert LabMap.from_dict(d).at((0, 0)) == OCCUPIED


@pytest.mark.parametrize('mutate,match', [
    (lambda d: d.update(schema='x'), 'schema'),
    (lambda d: d.update(version='2.0'), 'major version 2'),
    (lambda d: d.update(version='x'), 'bad map version'),
    (lambda d: d.update(rows=['....', '..']), 'rows'),
    (lambda d: d.update(rows=['..x.', '....']), 'rows may only'),
    (lambda d: d.update(rows=['..é.', '....']), 'rows may only'),
    (lambda d: d.update(cost='x'), 'cost'),
    (lambda d: d.update(geo=[1]), 'geo'),
    (lambda d: d['geo'].update(origin=[1]), 'origin'),
    (lambda d: d.update(meta=[1]), 'meta'),
    (lambda d: d.update(width=10 ** 9), 'width'),
])
def test_malformed_maps_are_refused(mutate, match):
    d = json.loads(geo_map().to_json())
    mutate(d)
    d.pop('content_hash', None)
    with pytest.raises(MapError, match=match):
        LabMap.from_dict(d)


def test_minor_versions_and_unknown_fields_are_accepted():
    d = json.loads(geo_map().to_json())
    d['version'] = '1.7'
    d['future_field'] = {'x': 1}
    assert LabMap.from_dict(d) == geo_map()


def test_non_json_and_deep_nesting_are_refused_cleanly():
    with pytest.raises(MapError):
        LabMap.from_json('{')
    with pytest.raises(MapError):
        LabMap.from_json('[' * 100000 + ']' * 100000)
    with pytest.raises(MapError):
        LabMap.from_json('[1, 2]')


@settings(max_examples=200, derandomize=True, database=None, deadline=None)
@given(st.integers(1, 12), st.integers(1, 12), st.data())
def test_json_round_trip_property(width, height, data):
    occ = data.draw(st.binary(min_size=width * height,
                              max_size=width * height))
    occ = bytes(b % 3 for b in occ)
    cost = data.draw(st.none() | st.lists(
        st.floats(0, 1e6, allow_nan=False), min_size=width * height,
        max_size=width * height))
    m = LabMap(width, height, occ, cost, map_id='p')
    assert LabMap.from_json(m.to_json()) == m


# -- the move model is a run input -----------------------------------------

def test_to_grid_applies_the_unknown_policy():
    m, marks = small()
    blocked = m.to_grid(unknown='blocked')
    free = m.to_grid(unknown='free')
    assert blocked.is_blocked((1, 1)) and not free.is_blocked((1, 1))
    assert blocked.is_blocked((0, 2)) and free.is_blocked((0, 2))
    with pytest.raises(MapError):
        m.to_grid(unknown='maybe')


def test_one_map_many_move_models():
    m, marks = LabMap.from_ascii("""
        S#
        #G
    """)
    s, g = marks['S'], marks['G']
    assert search(m.to_grid(connectivity=4), s, g, 'bfs').status == 'no_path'
    assert search(m.to_grid(corner_cutting=False), s, g,
                  'bfs').status == 'no_path'
    assert search(m.to_grid(corner_cutting=True), s, g,
                  'dijkstra').cost == pytest.approx(2 ** 0.5)
    assert search(m.to_grid(corner_cutting=True, diagonal_cost=1.0), s, g,
                  'dijkstra').cost == 1.0


def test_the_cost_layer_reaches_the_grid():
    m = LabMap(2, 1, b'\x00\x00', cost=[0.0, 252.0])
    assert m.to_grid(cost_weight=2.0).edge_cost((0, 0), (0, 1)) == 3.0
    assert m.to_grid(cost_weight=0.0).edge_cost((0, 0), (0, 1)) == 1.0


# -- downsampling ------------------------------------------------------------

def test_downsample_is_conservative_and_keeps_the_origin():
    m = LabMap.from_ascii("""
        ....?
        ..#..
        .....
    """, resolution=0.05, origin=(1.0, 2.0), frame='map')[0]
    d = m.downsample(2)
    # 5 x 3 -> 3 x 2, blocks anchored at the bottom-left, so the top row
    # of the coarse map covers only the fine map's row 0.
    assert (d.width, d.height) == (3, 2)
    assert d.to_ascii() == '..?\n.#.'
    assert d.origin == (1.0, 2.0) and d.resolution == pytest.approx(0.1)
    # Conservative: every coarse free cell is free at full resolution.
    for r in range(d.height):
        for c in range(d.width):
            if d.at((r, c)) == FREE:
                x, y = d.cell_centre(r, c)
                for dx in (-0.025, 0.025):
                    for dy in (-0.025, 0.025):
                        fine = m.cell_at(x + dx, y + dy)
                        assert fine is None or m.at(fine) == FREE
    assert m.downsample(1).occupancy == m.occupancy
    with pytest.raises(MapError):
        m.downsample(0)


# -- rasterising -------------------------------------------------------------

def test_centre_and_overlap_rules_differ_exactly_at_partial_cells():
    r = Raster(10, 1, 1.0, (0.0, 0.0))
    assert r.paint(2.6, 4.4, 0.0, 1.0, OCCUPIED, 'centre') == 1   # 3.5
    r2 = Raster(10, 1, 1.0, (0.0, 0.0))
    assert r2.paint(2.6, 4.4, 0.0, 1.0, OCCUPIED, 'overlap') == 3  # 2, 3, 4
    # A wall thinner than a cell and between centres: the centre rule
    # loses it, the overlap rule keeps it.
    r3 = Raster(10, 1, 1.0, (0.0, 0.0))
    assert r3.paint(3.6, 3.9, 0.0, 1.0, OCCUPIED, 'centre') == 0
    assert r3.paint(3.6, 3.9, 0.0, 1.0, OCCUPIED, 'overlap') == 1
    with pytest.raises(MapError):
        r3.paint(0, 1, 0, 1, OCCUPIED, 'nearest')


def test_overlap_matches_the_navigation_world_generator_rule():
    # gen_navigation_world.py: a - res/2 < x < b + res/2 on cell centres.
    res, ox, oy = 0.05, -8.5, -9.5
    box = (1.013, 1.387, -0.41, 0.1)
    r = Raster(60, 60, res, (ox, oy))
    r.paint(*box, OCCUPIED, 'overlap')
    for row in range(60):
        y = oy + (60 - row - .5) * res
        for col in range(60):
            x = ox + (col + .5) * res
            expect = (box[0] - res / 2 < x < box[1] + res / 2
                      and box[2] - res / 2 < y < box[3] + res / 2)
            assert (r.cells[row * 60 + col] == OCCUPIED) == expect


def test_later_paints_override_earlier_ones():
    r = Raster(4, 1, 1.0, (0.0, 0.0), fill=UNKNOWN)
    r.paint(0, 4, 0, 1, FREE)
    r.paint(1, 2, 0, 1, OCCUPIED)
    m = r.build('r', frame='map')
    assert m.to_ascii() == '.#..' and m.frame == 'map'


def test_compare_occupied():
    truth = LabMap.from_ascii('##..\n##..')[0]
    test = LabMap.from_ascii('#?#.\n##..')[0]
    out = maps.compare_occupied(truth, test)
    assert (out['true_positive'], out['false_positive'],
            out['false_negative'],
            out['truth_occupied_marked_unknown']) == (3, 1, 0, 1)
    assert out['precision'] == 0.75 and out['recall'] == 0.75
    with pytest.raises(MapError):
        maps.compare_occupied(truth, LabMap.from_ascii('###')[0])


# -- Nav2 saved maps ---------------------------------------------------------

YAML = """image: m.pgm
mode: trinary
resolution: 0.05
origin: [-6.5, -9.5, 0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
"""


def test_nav2_trinary_thresholds_match_map_server():
    # 254 -> free, 0 -> occupied, 205 -> unknown (map_saver's values), and
    # the threshold edges: occ = (255 - p) / 255.
    pixels = bytes([254, 0, 205, 89, 90, 205, 206, 255])
    pgm = b'P5\n# a comment\n8 1\n255\n' + pixels
    m = maps.from_nav2(YAML, pgm, map_id='n')
    # p=89 -> occ 0.651 > 0.65 occupied; p=90 -> 0.647 unknown;
    # p=206 -> 0.192 < 0.196 free; p=205 -> 0.196 unknown.
    assert m.to_ascii() == '.#?#??..'
    assert m.resolution == 0.05 and m.origin == (-6.5, -9.5)
    assert m.frame == 'map' and m.meta['source'] == 'nav2_map_server'


def test_nav2_negate_and_p2():
    y = YAML.replace('negate: 0', 'negate: 1')
    m = maps.from_nav2(y, b'P2\n2 1\n255\n0 254\n')
    assert m.to_ascii() == '.#'


def test_nav2_round_trip():
    m = LabMap.from_ascii('.#?\n..#', resolution=0.05,
                          origin=(-6.5, -9.5), frame='map')[0]
    yaml_text, pgm = maps.to_nav2(m, 'x.pgm')
    back = maps.from_nav2(yaml_text, pgm)
    assert back.occupancy == m.occupancy
    assert (back.resolution, back.origin) == (m.resolution, m.origin)
    # map_saver writes 205 for unknown; with free_thresh 0.25 that would
    # read back FREE (occ = 0.196). to_nav2 writes 0.196 so it cannot.
    assert maps.from_nav2(yaml_text.replace('0.196', '0.25'),
                          pgm).at((0, 2)) == FREE
    with pytest.raises(MapError):
        maps.to_nav2(LabMap(1, 1, b'\x00', cost=[1.0], resolution=1,
                            origin=(0, 0)), 'x.pgm')


@pytest.mark.parametrize('yaml_text,match', [
    (YAML + 'extra: 1\n', 'unknown key'),
    (YAML + 'resolution: 0.1\n', 'duplicate'),
    (YAML.replace('trinary', 'scale'), 'trinary'),
    (YAML.replace('[-6.5, -9.5, 0]', '[-6.5, -9.5, 0.3]'), 'yaw'),
    (YAML.replace('[-6.5, -9.5, 0]', '[-6.5, -9.5]'), 'origin'),
    (YAML.replace('negate: 0', 'negate: 2'), 'negate'),
    (YAML.replace('free_thresh: 0.196', 'free_thresh: 0.9'), 'thresh'),
    ('image: m.pgm\n  nested: 1\n', 'flat'),
    ('mode: trinary\n', "no 'image'"),
])
def test_nav2_yaml_outside_the_language_is_refused(yaml_text, match):
    with pytest.raises(MapError, match=match):
        maps.from_nav2(yaml_text, b'P5\n1 1\n255\n\xfe')


@pytest.mark.parametrize('pgm,match', [
    (b'P6\n1 1\n255\n\x00', 'magic'),
    (b'P5\n2 2\n255\n\x00', 'pixel bytes'),
    (b'P5\n1 1\n65535\n\x00\x00', 'maxval'),
    (b'P5\n1\n', 'header'),
    (b'P5\n1 1\n100\n\xff', 'exceeds'),
    (b'P5\n99999 99999\n255\n', 'exceeds|width|height'),
    (b'P2\n2 1\n255\n1\n', 'pixels'),
])
def test_malformed_pgm_is_refused(pgm, match):
    with pytest.raises(MapError, match=match):
        maps.parse_pgm(pgm)


def test_the_repository_navigation_map_loads():
    here = os.path.dirname(__file__)
    yaml_path = os.path.join(here, '..', '..', 'gazebo_models', 'maps',
                             'coco_navigation.yaml')
    if not os.path.exists(yaml_path):
        pytest.skip('not run from a repository checkout')
    m = maps.load_nav2(yaml_path, map_id='coco_navigation')
    assert (m.width, m.height, m.resolution) == (500, 380, 0.05)
    assert m.origin == (-6.5, -9.5)
    assert m.count(OCCUPIED) > 0 and m.count(UNKNOWN) > 0


# -- the document ------------------------------------------------------------

def test_the_doc_matches_the_implementation():
    with open(DOC) as f:
        doc = f.read()
    assert f'`{maps.SCHEMA}`' in doc
    assert f'"{maps.VERSION}"' in doc
    for ch, name in zip(maps.CELL_CHARS, ('free', 'occupied', 'unknown')):
        assert re.search(rf'`{re.escape(ch)}`[^\n]*{name}', doc), (ch, name)
    for field in ('schema', 'version', 'id', 'width', 'height', 'rows',
                  'cost', 'geo', 'meta', 'content_hash'):
        assert f'`{field}`' in doc, field
    for key in maps.NAV2_KEYS:
        assert f'`{key}`' in doc, key
    for rule in maps.RULES:
        assert f'`{rule}`' in doc, rule
    assert 'coco_lab.map/1 <width> <height>' in doc
