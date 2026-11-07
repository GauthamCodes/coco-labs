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


def test_scope_allows_only_the_writers_result_for_a_submitted_entry():
    sub = [f'leaderboard/submissions/depot-nav-100/theta_star/{f}'
           for f in ('algorithm.py', 'meta.yaml', 'summary.json')]
    res = 'leaderboard/results/depot-nav-100/theta_star/result.json'
    assert W.in_scope(sub) == (True, [])
    assert W.in_scope(sub + [res]) == (True, [('depot-nav-100', 'theta_star')])
    # a result for an entry the PR does not submit, or any other file: out of scope
    assert not W.in_scope(sub + ['leaderboard/results/depot-nav-100/astar/result.json'])[0]
    assert not W.in_scope(sub + ['leaderboard/index.json'])[0]
    assert not W.in_scope(sub + ['leaderboard/results/depot-nav-100/theta_star/report.md'])[0]
    assert not W.in_scope([res])[0]   # a result alone is no submission


def test_stable_ignores_the_machine_and_times_only():
    a = entry(host={'cpu': 'A'})
    b = entry(host={'cpu': 'B'})
    a['public']['score']['compute_ms'] = {'n': 1, 'median': 5.0}
    assert W.stable(a) == W.stable(b)
    b['held_out']['score']['successes'] = 19
    assert W.stable(a) != W.stable(b)


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


def _well_formed(d):
    return (sorted(p.name for p in d.iterdir()) == ['algorithm.py', 'meta.yaml', 'summary.json']
            and L.read_meta(d)['licence'] in ('MIT', 'Apache-2.0'))


def test_every_committed_submission_is_well_formed(tmp_path):
    # submissions arrive by pull request (Gautham's Theta* is PR #31): whatever is committed under
    # leaderboard/submissions/<suite>/<name>/ must be exactly the three files. Passes with none
    # committed, and never vacuously: the rule itself is checked on a made-up submission (the Lab
    # workflow allows no skips, so this is not a skip)
    for d in sorted((REPO / 'leaderboard' / 'submissions').glob('*/*/')):
        assert _well_formed(d), d
    d = tmp_path / 'depot-nav-100' / 'mine'
    d.mkdir(parents=True)
    for f in ('algorithm.py', 'summary.json'):
        (d / f).write_text('')
    (d / 'meta.yaml').write_text('author: A\ndisplay_name: X\ndescription: d\nlicence: MIT\n')
    assert _well_formed(d)
    (d / 'extra.txt').write_text('')
    assert not _well_formed(d)


def test_the_index_is_generated_from_every_verified_result(tmp_path):
    # R3 Part A: no committed copy (a submission's verified result made it stale); every build
    # generates it (build_catalog.py), so it must be deterministic and complete
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    L.index(a)
    L.index(b)
    assert a.read_text() == b.read_text()
    assert not (REPO / 'leaderboard' / 'index.json').exists()
    listed = {(r['entry']['suite'], r['entry']['name'])
              for rows in json.loads(a.read_text())['boards'].values() for r in rows}
    for p in (REPO / 'leaderboard' / 'results').glob('*/*/result.json'):
        r = json.loads(p.read_text())
        assert ((r['entry']['suite'], r['entry']['name']) in listed) == bool(r['verified']), p
