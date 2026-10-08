# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Glue between the Arena worker (arena.worker.ts) and coco_lab.arena.

It computes nothing itself (README section 3: the browser never
re-implements an algorithm): it builds coco_lab's Arena, steps it, and
hands its outputs to JavaScript as JSON plus typed-array buffers -- the
world's occupancy once, each tick's ranges, and plan events in columnar
batches WHILE the search runs (ADR 0001). Imports: coco_lab, json, array.
"""

from array import array
import json

from coco_lab.arena import Arena, InputEvent, PLANNERS

_arena = None


def init(spec_json, seed, planner, post_batch, batch_size=2048):
    """Build the Arena; return (world JSON, occupancy bytes)."""
    global _arena

    def hook(columns, meta):
        post_batch(columns, json.dumps(meta))

    _arena = Arena(json.loads(spec_json), int(seed), planner=planner,
                   on_plan_batch=hook, plan_batch_size=int(batch_size))
    m = _arena.lab_map
    li = _arena.lidar
    world = {
        'id': _arena.spec['id'],
        'width': m.width, 'height': m.height, 'resolution': m.resolution,
        'origin': list(m.origin), 'frame': m.frame,
        'start': list(_arena.start), 'dt': _arena.dt,
        'radius': _arena.radius, 'limits': _arena.limits,
        'lidar': {'samples': li.samples, 'angle_min': li.angle_min,
                  'angle_max': li.angle_max, 'range_max': li.range_max,
                  'mount': list(li.mount)},
        'planners': list(PLANNERS), 'planner': _arena.planner,
        'hash': _arena.state_hash(),
    }
    return json.dumps(world), m.occupancy


def step(inputs_json):
    """Step one tick; return (tick JSON, ranges as float32)."""
    events = [InputEvent(**e) for e in json.loads(inputs_json)]
    t = _arena.step(events)
    tick = {
        'tick': t.tick, 't_world': t.t_world, 'pose': list(t.pose),
        'v': t.v, 'w': t.w, 'mode': t.mode, 'blocked': t.blocked,
        'arrived': t.arrived, 'hash': t.state_hash,
        'chain': _arena.chain,
        'plans': [{
            'search_id': k,
            'planner': p.planner, 'goal': list(p.goal), 'tick': p.tick,
            'status': p.result.status,
            'summary': p.result.trace.summary,
            'waypoints': [list(w) for w in p.waypoints],
        } for k, p in enumerate(t.plans, _arena.plans_made - len(t.plans))],
    }
    return json.dumps(tick), array('f', t.ranges)
