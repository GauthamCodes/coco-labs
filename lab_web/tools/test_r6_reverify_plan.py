# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""R6.A7: the leaderboard re-verify plan (tools/r2/reverify_plan.py): a matrix of only the entries that need it."""
import importlib.util
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]


def _load():
    sys.path[:0] = [str(REPO / 'tools' / 'r2'), str(REPO / 'coco_lab')]
    spec = importlib.util.spec_from_file_location('reverify_plan', REPO / 'tools' / 'r2' / 'reverify_plan.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_committed_entry_is_planned_and_all_selects_all(tmp_path):
    rp = _load()
    entries = sorted(REPO.glob('leaderboard/results/*/*/result.json'))
    p = rp.plan(force_all=True)
    assert p['total'] == len(entries) == p['count'] > 0
    assert all(r['reasons'] == ['all (requested)'] or r['reasons'][0] == 'all (requested)' for r in p['entries'])


def test_the_matrix_names_one_job_per_suite_and_entry(tmp_path):
    rp = _load()
    out = tmp_path / 'gho'
    rp.main(['--all', '--github-output', str(out)])
    lines = dict(x.split('=', 1) for x in out.read_text().splitlines())
    m = json.loads(lines['matrix'])
    assert int(lines['count']) == len(m['include'])
    keys = [(j['suite'], j['name']) for j in m['include']]
    assert len(keys) == len(set(keys))                       # one job per suite x entry
    assert all(set(j) == {'suite', 'name', 'kind', 'merge_base'} for j in m['include'])


def test_a_changed_version_or_input_is_the_reason_and_nothing_else_is():
    rp = _load()
    p = rp.plan()
    for r in p['entries']:
        assert r['reverify'] == bool(r['reasons'])
        for why in r['reasons']:
            assert why.startswith(('versions:', 'changed since', 'verified at')), why
