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
from coco_lab.search import search  # noqa: E402
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


def build(out=OUT, wheel='build', with_benchmark=True):
    """Build the site data under ``out``; return the catalog."""
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, 'bundles'))
    entries = []
    for bid, rel, title, group, cite in SERVED_INFO:
        dst = os.path.join(out, 'bundles', bid)
        shutil.copytree(os.path.join(common.REPO, rel), dst)
        entries.append(_entry(bid, dst, title, group, cite,
                              editable=group == TEACHING))
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
        'schema': 'coco_lab.catalog', 'version': '1.0',
        'coco_lab_version': coco_lab.__version__,
        'built_from': git, 'tool': TOOL,
        'wheel': wheel_info,
        'bundles': entries,
    }
    with open(os.path.join(out, 'catalog.json'), 'w') as f:
        f.write(json.dumps(catalog, indent=1, sort_keys=True) + '\n')
    return catalog


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--wheel', default='build',
                    help="a prebuilt wheel to serve, or 'build' (default)")
    ap.add_argument('--no-benchmark', action='store_true')
    args = ap.parse_args(argv)
    cat = build(args.out, args.wheel, not args.no_benchmark)
    for e in cat['bundles']:
        print(f"{e['id']:28s} {e['source_kind']:13s} {e['events']:7d} "
              f"events {e['bytes']:9d} B  {e['validated']['replay']}")
    print('wheel:', cat['wheel'])


if __name__ == '__main__':
    main()
