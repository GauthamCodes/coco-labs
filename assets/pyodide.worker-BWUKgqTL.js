let e=null;async function t(e){let t=await crypto.subtle.digest(`SHA-256`,e);return[...new Uint8Array(t)].map(e=>e.toString(16).padStart(2,`0`)).join(``)}async function n(e){let n={},r=performance.now(),i=await(await import(
/* @vite-ignore */
`${e.pyodideIndexUrl}pyodide.mjs`)).loadPyodide({indexURL:e.pyodideIndexUrl});n.pyodide_load_ms=performance.now()-r,r=performance.now(),await i.loadPackage([`micropip`]),n.micropip_ms=performance.now()-r,r=performance.now();let a=await fetch(e.wheelUrl,{credentials:`omit`});if(!a.ok)throw Error(`cannot fetch the coco_lab wheel: HTTP ${a.status}`);let o=new Uint8Array(await a.arrayBuffer()),s=await t(o);if(s!==e.wheelSha256)throw Error(`coco_lab wheel sha256 ${s} is not the catalog's ${e.wheelSha256}`);let c=e.wheelUrl.split(`/`).pop();return i.FS.mkdirTree(`/tmp/wheels`),i.FS.writeFile(`/tmp/wheels/${c}`,o),await i.pyimport(`micropip`).install(`emfs:/tmp/wheels/${c}`),n.wheel_install_ms=performance.now()-r,r=performance.now(),i.FS.mkdirTree(`/home/pyodide/lab`),i.FS.writeFile(`/home/pyodide/lab/lab_recompute.py`,`# Copyright 2026 Gautham Anil
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

1. takes the page's CURRENT bundle, validated by \`\`coco_lab\`\`'s own
   \`\`load_bundle\`\` (full structural + semantic validation) -- or, when the
   same content hash was validated earlier in this worker, that bundle;
2. applies the painted strokes to the map (occupied or free, cell by cell)
   and refuses one that covers the start or the goal;
3. reruns \`\`coco_lab.search.search\`\` once per requested run (one for an
   edit or a settings change, two to four for a race), with the settings
   the page chose and the bundle's start, goal and move model;
4. when asked, runs the same search with \`\`'dijkstra'\`\` for the optimum;
5. serialises each result with \`\`coco_lab\`\`'s own \`\`Bundle.validate\`\`,
   \`\`Bundle.manifest\`\` and \`\`Bundle.arrays\`\` -- exactly what
   \`\`write_bundle\`\` writes, without the file system -- as a \`\`glass-box\`\`
   bundle whose provenance says \`\`tool='lab_web/pyodide'\`\`.

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
    Return \`\`(bundle, load_ms)\`\` for the page's current bundle.

    A bundle not seen before goes through \`\`coco_lab.bundle.load_bundle\`\`,
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
    """Validate, then return \`\`(manifest bytes, arrays bytes, hash)\`\`."""
    b.validate()
    manifest = b.manifest('none')
    raw = b''.join(d for _, _, d in b.arrays())
    return (bundle.canonical_json(manifest).encode('utf-8'), raw,
            manifest['content_hash'])


def _paint(m, strokes, protect):
    """Return \`\`m\`\` with \`\`strokes\`\` applied; refuse covering \`\`protect\`\`."""
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

    \`\`request_json\`\` is \`\`{"strokes": [{"value": "occupied"|"free",
    "cells": [[r, c], ...]}, ...], "connectivity": 4|8|null, "runs":
    [{"algorithm", "heuristic", "weight", "tie_break"}, ...],
    "optimal": bool}\`\`.
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
    """Return \`\`(LocBundle, load_ms)\`\`, validated by coco_lab, cached."""
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
    if not isinstance(v, (int, float)) or isinstance(v, bool) or \\
            not (lo <= v <= hi):
        raise Refused(f'{key} must be a number from {lo} to {hi}')
    return v


def localise(request_json, manifest, arrays_name, arrays_file):
    """
    Rerun the current localisation scenario with the learner's settings.

    \`\`request_json\`\`: \`\`{particles, motion_noise, sensor_sigma, injection,
    alpha_slow, alpha_fast, inject_fraction, init, kidnap: null | {t, to:
    [x, y, yaw]}, seed, filter_seed}\`\`. One Sketch world is simulated from
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


# -- Lab 3: Map ------------------------------------------------------------------

_SLAM_CACHE = OrderedDict()


def _load_slam(manifest_bytes, arrays_name, arrays_file):
    """Return \`\`(SlamBundle, load_ms)\`\`, validated by coco_lab, cached."""
    from coco_lab import slambundle
    manifest_bytes = _bytes(manifest_bytes)
    claimed = json.loads(manifest_bytes).get('content_hash')
    if claimed in _SLAM_CACHE:
        _SLAM_CACHE.move_to_end(claimed)
        return _SLAM_CACHE[claimed], 0.0
    t0 = time.perf_counter()
    work = tempfile.mkdtemp(prefix='lab_map_')
    try:
        with open(os.path.join(work, 'manifest.json'), 'wb') as f:
            f.write(manifest_bytes)
        with open(os.path.join(work, arrays_name), 'wb') as f:
            f.write(_bytes(arrays_file))
        sb = slambundle.load_slam_bundle(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _SLAM_CACHE[claimed] = sb
    while len(_SLAM_CACHE) > 3:
        _SLAM_CACHE.popitem(last=False)
    return sb, _ms(t0)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def mapping(request_json, manifest, arrays_name, arrays_file):
    """
    Rerun the current Sketch mapping world with the learner's settings.

    \`\`request_json\`\`: \`\`{clicks: [[x, y], ...], noise_scale, particles,
    fastslam_seed, seed, runs: [run ids]}\`\`. coco_lab plans the drive
    through the clicks (Lab 1's A*, \`\`map_teaching.plan_route\`\`), simulates
    ONE Sketch world from the current bundle's start and LiDAR, and runs
    every requested algorithm on it -- identical inputs, in ONE bundle,
    scored by \`\`coco_lab.mapeval\`\`.
    """
    from coco_lab import map_teaching, mapworld, slambundle
    t_all = time.perf_counter()
    req = json.loads(request_json)
    sb, load_ms = _load_slam(manifest, arrays_name, arrays_file)
    if sb.world.source != 'sketch':
        raise Refused('a recorded drive cannot be driven again: it is a '
                      'recording')
    clicks = req.get('clicks')
    if not (isinstance(clicks, list) and
            1 <= len(clicks) <= map_teaching.MAX_CLICKS and
            all(isinstance(c, list) and len(c) == 2 and
                all(_is_num(v) for v in c) for c in clicks)):
        raise Refused(f'the drive needs 1 to {map_teaching.MAX_CLICKS} '
                      f'waypoints')
    scale = _num(req, 'noise_scale', 0.0, 5.0)
    particles = int(_num(req, 'particles', 2, 100))
    fseed = int(_num(req, 'fastslam_seed', 0, 2 ** 31 - 1))
    seed = int(_num(req, 'seed', 0, 2 ** 31 - 1))
    runs = req.get('runs')
    if not (isinstance(runs, list) and runs and len(set(runs)) == len(runs)
            and all(r in map_teaching.RUN_IDS for r in runs)):
        raise Refused(f'runs must be some of {list(map_teaching.RUN_IDS)}')
    ids = [r for r in map_teaching.RUN_IDS if r in runs]
    smap = _smap(sb.lab_map)
    try:
        sc = map_teaching.scenario_for(sb.world.scenario, smap,
                                       [tuple(c) for c in clicks], scale,
                                       seed)
    except ValueError as exc:
        raise Refused(str(exc)) from None
    t0 = time.perf_counter()
    try:
        world = mapworld.from_sketch(sb.lab_map, sc, sb.world.landmark_spec,
                                     smap=smap)
        specs = map_teaching.run_specs(scale=scale, particles=particles,
                                       fastslam_seed=fseed, ids=ids)
        nb = slambundle.SlamBundle.compute(
            sb.lab_map, world, specs, bundle.make_provenance(
                'sketch', seed=seed, tool=TOOL), tol=sb.tol)
    except ValueError as exc:
        raise Refused(str(exc)) from None
    compute_ms = _ms(t0)
    t0 = time.perf_counter()
    m_out, name, a_out, digest = nb.to_bytes('none')
    _SLAM_CACHE[digest] = nb
    write_ms = _ms(t0)
    return {
        'bundles': [{'manifest': m_out, 'arrays_file': a_out,
                     'arrays_name': name, 'content_hash': digest}],
        'optimal_cost': None,
        'coco_lab_version': coco_lab.__version__,
        'python_version': sys.version.split()[0],
        'timings': {'load_bundle_ms': load_ms, 'search_ms': compute_ms,
                    'write_bundle_ms': write_ms, 'optimal_ms': 0.0,
                    'runs': len(specs), 'total_ms': _ms(t_all)},
    }


# -- Lab 4: search -----------------------------------------------------------------

def search_lab(request_json, manifest, arrays_name, arrays_file):
    """
    Rerun Lab 4's searches on the current problem with the learner's settings.

    \`\`request_json\`\`: \`\`{prior: [w per region], detection, true_detection,
    truth: index | null, order: [indices] (the learner's, may be partial or
    empty), seed}\`\`. coco_lab builds the problem from the CURRENT bundle's
    (validated by \`\`searchbundle.load_search_bundle\`\`) with the learner's
    prior and detection, and runs -- on ONE problem, ONE placement, ONE
    seed (rule 6) -- the robot's policy, the learner's order (if any) and
    the two teaching policies. Every expected cost on the page is in the
    returned bundle's summaries (\`\`plan\`\`), computed here by coco_lab.
    """
    from coco_lab import regionsearch as rs, searchbundle as sbm
    import dataclasses
    t_all = time.perf_counter()
    req = json.loads(request_json)
    t0 = time.perf_counter()
    work = tempfile.mkdtemp(prefix='lab_search_')
    try:
        with open(os.path.join(work, 'manifest.json'), 'wb') as f:
            f.write(_bytes(manifest))
        with open(os.path.join(work, arrays_name), 'wb') as f:
            f.write(_bytes(arrays_file))
        sb = sbm.load_search_bundle(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    load_ms = _ms(t0)
    p = sb.problem
    n = p.n
    prior = req.get('prior')
    if not (isinstance(prior, list) and len(prior) == n
            and all(_is_num(w) and w >= 0 for w in prior) and sum(prior) > 0):
        raise Refused(f'the prior needs {n} non-negative weights, not all '
                      f'zero')
    d = _num(req, 'detection', 0.5, 1.0)
    td = _num(req, 'true_detection', 0.0, 1.0)
    seed = int(_num(req, 'seed', 0, 2 ** 31 - 1))
    truth = req.get('truth')
    if truth is not None and not (isinstance(truth, int) and 0 <= truth < n):
        raise Refused('the target must stand in one of the bays')
    order = req.get('order') or []
    if not (isinstance(order, list) and len(set(order)) == len(order)
            and all(isinstance(i, int) and 0 <= i < n for i in order)):
        raise Refused('your order must name each bay at most once')
    try:
        problem = dataclasses.replace(
            p, detection=tuple(d for _ in range(n)), prior=rs.normalise(prior))
        problem.validate()
    except rs.SearchError as exc:
        raise Refused(str(exc)) from None
    t0 = time.perf_counter()
    common = dict(seed=seed, true_detection=[td] * n)
    runs = [sbm.SearchRun('robot', 'sketch', rs.run_search(
        problem, 'expected_cost', truth, **common))]
    if order:
        runs.append(sbm.SearchRun('mine', 'sketch', rs.run_search(
            problem, 'given', truth, given_order=tuple(order), **common)))
    runs.append(sbm.SearchRun('nearest', 'sketch', rs.run_search(
        problem, 'nearest', truth, **common)))
    runs.append(sbm.SearchRun('likely', 'sketch', rs.run_search(
        problem, 'most_likely', truth, **common)))
    nb = sbm.SearchBundle(bundle.make_provenance('sketch', seed=seed,
                                                 tool=TOOL), problem, runs)
    nb.validate()
    compute_ms = _ms(t0)
    t0 = time.perf_counter()
    m_out, name, a_out, digest = nb.to_bytes('none')
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


# -- Lab 5: replanning (D* Lite) ------------------------------------------------

def replan_lab(request_json, manifest, arrays_name, arrays_file):
    """
    Rerun Lab 5's D* Lite episode with the learner's world.

    \`\`request_json\`\`: \`\`{seed: int | null, sense_radius, painted: [[row,
    col], ...]}\`\`. With a seed coco_lab builds \`\`replan.sketch_world(seed)\`\`;
    without one it reuses the CURRENT bundle's world (validated by
    \`\`movebundle.load_replan_bundle\`\`). \`\`painted\`\` cells become obstacles
    of the WORLD that the robot's map does not have -- the robot meets them
    only when it is close enough to see them. coco_lab drives the episode
    (\`\`replan.run_replan\`\`: D* Lite, and A* from scratch beside every
    round); the page only draws the bundle it returns.
    """
    from coco_lab import movebundle as mb, replan
    import dataclasses
    t_all = time.perf_counter()
    req = json.loads(request_json)
    t0 = time.perf_counter()
    work = tempfile.mkdtemp(prefix='lab_replan_')
    try:
        with open(os.path.join(work, 'manifest.json'), 'wb') as f:
            f.write(_bytes(manifest))
        with open(os.path.join(work, arrays_name), 'wb') as f:
            f.write(_bytes(arrays_file))
        _, world = mb.load_replan_bundle(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    load_ms = _ms(t0)
    sense = _num(req, 'sense_radius', 1.5, 6.0)
    seed = req.get('seed')
    if seed is not None:
        if not (isinstance(seed, int) and 0 <= seed <= 9999):
            raise Refused('the seed must be a whole number from 0 to 9999')
        world = replan.sketch_world(seed, sense_radius=sense)
    else:
        world = dataclasses.replace(world, sense_radius=sense,
                                    known=list(world.known),
                                    truth=list(world.truth))
    painted = req.get('painted') or []
    if not (isinstance(painted, list) and len(painted) <= 200):
        raise Refused('paint at most 200 cells')
    for cell in painted:
        if not (isinstance(cell, list) and len(cell) == 2
                and all(isinstance(v, int) for v in cell)
                and 0 <= cell[0] < world.height
                and 0 <= cell[1] < world.width):
            raise Refused('a painted cell is off the map')
        if tuple(cell) in (world.start, world.goal):
            raise Refused('the start and the goal must stay free')
        world.truth[cell[0] * world.width + cell[1]] = True
    t0 = time.perf_counter()
    try:
        res = replan.run_replan(world)
    except ValueError as exc:
        raise Refused(str(exc)) from None
    compute_ms = _ms(t0)
    t0 = time.perf_counter()
    prov = bundle.make_provenance('sketch', seed=seed, tool=TOOL)
    m_out, name, a_out, digest = mb.replan_bytes(res, prov, 'none')
    write_ms = _ms(t0)
    return {
        'bundles': [{'manifest': m_out, 'arrays_file': a_out,
                     'arrays_name': name, 'content_hash': digest}],
        'optimal_cost': None,
        'coco_lab_version': coco_lab.__version__,
        'python_version': sys.version.split()[0],
        'timings': {'load_bundle_ms': load_ms, 'search_ms': compute_ms,
                    'write_bundle_ms': write_ms, 'optimal_ms': 0.0,
                    'runs': len(res.rounds), 'total_ms': _ms(t_all)},
    }
`),i.runPython(`import sys
sys.path.insert(0, '/home/pyodide/lab')
import lab_recompute`),n.import_ms=performance.now()-r,{py:i,cold:n}}self.onmessage=async t=>{let r=t.data,i=`load`,a=(e,t=[])=>self.postMessage(e,t);try{let t=e===null;e??=n(r);let{py:o,cold:s}=await e;i=`edit`;let c=r.type===`localise`?`lab_recompute.localise`:r.type===`mapping`?`lab_recompute.mapping`:r.type===`search`?`lab_recompute.search_lab`:r.type===`replan`?`lab_recompute.replan_lab`:`lab_recompute.recompute`,l=o.runPython(c)(JSON.stringify(r.spec),r.manifest,r.arraysName,r.arraysFile),u=l.toJs({dict_converter:Object.fromEntries});l.destroy();let d=u.bundles.map(e=>({manifest:new Uint8Array(e.manifest),arraysFile:new Uint8Array(e.arrays_file),arraysName:e.arrays_name,contentHash:e.content_hash}));a({id:r.id,ok:!0,bundles:d,optimalCost:u.optimal_cost??null,cocoLabVersion:u.coco_lab_version,pythonVersion:u.python_version,pyodideVersion:o.version,timings:{...t?s:{},...u.timings}},d.flatMap(e=>[e.manifest.buffer,e.arraysFile.buffer]))}catch(t){let n=t.message??String(t);i===`load`&&(e=null);let o=n.trim().split(`
`).filter(Boolean).pop()??n,s=/^(lab_recompute\.)?Refused: /.test(o);a({id:r.id,ok:!1,stage:i,refused:s,error:i===`edit`?o.replace(/^(lab_recompute\.)?\w+: /,``):n})}};