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
Build what the site serves: every bundle validated by ``coco_lab`` first.

Writes ``lab_web/public/generated/`` (gitignored):

``bundles/<id>/``
    Byte-exact copies of the committed bundles the site shows (the five
    golden teaching traces and the three 1C recorded runs), plus two
    glass-box bundles ``coco_lab`` computes here: the arena at 0.10 m
    (the edit map) and the arena at its native 0.05 m (the full-arena
    Dijkstra benchmark, 283k events). Both use Phase 1B's map, model,
    start and goal (``docs/data/lab1b/resolution.py``).
``py/coco_lab-<v>-py3-none-any.whl``
    The pure-Python wheel the Pyodide worker installs.
``catalog.json``
    One entry per bundle: its content hash (the browser draws a bundle
    only if its hash is here, or if the worker just made it), source
    kind, what validated it, and the evidence it cites.

Every bundle is loaded with ``coco_lab.bundle.load_bundle`` -- the full
structural AND semantic validation, which the browser does not repeat --
and every glass-box bundle is re-run with ``bundle.replay``; a bundle that
does not reproduce is refused and the build fails. Nothing is repaired.

Usage (from the repository root; ``coco_lab`` importable, no ROS)::

    python3 lab_web/tools/build_catalog.py [--wheel PATH] [--no-benchmark]
