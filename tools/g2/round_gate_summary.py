#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2 per-round gate: summarise tools/g2/round_gate.sh's runs (STACK) for the repository.

    tools/g2/round_gate_summary.py RUNS_DIR OUT.json [--table OUT.md]

Reads RUNS_DIR/gate_rounds.jsonl (one line per run, void runs included) and each counted run's
results.jsonl and meta.json. Writes every run's legs (Nav2 status, sim time, distance, truth-to-goal
and AMCL error at the leg's end), the run's sources (git commit, world / map / params / goals
sha256, bag files' sha256 and bytes) and machine state, and per round the pass count. The raw runs
(bags, logs) stay outside git.
"""
import argparse
import hashlib
import json
import os


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def run_record(line):
    out = {'round': line['round'], 'run': line['run'], 'dir': os.path.basename(line['dir']), 'rc': line['rc'],
           'void': line['void']}
    if line['void']:
        return out
    d = line['dir']
    legs = [json.loads(x) for x in open(os.path.join(d, 'results.jsonl')) if x.strip()]
    meta = json.load(open(os.path.join(d, 'meta.json')))
    bag = os.path.join(d, 'bag')
    bags = sorted(f for f in os.listdir(bag) if f.endswith('.mcap')) if os.path.isdir(bag) else []
    out.update({
        'all_succeeded': bool(legs) and all(L['status'] == 'SUCCEEDED' for L in legs),
        'legs': [{k: L.get(k) for k in ('id', 'status', 'error_code', 'sim_s', 'driven_m', 'truth_to_goal_m',
                                        'amcl_error_m')} for L in legs],
        'meta': {k: meta.get(k) for k in ('started_utc', 'level', 'git_commit', 'git_dirty_paths', 'world_sha256',
                                          'map_pgm_sha256', 'map_yaml_sha256', 'nav2_params_sha256', 'goals_sha256',
                                          'power_profile', 'ac_online', 'nvidia', 'packages', 'ros_domain_id')},
        'bags': {f: {'sha256': sha(os.path.join(bag, f)), 'bytes': os.path.getsize(os.path.join(bag, f))}
                 for f in bags},
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('runs')
    ap.add_argument('out')
    ap.add_argument('--table')
    o = ap.parse_args()
    lines = [json.loads(x) for x in open(os.path.join(o.runs, 'gate_rounds.jsonl')) if x.strip()]
    runs = [run_record(x) for x in lines]
    rounds = {}
    for r in runs:
        s = rounds.setdefault(r['round'], {'counted': 0, 'passed': 0, 'void': 0})
        if r['void']:
            s['void'] += 1
        else:
            s['counted'] += 1
            s['passed'] += int(r['all_succeeded'])
    doc = {'schema': 'coco_lab.g2_round_gate', 'version': 1, 'evidence': 'STACK',
           'about': 'G2 per-round gate (owner 2026-10-25): tools/g2/round_gate.sh, a fresh headless Gazebo + Nav2 '
                    'per run, m6f8_nav.py --initial-pose; Gazebo actors parked; driving legs only, no grasp; '
                    'never hardware',
           'rounds': rounds, 'runs': runs}
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write('\n')
    if o.table:
        rows = ['| Round | Run | Legs (sim time) | Truth to goal at each leg\'s end (m) | AMCL error (m) | Pass |',
                '|---|---|---|---|---|---|']
        for r in runs:
            if r['void']:
                rows.append(f"| {r['round']} | {r['run']} | void (runner rc {r['rc']}; retried) | | | — |")
                continue
            legs = ' · '.join(f"{'✓' if L['status'] == 'SUCCEEDED' else '✗ ' + L['status']} {L['sim_s']} s"
                              for L in r['legs'])
            tg = ' · '.join(f"{L['truth_to_goal_m']}" for L in r['legs'])
            am = ' · '.join(f"{L['amcl_error_m']}" for L in r['legs'])
            rows.append(f"| {r['round']} | {r['run']} | {legs} | {tg} | {am} | {'✓' if r['all_succeeded'] else '✗'} |")
        rows += ['', '| Round | Passed / counted | Void (retried) |', '|---|---|---|']
        rows += [f"| {k} | {v['passed']} / {v['counted']} | {v['void']} |" for k, v in rounds.items()]
        with open(o.table, 'w') as f:
            f.write('\n'.join(rows) + '\n')
    print(json.dumps(rounds))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
