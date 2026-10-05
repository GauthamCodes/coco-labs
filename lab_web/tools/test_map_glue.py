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
Lab 3's worker glue (``recompute.mapping``), run under CPython.

The same file the browser runs. Every output is re-read with coco_lab's
``load_slam_bundle`` and REPLAYED, so what the page draws is a bundle
coco_lab accepts and can reproduce; the learner's drive and settings reach
the world exactly as the glue's docstring says; refusals are explained,
never crashes.
"""

import json
import os
import sys

from coco_lab import map_teaching, mapworld, slambundle
import common
import pytest

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import recompute  # noqa: E402
sys.dont_write_bytecode = _dont_write

FIXTURES = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures',
                        'slam_bundles')
BASE = {'clicks': [[6.0, 2.0], [4.0, 1.5]], 'noise_scale': 3.0,
        'particles': 4, 'fastslam_seed': 0, 'seed': 31,
        'runs': ['known', 'odometry', 'pose_graph']}


@pytest.fixture(autouse=True)
def fresh_worker():
    """Each test starts with a worker that has validated nothing."""
    recompute._SLAM_CACHE.clear()
    recompute._SMAPS.clear()
    yield


def files(name='loop_small'):
    d = os.path.join(FIXTURES, name)
    arrays = [n for n in os.listdir(d) if n.startswith('arrays')][0]
    with open(os.path.join(d, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(d, arrays), 'rb') as f:
        a = f.read()
    return m, arrays, a


def run(tmp_path, **over):
    m, name, a = files()
    out = recompute.mapping(json.dumps(dict(BASE, **over)), m, name, a)
    b = out['bundles'][0]
    d = tmp_path / 'out'
    d.mkdir(exist_ok=True)
    (d / 'manifest.json').write_bytes(b['manifest'])
    (d / b['arrays_name']).write_bytes(b['arrays_file'])
    sb = slambundle.load_slam_bundle(str(d))
    assert sb.manifest()['content_hash'] == b['content_hash']
    return out, sb


def test_the_glue_returns_a_bundle_coco_lab_loads_and_replays(tmp_path):
    out, sb = run(tmp_path)
    slambundle.replay_check(sb)
    assert [rid for rid, _ in sb.runs] == ['known', 'odometry', 'pose_graph']
    assert sb.provenance['tool'] == 'lab_web/pyodide'
    assert out['timings']['runs'] == 3


def test_the_glue_is_exactly_coco_labs_computation(tmp_path):
    """The page's settings reach coco_lab unchanged: same world, same runs."""
    from coco_lab.sketch import SketchMap
    _, sb = run(tmp_path)
    base = slambundle.load_slam_bundle(os.path.join(FIXTURES, 'loop_small'))
    sc = map_teaching.scenario_for(base.world.scenario,
                                   SketchMap(base.lab_map),
                                   [(6.0, 2.0), (4.0, 1.5)], 3.0, 31)
    w = mapworld.from_sketch(base.lab_map, sc, base.world.landmark_spec)
    again = slambundle.SlamBundle.compute(
        base.lab_map, w, map_teaching.run_specs(
            scale=3.0, particles=4, ids=('known', 'odometry', 'pose_graph')),
        sb.provenance)
    assert {n: d for n, _, d in again.arrays()} == \
        {n: d for n, _, d in sb.arrays()}


def test_a_click_inside_a_wall_is_refused_with_a_reason(tmp_path):
    with pytest.raises(recompute.Refused, match='cannot be reached'):
        run(tmp_path, clicks=[[8.0, 5.0]])  # inside the loop room's block


def test_bad_settings_are_refused(tmp_path):
    for over, msg in (({'clicks': []}, 'waypoints'),
                      ({'runs': ['nope']}, 'runs must be'),
                      ({'noise_scale': 9}, 'noise_scale'),
                      ({'particles': 1}, 'particles')):
        with pytest.raises(recompute.Refused, match=msg):
            run(tmp_path, **over)


def test_a_recording_cannot_be_driven_again():
    m, name, a = files('recorded_small_gz')
    with pytest.raises(recompute.Refused, match='recording'):
        recompute.mapping(json.dumps(BASE), m, name, a)


def test_a_second_request_reuses_the_validated_bundle(tmp_path):
    out1, _ = run(tmp_path)
    out2, _ = run(tmp_path, seed=32)
    assert out2['timings']['load_bundle_ms'] == 0.0
    assert out1['bundles'][0]['content_hash'] != \
        out2['bundles'][0]['content_hash']
