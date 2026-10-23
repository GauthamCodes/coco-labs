# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G1.8: the cases of the native-vs-Pyodide gate, run unchanged in both runtimes.

tools/g1/native_gate.mjs runs this file in CPython (a subprocess) and in Pyodide
(the built site's own coco_lab packs) and compares what each returns. It reads
the globals ``arena_json`` (worlds/coco_arena_v1.json), ``depot_json``
(worlds/coco_depot_v1.json), ``record_json`` (a played Fetch Rush record) and
``hash_version``, and leaves its result in ``result`` (JSON text).

The cases are M5's review requests (docs/v2/data/m5/review/browser-families-ac/:
the four-arm control and localisation Compare loops, goal (2.5, 2), 60 ticks;
the global planners, same goal and inflation) and a Fetch Rush session on the
Depot, every tick's state hash.
"""
import json

from coco_lab import games, numerics
from coco_lab.arena import Arena, InputEvent
from coco_lab.compare_loop import LoopComparison
from coco_lab.compare_planning import COMPARE_PLANNERS, run_planner
from coco_lab.costmap import build_layers, InflationParams, scan_obstacle_cells
from coco_lab.grid import Grid
from coco_lab.sketch import _nearest_free

INFLATION = {'inflation_radius': 0.5, 'cost_scaling_factor': 10, 'robot_radius': 0.25}
GOAL = [2.5, 2]
LOOPS = {'control': ['dwa', 'rpp', 'mppi', 'dwa'], 'localise': ['mcl', 'mcl_augmented', 'ekf', 'mcl']}


def loop_case(spec, family):
    c = LoopComparison(spec, {'family': family, 'names': LOOPS[family], 'goal': GOAL,
                              'inflation': INFLATION, 'steps': 60, 'hash_version': hash_version})
    return [c.advance() for _ in range(60)]


def planner_case(spec):
    """Every Compare planner on the costmap Compare builds (arena_glue.compare's own steps)."""
    a = Arena(spec, 1, hash_version=hash_version)
    m, li = a.lab_map, a.lidar
    params = InflationParams(**INFLATION)
    hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles, li.mount, li.range_min, li.range_max)
    layers = build_layers(m.width, m.height, m.resolution, [v != 0 for v in m.occupancy], hits, params)
    g = Grid(m.width, m.height, blocked=[v >= 253 for v in layers.combined],
             cost=layers.combined, connectivity=8)
    start = _nearest_free(g, m.cell_at(*a.pose[:2]))
    goal = _nearest_free(g, m.cell_at(*GOAL))
    out = {'costmap': list(layers.combined), 'start': start, 'goal': goal}
    for name in COMPARE_PLANNERS:
        events = []
        r = run_planner(g, start, goal, name, events.append)
        out[name] = {'status': r.status, 'path': [list(p) for p in r.path],
                     'summary': r.summary, 'events': [list(e) for e in events]}
    return out


def game_case(spec, record):
    """games.play's loop, keeping every tick's hash (the chain alone would hide where)."""
    a = Arena(spec, record['seed'], hash_version=hash_version)
    by = {}
    for e in record['inputs']:
        by.setdefault(e['tick'], []).append(InputEvent(**e))
    rules = games._rules(record['game'], record['arg'])
    hashes = []
    for _ in range(record['ticks']):
        t = a.step(by.get(a.tick, ()))
        if not rules.started:
            rules.start(a)
        rules.observe(a, t)
        hashes.append(t.state_hash)
    return {'tick_hashes': hashes, 'scorecard': games._card(rules, a)}


arena_spec = json.loads(arena_json)
with numerics.version(hash_version):   # the cases' out-of-step work too (G1.11: scoped)
    result = json.dumps({
        'hash_version': hash_version,
        'control': loop_case(arena_spec, 'control'),
        'localise': loop_case(arena_spec, 'localise'),
        'planners': planner_case(arena_spec),
        'fetch_rush': game_case(json.loads(depot_json), json.loads(record_json)),
    })
