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
Lab 5's site data (build_move), under CPython.

Every Lab 5 claim cites a test that exists, every run 15 quotation is in
RESULTS.md, and every bundle the catalog lists is validated and replayed.
These three were in test_move_glue.py until M2.10 retired the v1 lab views
and their worker glue; the site data still feeds the converters
(build_v2_runs.mjs) and the Learn missions.
"""

import json
import os
import re

from coco_lab import movebundle as mb
import common


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
