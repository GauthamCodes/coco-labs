#!/usr/bin/env python3
"""
R1.5: compute COCO-Bench v0 reference results natively and commit them.

For every suite and family it serves, every built-in algorithm at its default parameters
(localisation: MCL with 60 particles and 12 beams, the EKF with 12 beams -- the Compare
teaching profile, stated in the spec), run by `coco experiment run` (this module's CLI) into
docs/v2/r1/bench/<suite>/<family>/: results.csv, summary.json, spec.json, manifest.json,
runs.jsonl. Counts are device-independent; the manifest names the machine for compute_ms.

    python tools/r1/make_references.py [--workers N] [--only suite/family ...]
"""
import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import experiments as ex  # noqa: E402

OUT = REPO / 'docs' / 'v2' / 'r1' / 'bench'
ALGOS = {
    'planning': [{'name': n} for n in ex.ALGORITHMS['planning']],
    'control': [{'name': n} for n in ex.ALGORITHMS['control']],
    'localisation': [{'name': 'mcl', 'params': {'mcl.particles': 60, 'mcl.beams': 12}},
                     {'name': 'mcl_augmented', 'params': {'mcl.particles': 60, 'mcl.beams': 12}},
                     {'name': 'ekf', 'params': {'ekf.beams': 12}}],
    'fulltask': [{'name': n} for n in ex.ALGORITHMS['fulltask']],
}
RUNS = {'arena-nav-50': ['planning', 'control', 'localisation'], 'depot-nav-100': ['planning', 'control'],
        'depot-narrow-30': ['planning', 'control'], 'colour-fetch-4': ['fulltask']}


def spec_for(suite_id, family):
    st = ex.suite(suite_id)
    spec = {'schema': ex.SCHEMA, 'title': f'COCO-Bench v0 reference: {suite_id}, {family}', 'family': family,
            'seed': 1, 'algorithms': ALGOS[family], 'scenarios': {'kind': 'suite', 'id': suite_id}}
    if family != 'fulltask':
        spec['world'] = st['world']
    if family in ('control', 'localisation'):
        spec['limits'] = {'max_ticks': 3000}
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    for suite_id, families in RUNS.items():
        for family in families:
            key = f'{suite_id}/{family}'
            if a.only and key not in a.only:
                continue
            d = OUT / suite_id / family
            d.mkdir(parents=True, exist_ok=True)
            (d / 'spec.input.json').write_text(json.dumps(spec_for(suite_id, family), indent=1) + '\n')
            print('==', key, flush=True)
            rc = ex.main(['run', str(d / 'spec.input.json'), '--out', str(d), '--workers', str(a.workers)])
            (d / 'spec.input.json').unlink()
            if rc:
                sys.exit(rc)


if __name__ == '__main__':
    main()
