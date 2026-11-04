# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
R2.2: the user-code worker's Python side (ADR 0012). Trusted code; user code only ever
runs through coco_lab.user_code's guard, inside coco_lab.experiments' runs.

Every answer is JSON. While a run is in flight the worker hears from us after every call
of the user's function (``beat``: the page's time limit counts the silence between beats)
and gets the run's thinking and frames in chunks (``chunk``), so the Studio draws as it runs.
"""

import json
import sys
from time import perf_counter

from coco_lab import experiments, exp_user

_post = None
_beat_at = [0.0]
_calls = [0]
#: what one run may send to the page for drawing (the rest is counted, never sent)
MAX_DRAW_EVENTS = 200_000
MAX_FRAMES = 20_000


def _finite(v):
    """Strict JSON for the page: a non-finite number becomes null (JSON has no Infinity/NaN)."""
    if isinstance(v, float):
        return v if v == v and v not in (float('inf'), float('-inf')) else None
    if isinstance(v, dict):
        return {k: _finite(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_finite(x) for x in v]
    return v


def _dumps(obj):
    return json.dumps(_finite(obj), allow_nan=False)


def set_post(fn):
    """Remember the worker's post function (a JS function taking one JSON string)."""
    global _post
    _post = fn


def _on_call(ms):
    _calls[0] += 1
    now = perf_counter()
    if now - _beat_at[0] > 0.05 or ms > 50:
        _beat_at[0] = now
        _post(json.dumps({'k': 'beat', 'calls': _calls[0], 'ms': ms}))


exp_user.ON_CALL = _on_call


def register_worlds(worlds_json):
    """Register the shipped World Specs (fetched before lockdown: no network after it)."""
    for wid, text in json.loads(worlds_json).items():
        experiments.register_world(wid, json.loads(text))


def lockdown():
    """Take the JavaScript bridge modules away from Python (the guard also refuses them)."""
    blocked = ('js', 'pyodide_js')
    for name in list(sys.modules):
        if name.split('.')[0] in blocked:
            del sys.modules[name]

    class _Deny:
        @staticmethod
        def find_spec(name, path=None, target=None):
            if name.split('.')[0] in blocked:
                raise ImportError(f'{name} is not available in the algorithm sandbox')
            return None
    sys.meta_path.insert(0, _Deny())


def probe():
    """Fixed Python-side probes (no user input): can the bridge still be imported?"""
    out = {}
    for name in ('js', 'pyodide_js'):
        try:
            __import__(name)
            out[f'import {name}'] = 'REACHABLE'
        except ImportError as e:
            out[f'import {name}'] = f'blocked ({type(e).__name__})'
    from coco_lab import user_code
    for src in ('import js', 'from pyodide.ffi import to_js', 'x = ().__class__',
                'import sys', 'f = open'):
        try:
            user_code.load(src + '\ndef plan(c, s, g, ctx):\n    return f()\n'
                           if src.startswith('f =') else
                           src + '\ndef plan(c, s, g, ctx):\n    return None\n').fn(
                None, None, None, None)
            out[f'guard: {src}'] = 'REACHABLE'
        except (user_code.GuardError, NameError) as e:
            out[f'guard: {src}'] = f'blocked ({type(e).__name__})'
    return json.dumps(out)