"""

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import coco_lab  # noqa: E402
from coco_lab import bundle, maps  # noqa: E402
from coco_lab.graph import HEURISTICS  # noqa: E402
from coco_lab.heuristics import analyse, MoveModel, SQRT2  # noqa: E402
from coco_lab.search import (ALGORITHMS, search,  # noqa: E402
                             suboptimality_bound, TIE_BREAKS)
import build_localise  # noqa: E402
import common  # noqa: E402

OUT = os.path.join(common.LAB_WEB, 'public', 'generated')
RESOLUTION_PY = os.path.join(common.REPO, 'docs', 'data', 'lab1b',
                             'resolution.py')
TOOL = 'lab_web/tools/build_catalog.py'

TEACHING = 'Teaching traces (glass-box)'
RECORDED = 'Recorded real runs (Phase 1C)'
ARENA = 'Arena traces (glass-box)'

GOLDEN_CITE = ('coco_lab/test/golden_bundles.py; '
               'coco_lab/test/test_bundle.py::'
               'test_golden_bundles_load_validate_and_replay')
LAB1C_CITE = ('docs/RESULTS.md, "COCO Lab Phase 1C" > '
              '"The three real runs (measured)"')
ARENA_CITE = ('docs/RESULTS.md, "COCO Lab Phase 1B" > "Bundles (measured)"; '
              'docs/data/lab1b/resolution.py')

#: (id, repository-relative dir, title, group, citation)
SERVED_INFO = [
    ('astar_open', 'coco_lab/test/fixtures/bundles/astar_open',
     'A* on an open 20 x 20 grid', TEACHING, GOLDEN_CITE),
    ('dijkstra_cost_field_gz',
     'coco_lab/test/fixtures/bundles/dijkstra_cost_field_gz',
     'Dijkstra across a cost field', TEACHING, GOLDEN_CITE),
    ('weighted_astar_greedy_trap',
     'coco_lab/test/fixtures/bundles/weighted_astar_greedy_trap',
     'Weighted A* (w = 2) in the greedy trap', TEACHING, GOLDEN_CITE),
    ('bfs_no_path', 'coco_lab/test/fixtures/bundles/bfs_no_path',
     'BFS with no path to the goal', TEACHING, GOLDEN_CITE),
    ('astar_turn_trap_heading',
     'coco_lab/test/fixtures/bundles/astar_turn_trap_heading',
     'A* on a (cell, heading) graph: the turn trap', TEACHING, GOLDEN_CITE),
    ('lab1c_astar', 'docs/data/lab1c/bundles/astar',
     'A* driven by COCO (recorded run)', RECORDED, LAB1C_CITE),
    ('lab1c_dijkstra', 'docs/data/lab1c/bundles/dijkstra',
     'Dijkstra driven by COCO (recorded run)', RECORDED, LAB1C_CITE),
    ('lab1c_greedy', 'docs/data/lab1c/bundles/greedy',
     'Greedy best-first driven by COCO (recorded run)', RECORDED,
     LAB1C_CITE),
]
SERVED = [(bid, rel) for bid, rel, *_ in SERVED_INFO]


def _resolution_module():
    spec = importlib.util.spec_from_file_location('lab1b_resolution',
                                                  RESOLUTION_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args):
    return subprocess.run(['git', '-C', common.REPO, *args],
                          capture_output=True, text=True, timeout=10,
                          check=True).stdout.strip()


def _source_time():
    """Return HEAD's commit time as ``YYYY-MM-DDTHH:MM:SSZ``, or None."""
    try:
        epoch = int(_git('log', '-1', '--format=%ct'))
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return datetime.datetime.fromtimestamp(
        epoch, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def arena_bundle(native: bool):
    """Return the Phase 1B full-arena Dijkstra bundle (native or 0.10 m)."""
    res = _resolution_module()
    m = maps.load_nav2(res.NAV_YAML, map_id='coco_navigation/nav2_saved')
    if not native:
        m = m.downsample(2)
    s, g = res.nearest_free(m, res.START_XY), res.nearest_free(m, res.GOAL_XY)
    model = dict(res.MODEL)
    grid = m.to_grid(**model)
    result = search(grid, s, g, 'dijkstra')
    created = _source_time() or '1970-01-01T00:00:00Z'
    prov = bundle.make_provenance(
        'glass-box', git=bundle.git_provenance(common.REPO),
        created_utc=created, tool=TOOL)
    return bundle.Bundle.from_run(result, m, {'start': s, 'goal': g,
                                              'model': model}, prov)


LAB1C_ASTAR = os.path.join(common.REPO, 'docs', 'data', 'lab1c', 'bundles',
                           'astar')
COSTMAP_CITE = ('docs/data/lab1c/bundles/astar (the recorded '
                '/global_costmap/costmap_raw snapshot), downsampled x2 by '
                'coco_lab.maps.LabMap.downsample; docs/RESULTS.md, '
                '"COCO Lab Phase 1C"')
ROBOT_PY = os.path.join(common.REPO, 'coco_config', 'coco_config', 'robot.py')

#: The weighted-A* slider's positions: every bound the page shows is one
#: coco_lab computed here, at one of these weights.
SLIDER_WEIGHTS = [i / 4 for i in range(21)]


def costmap_bundle():
    """
    Return the ladder's third rung: A* on Nav2's own inflated costmap.

    The map is the global costmap_raw snapshot recorded in the 1C A* run,
    downsampled x2 (0.10 m, the edit map's resolution) by coco_lab. The
    move model, algorithm and heuristic are that run's; the start and goal
    are its cells, carried through world coordinates to the nearest free
    coarse cell.
    """
    rec = bundle.load_bundle(LAB1C_ASTAR)
    run = rec.run
    fine = rec.lab_map
    m = fine.downsample(2, map_id=f'{fine.id}@x2')
    res = _resolution_module()
    s = res.nearest_free(m, fine.cell_centre(*run['start']))
    g = res.nearest_free(m, fine.cell_centre(*run['goal']))
    model = dict(run['model'])
    grid = m.to_grid(**model)
    result = search(grid, s, g, run['algorithm'], run['heuristic'],
                    tie_break=run['tie_break'])
    created = _source_time() or '1970-01-01T00:00:00Z'
    prov = bundle.make_provenance(
        'glass-box', git=bundle.git_provenance(common.REPO),
        created_utc=created, tool=TOOL)
    return bundle.Bundle.from_run(result, m, {'start': s, 'goal': g,
                                              'model': model}, prov)


def settings_analysis(diagonal_costs):
    """
    Return coco_lab's verdicts for the settings panel, for every move model.

    For each heuristic, connectivity and diagonal cost: the admissibility
    and consistency report (``coco_lab.heuristics.analyse``) and the
    suboptimality bound of each algorithm (``suboptimality_bound``), for
    weighted A* at every slider weight. The page only looks these up.
    """
    out = []
    for connectivity in (4, 8):
        diags = [SQRT2] if connectivity == 4 else sorted(diagonal_costs)
        for diag in diags:
            mm = MoveModel(connectivity, diag)
            for h in HEURISTICS:
                rep = analyse(h, mm)
                bounds = {a: suboptimality_bound(a, rep)
                          for a in ALGORITHMS if a != 'weighted_astar'}
                bounds['weighted_astar'] = [
                    suboptimality_bound('weighted_astar', rep, weight=w)
                    for w in SLIDER_WEIGHTS]
                out.append({
                    'connectivity': connectivity,
                    'diagonal_cost': diag if connectivity == 8 else None,
                    'heuristic': h, 'admissible': rep.admissible,
                    'consistent': rep.consistent, 'reason': rep.reason,
                    'witness': (list(rep.witness) if rep.witness else None),
                    'bounds': bounds})
    return {
        'by': (f'coco_lab {coco_lab.__version__} heuristics.analyse and '
               f'search.suboptimality_bound'),
        'cite': ('coco_lab/test/test_heuristics.py; coco_lab/test/'
                 'test_properties.py::'
                 'test_the_reported_suboptimality_bound_holds'),
        'algorithms': list(ALGORITHMS), 'heuristics': list(HEURISTICS),
        'tie_breaks': list(TIE_BREAKS), 'weights': SLIDER_WEIGHTS,
        'models': out,
    }


def robot_footprint():
    """
    Return COCO's ground footprint, derived from coco_config's constants.

    ``robot.py`` is loaded by path (it needs only ``math`` and ``typing``),
    so this runs without ROS. The footprint is the rectangle enclosing the
    chassis and the four wheels: length ``max(chassis length, wheelbase +
    2 x wheel radius)``, width ``max(chassis width, track + wheel width)``,
    centred on ``base_footprint``.
    """
    spec = importlib.util.spec_from_file_location('coco_robot', ROBOT_PY)
    r = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r)
    length = max(r.CHASSIS_SIZE[0], r.WHEELBASE + 2 * r.WHEEL_RADIUS)
    width = max(r.CHASSIS_SIZE[1], r.WHEEL_SEPARATION + r.WHEEL_WIDTH)
    return {
        'length_m': round(length, 6), 'width_m': round(width, 6),
        'source': 'coco_config/coco_config/robot.py',
        'derivation': (
            f'length = max(CHASSIS_SIZE[0] {r.CHASSIS_SIZE[0]}, WHEELBASE '
            f'{r.WHEELBASE} + 2 x WHEEL_RADIUS {r.WHEEL_RADIUS}); width = '
            f'max(CHASSIS_SIZE[1] {r.CHASSIS_SIZE[1]}, WHEEL_SEPARATION '
            f'{r.WHEEL_SEPARATION} + WHEEL_WIDTH {r.WHEEL_WIDTH}); centred '
            f'on base_footprint (derived)'),
    }


