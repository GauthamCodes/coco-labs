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

"""Lab 5's bundle formats (coco_lab.movebundle): write, read, replay, refuse."""

import gzip
import json
import math
import os

from coco_lab import bundle as b
from coco_lab import movebundle as mb
from coco_lab import movemetrics as mm
from coco_lab.replan import run_replan, sketch_world
import pytest


def sketch_prov(seed=0):
    return b.make_provenance('sketch', seed=seed,
                             created_utc='2026-10-07T00:00:00Z')


def recorded_prov():
    # Lab 4's convention for a multi-run bundle: the hash of the sorted
    # per-run bag hashes (each run's record carries its own)
    return b.make_provenance('recorded-run', rosbag={
        'sha256': 'ab' * 32, 'sim_time_start': 0.0, 'sim_time_end': 10.0})


# -- replan bundle ------------------------------------------------------------

def test_a_replan_bundle_round_trips_and_replays(tmp_path):
    res = run_replan(sketch_world(4))
    h = mb.write_replan_bundle(res, sketch_prov(4), str(tmp_path))
    assert h.startswith('sha256:')
    m, world = mb.load_replan_bundle(str(tmp_path))
    assert m['summary'] == json.loads(json.dumps(res.summary()))
    assert world.truth == res.world.truth and world.known == res.world.known
    assert mb.replay_replan(str(tmp_path))['content_hash'] == h
    assert mb.ensure(str(tmp_path)) == mb.REPLAN_SCHEMA


def test_the_same_episode_writes_the_same_bytes(tmp_path):
    a, c = tmp_path / 'a', tmp_path / 'c'
    mb.write_replan_bundle(run_replan(sketch_world(2)), sketch_prov(2), str(a))
    mb.write_replan_bundle(run_replan(sketch_world(2)), sketch_prov(2), str(c))
    for name in os.listdir(a):
        assert (a / name).read_bytes() == (c / name).read_bytes()


def test_a_tampered_array_is_refused(tmp_path):
    mb.write_replan_bundle(run_replan(sketch_world(1)), sketch_prov(1),
                           str(tmp_path), compression='none')
    p = tmp_path / 'arrays.bin'
    raw = bytearray(p.read_bytes())
    raw[0] ^= 1
    p.write_bytes(bytes(raw))
    with pytest.raises(mb.MoveBundleError, match='content_hash'):
        mb.load_replan_bundle(str(tmp_path))


def test_a_bundle_whose_arrays_tell_another_story_fails_replay(tmp_path):
    # a VALID bundle (its hash matches) whose recorded walk is not the walk
    # its world produces: replay must refuse it. (Changing an obstacle the
    # robot never senses would NOT do: that is another world with the same
    # episode, and replaying it reproduces every byte.)
    res = run_replan(sketch_world(3))
    arrays = mb.replan_arrays(res)
    k = [n for n, _, _ in arrays].index('walk')
    walk = [v for c in res.walk for v in c]
    walk[-4:] = walk[-2:] + walk[-4:-2]          # swap the last two cells
    arrays[k] = ('walk', 'i32', mb._pack('i32', walk))
    mb._write(mb.replan_body(res, sketch_prov(3)), arrays, str(tmp_path),
              'gzip')
    mb.load_replan_bundle(str(tmp_path))            # structurally fine
    with pytest.raises(mb.MoveBundleError, match='replay'):
        mb.replay_replan(str(tmp_path))


def test_an_unknown_major_and_a_stranger_array_are_refused(tmp_path):
    res = run_replan(sketch_world(0))
    body = mb.replan_body(res, sketch_prov())
    mb._write(dict(body, version='2.0'), mb.replan_arrays(res),
              str(tmp_path / 'v2'), 'none')
    with pytest.raises(mb.MoveBundleError, match='major version 2'):
        mb.load_replan_bundle(str(tmp_path / 'v2'))
    mb._write(body, mb.replan_arrays(res) + [('extra', 'u8', b'\x00')],
              str(tmp_path / 'x'), 'none')
    with pytest.raises(mb.MoveBundleError, match='unexpected arrays'):
        mb.load_replan_bundle(str(tmp_path / 'x'))


