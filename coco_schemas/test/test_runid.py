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

"""run_id: same inputs, same id; the committed vectors pin the method."""

import json
import os

from coco_schemas.runid import run_id, spec_sha256
from conftest import PKG
import pytest

VECTORS = os.path.join(PKG, 'test', 'vectors', 'run_id.json')


def vectors():
    with open(VECTORS) as f:
        return json.load(f)['vectors']


@pytest.mark.parametrize('v', vectors(), ids=lambda v: v['note'])
def test_committed_vectors(v):
    spec = v['spec_utf8'].encode('utf-8')
    assert spec_sha256(spec) == v['spec_sha256']
    assert run_id(spec, int(v['seed']), v['engines']) == v['run_id']


def test_engine_order_does_not_matter_but_every_input_does():
    a = run_id(b'{}', 1, [('coco_lab', '1'), ('pyodide', '314.0.7')])
    assert a == run_id(b'{}', 1, [('pyodide', '314.0.7'), ('coco_lab', '1')])
    assert a != run_id(b'{} ', 1, [('coco_lab', '1'), ('pyodide', '314.0.7')])
    assert a != run_id(b'{}', 2, [('coco_lab', '1'), ('pyodide', '314.0.7')])
    assert a != run_id(b'{}', 1, [('coco_lab', '2'), ('pyodide', '314.0.7')])


@pytest.mark.parametrize('seed', [-1, 2 ** 64, 1.0, '1', True])
def test_bad_seeds_are_refused(seed):
    with pytest.raises(ValueError):
        run_id(b'', seed, [])


def test_an_engine_named_twice_is_refused():
    with pytest.raises(ValueError):
        run_id(b'', 0, [('a', '1'), ('a', '2')])
