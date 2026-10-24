#!/usr/bin/env python3
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.2: the parity fixture for the page's ROS-shaped model (lab_web/src/ros/shapes.ts).

    tools/g2/make_ros_parity_fixture.py [--check]

AGENTS.md: a second implementation must agree with Python's on recorded data, in CI. This
plays a short Free Drive session on the Depot through the browser's own glue
(lab_web/src/arena/arena_glue.py, in CPython; hash version 3), and writes, per tick, what the
page receives (the tick JSON's fields shapes.ts reads, and the ranges) beside what
coco_lab.ros_shapes builds from the Arena at that tick: LaserScan, Odometry, TFMessage,
TwistStamped, the plan's Path; once: the static frames and the OccupancyGrid's header, info
and a digest of its data. test/g2_ros_shapes.test.ts builds the TS shapes from the page's
side and compares them with Python's. ``--check`` regenerates in memory and compares with
the committed file (lab_web/tools/test_g2_ros_parity.py runs it).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from array import array

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
OUT = os.path.join(REPO, 'lab_web', 'test', 'fixtures', 'ros_shapes_parity.json')

#: the session: the setup, teleop for a while, a goal (a plan), then the planner drives
INPUTS = {1: [{'kind': 'teleop', 'linear': 0.3, 'angular': 0.25}],
          9: [{'kind': 'teleop', 'linear': 0.0, 'angular': 0.0}],
          10: [{'kind': 'goal', 'x': 26.0, 'y': 6.0}]}
TICKS = 24
RANGES_EVERY = 4


def glue():
    spec = importlib.util.spec_from_file_location('g2_parity_glue', os.path.join(REPO, 'lab_web/src/arena/arena_glue.py'))
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def rle(cells):
    """The LabMap's cells as [value, count] runs (the page receives them as bytes)."""
    out = []
    for v in cells:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def build():
    from coco_lab import numerics, ros_shapes
    g = glue()
    spec = open(os.path.join(REPO, 'worlds', 'coco_depot_v1.json')).read()
    world_json, occ = g.game_init(spec, 'free', 0, 1, lambda *_: None, hash_version=3)
    world = json.loads(world_json)
    a = g._arena
    ticks = []
    for k in range(TICKS):
        rows = world['game']['setup'] if k == 0 else INPUTS.get(k, [])
        g.begin(json.dumps(rows))          # as the worker steps: begin, advance, finish
        while not g.advance(4096):
            pass
        tick_json, ranges = g.finish()
        t = json.loads(tick_json)
        plan = t['plans'][-1]['waypoints'] if t['plans'] else None
        with numerics.version(a.hash_version):
            want = {'scan': ros_shapes.laser_scan(a), 'odom': ros_shapes.odometry(a),
                    'tf': ros_shapes.tf(a), 'cmd_vel': ros_shapes.twist_stamped(a.v, a.w, a.t_world)}
            if plan:
                want['plan'] = ros_shapes.path([tuple(p) for p in plan], a.t_world)
        ranges_py = want['scan'].pop('ranges')
        assert list(ranges) == [float(f) for f in array('f', ranges_py)], 'the page gets the ranges as float32'
        row = {'page': {'tick': t['tick'], 't_world': t['t_world'], 'v': t['v'], 'w': t['w'],
                        'ros': t['ros'], 'plan': plan}, 'want': want}
        if k % RANGES_EVERY == 0:   # the ranges, in full, every RANGES_EVERY-th tick (the file's size)
            row['ranges'] = [r if r == r and abs(r) != float('inf') else None for r in ranges_py]   # JSON: no-return beams (inf) as null
        ticks.append(row)
    with numerics.version(a.hash_version):
        grid = ros_shapes.occupancy_grid(a.lab_map)
    data = grid.pop('data')
    m = a.lab_map
    return {'about': 'G2.2: ROS-shaped model parity, coco_lab.ros_shapes (Python) vs lab_web/src/ros/shapes.ts '
                     '(tools/g2/make_ros_parity_fixture.py); Free Drive on the Depot, hash v3',
            'info': world['game']['ros'],
            'map': {'width': m.width, 'height': m.height, 'resolution': m.resolution,
                    'origin': list(m.origin),
                    'occupancy_sha256': hashlib.sha256(bytes(occ)).hexdigest(),
                    'occupancy_rle': rle(bytes(occ)),
                    'grid': grid,
                    'grid_data_sha256': hashlib.sha256(json.dumps(data, separators=(',', ':')).encode()).hexdigest(),
                    'grid_data_counts': {str(v): data.count(v) for v in sorted(set(data))}},
            'ticks': ticks}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--check', action='store_true')
    o = ap.parse_args()
    text = json.dumps(build(), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
    if o.check:
        same = os.path.exists(OUT) and open(OUT).read() == text
        print('ros parity fixture is current' if same else f'{OUT} is stale: run {__file__}')
        return 0 if same else 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        f.write(text)
    print('wrote', OUT, len(text), 'bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
