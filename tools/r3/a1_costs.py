#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3 Part A (Gautham's answer 2): does Lazy Theta*'s path put the robot's centre in inscribed or
lethal cost where Nav2's RPP checks for collisions? STACK evidence, from ros2_bench.py --costs.

    tools/r3/a1_costs.py RUNS_DIR OUT.json

RUNS_DIR holds costs_<planner>/ sessions (results.jsonl + costs.jsonl). For every planner and
scenario: how many received plans there were, how many had at least one pose at cost >= 253
(INSCRIBED_INFLATED_OBSTACLE: the robot's centre may not be there) in the LOCAL costmap (the
one RPP's collision check reads) and in the global one, the largest share of such poses in a
plan, and the drive's outcome. Nothing is inferred here; the comparison is in the README.
"""
import json
from pathlib import Path
import sys


def summarise(d: Path) -> dict:
    results = {}
    for line in (d / 'results.jsonl').read_text().splitlines():
        r = json.loads(line)
        results[r['id']] = {'status': r.get('status'), 'error_code': r.get('error_code'),
                            'driven_m': r.get('driven_m'), 'truth_to_goal_m': r.get('truth_to_goal_m')}
    per = {}
    for line in (d / 'costs.jsonl').read_text().splitlines():
        c = json.loads(line)
        s = per.setdefault(c['id'], {'plans': 0, 'local_ge253': 0, 'global_ge253': 0,
                                     'local_ge128': 0, 'max_local_share_ge253': 0.0,
                                     'local_unavailable': 0})
        s['plans'] += 1
        loc, glo = c.get('local'), c.get('global')
        if isinstance(loc, dict) and 'n_ge_253' in loc:
            if loc['n_ge_253']:
                s['local_ge253'] += 1
            if loc['n_ge_128']:
                s['local_ge128'] += 1
            if loc['inside']:
                s['max_local_share_ge253'] = max(s['max_local_share_ge253'],
                                                 round(loc['n_ge_253'] / loc['inside'], 4))
        else:
            s['local_unavailable'] += 1
        if isinstance(glo, dict) and glo.get('n_ge_253'):
            s['global_ge253'] += 1
    out = {}
    for sid, r in sorted(results.items()):
        s = per.get(sid, {'plans': 0})
        out[sid] = dict(r, **s, share_of_plans_local_ge253=round(
            s.get('local_ge253', 0) / s['plans'], 4) if s['plans'] else None)
    session = json.loads((d / 'session.json').read_text())
    return {'session': session, 'scenarios': out,
            'reached': sum(1 for r in results.values() if r['status'] == 'SUCCEEDED'),
            'goals': len(results)}


def main():
    runs, out = Path(sys.argv[1]), Path(sys.argv[2])
    doc = {'about': __doc__.strip().split('\n\n')[1].replace('\n', ' '),
           'planners': {d.name[len('costs_'):]: summarise(d)
                        for d in sorted(runs.glob('costs_*')) if (d / 'DONE').exists()}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    for name, p in doc['planners'].items():
        print(f"{name}: reached {p['reached']}/{p['goals']}")
        for sid, s in p['scenarios'].items():
            print(f"  {sid} {s['status']:9s} plans {s['plans']:5d}  local>=253 in "
                  f"{s.get('local_ge253', 0):5d} ({s['share_of_plans_local_ge253']})  "
                  f"global>=253 in {s.get('global_ge253', 0)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
