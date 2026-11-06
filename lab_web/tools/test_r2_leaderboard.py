# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""R2.6: the leaderboard's verifier and trusted writer (tools/r2/), without running a suite."""
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'tools' / 'r2' / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


W = _load('leaderboard_writer')
L = _load('leaderboard')


def entry(**over):
    r = {'schema': W.SCHEMA, 'verified': True, 'problems': [],
         'entry': {'suite': 'depot-nav-100', 'name': 'theta_star', 'display_name': 'Theta*',
                   'author': 'A', 'description': 'd', 'licence': 'MIT', 'family': 'planning',
                   'kind': 'submission', 'paper': None},
         'public': {'score': {'n': 100, 'successes': 100, 'path_ratio': {'n': 100, 'median': 0.98,
                                                                         'q1': 0.95, 'q3': 1.0}}},
         'held_out': {'score': {'n': 20, 'successes': 20}},
         'checks': {'deterministic': True, 'contract_problems': 0, 'claim_matches': True}}
    r.update(over)
    return r


def test_writer_accepts_a_verifier_result():
    assert W.validate(entry())['verified']


@pytest.mark.parametrize('bad', [
    {'schema': 'other'}, {'verified': 'yes'}, {'problems': ['x'] * 60},
    {'entry': {'suite': 'depot-nav-100', 'name': '../../etc', 'display_name': 'x', 'author': 'a',
               'description': 'd', 'licence': 'MIT', 'family': 'planning', 'kind': 'submission'}},
    {'entry': {'suite': 'depot-nav-100', 'name': 'ok_name', 'display_name': 'x', 'author': 'a',
               'description': 'd', 'licence': 'GPL', 'family': 'planning', 'kind': 'submission'}},
    {'public': {'score': {'n': 100, 'successes': 101}}},
    {'public': {'score': {'n': 100, 'successes': 1, 'path_ratio': {'median': float('nan')}}}},
    {'checks': {'deterministic': 'true'}},
])
def test_writer_refuses_anything_else(bad):
    with pytest.raises(W.Invalid):
        W.validate(entry(**bad))


def test_comment_is_regenerated_and_inert():
    r = entry()
    r['entry']['display_name'] = '@everyone [click](https://evil.example) <img src=x>'
    text = W.comment([('x', r)], True, 'success')
    assert 'VERIFIED' in text and '@everyone' not in text and '](https' not in text
    assert '<img' not in text
    assert 'NOT VERIFIED' in W.comment([('x', r)], False, 'success')
    assert 'NOT VERIFIED' in W.comment([('x', r)], True, 'failure')


def test_compare_ignores_only_the_machine(tmp_path):
    a, b = entry(host={'cpu': 'A'}), entry(host={'cpu': 'B'})
    (tmp_path / 'a.json').write_text(json.dumps(a))
    (tmp_path / 'b.json').write_text(json.dumps(b))
    assert W.compare(tmp_path / 'a.json', tmp_path / 'b.json') == 0
    b['public']['score']['successes'] = 99
    (tmp_path / 'b.json').write_text(json.dumps(b))
    assert W.compare(tmp_path / 'a.json', tmp_path / 'b.json') == 1


def test_held_out_seed_is_fixed_and_53_bit():
    s = L.held_out_seed('depot-nav-100', 'a' * 40)
    assert s == L.held_out_seed('depot-nav-100', 'a' * 40) and 0 <= s < 2 ** 53
    assert s != L.held_out_seed('depot-nav-100', 'b' * 40)


def test_meta_rules(tmp_path):
    d = tmp_path / 'depot-nav-100' / 'x1'
    d.mkdir(parents=True)
    (d / 'meta.yaml').write_text('author: A\ndisplay_name: X\ndescription: d\nlicence: GPL-3.0\n')
    with pytest.raises(L.SubmissionError):
        L.read_meta(d)
    (d / 'meta.yaml').write_text('author: A\ndisplay_name: X\ndescription: d\nlicence: MIT\n'
                                 'paper: http://insecure.example\n')
    with pytest.raises(L.SubmissionError):
        L.read_meta(d)
    (d / 'meta.yaml').write_text('author: A\ndisplay_name: X\ndescription: d\nlicence: MIT\n')
    assert L.read_meta(d)['licence'] == 'MIT'


def test_every_committed_submission_is_well_formed():
    # submissions arrive by pull request (Gautham's Theta* is PR #31, not on this branch): whatever is
    # committed under leaderboard/submissions/<suite>/<name>/ must be exactly the three files
    found = sorted((REPO / 'leaderboard' / 'submissions').glob('*/*/'))
    if not found:
        pytest.skip('no submission committed yet (PR #31 brings the first)')
    for d in found:
        assert sorted(p.name for p in d.iterdir()) == ['algorithm.py', 'meta.yaml', 'summary.json'], d
        assert L.read_meta(d)['licence'] in ('MIT', 'Apache-2.0'), d


def test_the_committed_index_is_current(tmp_path):
    out = tmp_path / 'index.json'
    L.index(out)
    assert out.read_text() == (REPO / 'leaderboard' / 'index.json').read_text()
