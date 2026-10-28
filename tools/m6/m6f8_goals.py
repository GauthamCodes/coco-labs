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
M6F.8's Nav2 goals on the Depot, from the model (docs/v2/m6/M6F8_PLAN.md, run steps 3-4).

    m6f8_goals.py smoke OUT.json
    m6f8_goals.py ghost OUT.json [--mode phone] [--seed 1] [--rules 3|4|5]
    m6f8_goals.py colour OUT.json --colour red [--rules 2]

``smoke``: one goal per place the plan names, each a pose the model itself drives to --
the loading dock and the office block at their zone's roomiest free plan-grid cell (the
rounds' start rule, ``make_fetch_rush_rounds_r3.start_points``); high-bay aisles 1 and 3,
an office room, the workshop maze and the dock object at a Grasp Assist pre-grasp pose (the
shortest A* route from the level's start); the dispatch floor at its drop zone's centre;
then back to the level's start. Not the mezzanine deck (the 2D Nav2 map holds it as a
silhouette).

``ghost``: a Fetch Rush rules 3 round's driving legs (``games.round_for``): its start pose,
then per order the object's pre-grasp pose (the end of the round's own planned route to it,
``approach`` in the rounds file) and the drop zone's centre (the end of the route after it).
Grasping and dropping are not driven: the legs only.

``colour`` (G2, Fetch by colour on ``coco_depot_colours_v1``): the colour round's start (the start
pad), the chosen rod's pre-grasp pose (``pick`` in the rounds file, the end of the round's planned
route to it), then the drop zone's centre (Dispatch).

World and map frames coincide on the Depot (``world_to_map`` [0, 0]); every pose is (x, y,
yaw) in the map frame. Evidence class of the poses: MODEL (they are the model's).
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.join(REPO, 'tools', 'g1'))
from coco_lab import games, loc_arena, numerics  # noqa: E402,F401 -- loc_arena: the subsystem
import make_fetch_rush_rounds_r3 as r3  # noqa: E402

LEVEL = 'coco_depot_v1'


def smoke(a, spec):
    assist = a.subsystems['assist']
    starts = r3.start_points(a)
    sx, sy, sth = spec['start']['x'], spec['start']['y'], spec['start']['theta']
    out = []

    def obj(oid, label):
        best = None
        for p in assist.approach_poses(a, assist.objects[oid]):
            got = r3.path(a, (sx, sy), (p[0], p[1]))
            if got is not None and (best is None or got[0] < best[1]):
                best = (p, got[0])
        if best is None:
            raise SystemExit(f'{oid}: no reachable pre-grasp pose')
        out.append({'id': f'{oid}_pregrasp', 'label': label, 'zone_object': oid,
                    'pose': [round(best[0][0], 3), round(best[0][1], 3), round(best[0][2], 4)],
                    'model_plan_m_from_start': round(best[1], 2)})

    def zone(zid, label):
        x, y = starts[zid]
        out.append({'id': f'{zid}_open', 'label': label, 'zone': zid,
                    'pose': [round(x, 3), round(y, 3), 0.0]})

    zone('zone_loading_dock', 'loading dock (roomiest free cell)')
    obj('obj_dock', 'loading dock object')
    obj('obj_aisle_1', 'high-bay aisle 1')
    obj('obj_aisle_3', 'high-bay aisle 3')
    zone('zone_office', 'office block (roomiest free cell: the corridor)')
    obj('obj_office_ne', 'office room (north-east)')
    obj('obj_maze_1', 'workshop maze')
    x, y = r3.centre(a, 'dispatch_drop')
    out.append({'id': 'dispatch_drop_centre', 'label': 'dispatch floor', 'zone': 'dispatch_drop',
                'pose': [round(x, 3), round(y, 3), 0.0]})
    out.append({'id': 'level_start', 'label': 'back to the start',
                'pose': [sx, sy, sth]})
    return {'start': [sx, sy, sth], 'goals': out}


def ghost(a, mode, seed, rules=3):
    rnd = games.round_for(seed, rules=rules, mode=mode)
    doc = games.load_rounds(rules=rules)
    out, frm = [], rnd['region']
    for k, ((oid, drop), route) in enumerate(zip(rnd['orders'], rnd['routes'])):
        p = doc['approach'][frm][oid]
        out.append({'id': f'order{k + 1}_{oid}_pregrasp', 'label': f'order {k + 1}: to {oid}',
                    'pose': [round(p[0], 3), round(p[1], 3), round(p[2], 4)]})
        x, y = r3.centre(a, drop)
        out.append({'id': f'order{k + 1}_{drop}', 'label': f'order {k + 1}: to {drop}',
                    'pose': [round(x, 3), round(y, 3), 0.0], 'route_end': route[-1]})
        frm = drop
    return {'start': rnd['start'], 'mode': mode, 'seed': seed, 'rules': rules, 'region': rnd['region'],
            'orders': rnd['orders'], 'ghost_m': rnd['ghost_m'],
            'reference_time_s': rnd['reference_time_s'], 'goals': out}


def colour(a, colour_id, rules):
    with open(games.colour_rounds_file(rules=rules), encoding='utf-8') as f:
        doc = json.load(f)
    rnd = doc['rounds'][colour_id]
    (oid, drop), = rnd['orders']
    p = rnd['pick'][0]
    x, y = r3.centre(a, drop)
    goals = [{'id': f'order1_{oid}_pregrasp', 'label': f'order 1: to {oid}',
              'pose': [round(p[0], 3), round(p[1], 3), round(p[2], 4)]},
             {'id': f'order1_{drop}', 'label': f'order 1: to {drop}',
              'pose': [round(x, 3), round(y, 3), 0.0], 'route_end': rnd['routes'][-1][-1]}]
    return {'start': rnd['start'], 'game': 'fetch_colour', 'colour': colour_id, 'rules': rules,
            'region': rnd['region'], 'orders': rnd['orders'], 'ghost_m': rnd['ghost_m'],
            'reference_time_s': rnd['reference_time_s'], 'goals': goals}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('what', choices=('smoke', 'ghost', 'colour'))
    ap.add_argument('out')
    ap.add_argument('--mode', default='phone')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--rules', type=int, default=None, choices=(1, 2, 3, 4, 5),
                    help='the rounds file: Fetch Rush 3 (default), 4 (G2.1), 5 (G2 rules 5); '
                         'Fetch by colour 1 or 2 (default: the current rules)')
    ap.add_argument('--colour', choices=games.FETCH_COLOURS, help='colour: the rod to fetch')
    o = ap.parse_args()
    level = games.FETCH_COLOUR_LEVEL if o.what == 'colour' else LEVEL
    spec = json.load(open(os.path.join(REPO, 'worlds', f'{level}.json')))
    a = r3.arena(spec)
    if o.what == 'smoke':
        doc = smoke(a, spec)
    elif o.what == 'ghost':
        doc = ghost(a, o.mode, o.seed, o.rules or 3)
    else:
        if not o.colour:
            ap.error('colour needs --colour')
        doc = colour(a, o.colour, o.rules or games.FETCH_COLOUR_RULES)
    doc.update({'level': level, 'frame': 'map', 'world_to_map': spec['world_to_map'],
                'made_by': 'tools/m6/m6f8_goals.py ' + o.what})
    with open(o.out, 'w') as f:
        json.dump(doc, f, indent=1)
        f.write('\n')
    for g in doc['goals']:
        print(g['id'], g['pose'])
    return 0


if __name__ == '__main__':
    with numerics.version(r3.HV):
        code = main()
    sys.exit(code)
