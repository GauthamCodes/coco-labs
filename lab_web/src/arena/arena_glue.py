# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Glue between the Arena worker (arena.worker.ts) and coco_lab.arena.

It computes nothing itself (README section 3: the browser never
re-implements an algorithm): it builds coco_lab's Arena, steps it, and
hands its outputs to JavaScript as JSON plus typed-array buffers -- the
world's occupancy once, each tick's ranges, and plan events in columnar
batches WHILE the search runs (ADR 0001). Imports: coco_lab, json, array,
functools.
"""

from array import array
import functools
import json

from coco_lab import numerics
from coco_lab.arena import Arena, InputEvent, LOOP_KINDS, PLANNERS

_arena = None
_post_family = None
#: the World Spec the Arena was built from (Play's map challenge re-simulates on it)
_spec_json = None
#: M3.5: a map challenge's distance budget, while one is being driven
_budget = None


def _in_run(fn):
    """G1.8/G1.11: run a worker call in the live Arena's numerics, and only that call."""
    @functools.wraps(fn)
    def run(*args, **kw):
        with numerics.version(_arena.hash_version if _arena is not None else 1):
            return fn(*args, **kw)
    return run


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
         post_family=None, hash_version=1):
    """Build the Arena; return (world JSON, occupancy bytes)."""
    global _arena, _post_family, _spec_json, _budget, _game
    _game = None
    _post_family = post_family
    _spec_json = spec_json
    _budget = None

    def hook(columns, meta):
        post_batch(columns, json.dumps(meta))

    def family(channel, tick, columns, scalars):
        if columns is None:
            emit_header(channel, scalars)
        else:
            emit_family(channel, tick, columns, scalars)

    _arena = Arena(json.loads(spec_json), int(seed), planner=planner,
                   on_plan_batch=hook if post_batch is not None else None,
                   plan_batch_size=int(batch_size),
                   on_family=family, hash_version=int(hash_version))
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
        # M4.6: where the scan is drawn in 3D (presentation; the model casts at this height)
        'beam_height': _arena.beam_height,
    }
    if _arena.terrain is not None:
        # M4.3: where the targets stand (the frozen layout, on the platforms), to draw them
        from coco_lab.grasp import Grasp, TARGET_DIAMETER, TARGET_HEIGHT
        world['targets'] = [
            {'colour': c, 'x': x, 'y': y, 'z': _arena.terrain.height(x, y),
             'diameter': TARGET_DIAMETER[c], 'height': TARGET_HEIGHT}
            for c, (x, y) in sorted(Grasp(_arena.spec['world_to_map']).targets.items())]
    return json.dumps(world), m.occupancy


