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
Write worlds/coco_depot_v1.yaml, the COCO Depot (M6F.3; docs/v2/m6/DEPOT_DESIGN.md).

The Depot is authored here, as a layout, because three parts of it are better
computed than typed: the workshop maze (a seeded recursive backtracker on a 2 m
grid, plus a few extra openings so planners have choices), the actors' phases
(searched so that no two actors' collision bodies ever overlap), and the robot
block (copied from worlds/coco_arena_v2.yaml so the two cannot drift). Every
other number is the level's design, written once below; the robot and gripper
numbers are never typed here (Grasp Assist reads them from coco_lab).

    worlds/tools/make_coco_depot_v1.py [--check] [--variant colours]

``--check`` exits 1 if the committed YAML differs from what this writes.

``--variant colours`` (owner request, 2026-10-24: "multiple rods like in the beginning") writes
worlds/coco_depot_colours_v1.yaml instead: the Depot exactly as above plus a row of four rods --
the catalog's four Stack targets (red 20 mm, green 24 mm, blue 28 mm, yellow 32 mm; 0.158 m)
-- 1 m apart north of COCO's start, red to yellow in the Stack's order. It is a new level with
its own id; the Depot's YAML, its JSON and every hash made on it are untouched (a test checks).
"""

import argparse
import math
import os
import random
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
WORLDS = os.path.dirname(HERE)
REPO = os.path.dirname(WORLDS)
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
OUT = os.path.join(WORLDS, 'coco_depot_v1.yaml')
#: --variant colours: the level id, and its four rods (id, catalog item, world xy). The row
#: stands on the dispatch floor 2 m north of start_pad (23, 6): south of the forklift lane
#: (y >= 10) and the aisle walker's lane (x 24.2, y >= 8.5), clear of bad_too_wide (19, 7.5).
#: Red to yellow west to east, as the Stack's bays run red to yellow (coco_config TARGETS).
COLOURS_ID = 'coco_depot_colours_v1'
COLOUR_RODS = [('rod_red', 'can_small', (20.0, 8.0)), ('rod_green', 'bottle_steel', (21.0, 8.0)),
               ('rod_blue', 'canister', (22.0, 8.0)), ('rod_yellow', 'can_large', (23.0, 8.0))]
VARIANTS = {'': ('coco_depot_v1', OUT),
            'colours': (COLOURS_ID, os.path.join(WORLDS, f'{COLOURS_ID}.yaml'))}

W, H = 48.0, 32.0                  # the hall, x 0..48, y 0..32 (world frame)
OUTER_T, OUTER_H = 0.3, 6.0        # outer walls
INNER_T, OFFICE_H = 0.15, 3.0      # office partitions
MAZE_T, MAZE_H = 0.15, 2.0         # workshop maze walls
MAZE_CELL, MAZE_COLS, MAZE_ROWS = 2.0, 7, 9    # x 0..14, y 0..18
MAZE_SEED, MAZE_LOOPS = 20261017, 5
DOOR = 0.9                         # office doors
WIDE_DOOR = 1.2                    # maze and office entrances
#: the COCO arena's bay ramp (worlds/coco_arena_v2.yaml elevation: run 2, rise
#: 2 tan 18 deg, width 2.5): the one grade the Stack has climbed
RAMP_RUN, RAMP_RISE, RAMP_WIDTH = 2.0, 0.649839392466, 2.5
RACK_DEPTH, RACK_H, AISLE = 1.1, 6.0, 2.4
RACK_SHELVES = [0.25, 1.75, 3.25, 4.75]


def r(v):
    """Round a derived coordinate to the millimetre the YAML keeps."""
    return round(v, 3) + 0.0


def wall(i, a, b, t, h):
    return {'id': i, 'kind': 'wall', 'from': [r(a[0]), r(a[1])], 'to': [r(b[0]), r(b[1])],
            'thickness': t, 'height': h}


def door(i, w, at, width):
    return {'id': i, 'kind': 'door', 'wall': w, 'at': r(at), 'width': width}


# -- the workshop maze ----------------------------------------------------------------

def maze_walls():
    """Carve the maze; return its internal wall runs and its dead-end cells."""
    rng = random.Random(MAZE_SEED)
    cols, rows = MAZE_COLS, MAZE_ROWS
    # walls between cells: v[(c, r)] = wall on the east side of cell (c, r);
    # h[(c, r)] = wall on the north side of cell (c, r)
    v = {(c, rr): True for c in range(cols - 1) for rr in range(rows)}
    hz = {(c, rr): True for c in range(cols) for rr in range(rows - 1)}
    seen, stack = {(0, 0)}, [(0, 0)]
    while stack:
        c, rr = stack[-1]
        nbrs = [(c + dc, rr + dr) for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= c + dc < cols and 0 <= rr + dr < rows and (c + dc, rr + dr) not in seen]
        if not nbrs:
            stack.pop()
            continue
        nc, nr = rng.choice(nbrs)
        if nr == rr:
            v[(min(c, nc), rr)] = False
        else:
            hz[(c, min(rr, nr))] = False
        seen.add((nc, nr))
        stack.append((nc, nr))
    # a few loops: open extra walls, so A*, Dijkstra and greedy can disagree
    closed = sorted([('v',) + k for k, on in v.items() if on] +
                    [('h',) + k for k, on in hz.items() if on])
    for kind, c, rr in rng.sample(closed, MAZE_LOOPS):
        (v if kind == 'v' else hz)[(c, rr)] = False

    def degree(c, rr):
        n = 0
        n += c + 1 < cols and not v[(c, rr)]
        n += c > 0 and not v[(c - 1, rr)]
        n += rr + 1 < rows and not hz[(c, rr)]
        n += rr > 0 and not hz[(c, rr - 1)]
        return n
    dead = [(c, rr) for c in range(cols) for rr in range(rows) if degree(c, rr) == 1]
    runs = []
    # vertical runs: the line x = (c + 1) * cell, merged along y
    for c in range(cols - 1):
        rr = 0
        while rr < rows:
            if v[(c, rr)]:
                r0 = rr
                while rr < rows and v[(c, rr)]:
                    rr += 1
                runs.append(((c + 1) * MAZE_CELL, r0 * MAZE_CELL, (c + 1) * MAZE_CELL,
                             rr * MAZE_CELL))
            else:
                rr += 1
    for rr in range(rows - 1):
        c = 0
        while c < cols:
            if hz[(c, rr)]:
                c0 = c
                while c < cols and hz[(c, rr)]:
                    c += 1
                runs.append((c0 * MAZE_CELL, (rr + 1) * MAZE_CELL, c * MAZE_CELL,
                             (rr + 1) * MAZE_CELL))
            else:
                c += 1
    return runs, dead, v, hz


# -- the level ---------------------------------------------------------------------------

def catalog():
    # Dimensions and masses are the level's design (props at COCO's scale). The
    # graspable ones repeat the Stack's four verified targets exactly
    # (coco_config.robot.TARGETS: diameters 20/24/28/32 mm, height TARGET_HEIGHT
    # 0.158 m, mass TARGET_MASS 0.05 kg); the others are built to fail one check.
    def cyl(i, label, d, h, magnetic, colour, mass, notes):
        return {'id': i, 'label': label, 'shape': 'cylinder', 'diameter': d, 'height': h,
                'magnetic': magnetic, 'colour': colour, 'mass': mass, 'notes': notes}
    return [
        cyl('can_small', 'Small can', 0.020, 0.158, True, 'red', 0.05,
            'the Stack red target: 20 mm, 0.158 m, magnetic'),
        cyl('bottle_steel', 'Steel bottle', 0.024, 0.158, True, 'green', 0.05,
            'the Stack green target: 24 mm'),
        cyl('canister', 'Magnetic canister', 0.028, 0.158, True, 'blue', 0.05,
            'the Stack blue target: 28 mm'),
        cyl('can_large', 'Large can', 0.032, 0.158, True, 'yellow', 0.05,
            'the Stack yellow target: 32 mm, the widest the Stack has picked'),
        cyl('paint_tin', 'Paint tin', 0.090, 0.158, True, 'silver', 0.4,
            'too wide for the fingers'),
        cyl('plastic_bottle', 'Plastic bottle', 0.024, 0.158, False, 'white', 0.03,
            'right size, not magnetic: the magnet does the holding'),
        cyl('low_tin', 'Low tin', 0.028, 0.060, True, 'orange', 0.03,
            "its grasp band sits below the arm's reach envelope"),
        {'id': 'crate', 'label': 'Crate', 'shape': 'box', 'size': [0.4, 0.3, 0.3],
         'magnetic': False, 'colour': 'brown', 'mass': 2.0,
         'notes': 'too wide and not magnetic'},
    ]


def build():
    with open(os.path.join(WORLDS, 'coco_arena_v2.yaml'), encoding='utf-8') as f:
        arena = yaml.safe_load(f)
    kit = []
    # -- the hall
    kit += [wall('hall_south', (0, 0), (W, 0), OUTER_T, OUTER_H),
            wall('hall_north', (0, H), (W, H), OUTER_T, OUTER_H),
            wall('hall_west', (0, 0), (0, H), OUTER_T, OUTER_H),
            wall('hall_east', (W, 0), (W, H), OUTER_T, OUTER_H)]
    # -- zone 5: the workshop maze, x 0..14, y 0..18
    kit += [wall('workshop_east', (14, 0), (14, 18), MAZE_T, MAZE_H),
            door('workshop_door_south', 'workshop_east', 3.0, WIDE_DOOR),
            door('workshop_door_north', 'workshop_east', 15.0, WIDE_DOOR),
            wall('workshop_north', (0, 18), (14, 18), MAZE_T, MAZE_H),
            door('workshop_door_office', 'workshop_north', 7.0, WIDE_DOOR)]
    runs, dead, _, _ = maze_walls()
    for k, (x0, y0, x1, y1) in enumerate(runs):
        kit.append(wall(f'maze_{k:02d}', (x0, y0), (x1, y1), MAZE_T, MAZE_H))
    # -- zone 4: the office block, x 0..14, y 20..32
    kit += [wall('office_south', (0, 20), (14, 20), INNER_T, OFFICE_H),
            wall('office_east', (14, 20), (14, H), INNER_T, OFFICE_H),
            door('office_entrance', 'office_east', 6.5, WIDE_DOOR),
            wall('corridor_south', (0, 25.5), (14, 25.5), INNER_T, OFFICE_H),
            door('door_room_sw', 'corridor_south', 3.5, DOOR),
            door('door_room_se', 'corridor_south', 10.5, DOOR),
            wall('corridor_north', (0, 27.5), (14, 27.5), INNER_T, OFFICE_H),
            door('door_room_nw', 'corridor_north', 3.5, DOOR),
            door('door_room_ne', 'corridor_north', 10.5, DOOR),
            wall('rooms_south_divider', (7, 20), (7, 25.5), INNER_T, OFFICE_H),
            wall('rooms_north_divider', (7, 27.5), (7, H), INNER_T, OFFICE_H),
            {'id': 'desk_sw', 'kind': 'bench', 'center': [2.0, 21.0], 'size': [1.4, 0.7],
             'height': 0.75},
            {'id': 'desk_se', 'kind': 'bench', 'center': [12.0, 21.0], 'size': [1.4, 0.7],
             'height': 0.75},
            {'id': 'desk_ne', 'kind': 'bench', 'center': [12.0, 31.0], 'size': [1.4, 0.7],
             'height': 0.75}]
    # -- zone 2: the high-bay aisles, x 16..31.4, y 15..28.8: six rack rows, each split
    # by a transverse gap (x 23..25.4); back-to-back pairs share no aisle
    rows = [('A', 15.0, ['+y']), ('B', 18.5, ['-y']), ('C', 19.6, ['+y']),
            ('D', 23.1, ['-y']), ('E', 24.2, ['+y']), ('F', 27.7, ['-y'])]
    for name, y0, sides in rows:
        for k, (x0, x1) in enumerate(((16.0, 23.0), (25.4, 31.4)), start=1):
            kit.append({'id': f'rack_{name}{k}', 'kind': 'rack',
                        'center': [r((x0 + x1) / 2), r(y0 + RACK_DEPTH / 2)],
                        'size': [r(x1 - x0), RACK_DEPTH], 'height': RACK_H,
                        'shelves': RACK_SHELVES, 'aisle': AISLE, 'aisles': sides})
    # -- zone 3: the mezzanine and its ramp, x 34..47.7, y 24..31.7
    deck_x0, deck_x1, deck_y0, deck_y1 = 36.0, 47.7, 24.0, 31.7
    ramp_y = 27.85
    kit += [{'id': 'mezzanine_ramp', 'kind': 'ramp', 'foot': [deck_x0 - RAMP_RUN, ramp_y],
             'yaw': 0.0, 'run': RAMP_RUN, 'rise': RAMP_RISE, 'width': RAMP_WIDTH,
             'onto': 'mezzanine_deck'},
            {'id': 'mezzanine_deck', 'kind': 'platform',
             'center': [r((deck_x0 + deck_x1) / 2), r((deck_y0 + deck_y1) / 2)],
             'size': [r(deck_x1 - deck_x0), r(deck_y1 - deck_y0)], 'top': RAMP_RISE}]
    rail_h = 1.75          # standing on the floor: 1.1 m above the deck
    kit += [{'id': 'rail_south', 'kind': 'box', 'role': 'guard',
             'center': [r((deck_x0 + deck_x1) / 2), deck_y0 + 0.05],
             'size': [r(deck_x1 - deck_x0), 0.1], 'height': rail_h},
            {'id': 'rail_west_south', 'kind': 'box', 'role': 'guard',
             'center': [deck_x0 + 0.05, r((deck_y0 + 0.1 + ramp_y - RAMP_WIDTH / 2) / 2)],
             'size': [0.1, r(ramp_y - RAMP_WIDTH / 2 - deck_y0 - 0.1)], 'height': rail_h},
            {'id': 'rail_west_north', 'kind': 'box', 'role': 'guard',
             'center': [deck_x0 + 0.05, r((ramp_y + RAMP_WIDTH / 2 + deck_y1) / 2)],
             'size': [0.1, r(deck_y1 - ramp_y - RAMP_WIDTH / 2)], 'height': rail_h}]
    # -- zone 1: the loading dock, x 35.5..47.85, y 0..9.5
    for k, x in enumerate((36.6, 38.6, 40.6, 42.6, 44.6, 46.6), start=1):
        kit.append({'id': f'pallet_stage_{k}', 'kind': 'pallet', 'center': [x, 4.5],
                    'size': [1.2, 1.0], 'height': 1.4})
    kit += [{'id': 'pallet_pair_w', 'kind': 'pallet', 'center': [36.6, 7.5],
             'size': [1.2, 1.0], 'height': 1.4},
            {'id': 'pallet_pair_e', 'kind': 'pallet', 'center': [38.2, 7.5],
             'size': [1.2, 1.0], 'height': 1.4}]
    for k, x in enumerate((38.5, 42.0, 45.5), start=1):
        kit.append({'id': f'dock_{k}', 'kind': 'zone', 'role': 'drop', 'center': [x, 1.3],
                    'size': [2.6, 2.0], 'label': f'Dock {k}'})
    # -- the dispatch floor, x 14.5..32, y 0..9.5: the start, a drop zone, packing benches
    kit += [{'id': 'dispatch_drop', 'kind': 'zone', 'role': 'drop', 'center': [23.0, 1.4],
             'size': [3.0, 2.0], 'label': 'Dispatch'},
            {'id': 'start_pad', 'kind': 'zone', 'role': 'start', 'center': [23.0, 6.0],
             'size': [1.0, 1.0], 'label': 'COCO start'},
            {'id': 'packing_bench_w', 'kind': 'bench', 'center': [18.0, 3.0],
             'size': [1.6, 0.8], 'height': 0.9},
            {'id': 'packing_bench_e', 'kind': 'bench', 'center': [28.0, 3.0],
             'size': [1.6, 0.8], 'height': 0.9}]
    # -- the six zones, as regions (UI and docs)
    for zid, label, cx, cy, sx, sy in (
            ('zone_loading_dock', 'Loading dock', 41.7, 4.8, 12.3, 9.3),
            ('zone_high_bay', 'High-bay aisles', 23.7, 21.9, 16.0, 14.0),
            ('zone_mezzanine', 'Mezzanine', 40.9, 27.85, 13.6, 7.7),
            ('zone_office', 'Office block', 7.0, 26.0, 14.0, 12.0),
            ('zone_workshop', 'Workshop maze', 7.0, 9.0, 14.0, 18.0),
            ('zone_forklift_lanes', 'Forklift lanes', 31.2, 11.75, 33.4, 3.5)):
        kit.append({'id': zid, 'kind': 'zone', 'role': 'region', 'center': [cx, cy],
                    'size': [sx, sy], 'label': label})
    # -- objects
    deads = sorted(dead, key=lambda c: (-c[0] - c[1], c))
    cell = [((c + 0.5) * MAZE_CELL, (rr + 0.5) * MAZE_CELL) for c, rr in deads]
    objs = [
        ('obj_maze_1', 'can_small', cell[0], 'floor'),
        ('obj_maze_2', 'canister', cell[len(cell) // 2], 'floor'),
        ('obj_mez_1', 'bottle_steel', (42.0, 30.0), 'mezzanine_deck'),
        ('obj_mez_2', 'canister', (45.0, 26.0), 'mezzanine_deck'),
        ('obj_aisle_1', 'can_large', (20.0, 17.3), 'floor'),
        ('obj_aisle_3', 'canister', (28.5, 26.5), 'floor'),
        ('obj_office_ne', 'can_small', (10.0, 29.5), 'floor'),
        ('obj_office_sw', 'bottle_steel', (2.5, 23.5), 'floor'),
        ('obj_dispatch', 'can_large', (27.0, 7.5), 'floor'),
        ('obj_dock', 'canister', (46.5, 7.5), 'floor'),
        ('bad_too_wide', 'paint_tin', (19.0, 7.5), 'floor'),
        ('bad_not_magnetic', 'plastic_bottle', (22.0, 21.9), 'floor'),
        ('bad_too_low', 'low_tin', (4.5, 30.0), 'floor'),
        ('bad_on_shelf', 'can_small', (19.5, 20.15), 'rack_C1'),
        ('bad_on_desk', 'canister', (12.0, 21.0), 'desk_se'),
        ('bad_blocked', 'can_large', (37.4, 7.5), 'floor'),
        ('bad_crate', 'crate', (44.5, 7.5), 'floor'),
        ('bad_on_bench', 'can_large', (28.0, 3.0), 'packing_bench_e'),
    ]
    for oid, item, (x, y), sup in objs:
        o = {'id': oid, 'kind': 'object', 'item': item, 'at': [r(x), r(y)]}
        if sup != 'floor':
            o['support'] = sup
        if sup.startswith('rack_'):
            o['shelf'] = 0
        kit.append(o)
    # -- actors: two forklifts and two walkers, phases chosen so no two ever meet
    actors = [
        {'id': 'forklift_east_west', 'kind': 'actor', 'actor': 'forklift',
         'path': [[16.0, 11.0], [46.0, 11.0]], 'mode': 'pingpong', 'speed': 1.5,
         'footprint': [2.4, 1.2], 'height': 2.2},
        {'id': 'forklift_north_south', 'kind': 'actor', 'actor': 'forklift',
         'path': [[33.75, 14.5], [33.75, 22.5]], 'mode': 'pingpong', 'speed': 1.5,
         'footprint': [2.4, 1.2], 'height': 2.2},
        {'id': 'walker_aisle_gap', 'kind': 'actor', 'actor': 'walker',
         'path': [[24.2, 8.5], [24.2, 14.5]], 'mode': 'pingpong', 'speed': 1.2,
         'footprint': [0.5, 0.5], 'height': 1.75},
        {'id': 'walker_dock', 'kind': 'actor', 'actor': 'walker',
         'path': [[40.0, 8.75], [40.0, 14.75]], 'mode': 'pingpong', 'speed': 1.2,
         'footprint': [0.5, 0.5], 'height': 1.75},
    ]
    choose_phases(actors)
    kit += actors
    spec = {
        'spec_version': 'coco.world_spec.v3',
        'id': 'coco_depot_v1',
        'title': 'COCO Depot: a night-shift warehouse, 48 x 32 m, six zones',
        'sources': {
            'layout': 'worlds/tools/make_coco_depot_v1.py (this file is generated)',
            'design': 'docs/v2/m6/DEPOT_DESIGN.md',
            'robot': 'worlds/coco_arena_v2.yaml (copied; a test asserts they agree)',
            'ramp': 'worlds/coco_arena_v2.yaml elevation (the bay ramp: run 2, 18 deg)',
            'catalog_graspable': 'coco_config/coco_config/robot.py TARGETS, TARGET_HEIGHT, '
                                 'TARGET_MASS',
        },
        'frame': 'world',
        'world_to_map': [0, 0],
        'bounds': {'x_min': 0, 'x_max': W, 'y_min': 0, 'y_max': H},
        'robot': arena['robot'],
        'start': {'x': 23.0, 'y': 6.0, 'theta': 0.0},
        'arena': {'resolution': 0.1, 'margin': 0.5, 'dt': 0.1, 'unknown': 'blocked'},
        'catalog': catalog(),
        'kit': kit,
    }
    return spec


def build_colours():
    """Build the Depot plus its four colour rods (``--variant colours``): nothing else changes."""
    spec = build()
    kit = spec['kit']
    at = next(i for i, e in enumerate(kit) if e['kind'] == 'actor')
    rods = [{'id': oid, 'kind': 'object', 'item': item, 'at': [r(x), r(y)]}
            for oid, item, (x, y) in COLOUR_RODS]
    spec['kit'] = kit[:at] + rods + kit[at:]
    spec['id'] = COLOURS_ID
    spec['title'] = ('COCO Depot, colour rods: the Depot plus four rods (red, green, blue, '
                     'yellow), fetch by colour')
    spec['sources'] = dict(spec['sources'],
                           layout='worlds/tools/make_coco_depot_v1.py --variant colours '
                                  '(this file is generated)',
                           rods='the Stack targets by colour (coco_config/coco_config/robot.py '
                                'TARGETS), placed in a row as the Stack bays are')
    return spec


def choose_phases(actors, horizon=600.0, step=0.05):
    """Give each actor the smallest phase (0.5 m steps) that never meets an earlier one."""
    from coco_lab import worldspec_v3 as v3

    def length(a):
        p = a['path']
        return 2 * sum(math.dist(p[i], p[i + 1]) for i in range(len(p) - 1))
    placed = []
    for a in actors:
        for k in range(int(length(a) / 0.5)):
            a['phase'] = 0.5 * k
            if all(not _meet(a, b, horizon, step, v3) for b in placed):
                break
        else:
            raise SystemExit(f'no phase keeps {a["id"]} clear of the others')
        placed.append(a)


def _meet(a, b, horizon, step, v3):
    n = int(horizon / step)
    for i in range(n):
        t = i * step
        ca, cb = v3.actor_corners(a, t), v3.actor_corners(b, t)
        xs = [p[0] for p in cb]
        ys = [p[1] for p in cb]
        if v3.obb_hits_rect(ca, (min(xs), max(xs), min(ys), max(ys))):
            return True
    return False


def dump(spec, variant=''):
    head = ('# COCO Depot, World Spec v3 (docs/v2/m6/WORLD_SPEC_V3.md; '
            'docs/v2/m6/DEPOT_DESIGN.md).\n'
            '# GENERATED by worlds/tools/make_coco_depot_v1.py; edit that and regenerate, '
            'never this file.\n')
    if variant:
        head = ('# COCO Depot, colour rods (variant of coco_depot_v1), World Spec v3.\n'
                f'# GENERATED by worlds/tools/make_coco_depot_v1.py --variant {variant}; '
                'never edit this file.\n')
    return head + yaml.safe_dump(spec, sort_keys=False, default_flow_style=None, width=100)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--variant', default='', choices=sorted(VARIANTS))
    a = ap.parse_args()
    out = VARIANTS[a.variant][1]
    text = dump(build_colours() if a.variant == 'colours' else build(), a.variant)
    if a.check:
        with open(out, encoding='utf-8') as f:
            same = f.read() == text
        print('up to date' if same else 'DIFFERS: regenerate')
        return 0 if same else 1
    with open(out, 'w', encoding='utf-8') as f:
        f.write(text)
    print(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
