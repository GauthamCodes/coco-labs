"""R3.5: tools/r3/gap.py on synthetic MODEL and STACK runs (no Gazebo, no baselines needed)."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location('r3_gap', REPO / 'tools/r3/gap.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['r3_gap'] = mod
    spec.loader.exec_module(mod)
    return mod


G = _load()


def write_model(bench, suite, family, rows):
    d = bench / suite / family / 'public'
    d.mkdir(parents=True)
    (d / 'runs.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))


def write_stack(runs, name, rows, done=True):
    d = runs / name
    d.mkdir(parents=True)
    (d / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    if done:
        (d / 'DONE').write_text('')


def m(alg, sid, ok, **metrics):
    return {'algorithm': alg, 'scenario': sid, 'success': ok, 'metrics': metrics}


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    bench, runs = tmp_path / 'bench', tmp_path / 'runs'
    bench.mkdir()
    runs.mkdir()
    monkeypatch.setattr(G, 'BENCH', bench)
    return bench, runs


def test_majority_needs_more_than_half():
    assert G.majority([True, True, False])
    assert not G.majority([True, False, False])
    assert not G.majority([True, False])   # a tie is not a success
    assert not G.majority([])


def test_pair_stats_counts_shares_and_ratio():
    items = [('a', True, [True, True, False], 10.0, [11.0, 12.0, None]),   # both; ratio 11.5/10
             ('b', True, [False, False, True], 10.0, [None, None, 9.0]),   # model only
             ('c', False, [True, True, True], None, [5.0, 5.0, 5.0]),      # stack only
             ('d', False, [False], None, [None])]                          # neither
    s = G.pair_stats(items)
    assert s['confusion'] == {'both': 1, 'model_only': 1, 'stack_only': 1, 'neither': 1}
    assert s['n'] == 4 and s['agreement'] == 0.5
    assert s['model_optimistic'] == 0.25 and s['model_pessimistic'] == 0.25
    assert s['ratio_median'] == 1.15 and s['ratio_n'] == 1


def test_pair_stats_empty():
    s = G.pair_stats([])
    assert s['n'] == 0 and s['agreement'] is None and s['ratio_median'] is None


def test_planning_votes_across_repeats_and_skips_unpaired(dirs):
    bench, runs = dirs
    write_model(bench, 'depot-nav-100', 'planning',
                [m('astar', 's001', True, path_length_m=10.0),
                 m('astar', 's002', True, path_length_m=20.0)])
    srv = 'user_compute_path_to_pose'
    for k, ok2 in ((1, True), (2, False), (3, False)):
        write_stack(runs, f'depot-nav-100_plan_rep{k}', [
            {'id': 's001', 'server': srv, 'status': 'SUCCEEDED', 'length_m': 10.0 + k},
            {'id': 's002', 'server': srv, 'status': 'SUCCEEDED' if ok2 else 'STATUS_6',
             'length_m': 21.0 if ok2 else None},
            {'id': 's999', 'server': srv, 'status': 'SUCCEEDED', 'length_m': 1.0}])   # no model run
    out = G.planning(runs, 'depot-nav-100')
    p = out[srv]
    assert p['n'] == 2 and p['model'] == 'astar'
    assert p['confusion'] == {'both': 1, 'model_only': 1, 'stack_only': 0, 'neither': 0}
    assert p['ratio_median'] == 1.2   # median(11, 12, 13) / 10
    assert set(out) == {srv}          # no other server had rows


def test_unfinished_and_void_sessions_are_ignored(dirs):
    bench, runs = dirs
    write_model(bench, 'depot-nav-100', 'planning', [m('astar', 's001', True, path_length_m=10.0)])
    row = {'id': 's001', 'server': 'compute_path_to_pose', 'status': 'STATUS_6', 'length_m': None}
    write_stack(runs, 'depot-nav-100_plan_rep1', [dict(row, status='SUCCEEDED', length_m=10.0)])
    write_stack(runs, 'depot-nav-100_plan_rep1_void1', [row], done=False)
    write_stack(runs, 'depot-nav-100_plan_rep2', [row], done=False)
    p = G.planning(runs, 'depot-nav-100')['compute_path_to_pose']
    assert p['confusion']['both'] == 1 and p['ratio_median'] == 1.0


def test_snapped_and_planner_id_servers_pair_with_their_model_counterparts(dirs):
    bench, runs = dirs
    write_model(bench, 'depot-long-50', 'planning',
                [m('astar', 'l001', True, path_length_m=40.0),
                 m('dijkstra', 'l001', True, path_length_m=40.0)])
    write_stack(runs, 'depot-long-50_plan_rep1', [
        {'id': 'l001', 'server': 'compute_path_to_pose@NavFn', 'status': 'STATUS_6'},
        {'id': 'l001', 'server': 'compute_path_to_pose@NavFn+snapped', 'status': 'SUCCEEDED',
         'length_m': 44.0}])
    out = G.planning(runs, 'depot-long-50')
    assert out['compute_path_to_pose@NavFn']['model'] == 'dijkstra'
    assert out['compute_path_to_pose@NavFn']['confusion']['model_only'] == 1
    assert out['compute_path_to_pose@NavFn+snapped']['ratio_median'] == 1.1


def test_control_pairs_and_the_noyield_half(dirs):
    bench, runs = dirs
    write_model(bench, 'ctrl-dynamic-30', 'control',
                [m('rpp', 'd001_yield', True, time_s=50.0),
                 m('rpp', 'd001_no_yield', False, time_s=60.0),
                 m('dwa', 'd001_yield', False, time_s=300.0)])
    write_stack(runs, 'ctrl-dynamic-30_rpp_rep1', [{'id': 'd001_yield', 'status': 'SUCCEEDED', 'sim_s': 55.0}])
    write_stack(runs, 'ctrl-dynamic-30_dwb_rep1', [{'id': 'd001_yield', 'status': 'SUCCEEDED', 'sim_s': 70.0}])
    write_stack(runs, 'ctrl-dynamic-30-noyield_rpp_rep1',
                [{'id': 'd001_no_yield', 'status': 'SUCCEEDED', 'sim_s': 65.0}])
    yield_ = G.control(runs, 'ctrl-dynamic-30')
    assert set(yield_) == {'rpp', 'dwb'}            # the noyield sessions are not read here
    assert yield_['rpp']['ratio_median'] == 1.1 and yield_['rpp']['n'] == 1
    assert yield_['dwb']['model'] == 'dwa' and yield_['dwb']['confusion']['stack_only'] == 1
    noy = G.control(runs, 'ctrl-dynamic-30', '-noyield')
    assert set(noy) == {'rpp'}
    assert noy['rpp']['confusion'] == {'both': 0, 'model_only': 0, 'stack_only': 1, 'neither': 0}


def test_main_writes_the_document(dirs, tmp_path):
    bench, runs = dirs
    write_model(bench, 'ctrl-corners-30', 'control', [m('mppi', 't001', True, time_s=40.0)])
    write_stack(runs, 'ctrl-corners-30_mppi_rep1', [{'id': 't001', 'status': 'SUCCEEDED', 'sim_s': 48.0}])
    out = tmp_path / 'gap.json'
    sys_argv = sys.argv
    sys.argv = ['gap.py', str(runs), str(out)]
    try:
        assert G.main() == 0
    finally:
        sys.argv = sys_argv
    doc = json.loads(out.read_text())
    assert doc['control']['ctrl-corners-30']['mppi']['ratio_median'] == 1.2
    assert doc['planning'] == {}