@_in_run
def compare(planner_a, planner_b, gx, gy, post_batch, batch_size=2048,
            inflation_json=None, planners_json=None):
    """
    Run two planners from the robot's cell to (gx, gy); change nothing.

    Side-by-side compare (M1.8): the same map, start, goal and seed for both,
    on the Arena's own planning grid, streamed as columnar batches tagged
    'A' / 'B' (search ids -101 / -102: never the run's own, never a
    PlanStore's empty -1). The Arena's state,
    and so every hash, is untouched. Returns both summaries as JSON.
    """
    from time import perf_counter
    from coco_lab.events import SearchEventColumns
    from coco_lab.compare_planning import COMPARE_PLANNERS, run_planner
    from coco_lab.sketch import _nearest_free

    a = _arena
    names = json.loads(planners_json) if planners_json else [planner_a, planner_b]
    if (not isinstance(names, list) or len(names) not in (2, 4) or
            any(not isinstance(name, str) or name not in COMPARE_PLANNERS
                for name in names)):
        raise ValueError('Compare needs two or four supported planners')
    g = a.grid
    if inflation_json is not None:
        from coco_lab.costmap import (InflationParams, build_layers,
                                      scan_obstacle_cells, emit_layers)
        from coco_lab.grid import Grid
        m, li = a.lab_map, a.lidar
        params = InflationParams(**json.loads(inflation_json))
        hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles,
                                   li.mount, li.range_min, li.range_max)
        layers = build_layers(m.width, m.height, m.resolution,
                              [v != 0 for v in m.occupancy], hits, params)
        emit_layers(layers, params, m.origin,
                    lambda channel, tick, columns, scalars:
                    emit_header(channel, scalars) if columns is None else
                    emit_family(channel, tick, columns, scalars),
                    tick=a.tick, t_world=a.t_world, update=a.tick)
        # A separate graph: never assign Arena.grid/plan_map or its radius.
        g = Grid(m.width, m.height,
                 blocked=[v >= 253 for v in layers.combined],
                 cost=layers.combined, connectivity=8)
    here = a.belief() if inflation_json is not None else a.pose
    s = _nearest_free(g, a.plan_map.cell_at(here[0], here[1]))
    t_cell = a.plan_map.cell_at(float(gx), float(gy))
    if s is None or t_cell is None:
        raise ValueError(f'goal ({gx}, {gy}) or the robot is off the map')
    t = _nearest_free(g, t_cell)
    if t is None:
        raise ValueError('costmap has no free goal cell')
    out = {}
    for i, name in enumerate(names):
        side, sid = 'ABCD'[i], -101 - i
        if name not in COMPARE_PLANNERS:
            raise ValueError(f'unknown planner {name!r}')
        cols = SearchEventColumns(search_id=sid, tick=a.tick,
                                  t_world=a.t_world)
        meta = {'search_id': sid, 'planner': name, 'tick': a.tick,
                'compare': side}

        def sink(row, cols=cols, meta=meta):
            cols.add(row)
            if len(cols) >= int(batch_size):
                post_batch(cols.drain(), json.dumps(dict(meta, final=False)))
        started = perf_counter()
        res = run_planner(g, s, t, name, sink)
        elapsed = (perf_counter() - started) * 1000
        post_batch(cols.drain(), json.dumps(dict(meta, final=True)))
        summary = dict(res.summary)
        if inflation_json is not None:
            summary['minimum_clearance_m'] = min(
                (layers.clearance[row * g.width + col] - params.robot_radius
                 for row, col in res.path), default=None)
            summary['compute_ms'] = elapsed
        out[side] = {'planner': name, 'status': res.status,
                     'summary': summary,
                     'resolution': a.plan_map.resolution}
    return json.dumps(out)


