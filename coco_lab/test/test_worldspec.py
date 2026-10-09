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
World Spec v1 (M1.2): the COCO arena spec and what is generated from it.

The canonical form, and the Arena world generated from the spec -- which
must equal the Stack's own saved map cell for cell, and whose boxes must
equal the Gazebo world's models.
"""

import copy
import os
import random
import subprocess
import sys
import xml.etree.ElementTree as ET

from coco_lab.maps import load_nav2
from coco_lab.sketch import COCO_LIDAR, ROBOT_RADIUS
from coco_lab.worldspec import (arena_map, canonical_bytes, normalize,
                                ramp_rectangles, scan_height, SpecError)
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SPEC = os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')
NAV_MAP = os.path.join(REPO, 'gazebo_models', 'maps', 'coco_navigation.yaml')
NAV_WORLD = os.path.join(REPO, 'gazebo_models', 'worlds',
                         'coco_navigation.world')


@pytest.fixture(scope='module')
def spec():
    with open(SPEC, encoding='utf-8') as f:
        return yaml.safe_load(f)


def test_the_spec_is_current_with_its_sources():
    """worlds/coco_arena_v1.yaml is exactly what its sources generate."""
    r = subprocess.run([sys.executable, os.path.join(
        REPO, 'worlds', 'tools', 'make_coco_arena_v1.py'), '--check'],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_spec_validates_and_names_its_sources(spec):
    n = normalize(spec)
    assert n['spec_version'] == 'coco.world_spec.v1'
    assert len(n['boxes']) == 70
    assert set(n['sources']) >= {'geometry', 'robot'}
    # the robot block agrees with coco_lab's own Sketch constants
    li = n['robot']['lidar']
    assert (li['samples'], li['angle_min'], li['angle_max'],
            li['range_min'], li['range_max']) == (
        COCO_LIDAR.samples, COCO_LIDAR.angle_min, COCO_LIDAR.angle_max,
        COCO_LIDAR.range_min, COCO_LIDAR.range_max)
    assert li['mount'][:2] == list(COCO_LIDAR.mount[:2])
    assert n['robot']['radius'] == ROBOT_RADIUS


def test_canonical_bytes_ignore_how_numbers_were_written(spec):
    a = canonical_bytes(spec)
    b = copy.deepcopy(spec)
    b['boxes'][0]['center'] = [float(v) for v in b['boxes'][0]['center']]
    b['bounds']['x_min'] = float(b['bounds']['x_min'])
    assert canonical_bytes(b) == a
    c = copy.deepcopy(spec)
    c['boxes'][0]['center'][0] += 0.001
    assert canonical_bytes(c) != a
    assert a == canonical_bytes(normalize(spec))  # idempotent


def test_the_arena_world_equals_the_stacks_saved_map(spec):
    """Cell for cell: occupancy, size, resolution and origin (map frame)."""
    arena = arena_map(spec)
    nav = load_nav2(NAV_MAP)
    assert (arena.width, arena.height) == (nav.width, nav.height)
    assert arena.resolution == nav.resolution
    assert arena.origin == pytest.approx(nav.origin, abs=1e-12)
    assert arena.occupancy == nav.occupancy
    assert arena.frame == 'map'


def test_every_box_is_the_gazebo_worlds_model(spec):
    """Designed for SDF: the spec carries each box's 3D pose and size."""
    world = ET.parse(NAV_WORLD).getroot().find('world')
    models = {}
    for m in world.findall('model'):
        if m.get('name') == 'ground_plane':
            continue
        pose = [float(v) for v in m.find('pose').text.split()]
        size = [float(v) for v in m.find('.//collision//box/size').text.split()]
        models[m.get('name')] = (pose[:3], size)
    boxes = {b['id']: b for b in normalize(spec)['boxes']}
    assert set(boxes) == set(models)
    for name, (pose, size) in models.items():
        b = boxes[name]
        assert b['center'] + [b['z']] == pose, name
        assert b['size'] + [b['height']] == size, name


def test_ramps_are_their_scan_height_silhouette(spec):
    n = normalize(spec)
    assert scan_height(n) == pytest.approx(0.2135)
    (x0, x1, y0, y1) = ramp_rectangles(n)[0]
    assert y1 - y0 == n['ramps']['width']
    assert x0 > n['ramps']['foot_x']
    assert x1 < n['ramps']['foot_x'] + 2 * n['ramps']['run'] + \
        n['ramps']['platform_length']


