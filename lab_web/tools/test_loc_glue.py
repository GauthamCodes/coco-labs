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
Lab 2's worker glue (``recompute.localise``), run under CPython.

The same file the browser runs. Every output is re-read with coco_lab's
``load_loc_bundle`` and REPLAYED, so what the page draws is a bundle
coco_lab accepts and can reproduce; the learner's settings reach the
world and the filters exactly as the glue's docstring says; refusals are
explained, never crashes.
"""

import json
import os
import sys

from coco_lab import locbundle
import common
import pytest

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import recompute  # noqa: E402
sys.dont_write_bytecode = _dont_write

FIXTURE = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures',
                       'loc_bundles', 'kidnap_small_gz')
BASE = {'particles': 40, 'motion_noise': 1.0, 'sensor_sigma': 0.02,
        'injection': 'augmented', 'alpha_slow': 0.001, 'alpha_fast': 0.1,
        'inject_fraction': 0.05, 'init': 'tracking',
        'kidnap': {'t': 6.0, 'to': [9.0, 4.5, 3.14159]}, 'seed': 22,
        'filter_seed': 2}


@pytest.fixture(autouse=True)
def fresh_worker():
    """Each test starts with a worker that has validated nothing."""
    recompute._LOC_CACHE.clear()
    recompute._SMAPS.clear()
    yield


def files():
    with open(os.path.join(FIXTURE, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(FIXTURE, 'arrays.bin.gz'), 'rb') as f:
        a = f.read()
    return m, 'arrays.bin.gz', a


def run(tmp_path, **over):
    m, name, a = files()
    out = recompute.localise(json.dumps(dict(BASE, **over)), m, name, a)
    b = out['bundles'][0]
    d = tmp_path / 'out'
    d.mkdir(exist_ok=True)
    (d / 'manifest.json').write_bytes(b['manifest'])
    (d / b['arrays_name']).write_bytes(b['arrays_file'])
    lb = locbundle.load_loc_bundle(str(d))
    assert lb.manifest()['content_hash'] == b['content_hash']
    return out, lb


def test_the_glue_returns_a_bundle_coco_lab_loads_and_replays(tmp_path):
    out, lb = run(tmp_path)
    locbundle.replay_check(lb)
    assert [rid for rid, _ in lb.runs] == ['mcl', 'mcl_coco', 'ekf']
    assert lb.provenance['tool'] == 'lab_web/pyodide'
    assert lb.provenance['source_kind'] == 'sketch'
    assert out['timings']['runs'] == 3


def test_every_run_reads_one_world(tmp_path):
    _, lb = run(tmp_path)
    for _, tr in lb.runs:
        assert list(tr.columns['row']) == list(lb.world.updates)


def test_the_settings_reach_the_world_and_the_filters(tmp_path):
    _, lb = run(tmp_path, particles=70, motion_noise=2.0, sensor_sigma=0.3,
                seed=99, filter_seed=7)
    sc = lb.world.scenario
    assert sc.seed == 99
    assert sc.noise.odom_alphas == (0.04,) * 4
    assert sc.noise.range_sigma == 0.3
    mcl = dict(lb.runs)['mcl'].header['params']
    assert mcl['particles'] == 70 and mcl['seed'] == 7
    assert mcl['alphas'] == [0.04] * 4
    # the filters never assume less range noise than COCO's AMCL (0.2 m)
    assert mcl['sigma_hit'] == 0.3
    assert dict(lb.runs)['ekf'].header['params']['sigma_hit'] == 0.3
    assert dict(lb.runs)['mcl_coco'].header['params']['injection'] == 'none'


def test_injection_off_runs_two_filters_and_the_floor_holds(tmp_path):
    _, lb = run(tmp_path, injection='none', sensor_sigma=0.05)
    assert [rid for rid, _ in lb.runs] == ['mcl', 'ekf']
    assert dict(lb.runs)['mcl'].header['params']['sigma_hit'] == 0.2


def test_no_kidnap_means_no_kidnap(tmp_path):
    _, lb = run(tmp_path, kidnap=None)
    assert lb.world.kidnap_row is None and lb.world.scenario.kidnap is None


@pytest.mark.parametrize('over,msg', [
    ({'kidnap': {'t': 6.0, 'to': [0.05, 0.05, 0.0]}}, 'inside or against'),
    ({'particles': 5000}, 'particles must be'),
    ({'injection': 'sometimes'}, 'injection must be'),
    ({'init': 'anywhere'}, 'init must be'),
    ({'motion_noise': -1}, 'motion_noise must be'),
    ({'kidnap': {'t': 6.0}}, 'needs a place'),
])
def test_bad_requests_are_refused_with_a_reason(over, msg):
    m, name, a = files()
    with pytest.raises(recompute.Refused, match=msg):
        recompute.localise(json.dumps(dict(BASE, **over)), m, name, a)


def test_a_tampered_bundle_is_refused_before_anything_runs():
    m, name, a = files()
    bad = bytearray(a)
    bad[-20] ^= 0xFF
    with pytest.raises(Exception):
        recompute.localise(json.dumps(BASE), m, name, bytes(bad))
    assert not recompute._LOC_CACHE


def test_a_validated_bundle_is_reused_and_tampered_bytes_are_never_used():
    """
    Cached by its content hash, as Lab 1's glue caches: a copy claiming a
    hash this worker already validated is answered from the VALIDATED
    bundle, so the tampered bytes are never read.
    """
    m, name, a = files()
    first = recompute.localise(json.dumps(BASE), m, name, a)
    bad = bytearray(a)
    bad[-20] ^= 0xFF
    second = recompute.localise(json.dumps(BASE), m, name, bytes(bad))
    assert second['timings']['load_bundle_ms'] == 0.0
    assert second['bundles'][0]['content_hash'] == \
        first['bundles'][0]['content_hash']
