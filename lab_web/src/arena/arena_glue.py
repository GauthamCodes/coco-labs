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

from coco_lab.arena import Arena, InputEvent, LOOP_KINDS, PLANNERS

_arena = None
_post_family = None
#: the World Spec the Arena was built from (Play's map challenge re-simulates on it)
_spec_json = None
#: M3.5: a map challenge's distance budget, while one is being driven
_budget = None


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
                   on_plan_batch=hook, plan_batch_size=int(batch_size),
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


def begin(inputs_json):
    """Apply this tick's inputs and start its search; nothing runs yet."""
    global _pending_rows, _held_rows
    rows = _held_rows + json.loads(inputs_json)
    _held_rows = []
    for r in rows:
        r['tick'] = _arena.tick
    _arena.begin_step([InputEvent(**e) for e in rows])
    _pending_rows = rows


def advance(n):
    """Take up to n events of the tick's search; return whether it is done."""
    return _arena.advance(int(n))


def amend(inputs_json):
    """Inputs that arrived while the tick planned: they join this tick."""
    rows = _stamp(inputs_json)
    _held_rows.extend(r for r in rows if r['kind'] in LOOP_KINDS)
    rows = [r for r in rows if r['kind'] not in LOOP_KINDS]
    if rows:
        _arena.amend([InputEvent(**e) for e in rows])
        _pending_rows.extend(rows)


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



def costmap_view():
    """Emit a view-only snapshot from current model data, without a tick/input."""
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
              post_family=None, hash_version=2):
    """Build the Arena on a level for ``game`` ('fetch_rush' or 'free'); return init()'s pair."""
    global _game
    import hashlib
    from coco_lab import games
    from coco_lab import worldspec_v3 as v3
    out = init(spec_json, seed, 'astar', post_batch, batch_size, post_family, hash_version)
    world = json.loads(out[0])
    spec = _arena.spec
    dx, dy = spec['world_to_map']
    v3_level = v3.is_v3(spec)
    rules = games._rules(game, arg) if game in games.GAMES else None
    _game = {'rules': rules, 'game': game, 'arg': arg, 'seed': int(seed),
             'chain': hashlib.sha256(), 'ticks': 0, 'inputs': [], 'v3': v3_level,
             'hash_version': int(hash_version)}
    info = {'game': game, 'arg': arg, 'v3': v3_level}
    if v3_level:
        info['setup'] = games.setup_inputs(game if rules else 'fetch_rush', arg)
        info['seconds'] = games.FETCH_RUSH_SECONDS if game == 'fetch_rush' else None
        info['objects'] = [dict(o, x=o['x'] + dx, y=o['y'] + dy) for o in v3.objects(spec)]
        info['zones'] = [dict(z, center=[z['center'][0] + dx, z['center'][1] + dy])
                         for z in spec['kit'] if z['kind'] == 'zone']
        info['actors'] = [{'id': a['id'], 'actor': a['actor'], 'footprint': a['footprint'],
                           'height': a['height']} for a in v3.elements(spec, 'actor')]
    else:
        info['setup'] = []
    world['game'] = info
    return json.dumps(world), out[1]


def _game_block(t):
    """The game's state after tick ``t``: what the HUD draws; read from coco_lab only."""
    from coco_lab import games
    from coco_lab import worldspec_v3 as v3
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
        dx, dy = act.offset
        out['actors'] = []
        for e in act.actors:
            x, y, yaw = v3.actor_pose(e, a.t_world)
            out['actors'].append([e['id'], x + dx, y + dy, yaw])
        out['clearance'] = act.clearance(a.pose[0], a.pose[1], a.radius)
    r = g['rules']
    if isinstance(r, games.FetchRush) and r.started:
        cur = r.current()
        out['fetch'] = {'t': a.t_world - r.t0, 'seconds': games.FETCH_RUSH_SECONDS,
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
    g['chain'].update(t.state_hash.encode())
    g['ticks'] += 1
    g['inputs'].extend(rows)
    return _game_block(t)


def game_record():
    """Return the played session as a record games.play() replays, and its chain."""
    g = _game
    keys = ('tick', 'kind', 'x', 'y', 'theta', 'has_theta', 'linear', 'angular', 'choice')
    inputs = [{k: e[k] for k in keys if k in e} for e in g['inputs']]
    return json.dumps({'record': {'game': g['game'], 'arg': g['arg'], 'seed': g['seed'],
                                  'ticks': g['ticks'], 'inputs': inputs,
                                  'hash_version': g['hash_version']},
                       'hash_chain': g['chain'].hexdigest(), 'last_hash': _arena.state_hash()})


def game_stars(reference_json):
    """Return the scorecard, and its stars against the committed reference card when there is one."""
    from coco_lab import games
    g = _game
    r = g['rules'] if g else None
    if r is None:
        return json.dumps({'card': None, 'stars': None, 'reference': None})
    card = games._card(r, _arena)
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


def game_auto_goal():
    """AUTO in Fetch Rush: where the planner would send COCO next (the ghost's own legs)."""
    from coco_lab import games
    a = _arena
    r = _game['rules'] if _game else None
    assist = a.subsystems.get('assist')
    if not isinstance(r, games.FetchRush) or assist is None or r.current() is None:
        return json.dumps(None)
    oid, drop = r.current()
    if assist.carried() == oid:
        z = games.zone_rect(a.spec, drop)
        return json.dumps({'x': (z[0] + z[1]) / 2, 'y': (z[2] + z[3]) / 2, 'why': 'drop'})
    ba = games.best_approach(a, assist, oid, a.pose[:2])
    if not ba:
        return json.dumps(None)
    return json.dumps({'x': ba[0][0], 'y': ba[0][1], 'why': 'pick', 'object': oid})


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
    raise ValueError(f'unknown game op {op!r}')