#: The map ladder: the same question asked of ever more real maps.
LADDER = [
    {'rung': 1, 'id': 'astar_open', 'title': 'Teaching grid',
     'note': '20 x 20, no scale: a cell is a cell'},
    {'rung': 2, 'id': 'arena_0_10m', 'title': 'Arena occupancy',
     'note': 'the arena Nav2 map at 0.10 m: walls only'},
    {'rung': 3, 'id': 'costmap_0_10m', 'title': 'Inflated costmap',
     'note': "Nav2's own global costmap from a real run: walls grown by the "
             'inflation layer, cost rising near them'},
]


RESULTS_MD = os.path.join(common.REPO, 'docs', 'RESULTS.md')
ISRO_MD = os.path.join(common.REPO, 'docs', 'labs', 'ISRO_INVESTIGATION.md')
CONFORMANCE = os.path.join(common.REPO, 'docs', 'data', 'lab1c', 'conformance')
ISRO_JSON = os.path.join(common.REPO, 'docs', 'data', 'lab1b', 'isro_experiment.json')


def _in_doc(path, *needles):
    """Refuse to ship a figure that the document it cites does not print."""
    with open(path, encoding='utf-8') as f:
        text = f.read()
    for n in needles:
        if n not in text:
            raise SystemExit(f'{path} does not contain {n!r}; the exhibit cites it')


