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
Experiment C: D* Lite on two of Nav2's own global costmaps. No ROS.

  python3 -P docs/data/lab5/lab5_replan_c.py SNAPSHOT_RUN_DIR [--out docs/data/lab5]

``SNAPSHOT_RUN_DIR`` is a ``lab5_run.sh snapshot`` session: its
``costmap_before.json`` (the apron with nobody on it) and
``costmap_after.json`` (a person standing 2.2 m from the robot, on its
path). Both are cropped to the same window around the apron (``WINDOW``,
map frame) at their native resolution and turned into coco_lab's grid the
way Phase 1C turns every snapshot into one (``Snapshot.to_labmap``: 253 /
254 / 255 blocked, the raw cost of every other cell kept as the cost
layer), with Lab 1's default move model C0 (8-connected, no corner
cutting, cost weight 2, scale 252).

The robot's MAP is the before snapshot and the WORLD is the after one;
the update arrives after the first plan (``first_sense_step`` 1, global
sensing), as a costmap update would. coco_lab's ``run_replan`` drives the
episode -- D* Lite repairs, A* searches the after map from scratch, and
the two must agree on cost -- and writes it as a glass-box replan bundle
(``replan/arena_c/``), replayed before it is kept, plus ``replan_c.json``.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

from coco_lab import bundle as cb, movebundle as mb
from coco_lab.maps import FREE
from coco_lab.replan import ReplanWorld, run_replan
from coco_lab_ros.costmap import Snapshot

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
#: map-frame window (x0, x1, y0, y1): the apron and its walls, start to goal
WINDOW = (-2.0, 1.3, -8.2, 0.6)
START = (0.0, 0.0)
GOAL = (0.0, -7.5)


def load(path):
    d = json.load(open(path))
    s = Snapshot(width=d['width'], height=d['height'],
                 resolution=d['resolution'], origin=tuple(d['origin']),
                 frame_id=d['frame_id'], data=bytes(d['data']))
    if s.content_hash() != d['content_hash']:
        raise SystemExit(f'{path}: content hash does not match its data')
    return s, d


def crop(snap):
    """Return ``(width, height, blocked, cost, cell_of)`` of the window."""
    lm = snap.to_labmap('crop')
    (mx0, my0) = snap.world_to_cell(WINDOW[0], WINDOW[2])
    (mx1, my1) = snap.world_to_cell(WINDOW[1], WINDOW[3])
    r0, c0 = snap.to_lab(mx0, my1)          # top-left (max y)
    r1, c1 = snap.to_lab(mx1, my0)          # bottom-right
    w, h = c1 - c0 + 1, r1 - r0 + 1
    blocked, cost = [], []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            i = r * lm.width + c
            blocked.append(lm.occupancy[i] != FREE)
            cost.append(float(lm.cost[i]))

    def cell_of(x, y):
        rr, cc = snap.to_lab(*snap.world_to_cell(x, y))
        return (rr - r0, cc - c0)
    return w, h, blocked, cost, cell_of


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument('run_dir')
    ap.add_argument('--out', default=HERE)
    a = ap.parse_args()
    sb, db = load(os.path.join(a.run_dir, 'costmap_before.json'))
    sa, da = load(os.path.join(a.run_dir, 'costmap_after.json'))
    if (sb.width, sb.height, sb.resolution, sb.origin) != \
            (sa.width, sa.height, sa.resolution, sa.origin):
        raise SystemExit('the two snapshots are not the same grid')
    w, h, kb, cb_, cell_of = crop(sb)
    _, _, ka, ca, _ = crop(sa)
    start, goal = cell_of(*START), cell_of(*GOAL)
    world = ReplanWorld(w, h, kb, ka, start, goal, sense_radius=None,
                        connectivity=8, heuristic='octile', cost=cb_,
                        truth_cost=ca, first_sense_step=1)
    res = run_replan(world)
    try:
        git = {'commit': subprocess.run(
            ['git', '-C', REPO, 'rev-parse', 'HEAD'], capture_output=True,
            text=True, check=True).stdout.strip(), 'dirty': bool(
            [ln for ln in subprocess.run(
                ['git', '-C', REPO, 'status', '--porcelain'],
                capture_output=True, text=True).stdout.splitlines()
             if ln.strip() and not ln.endswith('AGENTS.md')])}
    except (OSError, subprocess.CalledProcessError):
        git = None
    prov = cb.make_provenance('glass-box', git=git,
                              tool='docs/data/lab5/lab5_replan_c.py')
    prov['title'] = ("Nav2's global costmap, before and after a person "
                     "stopped on the apron (Experiment C)")
    prov['inputs'] = {'before': db['content_hash'],
                      'after': da['content_hash'],
                      'window_map_frame': list(WINDOW),
                      'resolution_m': sb.resolution,
                      'move_model': 'C0 (coco_lab default)'}
    dst = os.path.join(a.out, 'replan', 'arena_c')
    digest = mb.write_replan_bundle(res, prov, dst, 'gzip')
    m = mb.replay_replan(dst)
    changed = sum(1 for x, y, p, q in zip(kb, ka, cb_, ca)
                  if x != y or p != q)
    out = {'schema': 'coco_lab.lab5_replan_c', 'version': '1.0',
           'run_dir': os.path.abspath(a.run_dir),
           'before': db['content_hash'], 'after': da['content_hash'],
           'window_map_frame': list(WINDOW), 'grid': [w, h],
           'resolution_m': sb.resolution, 'start_cell': list(start),
           'goal_cell': list(goal), 'cells_changed': changed,
           'newly_blocked': sum(1 for x, y in zip(kb, ka) if y and not x),
           'summary': m['summary'], 'rounds': m['rounds'],
           'bundle': 'replan/arena_c/', 'content_hash': digest,
           'bytes': sum(os.path.getsize(os.path.join(dst, f))
                        for f in os.listdir(dst)),
           'sha256_before_file': hashlib.sha256(open(os.path.join(
               a.run_dir, 'costmap_before.json'), 'rb').read()).hexdigest()}
    with open(os.path.join(a.out, 'replan_c.json'), 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: out[k] for k in ('grid', 'cells_changed',
                                          'newly_blocked', 'summary')}))
    for r in m['rounds']:
        print(f"round at step {r['step']}: changed {len(r['changed'])}, "
              f"cost {r['cost']}, D* {r['dstar_expansions']} "
              f"(re {r['dstar_reexpansions']}), A* {r['astar_expansions']} "
              f"cost {r['astar_cost']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
