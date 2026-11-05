#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.7: MODEL beside STACK for the files that ran as real ROS 2 nodes.

    ros2_summary.py [--runs ~/coco_lab_runs/r2] [--out docs/v2/r2/data/r27]

Reads the Gazebo + Nav2 sessions (tools/r2/ros2_queue.sh; STACK, simulation), runs the same files
on the same scenarios in COCO Lab's model natively (MODEL), and writes:

- ``summary.json`` -- every number below, per session and pooled;
- ``stack.json`` -- the "Browser vs ROS 2" panel's rows, keyed by each file's sha256 (the Studio and
  the leaderboard show them only for that exact file);
- ``raw_checksums.sha256`` -- sha256 of every raw results/log file the numbers came from.

Gaps are stated as STACK minus MODEL over the scenarios both succeeded on (paired), never
across different scenario sets. Nothing is rounded away; a failure is counted, not dropped.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics as st
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / 'coco_lab'), str(REPO / 'coco_schemas'), str(REPO / 'coco_config')]
from coco_lab import experiments as ex, exp_user  # noqa: E402

T = REPO / 'coco_lab' / 'coco_lab' / 'templates'
FILES = {'astar_starter': T / 'planner_astar.py',
         'theta_star': REPO / 'docs' / 'v2' / 'r2' / 'data' / 'r27' / 'files' / 'theta_star.py',  # PR #31's file
         'pure_pursuit': T / 'controller_pure_pursuit.py',
         'particle_filter': T / 'localiser_particle_filter.py'}
SERVERS = {'compute_path_to_pose': 'stock', 'user_compute_path_to_pose': 'astar_starter',
           'user_theta_compute_path_to_pose': 'theta_star'}


def rows(p):
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()] if p.exists() else []


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def fmt(v, unit=''):
    return '—' if v is None else f'{v:.3f}{unit}' if isinstance(v, float) else f'{v}{unit}'


def model_planning(name, scenarios):
    """The file on the same scenarios in the model (planning family, the Depot's defaults)."""
    src = FILES[name].read_text()
    sha = exp_user.register(src)
    # the model's goal is a position: the heading is only what Nav2's goal pose needed
    pairs = [{'id': s['id'], 'start': s['start'], 'goal': s['goal'][:2]} for s in scenarios]
    p = ex.plan({'schema': ex.SCHEMA, 'family': 'planning', 'world': 'coco_depot_v1', 'seed': 1,
                 'algorithms': [{'name': 'user', 'id': name, 'code_sha256': sha}],
                 'scenarios': {'kind': 'pairs', 'pairs': pairs, 'seed': 1}})
    return {r['scenario']: r for r in ex.run_all(p)}, sha


