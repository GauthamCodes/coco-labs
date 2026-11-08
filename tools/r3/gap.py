#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R3.5: the browser model against real Nav2 on the same scenarios (MODEL vs STACK).

    tools/r3/gap.py RUNS_DIR OUT.json

RUNS_DIR is ~/coco_lab_runs/r3/r34 (tools/r3/ros2_queue_r34.sh); the model side is the committed
R3.2 baselines (docs/v2/r3/bench/<suite>/<family>/public/runs.jsonl). Pairs, per scenario id:

- planning: model A* vs the exported A* starter as a ROS 2 node (the same algorithm); model A* vs
  Nav2 Smac 2D, model Dijkstra vs Nav2 NavFn (counterparts, not the same code) -- each Nav2 planner
  as given (stock) and snapped. Success = a path found; length ratio = STACK / MODEL.
- control: model RPP / DWA / MPPI vs Nav2 RPP / DWB / MPPI (Nav2's own controllers, counterparts)
  under the same scenario; success = goal reached; ratios of time and distance driven.
- localisation (loc-track-30): model MCL and MCL + injection vs Nav2 AMCL, and model MCL vs the
  particle-filter starter as a ROS 2 node in AMCL's place (counterparts). Drive sessions record no
  estimate error, so STACK success = Nav2 SUCCEEDED and the TRUE distance to the goal within
  ``LOC_OK_M`` (Nav2's 0.25 m goal tolerance + the model's 0.5 m ``localise.OK_XY``); the model's
  own success (arrived and its estimate within 0.5 m / 0.3 rad) is unchanged. Ratio: time to goal.

For every pair: the success confusion table (model x stack), agreement, the share where the model is
optimistic (model succeeds, stack fails) or pessimistic (the reverse), and the median ratios over
scenarios both solved. STACK sessions repeat (rep1..3): a scenario's STACK success is the majority
over its repeats, and every repeat is kept in the per-scenario rows.
"""
import json
from pathlib import Path
import statistics
import sys

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / 'docs' / 'v2' / 'r3' / 'bench'
PLAN_PAIRS = [('astar', 'user_compute_path_to_pose', 'the same A* file, browser vs ROS 2 node'),
              ('astar', 'compute_path_to_pose', 'model A* vs Nav2 Smac 2D, stock'),
              ('astar', 'compute_path_to_pose+snapped', 'model A* vs Nav2 Smac 2D, snapped'),
              ('dijkstra', 'compute_path_to_pose@NavFn', 'model Dijkstra vs Nav2 NavFn, stock'),
              ('dijkstra', 'compute_path_to_pose@NavFn+snapped', 'model Dijkstra vs Nav2 NavFn, snapped'),
              ('astar', 'compute_path_to_pose@SmacHybrid+snapped',
               'model A* vs Nav2 Smac Hybrid-A*, snapped (no model counterpart: reference only)')]
CTRL_PAIRS = [('rpp', 'rpp'), ('dwa', 'dwb'), ('mppi', 'mppi')]
LOC_PAIRS = [('mcl', 'amcl', 'model MCL vs Nav2 AMCL'),
             ('mcl_augmented', 'amcl', 'model MCL + injection vs Nav2 AMCL'),
             ('mcl', 'pf', 'model MCL vs the particle-filter starter as a ROS 2 node')]
#: STACK localisation success: Nav2's xy_goal_tolerance (prepare_gazebo.py) + localise.OK_XY (m)
LOC_OK_M = 0.25 + 0.5


def model_runs(suite, family):
    p = BENCH / suite / family / 'public' / 'runs.jsonl'
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        r = json.loads(line)
        out[(r['algorithm'], r['scenario'])] = r
    return out


def stack_rows(runs_dir, prefix):
    rows = []
    for d in sorted(runs_dir.glob(prefix + '_rep*')):
        if not (d / 'DONE').exists() or not (d / 'results.jsonl').exists():
            continue
        for line in (d / 'results.jsonl').read_text().splitlines():
            rows.append(dict(json.loads(line), session=d.name))
    return rows


def majority(vals):
    return sum(vals) * 2 > len(vals)


def pair_stats(items):
    """items: [(scenario, model_ok, [stack_ok...], model_value, [stack_values...])]."""
    conf = {'both': 0, 'model_only': 0, 'stack_only': 0, 'neither': 0}
    ratios = []
    for sid, m_ok, s_oks, m_val, s_vals in items:
        s_ok = majority(s_oks)
        key = 'both' if m_ok and s_ok else 'model_only' if m_ok else 'stack_only' if s_ok else 'neither'
        conf[key] += 1
        good = [v for ok, v in zip(s_oks, s_vals) if ok and v is not None]
        if m_ok and s_ok and m_val and good:
            ratios.append(statistics.median(good) / m_val)
    n = len(items)
    return {'n': n, 'confusion': conf,
            'agreement': round((conf['both'] + conf['neither']) / n, 4) if n else None,
            'model_optimistic': round(conf['model_only'] / n, 4) if n else None,
            'model_pessimistic': round(conf['stack_only'] / n, 4) if n else None,
            'ratio_median': round(statistics.median(ratios), 4) if ratios else None,
            'ratio_n': len(ratios)}


def planning(runs_dir, suite):
    model = model_runs(suite, 'planning')
    rows = stack_rows(runs_dir, f'{suite}_plan')
    out = {}
    for m_alg, server, label in PLAN_PAIRS:
        by = {}
        for r in rows:
            if r.get('server') == server:
                by.setdefault(r['id'], []).append(r)
        items = []
        for sid, rs in sorted(by.items()):
            m = model.get((m_alg, sid))
            if m is None:
                continue
            items.append((sid, m['success'], [r['status'] == 'SUCCEEDED' for r in rs],
                          m['metrics'].get('path_length_m'), [r.get('length_m') for r in rs]))
        if items:
            out[server] = dict(pair_stats(items), model=m_alg, label=label, metric='path length')
    return out


def control(runs_dir, suite, rule=''):
    model = model_runs(suite, 'control')
    out = {}
    for m_alg, s_ctrl in CTRL_PAIRS:
        rows = stack_rows(runs_dir, f'{suite}{rule}_{s_ctrl}')
        by = {}
        for r in rows:
            by.setdefault(r['id'], []).append(r)
        items = []
        for sid, rs in sorted(by.items()):
            m = model.get((m_alg, sid))
            if m is None:
                continue
            items.append((sid, m['success'], [r['status'] == 'SUCCEEDED' for r in rs],
                          m['metrics'].get('time_s'), [r.get('sim_s') for r in rs]))
        if items:
            out[s_ctrl] = dict(pair_stats(items), model=m_alg, metric='time to goal (s)',
                               label=f'model {m_alg} vs Nav2 {s_ctrl.upper()}')
    return out


def localisation(runs_dir, suite='loc-track-30'):
    model = model_runs(suite, 'localisation')
    out = {}
    for m_alg, s_loc, label in LOC_PAIRS:
        by = {}
        for r in stack_rows(runs_dir, f'{suite}_{s_loc}'):
            by.setdefault(r['id'], []).append(r)
        items = []
        for sid, rs in sorted(by.items()):
            m = model.get((m_alg, sid))
            if m is None:
                continue
            oks = [r['status'] == 'SUCCEEDED' and r.get('truth_to_goal_m') is not None
                   and r['truth_to_goal_m'] <= LOC_OK_M for r in rs]
            items.append((sid, m['success'], oks, m['metrics'].get('time_s'), [r.get('sim_s') for r in rs]))
        if items:
            out[f'{s_loc}:{m_alg}'] = dict(pair_stats(items), model=m_alg, label=label,
                                         metric=f'time to goal (s); STACK success = arrived, truth within {LOC_OK_M} m')
    return out


def main():
    runs_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    doc = {'about': __doc__.strip().split('\n\n')[1].replace('\n', ' '), 'planning': {}, 'control': {}, 'localisation': {}}
    for s in ('depot-nav-100', 'depot-narrow-30', 'depot-long-50', 'depot-clutter-50'):
        r = planning(runs_dir, s)
        if r:
            doc['planning'][s] = r
    for s in ('ctrl-corridor-30', 'ctrl-corners-30', 'ctrl-dynamic-30'):
        r = control(runs_dir, s)
        if r:
            doc['control'][s] = r
    r = control(runs_dir, 'ctrl-dynamic-30', '-noyield')
    if r:
        doc['control']['ctrl-dynamic-30 (actors keep schedule)'] = r
    r = localisation(runs_dir)
    if r:
        doc['localisation'] = {'loc-track-30': r}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    print(json.dumps({k: {s: {p: (v['agreement'], v['ratio_median']) for p, v in x.items()}
                          for s, x in doc[k].items()} for k in ('planning', 'control', 'localisation')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
