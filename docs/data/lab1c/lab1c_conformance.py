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
Phase 1C conformance: coco_lab vs SmacPlanner2D vs NavFn, one snapshot.

Run by ``lab1c_run.sh conformance`` against a live, stationary stack.
The design is ``docs/labs/PHASE_1C_PLAN.md`` §D and §E.1, fixed before
this ran; the interpretations below were written into SESSION_LOG 1C-3
BEFORE the run:

- **S0** is the first ``costmap_raw`` whose hash repeats ``--settle``
  times in a row. Every request is bracketed by the latest costmap hash;
  a pair is VOID if any differs from S0. Nothing is ever mixed.
- **Candidates** are the cells of S0 with raw cost <= 252, in Nav2 index
  order (``my * width + mx``). Pairs are drawn with
  ``random.Random(seed)``: ``start = rng.choice``, ``goal = rng.choice``.
  A pair whose cell centres are under ``--min-sep`` (2.0 m) apart is
  resampled; those are counted (``separation_rejects``) and are NOT
  draws. A draw is one pair meeting the separation rule; at most
  ``--cap`` (100) draws.
- A pair is **valid** when it is not void and coco_lab C1 finds a path.
  C1-unreachable pairs go to ``no_path`` (Smac and NavFn are still asked;
  they should fail too). The run stops at ``--valid`` (50) valid pairs or
  the cap; fewer than 50 at the cap is failure F-5, reported as such.
- Start and goal are sent as the cell CENTRES, yaw 0, ``use_start``.
- **Two passes** (amended at 1C-3, BEFORE the Gazebo run, from the static
  dry run): NavFn's ``clearRobotCell`` writes FREE_SPACE into the SHARED
  global costmap at its start cell (``navfn_planner.cpp`` @1.3.11
  :241-242, :519-524), and the write persists. Asking all three planners
  per pair would therefore void every later pair. So:

  1. **Smac pass.** Per draw: Smac (GridBased) with its
     ``unsmoothed_plan``, bracketed by the costmap hash, which must equal
     S0 (else VOID); coco_lab C1 Dijkstra, C1 A* (euclidean) and C0
     Dijkstra on S0.
  2. **NavFn pass.** On the same valid pairs, in order: NavFn
     (``use_astar: false``) then NavFnAStar (``true``). After each request
     the costmap's cell-level difference from S0 is recorded; the NavFn
     half is accepted only if every changed cell is a start cell of a
     NavFn request so far, now 0. Anything else is reported as such.

  Metrics per ``coco_lab_ros.metrics``, always evaluated on S0. Planning
  times are recorded, never compared.
- The **M3 analogue** (not one of the pairs): spawn (map (0, 0)) to the
  approved goal G* (world (0.5, 6.0) = map (2.5, 6.0)), same metrics.

