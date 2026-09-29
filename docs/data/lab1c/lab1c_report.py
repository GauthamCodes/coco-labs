#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Derive the Phase 1C conformance summary from conformance.json. Pure.

  python3 lab1c_report.py conformance.json [--out summary.json]

Every quantity is DERIVED from the measured per-pair records by the
formulas below, fixed before the run (plan §D, §E.1). Relative gaps are
``(other - reference) / reference``.

- ``E_gap_smac_raw_vs_C1``: Smac's raw path's C1 edge sum against the C1
  Dijkstra optimum, over pairs whose raw path was captured, is defined
  (8-connected, free) and ends on the goal cell. The pre-registered
  prediction: every one within relative 1e-4.
- ``L_gap_smac_vs_C1`` and ``I_gap_smac_vs_C1``: Smac's RETURNED
  (smoothed) path against the C1 Dijkstra path, over pairs where Smac
  succeeded. Also ``_raw`` versions of L and I.
- ``NavFn``/``NavFnAStar`` L and I against C1 and against Smac's returned
  path, over pairs where that planner succeeded AND its NavFn-pass
  costmap difference was fully explained (accepted).
- ``E_C0_over_C1``: C0 Dijkstra's optimum over C1's, where both exist.
- Counts: valid, draws, void, no_path (and Smac's answer on them),
  endpoint failures, captured raw paths, prediction holds/fails.
"""

import argparse
import json
import sys

from coco_lab_ros.metrics import distribution

PRED_TOL = 1e-4


def rel(a, b):
    return (a - b) / b


def summarise(doc):
    pairs = doc['pairs']
    out = {'valid': len(pairs), 'draws': doc['draws'],
           'separation_rejects': doc['separation_rejects'],
           'void': len(doc['void']), 'no_path': len(doc['no_path']),
           'f5_shortfall': doc.get('f5_shortfall'),
           'navfn_unexplained_changes': doc.get('navfn_unexplained_changes'),
           'S0': doc.get('S0', {}).get('content_hash')}
    e_gap, disagree, raw_missing, raw_undef, raw_endpoint = [], [], 0, 0, 0
    for p in pairs:
        r = p['smac_raw']
        if not r.get('captured'):
            raw_missing += 1
            continue
        if r['E'] is None:
            raw_undef += 1
            continue
        if not r['endpoint_ok']:
            raw_endpoint += 1
            continue
        g = rel(r['E'], p['lab']['C1_dijkstra']['E'])
        e_gap.append(g)
        if abs(g) > PRED_TOL:
            disagree.append({'draw': p['draw'], 'gap': g,
                             'start': p['start_cell'],
                             'goal': p['goal_cell']})
    out['smac_raw'] = {'not_captured': raw_missing, 'E_undefined': raw_undef,
                       'endpoint_not_goal': raw_endpoint,
                       'compared': len(e_gap)}
    out['E_gap_smac_raw_vs_C1'] = distribution(e_gap)
    out['prediction'] = {'tolerance': PRED_TOL,
                         'within': len(e_gap) - len(disagree),
                         'outside': len(disagree), 'outside_pairs': disagree}
    out['E_gap_smac_raw_vs_C1_signed'] = {
        'above': sum(1 for g in e_gap if g > PRED_TOL),
        'below': sum(1 for g in e_gap if g < -PRED_TOL)}

    def gaps(planner, key, ref='C1', need_accept=False, raw=False):
        vals = []
        for p in pairs:
            if raw:
                r = p['smac_raw']
                if not r.get('captured') or key not in r:
                    continue
                v = r[key]
            else:
                n = p['nav2'].get(planner)
                if not n or not n.get('ok'):
                    continue
                if need_accept and not p.get('navfn_pass', {}).get(
                        'accepted'):
                    continue
                v = n[key]
            if ref == 'C1':
                b = p['lab']['C1_dijkstra'][key]
            else:
                s = p['nav2']['GridBased']
                if not s.get('ok'):
                    continue
                b = s[key]
            vals.append(rel(v, b))
        return distribution(vals)

    for key in ('L', 'I'):
        out[f'{key}_gap_smac_vs_C1'] = gaps('GridBased', key)
        out[f'{key}_gap_smac_raw_vs_C1'] = gaps(None, key, raw=True)
        for nf in ('NavFn', 'NavFnAStar'):
            out[f'{key}_gap_{nf}_vs_C1'] = gaps(nf, key, need_accept=True)
            out[f'{key}_gap_{nf}_vs_smac'] = gaps(nf, key, ref='smac',
                                                  need_accept=True)
    c0 = [p['lab']['C0_dijkstra']['E'] / p['lab']['C1_dijkstra']['E']
          for p in pairs if p['lab']['C0_dijkstra'].get('E')]
    out['E_C0_over_C1'] = distribution(c0)
    out['C0_strictly_costlier'] = sum(1 for v in c0 if v > 1 + 1e-12)
    out['astar_equals_dijkstra_C1'] = sum(
        1 for p in pairs if abs(rel(p['lab']['C1_astar']['E'],
                                    p['lab']['C1_dijkstra']['E'])) < 1e-9)
    out['planner_ok'] = {pid: sum(1 for p in pairs if p['nav2'][pid]['ok'])
                         for pid in ('GridBased', 'NavFn', 'NavFnAStar')}
    out['no_path_smac_answers'] = [
        {'draw': p['draw'], 'smac_ok': p['nav2']['GridBased']['ok'],
         'error_code': p['nav2']['GridBased']['error_code']}
        for p in doc['no_path']]
    out['enters_blocked'] = {
        pid: sum(1 for p in pairs if p['nav2'][pid].get('enters_blocked'))
        for pid in ('GridBased', 'NavFn', 'NavFnAStar')}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('conformance')
    ap.add_argument('--out')
    a = ap.parse_args()
    with open(a.conformance) as f:
        s = summarise(json.load(f))
    text = json.dumps(s, sort_keys=True, indent=1)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
