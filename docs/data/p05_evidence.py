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
Phase 5 evidence: the Gazebo matrix's run directories -> results and replays.

    python3 docs/data/p05_evidence.py ~/coco_lab_runs/lab4/matrix

reads every run directory written by ``p05_search_run.sh`` (via
``~/coco_search_ws/matrix.sh``) and writes, under ``docs/data/lab4/``:

``runs/<name>.json``
    one digest per run: what the robot was told, the episode (manifest,
    evaluator side), every look and what it saw, the FSM timeline in
    simulator seconds, the mission's outcome, the lift, the home error,
    relocalisations, recoveries, runner checks and the commit.
``results.json``
    the matrix table (what ``lab_web`` shows, marked measured).
``replay/p05_matrix/``
    a search bundle 1.0: every run that looked at least once, REBUILT FROM
    ITS LOOKS ALONE by ``coco_lab.regionsearch.replay_search`` on the
    problem the mission built -- the policy must choose every bay the
    robot chose, or this script stops. The truth goes in each run's
    evaluator block, which replay never reads.

Void runs (directories named ``*.void-N``: a reboot, a dead runner) are
listed in results.json as void and never scored. Ground truth (the
``gt_*`` columns, the manifest) is used for SCORING only.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path[:0] = [os.path.join(REPO, 'coco_lab'),
                os.path.join(REPO, 'lab_web', 'tools')]

from coco_lab import bundle, regionsearch as rs, searchbundle as sbm  # noqa
import build_search  # noqa: E402

OUT = os.path.join(REPO, 'docs', 'data', 'lab4')
HOME = (-2.0, 0.0)
SEARCH_STATES = ('SELECT_SEARCH_REGION', 'SURVEY_REGION',
                 'MARK_REGION_SEARCHED', 'LEAVE_REGION')
TRANSITION = re.compile(
    r'mission_executive\]: ([A-Z_]+) -> ([A-Z_]+)(?: \[([A-Z_]+)\])?(?:: (.*))?$')
MISS = re.compile(r'(bay_\d): no (\w+) in (\d+) perception lines \(saw ([\w,]+)\)')
CHOSE = re.compile(r'search chose (bay_\d)')
TRAVEL = re.compile(r"travel \(m, A\* on [^)]*\) (\{.*\})\s*$")


def _kv(path):
    out = {}
    if os.path.exists(path):
        for ln in open(path):
            if '=' in ln:
                k, v = ln.strip().split('=', 1)
                out[k] = v
    return out


def _sha_dir(path):
    h = hashlib.sha256()
    for root, _, files in sorted(os.walk(path)):
        for f in sorted(files):
            with open(os.path.join(root, f), 'rb') as fh:
                h.update(f.encode() + b'\0' + fh.read())
    return h.hexdigest()


def _hrec(path):
    rows = []
    if os.path.exists(path):
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
    return rows


def _timeline(rows):
    """[[t_sim, state, None], ...] at each change of state in hrec."""
    out, last = [], None
    for r in rows:
        if r['state'] != last:
            out.append([round(float(r['t_sim']), 3), r['state'], None])
            last = r['state']
    return out


