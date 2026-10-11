# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
The World Spec agrees with COCO's Gazebo world (M4.2; README §5.1, §7 M4.2;
docs/v2/adr/0007-world-spec-elevation.md).

The reference is the recorded SDF world, converted by
lab_web/tools/assets/convert_world.py into lab_web/public/assets3d/arena.json
(every box's footprint, and the ramp bays `traverse:=true` spawns). Every
obstacle footprint, centre height and height of World Spec v1, and every
wedge and platform of World Spec v2, must agree with it within TOLERANCE.
On a disagreement the World Spec is fixed, never the SDF.
"""

import json
import math
import os

import yaml

from coco_lab.worldspec import normalize

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
#: metres (and radians for a yaw): 1 mm
TOLERANCE = 1e-3
SDF = json.load(open(os.path.join(REPO, 'lab_web', 'public', 'assets3d', 'arena.json')))
V1 = normalize(yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'))))
V2 = normalize(yaml.safe_load(open(os.path.join(REPO, 'worlds', 'coco_arena_v2.yaml'))))


def close(a, b):
    return all(abs(x - y) <= TOLERANCE for x, y in zip(a, b)) and len(a) == len(b)


def same_yaw(a, b):
    return abs(math.remainder(a - b, 2 * math.pi)) <= TOLERANCE


def test_every_box_of_the_spec_is_a_box_of_the_recorded_world_and_back():
    sdf = {f['name']: f for f in SDF['footprints'] if f['kind'] not in ('ramps', 'platforms')}
    spec = {b['id']: b for b in V1['boxes']}
    assert set(spec) == set(sdf) and len(spec) == 70
    for name, f in sdf.items():
        b = spec[name]
        assert close(b['center'], f['center'][:2]), name           # footprint centre
        assert close(b['size'], f['size'][:2]), name                # footprint size
        assert same_yaw(0.0, f['yaw']), name                        # the spec's boxes are axis-aligned
        assert close([b['z'], b['height']], [f['center'][2], f['size'][2]]), name


def test_every_wedge_and_platform_of_v2_is_one_the_recorded_world_spawns_and_back():
    wedges = [e for e in V2['elevation'] if e['kind'] == 'wedge']
    plats = [e for e in V2['elevation'] if e['kind'] == 'platform']
    sw = [f for f in SDF['footprints'] if f['kind'] == 'ramps']
    sp = [f for f in SDF['footprints'] if f['kind'] == 'platforms']
    assert (len(wedges), len(plats)) == (len(sw), len(sp)) == (8, 4)
    for f in sw:
        m = [w for w in wedges if close(w['foot'], f['foot'][:2]) and same_yaw(w['yaw'], f['yaw'])]
        assert len(m) == 1, f['name']
        assert close([m[0]['run'], m[0]['rise'], m[0]['width']], [f['run'], f['rise'], f['width']]), f['name']
    for f in sp:
        m = [p for p in plats if close(p['center'], f['center'][:2])]
        assert len(m) == 1, f['name']
        assert close(m[0]['size'], f['size']), f['name']
        assert close([f['center'][2]], [m[0]['size'][2] / 2]), f['name']   # stands on the ground


def test_v2_is_v1_plus_its_elevation():
    strip = lambda s: {k: v for k, v in s.items() if k not in ('spec_version', 'id', 'title', 'elevation')}  # noqa: E731
    assert strip(V1) == strip(V2)
    assert V1['spec_version'] == 'coco.world_spec.v1' and V2['spec_version'] == 'coco.world_spec.v2'


def test_the_spec_files_are_what_their_generators_make():
    import subprocess
    import sys
    for g in ('make_coco_arena_v1.py', 'make_coco_arena_v2.py'):
        r = subprocess.run([sys.executable, os.path.join(REPO, 'worlds', 'tools', g), '--check'],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
