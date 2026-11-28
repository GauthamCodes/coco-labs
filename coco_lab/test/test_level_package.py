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
"""R5.4: a level and its goals as a ROS 2 package (coco_lab.level_package, level_files)."""
import ast
import json
from pathlib import Path
import subprocess
import sys

from coco_lab import level_files as lf
from coco_lab import level_package as lp
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORLD = (REPO / 'gazebo_models/worlds/coco_navigation.world').read_text(encoding='utf-8')
NAV2 = yaml.safe_load((REPO / 'gazebo_models/config/nav2_params.yaml').read_text(encoding='utf-8'))
CTRL = yaml.safe_load(
    (REPO / 'gazebo_models/urdf/coco_controllers.yaml').read_text(encoding='utf-8')
)
DEPOT = yaml.safe_load((REPO / 'worlds/coco_depot_v1.yaml').read_text(encoding='utf-8'))
PKG = 'coco_level_coco_depot_v1'


@pytest.fixture(scope='module')
def files():
    return lp.package(
        DEPOT, [[26, 6.5], [30, 11]], WORLD, NAV2, CTRL, scenario='two_goals', dump=yaml.safe_dump
    )


def test_the_package_has_what_its_readme_names(files):
    names = set(files)
    for rel in (
        'package.xml',
        'setup.py',
        'setup.cfg',
        f'resource/{PKG}',
        f'{PKG}/__init__.py',
        f'{PKG}/bringup.py',
        f'{PKG}/run_goals.py',
        'launch/level.launch.py',
        'README.md',
        'scenario.json',
        'level/gazebo/coco_depot_v1.sdf',
        'level/nav2/coco_depot_v1.yaml',
        'level/nav2/coco_depot_v1.pgm',
        'level/nav2/nav2_params.yaml',
        'level/gazebo/diff_drive_calibration.yaml',
        'level/checksums.json',
    ):
        assert f'{PKG}/{rel}' in names, rel
    assert not any('/level/arena/' in n for n in names)  # the browser model's files stay out
    for rel in (f'{PKG}/bringup.py', f'{PKG}/run_goals.py', 'launch/level.launch.py', 'setup.py'):
        ast.parse(files[f'{PKG}/{rel}'].decode())  # Python that parses
    for name, data in files.items():
        if name.endswith(('.py', '.xml', '.md', '.json', '.cfg')):
            assert '@@' not in data.decode(), name  # no unfilled placeholder


def test_the_level_files_are_gen_levels(files):
    # the same bytes tools/m6/gen_level.py writes (it calls level_files with yaml.safe_dump)
    _, gen = lf.level_files(DEPOT, WORLD, NAV2, CTRL, yaml.safe_dump, derivation=lp.DERIVATION)
    for rel, data in gen.items():
        if not rel.startswith('arena/'):
            assert files[f'{PKG}/level/{rel}'] == data, rel


def test_start_goals_and_calibration(files):
    sc = json.loads(files[f'{PKG}/scenario.json'])
    assert sc['start'] == [23.0, 6.0, 0.0] and sc['frame'] == 'map'
    assert [g['goal'] for g in sc['goals']] == [
        [26.0, 6.5],
        [30.0, 11.0],
    ]  # world_to_map [0, 0] on the Depot
    b = files[f'{PKG}/{PKG}/bringup.py'].decode()
    assert 'START = (23.0, 6.0, 0.0)' in b and 'MULTIPLIER = 1.323' in b and 'TELEPORT = True' in b
    checks = json.loads(files[f'{PKG}/level/checksums.json'])
    assert 'level/nav2/nav2_params.yaml' in checks and 'README.md' in checks