def digest(run_dir):
    """Return the per-run record, or None for a run with no mission log."""
    name = os.path.basename(run_dir.rstrip('/'))
    meta = _kv(os.path.join(run_dir, 'meta.txt'))
    log_path = os.path.join(run_dir, 'mission.log')
    if not os.path.exists(log_path):
        return None
    lines = open(log_path, errors='replace').read().splitlines()
    transitions, looks, travel = [], [], None
    found_seen = None
    for ln in lines:
        m = TRAVEL.search(ln)
        if m and travel is None:
            travel = json.loads(m.group(1).replace("'", '"'))
        m = TRANSITION.search(ln)
        if not m:
            continue
        prev, state, reason, detail = m.groups()
        transitions.append([prev, state, reason, detail or ''])
        if prev == 'SURVEY_REGION' and state == 'MARK_REGION_SEARCHED':
            mm = MISS.search(detail or '')
            looks.append({'region': mm.group(1), 'found': False,
                          'lines': int(mm.group(3)),
                          'seen': [] if mm.group(4) == 'nothing'
                          else mm.group(4).split(',')})
        if prev == 'SURVEY_REGION' and state == 'STOW_ARM':
            chose = [CHOSE.search(t[3]).group(1) for t in transitions
                     if t[0] == 'SELECT_SEARCH_REGION' and CHOSE.search(t[3])]
            looks.append({'region': chose[-1], 'found': True, 'lines': None,
                          'seen': None})
    for ln in lines:
        if 'search: mode=discover' in ln and 'discovered=bay_' in ln:
            found_seen = re.search(r'seen=([\w,-]+)', ln).group(1)
    for look in looks:
        if look['found']:
            look['seen'] = [] if found_seen in (None, '--') \
                else found_seen.split(',')
    final = _kv(os.path.join(run_dir, 'final_state.txt'))
    fs = open(os.path.join(run_dir, 'final_state.txt')).read() \
        if os.path.exists(os.path.join(run_dir, 'final_state.txt')) else ''
    state = (re.search(r'state=([A-Z_]+)', fs) or [None, None])[1]
    reason = (re.search(r' reason=([^ ]+)', fs) or [None, None])[1]
    result = (re.search(r' result=([^ \n]+)', fs) or [None, None])[1]
    del final
    rows = _hrec(os.path.join(run_dir, 'hrec.csv'))
    # The bag's timeline (p05_bagtimes.py: every transition, simulator
    # seconds from LOCALIZE) when there is one; hrec's 10 Hz samples
    # otherwise, which can miss a state shorter than 0.1 s.
    bt_path = os.path.join(run_dir, 'bag_timeline.json')
    if os.path.exists(bt_path):
        timeline = json.load(open(bt_path))['timeline']
        timeline_source = 'rosbag'
    else:
        timeline = _timeline(rows)
        timeline_source = 'hrec (10 Hz samples)'
    states = [t[1] for t in timeline]
    home_error = None
    if rows and state == 'COMPLETE':
        last = rows[-1]
        home_error = round(math.hypot(float(last['gt_x']) - HOME[0],
                                      float(last['gt_y']) - HOME[1]), 3)
    manifest = json.load(open(os.path.join(run_dir, 'manifest.json')))
    colour = manifest['requested_colour']
    truth = next(t['region_id'] for t in manifest['targets']
                 if t['colour'] == colour)
    runner = open(os.path.join(run_dir, 'runner.log'),
                  errors='replace').read()
    order_arg = meta.get('search_order', 'policy')
    lifted = None
    if 'VERIFY_GRASP' in states:
        lifted = any(p == 'VERIFY_GRASP' and s == 'DESCEND'
                     for p, s, _, _ in transitions)
    bag = os.path.join(run_dir, 'bag')
    sim_end = timeline[-1][0] if timeline_source == 'rosbag' and timeline \
        else (float(rows[-1]['t_sim']) if rows else None)
    return {
        'run': name, 'void': '.void-' in name,
        'commit': meta.get('head'), 'dirty_paths': meta.get('dirty_paths'),
        'level': meta.get('level'), 'seed': int(meta.get('seed', -1)),
        'colour': colour, 'told': {'target_colour': colour},
        'episode_id': manifest.get('episode_id'),
        'truth_region': truth, 'order_arg': order_arg,
        'looks': looks,
        'order': [k['region'] for k in looks],
        'discovered': next((k['region'] for k in looks if k['found']), None),
        'discovered_at': next((i + 1 for i, k in enumerate(looks)
                               if k['found']), None),
        'outcome': state or 'VOID', 'reason': reason, 'result': result,
        'lifted': lifted, 'home_error_m': home_error,
        'relocalisations': states.count('RELOCALIZE'),
        'recoveries': states.count('RECOVERY'),
        'sim_s': sim_end,
        'runner_checks_pass': 'FAIL ' not in runner and 'torn down; runner '
                              'checks PASS' in runner,
        'travel_logged': travel,
        'timeline': timeline, 'timeline_source': timeline_source,
        'bag_sha256': _sha_dir(bag) if os.path.isdir(bag) else None,
        'evidence_dir': run_dir,
    }


