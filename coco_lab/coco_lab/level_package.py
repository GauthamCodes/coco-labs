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
R5.4 "Run it in ROS 2": a COCO Lab level and scenario as a ROS 2 Jazzy package.

The package is a ready ``ament_python`` package:

    python3 tools/r5/level_package.py worlds/coco_depot_v1.yaml --goals 26,6.5 30,11 --out DIR

:func:`package` returns ``{relative path: bytes}``; the browser's "Download as ROS 2 package" calls
the same function in its Python worker and zips it, so both give the same files (given the same
``dump``; see :mod:`coco_lab.level_files`). The package ``coco_level_<id>`` holds the level's
Gazebo world, Nav2 map and parameters (``level_files``, derivation 5: what COCO's recorded STACK
runs and the coco-ros2 image use), the scenario's goals, a launch file that brings the level up as
the coco-ros2 image does (``bringup``: the start pose and the odometry calibration, checked), a
goal runner, and a README with the exact commands. Nothing here imports ROS (invariant 1): the
files are text until they are built.
"""
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Sequence

from coco_lab import level_files as lf
from coco_lab.worldspec import to_map_frame

TEMPLATES = Path(__file__).parent / 'level_package'
DERIVATION = 5
NAME = re.compile(r'^[a-z][a-z0-9_]{0,39}$')


class PackageError(ValueError):
    """The level, the scenario or a name cannot make a package."""


def _fill(text: str, sub: Dict[str, str], name: str) -> str:
    for k, v in sub.items():
        text = text.replace(f'@@{k}@@', v)
    if re.search(r'@@[A-Z_]+@@', text):
        raise PackageError(f'{name}: an unfilled placeholder')
    return text


def scenario_goals(goals: Sequence) -> List[Dict]:
    """``[[x, y], ...]`` or ``[{'id', 'goal': [x, y]}, ...]`` -> checked goal records."""
    out = []
    for k, g in enumerate(goals):
        if isinstance(g, dict):
            gid, xy = str(g.get('id', f'g{k + 1:03d}')), g.get('goal')
        else:
            gid, xy = f'g{k + 1:03d}', g
        if not (
            isinstance(xy, (list, tuple))
            and len(xy) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in xy)
        ):
            raise PackageError(f'goal {k + 1}: [x, y] in metres')
        if not re.match(r'^[A-Za-z0-9_.-]{1,40}$', gid):
            raise PackageError(f'goal {k + 1}: an id of letters, digits, _ . -')
        out.append({'id': gid, 'goal': [float(xy[0]), float(xy[1])]})
    if not 1 <= len(out) <= 100:
        raise PackageError('1 to 100 goals')
    return out


def package(
    spec: Dict,
    goals: Sequence,
    world_template: str,
    nav2_params: Dict,
    controllers: Dict,
    scenario: str = 'goals',
    dump=lf.json_dump,
    templates: Optional[Dict[str, str]] = None,
    author: str = 'COCO Lab user',
) -> Dict[str, bytes]:
    """
    Return the package ``coco_level_<id>`` as ``{relative path: bytes}``.

    ``spec`` is a World Spec dict; ``goals`` the scenario's goals in the World Spec's frame (as
    COCO Lab shows them); ``world_template``, ``nav2_params``, ``controllers`` and ``dump`` as
    :func:`coco_lab.level_files.level_files`; ``templates`` the six ``*.tmpl`` texts (default: this
    package's own files; the browser passes the ones it fetched).
    """
    if not NAME.match(scenario):
        raise PackageError('the scenario name: a lower-case letter, then letters, digits or _')
    s, files = lf.level_files(
        spec, world_template, nav2_params, controllers, dump, derivation=DERIVATION
    )
    lid = s['id']
    pkg = f'coco_level_{re.sub(r"[^a-z0-9_]", "_", lid.lower())}'
    gs = scenario_goals(goals)
    # goals and start in Nav2's map frame (the World Spec's, shifted by world_to_map: [0, 0] on the
    # Depot)
    for g in gs:
        g['goal'] = list(to_map_frame(s, g['goal'][0], g['goal'][1]))
    sx, sy = s['start']['x'], s['start']['y']
    multiplier = None
    if 'gazebo/diff_drive_calibration.yaml' in files:
        # the calibrated value, as the generated file's header states it ('-> 1.323. Loaded over
        # ...')
        m = re.search(
            r'-> ([0-9.]+)\. Loaded over', files['gazebo/diff_drive_calibration.yaml'].decode()
        )
        if not m:
            raise PackageError(
                'the odometry calibration file does not state its wheel_separation_multiplier'
            )
        multiplier = m.group(1)
    sub = {
        'PKG': pkg,
        'LEVEL_ID': lid,
        'TITLE': re.sub(r'[<>&"\'@]', '', str(s.get('title', lid)))[:120],
        'SCENARIO': scenario,
        'AUTHOR': re.sub(r'[<>&"\'@]', '', author)[:80],
        'N_GOALS': str(len(gs)),
        'START_X': repr(float(sx)),
        'START_Y': repr(float(sy)),
        'START_THETA': repr(float(s['start']['theta'])),
        'TELEPORT': 'True',
        'MULTIPLIER': multiplier if multiplier else 'None',
        'DERIVATION': str(DERIVATION),
    }
    t = templates or {p.name: p.read_text(encoding='utf-8') for p in TEMPLATES.glob('*.tmpl')}
    out: Dict[str, bytes] = {}

    def put(rel: str, data):
        out[f'{pkg}/{rel}'] = data if isinstance(data, bytes) else data.encode('utf-8')

    put('package.xml', _fill(t['package.xml.tmpl'], sub, 'package.xml'))
    put('setup.py', _fill(t['setup.py.tmpl'], sub, 'setup.py'))
    put(
        'setup.cfg',
        f'[develop]\nscript_dir=$base/lib/{pkg}\n[install]\ninstall_scripts=$base/lib/{pkg}\n',
    )
    put(f'resource/{pkg}', '')
    put(f'{pkg}/__init__.py', '')
    put(f'{pkg}/bringup.py', _fill(t['bringup.py.tmpl'], sub, 'bringup.py'))
    put(f'{pkg}/run_goals.py', _fill(t['run_goals.py.tmpl'], sub, 'run_goals.py'))
    put('launch/level.launch.py', _fill(t['launch.py.tmpl'], sub, 'launch'))
    put('README.md', _fill(t['README.md.tmpl'], sub, 'README'))
    put(
        'scenario.json',
        json.dumps(
            {
                'schema': 'coco_lab.level_package.scenario',
                'version': 1,
                'level': lid,
                'scenario': scenario,
                'frame': 'map',
                'start': [sx, sy, s['start']['theta']],
                'goals': gs,
            },
            indent=1,
        )
        + '\n',
    )
    for rel, data in sorted(files.items()):
        if rel.startswith('arena/'):
            continue  # the browser model's files: not needed in ROS 2
        put(f'level/{rel}', data)
    put(
        'level/checksums.json',
        json.dumps(
            lf.sha256s({k[len(pkg) + 1:]: v for k, v in out.items()}), indent=1, sort_keys=True
        )
        + '\n',
    )
    return out
