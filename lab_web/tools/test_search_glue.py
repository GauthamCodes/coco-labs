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
Lab 4's worker glue (``recompute.search_lab``), run under CPython.

The same file the browser runs. Every output is re-read with coco_lab's
``load_search_bundle`` and REPLAYED, so what the page draws is a bundle
coco_lab accepts and can reproduce; the learner's settings reach coco_lab
exactly as the glue's docstring says; every run shares one problem, one
placement and one seed; refusals are explained, never crashes.
"""

import dataclasses
import json
import os
import sys

from coco_lab import regionsearch as rs, searchbundle as sbm
import common
import pytest

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import recompute  # noqa: E402
sys.dont_write_bytecode = _dont_write

FIXTURES = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures',
                        'search_bundles')
BASE = {'prior': [1, 1, 1, 1], 'detection': 0.9, 'true_detection': 0.9,
        'truth': 0, 'order': [3, 2, 1, 0], 'seed': 0}


def files(name='arena_recorded_gz'):
    d = os.path.join(FIXTURES, name)
    arrays = [n for n in os.listdir(d) if n.startswith('arrays')][0]
    with open(os.path.join(d, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(d, arrays), 'rb') as f:
        a = f.read()
    return m, arrays, a


def run(tmp_path, **over):
    m, name, a = files()
    out = recompute.search_lab(json.dumps(dict(BASE, **over)), m, name, a)
    b = out['bundles'][0]
    d = tmp_path / 'out'
    d.mkdir(exist_ok=True)
    (d / 'manifest.json').write_bytes(b['manifest'])
    (d / b['arrays_name']).write_bytes(b['arrays_file'])
    sb = sbm.load_search_bundle(str(d))
    assert sb.manifest()['content_hash'] == b['content_hash']
    return out, sb


def test_the_glue_returns_a_bundle_coco_lab_loads_and_replays(tmp_path):
    out, sb = run(tmp_path)
    sbm.replay_check(sb)
    assert [r.id for r in sb.runs] == ['robot', 'mine', 'nearest', 'likely']
    assert sb.provenance['tool'] == 'lab_web/pyodide'
    assert out['timings']['runs'] == 4


def test_the_glue_is_exactly_coco_labs_computation(tmp_path):
    _, sb = run(tmp_path, prior=[3, 1, 1, 1], detection=0.8)
    base = sbm.load_search_bundle(os.path.join(FIXTURES,
                                               'arena_recorded_gz')).problem
    p = dataclasses.replace(base, detection=(0.8,) * 4,
                            prior=rs.normalise([3, 1, 1, 1]))
    robot = rs.run_search(p, 'expected_cost', 0, seed=0,
                          true_detection=[0.9] * 4)
    got = sb.runs[0].trace
    assert (got.kind, got.region, got.belief) == \
        (robot.kind, robot.region, robot.belief)
    assert got.summary == robot.summary


def test_every_run_shares_one_problem_placement_and_seed(tmp_path):
    _, sb = run(tmp_path)
    assert {r.trace.summary['truth'] for r in sb.runs} == {'bay_1'}
    assert {r.trace.header['seed'] for r in sb.runs} == {0}


def test_a_partial_order_is_a_search_that_stopped_short(tmp_path):
    _, sb = run(tmp_path, order=[2])          # only bay_3; truth bay_1
    mine = next(r for r in sb.runs if r.id == 'mine').trace
    assert mine.summary['status'] == 'exhausted'
    assert not rs.challenge_passed(mine)


def test_no_order_means_no_learner_run(tmp_path):
    _, sb = run(tmp_path, order=[])
    assert [r.id for r in sb.runs] == ['robot', 'nearest', 'likely']


def test_bad_settings_are_refused(tmp_path):
    for over, msg in (({'prior': [0, 0, 0, 0]}, 'prior'),
                      ({'prior': [1, 1]}, 'prior'),
                      ({'detection': 0.2}, 'detection'),
                      ({'truth': 7}, 'bays'),
                      ({'order': [1, 1]}, 'at most once')):
        with pytest.raises(recompute.Refused, match=msg):
            run(tmp_path, **over)
