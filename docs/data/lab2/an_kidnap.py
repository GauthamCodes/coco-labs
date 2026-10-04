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
The real-stack kidnap A/B: AMCL recovery_alpha off (as shipped) vs on.

Reads ``lab2_run.sh kidnap`` sessions (``ROOT/kidnap_<arm>_<target>/``):
every ``/amcl_pose`` the probe logged after the teleport, against the
truth. **Recovered** means AMCL's pose came within ``OK_XY`` (0.5 m) and
``OK_YAW`` (0.3 rad) of the truth and stayed there for ``HOLD_S`` (5.0 s)
of sim time -- the Sketch summaries' definition (``coco_lab.localise``,
0.5 m / 0.3 rad), held by time here because AMCL's update rate is not
fixed. ``recovery_s`` is from the teleport to the start of that window.

A session that did not run its trial is VOID and counted separately: its
``meta.json`` has a ``void_reason``, or its runner checks failed, or the
probe logged no kidnap. VOID is not a failure to recover.

Usage::

    python3 docs/data/lab2/an_kidnap.py ROOT --out docs/data/lab2/kidnap_ab.json
"""

import argparse
import glob
import json
import math
import os
import sys

OK_XY = 0.5
OK_YAW = 0.3
HOLD_S = 5.0
ARMS = {'shipped': (0.0, 0.0), 'recovery': (0.001, 0.1)}


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def trial(path):
    meta = json.load(open(os.path.join(path, 'meta.json')))
    rows_path = os.path.join(path, 'kidnap.jsonl')
    rows = [json.loads(line) for line in open(rows_path)] \
        if os.path.exists(rows_path) else []
    tel = [r for r in rows if r['kind'] == 'teleport']
    void = meta.get('void_reason')
    if not void and meta.get('runner_checks_failed'):
        void = 'a runner check failed (see runner.log)'
    if not void and not tel:
        void = 'no kidnap logged'
    out = {'session': os.path.basename(path), 'arm': meta['arm'],
           'target': meta['target'], 'to_map': meta['kidnap_to_map'],
           'source': meta.get('source_copy_of') or meta.get('git_commit'),
           'started_utc': meta.get('started_utc'), 'void': void,
           'recovered': None, 'recovery_s': None, 't': [], 'err_xy': [],
           'err_yaw': [], 'amcl_updates': None}
    if void:
        return out
    tk = tel[0]['t']
    after = [r for r in rows if r['kind'] == 'kidnap' and r['phase'] in
             ('after', 'end')]
    pts = []
    for r in after:
        a, g = r['amcl'], r['truth']
        pts.append((r['t'] - tk, math.hypot(a[1] - g[1], a[2] - g[2]),
                    abs(wrap(a[3] - g[3]))))
    ok = [e < OK_XY and y < OK_YAW for _, e, y in pts]
    rec = None
    for i in range(len(pts)):
        if not ok[i]:
            continue
        j = i
        while j + 1 < len(pts) and ok[j + 1]:
            j += 1
        if pts[j][0] - pts[i][0] >= HOLD_S:
            rec = pts[i][0]
            break
    out.update(recovered=rec is not None, recovery_s=rec,
               t=[round(p[0], 2) for p in pts],
               err_xy=[round(p[1], 3) for p in pts],
               err_yaw=[round(p[2], 3) for p in pts],
               amcl_updates=after[-1]['amcl_n'] - after[0]['amcl_n']
               if after else 0,
               duration_s=round(pts[-1][0], 1) if pts else None)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('root')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    paths = sorted(p for p in glob.glob(os.path.join(args.root, 'kidnap_*'))
                   if os.path.isdir(p) and os.path.exists(
                       os.path.join(p, 'meta.json')))
    trials = [trial(p) for p in paths]
    arms = {}
    for arm, (a_slow, a_fast) in ARMS.items():
        ts = [t for t in trials if t['arm'] == arm]
        valid = [t for t in ts if not t['void']]
        arms[arm] = {'alpha_slow': a_slow, 'alpha_fast': a_fast,
                     'n': len(valid),
                     'recovered': sum(1 for t in valid if t['recovered']),
                     'void': len(ts) - len(valid),
                     'recovery_s': sorted(t['recovery_s'] for t in valid
                                          if t['recovered'])}
    result = {
        'tool': 'docs/data/lab2/an_kidnap.py',
        'command': 'python3 docs/data/lab2/an_kidnap.py '
                   f'{os.path.basename(os.path.normpath(args.root))} --out '
                   'docs/data/lab2/kidnap_ab.json',
        'cite': 'docs/RESULTS.md "COCO Lab Phase 3"; '
                'docs/data/lab2/kidnap_ab.json',
        'definition': (
            'Fresh simulator per trial (full_world_robo traverse:=true + '
            'lab_stack with the mission parameters merged with '
            'nav2_loc_<arm>.yaml). AMCL localised at the spawn, then the '
            'robot was teleported (gz set_pose) to one of five targets and '
            'rotated in place at 0.5 rad/s for 180 s of sim time through '
            '/cmd_vel_teleop. Recovered: within 0.5 m and 0.3 rad of the '
            'truth for 5 s of sim time.'),
        'ok_xy': OK_XY, 'ok_yaw': OK_YAW, 'hold_s': HOLD_S,
        'arms': arms, 'trials': trials,
    }
    with open(args.out, 'w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
    for arm, a in arms.items():
        print(f"{arm:9s} recovered {a['recovered']} of {a['n']} "
              f"(void {a['void']}) times {a['recovery_s']}")
    for t in trials:
        print(f"  {t['session']:24s} void={t['void']} recovered="
              f"{t['recovered']} t={t['recovery_s']} updates="
              f"{t['amcl_updates']} final_err="
              f"{t['err_xy'][-1] if t['err_xy'] else None}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
