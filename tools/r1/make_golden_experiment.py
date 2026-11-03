#!/usr/bin/env python3
"""
R1.1: write coco_lab/test/fixtures/r1/golden_experiment.json (run once; never edited).

One small experiment per family, run natively; the fixture keeps each spec, its id,
every run's chain and the experiment digest. ``test_experiments.py`` re-runs them and
the browser parity check (lab_web/tools/r1/parity.mjs) runs the same specs in Pyodide.

    python tools/r1/make_golden_experiment.py [--check]
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import experiments as ex  # noqa: E402

OUT = REPO / 'coco_lab' / 'test' / 'fixtures' / 'r1' / 'golden_experiment.json'
SPECS = {
    'planning': {
        'schema': ex.SCHEMA, 'title': 'Golden: planners on the Proving Ground, an inflation sweep',
        'world': 'coco_arena_v1', 'family': 'planning', 'seed': 1,
        'algorithms': [{'name': 'astar'}, {'name': 'dijkstra'}, {'name': 'dstar_lite'},
                       {'name': 'weighted_astar', 'params': {'heuristic_weight': 3.0}}],
        'scenarios': {'kind': 'sampled', 'n': 4, 'seed': 1, 'min_separation_m': 3.0},
        'sweep': {'params': [{'name': 'inflation_radius', 'values': [0.4, 0.6]}]}},
    'control': {
        'schema': ex.SCHEMA, 'title': 'Golden: controllers on the Proving Ground',
        'world': 'coco_arena_v1', 'family': 'control', 'seed': 1,
        'algorithms': [{'name': 'builtin'}, {'name': 'rpp', 'params': {'rpp.lookahead_dist': 0.8}},
                       {'name': 'mppi', 'params': {'mppi.batch_size': 32}}],
        'scenarios': {'kind': 'sampled', 'n': 2, 'seed': 5, 'min_separation_m': 2.0},
        'limits': {'max_ticks': 700}},
    'localisation': {
        'schema': ex.SCHEMA, 'title': 'Golden: EKF and a small MCL, with a kidnap',
        'world': 'coco_arena_v1', 'family': 'localisation', 'seed': 1,
        'algorithms': [{'name': 'ekf'},
                       {'name': 'mcl', 'params': {'mcl.particles': 30, 'mcl.beams': 8}}],
        'scenarios': {'kind': 'sampled', 'n': 1, 'seed': 6, 'min_separation_m': 3.0},
        'limits': {'max_ticks': 200}, 'options': {'kidnap_at_s': 5}},
    'fulltask': {
        'schema': ex.SCHEMA, 'title': 'Golden: Fetch by colour, red, driven by A*',
        'family': 'fulltask', 'seed': 1, 'algorithms': [{'name': 'astar'}],
        'scenarios': {'kind': 'rounds', 'game': 'fetch_colour', 'colours': ['red']}},
}


def build():
    cases = []
    for name, spec in SPECS.items():
        p = ex.plan(spec)
        rs = ex.run_all(p)
        cases.append({'name': name, 'spec': p['spec'], 'id': p['id'],
                      'statuses': [r['status'] for r in rs],
                      'chains': [r['chain'] for r in rs], 'digest': ex.digest(rs)})
        print(name, p['id'], len(rs), 'runs', ex.digest(rs)[:16], [r['status'] for r in rs])
    return {'about': 'R1.1 golden experiment (coco.experiment.v1, hash v3): never edited; '
                     'made by tools/r1/make_golden_experiment.py', 'cases': cases}


if __name__ == '__main__':
    gold = build()
    if '--check' in sys.argv:
        old = json.loads(OUT.read_text())
        same = old['cases'] == gold['cases']
        print('golden unchanged' if same else 'GOLDEN DIFFERS')
        sys.exit(0 if same else 1)
    if OUT.exists():
        sys.exit(f'{OUT} exists: the golden experiment is never rewritten (use --check)')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(gold, indent=1, sort_keys=True) + '\n')
    print('wrote', OUT)