def test_a_replan_bundle_is_a_sketch_or_glass_box(tmp_path):
    with pytest.raises(mb.MoveBundleError):
        mb.write_replan_bundle(run_replan(sketch_world(0)), recorded_prov(),
                               str(tmp_path))


def test_a_gzip_bomb_stops_at_the_table(tmp_path):
    res = run_replan(sketch_world(0))
    mb.write_replan_bundle(res, sketch_prov(), str(tmp_path))
    (tmp_path / 'arrays.bin.gz').write_bytes(
        gzip.compress(b'\x00' * (50 * 1024 * 1024), mtime=0))
    with pytest.raises(mb.MoveBundleError):
        mb.load_replan_bundle(str(tmp_path))


# -- drive bundle ---------------------------------------------------------------

def drive_data(rollouts=True):
    path = [[x / 10, 0.0, 0.0] for x in range(31)]
    scenario = {'id': 'toy', 'title': 'a toy', 'path': path,
                'path_sha256': 'cd' * 32, 'start': [0, 0, 0],
                'goal': [3, 0, 0], 'boxes': [[1.5, 1.0, 0.2, 0.2]],
                'actor_radius': 0.15, 'actors_spec': [], 'inject': None}
    gt = [[t / 10, 0.1 * t / 10, 0.02, 0.0] for t in range(31)]
    run = {'id': 'DWB_1', 'controller': 'DWB', 'outcome': 'succeeded',
           'window': [0.0, 3.0], 'record': {'run_id': 'x'},
           'gt': gt, 'amcl': [[0.0, 0.0, 0.0, 0.0], [2.0, 0.2, 0.0, 0.0]],
           'cmd': [[t / 10, 0.1, 0.0] for t in range(31)],
           'wheel': [[t / 10, 0.1, 0.0] for t in range(31)],
           'actors': {'actor_0': [[0.0, 2.0, -1.0, 1.57],
                                  [3.0, 2.0, 1.0, 1.57]]},
           'chosen': [[0.5, [[0.05, 0.0], [0.2, 0.0]]], [1.0, [[0.1, 0]]]],
           'eval': [[0.5, 819, 819], [1.0, 819, 0]],
           'monitor': [[1.0, 2, 'PolygonSlow']],
           'actor_trigger': {'actor_0': 0.0}}
    if rollouts:
        run['rollouts'] = [{'t': 0.5, 'n': 819, 'n_valid': 400, 'candidates': [
            {'pts': [[0, 0], [0.1, 0]], 'total': 3.5, 'valid': True,
             'best': True},
            {'pts': [[0, 0], [0.1, 0.1]], 'total': -1.0, 'valid': False,
             'best': False}]},
            {'t': 1.0, 'n': 400, 'n_valid': None, 'candidates': [
                {'pts': [[0, 0]], 'total': None, 'valid': None,
                 'best': False}]}]
    return scenario, [run]


def test_a_drive_bundle_round_trips_and_its_metrics_replay(tmp_path):
    scenario, runs = drive_data()
    h = mb.write_drive_bundle(scenario, runs, recorded_prov(), str(tmp_path))
    m = mb.replay_drive(str(tmp_path))
    assert m['content_hash'] == h
    _, sc, back = mb.load_drive_bundle(str(tmp_path))
    r = back[0]
    assert sc['path'] == scenario['path']
    assert r['gt'] == runs[0]['gt'] and r['chosen'] == runs[0]['chosen']
    want = mm.evaluate(scenario['path'], runs[0]['gt'], (0.0, 3.0),
                       runs[0]['cmd'], [tuple(x) for x in scenario['boxes']],
                       [{'radius': 0.15, 'track': [(0.0, 2.0, -1.0),
                                                   (3.0, 2.0, 1.0)]}])
    assert r['metrics'] == json.loads(json.dumps(want))
    ro = r['rollouts']
    assert ro['n'] == [819, 400, 400, -1]
    assert list(ro['flags']) == [1 | 4, 0, 2]
    assert ro['total'][:2] == [3.5, -1.0] and math.isnan(ro['total'][2])
    assert mb.ensure(str(tmp_path)) == mb.DRIVE_SCHEMA


