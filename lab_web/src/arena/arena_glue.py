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
_post_family = None


def emit_family(channel, tick, columns, scalars):
    """
    Hand one family batch (coco_lab.columns.Batch.drain()) to JavaScript.

    Numeric columns go as arrays (the worker transfers their buffers);
    string and bool columns, and the per-batch scalars, go as JSON
    (M2.2; ADR 0001).
    """
    if _post_family is None:
        return
    numeric, plain = {}, {}
    for name, col in columns.items():
        if isinstance(col, array) and col.typecode != 'B':
            numeric[name] = col
        elif isinstance(col, array):
            plain[name] = [bool(v) for v in col]
        else:
            plain[name] = list(col)
    _post_family(numeric, json.dumps({'channel': channel, 'tick': int(tick),
                                      'numeric': list(numeric),
                                      'plain': plain, 'scalars': scalars}))


def emit_header(channel, header):
    """Hand a static header (a dict) to JavaScript, once."""
    if _post_family is not None:
        _post_family({}, json.dumps({'channel': channel, 'header': header}))


def init(spec_json, seed, planner, post_batch, batch_size=2048,
         post_family=None):
    """Build the Arena; return (world JSON, occupancy bytes)."""
    global _arena, _post_family
    _post_family = post_family

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


def compare(planner_a, planner_b, gx, gy, post_batch, batch_size=2048):
    """
    Run two planners from the robot's cell to (gx, gy); change nothing.

    Side-by-side compare (M1.8): the same map, start, goal and seed for both,
    on the Arena's own planning grid, streamed as columnar batches tagged
    'A' / 'B' (search ids -101 / -102: never the run's own, never a
    PlanStore's empty -1). The Arena's state,
    and so every hash, is untouched. Returns both summaries as JSON.
    """
    from coco_lab.events import SearchEventColumns
    from coco_lab.search import collect, search_events
    from coco_lab.sketch import _nearest_free

    a = _arena
    g = a.grid
    s = _nearest_free(g, a.plan_map.cell_at(a.pose[0], a.pose[1]))
    t_cell = a.plan_map.cell_at(float(gx), float(gy))
    if s is None or t_cell is None:
        raise ValueError(f'goal ({gx}, {gy}) or the robot is off the map')
    t = _nearest_free(g, t_cell)
    out = {}
    for side, sid, name in (('A', -101, planner_a), ('B', -102, planner_b)):
        if name not in PLANNERS:
            raise ValueError(f'unknown planner {name!r}')
        cols = SearchEventColumns(search_id=sid, tick=a.tick,
                                  t_world=a.t_world)
        meta = {'search_id': sid, 'planner': name, 'tick': a.tick,
                'compare': side}

        def sink(row, cols=cols, meta=meta):
            cols.add(row)
            if len(cols) >= int(batch_size):
                post_batch(cols.drain(), json.dumps(dict(meta, final=False)))
        res = collect(search_events(g, s, t, **PLANNERS[name]), sink)
        post_batch(cols.drain(), json.dumps(dict(meta, final=True)))
        out[side] = {'planner': name, 'status': res.status,
                     'summary': res.trace.summary,
                     'resolution': a.plan_map.resolution}
    return json.dumps(out)


def _tick_json(t, inputs):
    return json.dumps({
        'tick': t.tick, 't_world': t.t_world, 'pose': list(t.pose),
        'v': t.v, 'w': t.w, 'mode': t.mode, 'blocked': t.blocked,
        'arrived': t.arrived, 'hash': t.state_hash,
        'chain': _arena.chain,
        # the inputs this tick applied: the run's input log (share links)
        'inputs': inputs,
        'plans': [{
            'search_id': k,
            'planner': p.planner, 'goal': list(p.goal), 'tick': p.tick,
            'status': p.result.status,
            'summary': p.result.trace.summary,
            'waypoints': [list(w) for w in p.waypoints],
        } for k, p in enumerate(t.plans, _arena.plans_made - len(t.plans))],
    })


def step(inputs_json):
    """Step one tick; return (tick JSON, ranges as float32)."""
    rows = json.loads(inputs_json)
    t = _arena.step([InputEvent(**e) for e in rows])
    return _tick_json(t, rows), array('f', t.ranges)


# -- a step in slices (M2.0): the worker yields between them, so an input
# -- that arrives while the tick plans can join it (amend) ----------------

_pending_rows = []


def _stamp(inputs_json):
    """Stamp every row with the model's tick: the worker owns the input log."""
    rows = json.loads(inputs_json)
    for r in rows:
        r['tick'] = _arena.tick
    return rows


def begin(inputs_json):
    """Apply this tick's inputs and start its search; nothing runs yet."""
    global _pending_rows
    rows = _stamp(inputs_json)
    _arena.begin_step([InputEvent(**e) for e in rows])
    _pending_rows = rows


def advance(n):
    """Take up to n events of the tick's search; return whether it is done."""
    return _arena.advance(int(n))


def amend(inputs_json):
    """Inputs that arrived while the tick planned: they join this tick."""
    rows = _stamp(inputs_json)
    _arena.amend([InputEvent(**e) for e in rows])
    _pending_rows.extend(rows)


def finish():
    """Finish the tick; return (tick JSON, ranges as float32)."""
    t = _arena.finish_step()
    return _tick_json(t, _pending_rows), array('f', t.ranges)
