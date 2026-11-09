#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3 Part A (Gautham's answer 3): stock Nav2 as asked, and with start and goal snapped to the
nearest free cell, beside the A* starter -- STACK, from ros2_bench.py --snap.

    tools/r3/a1_snap.py RUNS_DIR OUT.json

Per server: requests, plans found, error codes; the snap distances; the paired median path
length difference between snapped Nav2 and the A* starter (same scenario and session).
"""
import json
from pathlib import Path
import statistics
import sys


def main():
    runs, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    sessions = sorted(d for d in runs.glob('plan_snap*') if (d / 'DONE').exists())
    meta = {}
    for d in sessions:
        meta[d.name] = json.loads((d / 'session.json').read_text())
        for line in (d / 'results.jsonl').read_text().splitlines():
            rows.append(dict(json.loads(line), session=d.name))
    servers = sorted({r['server'] for r in rows})
    per = {}
    for s in servers:
        rs = [r for r in rows if r['server'] == s]
        codes = {}
        for r in rs:
            if r['status'] != 'SUCCEEDED':
                codes[str(r.get('error_code'))] = codes.get(str(r.get('error_code')), 0) + 1
        lens = [r['length_m'] for r in rs if r['status'] == 'SUCCEEDED']
        per[s] = {'requests': len(rs), 'found': sum(r['status'] == 'SUCCEEDED' for r in rs),
                  'failures_by_error_code': codes,
                  'median_length_m': round(statistics.median(lens), 4) if lens else None,
                  'failed_scenarios': sorted({r['id'] for r in rs if r['status'] != 'SUCCEEDED'})}
    snapped = [r for r in rows if r['server'].endswith('+snapped')]
    # moved: more than one cell (0.05 m); every request moves ~0.035 m to its cell's centre
    moved = [r for r in snapped if (r.get('start_snap_m') or 0) > 0.05 or (r.get('goal_snap_m') or 0) > 0.05]
    per['snap'] = {'requests_moved': len(moved),
                   'start_snap_m_max': max((r.get('start_snap_m') or 0) for r in snapped),
                   'goal_snap_m_max': max((r.get('goal_snap_m') or 0) for r in snapped),
                   'moved_scenarios': sorted({r['id'] for r in moved}),
                   'per_scenario_m': {r['id']: [r.get('start_snap_m'), r.get('goal_snap_m')]
                                      for r in moved if r['session'] == sessions[0].name}}
    key = {(r['session'], r['id'], r['server']): r for r in rows}
    gaps = []
    for (sess, sid, srv), r in key.items():
        if srv == 'compute_path_to_pose+snapped' and r['status'] == 'SUCCEEDED':
            u = key.get((sess, sid, 'user_compute_path_to_pose'))
            if u and u['status'] == 'SUCCEEDED':
                gaps.append(r['length_m'] - u['length_m'])
    per['paired_snapped_minus_astar_starter_m'] = {
        'n': len(gaps), 'median': round(statistics.median(gaps), 4) if gaps else None}
    doc = {'about': __doc__.strip().split('\n\n')[1].replace('\n', ' '), 'sessions': meta,
           'servers': per}
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    for s, v in per.items():
        print(s, v)
    return 0


if __name__ == '__main__':
    sys.exit(main())
