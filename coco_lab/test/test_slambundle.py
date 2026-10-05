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

"""Map bundle 1.0: round trip, byte stability, replay, refusals."""

import json
import math
import os

from coco_lab import bundle, loc_teaching, map_teaching, mapworld, slambundle
from coco_lab.sketch import Scenario
import golden_slam_bundles
import pytest

ROUTE = loc_teaching.LANDMARKS_ROUTE[:3]
PROV = {'created_utc': '2026-10-05T00:00:00Z', 'tool': 'test_slambundle'}


def _bundle(ids=('known', 'odometry', 'ekf_slam', 'fastslam', 'pose_graph',
                 'pose_graph_noloop')):
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=ROUTE, seed=4,
                  noise=map_teaching.noise())
    w = mapworld.from_sketch(m, sc)
    specs = map_teaching.run_specs(particles=6, snapshots=4, ids=ids)
    return slambundle.SlamBundle.compute(
        m, w, specs, bundle.make_provenance('sketch', seed=4, **PROV))


@pytest.fixture(scope='module')
def sb():
    return _bundle()


@pytest.fixture(scope='module')
def written(sb, tmp_path_factory):
    d = str(tmp_path_factory.mktemp('slam') / 'b')
    digest = slambundle.write_slam_bundle(sb, d)
    return d, digest


def test_it_round_trips(sb, written):
    d, digest = written
    back = slambundle.load_slam_bundle(d)
    assert back.manifest()['content_hash'] == digest
    assert [r for r, _ in back.runs] == [r for r, _ in sb.runs]
    for (_, a), (_, b) in zip(sb.runs, back.runs):
        assert a.columns == b.columns and a.maps == b.maps
        assert a.summary == b.summary
        for name, (dt, vals) in a.arrays.items():
            got = b.arrays[name][1]
            if dt == 'f32':
                assert all(math.isclose(u, v, rel_tol=1e-6, abs_tol=1e-6)
                           for u, v in zip(vals, got))
            else:
                assert got == vals


def test_the_writer_is_byte_stable(sb, written, tmp_path):
    d, _ = written
    d2 = str(tmp_path / 'again')
    slambundle.write_slam_bundle(sb, d2)
    for name in os.listdir(d):
        with open(os.path.join(d, name), 'rb') as f1, \
                open(os.path.join(d2, name), 'rb') as f2:
            assert f1.read() == f2.read()


def test_it_replays_byte_for_byte(written):
    slambundle.replay_check(slambundle.load_slam_bundle(written[0]))


def test_every_run_read_the_same_world(sb):
    rows = list(sb.world.updates)
    for _, tr in sb.runs:
        assert list(tr.columns['row']) == rows
        assert tr.header['n_updates'] == len(rows)


def test_every_run_is_scored_with_the_documented_definitions(sb):
    m = sb.manifest()
    assert m['scoring'] == {'align': False, 'tol_m': 0.1,
                            'definitions': 'coco_lab.mapeval'}
    for _, tr in sb.runs:
        s = tr.summary
        assert set(s) == {'ate_online', 'ate_final', 'map'}
        assert 0 <= s['map']['f1'] <= 1
        n = len(tr)
        assert len(tr.arrays['score.err_online'][1]) == n
        assert len(tr.arrays['score.diff'][1]) == \
            sb.lab_map.width * sb.lab_map.height


def test_known_poses_score_zero_trajectory_error(sb):
    known = dict(sb.runs)['known']
    assert known.summary['ate_final']['rmse'] == 0.0


def test_a_flipped_byte_is_refused(written, tmp_path):
    import gzip
    import shutil
    d = str(tmp_path / 'bad')
    shutil.copytree(written[0], d)
    p = os.path.join(d, 'arrays.bin.gz')
    raw = bytearray(gzip.decompress(open(p, 'rb').read()))
    raw[1000] ^= 1
    with open(p, 'wb') as f:
        f.write(gzip.compress(bytes(raw), mtime=0))
    with pytest.raises(slambundle.SlamBundleError, match='content_hash'):
        slambundle.load_slam_bundle(d)


def test_an_unknown_major_is_refused(written):
    m = json.loads(open(os.path.join(written[0], 'manifest.json')).read())
    m['version'] = '2.0'
    with pytest.raises(slambundle.SlamBundleError, match='major'):
        slambundle.parse_manifest(json.dumps(m).encode())


def test_a_tampered_summary_fails_the_replay(written, tmp_path):
    back = slambundle.load_slam_bundle(written[0])
    back.runs[1][1].summary['map']['f1'] = 0.999
    with pytest.raises(slambundle.SlamBundleError):
        slambundle.replay_check(back)


