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
Phase 6's evidence: the matrix's runs, as bundles and one results file.

  python3 -P docs/data/lab5/lab5_evidence.py MATRIX_DIR [--out docs/data/lab5]

Needs ``coco_lab`` importable; no ROS (it reads each run's ``run.json``,
written by ``lab5_extract.py``, and the runner's JSON files). Writes:

``drive/<scenario>/``
    One drive bundle 1.0 per scenario (``coco_lab.movebundle``): the frozen
    path, the arena's boxes in the map frame, and every valid run of every
    controller. Each run's four metrics are computed by
    ``coco_lab.movemetrics`` from the bundle's own arrays and the bundle is
    REPLAYED (``replay_drive``) before it is kept. The first valid run of
    each controller also carries its candidate rollouts, thinned for the
    browser (at most 1 frame per second, 24 candidates per frame -- the
    best always kept -- and 12 points per candidate).
``results.json``
    Per scenario and controller: outcomes, and for each metric the
    distribution over runs (n, min, median, max); the actor-visibility and
    injection checks; every run's row. Numbers are copied from the bundles'
    replayed metrics, never typed.

Run directories without ``run.json`` (VOID attempts, ``*.void-K``) are
listed under ``void`` with their reason and are never in a statistic.

Two SUPPLEMENTARY facts per run, outside the metric definitions and
labelled so: DWB control cycles in which it scored candidates and rejected
every one (``all_rejected``: n > 0, none valid -- run 15's "0 of 819") are
counted apart from cycles with nothing to score (``empty``: n = 0); and
``actor_contact_whole_recording`` repeats the actor-clearance computation
over the WHOLE recording, not just the FollowPath window -- a robot that
stopped and aborted can still be walked into afterwards by a kinematic
actor that does not stop.
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys

from coco_lab import bundle as cb
from coco_lab import movebundle as mb
from coco_lab import movemetrics as mm

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
WORLD = os.path.join(REPO, 'gazebo_models', 'config', 'navigation_world.json')
SCENARIOS = ('static_room', 'crossing', 'oncoming', 'mislocalised')
CONTROLLERS = ('DWB', 'MPPI', 'RPP')
MARGIN_S = 1.0          # context kept around the window, display only


def sha_file(path):
    """Return the sha256 of a file, or None."""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def thin_points(pts, k=12):
    """Keep at most ``k`` points, first and last included, evenly by index."""
    if len(pts) <= k:
        return pts
    idx = sorted({round(i * (len(pts) - 1) / (k - 1)) for i in range(k)})
    return [pts[i] for i in idx]


def thin_rollouts(frames, hz=1.0, per=24):
    """Thin rollout frames for the browser (module doc)."""
    out, next_t = [], -math.inf
    for fr in frames:
        if fr['t'] < next_t:
            continue
        next_t = fr['t'] + 1.0 / hz
        cands = fr['candidates']
        best = [c for c in cands if c['best']]
        rest = [c for c in cands if not c['best']]
        step = max(1, math.ceil(len(rest) / max(1, per - len(best))))
        keep = best + rest[::step]
        out.append({'t': fr['t'], 'n': fr['n'], 'n_valid': fr['n_valid'],
                    'candidates': [dict(c, pts=thin_points(c['pts']))
                                   for c in keep]})
    return out


def in_span(rows, t0, t1):
    return [r for r in rows if t0 - MARGIN_S <= r[0] <= t1 + MARGIN_S]


def load_run(d):
    """Return ``(run.json dict, extras)`` for a run directory."""
    run = json.load(open(os.path.join(d, 'run.json')))
    extras = {}
    for name in ('actor_seen.json', 'inject.json', 'checks.json',
                 'params_readback.json'):
        p = os.path.join(d, name)
        if os.path.exists(p):
            extras[name] = json.load(open(p))
    extras['bag_sha256'] = sha_file(os.path.join(d, 'bag', 'bag_0.mcap'))
    return run, extras


def bundle_run(name, run, extras, k, rollouts):
    """Return one drive-bundle run dict from a run.json."""
    t0, t1 = run['window']
    res = run['result'] or {}
    seen = extras.get('actor_seen.json')
    inj = extras.get('inject.json')
    record = {
        'run': name, 'run_id': run['meta'].get('run_id'),
        'lab_source': run['meta'].get('lab_source'),
        'started_utc': run['meta'].get('started_utc'),
        'loadavg_start': run['meta'].get('loadavg_start'),
        'runner_checks_pass': run['meta'].get('runner_checks_failed') is False,
        'error_code': res.get('error_code'),
        'bag_sha256': extras['bag_sha256'],
        'heavy': run.get('heavy'),
        'path_sha256': run.get('path_sha256'),
        'belief_at_start': run.get('belief_at_start'),
        'watch_violations': (extras.get('checks.json') or {}).get(
            'violation_count'),
        'actor_seen': None if not seen else {
            k2: seen[k2] for k2 in ('scans_in_range', 'hits', 'misses',
                                    'abs_error_m', 'within_m', 'tol_m')},
        'inject': inj,
        'actor_whole': whole_recording_actor_clearance(run),
    }
    out = {
        'id': f'{run["meta"]["controller"]}_{k}',
        'controller': run['meta']['controller'],
        'outcome': run['outcome'], 'window': [t0, t1], 'record': record,
        'gt': in_span(run['gt'], t0, t1), 'amcl': in_span(run['amcl'], t0, t1),
        'cmd': in_span(run['cmd_nav'], t0, t1),
        'wheel': in_span(run['cmd_wheel'], t0, t1),
        'actors': {a: in_span(tr, t0, t1) for a, tr in run['actors'].items()},
        'chosen': [[c[0], c[2]] for c in run['chosen'][::5]
                   if t0 - MARGIN_S <= c[0] <= t1 + MARGIN_S],
        'eval': [[e[0], e[1], e[2]] for e in run['eval']],
        'monitor': [list(m) for m in run['monitor']],
        'actor_trigger': run['actor_trigger'],
    }
    if rollouts:
        out['rollouts'] = thin_rollouts(
            [fr for fr in run['rollouts']
             if t0 - MARGIN_S <= fr['t'] <= t1 + MARGIN_S])
    return out


def git_info():
    try:
        c = subprocess.run(['git', '-C', REPO, 'rev-parse', 'HEAD'],
                           capture_output=True, text=True, check=True)
        s = subprocess.run(['git', '-C', REPO, 'status', '--porcelain'],
                           capture_output=True, text=True, check=True)
        return {'commit': c.stdout.strip(),
                'dirty': any(ln.strip() and not ln.endswith('AGENTS.md')
                             for ln in s.stdout.splitlines())}
    except (OSError, subprocess.CalledProcessError):
        return None


def dist(vals):
    return mm.distribution([v for v in vals if v is not None])


def whole_recording_actor_clearance(run):
    """
    Actor clearance over the whole recording (supplementary).

    Also, for a contact, the FIRST ground-truth sample at clearance 0, the
    wheel command (``/diff_drive_controller/cmd_vel``) in force then, and
    the robot's largest distance from the path's line x = 0 before it.
    """
    if not run['actors']:
        return None
    acts = [{'radius': 0.15, 'track': [(r[0], r[1], r[2]) for r in tr]}
            for tr in run['actors'].values()]
    gt = [tuple(g) for g in run['gt']]
    c = mm.clearance(gt, [], acts)['actor']
    out = {'min_m': c['min_m'], 't': c['t'],
           'after_window': None if c['t'] is None
           else c['t'] > run['window'][1],
           'first_contact_t': None, 'wheel_v_at_contact': None}
    if c['min_m'] == 0.0:
        for g in gt:
            if mm.clearance([g], [], acts)['actor']['min_m'] == 0.0:
                out['first_contact_t'] = g[0]
                w = [v for v in run['cmd_wheel'] if v[0] <= g[0]]
                out['wheel_v_at_contact'] = w[-1][1] if w else None
                break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument('matrix')
    ap.add_argument('--out', default=HERE)
    a = ap.parse_args()
    world = json.load(open(WORLD))
    boxes = [list(b) for b in mm.boxes_in_map(world['boxes'],
                                              world['world_to_map'])]
    git = git_info()
    results = {'schema': 'coco_lab.lab5_results', 'version': '1.0',
               'matrix': os.path.abspath(a.matrix), 'git': git,
               'scenarios': {}, 'void': []}
    names = sorted(os.listdir(a.matrix))
    for n in names:
        d = os.path.join(a.matrix, n)
        if os.path.isdir(d) and not os.path.exists(os.path.join(d,
                                                                 'run.json')):
            meta = os.path.join(d, 'meta.json')
            reason = json.load(open(meta)).get('void_reason') \
                if os.path.exists(meta) else 'no meta.json'
            results['void'].append({'run': n, 'reason': reason})
    for sc in SCENARIOS:
        runs, rows, scenario = [], [], None
        for ctrl in CONTROLLERS:
            k = 0
            for n in names:
                if not (n.startswith(f'{sc}_{ctrl}_') and '.void' not in n):
                    continue
                d = os.path.join(a.matrix, n)
                if not os.path.exists(os.path.join(d, 'run.json')):
                    continue
                run, extras = load_run(d)
                if run['outcome'] not in mb.OUTCOMES or None in run['window']:
                    results['void'].append({'run': n, 'reason':
                                            f'no window ({run["outcome"]})'})
                    continue
                k += 1
                if scenario is None:
                    sd = run['meta']['scenario_def']
                    scenario = {
                        'id': sc, 'title': sd['title'], 'path': run['path'],
                        'path_sha256': run['path_sha256'],
                        'start': sd['start'], 'goal': sd['goal'],
                        'boxes': boxes, 'actor_radius': 0.15,
                        'actors_spec': sd.get('actors', []),
                        'inject': sd.get('inject')}
                elif run['path_sha256'] != scenario['path_sha256']:
                    raise SystemExit(f'{n}: a different path; refusing to '
                                     f'compare it')
                runs.append(bundle_run(n, run, extras, k, rollouts=(k == 1)))
        if not runs:
            results['scenarios'][sc] = {'status': 'not yet measured'}
            continue
        hashes = sorted(r['record']['bag_sha256'] or '' for r in runs)
        prov = cb.make_provenance(
            'recorded-run', git=git, tool='docs/data/lab5/lab5_evidence.py',
            rosbag={'sha256': hashlib.sha256('\n'.join(hashes).encode())
                    .hexdigest(), 'sim_time_start': min(
                        r['window'][0] for r in runs),
                    'sim_time_end': max(r['window'][1] for r in runs)})
        dst = os.path.join(a.out, 'drive', sc)
        digest = mb.write_drive_bundle(scenario, runs, prov, dst, 'gzip')
        m = mb.replay_drive(dst)
        size = sum(os.path.getsize(os.path.join(dst, f))
                   for f in os.listdir(dst))
        per = {}
        for b in m['runs']:
            per.setdefault(b['controller'], []).append(b)
        block = {'status': 'measured', 'bundle': f'drive/{sc}/',
                 'content_hash': digest, 'bytes': size,
                 'path_sha256': scenario['path_sha256'],
                 'title': scenario['title'], 'controllers': {}}
        for ctrl in CONTROLLERS:
            bs = per.get(ctrl, [])
            ok = [b for b in bs if b['outcome'] == 'succeeded']
            met = [b['metrics'] for b in bs]
            block['controllers'][ctrl] = {
                'runs': len(bs),
                'outcomes': {o: sum(1 for b in bs if b['outcome'] == o)
                             for o in sorted({b['outcome'] for b in bs})},
                'error_codes': sorted({b['record']['error_code'] for b in bs
                                       if b['record']['error_code']}),
                'tracking_mean_m': dist([x['tracking_m']['mean'] for x in met]),
                'tracking_max_m': dist([x['tracking_m']['max'] for x in met]),
                'time_s_succeeded': dist([b['metrics']['time_s'] for b in ok]),
                'rms_linear_accel': dist([x['smoothness']['rms_linear_accel']
                                          for x in met]),
                'rms_angular_accel': dist([x['smoothness']['rms_angular_accel']
                                           for x in met]),
                'min_clearance_m': dist([x['clearance']['min_m'] for x in met]),
                'min_clearance_static_m': dist(
                    [x['clearance']['static']['min_m'] for x in met]),
                'min_clearance_actor_m': dist(
                    [x['clearance']['actor']['min_m'] for x in met]),
                'contacts': sum(1 for x in met if x['clearance']['contact']),
                'dwb_all_rejected_cycles': [
                    sum(1 for e in r['eval'] if e[1] > 0 and e[2] == 0)
                    for r in runs if r['controller'] == ctrl]
                if ctrl == 'DWB' else None,
                'dwb_empty_cycles': [
                    sum(1 for e in r['eval'] if e[1] == 0)
                    for r in runs if r['controller'] == ctrl]
                if ctrl == 'DWB' else None,
                'actor_contacts_whole_recording': sum(
                    1 for r in runs if r['controller'] == ctrl
                    and (r['record'].get('actor_whole') or {}).get('min_m')
                    == 0.0),
                'actor_contacts_while_wheels_stopped': sum(
                    1 for r in runs if r['controller'] == ctrl
                    and (r['record'].get('actor_whole') or {}).get(
                        'wheel_v_at_contact') == 0.0),
                'max_lateral_m': dist([max(
                    (abs(g[1] - r['gt'][0][1]) for g in r['gt']
                     if r['window'][0] <= g[0] <= r['window'][1]),
                    default=None) for r in runs if r['controller'] == ctrl])
                if sc in ('crossing', 'oncoming') else None,
            }
        for b in m['runs']:
            r = next(x for x in runs if x['id'] == b['id'])
            rows.append({'run': b['record']['run'], 'id': b['id'],
                         'controller': b['controller'],
                         'outcome': b['outcome'],
                         'error_code': b['record']['error_code'],
                         'metrics': b['metrics'],
                         'actor_seen': b['record']['actor_seen'],
                         'inject': b['record']['inject'],
                         'runner_checks_pass':
                             b['record']['runner_checks_pass'],
                         'eval_cycles': len(r['eval']),
                         'eval_all_rejected': sum(1 for e in r['eval']
                                                  if e[1] > 0 and e[2] == 0),
                         'eval_empty': sum(1 for e in r['eval']
                                           if e[1] == 0),
                         'actor_whole_recording':
                             r['record'].get('actor_whole')})
        block['rows'] = rows
        results['scenarios'][sc] = block
        print(f'{sc}: {len(runs)} runs, bundle {digest[:19]}… {size} B')
    with open(os.path.join(a.out, 'results.json'), 'w') as f:
        json.dump(results, f, indent=1, sort_keys=True, allow_nan=False)
        f.write('\n')
    print('void', len(results['void']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
