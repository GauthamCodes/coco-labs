# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R1.2: the experiments both hosts run (CPython and Pyodide; lab_web/tools/r1/parity.mjs).

Globals in: ``golden_json`` (coco_lab/test/fixtures/r1/golden_experiment.json) and
``worlds_json`` ({world id: World Spec text}). Global out: ``result``, JSON: per golden
case, the plan id, every run's (index, status, chain, counts), the digest, and the
exported results.csv and summary.json with the wall-clock column and statistics
removed (``compute_ms``: the one device-dependent metric).
"""
import json

from coco_lab import experiments as ex


def _no_timing_csv(text):
    rows = [r.split(',') for r in text.splitlines()]
    k = rows[0].index('compute_ms')
    return '\n'.join(','.join(c for j, c in enumerate(r) if j != k) for r in rows)


def _no_timing_summary(s):
    for g in s['groups']:
        g['metrics'].pop('compute_ms', None)
    for row in s['paired']:
        row['metrics'].pop('compute_ms', None)
    return s


for wid, text in json.loads(worlds_json).items():  # noqa: F821 -- a global set by the host
    ex.register_world(wid, json.loads(text))
_out = {}
for case in json.loads(golden_json)['cases']:  # noqa: F821
    p = ex.plan(case['spec'])
    rs = ex.run_all(p)
    files = ex.export(p, rs, {'runner': 'parity'})
    _out[case['name']] = {
        'id': p['id'], 'golden_id': case['id'], 'digest': ex.digest(rs),
        'golden_digest': case['digest'],
        'records': [[r['index'], r['status'], r['chain'], ex.counts(r)] for r in ex.plain(rs)],
        'csv': _no_timing_csv(files['results.csv'].decode()),
        'summary': _no_timing_summary(json.loads(files['summary.json'])),
    }
result = json.dumps(_out, sort_keys=True)