Only raw measurements are written here; ``lab1c_report.py`` derives the
distributions from the JSON.
"""

import argparse
import datetime
import gzip
import hashlib
import json
import math
import os
import random
import sys
import threading
import time

from coco_lab_ros import metrics as M
from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.nav2_client import Nav2Probe
from coco_lab_ros.pathing import cells_from_poses, path_poses
from coco_lab_ros.planning import Planner
import rclpy
from rclpy.executors import MultiThreadedExecutor

PLANNERS = ('GridBased', 'NavFn', 'NavFnAStar')
LAB = (('C1_dijkstra', 'dijkstra', 'zero', 'C1'),
       ('C1_astar', 'astar', 'euclidean', 'C1'),
       ('C0_dijkstra', 'dijkstra', 'zero', 'C0'))


def path_metrics(points, snap, goal_cell):
    """L, I, c_max, enters_blocked, end cell and goal distance of a path."""
    if not points:
        return None
    i = M.integrated_cost(points, snap)
    gx, gy = snap.cell_centre(*goal_cell)
    end = points[-1]
    return {'L': M.path_length(points), 'I': i['I'], 'c_max': i['c_max'],
            'enters_blocked': i['enters_blocked'], 'poses': len(points),
            'end_goal_dist': math.hypot(end[0] - gx, end[1] - gy)}


def lab_result(planner, name, algo, h, cfg, s, g):
    p = planner.plan_cells(s, g, algo, h, cfg)
    out = {'status': p.result.status, 'plan_s': p.plan_seconds,
           'expansions': p.result.trace.summary['expansions']}
    if p.found:
        cells = p.cells_nav2()
        pts = [q[:2] for q in path_poses(cells, planner.snapshot, 0.0)]
        out.update({'E': p.result.cost, 'cells': len(cells),
                    'endpoint_ok': cells[-1] == tuple(g)})
        out.update(path_metrics(pts, planner.snapshot, g))
    return out


def smac_raw(raw, snap, grid, s, g):
    if not raw:
        return {'captured': False}
    cells, residual = cells_from_poses(raw, snap, 'corner')
    e, why = M.edge_sum(M.lab_cells_of(cells, snap), grid)
    out = {'captured': True, 'corner_residual_cells': residual,
           'cells': len(cells), 'start_ok': cells[0] == tuple(s),
           'endpoint_ok': cells[-1] == tuple(g), 'E': e,
           'E_undefined_reason': why, 'end_cell': list(cells[-1])}
    out.update(path_metrics(raw, snap, g))
    return out


def ask(probe, snap, s, g, h0, planners=PLANNERS):
    """Ask Nav2 planners; bracket each call with the costmap hash."""
    out, hashes = {}, []
    start = snap.cell_centre(*s) + (0.0,)
    goal = snap.cell_centre(*g) + (0.0,)
    for pid in planners:
        hashes.append(probe.latest_costmap()[1])
        r = probe.compute(pid, start, goal)
        hashes.append(probe.latest_costmap()[1])
        pts = [q[:2] for q in r['poses']]
        rec = {'ok': r['ok'], 'error_code': r['error_code'],
               'error_msg': r['error_msg'],
               'planning_time_s': r['planning_time'], 'wall_s': r['wall'],
               'raw_messages': r.get('raw_messages', 0)}
        if pts:
            rec.update(path_metrics(pts, snap, g))
        out[pid] = (rec, r['raw'])
    void = any(h != h0 for h in hashes)
    return out, void, hashes


def diff_from(snap, msg):
    """Return ``[[mx, my, s0_value, now_value]]`` of every changed cell."""
    now = bytes(bytearray(msg.data))
    w = snap.width
    return [[i % w, i // w, a, b]
            for i, (a, b) in enumerate(zip(snap.data, now)) if a != b]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=20260929)
    ap.add_argument('--valid', type=int, default=50)
    ap.add_argument('--cap', type=int, default=100)
    ap.add_argument('--min-sep', type=float, default=2.0)
    ap.add_argument('--settle', type=int, default=2)
    ap.add_argument('--g-star', nargs=2, type=float, default=[2.5, 6.0],
                    help='the M3 analogue goal, MAP frame')
    ap.add_argument('--spawn', nargs=2, type=float, default=[0.0, 0.0])
    ap.add_argument('--meta', default=None, help='runner provenance JSON')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rclpy.init()
    probe = Nav2Probe(name='lab1c_conformance_probe')
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(probe)
    spin = threading.Thread(target=ex.spin, daemon=True)
    spin.start()
    log = open(os.path.join(a.out, 'conformance.log'), 'a')

    def say(*x):
        line = ' '.join(str(v) for v in x)
        print(line, flush=True)
        log.write(line + '\n')
        log.flush()

    doc = {'schema': 'coco_lab.lab1c.conformance/1',
           'started_utc': datetime.datetime.now(datetime.timezone.utc)
           .strftime('%Y-%m-%dT%H:%M:%SZ'),
           'args': vars(a), 'meta': None, 'pairs': [], 'no_path': [],
           'void': [], 'draws': 0, 'separation_rejects': 0}
    if a.meta:
        with open(a.meta) as f:
            doc['meta'] = json.load(f)
    try:
        if not probe.wait_for_planner(120.0):
            raise SystemExit('compute_path_to_pose never appeared')
        msg, h0 = probe.wait_settled(repeats=a.settle, timeout=180.0)
        if msg is None:
            raise SystemExit('costmap_raw never settled')
        snap = Snapshot.from_msg(msg, probe.costmap_topic)
        say('S0', h0, snap.width, snap.height, snap.resolution, snap.origin)
        doc['S0'] = snap.describe()
        with open(os.path.join(a.out, 'S0_costmap_raw.bin.gz'), 'wb') as f:
            f.write(gzip.compress(snap.data, mtime=0))
        doc['S0']['data_gz_sha256'] = hashlib.sha256(
            gzip.compress(snap.data, mtime=0)).hexdigest()
        deadline = time.monotonic() + 20
        while probe.raw_subscribed() < 1 and time.monotonic() < deadline:
            time.sleep(0.1)
        doc['unsmoothed_plan_publishers'] = probe.raw_subscribed()

        planner = Planner(snap)
        c1 = planner.grid('C1')
        cands = [(mx, my) for my in range(snap.height)
                 for mx in range(snap.width) if snap.cost(mx, my) <= 252]
        doc['candidates'] = len(cands)
        rng = random.Random(a.seed)
        valid = 0
        while valid < a.valid and doc['draws'] < a.cap:
            s, g = rng.choice(cands), rng.choice(cands)
            sx, sy = snap.cell_centre(*s)
            gx, gy = snap.cell_centre(*g)
            if math.hypot(gx - sx, gy - sy) < a.min_sep:
                doc['separation_rejects'] += 1
                continue
            doc['draws'] += 1
            idx = doc['draws']
            nav, void, hashes = ask(probe, snap, s, g, h0, ('GridBased',))
            rec = {'draw': idx, 'start_cell': list(s), 'goal_cell': list(g),
                   'start_world': [sx, sy], 'goal_world': [gx, gy],
                   'hashes_equal_S0': not void}
            if void:
                rec['hashes'] = hashes
                doc['void'].append(rec)
                say('draw', idx, 'VOID')
                continue
            rec['nav2'] = {pid: r for pid, (r, _) in nav.items()}
            rec['smac_raw'] = smac_raw(nav['GridBased'][1], snap, c1, s, g)
            rec['lab'] = {n: lab_result(planner, n, al, h, cfg, s, g)
                          for n, al, h, cfg in LAB}
            if rec['lab']['C1_dijkstra']['status'] != 'found':
                doc['no_path'].append(rec)
                say('draw', idx, 'no C1 path; smac ok =',
                    rec['nav2']['GridBased']['ok'])
                continue
            valid += 1
            doc['pairs'].append(rec)
            say('draw', idx, 'valid', valid, 'E_c1',
                round(rec['lab']['C1_dijkstra']['E'], 6), 'E_smac_raw',
                rec['smac_raw'].get('E'))

        # The M3 analogue, Smac pass: spawn -> G*, map frame.
        ms = snap.world_to_cell(*a.spawn)
        mg = snap.world_to_cell(*a.g_star)
        nav, void, hashes = ask(probe, snap, ms, mg, h0, ('GridBased',))
        m3 = {'start_world': a.spawn, 'goal_world': a.g_star,
              'start_cell': list(ms), 'goal_cell': list(mg),
              'hashes_equal_S0': not void, 'smac_hashes': hashes,
              'nav2': {pid: r for pid, (r, _) in nav.items()},
              'smac_raw': smac_raw(nav['GridBased'][1], snap, c1, ms, mg),
              'start_cost': snap.cost(*ms), 'goal_cost': snap.cost(*mg)}
        try:
            m3['lab'] = {n: lab_result(planner, n, al, h, cfg, ms, mg)
                         for n, al, h, cfg in LAB}
        except Exception as exc:  # noqa: B902 -- recorded, not hidden
            m3['lab_error'] = repr(exc)
        doc['m3_analogue'] = m3
        say('m3 analogue smac', 'void' if void else 'ok')

        # NavFn pass: the same pairs, then the M3 analogue.
        cleared = set()
        unexplained_total = 0
        for rec in doc['pairs'] + [m3]:
            s, g = tuple(rec['start_cell']), tuple(rec['goal_cell'])
            nav, _, hashes = ask(probe, snap, s, g, h0,
                                 ('NavFn', 'NavFnAStar'))
            cleared.add(s)
            time.sleep(0.5)          # let one more costmap publish land
            msg, _, _ = probe.wait_costmap(5.0, probe.latest_costmap()[2])
            if msg is None:
                msg = probe.latest_costmap()[0]
            diff = diff_from(snap, msg)
            unexplained = [d for d in diff
                           if (d[0], d[1]) not in cleared or d[3] != 0]
            unexplained_total += len(unexplained)
            for pid, (r, _) in nav.items():
                rec['nav2'][pid] = r
            rec['navfn_pass'] = {
                'hashes': hashes, 'cells_changed_from_S0': len(diff),
                'changed': diff[:50], 'unexplained': unexplained[:50],
                'unexplained_count': len(unexplained),
                'accepted': not unexplained}
        doc['navfn_cleared_start_cells'] = len(cleared)
        doc['navfn_unexplained_changes'] = unexplained_total
        say('navfn pass done; unexplained changes', unexplained_total)
        doc['valid'] = valid
        doc['f5_shortfall'] = valid < a.valid
        doc['final_costmap_hash'] = probe.latest_costmap()[1]
    finally:
        doc['ended_utc'] = datetime.datetime.now(datetime.timezone.utc) \
            .strftime('%Y-%m-%dT%H:%M:%SZ')
        with open(os.path.join(a.out, 'conformance.json'), 'w') as f:
            json.dump(doc, f, sort_keys=True, indent=1)
        say('wrote', os.path.join(a.out, 'conformance.json'),
            'valid', doc.get('valid'), 'draws', doc['draws'],
            'void', len(doc['void']), 'no_path', len(doc['no_path']))
        ex.shutdown()
        spin.join(timeout=10)       # never destroy under a spinning executor
        probe.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