def test_deterministic_and_the_browser_flavour_differs_only_in_dumped_yaml(files):
    again = lp.package(
        DEPOT, [[26, 6.5], [30, 11]], WORLD, NAV2, CTRL, scenario='two_goals', dump=yaml.safe_dump
    )
    assert again == files
    browser = lp.package(
        DEPOT, [[26, 6.5], [30, 11]], WORLD, NAV2, CTRL, scenario='two_goals'
    )  # json_dump
    differ = sorted(k for k in files if files[k] != browser[k])
    assert differ == [
        f'{PKG}/level/checksums.json',
        f'{PKG}/level/gazebo/diff_drive_calibration.yaml',
        f'{PKG}/level/nav2/nav2_params.yaml',
    ]
    # the same parameters, only written as JSON (which YAML parsers read)

    def body(t):
        text = '\n'.join(x for x in t.decode().splitlines() if not x.startswith('#'))
        return yaml.safe_load(text)

    for k in differ[1:]:
        assert body(browser[k]) == body(files[k]), k


@pytest.mark.parametrize(
    'goals,why',
    [
        ([], '1 to 100'),
        ([[1, 2, 3]], r'\[x, y\]'),
        ([['a', 2]], r'\[x, y\]'),
        ([{'id': 'bad id!', 'goal': [1, 2]}], 'an id'),
    ],
)
def test_bad_goals_are_refused(goals, why):
    with pytest.raises(lp.PackageError, match=why):
        lp.package(DEPOT, goals, WORLD, NAV2, CTRL)


def test_a_bad_scenario_name_is_refused():
    with pytest.raises(lp.PackageError, match='scenario name'):
        lp.package(DEPOT, [[26, 6.5]], WORLD, NAV2, CTRL, scenario='Two Goals')


DRIVER = (REPO / 'tools/g2/actor_scenario.py').read_text(encoding='utf-8')


def test_a_depot_package_carries_the_actor_driver_and_its_coco_lab(tmp_path):
    """R6.A4: a level package carries G2.9's actor driver, unchanged, and its coco_lab."""
    out = lp.package(DEPOT, [[26, 6.5]], WORLD, NAV2, CTRL, actor_driver=DRIVER)
    assert out[f'{PKG}/actors/actor_scenario.py'] == DRIVER.encode('utf-8')
    mods = sorted(k.rsplit('/', 1)[1] for k in out if k.startswith(f'{PKG}/actors/coco_lab/'))
    assert {'__init__.py', 'games.py', 'worldspec_v3.py', 'numerics.py'} <= set(mods)
    assert [
        m[:-3] for m in mods if m.endswith('.py') and m != '__init__.py'
    ] == lp.coco_lab_closure()
    assert 'link_limits.json' in mods  # link_bounds reads it at import
    launch = out[f'{PKG}/launch/level.launch.py'].decode()
    assert 'HAS_ACTORS = True' in launch and "'actor_scenario.py'" in launch
    assert b'move by G2.9' in out[f'{PKG}/README.md']
    # the bundled coco_lab stands on its own: the driver's imports, with only the package's
    # actors/ on the path
    for rel, data in out.items():
        if rel.startswith(f'{PKG}/actors/'):
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
    code = (
        'import sys; sys.path[:] = [p for p in sys.path if "coco_lab" not in p]; '
        f'sys.path.insert(0, {str(tmp_path / PKG / "actors")!r}); '
        'from coco_lab.games import box_distance; from coco_lab.worldspec_v3 import actor_pose; '
        'import coco_lab; print(coco_lab.__file__)'
    )
    r = subprocess.run(
        [sys.executable, '-I', '-c', code], capture_output=True, text=True, check=True
    )
    assert str(tmp_path / PKG / 'actors') in r.stdout


def test_without_the_driver_the_actors_stand_still_and_say_so(files):
    """Without the driver (actor_driver=None): no actors/, and the README says they stand still."""
    assert not any('/actors/' in k for k in files)
    assert 'HAS_ACTORS = False' in files[f'{PKG}/launch/level.launch.py'].decode()
    assert b'made without their driver, so they stand still' in files[f'{PKG}/README.md']
