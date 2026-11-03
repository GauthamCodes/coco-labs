#!/usr/bin/env python3
"""
R1.5: generate COCO-Bench v0 (draft) -- four frozen benchmark suites.

Each suite is written once to coco_lab/coco_lab/benchmarks/<id>.v0.json and never
regenerated (a later suite is a new version): a fixed scenario list, a fixed metric
set, and the text saying what it tests. Run with --check to confirm the committed
suites are what this generator produces (they must be: the generator is
deterministic, hash version 3).

    python tools/r1/make_suites.py [--check]
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'coco_lab'))
os.environ.setdefault('COCO_WORLDS', str(REPO / 'worlds'))

from coco_lab import experiments as ex  # noqa: E402
from coco_lab import numerics  # noqa: E402
from coco_lab.arena import PLANNERS  # noqa: E402
from coco_lab.costmap import InflationParams  # noqa: E402
from coco_lab.exp_families import COSTMAPS  # noqa: E402
from coco_lab.exp_scenarios import sample_pairs  # noqa: E402
from coco_lab.search import search  # noqa: E402
from coco_lab.sketch import _nearest_free  # noqa: E402

OUT = REPO / 'coco_lab' / 'coco_lab' / 'benchmarks'
TOOL = 'tools/r1/make_suites.py'
NAV_METRICS = {f: [m['id'] for m in ex.METRICS[f]] for f in ('planning', 'control', 'localisation')}


def nav_suite(sid, title, tests, world_id, families, n, seed, min_sep, stratify='none'):
    w = ex.world(world_id)
    got = sample_pairs(w, n, seed, min_sep, 0.35, None, stratify, True)
    return {'schema': 'coco.bench.suite.v0', 'id': sid, 'version': 0, 'title': title, 'tests': tests,
            'world': world_id, 'world_sha256': ex.world_sha256(world_id), 'families': families,
            'metrics': {f: NAV_METRICS[f] for f in families},
            'generator': {'tool': TOOL, 'kind': 'sampled', 'n': n, 'seed': seed,
                          'min_separation_m': min_sep, 'min_clearance_m': 0.35,
                          'stratify': stratify, 'require_reachable': True,
                          'rejected_unreachable': got['rejected_unreachable'],
                          'rejected_separation': got['rejected_separation']},
            'scenarios': got['scenarios']}


def narrow_suite():
    world_id = 'coco_depot_v1'
    w = ex.world(world_id)
    seed, pool_n, need, min_in = 3001, 600, 15, 5.0
    cands = sample_pairs(w, pool_n, seed, 4.0, 0.35, None, 'none', True)['scenarios']
    picked = {'zone_workshop': [], 'zone_high_bay': []}
    with numerics.version(3):
        ip = InflationParams()
        _, grid = COSTMAPS.get(w, ip, 8, 2.0)
        m = w.lab_map
        for s in cands:
            if all(len(v) >= need for v in picked.values()):
                break
            a = _nearest_free(grid, m.cell_at(*s['start'][:2]))
            b = _nearest_free(grid, m.cell_at(*s['goal'][:2]))
            r = search(grid, a, b, **PLANNERS['astar'])
            if not r.found:
                continue
            for z in picked:
                rr = w.regions[z]
                n_in = sum(1 for c in r.path
                           if rr[0] <= m.cell_centre(c[0], c[1])[0] <= rr[1]
                           and rr[2] <= m.cell_centre(c[0], c[1])[1] <= rr[3])
                length = n_in * m.resolution
                through = s['start_zone'] != z and s['goal_zone'] != z
                ok = length >= min_in and (through if z == 'zone_high_bay' else True)
                if ok and len(picked[z]) < need and not any(s is p for v in picked.values() for p in v):
                    picked[z].append(dict(s, passes=z, in_zone_m=round(length, 3)))
                    break
    scen = []
    for z in ('zone_workshop', 'zone_high_bay'):
        if len(picked[z]) < need:
            raise SystemExit(f'only {len(picked[z])} {z} pairs in {pool_n} candidates')
        scen += picked[z]
    for i, s in enumerate(scen):
        s['id'] = f'n{i + 1:03d}'
    return {'schema': 'coco.bench.suite.v0', 'id': 'depot-narrow-30', 'version': 0,
            'title': 'Depot: the workshop maze and the rack aisles',
            'tests': ('Planning and control where the Depot is tight. 15 pairs whose reference A* '
                      'path (default costmap: inflation 0.5 m, scaling 10, robot radius 0.25 m) runs '
                      'at least 5 m inside the workshop maze (a dead-end corner of the Depot: one end '
                      'is in the maze, so the route must thread it), and 15 whose reference path '
                      'crosses at least 5 m of the high-bay rack aisles with both ends outside them. '
                      'Pairs come in draw order from a seeded pool of 600 (seed 3001, separation '
                      '>= 4 m); "passes" and "in_zone_m" record why each was chosen.'),
            'world': world_id, 'world_sha256': ex.world_sha256(world_id),
            'families': ['planning', 'control'],
            'metrics': {f: NAV_METRICS[f] for f in ('planning', 'control')},
            'generator': {'tool': TOOL, 'kind': 'filtered', 'pool': pool_n, 'seed': seed,
                          'min_separation_m': 4.0, 'min_clearance_m': 0.35, 'min_in_zone_m': min_in,
                          'reference': 'astar on the default static costmap'},
            'scenarios': scen}


def colour_suite():
    spec = {'game': 'fetch_colour', 'colours': list(ex.FETCH_COLOURS)}
    return {'schema': 'coco.bench.suite.v0', 'id': 'colour-fetch-4', 'version': 0,
            'title': 'Fetch by colour: the four rods',
            'tests': ('The full task on the Depot with colour rods: the reference bot (planner + '
                      'waypoint driver + Grasp Assist) fetches each rod (red 20 mm, green 24 mm, blue '
                      '28 mm, yellow 32 mm) and delivers it to Dispatch, driven by each global planner. '
                      'Grasp Assist\'s approach planning stays A*, as in Play. Fetch by colour rules 2 '
                      '(actors yield). Gazebo + Nav2 recordings of the same four rounds exist (STACK '
                      'ghosts g2_colour_<colour>).'),
            'world': 'coco_depot_colours_v1', 'world_sha256': ex.world_sha256('coco_depot_colours_v1'),
            'families': ['fulltask'], 'metrics': {'fulltask': [m['id'] for m in ex.METRICS['fulltask']]},
            'generator': {'tool': TOOL, 'kind': 'rounds', 'rules': ex.FETCH_COLOUR_RULES},
            'scenarios_spec': spec, 'scenarios': ex._rounds(dict(spec, kind='rounds')),
            'stack': {c: f'lab_web/public/stack/ghosts/g2_colour_{c}.json' for c in ex.FETCH_COLOURS}}


def build():
    return [
        nav_suite('arena-nav-50', 'Proving Ground: 50 start/goal pairs',
                  'Navigation on the original COCO arena (the Proving Ground, 0.05 m cells): 50 '
                  'seeded start/goal pairs in free space (clearance > 0.35 m, at least 3 m apart, '
                  'connected on the planning grid). The reference world for every existing STACK '
                  'recording.', 'coco_arena_v1', ['planning', 'control', 'localisation'], 50, 5001, 3.0),
        nav_suite('depot-nav-100', 'Depot: 100 pairs across its six zones',
                  'Navigation across the COCO Depot (0.1 m cells): 100 seeded pairs stratified by '
                  'the START\'s zone over the six region zones (17, 17, 17, 17, 16, 16 in spec order: '
                  'loading dock, high bay, mezzanine, office, workshop, forklift lanes), goals in any '
                  'zone, at least 5 m apart, connected on the planning grid.',
                  'coco_depot_v1', ['planning', 'control', 'localisation'], 100, 1001, 5.0, 'zone'),
        narrow_suite(),
        colour_suite(),
    ]


def text(s):
    return json.dumps(s, indent=1, sort_keys=True) + '\n'


if __name__ == '__main__':
    suites = build()
    check = '--check' in sys.argv
    bad = 0
    for s in suites:
        p = OUT / f'{s["id"]}.v0.json'
        if check:
            same = p.exists() and p.read_text() == text(s)
            bad += not same
            print(s['id'], 'unchanged' if same else 'DIFFERS')
        elif p.exists():
            print(s['id'], 'exists: a suite is never rewritten (make a new version)')
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            p.write_text(text(s))
            print('wrote', p, len(s['scenarios']), 'scenarios')
    sys.exit(1 if bad else 0)
