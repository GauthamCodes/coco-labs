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
Glue ONLY: the Pyodide worker's bridge to coco_lab.

This file contains no search logic. For each request it:

1. takes the page's CURRENT bundle, validated by ``coco_lab``'s own
   ``load_bundle`` (full structural + semantic validation) -- or, when the
   same content hash was validated earlier in this worker, that bundle;
2. applies the painted strokes to the map (occupied or free, cell by cell)
   and refuses one that covers the start or the goal;
3. reruns ``coco_lab.search.search`` once per requested run (one for an
   edit or a settings change, two to four for a race), with the settings
   the page chose and the bundle's start, goal and move model;
4. when asked, runs the same search with ``'dijkstra'`` for the optimum;
5. serialises each result with ``coco_lab``'s own ``Bundle.validate``,
   ``Bundle.manifest`` and ``Bundle.arrays`` -- exactly what
   ``write_bundle`` writes, without the file system -- as a ``glass-box``
   bundle whose provenance says ``tool='lab_web/pyodide'``.

The page decodes the returned bytes with the same TypeScript decoder as
every other bundle.
"""

from collections import OrderedDict
import json
import os
import shutil
import sys
import tempfile
import time

import coco_lab
from coco_lab import bundle, locbundle
from coco_lab.localise import EKFParams, MCLParams
from coco_lab.maps import FREE, LabMap, OCCUPIED
from coco_lab.search import search
from coco_lab.sketch import Kidnap, Noise, Scenario, SketchMap

TOOL = 'lab_web/pyodide'
#: validated bundles by content hash, most recent last (bounded)
_CACHE = OrderedDict()
_CACHE_SIZE = 8


class Refused(ValueError):
    """An edit the page must explain to the learner, not a crash."""


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


def _bytes(data):
    """Bytes from a JS Uint8Array proxy (one memcpy) or a bytes-like."""
    to_bytes = getattr(data, 'to_bytes', None)
    # bytes(proxy) would copy element by element across the JS boundary:
    # measured ~10x slower than CPython's whole load for a 3.5 MB bundle
    return to_bytes() if to_bytes is not None else bytes(data)


def _remember(content_hash, b):
    _CACHE[content_hash] = b
    _CACHE.move_to_end(content_hash)
    while len(_CACHE) > _CACHE_SIZE:
        _CACHE.popitem(last=False)


def _load(manifest_bytes, arrays_name, arrays_file):
    """
    Return ``(bundle, load_ms)`` for the page's current bundle.

    A bundle not seen before goes through ``coco_lab.bundle.load_bundle``,
    exactly as in 1D; one this worker validated (or wrote) earlier is
    taken from the cache by its content hash, at 0 ms.
    """
    manifest_bytes = _bytes(manifest_bytes)
    claimed = json.loads(manifest_bytes).get('content_hash')
    if claimed in _CACHE:
        _CACHE.move_to_end(claimed)
        return _CACHE[claimed], 0.0
    t0 = time.perf_counter()
    work = tempfile.mkdtemp(prefix='lab_load_')
    try:
        with open(os.path.join(work, 'manifest.json'), 'wb') as f:
            f.write(manifest_bytes)
        with open(os.path.join(work, arrays_name), 'wb') as f:
            f.write(_bytes(arrays_file))
        b = bundle.load_bundle(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _remember(claimed, b)  # load_bundle checked the claimed hash
    return b, _ms(t0)


def _serialise(b):
    """Validate, then return ``(manifest bytes, arrays bytes, hash)``."""
    b.validate()
    manifest = b.manifest('none')
    raw = b''.join(d for _, _, d in b.arrays())
    return (bundle.canonical_json(manifest).encode('utf-8'), raw,
            manifest['content_hash'])


def _paint(m, strokes, protect):
    """Return ``m`` with ``strokes`` applied; refuse covering ``protect``."""
    if not strokes:
        return m
    occ = bytearray(m.occupancy)
    for stroke in strokes:
        value = {'occupied': OCCUPIED, 'free': FREE}[stroke['value']]
        for row, col in stroke['cells']:
            if not m.in_bounds((row, col)):
                raise Refused(f'cell ({row}, {col}) is outside the map')
            if value == OCCUPIED and (row, col) in protect:
                what = protect[(row, col)]
                raise Refused(
                    f'the brush covered the {what} cell ({row}, {col}). A '
                    f'search needs a free {what}, so this stroke was not '
                    f'applied: paint around it.')
            occ[row * m.width + col] = value
    return LabMap(m.width, m.height, bytes(occ), m.cost, map_id=m.id,
                  resolution=m.resolution, origin=m.origin, frame=m.frame,
                  meta=m.meta)


def recompute(request_json, manifest, arrays_name, arrays_file):
    """
    Apply the request to the current bundle; return the new bundles.

    ``request_json`` is ``{"strokes": [{"value": "occupied"|"free",
    "cells": [[r, c], ...]}, ...], "connectivity": 4|8|null, "runs":
    [{"algorithm", "heuristic", "weight", "tie_break"}, ...],
    "optimal": bool}``.
    """
    t_all = time.perf_counter()
    req = json.loads(request_json)
    b, load_ms = _load(manifest, arrays_name, arrays_file)
    run = b.run
    kind = run['graph']['kind']
    protect = {tuple(run['start'][:2]): 'start', tuple(run['goal'][:2]): 'goal'}
    new_map = _paint(b.lab_map, req.get('strokes') or [], protect)
    model = dict(run['model'])
    if req.get('connectivity') is not None:
        if kind != 'grid':
            raise Refused(f'connectivity applies to grid maps, not {kind!r}')
        model['connectivity'] = int(req['connectivity'])
    inputs = {'start': run['start'], 'goal': run['goal'], 'model': model}
    probe = bundle.Bundle(b.provenance, dict(run, model=model), new_map,
                          b.trace)
    graph = probe.graph()
    start = bundle.start_state(graph, run['start'])
    goal = bundle.goal_state(graph, run['goal'])
    for what, state in (('start', start), ('goal', goal)):
        if not graph.is_valid(state):
            raise Refused(f'the {what} is blocked on this map, so nothing '
                          f'can be searched from it')

    runs = req.get('runs') or [{
        'algorithm': run['algorithm'], 'heuristic': run['heuristic'],
        'weight': run['weight'], 'tie_break': run['tie_break']}]
    if not 1 <= len(runs) <= 4:
        raise Refused(f'a request runs one to four searches, not {len(runs)}')
    out, search_ms, write_ms = [], [], []
    for r in runs:
        t0 = time.perf_counter()
        result = search(graph, start, goal, r['algorithm'], r['heuristic'],
                        weight=r.get('weight'),
                        tie_break=r.get('tie_break', 'low_h'))
        search_ms.append(_ms(t0))
        t0 = time.perf_counter()
        prov = bundle.make_provenance('glass-box', tool=TOOL)
        nb = bundle.Bundle.from_run(result, new_map, inputs, prov)
        m_out, a_out, digest = _serialise(nb)
        _remember(digest, nb)
        write_ms.append(_ms(t0))
        out.append({'manifest': m_out, 'arrays_file': a_out,
                    'arrays_name': 'arrays.bin', 'content_hash': digest})

    optimal, optimal_ms = None, 0.0
    if req.get('optimal'):
        t0 = time.perf_counter()
        # the optimum on identical inputs, from coco_lab's own Dijkstra
        opt = search(graph, start, goal, 'dijkstra', 'zero')
        optimal = opt.cost
        optimal_ms = _ms(t0)
    return {
        'bundles': out, 'optimal_cost': optimal,
        'coco_lab_version': coco_lab.__version__,
        'python_version': sys.version.split()[0],
        'timings': {'load_bundle_ms': load_ms, 'search_ms': sum(search_ms),
                    'write_bundle_ms': sum(write_ms),
                    'optimal_ms': optimal_ms, 'runs': len(runs),
                    'total_ms': _ms(t_all)},
    }


# -- Lab 2: localisation -------------------------------------------------------

#: The Sketch world's default odometry alphas (coco_lab.sketch.Noise) are
#: what the motion-noise slider scales; the filters are told the same.
_ALPHA0 = Noise().odom_alphas[0]
#: The filters never assume less range noise than COCO's AMCL does
#: (sigma_hit 0.2 m, gazebo_models/config/nav2_params.yaml).
_SIGMA_FLOOR = 0.2
_LOC_CACHE = OrderedDict()
_SMAPS = OrderedDict()


def _load_loc(manifest_bytes, arrays_name, arrays_file):
    """Return ``(LocBundle, load_ms)``, validated by coco_lab, cached."""
    manifest_bytes = _bytes(manifest_bytes)
    claimed = json.loads(manifest_bytes).get('content_hash')
    if claimed in _LOC_CACHE:
        _LOC_CACHE.move_to_end(claimed)
        return _LOC_CACHE[claimed], 0.0
    t0 = time.perf_counter()
    work = tempfile.mkdtemp(prefix='lab_loc_')
    try:
        with open(os.path.join(work, 'manifest.json'), 'wb') as f:
            f.write(manifest_bytes)
        with open(os.path.join(work, arrays_name), 'wb') as f:
            f.write(_bytes(arrays_file))
        lb = locbundle.load_loc_bundle(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _LOC_CACHE[claimed] = lb
    while len(_LOC_CACHE) > 4:
        _LOC_CACHE.popitem(last=False)
    return lb, _ms(t0)


def _smap(lab_map):
    key = lab_map.content_hash()
    if key not in _SMAPS:
        _SMAPS[key] = SketchMap(lab_map)
        while len(_SMAPS) > 3:
            _SMAPS.popitem(last=False)
    return _SMAPS[key]


def _num(req, key, lo, hi):
    v = req.get(key)
    if not isinstance(v, (int, float)) or isinstance(v, bool) or \
            not (lo <= v <= hi):
        raise Refused(f'{key} must be a number from {lo} to {hi}')
    return v


def localise(request_json, manifest, arrays_name, arrays_file):
    """
    Rerun the current localisation scenario with the learner's settings.

    ``request_json``: ``{particles, motion_noise, sensor_sigma, injection,
    alpha_slow, alpha_fast, inject_fraction, init, kidnap: null | {t, to:
    [x, y, yaw]}, seed, filter_seed}``. One Sketch world is simulated from
    the bundle's scenario with these settings, and on it coco_lab runs
    MCL (the learner's settings), the same MCL with injection OFF when
    injection is on (COCO's AMCL setting, for the A/B), and the EKF -- all
    on identical inputs, in ONE bundle.
    """
    t_all = time.perf_counter()
    req = json.loads(request_json)
    lb, load_ms = _load_loc(manifest, arrays_name, arrays_file)
    n = int(_num(req, 'particles', 10, 2000))
    scale = _num(req, 'motion_noise', 0.0, 5.0)
    sigma = _num(req, 'sensor_sigma', 0.0, 0.5)
    inj = req.get('injection')
    if inj not in ('none', 'augmented', 'fixed'):
        raise Refused('injection must be none, augmented or fixed')
    a_slow = _num(req, 'alpha_slow', 0.0, 1.0)
    a_fast = _num(req, 'alpha_fast', 0.0, 1.0)
    frac = _num(req, 'inject_fraction', 0.0, 0.5)
    init = req.get('init')
    if init not in ('tracking', 'global'):
        raise Refused('init must be tracking or global')
    seed = int(_num(req, 'seed', 0, 2 ** 31 - 1))
    fseed = int(_num(req, 'filter_seed', 0, 2 ** 31 - 1))
    old = lb.world.scenario
    d = old.to_dict()
    alphas = [_ALPHA0 * scale] * 4
    d['noise'] = {'odom_alphas': alphas, 'range_sigma': sigma}
    d['seed'] = seed
    kid = req.get('kidnap')
    if kid is None:
        d['kidnap'] = None
    else:
        t = _num(kid, 't', 0.5, old.max_time)
        to = kid.get('to')
        if not (isinstance(to, list) and len(to) == 3 and all(
                isinstance(v, (int, float)) for v in to)):
            raise Refused('the kidnap needs a place: (x, y, yaw)')
        d['kidnap'] = Kidnap(float(t), tuple(float(v) for v in to)).to_dict()
    sc = Scenario.from_dict(d)
    smap = _smap(lb.lab_map)
    if kid is not None and smap.clearance(*sc.kidnap.to[:2]) < 0.11:
        raise Refused('that kidnap target is inside or against a wall: '
                      'pick a free spot')
    hit = max(_SIGMA_FLOOR, sigma)
    mcl = MCLParams(particles=n, alphas=tuple(alphas), sigma_hit=hit,
                    init=init, injection=inj, alpha_slow=a_slow,
                    alpha_fast=a_fast, inject_fraction=frac, seed=fseed)
    runs = [('mcl', 'mcl', mcl)]
    if inj != 'none':
        runs.append(('mcl_coco', 'mcl', MCLParams(
            particles=n, alphas=tuple(alphas), sigma_hit=hit, init=init,
            injection='none', seed=fseed)))
    runs.append(('ekf', 'ekf', EKFParams(alphas=tuple(alphas),
                                          sigma_hit=hit, init=init)))
    t0 = time.perf_counter()
    try:
        nb = locbundle.LocBundle.compute(
            lb.lab_map, sc, runs, bundle.make_provenance(
                'sketch', seed=seed, tool=TOOL), smap=smap)
    except ValueError as exc:
        raise Refused(str(exc)) from None
    compute_ms = _ms(t0)
    t0 = time.perf_counter()
    m_out, name, a_out, digest = nb.to_bytes('none')
    _LOC_CACHE[digest] = nb
    write_ms = _ms(t0)
    return {
        'bundles': [{'manifest': m_out, 'arrays_file': a_out,
                     'arrays_name': name, 'content_hash': digest}],
        'optimal_cost': None,
        'coco_lab_version': coco_lab.__version__,
        'python_version': sys.version.split()[0],
        'timings': {'load_bundle_ms': load_ms, 'search_ms': compute_ms,
                    'write_bundle_ms': write_ms, 'optimal_ms': 0.0,
                    'runs': len(runs), 'total_ms': _ms(t_all)},
    }