def test_external_runs_belong_to_recorded_drives(sb):
    ext = slambundle.ExternalRun('x', 'slam_toolbox', 'loop',
                                 sb.world.true_poses(), b'\0', {
                                     'width': 1, 'height': 1,
                                     'resolution': 0.1,
                                     'origin': [0.0, 0.0]}, {})
    with pytest.raises(slambundle.SlamBundleError, match='recorded'):
        slambundle.SlamBundle(sb.provenance, sb.lab_map, sb.world, sb.runs,
                              [ext]).validate()


def test_a_recorded_world_round_trips_with_an_external_run(tmp_path):
    """A recorded world is taken as recorded; externals are re-scored."""
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=ROUTE, seed=4,
                  noise=map_teaching.noise())
    w = mapworld.from_sketch(m, sc)
    w.source, w.scenario = 'recorded', None
    w.recorded = {'note': 'a Sketch world relabelled, for the test'}
    gt = w.true_poses()
    ext = slambundle.ExternalRun(
        'backend', 'slam_toolbox', 'loop',
        [(x + 0.01, y, th) for x, y, th in gt], bytes(m.width * m.height),
        {'width': m.width, 'height': m.height, 'resolution': m.resolution,
         'origin': list(m.origin)}, {'run': 'test'})
    prov = bundle.make_provenance(
        'recorded-run', rosbag={'sha256': '0' * 64, 'sim_time_start': 0.0,
                                'sim_time_end': 1.0}, **PROV)
    sb = slambundle.SlamBundle.compute(
        m, w, map_teaching.run_specs(snapshots=2, ids=('known', 'odometry')),
        prov, align=True, external=[ext])
    d = str(tmp_path / 'rec')
    slambundle.write_slam_bundle(sb, d)
    back = slambundle.load_slam_bundle(d)
    slambundle.replay_check(back)
    e = back.external[0]
    assert e.summary['ate_online']['rmse'] == pytest.approx(0.0, abs=1e-6)
    assert e.summary['map']['coverage'] == 1.0


GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'fixtures', 'slam_bundles')


def _files(d):
    return {n: open(os.path.join(d, n), 'rb').read()
            for n in sorted(os.listdir(d))}


@pytest.mark.parametrize('name', sorted(golden_slam_bundles.GOLDEN))
def test_golden_map_bundles_are_byte_identical_to_the_writer(name,
                                                             tmp_path):
    b, compression = golden_slam_bundles.make(name)
    slambundle.write_slam_bundle(b, str(tmp_path / name), compression)
    committed = os.path.join(GOLDEN_DIR, name)
    assert os.path.isdir(committed), f'missing golden fixture {committed}'
    assert _files(str(tmp_path / name)) == _files(committed)


@pytest.mark.parametrize('name', sorted(golden_slam_bundles.GOLDEN))
def test_golden_map_bundles_load_and_replay(name):
    slambundle.replay_check(slambundle.load_slam_bundle(
        os.path.join(GOLDEN_DIR, name)))


def test_the_doc_matches_the_implementation():
    """docs/labs/SLAM_FORMAT.md names every column, array and key there is."""
    doc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                            '..', 'docs', 'labs', 'SLAM_FORMAT.md')).read()
    from coco_lab import ekfslam, fastslam, posegraph, slam
    for name in (slambundle.SCHEMA, slam.SCHEMA, *slam.ALGORITHMS,
                 *slam.COMMON_COLUMNS, *ekfslam.COLUMNS, *fastslam.COLUMNS,
                 *posegraph.COLUMNS, *slambundle.WORLD_COLUMNS):
        assert f'`{name}`' in doc or name in doc, name
    b = slambundle.load_slam_bundle(os.path.join(GOLDEN_DIR,
                                                 'recorded_small_gz'))
    s = slambundle.load_slam_bundle(os.path.join(GOLDEN_DIR, 'loop_small'))
    for sb in (b, s):
        for key in sb.manifest():
            assert f'`{key}`' in doc, key
        for _, tr in sb.runs:
            for name in tr.arrays:
                assert f'`{name}`' in doc, name
    assert f'`{slambundle.VERSION}`' in doc or \
        f'"{slambundle.VERSION}"' in doc


def test_the_golden_set_covers_what_the_decoder_needs():
    loaded = {n: slambundle.load_slam_bundle(os.path.join(GOLDEN_DIR, n))
              for n in golden_slam_bundles.GOLDEN}
    algs = {tr.algorithm for b in loaded.values() for _, tr in b.runs}
    assert algs == {'known', 'odometry', 'ekf_slam', 'fastslam',
                    'pose_graph'}
    sources = {b.world.source for b in loaded.values()}
    assert sources == {'sketch', 'recorded'}
    assert any(b.external for b in loaded.values())
    comps = {json.load(open(os.path.join(GOLDEN_DIR, n, 'manifest.json')))
             ['encoding']['compression'] for n in loaded}
    assert comps == {'none', 'gzip'}