def exhibit_data():
    """
    The exhibit "The A* myth, twice", from committed evidence only.

    (a) is run live in the browser; its claim cites the 1,000-map property.
    (b) comes from 1C's conformance record; M3's own figures are copied from
    RESULTS.md and checked to be printed there. (c) comes from 1B's
    controlled experiment; the report's Table 1 figures are copied from the
    investigation and checked to be printed there. Nothing is filled in:
    1C recorded the analogue's lengths, not its paths, so none is drawn.
    """
    with open(os.path.join(CONFORMANCE, 'conformance.json')) as f:
        conf = json.load(f)
    with open(os.path.join(CONFORMANCE, 'conformance_summary.json')) as f:
        summ = json.load(f)
    with open(ISRO_JSON) as f:
        isro = json.load(f)
    a3 = conf['m3_analogue']
    _in_doc(RESULTS_MD, '| **GridBased** (SmacPlanner2D, A\\*) | **3.165** |',
            '| NavFn (Dijkstra) | 3.373 |', "**M3's 6.2 % is neither reproduced nor refuted here**")
    _in_doc(ISRO_MD, '| A\\* | 2.64 | 1.59 | 1.2 |', '| Dijkstra | 2.55 | 1.73 | 6.0 |')
    c1c = 'docs/RESULTS.md, "COCO Lab Phase 1C" > '
    lng, sht = isro['long'], isro['short']
    return {
        'schema': 'lab_web.exhibit', 'version': '1.0',
        'a': {
            'property': ('coco_lab/test/test_properties.py::'
                         'test_astar_cost_equals_dijkstra_with_admissible_heuristic'),
            'property_maps': 1000,
            'counter': ('coco_lab/test/test_heuristics.py::'
                        'test_an_inadmissible_heuristic_makes_astar_suboptimal'),
            'live': {'bundle': 'weighted_astar_greedy_trap', 'heuristic': 'octile',
                     'connectivity': 8},
            'real_stack': {'astar_equals_dijkstra_C1': summ['astar_equals_dijkstra_C1'],
                           'of': summ['valid'],
                           'cite': c1c + '"Conformance: coco_lab vs SmacPlanner2D vs NavFn"'},
        },
        'b': {
            'm3': {'smac_m': 3.165, 'navfn_m': 3.373,
                   'cite': ('docs/RESULTS.md, "A — SmacPlanner2D and the evidence '
                            'for it"; gazebo_models/scripts/plan_compare.py'),
                   'status': c1c + '"NavFn and M3 (the 6.2 %)"'},
            'analogue': {
                'start_world': a3['start_world'], 'goal_world': a3['goal_world'],
                'rows': [
                    {'path': 'SmacPlanner2D, returned (smoothed)',
                     'L': a3['nav2']['GridBased']['L'], 'poses': a3['nav2']['GridBased']['poses']},
                    {'path': 'NavFn, use_astar: false', 'L': a3['nav2']['NavFn']['L'],
                     'poses': a3['nav2']['NavFn']['poses']},
                    {'path': 'NavFn, use_astar: true', 'L': a3['nav2']['NavFnAStar']['L'],
                     'poses': a3['nav2']['NavFnAStar']['poses']},
                    {'path': "SmacPlanner2D raw A* (unsmoothed_plan)", 'L': a3['smac_raw']['L'],
                     'poses': a3['smac_raw']['poses'], 'E': a3['smac_raw']['E']},
                    {'path': "coco_lab C1 optimum (cell path)", 'L': a3['lab']['C1_dijkstra']['L'],
                     'poses': a3['lab']['C1_dijkstra']['cells'], 'E': a3['lab']['C1_dijkstra']['E']},
                ],
                'paths_recorded': False,
                'cite': c1c + '"NavFn and M3 (the 6.2 %)"; docs/data/lab1c/conformance/conformance.json (m3_analogue)',
            },
            'fifty': {
                'n': summ['valid'],
                'e_within': summ['prediction']['within'],
                'e_applies': summ['prediction']['within'] + summ['prediction']['outside'],
                'e_gap_max': summ['E_gap_smac_raw_vs_C1']['max'],
                'navfn_vs_smac_L': summ['L_gap_NavFn_vs_smac'],
                'smac_vs_c1_L': summ['L_gap_smac_vs_C1'],
                'cite': c1c + '"Conformance: coco_lab vs SmacPlanner2D vs NavFn"; '
                        'docs/data/lab1c/conformance/conformance_summary.json',
            },
            'mechanism_cite': 'docs/DESIGN_DECISIONS.md (NavFn calcPath); README.md "What the 6.2 % is, and what it is not"',
        },
        'c': {
            'label': 'reconstruction',
            'label_why': ('Phase 1B examined a faithful recreation of the simulator, '
                          'transcribed from the internship report\'s code listing (commit '
                          '5aad7b3); no internship-era file or metrics CSV exists. 1B '
                          'recorded the result as a reconstruction.'),
            'table1': {'astar_steps': 2.64, 'dijkstra_steps': 2.55,
                       'astar_ms': 1.2, 'dijkstra_ms': 6.0,
                       'cite': 'docs/labs/ISRO_INVESTIGATION.md §6 (report §VIII, Table 1)'},
            'steps_ratio_long': lng['M1_smoothed_steps']['ratio_of_means'],
            'steps_ratio_short': sht['M1_smoothed_steps']['ratio_of_means'],
            'm1_cost': lng['M1_astar_vs_M1_dijkstra_cost'],
            'm1_vs_optimum': lng['M1_astar_vs_optimum'],
            'm2_cost': lng['M2_astar_vs_M2_dijkstra'],
            'time_ratio_long': [lng['M1_time_UNHASHED']['ratio_of_means_dijkstra_over_astar'],
                                lng['M1_time_UNHASHED']['ratio_of_medians_dijkstra_over_astar']],
            'live': {'bundle': 'astar_turn_trap_heading'},
            'cite': ('docs/labs/ISRO_INVESTIGATION.md §5 (MEASURED); '
                     'docs/data/lab1b/isro_experiment.json; docs/RESULTS.md, '
                     '"COCO Lab Phase 1B"'),
        },
    }