def test_runs_without_rollouts_carry_none(tmp_path):
    scenario, runs = drive_data(rollouts=False)
    mb.write_drive_bundle(scenario, runs, recorded_prov(), str(tmp_path))
    _, _, back = mb.load_drive_bundle(str(tmp_path))
    assert 'rollouts' not in back[0]


def test_a_metric_that_does_not_reproduce_is_refused(tmp_path):
    scenario, runs = drive_data()
    body = mb.drive_body(scenario, runs, recorded_prov())
    body['runs'][0]['metrics']['time_s'] = 2.5
    mb._write(body, mb.drive_arrays(scenario, runs), str(tmp_path), 'gzip')
    with pytest.raises(mb.MoveBundleError, match='metrics differ'):
        mb.replay_drive(str(tmp_path))


@pytest.mark.parametrize('change, match', [
    (lambda r: r.update(controller='TEB'), 'controller'),
    (lambda r: r.update(outcome='won'), 'outcome'),
    (lambda r: r['gt'].reverse(), 'back in time'),
    (lambda r: r.update(window=[3.0, 1.0]), 'window'),
    (lambda r: r['cmd'][0].__setitem__(1, math.nan), 'finite'),
])
def test_bad_drive_data_is_refused(tmp_path, change, match):
    scenario, runs = drive_data()
    change(runs[0])
    with pytest.raises(mb.MoveBundleError, match=match):
        mb.write_drive_bundle(scenario, runs, recorded_prov(), str(tmp_path))


def test_a_drive_bundle_is_a_recording(tmp_path):
    scenario, runs = drive_data()
    with pytest.raises(mb.MoveBundleError):
        mb.write_drive_bundle(scenario, runs, sketch_prov(), str(tmp_path))


def test_the_golden_bundles_are_what_the_writer_writes(tmp_path):
    import golden_move_bundles
    golden_move_bundles.make(str(tmp_path))
    here = os.path.join(os.path.dirname(__file__), 'fixtures',
                        'move_bundles')
    names = sorted(os.listdir(here))
    assert names == ['drive_toy_gz', 'replan_small']
    for name in names:
        for f in sorted(os.listdir(os.path.join(here, name))):
            with open(os.path.join(here, name, f), 'rb') as a, \
                    open(os.path.join(tmp_path, name, f), 'rb') as c:
                assert a.read() == c.read(), (name, f)
    mb.replay_replan(os.path.join(here, 'replan_small'))
    mb.replay_drive(os.path.join(here, 'drive_toy_gz'))


def test_the_format_document_matches_the_code():
    doc = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'labs',
                       'MOVE_FORMAT.md')
    with open(doc, encoding='utf-8') as f:
        text = f.read()
    for needle in (mb.REPLAN_SCHEMA, mb.DRIVE_SCHEMA, f'`{mb.VERSION}`',
                   f'1 to {mb.MAX_RUNS}'):
        assert needle in text, needle
    names = {n for n, _, _ in mb.replan_arrays(run_replan(sketch_world(0)))}
    scenario, runs = drive_data()
    names |= {n.replace('DWB_1', '<id>').replace('actor_0', '<aid>')
              for n, _, _ in mb.drive_arrays(scenario, runs)}
    for n in sorted(names):
        if n.startswith('trace.'):
            assert n[6:] in text, n
        elif n.startswith('run.<id>.roll.'):
            assert 'run.<id>.roll.*' in text and n.split('.')[-1] in text, n
        elif n.startswith('run.<id>.chosen.'):
            assert 'run.<id>.chosen.t' in text, n
        else:
            assert f'`{n}`' in text, n
