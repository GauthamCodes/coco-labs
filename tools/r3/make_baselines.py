#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.2: COCO-Bench v1 browser-model baselines (MODEL) -- every built-in on every v1 suite, on the
public scenarios and on a held-out draw, committed with manifests.

    python tools/r3/make_baselines.py [--workers N] [--only SUITE/FAMILY ...] [--list]

Into docs/v2/r3/bench/<suite>/<family>/{public,held_out}/ (the export set of `coco experiment
run`: spec.json, runs.jsonl, results.csv, summary.json, manifest.json), then tiers.json per suite
and family: success (Wilson 95 %) and medians of the headline metrics per tier and algorithm.

- Profiles, as R1's references: built-ins at their defaults; localisation MCL with 60 particles
  and 12 beams, the EKF with 12 beams (Compare's teaching profile); max_ticks 3000 for control
  and localisation. loc-global-20 runs the MCL family only (an EKF cannot start without a pose).
- Held-out for the baselines: the suite's own generator from the public seed
  ``leaderboard.held_out_seed(suite, 'reference-v1')`` (a reference draw, not a secret; ADR 0014's
  secret sets are for submissions).
- task-fetch-10: its two experiments (Fetch Rush phone rounds; the colour rounds), public only.
Counts are device-independent; each manifest names the machine for compute_ms.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import bench_v1 as B  # noqa: E402
from coco_lab import exp_stats  # noqa: E402
from coco_lab import experiments as ex  # noqa: E402

OUT = REPO / 'docs' / 'v2' / 'r3' / 'bench'
LOC = {'mcl': {'mcl.particles': 60, 'mcl.beams': 12},
       'mcl_augmented': {'mcl.particles': 60, 'mcl.beams': 12}, 'ekf': {'ekf.beams': 12}}
HEADLINE = {'planning': ('path_length_m', 'expansions', 'min_clearance_m'),
            'control': ('time_s', 'min_clearance_m', 'contacts'),
            'localisation': ('final_err_xy_m', 'mean_err_xy_m', 'converged_s', 'recovery_s'),
            'fulltask': ('net_deliveries', 'time_to_complete_s', 'contacts')}


def _leaderboard():
    spec = importlib.util.spec_from_file_location('r2_leaderboard', REPO / 'tools/r2/leaderboard.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def algorithms(sid, family):
    allowed = B.SUITES.get(sid, {}).get('algorithms')
    names = [n for n in ex.ALGORITHMS[family] if not allowed or n in allowed]
    return [dict({'name': n}, **({'params': LOC[n]} if family == 'localisation' else {}))
            for n in names]


def jobs():
    out = []
    for sid, d in B.SUITES.items():
        for fam in d['families']:
            out.append((sid, fam))
    out.append((B.TASK_SUITE, 'fulltask'))
    return out


def spec(sid, family, which, held=None):
    title = f'COCO-Bench v1 baseline: {sid}, {family}, {which}'
    if sid == B.TASK_SUITE:
        raise ValueError('task suite: see task_specs')
    s = {'schema': ex.SCHEMA, 'title': title, 'family': family, 'seed': 1,
         'world': B.SUITES[sid]['world'], 'algorithms': algorithms(sid, family)}
    s['scenarios'] = ({'kind': 'suite', 'id': sid, 'version': 1} if which == 'public'
                      else {'kind': 'inline', 'scenarios': held})
    if family in ('control', 'localisation'):
        s['limits'] = {'max_ticks': 3000}
    return s


def task_specs():
    st = json.loads((ex.BENCHMARKS / f'{B.TASK_SUITE}.v1.json').read_text())
    return [(f'part{i + 1}', {'schema': ex.SCHEMA, 'family': 'fulltask', 'seed': 1,
                              'title': f'COCO-Bench v1 baseline: {B.TASK_SUITE}, part {i + 1}',
                              'algorithms': algorithms(B.TASK_SUITE, 'fulltask'),
                              'scenarios': e['scenarios']})
            for i, e in enumerate(st['experiments'])]


def held_out(sid, lb):
    keep = ('id', 'start', 'goal', 'seed', 'config', 'kidnap_at_s', 'kidnap')
    scen = B.generate(sid, seed=lb.held_out_seed(sid, 'reference-v1'), n=B.SUITES[sid]['heldout_n'])
    return [{k: s[k] for k in keep if k in s} for s in scen], scen


def run(spec_doc, d, workers):
    d.mkdir(parents=True, exist_ok=True)
    (d / 'spec.input.json').write_text(json.dumps(spec_doc, indent=1) + '\n')
    rc = ex.main(['run', str(d / 'spec.input.json'), '--out', str(d), '--workers', str(workers)])
    (d / 'spec.input.json').unlink()
    if rc:
        raise SystemExit(f'{d}: rc {rc}')


def tiers(d, family, tier_of):
    rows = [json.loads(line) for line in (d / 'runs.jsonl').read_text().splitlines()]
    out = {}
    for r in rows:
        t = tier_of.get(r['scenario'])
        if t is None:
            continue
        out.setdefault(r['algorithm'], {}).setdefault(t, []).append(r)
    res = {}
    for algo, by in out.items():
        res[algo] = {}
        for t in B.TIERS:
            rs = by.get(t, [])
            k = sum(1 for r in rs if r['success'])
            w = exp_stats.wilson(k, len(rs)) if rs else None
            e = {'n': len(rs), 'successes': k, 'wilson95': [w['low'], w['high']] if w else None}
            for m in HEADLINE[family]:
                vals = [r['metrics'].get(m) for r in rs if r['metrics'].get(m) is not None
                        and (r['success'] or family == 'localisation')]
                e[m + '_median'] = exp_stats.describe(vals)['median'] if vals else None
            res[algo][t] = e
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    lb = _leaderboard()
    for sid, fam in jobs():
        key = f'{sid}/{fam}'
        if a.list:
            print(key, [x['name'] for x in algorithms(sid, fam)])
            continue
        if a.only and key not in a.only:
            continue
        base = OUT / sid / fam
        if (base / 'DONE').exists():
            print('done already:', key, flush=True)
            continue
        print('==', key, flush=True)
        if sid == B.TASK_SUITE:
            for part, s in task_specs():
                run(s, base / part, a.workers)
            (base / 'DONE').write_text('')
            continue
        run(spec(sid, fam, 'public'), base / 'public', a.workers)
        held, full = held_out(sid, lb)
        run(spec(sid, fam, 'held_out', held), base / 'held_out', a.workers)
        suite = json.loads((ex.BENCHMARKS / f'{sid}.v1.json').read_text())
        tier_of = {s['id']: s['tier'] for s in suite['scenarios']}
        doc = {'about': 'R3.2 tools/r3/make_baselines.py: per tier (the suite file\'s tiers), '
                        'public scenarios', 'suite': sid, 'family': fam,
               'tiers': tiers(base / 'public', fam, tier_of),
               'held_out': {'seed': lb.held_out_seed(sid, 'reference-v1'), 'n': len(held),
                            'note': 'a reference draw from a public seed (not an ADR 0014 secret)'}}
        (base / 'tiers.json').write_text(json.dumps(ex.plain(doc), indent=1, sort_keys=True) + '\n')
        (base / 'DONE').write_text('')
    return 0


if __name__ == '__main__':
    sys.exit(main())
