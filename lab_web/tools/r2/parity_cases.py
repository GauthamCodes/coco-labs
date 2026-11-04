# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.4: every starter template run by both hosts (CPython and Pyodide; tools/r2/parity.mjs).

Globals in: ``templates_json`` ({file name: source}) and ``worlds_json`` ({world id: World
Spec text}). Global out: ``result``, JSON: per template, the plan id, every run's (index,
status, chain, counts, deterministic, validation report without its wall times) and the digest.
Each template runs on the first scenarios of a COCO-Bench v0 suite, beside one built-in.
"""
import json

from coco_lab import experiments as ex, exp_user

#: template -> (family, suite, scenarios, max ticks, the built-in beside it)
CASES = {
    'planner_astar.py': ('planning', 'arena-nav-50', 4, 3000, 'astar'),
    'planner_greedy.py': ('planning', 'arena-nav-50', 4, 3000, 'greedy'),
    'planner_empty.py': ('planning', 'arena-nav-50', 3, 3000, 'astar'),
    'teach_heuristic.py': ('planning', 'arena-nav-50', 3, 3000, 'dijkstra'),
    'controller_pure_pursuit.py': ('control', 'arena-nav-50', 2, 900, 'rpp'),
    'controller_empty.py': ('control', 'arena-nav-50', 2, 300, 'dwa'),
    'teach_tune_dwa.py': ('control', 'arena-nav-50', 1, 300, 'dwa'),
    'localiser_particle_filter.py': ('localisation', 'arena-nav-50', 1, 400, 'ekf'),
    'localiser_empty.py': ('localisation', 'arena-nav-50', 1, 400, 'ekf'),
}
_WALL = ('call_ms_max', 'call_ms_total', 'max_call_index')

for wid, text in json.loads(worlds_json).items():  # noqa: F821 -- a global set by the host
    ex.register_world(wid, json.loads(text))
_out = {}
for name, src in sorted(json.loads(templates_json).items()):  # noqa: F821
    family, suite, n, ticks, rival = CASES[name]
    sha = exp_user.register(src)
    st = ex.suite(suite)
    pairs = [{'id': s['id'], 'start': s['start'], 'goal': s['goal']} for s in st['scenarios'][:n]]
    spec = {'schema': ex.SCHEMA, 'family': family, 'world': st['world'], 'seed': 7,
            'algorithms': [{'name': 'user', 'id': name[:-3], 'code_sha256': sha},
                           {'name': rival}],
            'scenarios': {'kind': 'pairs', 'pairs': pairs, 'seed': 7},
            'limits': {'max_ticks': ticks}}
    p = ex.plan(spec)
    rs = ex.run_all(p)
    _out[name] = {
        'id': p['id'], 'digest': ex.digest(rs), 'code_sha256': sha,
        'runs': [{'index': r['index'], 'algorithm': r['algorithm'], 'status': r['status'],
                  'chain': r['chain'], 'counts': ex.counts(r),
                  'deterministic': r.get('deterministic'),
                  'report': {k: v for k, v in (r.get('report') or {}).items() if k not in _WALL}}
                 for r in rs]}
result = json.dumps(ex.plain(_out), sort_keys=True)