def reference_occupancy(spec):
    """arena_map's rules, cell by cell against every rectangle (M1.2's code)."""
    from coco_lab.maps import FREE, OCCUPIED, UNKNOWN
    from coco_lab.worldspec import box_rectangles
    spec = normalize(spec)
    b, res = spec['bounds'], spec['arena']['resolution']
    m = spec['arena']['margin']
    ox, oy = b['x_min'] - m, b['y_min'] - m
    width = round((b['x_max'] - b['x_min'] + 2 * m) / res)
    height = round((b['y_max'] - b['y_min'] + 2 * m) / res)
    ramps, boxes = ramp_rectangles(spec), box_rectangles(spec)
    h = res / 2
    occ = bytearray(width * height)
    for row in range(height):
        y = oy + (height - row - 0.5) * res
        for col in range(width):
            x = ox + (col + 0.5) * res
            v = FREE if (b['x_min'] < x < b['x_max']
                         and b['y_min'] < y < b['y_max']) else UNKNOWN
            for a, bb, c, d in ramps:
                if a - h < x < bb + h and c - h < y < d + h:
                    v = (OCCUPIED if min(abs(x - a), abs(x - bb), abs(y - c),
                                         abs(y - d)) <= res else UNKNOWN)
            for a, bb, c, d in boxes:
                if a - h < x < bb + h and c - h < y < d + h:
                    v = OCCUPIED
                    break
            occ[row * width + col] = v
    return bytes(occ)


def test_the_fast_rasteriser_equals_the_cell_by_cell_rules(spec):
    """Random worlds, including boxes on cell edges and off the map."""
    rng = random.Random(9)
    for k in range(25):
        s = copy.deepcopy(spec)
        s['bounds'] = {'x_min': rng.uniform(-3, -1), 'x_max': rng.uniform(2, 6),
                       'y_min': rng.uniform(-3, -1), 'y_max': rng.uniform(1, 4)}
        s['arena']['resolution'] = rng.choice([0.05, 0.1, 0.13])
        s['arena']['margin'] = rng.choice([0.0, 0.5, 0.25])
        s['ramps']['centres_y'] = [rng.uniform(-2, 3)]
        s['ramps']['foot_x'] = rng.uniform(-2, 2)
        s['boxes'] = []
        for i in range(rng.randint(1, 12)):
            # snap some boxes to exact cell edges, where < vs <= matters
            snap = rng.random() < 0.4
            cx = round(rng.uniform(-4, 7) / 0.05) * 0.05 if snap \
                else rng.uniform(-4, 7)
            s['boxes'].append({'id': f'b{i}', 'kind': 'obstacle',
                               'center': [cx, rng.uniform(-4, 5)],
                               'size': [rng.uniform(0.01, 3),
                                        rng.uniform(0.01, 3)],
                               'z': 0.5, 'height': 1.0})
        assert arena_map(s).occupancy == reference_occupancy(s), k


@pytest.mark.parametrize('mutate,match', [
    (lambda s: s.update(spec_version='coco.world_spec.v2'), 'knows'),
    (lambda s: s.update(colour='red'), 'unknown keys'),
    (lambda s: s.pop('robot'), 'missing'),
    (lambda s: s['boxes'][0].update(kind='lava'), 'kind'),
    (lambda s: s['boxes'][1].update(id=s['boxes'][0]['id']), 'used twice'),
    (lambda s: s['bounds'].update(x_min=99), 'inverted'),
    (lambda s: s['boxes'][0].update(size=[0, 1]), 'size'),
    (lambda s: s['robot']['lidar'].update(samples=0), 'samples'),
    (lambda s: s['robot']['lidar'].update(samples=True), 'samples'),
    (lambda s: s['arena'].update(unknown='free'), 'unknown'),
    (lambda s: s['ramps'].update(angle_deg=95), 'angle_deg'),
    (lambda s: s.update(frame='map'), 'frame'),
])
def test_bad_specs_are_refused_never_guessed(spec, mutate, match):
    s = copy.deepcopy(spec)
    mutate(s)
    with pytest.raises(SpecError, match=match):
        normalize(s)