def model_legs(name, family, legs):
    src = FILES[name].read_text()
    sha = exp_user.register(src)
    p = ex.plan({'schema': ex.SCHEMA, 'family': family, 'world': 'coco_depot_colours_v1', 'seed': 1,
                 'algorithms': [{'name': 'user', 'id': name, 'code_sha256': sha}],
                 'scenarios': {'kind': 'pairs', 'pairs': legs, 'seed': 1},
                 'limits': {'max_ticks': 4200}})
    return {r['scenario']: r for r in ex.run_all(p)}, sha


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(Path.home() / 'coco_lab_runs' / 'r2'))
    ap.add_argument('--out', default=str(REPO / 'docs' / 'v2' / 'r2' / 'data' / 'r27'))
    o = ap.parse_args()
    runs, out = Path(o.runs), Path(o.out)
    summary, stack, raw = {}, {}, []

    # -- planners: 20 Depot scenarios, 3 sessions each; stock Nav2 (Smac 2D) on the same costmap
    plan_sessions = sorted(d for d in runs.glob('plan_rep[0-9]') if (d / 'results.jsonl').exists())
    by = {}
    for d in plan_sessions:
        raw.append(d / 'results.jsonl')
        for r in rows(d / 'results.jsonl'):
            if 'server' in r and 'wall_s' in r:
                by.setdefault(SERVERS[r['server']], []).append(dict(r, session=d.name))
    # planning TIME is quoted from the balanced-profile session (the counts come from sessions 1-3)
    balanced = {}
    for d in sorted(runs.glob('plan_balanced_[0-9]')):
        raw.append(d / 'results.jsonl')
        for r in rows(d / 'results.jsonl'):
            if 'server' in r and 'wall_s' in r:
                balanced.setdefault(SERVERS[r['server']], []).append(r)
    scen = json.loads((out / 'depot20_plan.json').read_text())['scenarios']
    model = {}
    for name in ('astar_starter', 'theta_star'):
        model[name] = model_planning(name, scen)
    plan = {}
    for who, rs in by.items():
        ok = [r for r in rs if r['status'] == 'SUCCEEDED']
        plan[who] = {'requests': len(rs), 'succeeded': len(ok),
                     'by_status': {s: sum(1 for r in rs if r['status'] == s)
                                   for s in sorted({r['status'] for r in rs})},
                     'error_codes': sorted({r.get('error_code') for r in rs if r['status'] != 'SUCCEEDED'
                                            and r.get('error_code') is not None}),
                     'median_length_m': med([r['length_m'] for r in ok]),
                     'median_wall_s': med([r['wall_s'] for r in rs]), 'sessions': sorted({r['session'] for r in rs}),
                     'balanced': {'requests': len(balanced.get(who, [])),
                                  'succeeded': sum(1 for r in balanced.get(who, []) if r['status'] == 'SUCCEEDED'),
                                  'median_wall_s': med([r['wall_s'] for r in balanced.get(who, [])])}}
        if who in model:
            recs, sha = model[who]
            m_ok = {k: v for k, v in recs.items() if v['success']}
            pairs = [(m_ok[r['id']]['metrics']['path_length_m'], r['length_m']) for r in ok if r['id'] in m_ok]
            gaps = [s - m for m, s in pairs]
            plan[who]['model'] = {'scenarios': len(recs), 'succeeded': len(m_ok),
                                  'median_length_m': med([v['metrics']['path_length_m'] for v in m_ok.values()])}
            plan[who]['paired_gap_m'] = {'n': len(gaps), 'median': med(gaps),
                                         'median_relative': med([(s - m) / m for m, s in pairs])}
            stock_ok = {(r['session'], r['id']): r['length_m'] for r in by.get('stock', []) if r['status'] == 'SUCCEEDED'}
            vs = [r['length_m'] - stock_ok[(r['session'], r['id'])] for r in ok if (r['session'], r['id']) in stock_ok]
            plan[who]['vs_stock_paired_m'] = {'n': len(vs), 'median': med(vs)}
            P = plan[who]
            stack[sha] = {'label': f'{who} as the Nav2 planner (ComputePathToPose) on 20 depot-nav-100 scenarios, '
                                   f'{len(plan_sessions)} Gazebo sessions',
                          'rows': [
                              {'metric': 'plans found', 'model': f"{P['model']['succeeded']}/{P['model']['scenarios']}",
                               'stack': f"{P['succeeded']}/{P['requests']}", 'gap': '—'},
                              {'metric': 'path length, median (m)', 'model': fmt(P['model']['median_length_m']),
                               'stack': fmt(P['median_length_m']),
                               'gap': f"{fmt(P['paired_gap_m']['median'])} m paired median "
                                      f"(n={P['paired_gap_m']['n']})"},
                              {'metric': 'vs stock Nav2 (Smac 2D), same scenario and session',
                               'model': '—', 'stack': f"{fmt(P['vs_stock_paired_m']['median'])} m median "
                                                      f"(n={P['vs_stock_paired_m']['n']})", 'gap': '—'},
                              {'metric': 'planning time, median (wall s, this laptop, balanced profile)',
                               'model': '—', 'stack': fmt(P['balanced']['median_wall_s']),
                               'gap': 'not compared (devices differ)'}],
                          'source': 'MODEL: coco_lab, the planning family on the same scenarios (0.1 m Depot map). '
                                    'STACK: the exported package in Gazebo Harmonic + Nav2 Jazzy on its live '
                                    '0.05 m global costmap (simulation; no physical robot). '
                                    'docs/v2/r2/data/r27/README.md'}
    summary['planning'] = plan

    # -- drives: NavigateToPose with each planner in the behaviour tree
    drives = {}
    for d in sorted(runs.glob('drive_*')):
        if d.name.split('_void')[0] != d.name:
            continue
        rs = rows(d / 'results.jsonl')
        raw.append(d / 'results.jsonl')
        drives[d.name[6:]] = {'goals': len(rs), 'succeeded': sum(1 for r in rs if r.get('status') == 'SUCCEEDED'),
                              'statuses': [r.get('status') for r in rs],
                              'median_driven_m': med([r.get('driven_m') for r in rs]),
                              'median_sim_s': med([r.get('sim_s') for r in rs]),
                              'median_truth_to_goal_m': med([r.get('truth_to_goal_m') for r in rs])}
    summary['drive'] = drives
    # the drive belongs beside the plan in the panel: a plan Nav2's controller cannot follow is visible
    for name, (_, sha) in model.items():
        D, S = drives.get(f'coco_user_{name}'), drives.get('stock')
        if D and sha in stack:
            stack[sha]['rows'].append(
                {'metric': "driven to the goal (NavigateToPose, Nav2's stock RPP controller, 5 Depot goals)",
                 'model': '—', 'stack': f"{D['succeeded']}/{D['goals']}",
                 'gap': f"stock Nav2 planner: {S['succeeded']}/{S['goals']}" if S else '—'})

    # -- the pure-pursuit controller: the four colour rounds, five runs each
    def round_sessions(prefix):
        got = {}
        for d in sorted(runs.glob(f'{prefix}_*')):
            if '_void' in d.name or not (d / 'results.jsonl').exists():
                continue
            raw.append(d / 'results.jsonl')
            got[d.name] = rows(d / 'results.jsonl')
        return got
    pp = round_sessions('pp')
    legs_done = {k: sum(1 for r in v if r.get('status') == 'SUCCEEDED') for k, v in pp.items()}
    rounds_ok = {c: sum(1 for k, v in pp.items() if k.startswith(f'pp_{c}_') and v and
                        all(r.get('status') == 'SUCCEEDED' for r in v) and len(v) == 2)
                 for c in ('red', 'green', 'blue', 'yellow')}
    rounds_n = {c: sum(1 for k in pp if k.startswith(f'pp_{c}_')) for c in rounds_ok}
    goals = {c: json.loads((out / 'goals' / f'colour_{c}.json').read_text()) for c in rounds_ok}
    legs = []
    for c, g in goals.items():
        prev = g['start']
        for leg in g['goals']:
            legs.append({'id': f"{c}:{leg['id']}", 'start': prev, 'goal': leg['pose'][:2]})
            prev = leg['pose']
    if pp:
        recs, sha = model_legs('pure_pursuit', 'control', legs)
        m_ok = sum(1 for r in recs.values() if r['success'])
        st_legs = [r for v in pp.values() for r in v]
        # paired per leg: the median of a leg's STACK runs minus the model's time on that same leg
        per_leg = {}
        for k, v in pp.items():
            for r in v:
                if r.get('status') == 'SUCCEEDED' and r.get('sim_s') is not None:
                    per_leg.setdefault(f"{k.split('_')[1]}:{r['id']}", []).append(r['sim_s'])
        leg_gaps = {k: med(ts) - recs[k]['metrics']['time_s'] for k, ts in sorted(per_leg.items())
                    if k in recs and recs[k]['success']}
        summary['controller'] = {'rounds': {c: f'{rounds_ok[c]}/{rounds_n[c]}' for c in rounds_ok},
                                 'legs_succeeded': sum(legs_done.values()), 'legs': len(st_legs),
                                 'median_leg_sim_s': med([r.get('sim_s') for r in st_legs]),
                                 'model_legs': f'{m_ok}/{len(recs)}',
                                 'model_median_leg_s': med([r['metrics']['time_s'] for r in recs.values() if r['success']]),
                                 'paired_leg_gap_s': {'n': len(leg_gaps), 'median': med(list(leg_gaps.values())),
                                                      'per_leg': leg_gaps}}
        C = summary['controller']
        stack[sha] = {'label': 'the pure-pursuit starter as the Nav2 controller (FollowPath, through cmd_vel_arbiter) '
                               'on the four colour rounds, 5 runs each',
                      'rows': [{'metric': 'rounds completed', 'model': '—',
                                'stack': ', '.join(f'{c} {v}' for c, v in C['rounds'].items()), 'gap': '—'},
                               {'metric': 'legs reached', 'model': C['model_legs'],
                                'stack': f"{C['legs_succeeded']}/{C['legs']}", 'gap': '—'},
                               {'metric': 'time per leg, median (sim s)', 'model': fmt(C['model_median_leg_s']),
                                'stack': fmt(C['median_leg_sim_s']),
                                'gap': f"{fmt(C['paired_leg_gap_s']['median'], ' s')} paired median "
                                       f"(n={C['paired_leg_gap_s']['n']} legs)"}],
                      'source': 'MODEL: coco_lab, the control family on the same legs (Arena A* plans, the model\'s '
                                'kinematics). STACK: Gazebo + Nav2 with Nav2\'s own planner, the controller exported as '
                                'a ROS 2 package; legs counted by NavigateToPose. docs/v2/r2/data/r27/README.md'}

    # -- the particle filter in place of AMCL: one round, pose error against Gazebo's truth
    pf = round_sessions('pf')
    if pf:
        st_rows = [r for v in pf.values() for r in v]
        recs, sha = model_legs('particle_filter', 'localisation', legs[:2])
        summary['localiser'] = {'legs': len(st_rows),
                                'succeeded': sum(1 for r in st_rows if r.get('status') == 'SUCCEEDED'),
                                'error_at_leg_end_m': [r.get('amcl_error_m') for r in st_rows],
                                'model_final_err_m': [r['metrics'].get('final_err_xy_m') for r in recs.values()]}
        L = summary['localiser']
        stack[sha] = {'label': 'the particle-filter starter in place of AMCL (map -> odom, /amcl_pose), one red round',
                      'rows': [{'metric': 'legs reached', 'model': f"{sum(1 for r in recs.values() if r['metrics'].get('reached_goal'))}/{len(recs)}",
                                'stack': f"{L['succeeded']}/{L['legs']}", 'gap': '—'},
                               {'metric': 'pose error at each leg end (m)',
                                'model': ', '.join(fmt(v) for v in L['model_final_err_m']),
                                'stack': ', '.join(fmt(v) for v in L['error_at_leg_end_m']),
                                'gap': 'STACK error: /amcl_pose (yours) against Gazebo\'s ground truth'}],
                      'source': 'A smoke run, not a rate. docs/v2/r2/data/r27/README.md'}

    out.mkdir(parents=True, exist_ok=True)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True, default=str) + '\n')
    (out / 'stack.json').write_text(json.dumps({'schema': 'coco.r2.stack.v1', 'evidence': 'MODEL beside STACK',
                                                 'entries': stack}, indent=1, sort_keys=True) + '\n')
    lines = []
    # each session's meta.json too: it records the conditions (power profile, AC, versions, git)
    for p in sorted(set(raw) | {q.parent / 'meta.json' for q in raw}):
        if p.exists():
            lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(runs)}')
    (out / 'raw_checksums.sha256').write_text('\n'.join(lines) + '\n')
    print(json.dumps(summary, indent=1, default=str)[:4000])


if __name__ == '__main__':
    main()
