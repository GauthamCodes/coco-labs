"""R3.3 · ADR 0014: the secret held-out scheme's trusted side (tools/r3/heldout.py, the writer)."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


H = _load('r3_heldout', 'tools/r3/heldout.py')
W = _load('r3_writer', 'tools/r2/leaderboard_writer.py')
SECRET = '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff'


def test_the_seed_needs_the_secret_and_changes_per_head():
    s = H.seed_of(SECRET, 'depot-nav-100', 'a' * 40)
    assert s == H.seed_of(SECRET, 'depot-nav-100', 'a' * 40) and 0 <= s < 2 ** 53
    assert s != H.seed_of(SECRET, 'depot-nav-100', 'b' * 40)
    assert s != H.seed_of(SECRET, 'depot-narrow-30', 'a' * 40)
    assert s != H.seed_of('ff' + SECRET[2:], 'depot-nav-100', 'a' * 40)
    with pytest.raises(SystemExit):
        H.seed_of('00ff', 'depot-nav-100', 'a' * 40)   # too short to be a secret


def test_generate_writes_scenarios_only():
    doc = H.generate('ctrl-corners-30', 'c' * 40, SECRET)
    assert doc['n'] == 10 and doc['digest'] == H.scenarios_digest(doc['scenarios'])
    assert all(set(s) <= set(H.KEEP) for s in doc['scenarios'])
    assert SECRET not in json.dumps(doc)


def runs(fam, rows):
    keys = H.HEADLINE[fam]
    return {'family': fam, 'runs': [{'status': 'found' if ok else 'no_path', 'success': ok,
                                     'metrics': dict(zip(keys, v))} for ok, v in rows]}


def test_aggregate_rounds_and_says_nothing_per_scenario():
    a = H.aggregate(runs('planning', [(True, (1.0123456, 0.25)), (True, (1.0456789, 0.2)),
                                      (False, (None, None))]))
    assert a == {'family': 'planning', 'n': 3, 'successes': 2, 'wilson95': [0.208, 0.939],
                 'path_ratio_median': 1.03, 'min_clearance_m_median': 0.225}
    assert set(a) <= W.AGG_KEYS


@pytest.mark.parametrize('bad', [
    {'family': 'planning', 'runs': []},
    {'family': 'x', 'runs': [{'status': 'found', 'success': True, 'metrics': {}}]},
    {'family': 'planning', 'runs': [{'status': 'found', 'success': 'yes', 'metrics': {}}]},
    {'family': 'planning', 'runs': [{'status': 's' * 41, 'success': True, 'metrics': {}}]},
    {'family': 'planning', 'runs': [{'status': 'found', 'success': True,
                                     'metrics': {'path_ratio': float('nan')}}]},
    {'family': 'planning', 'runs': [{'status': 'found', 'success': True,
                                     'metrics': {'path_ratio': 'leak: 12.3,4.5'}}]},
])
def test_aggregate_refuses_anything_else(bad):
    with pytest.raises(H.Invalid):
        H.aggregate(bad)


def test_the_writer_reads_aggregates_as_data(tmp_path):
    good = H.aggregate(runs('control', [(True, (40.0, 0.2))]))
    (tmp_path / 'agg' / 'ctrl-corners-30').mkdir(parents=True)
    (tmp_path / 'agg' / 'ctrl-corners-30' / 'mine.json').write_text(json.dumps(good))
    assert W.secret_heldout(str(tmp_path), 'ctrl-corners-30', 'mine') == good
    assert W.secret_heldout(str(tmp_path), 'ctrl-corners-30', 'other') is None
    (tmp_path / 'agg' / 'ctrl-corners-30' / 'mine.json').write_text(
        json.dumps(dict(good, scenarios=[[1, 2]])))
    assert W.secret_heldout(str(tmp_path), 'ctrl-corners-30', 'mine') is None
    (tmp_path / 'heldout').mkdir()
    (tmp_path / 'heldout' / 'NONE').write_text('no secret configured')
    assert W.secret_heldout(str(tmp_path), 'ctrl-corners-30', 'mine') == 'none'


def test_a_fresh_secret_held_out_is_no_reason_to_recommit():
    a = {'schema': W.SCHEMA, 'verified': True, 'held_out_secret': {'n': 10, 'head': 'a' * 40}}
    b = dict(a, held_out_secret={'n': 10, 'head': 'b' * 40})
    assert W.stable(a) == W.stable(b)