def _tick_json(t, inputs, game=None):
    # the whole loop (M2.3): the robot is drawn where it BELIEVES it is,
    # the truth beside it (as a recorded stack run draws AMCL and truth)
    extra = {} if t.belief is None else {'truth': list(t.pose)}
    if t.actors:
        extra['actors'] = [list(a) for a in t.actors]
    if _budget is not None:
        _budget.update(t.pose)
        extra['play'] = {'path_m': _budget.path_m, 'budget_m': _budget.budget_m,
                         'done': _budget.done}
    mv = _arena.subsystems.get('move')
    given = mv.take_path() if mv is not None else None
    if given:
        extra['path'] = [v for p in given for v in p]
    # M4.3: the 3D fields (presentation; the state hash is the model's own)
    if _arena.terrain is not None:
        extra['tilt'] = [t.z, t.pitch, t.roll]
    if t.grasp is not None:
        extra['grasp'] = t.grasp
    if game is not None:
        extra['game'] = game
    if _game is not None:
        # G2.2: the ROS-shaped model's dynamic frames this tick (coco_lab.ros_shapes, M6F.7:
        # map -> odom -> base_footprint), for SIM view, telemetry and the rosbag2 export.
        # Read-only, computed by ros_shapes itself (the page never re-derives them).
        from coco_lab import ros_shapes
        extra['ros'] = {'tf': ros_shapes.tf(_arena)}
    return json.dumps({
        **extra,
        'wheels': list(t.wheels), 'source': t.source,
        'tick': t.tick, 't_world': t.t_world,
        'pose': list(t.belief if t.belief is not None else t.pose),
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


@_in_run
def step(inputs_json):
    """Step one tick; return (tick JSON, ranges as float32)."""
    rows = json.loads(inputs_json)
    t = _arena.step([InputEvent(**e) for e in rows])
    return _tick_json(t, rows, game_finish(t, rows)), array('f', t.ranges)


# -- a step in slices (M2.0): the worker yields between them, so an input
# -- that arrives while the tick plans can join it (amend) ----------------

_pending_rows = []
#: loop inputs (kidnap, config) that arrived as amendments: a loop input
#: opens a tick, so they wait for the next one (coco_lab.arena)
_held_rows = []


def _stamp(inputs_json):
    """Stamp every row with the model's tick: the worker owns the input log."""
    rows = json.loads(inputs_json)
    for r in rows:
        r['tick'] = _arena.tick
    return rows


@_in_run
def begin(inputs_json):
    """Apply this tick's inputs and start its search; nothing runs yet."""
    global _pending_rows, _held_rows
    rows = _held_rows + json.loads(inputs_json)
    _held_rows = []
    for r in rows:
        r['tick'] = _arena.tick
    _arena.begin_step([InputEvent(**e) for e in rows])
    _pending_rows = rows


@_in_run
def advance(n):
    """Take up to n events of the tick's search; return whether it is done."""
    return _arena.advance(int(n))


@_in_run
def amend(inputs_json):
    """Inputs that arrived while the tick planned: they join this tick."""
    rows = _stamp(inputs_json)
    _held_rows.extend(r for r in rows if r['kind'] in LOOP_KINDS)
    rows = [r for r in rows if r['kind'] not in LOOP_KINDS]
    if rows:
        _arena.amend([InputEvent(**e) for e in rows])
        _pending_rows.extend(rows)


@_in_run
def finish():
    """Finish the tick; return (tick JSON, ranges as float32)."""
    t = _arena.finish_step()
    return _tick_json(t, _pending_rows, game_finish(t, _pending_rows)), array('f', t.ranges)


# -- Play (M3.5): coco_lab.play scores; this only passes JSON -------------------

def play(request_json):
    """
    Play's one entry point: ``view`` a level, ``score`` a submission, or
    ``map_begin`` a map challenge's budget on the live Arena.

    Every score is :func:`coco_lab.play.score` -- the function ``coco
    verify`` runs in Node -- on the submission alone: a map drive is
    re-simulated from its input log, never read off the live Arena.
    """
    global _budget
    from coco_lab import play as p
    req = json.loads(request_json)
    op = req.get('op')
    if op == 'view':
        return json.dumps(p.view(req['levels'], req['challenge'], req['level']))
    if op == 'score':
        result = p.score(req['levels'], req['submission'], json.loads(_spec_json))
        expected = req.get('expected_hash')
        if expected:
            candidates = p.verification_hashes(result)
            if req['submission'].get('hash_version', 1) != 1:
                candidates = {'canonical': result['hash']}
            for layout, digest in candidates.items():
                if expected == digest:
                    result['verified_hash'] = digest
                    result['verification_layout'] = layout
                    break
        return json.dumps(result)
    if op == 'map_begin':
        _budget = p.MapBudget(float(req['budget_m']), _arena.pose)
        return json.dumps({'path_m': 0.0, 'budget_m': _budget.budget_m})
    raise ValueError(f'unknown play op {op!r}')


_loop_comparison = None


def loop_compare_begin(request_json):
    """Create independent Compare arms, never replace the live Arena."""
    global _loop_comparison
    from coco_lab.compare_loop import LoopComparison
    _loop_comparison = LoopComparison(json.loads(_spec_json), json.loads(request_json))
    from coco_lab.costmap import emit_layers
    emit_layers(_loop_comparison.layers, _loop_comparison.params,
                _loop_comparison.arms[0].lab_map.origin,
                lambda channel, tick, columns, scalars:
                emit_header(channel, scalars) if columns is None else
                emit_family(channel, tick, columns, scalars))


def loop_compare_advance():
    """Return one lockstep tick from the independent Compare experiment."""
    return json.dumps(_loop_comparison.advance())



#: G1.13: Play's costmap view: the static map's layers (computed once per Arena map) and the
#: last layers sent, so a refresh recomputes only around new scan marks and sends only changes
_costmap = {'key': None, 'static': None, 'last': None}


@_in_run
def _costmap_static():
    """The current Arena's StaticLayers (built once per map, in its numerics; G1.13)."""
    from coco_lab.costmap import InflationParams, StaticLayers
    a = _arena
    m = a.lab_map
    params = InflationParams(robot_radius=a.radius, inflation_radius=max(0.5, a.radius))
    key = (id(a), id(m), params)
    if _costmap['key'] != key:
        _costmap.update(key=key, static=StaticLayers(m.width, m.height, m.resolution,
                                                     [v != 0 for v in m.occupancy], params),
                        last=None)
    return _costmap['static']


@_in_run
def costmap_view(delta=False):
    """
    Emit a view-only snapshot from current model data, without a tick/input.

    ``delta`` (G1.13, Play's Robot vision): the same layers, from the cached static map's
    share (costmap.StaticLayers: byte for byte build_layers'), and only the cells whose
    costs changed since the last view (all non-zero cells the first time). Measured: the
    full rebuild and full emission stalled the model ~0.9 s in the browser every 4 s.
    """
    if delta:
        from coco_lab.costmap import emit_cells, scan_obstacle_cells
        a = _arena
        m, li = a.lab_map, a.lidar
        sl = _costmap_static()
        hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles,
                                   li.mount, li.range_min, li.range_max)
        layers = sl.layers(hits)
        touched = sl.touched
        last = _costmap['last']
        if last is None:
            cells = [i for i in range(len(layers[3])) if layers[3][i] or layers[2][i] or layers[1][i]]
        else:
            # outside the cells either view touched, both equal the static map's layers
            cells = sorted(i for i in touched | last[4] if layers[1][i] != last[1][i] or
                           layers[2][i] != last[2][i] or layers[3][i] != last[3][i])
        _costmap['last'] = layers + (touched,)
        emit_cells(m.width, cells, layers[:4], sl.params, m.origin,
                   lambda channel, tick, columns, scalars:
                   emit_header(channel, scalars) if columns is None else
                   emit_family(channel, tick, columns, scalars),
                   height=m.height, resolution=m.resolution,
                   tick=a.tick, t_world=a.t_world, update=a.tick)
        return
    from coco_lab.costmap import (InflationParams, build_layers,
                                  scan_obstacle_cells, emit_layers)
    a = _arena
    m, li = a.lab_map, a.lidar
    params = InflationParams(robot_radius=a.radius,
                             inflation_radius=max(0.5, a.radius))
    hits = scan_obstacle_cells(m, a.belief(), a.ranges, a.angles,
                               li.mount, li.range_min, li.range_max)
    layers = build_layers(m.width, m.height, m.resolution,
                          [v != 0 for v in m.occupancy], hits, params)
    emit_layers(layers, params, m.origin,
                lambda channel, tick, columns, scalars:
                emit_header(channel, scalars) if columns is None else
                emit_family(channel, tick, columns, scalars),
                tick=a.tick, t_world=a.t_world, update=a.tick)


# -- G1: the game (Fetch Rush, Free Drive) on a World Spec v3 level ------------
#
# coco_lab.games decides everything (orders, deliveries, contacts, the timer,
# stars); Grasp Assist decides every grasp. This glue passes JSON, and keeps
# the record a played session replays from (spec, seed, input log), with the
# same per-tick hash chain games.play() computes in CPython.

_game = None


def game_init(spec_json, game, arg, seed, post_batch, batch_size=2048,
              post_family=None, hash_version=3, mode=None):
    """Build the Arena on a level for ``game`` ('fetch_rush' or 'free'); return init()'s pair."""
    global _game
    import hashlib
    from coco_lab import games
    from coco_lab import worldspec_v3 as v3
    # G1.12: the game draws no search wave, so its Arena streams none (the search, and so
    # the state, is the same either way); a goal's search can then be run ahead (prefetch)
    out = init(spec_json, seed, 'astar', None, batch_size, post_family, hash_version)
    world = json.loads(out[0])
    spec = _arena.spec
    dx, dy = spec['world_to_map']
    v3_level = v3.is_v3(spec)
    # G1.11: Fetch Rush plays a precomputed round (games.FetchRushRound), so no tick ever
    # waits for a planner search; G1.12: rules 3, in the 'phone' (default) or 'full' mode.
    # Rush Hour is unchanged
    version = games.FETCH_RUSH_RULES if game == 'fetch_rush' else 1
    if game == 'fetch_rush':
        mode = mode or games.ROUND_MODE_DEFAULT
    else:
        mode = None
    rules = games._rules(game, arg, version, mode) if game in games.GAMES else None
    _game = {'rules': rules, 'game': game, 'arg': arg, 'seed': int(seed),
             'chain': hashlib.sha256(), 'ticks': 0, 'inputs': [], 'v3': v3_level,
             'hash_version': int(hash_version), 'rules_version': version, 'mode': mode}
    info = {'game': game, 'arg': arg, 'v3': v3_level, 'mode': mode}
    if v3_level:
        # G2 rules 5: Free Drive on a v3 level gets rules 5's actors (they stop for COCO) and
        # AUTO's reaction too; Fetch Rush gets them from its rules (FETCH_RUSH_RULES >= 5)
        info['setup'] = games.setup_inputs(game if rules else 'fetch_rush', arg, version,
                                           mode=mode, yielding=None if rules else True)
        info['seconds'] = rules.seconds if isinstance(rules, games.FetchRush) else None
        if isinstance(rules, games.FetchRushRound):
            rnd = rules.round
            label = next((z.get('label', z['id']) for z in spec['kit'] if z['id'] == rnd['region']), rnd['region'])
            info['round'] = {'region': rnd['region'], 'label': label, 'orders': rnd['orders'],
                             'ghost_m': rnd['ghost_m'], 'routes': rnd['routes'],
                             'reference_time_s': rnd['reference_time_s'], 'timer_s': rnd['timer_s']}
        info['objects'] = [dict(o, x=o['x'] + dx, y=o['y'] + dy) for o in v3.objects(spec)]
        info['zones'] = [dict(z, center=[z['center'][0] + dx, z['center'][1] + dy])
                         for z in spec['kit'] if z['kind'] == 'zone']
        info['actors'] = [{'id': a['id'], 'actor': a['actor'], 'footprint': a['footprint'],
                           'height': a['height']} for a in v3.elements(spec, 'actor')]
    else:
        info['setup'] = []
    info['ros'] = _ros_info()
    world['game'] = info
    if v3_level:
        _costmap_static()   # G1.13: Robot vision's static costmap, built while the page loads
    return json.dumps(world), out[1]


def _ros_info():
    """
    G2.2: the ROS-shaped model's constants for the page, from coco_lab.ros_shapes (M6F.7):
    its graph (nodes, topics, rates), the static frames, the scan's fixed fields. Labelled
    MODEL by ros_graph itself: these are message shapes, never a ROS connection.
    """
    from coco_lab import numerics, ros_shapes
    a = _arena
    li = a.lidar
    with numerics.version(a.hash_version):
        return {'graph': ros_shapes.ros_graph(a.dt), 'tf_static': ros_shapes.tf_static(a),
                'frames': list(ros_shapes.FRAMES),
                'scan': {'frame_id': ros_shapes.LASER_FRAME, 'angle_min': li.angle_min,
                         'angle_max': li.angle_max, 'range_min': li.range_min,
                         'range_max': li.range_max}}


def _game_block(t):
    """The game's state after tick ``t``: what the HUD draws; read from coco_lab only."""
    from coco_lab import games
    g = _game
    a = _arena
    out = {}
    assist = a.subsystems.get('assist')
    if assist is not None:
        out['assist'] = {'phase': assist.phase, 'target': assist.target,
                         'carried': assist.carried(), 'want': assist.want,
                         'reason': assist.reason, 'attempt': assist.attempt}
        out['objects'] = [[oid, o['x'], o['y'], o['z'], o['status']]
                          for oid, o in sorted(assist.objects.items())]
    act = a.subsystems.get('actors')
    if act is not None:
        # where each actor really is (G2 rules 5: an actor that stopped for COCO runs late on
        # its schedule), so the drawing is the model's own
        out['actors'] = [[e['id'], x, y, yaw]
                         for e, (x, y, yaw) in zip(act.actors, act.poses())]
        out['clearance'] = act.clearance(a.pose[0], a.pose[1], a.radius)
        if act.yielding():
            out['actors_held'] = [e['id'] for e, h in zip(act.actors, act.holding()) if h]
    av = a.subsystems.get('avoid')
    if av is not None and av.on:
        # G2 rules 5: AUTO's reaction (waiting, re-planned, ...) and, on a re-plan, its route
        out['avoid'] = av.view()
        if av.replanned == a.tick:
            out['avoid']['waypoints'] = [list(w) for w in a.waypoints]
    r = g['rules']
    if isinstance(r, games.FetchRush) and r.started:
        cur = r.current()
        out['fetch'] = {'t': a.t_world - r.t0, 'seconds': r.seconds,
                        'over': r.over, 'order': list(cur) if cur else None, 'k': r.k,
                        'orders': len(r.orders), 'deliveries': len(r.delivered),
                        'contacts': r.contacts, 'ghost': r.ghost}
    return out


def game_finish(t, rows):
    """After a tick: the rules observe it, the chain grows, the log keeps its inputs."""
    g = _game
    if g is None:
        return None
    r = g['rules']
    if r is not None and not g.get('over'):
        if not r.started:
            r.start(_arena)
        r.observe(_arena, t)
    if r is not None and getattr(r, 'started', False) and g.get('order_k') != getattr(r, 'k', None):
        g['order_k'], g['order_pose'] = r.k, tuple(_arena.pose)
    g['chain'].update(t.state_hash.encode())
    g['ticks'] += 1
    g['inputs'].extend(rows)
    return _game_block(t)


def game_record():
    """Return the played session as a record games.play() replays, and its chain."""
    g = _game
    keys = ('tick', 'kind', 'x', 'y', 'theta', 'has_theta', 'linear', 'angular', 'choice')
    inputs = [{k: e[k] for k in keys if k in e} for e in g['inputs']]
    rec = {'game': g['game'], 'arg': g['arg'], 'seed': g['seed'], 'ticks': g['ticks'],
           'inputs': inputs, 'hash_version': g['hash_version']}
    if g.get('rules_version', 1) != 1:
        rec['rules'] = g['rules_version']
    if g.get('mode'):
        rec['mode'] = g['mode']
    return json.dumps({'record': rec,
                       'hash_chain': g['chain'].hexdigest(), 'last_hash': _arena.state_hash()})


def game_stars(reference_json):
    """Return the scorecard, and its stars against the committed reference card when there is one."""
    from coco_lab import games
    g = _game
    r = g['rules'] if g else None
    if r is None:
        return json.dumps({'card': None, 'stars': None, 'reference': None})
    card = games._card(r, _arena)
    if isinstance(r, games.FetchRushRound):
        # rules 2 and 3: the round's own reference (the bot's run of this round, committed with it)
        ref = (r.round.get('reference') or {}).get('card')
    else:
        ref = json.loads(reference_json) if reference_json else None
    return json.dumps({'card': card, 'reference': ref,
                       'stars': games.stars(card, ref) if ref else None})


def game_preview():
    """
    What GRAB would do now, without doing it: Grasp Assist's own candidates
    (detect, check, rank), read-only. Nothing in the model changes.
    """
    a = _arena
    assist = a.subsystems.get('assist')
    if assist is None:
        return json.dumps({'rows': []})
    rows = assist.candidates(a)
    return json.dumps({'rows': [{k: (None if isinstance(v, float) and v != v else v)
                                 for k, v in r.items()} for r in rows]})


def _auto_goal():
    from coco_lab import games
    a = _arena
    r = _game['rules'] if _game else None
    assist = a.subsystems.get('assist')
    if not isinstance(r, games.FetchRush) or assist is None or r.current() is None:
        return None
    oid, drop = r.current()
    if assist.carried() == oid:
        z = games.zone_rect(a.spec, drop)
        return {'x': (z[0] + z[1]) / 2, 'y': (z[2] + z[3]) / 2, 'why': 'drop'}
    o = assist.objects[oid]
    return {'x': o['x'], 'y': o['y'], 'why': 'pick', 'object': oid}


def game_auto_goal():
    """
    AUTO in Fetch Rush: where the planner sends COCO next. To the order's object
    (the planner stops at the nearest free cell; GRAB, Grasp Assist, takes it from
    there), or, carrying it, to the drop zone's centre. One planning call, in the
    tick, like any goal; the 16-pose ghost search (games.best_approach) is not
    repeated here. G1.12: :func:`game_prefetch` has usually run that search already.
    """
    return json.dumps(_auto_goal())


@_in_run
def game_prefetch(budget_ms):
    """
    G1.12: between ticks, run AUTO's search ahead -- from where COCO is now to where
    AUTO would send it (Arena.prefetch) -- for at most ``budget_ms`` of this call.
    Return whether it is done. When AUTO is pressed, the tick takes that same search
    over (finished, or where it got to), so pressing AUTO no longer stops the clock
    for a whole search; the plan, and every hash, are what they would have been.
    """
    from time import perf_counter
    g = _game
    goal = _auto_goal() if g is not None and not g.get('over') and _arena is not None else None
    if goal is None or _arena._in_step or _arena.mode == 'goal':
        return True     # nothing to run ahead (or AUTO is already driving there)
    end = perf_counter() + float(budget_ms) / 1000.0
    while True:
        if _arena.prefetch((goal['x'], goal['y']), 64):
            return True
        if perf_counter() >= end:
            return False


def game_ghost():
    """
    The planner ghost for the current order, drawn: the A* route from where COCO stood
    when the order appeared to the object, then to the drop zone's centre (the planner
    stops at the nearest free cell). Read-only; FetchRush's own ghost LENGTH (its
    pre-grasp-pose search) is what the score uses.
    """
    from coco_lab import games
    from coco_lab.search import search
    from coco_lab.sketch import _nearest_free
    a = _arena
    r = _game['rules'] if _game else None
    if not isinstance(r, games.FetchRush) or r.current() is None:
        return json.dumps(None)
    if isinstance(r, games.FetchRushRound):
        # rules 2: the round's precomputed route (no search: the tick never waits)
        return json.dumps({'order': r.k, 'points': r.round['routes'][r.k]})
    oid, drop = r.current()
    o = a.subsystems['assist'].objects[oid]
    z = games.zone_rect(a.spec, drop)
    legs = [(_game.get('order_pose', a.pose)[:2], (o['x'], o['y'])),
            ((o['x'], o['y']), ((z[0] + z[1]) / 2, (z[2] + z[3]) / 2))]
    pts = []
    for frm, to in legs:
        sc, gc = a.plan_map.cell_at(*frm), a.plan_map.cell_at(*to)
        if sc is None or gc is None:
            return json.dumps(None)
        s, t = _nearest_free(a.grid, sc), _nearest_free(a.grid, gc)
        if s is None or t is None:
            return json.dumps(None)
        res = search(a.grid, s, t, **PLANNERS['astar'])
        if not res.found:
            return json.dumps(None)
        pts += [list(a.plan_map.cell_centre(c[0], c[1])) for c in res.path]
    return json.dumps({'order': r.k, 'points': pts[::2] + [pts[-1]]})


@_in_run
def game_op(op, arg_json=None):
    """The worker's one entry point for game queries (none of them changes the model)."""
    if op == 'preview':
        return game_preview()
    if op == 'auto_goal':
        return game_auto_goal()
    if op == 'record':
        return game_record()
    if op == 'stars':
        return game_stars(arg_json)
    if op == 'ghost':
        return game_ghost()
    raise ValueError(f'unknown game op {op!r}')