def _event_times(trace, timeline):
    """Simulator seconds for each trace event, from the FSM timeline."""
    entries = {}
    for t, state, _ in timeline:
        entries.setdefault(state, []).append(t)
    sel = list(entries.get('SELECT_SEARCH_REGION', []))
    survey_end = [t for i, (t, s, _) in enumerate(timeline)
                  if i and timeline[i - 1][1] == 'SURVEY_REGION'
                  and s in ('MARK_REGION_SEARCHED', 'STOW_ARM')]
    marks = list(entries.get('MARK_REGION_SEARCHED', []))
    out, k_sel, k_srv, k_mark = [], 0, 0, 0
    for e in range(trace.n_events):
        kind = rs.KINDS[trace.kind[e]]
        if kind == 'select' and k_sel < len(sel):
            out.append(sel[k_sel]); k_sel += 1
        elif kind == 'survey' and k_srv < len(survey_end):
            out.append(survey_end[k_srv]); k_srv += 1
        elif kind == 'mark' and k_mark < len(marks):
            out.append(marks[k_mark]); k_mark += 1
        elif kind == 'discover' and survey_end:
            out.append(survey_end[min(k_srv, len(survey_end)) - 1])
        else:
            out.append(timeline[-1][0] if timeline else math.nan)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('matrix_dir')
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args(argv)
    problem = build_search.arena_problem()
    os.makedirs(os.path.join(args.out, 'runs'), exist_ok=True)
    records = []
    for name in sorted(os.listdir(args.matrix_dir)):
        d = os.path.join(args.matrix_dir, name)
        if not os.path.isdir(d):
            continue
        rec = digest(d)
        if rec is None:
            continue
        if rec['travel_logged'] is not None and \
                rec['travel_logged'] != problem.travel:
            raise SystemExit(f'{name}: the mission logged a travel table '
                             f'that is not build_search.arena_problem()\'s')
        records.append(rec)
        with open(os.path.join(args.out, 'runs', f'{name}.json'), 'w') as f:
            f.write(json.dumps({k: v for k, v in rec.items()
                                if k != 'travel_logged'},
                               indent=1, sort_keys=True) + '\n')
    runs, hashes, ends = [], [], []
    for rec in records:
        if rec['void'] or not rec['looks']:
            continue
        given = () if rec['order_arg'] == 'policy' else tuple(
            problem.index(b) for b in rec['order_arg'].split(','))
        policy = 'expected_cost' if not given else 'given'
        tr = rs.replay_search(problem, policy,
                              [(k['region'], k['found'])
                               for k in rec['looks']], given)
        rid = re.sub(r'[^A-Za-z0-9_-]', '_', rec['run'])[:32]
        runs.append(sbm.SearchRun(
            rid, 'recorded', tr, _event_times(tr, rec['timeline']),
            [list(r) for r in rec['timeline']],
            {k: rec[k] for k in ('run', 'commit', 'level', 'seed', 'colour',
                                 'episode_id', 'order_arg', 'outcome',
                                 'reason', 'lifted', 'home_error_m',
                                 'relocalisations', 'recoveries',
                                 'runner_checks_pass', 'bag_sha256')}
            | {'observations': rec['looks']},
            {'truth_region': rec['truth_region'],
             'source': 'episode manifest (evaluator side)'}))
        if rec['bag_sha256']:
            hashes.append(rec['bag_sha256'])
        if rec['sim_s'] is not None:
            ends.append(rec['sim_s'])
    if runs:
        if len(hashes) != len(runs):
            raise SystemExit('every recorded run needs its rosbag')
        prov = bundle.make_provenance(
            'recorded-run', git=bundle.git_provenance(REPO),
            tool='docs/data/p05_evidence.py', rosbag={
                'sha256': hashlib.sha256('\n'.join(sorted(hashes)).encode())
                .hexdigest(),
                'sim_time_start': 0.0, 'sim_time_end': max(ends or [0.0])})
        prov['title'] = 'The real mission, searching in Gazebo (Phase 5 matrix)'
        sb = sbm.SearchBundle(prov, problem, runs)
        dst = os.path.join(args.out, 'replay', 'p05_matrix')
        digest_ = sbm.write_search_bundle(sb, dst, 'gzip')
        sbm.replay_check(sbm.load_search_bundle(dst))
        print('replay bundle', digest_, len(runs), 'runs')
    rows = [{k: r[k] for k in (
        'run', 'level', 'seed', 'colour', 'truth_region', 'order_arg',
        'order', 'discovered', 'discovered_at', 'outcome', 'reason',
        'lifted', 'home_error_m', 'relocalisations', 'recoveries',
        'sim_s', 'runner_checks_pass')} | {'group': r['run'][:1],
                                           'void': r['void'],
                                           'wall_s': None}
        for r in records]
    with open(os.path.join(args.out, 'results.json'), 'w') as f:
        f.write(json.dumps({
            'label': 'Phase 5 matrix: the searching mission in Gazebo, one '
                     'fresh simulator per run, never --fast (measured). '
                     'Told only the colour. 16 runs is not a rate.',
            'command': 'python3 docs/data/p05_evidence.py '
                       '~/coco_lab_runs/lab4/matrix',
            'rows': rows,
            'notes': [
                'Home error: ground truth at the end vs home (-2, 0), '
                'scoring only.',
                'Lift: VERIFY_GRASP passed (grasp_server lifted=1, which '
                'checks the object moved UP, not that it is upright).',
                'sim_s: simulator seconds from the recorder start to the '
                'last row.',
                'Void runs are listed and never scored.'],
        }, indent=1, sort_keys=True) + '\n')
    print('rows', len(rows))


if __name__ == '__main__':
    main()