class _Draw:
    """A run's drawing stream: thinking events and frames, posted in chunks."""

    def __init__(self, rid, family):
        self.rid, self.family = rid, family
        self.events = {}
        self.frames = []
        self.n_events = self.n_frames = self.cut = 0

    def event(self, kind, data):
        if self.n_events >= MAX_DRAW_EVENTS:
            self.cut += 1
            return
        self.n_events += 1
        self.events.setdefault(kind, []).append(data)
        if self.n_events % 5000 == 0:
            self.flush()

    def frame(self, a, t):
        if self.n_frames >= MAX_FRAMES:
            return
        self.n_frames += 1
        b = a.belief()
        mv = a.subsystems.get('move')
        last = getattr(mv, 'last', None) if mv is not None else None
        cands = []
        look = None
        if last is not None and getattr(last, 'candidates', None):
            for c in last.candidates[:24]:
                pts = c.traj[2::3] or c.traj
                cands.append({'points': [[round(p[0], 4), round(p[1], 4)] for p in pts],
                              'valid': bool(c.valid)})
            look = list(last.lookahead) if last.lookahead else None
        ev = self.events.pop('particles', None)
        parts = None
        if ev:
            p = ev[-1]
            step = max(1, len(p['x']) // 300)
            parts = {k: [round(v, 4) for v in p[k][::step]] for k in ('x', 'y', 'theta')}
        est = self.events.pop('estimate', None)
        self.frames.append({'tick': t.tick, 'truth': [round(v, 5) for v in t.pose],
                            'belief': [round(v, 5) for v in b], 'v': t.v, 'w': t.w,
                            'contact': bool(t.contact), 'candidates': cands, 'lookahead': look,
                            'particles': parts, 'estimate': est[-1] if est else None,
                            'scan': [round(r, 3) if r < 1e9 else -1.0 for r in a.ranges[::8]],
                            'waypoints': [[round(p[0], 3), round(p[1], 3)] for p in a.waypoints]
                            if t.tick % 10 == 0 or t.tick < 2 else None})
        self.events.pop('candidate', None)
        self.events.pop('lookahead', None)
        if len(self.frames) >= 25:
            self.flush()

    def flush(self):
        if self.events or self.frames:
            _post(_dumps({'k': 'chunk', 'id': self.rid, 'events': self.events,
                          'frames': self.frames}))
        self.events, self.frames = {}, []


def _check(src):
    """Load the file once (its top level runs, guarded): its kind, or every problem with its line."""
    from coco_lab import user_code
    try:
        m = user_code.load(src)
        return {'ok': True, 'kind': m.kind, 'function': m.function_name,
                'sha256': m.sha256, 'console': m.console.text()}
    except user_code.GuardError as e:
        return {'ok': False, 'problems': e.problems}
    except Exception as e:  # the file's own top level raised
        return {'ok': False, 'error': user_code.describe_error(e)}


def _map(world_id):
    """The world's map for drawing: geometry, occupancy as one character per cell, the LiDAR."""
    w = experiments.world(world_id)
    m = w.lab_map
    rb = w.spec['robot']
    li = rb['lidar']
    n = li['samples']
    return {'width': m.width, 'height': m.height, 'resolution': m.resolution,
            'origin': list(m.origin), 'occupancy': ''.join('012'[v] for v in m.occupancy),
            'radius': rb['radius'], 'lidar': {'angle_min': li['angle_min'],
                                              'angle_inc': (li['angle_max'] - li['angle_min'])
                                              / (n - 1) if n > 1 else 0.0,
                                              'mount': li['mount'][:2], 'every': 8}}


def run(request_json):
    """``{id, op, spec, code, indices}`` -> JSON (``check`` | ``map`` | ``plan`` | ``runs`` | ``scenario``)."""
    req = json.loads(request_json)
    op = req['op']
    if op == 'check':
        return _dumps(_check(req['code'][0]))
    if op == 'map':
        return _dumps(_map(req['world']))
    if op == 'export':
        # R2.7: the ROS 2 package -- coco_lab.ros2_export, the very function the CLI runs
        from coco_lab import ros2_export
        return _dumps(ros2_export.export(req['code'][0], req['name'], req.get('author') or
                                         'COCO Lab user', req.get('licence') or 'MIT'))
    for src in req.get('code') or []:
        exp_user.register(src)
    p = experiments.plan(req['spec'])
    if op == 'plan':
        return _dumps({'spec': p['spec'], 'id': p['id'], 'world_sha256': p['world_sha256'],
                           'scenarios': p['scenarios'], 'scenario_info': p['scenario_info'],
                           'sweep_points': p['sweep_points'], 'n_runs': len(p['runs'])})
    if op == 'summary':
        return _dumps(experiments.plain(experiments.summarise(p, req['records'])))
    _post(json.dumps({'k': 'beat', 'calls': _calls[0], 'ms': 0}))
    if op == 'runs':
        return _dumps(experiments.plain([experiments.run_one(p['runs'][int(i)])
                                         for i in req['indices']]))
    if op == 'scenario':
        d = p['runs'][int(req['indices'][0])]
        draw = _Draw(req['id'], d['family'])
        rows = []

        def sink(row):
            if row[0] == 3:
                rows.append([row[1], row[2]])
        rec = experiments.run_one(d, sink=sink if d['family'] == 'planning' else None,
                                  on_tick=draw.frame, on_event=draw.event)
        draw.flush()
        rec = experiments.plain(rec)
        rec['draw'] = {'events': draw.n_events, 'frames': draw.n_frames, 'cut': draw.cut,
                       'path_cells': rows}
        return _dumps(rec)
    raise ValueError(f'unknown op {op!r}')