TRACKING_CITE = ('docs/RESULTS.md, "COCO Lab Phase 1C" > "The three real runs '
                 '(measured)"; coco_lab_ros/test/test_run_analysis.py::'
                 'test_tracking_error')


def tracking_series(path):
    """
    Return the per-sample tracking error of a recorded run, for the plot.

    Recomputed here from the bundle's own ground-truth and plan streams with
    1C's definition and code (``coco_lab_ros.run_analysis.window`` and
    ``coco_lab_ros.metrics.distance_to_polyline``, pure Python), and refused
    unless its statistics equal the ones the bundle recorded -- so the plot
    is the series behind the recorded mean / p95 / max, not a new one.
    """
    sys.path.insert(0, os.path.join(common.REPO, 'coco_lab_ros'))
    from coco_lab_ros import metrics, run_analysis  # noqa: E402 (pure Python)
    b = bundle.load_bundle(path)
    gs, ps = b.streams['gt'], b.streams['plan']
    gt = list(zip(gs['t'], gs['x'], gs['y'], gs['yaw']))
    plan_xy = list(zip(ps['x'], ps['y']))
    meta = b.recording['meta']
    t0, t1 = meta['window_sim']
    gw = run_analysis.window(gt, t0, t1)
    errs = [metrics.distance_to_polyline((s[1], s[2]), plan_xy) for s in gw]
    stats = metrics.tracking_stats(errs)
    if stats != meta['tracking_error_m']:
        raise SystemExit(f'{path}: recomputed tracking error {stats} is not the '
                         f'recorded {meta["tracking_error_m"]}')
    return {
        'schema': 'lab_web.tracking', 'version': '1.0',
        'definition': ('for every ground-truth sample between FollowPath '
                       'acceptance and result, its distance (map frame) to '
                       'the nearest point of the published plan'),
        'by': ('coco_lab_ros.run_analysis.window + metrics.distance_to_polyline '
               '(1C code), recomputed at site build from this bundle; its '
               'n / mean / p95 / max equal the recorded ones exactly'),
        'cite': TRACKING_CITE,
        'window_sim': [t0, t1],
        't': [round(s[0] - t0, 3) for s in gw],
        'e': [round(e, 5) for e in errs],
        'stats': stats,
    }


