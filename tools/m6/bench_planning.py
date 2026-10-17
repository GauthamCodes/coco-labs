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
Time every global planner across the Depot (M6F.4; README §7 M6 "Planning").

    bench_planning.py --spec worlds/coco_depot_v1.yaml --out RESULT.json
        [--repeats 5] [--write-json tools/m6/out/coco_depot_v1.json]

The same :func:`run` runs in Pyodide-in-Node (``bench_planning_pyodide.mjs``
loads this file and coco_lab into Pyodide). What is timed is the reference
search the Arena runs (``coco_lab.search.search`` with ``arena.PLANNERS``) on the
Arena's plan grid (the map inflated by the robot's radius, 8-connected), from a
fixed start to a fixed goal, for each representative pair. Grid building is timed
separately. Cold = the first search of that planner and pair in the process;
warm = the median of ``repeats`` more.

The budget (stated, not measured): **300 ms warm per plan** in Pyodide-in-Node,
the interactive-play budget the M6F prompt names; M2's "goal after a planner
change" budget (median <= 100 ms, max <= 500 ms, ADR 0004) is reported beside it.
A planner over budget goes to the WebAssembly gate (README invariant 9) as an
ADR; nothing is ported here.

Standard library only in :func:`run` (Pyodide); the CLI uses PyYAML.
"""

import json
import os
import platform
import statistics
import sys
import time

#: (name, start (x, y), goal (x, y)), world = map frame on the Depot
PAIRS = [
    ('start_to_dock', (23.0, 6.0), (46.5, 6.5)),
    ('start_to_office_sw', (23.0, 6.0), (2.5, 23.0)),
    ('start_to_maze_dead_end', (23.0, 6.0), (11.0, 3.3)),
    ('start_to_mezzanine_deck', (23.0, 6.0), (42.0, 29.5)),
    ('dock_to_office_ne', (46.5, 6.5), (10.0, 29.0)),
    ('aisle_1_to_aisle_3', (20.0, 17.6), (28.5, 26.0)),
    ('maze_entrance_to_dead_end', (14.6, 3.0), (13.0, 17.3)),
]
BUDGET_WARM_MS = 300.0


def run(spec, repeats=5, pairs=PAIRS, planners=None, resolution=None):
    """Return the timings: grid build, then each planner on each pair."""
    from coco_lab import worldgen
    from coco_lab.arena import Arena, PLANNERS
    from coco_lab.search import search
    from coco_lab.sketch import _nearest_free

    clock = time.perf_counter
    s = worldgen.with_resolution(spec, resolution)
    t0 = clock()
    arena = Arena(s, seed=1)
    build_ms = (clock() - t0) * 1000
    g = arena.grid
    out = {'spec_id': s['id'], 'resolution': s['arena']['resolution'],
           'grid': [arena.plan_map.width, arena.plan_map.height],
           'arena_build_ms': build_ms, 'repeats': repeats, 'results': []}
    for name, start, goal in pairs:
        sc = _nearest_free(g, arena.plan_map.cell_at(*start))
        gc = _nearest_free(g, arena.plan_map.cell_at(*goal))
        for planner in planners or list(PLANNERS):
            times = []
            for _ in range(repeats + 1):
                t0 = clock()
                res = search(g, sc, gc, **PLANNERS[planner])
                times.append((clock() - t0) * 1000)
            warm = times[1:]
            out['results'].append({
                'pair': name, 'planner': planner, 'found': res.found,
                'expanded': len(res.expanded),
                'path_m': None if res.cost is None else res.cost * arena.plan_map.resolution,
                'cold_ms': times[0], 'warm_median_ms': statistics.median(warm),
                'warm_max_ms': max(warm), 'over_budget': statistics.median(warm) > BUDGET_WARM_MS})
    return out


def _profile():
    import subprocess
    try:
        return subprocess.run(['powerprofilesctl', 'get'], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def conditions():
    """Return the machine state a CPython run was taken in."""
    def read(path):
        try:
            with open(path, encoding='utf-8') as f:
                return f.read().strip()
        except OSError:
            return None
    procs = []
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            cmd = read(f'/proc/{pid}/cmdline')
            if cmd:
                procs.append(cmd.replace('\x00', ' '))
    return {
        'load_average': os.getloadavg(),
        'ac_online': read('/sys/class/power_supply/ACAD/online'),
        'power_profile': _profile(),
        'cpu': next((ln.split(':', 1)[1].strip() for ln in (read('/proc/cpuinfo') or '')
                     .splitlines() if ln.startswith('model name')), None),
        'nproc': os.cpu_count(), 'python': sys.version.split()[0],
        'platform': platform.platform(), 'nice': os.nice(0),
        'codex_running': any('codex' in p and 'resume' in p for p in procs),
        'perf_servers_running': sum('serve_dist.mjs' in p for p in procs),
        'gazebo_or_ros_running': any(k in p for p in procs
                                     for k in ('gz sim', 'gzserver', 'ros2 launch')),
    }


def main(argv=None):
    import argparse
    import yaml
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--write-json')
    a = ap.parse_args(argv)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                                    'coco_lab'))
    with open(a.spec, encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    if a.write_json:
        with open(a.write_json, 'w', encoding='utf-8') as f:
            json.dump(spec, f)
    before = conditions()
    result = run(spec, a.repeats)
    result.update(engine='cpython', conditions_before=before, conditions_after=conditions(),
                  budget_warm_ms=BUDGET_WARM_MS)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    for r in result['results']:
        print(f"{r['pair']:28s} {r['planner']:15s} found={r['found']!s:5s} "
              f"exp={r['expanded']:7d} cold={r['cold_ms']:8.1f} warm={r['warm_median_ms']:8.1f}")


if __name__ == '__main__':
    main()
