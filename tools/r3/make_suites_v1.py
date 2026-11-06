#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.1: write COCO-Bench v1 -- coco_lab/coco_lab/benchmarks/<id>.v1.json for every suite in
coco_lab.bench_v1.SUITES, plus task-fetch-10. Each is written once and frozen; ``--check``
confirms the committed files are what this generator produces (it is deterministic: hash
version 3), and that every carried-over suite's scenarios are its v0 scenarios exactly.

    python tools/r3/make_suites_v1.py [--check] [--only ID ...]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import bench_v1 as B  # noqa: E402
from coco_lab import experiments as ex  # noqa: E402

OUT = REPO / 'coco_lab' / 'coco_lab' / 'benchmarks'
LEVELS = REPO / 'coco_lab' / 'coco_lab' / 'levels'
STRIP = ('features', 'difficulty', 'tier')


def scen_sha(scenarios):
    return hashlib.sha256(ex.canonical(scenarios)).hexdigest()


def nav(sid):
    d = B.SUITES[sid]
    scen = B.generate(sid)
    if any(s['features'] is None for s in scen):
        raise SystemExit(f'{sid}: a scenario without a reference path')
    if d['generator']['kind'] == 'paired_rules':
        # tier the pairs, so both rules of one pair share its tier
        firsts = [s for s in scen if s['actor_rule'] == 'yield']
        tiers = B.assign_tiers(firsts, d['tier_features'])
        by_pair = {s['pair']: s for s in firsts}
        for s in scen:
            s['difficulty'], s['tier'] = by_pair[s['pair']]['difficulty'], by_pair[s['pair']]['tier']
        tiers['counts'] = {k: 2 * v for k, v in tiers['counts'].items()}
        tiers['method'] += '; over the pairs, both rules of a pair in its tier'
    else:
        tiers = B.assign_tiers(scen, d['tier_features'])
    fams = d['families']
    gen = dict(d['generator'], tool=B.TOOL, module='coco_lab.bench_v1')
    out = {'schema': B.SCHEMA, 'id': sid, 'version': 1, 'title': d['title'],
           'world': d['world'], 'world_sha256': ex.world_sha256(d['world']), 'families': fams,
           'metrics': {f: [m['id'] for m in ex.METRICS[f]] for f in fams},
           'generator': gen, 'tiers': tiers,
           'held_out': {'n': d['heldout_n'], 'scheme': 'ADR 0014 (secret salt, per head) in CI; '
                        'R2 public salt locally', 'generator': 'the same, another seed'},
           'datasheet': f'docs/bench/v1/{sid}.md'}
    if d.get('algorithms'):
        out['algorithms'] = d['algorithms']
    if gen['kind'] == 'carried':
        v0 = ex.suite(sid, 0)
        bare = [{k: v for k, v in s.items() if k not in STRIP} for s in scen]
        if bare != v0['scenarios']:
            raise SystemExit(f'{sid}: v1 scenarios differ from v0')
        out['from_v0'] = {'scenarios_sha256': scen_sha(v0['scenarios']),
                          'note': 'identical scenarios; v1 adds features and tiers only'}
    out['scenarios'] = scen
    return out


def task():
    fr = json.loads((LEVELS / 'coco_depot_v1.fetch_rush.r5.json').read_text())
    fc = json.loads((LEVELS / 'coco_depot_colours_v1.fetch_colour.r2.json').read_text())
    scen = []
    for seed in ex.FETCH_RUSH_SEEDS:
        r = fr['rounds']['phone'][str(seed)]
        scen.append({'id': f'fr_phone_{seed}', 'world': 'coco_depot_v1', 'game': 'fetch_rush',
                     'round': seed, 'mode': 'phone', 'rules': ex.FETCH_RUSH_RULES,
                     'features': {'route_m': round(sum(r['ghost_m']), 4),
                                  'orders': len(r['orders'])}})
    for c in ex.FETCH_COLOURS:
        r = fc['rounds'][c]
        scen.append({'id': f'colour_{c}', 'world': 'coco_depot_colours_v1',
                     'game': 'fetch_colour', 'colour': c, 'rules': ex.FETCH_COLOUR_RULES,
                     'features': {'route_m': round(sum(r['ghost_m']), 4),
                                  'orders': len(r['orders'])}})
    tiers = B.assign_tiers(scen, ['route_m', 'orders'])
    return {'schema': B.SCHEMA, 'id': B.TASK_SUITE, 'version': 1,
            'title': 'Full task: the six Fetch Rush phone rounds and the four colour rounds',
            'world': None, 'worlds': ['coco_depot_v1', 'coco_depot_colours_v1'],
            'world_sha256': {w: ex.world_sha256(w) for w in ('coco_depot_v1',
                                                                'coco_depot_colours_v1')},
            'families': ['fulltask'],
            'metrics': {'fulltask': [m['id'] for m in ex.METRICS['fulltask']]},
            'generator': {'kind': 'rounds', 'tool': B.TOOL,
                          'rule': 'the committed rounds only (R1): Fetch Rush rules '
                                  f'{ex.FETCH_RUSH_RULES} phone seeds 1-6, Fetch by colour rules '
                                  f'{ex.FETCH_COLOUR_RULES} (actors yield)',
                          'name': 'task-fetch-10: the prompt asked for 12; the committed rounds '
                                  'are 6 phone + 4 colour = 10, and new rounds are not invented'},
            'tiers': tiers,
            'held_out': {'n': 0, 'scheme': 'none: committed rounds only (stated limitation)'},
            'experiments': [{'world': 'coco_depot_v1', 'scenarios': {
                                'kind': 'rounds', 'game': 'fetch_rush',
                                'rounds': [{'seed': s, 'mode': 'phone'} for s in ex.FETCH_RUSH_SEEDS]}},
                            {'world': 'coco_depot_colours_v1', 'scenarios': {
                                'kind': 'rounds', 'game': 'fetch_colour',
                                'colours': list(ex.FETCH_COLOURS)}}],
            'datasheet': f'docs/bench/v1/{B.TASK_SUITE}.md', 'scenarios': scen}


def build(ids):
    out = {}
    for sid in ids:
        out[sid] = task() if sid == B.TASK_SUITE else nav(sid)
        print(f'{sid}: {len(out[sid]["scenarios"])} scenarios, tiers {out[sid]["tiers"]["counts"]}',
              flush=True)
    return out


def text(suite):
    return json.dumps(suite, indent=1, sort_keys=False) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    ids = a.only or list(B.SUITES) + [B.TASK_SUITE]
    bad = 0
    for sid, s in build(ids).items():
        p = OUT / f'{sid}.v1.json'
        if a.check:
            same = p.is_file() and p.read_text() == text(s)
            print(f'{sid}: {"up to date" if same else "DIFFERS"}')
            bad += not same
        else:
            if p.is_file() and p.read_text() != text(s):
                print(f'{sid}: REFUSING to overwrite a frozen suite (delete nothing; bump the '
                      'version instead)')
                bad += 1
                continue
            p.write_text(text(s))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