def _dir_bytes(path):
    return sum(os.path.getsize(os.path.join(path, n))
               for n in sorted(os.listdir(path)))


def _entry(bid, path, title, group, cite, editable):
    b = bundle.load_bundle(path)            # full tier (i) + (ii) validation
    with open(os.path.join(path, 'manifest.json'), 'rb') as f:
        manifest = json.loads(f.read())
    kind = b.provenance['source_kind']
    if kind == 'glass-box':
        r = bundle.replay(b)
        if not r.reproduced:
            raise SystemExit(f'{bid}: replay did not reproduce: {r.detail}')
        replay = f'reproduced: {r.detail}'
    else:
        replay = f'not replayable: a {kind} bundle does not record every ' \
                 f'input of its search'
    return {
        'id': bid, 'title': title, 'group': group,
        'path': f'bundles/{bid}/',
        'arrays_file': ('arrays.bin.gz'
                        if manifest['encoding']['compression'] == 'gzip'
                        else 'arrays.bin'),
        'bytes': _dir_bytes(path),
        'content_hash': manifest['content_hash'],
        'map_hash': manifest['map']['content_hash'],
        'source_kind': kind,
        'algorithm': manifest['run']['algorithm'],
        'events': len(b.trace),
        'editable': editable,
        'validated': {
            'by': f'coco_lab {coco_lab.__version__} bundle.load_bundle '
                  f'(structural and semantic)',
            'replay': replay},
        'citation': cite,
    }


def build_wheel(dest_dir):
    """Build coco_lab's wheel from a copy outside the source tree."""
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, 'coco_lab')
        shutil.copytree(os.path.join(common.REPO, 'coco_lab'), src,
                        ignore=shutil.ignore_patterns(
                            'build', '*.egg-info', '__pycache__', 'test'))
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(
            int(_git('log', '-1', '--format=%ct'))))
        pip = [sys.executable, '-m', 'pip']
        if subprocess.run(pip + ['--version'], capture_output=True,
                          check=False).returncode != 0:
            pip = ['python3', '-m', 'pip', '--python', sys.executable]
        subprocess.run(pip + ['wheel', '--no-deps', '-q', '-w', dest_dir,
                              src],
                       check=True, env=env)
    finally:
        shutil.rmtree(tmp)
    wheels = [n for n in os.listdir(dest_dir) if n.endswith('.whl')]
    if len(wheels) != 1:
        raise SystemExit(f'expected one wheel, found {wheels}')
    return os.path.join(dest_dir, wheels[0])


