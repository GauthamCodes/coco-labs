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
Lab 5's worker glue (``recompute.replan_lab``) and site build, under CPython.

The same glue file the browser runs. Every output is re-read with coco_lab's
``load_replan_bundle`` and REPLAYED, so what the page draws is an episode
coco_lab reproduces byte for byte; the learner's painted cells reach the
WORLD and never the robot's map; refusals are explained, never crashes.
And the site build: every Lab 5 bundle is coco_lab's and replays, every
cited test exists, every run 15 quotation is in RESULTS.md.
"""

import json
import os
import re
import sys

from coco_lab import movebundle as mb, replan
import common
import pytest

sys.path.insert(0, os.path.join(common.LAB_WEB, 'src', 'worker'))
_dont_write = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import recompute  # noqa: E402
sys.dont_write_bytecode = _dont_write

FIXTURE = os.path.join(common.REPO, 'coco_lab', 'test', 'fixtures',
                       'move_bundles', 'replan_small')


def files():
    with open(os.path.join(FIXTURE, 'manifest.json'), 'rb') as f:
        m = f.read()
    with open(os.path.join(FIXTURE, 'arrays.bin'), 'rb') as f:
        a = f.read()
    return m, 'arrays.bin', a


def run(tmp_path, **spec):
    m, name, a = files()
    body = {'seed': None, 'sense_radius': 1.5, 'painted': []}
    body.update(spec)
    out = recompute.replan_lab(json.dumps(body), m, name, a)
    b = out['bundles'][0]
    d = tmp_path / 'out'
    d.mkdir(exist_ok=True)
    (d / 'manifest.json').write_bytes(b['manifest'])
    (d / b['arrays_name']).write_bytes(b['arrays_file'])
    manifest = mb.replay_replan(str(d))
    assert manifest['content_hash'] == b['content_hash']
    return out, manifest, mb.load_replan_bundle(str(d))[1]


def test_the_glue_returns_an_episode_coco_lab_replays(tmp_path):
    out, m, _ = run(tmp_path)
    assert m['provenance']['tool'] == 'lab_web/pyodide'
    assert m['provenance']['source_kind'] == 'sketch'
    assert m['summary']['costs_agree'] is True
    assert out['timings']['runs'] == len(m['rounds'])


def test_the_same_world_gives_the_fixtures_episode(tmp_path):
    _, m, _ = run(tmp_path)
    fixture, _ = mb.load_replan_bundle(FIXTURE)
    assert m['summary'] == fixture['summary']
    assert m['rounds'] == fixture['rounds']


def test_painted_cells_change_the_world_and_never_the_map(tmp_path):
    _, m, world = run(tmp_path, painted=[[1, 1], [2, 3]])
    fixture_world = mb.load_replan_bundle(FIXTURE)[1]
    assert world.known == fixture_world.known
    w = world.width
    assert world.truth[1 * w + 1] and world.truth[2 * w + 3]


def test_a_seed_builds_coco_labs_sketch_world(tmp_path):
    _, m, world = run(tmp_path, seed=7, sense_radius=3.0)
    want = replan.sketch_world(7, sense_radius=3.0)
    assert world.truth == want.truth and world.known == want.known
    assert m['provenance']['seed'] == 7


@pytest.mark.parametrize('spec, match', [
    ({'sense_radius': 1.0}, 'sense_radius'),
    ({'seed': -1}, 'seed'),
    ({'painted': [[99, 0]]}, 'off the map'),
    ({'painted': [[0, 0]]}, 'start and the goal'),
    ({'painted': [[0, 0]] * 201}, '200'),
])
def test_bad_requests_are_refused_with_a_reason(spec, match):
    m, name, a = files()
    body = {'seed': None, 'sense_radius': 2.5, 'painted': []}
    body.update(spec)
    with pytest.raises(recompute.Refused, match=match):
        recompute.replan_lab(json.dumps(body), m, name, a)


# -- the site build ---------------------------------------------------------------

def _cited(src):
    text = json.dumps(src)
    return sorted(set(re.findall(r'([\w/]+\.py)::(test_\w+)', text)))


def test_every_lab5_cited_test_exists():
    import build_move
    cited = _cited([build_move.CLAIMS, build_move.CONTROLLERS,
                    build_move.replan_entries.__doc__ or ''])
    import inspect
    cited += _cited([inspect.getsource(build_move)])
    cited = sorted(set(cited))
    assert len(cited) >= 10, cited
    for path, name in cited:
        full = os.path.join(common.REPO, path)
        assert os.path.exists(full), path
        with open(full) as f:
            assert re.search(rf'^def {name}\(', f.read(), re.M), \
                f'{path}::{name}'


def test_the_run15_quotes_are_verbatim_in_results():
    import build_move
    with open(build_move.RESULTS_MD, encoding='utf-8') as f:
        text = f.read()
    for q in build_move.RUN15_QUOTES:
        assert q in text, q


def test_the_catalog_serves_lab5_validated_and_replayed(tmp_path):
    import build_move
    out = tmp_path / 'generated'
    block = build_move.move_block(str(out))
    sk = [e for e in block['replan']['bundles'] if e['kind'] == 'sketch']
    assert [e['id'] for e in sk] == [f'sketch_{s}' for s in build_move.SEEDS]
    for e in block['replan']['bundles']:
        m = mb.replay_replan(str(out / e['path']))
        assert m['content_hash'] == e['content_hash']
        assert e['summary']['costs_agree'] is True
    for e in block['drive']['bundles']:
        m = mb.replay_drive(str(out / e['path']))
        assert m['content_hash'] == e['content_hash']
    for c in block['claims'] + block['controllers']:
        assert c['cites'], c['id']
    assert {c['id'] for c in block['controllers']} == {'DWB', 'MPPI', 'RPP'}
