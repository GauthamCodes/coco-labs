# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Race submissions for the reproducibility check (M4.8), covering every star count.

For each race level:

- ``ghost``: the ghost's own drive (two stars, by construction);
- ``ghost_late_start``: the same, begun 50 ticks late (the clock starts at the first
  input: the same time);
- ``slow``: pure pursuit, closed loop, at 70 % of the teleop speed (one star);
- ``straighter``: pure pursuit along A*'s path string-pulled (waypoints skipped wherever
  the straight line stays on free cells of the Arena's own planning grid): a shorter
  line than the grid path, which beats the ghost (three stars). It shows three stars
  can be earned, and why: a grid planner's path is not the shortest in the plane;
- ``open_loop_slow``: the ghost's commands at 80 %, replayed blind: it drifts into walls
  (valid False);
- ``cut_halfway``: the ghost's drive stopped halfway (valid False).

Each is scored here in CPython; then by the page (tools/perf/play_verify.mjs score),
re-opened as a link in Chromium, Firefox and WebKit (reproduce), and re-scored by
coco verify.

    PYTHONPATH=coco_lab python3 docs/v2/data/m4/m48/make_race_submissions.py OUT.json
"""

import json
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))

from coco_lab import play, race  # noqa: E402
from coco_lab.arena import InputEvent  # noqa: E402


def closed_loop(spec, lv, path, vscale=1.0):
    """Pure pursuit (coco_lab.race.pursue) along ``path`` at ``vscale`` of the teleop speed."""
    path = race.densify(path)
    a = race._arena(spec, lv)
    lim = dict(a.limits, teleop_linear=a.limits['teleop_linear'] * vscale)
    gx, gy = lv['goal']
    log, last, done = [], None, 0
    for k in range(int(lv['max_ticks'])):
        if math.hypot(gx - a.pose[0], gy - a.pose[1]) <= lv['finish_m']:
            break
        v, w, done = race.pursue(a.pose, path, lim, done)
        cmd = (race._q(v), race._q(w))
        rows = []
        if cmd != last:
            rows = [{'tick': k, 'kind': 'teleop', 'linear': cmd[0], 'angular': cmd[1]}]
            last = cmd
            log.extend(rows)
        a.step([InputEvent(**r) for r in rows])
    return log


def string_pulled(spec, lv):
    """A*'s path with every waypoint skipped that a straight line on free cells can skip."""
    a = race._arena(spec, lv)

    def clear(p, q):
        n = max(2, int(math.hypot(q[0] - p[0], q[1] - p[1]) / 0.02))
        for i in range(n + 1):
            c = a.plan_map.cell_at(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n)
            if c is None or a.grid.is_blocked(c):
                return False
        return True
    pts = race.densify(race.ghost_path(spec, lv))
    out, i = [pts[0]], 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not clear(pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out


def main(out):
    with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    with open(os.path.join(REPO, 'lab_web', 'play', 'levels.json'), encoding='utf-8') as f:
        levels = json.load(f)
    subs = []
    for lv in levels['challenges']['race-the-ghost']['levels']:
        bare = {k: v for k, v in lv.items() if k not in ('reference', 'ghost_track')}
        ghost = race.ghost_inputs(spec, bare)
        variants = {
            'ghost': ghost,
            'ghost_late_start': [dict(r, tick=r['tick'] + 50) for r in ghost],
            'slow': closed_loop(spec, bare, race.ghost_path(spec, bare), 0.7),
            'straighter': closed_loop(spec, bare, string_pulled(spec, bare)),
            'open_loop_slow': [dict(r, linear=round(r['linear'] * 0.8, 2), angular=round(r['angular'] * 0.8, 2))
                               for r in ghost],
            'cut_halfway': ghost[: len(ghost) // 2] + [{'tick': ghost[len(ghost) // 2]['tick'], 'kind': 'stop'}],
        }
        for name, log in variants.items():
            s = {'v': 1, 'challenge': 'race-the-ghost', 'level': lv['id'],
                 'level_hash': play.level_hash(lv), 'inputs': log}
            r = play.score(levels, s, spec)
            subs.append({'name': f"{lv['id']}/{name}", **s, 'cpython': {
                'valid': r['valid'], 'stars': r['stars'], 'hash': r['hash'],
                'metrics': {m['name']: m['value'] for m in r['metrics']}}})
            print(f"{lv['id']}/{name}: valid {r['valid']} stars {r['stars']} "
                  f"{ {m['name']: m['value'] for m in r['metrics']} }")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'what': 'race-the-ghost submissions (M4.8), every star count: scored in CPython here',
                   'submissions': subs}, f, indent=1)
        f.write('\n')


if __name__ == '__main__':
    main(sys.argv[1])