def build(out=OUT, wheel='build', with_benchmark=True, with_localise=True):
    """Build the site data under ``out``; return the catalog."""
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, 'bundles'))
    entries = []
    os.makedirs(os.path.join(out, 'tracking'))
    for bid, rel, title, group, cite in SERVED_INFO:
        dst = os.path.join(out, 'bundles', bid)
        shutil.copytree(os.path.join(common.REPO, rel), dst)
        entries.append(_entry(bid, dst, title, group, cite,
                              editable=group == TEACHING))
        if group == RECORDED:
            with open(os.path.join(out, 'tracking', f'{bid}.json'), 'w') as f:
                f.write(json.dumps(tracking_series(dst), sort_keys=True) + '\n')
            entries[-1]['tracking'] = f'tracking/{bid}.json'
    generated = [('arena_0_10m', False,
                  'Dijkstra across the arena at 0.10 m (edit map)', True)]
    if with_benchmark:
        generated.append(('arena_native', True,
                          'Dijkstra across the arena at 0.05 m '
                          '(benchmark)', False))
    for bid, native, title, editable in generated:
        dst = os.path.join(out, 'bundles', bid)
        bundle.write_bundle(arena_bundle(native), dst, 'gzip')
        entries.append(_entry(bid, dst, title, ARENA, ARENA_CITE, editable))
    dst = os.path.join(out, 'bundles', 'costmap_0_10m')
    bundle.write_bundle(costmap_bundle(), dst, 'gzip')
    entries.append(_entry('costmap_0_10m', dst,
                          "A* on Nav2's inflated costmap at 0.10 m",
                          ARENA, COSTMAP_CITE, True))
    diagonal_costs = {SQRT2}
    for e in entries:
        with open(os.path.join(out, e['path'], 'manifest.json')) as f:
            graph = json.load(f)['run']['graph']
        if graph.get('kind') == 'grid' and graph.get('connectivity') == 8:
            diagonal_costs.add(float(graph['diagonal_cost']))
    ids = {e['id'] for e in entries}
    missing = [r['id'] for r in LADDER if r['id'] not in ids]
    if missing:
        raise SystemExit(f'the map ladder names unserved bundles: {missing}')

    wheel_info = None
    if wheel is not None:
        pydir = os.path.join(out, 'py')
        os.makedirs(pydir)
        if wheel == 'build':
            path = build_wheel(pydir)
        else:
            path = os.path.join(pydir, os.path.basename(wheel))
            shutil.copyfile(wheel, path)
        with open(path, 'rb') as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        wheel_info = {'path': f'py/{os.path.basename(path)}',
                      'sha256': digest, 'bytes': os.path.getsize(path)}

    git = bundle.git_provenance(common.REPO)
    catalog = {
        'schema': 'coco_lab.catalog', 'version': '1.1',
        'coco_lab_version': coco_lab.__version__,
        'built_from': git, 'tool': TOOL,
        'wheel': wheel_info,
        'bundles': entries,
        # 1.1 (additive): what the settings panel, the ladder and the
        # footprint sweep read -- all computed here, never in the page
        'settings': settings_analysis(diagonal_costs),
        'ladder': LADDER,
        'footprint': robot_footprint(),
        'exhibit': 'exhibit.json',  # fetched only when the exhibit is opened
    }
    if with_localise:
        # 1.2 (additive): Lab 2, Localise -- bundles coco_lab computed and
        # replayed here, and the evidence its exhibits cite
        catalog['version'] = '1.2'
        catalog['localise'] = build_localise.localise_block(out)
    with open(os.path.join(out, 'exhibit.json'), 'w') as f:
        f.write(json.dumps(exhibit_data(), indent=1, sort_keys=True) + '\n')
    with open(os.path.join(out, 'catalog.json'), 'w') as f:
        f.write(json.dumps(catalog, indent=1, sort_keys=True) + '\n')
    return catalog


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--wheel', default='build',
                    help="a prebuilt wheel to serve, or 'build' (default)")
    ap.add_argument('--no-benchmark', action='store_true')
    ap.add_argument('--no-localise', action='store_true')
    args = ap.parse_args(argv)
    cat = build(args.out, args.wheel, not args.no_benchmark,
                not args.no_localise)
    for e in cat['bundles']:
        print(f"{e['id']:28s} {e['source_kind']:13s} {e['events']:7d} "
              f"events {e['bytes']:9d} B  {e['validated']['replay']}")
    for e in cat.get('localise', {}).get('bundles', []):
        print(f"{e['id']:28s} sketch        {len(e['runs'])} runs "
              f"{e['bytes']:9d} B  {e['validated']['replay']}")
    print('wheel:', cat['wheel'])


if __name__ == '__main__':
    main()
