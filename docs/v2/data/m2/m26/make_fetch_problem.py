"""
Write coco_lab/coco_lab/fetch_problem.py: Lab 4's bay search problem (M2.6).

    PYTHONPATH=coco_lab:lab_web/tools python3 docs/v2/data/m2/m26/make_fetch_problem.py

The Arena's fetch mission searches COCO's four bays with exactly the
problem Lab 4 built and the real mission builds
(``lab_web/tools/build_search.py arena_problem``: coco_config's
TARGET_REGIONS, travel by coco_lab's A* on the robot's Nav2 map, the
mission's assumed detection 0.9, a uniform prior). coco_lab cannot import
coco_config or the build tools in the browser, so this writes the problem
into a module; ``lab_web/tools/test_fetch_problem.py`` checks it equals
``arena_problem()``. Also written: the frozen colour -> bay layout
(coco_config TARGETS: which bay each colour stands in -- the world's truth,
never the robot's prior) and each bay's target position.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
sys.path.insert(0, os.path.join(REPO, 'lab_web', 'tools'))

import build_search  # noqa: E402

OUT = os.path.join(REPO, 'coco_lab', 'coco_lab', 'fetch_problem.py')

HEAD = '''# Copyright 2026 Gautham Anil
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
Lab 4's bay search problem and the frozen target layout (M2.6). GENERATED.

Written by docs/v2/data/m2/m26/make_fetch_problem.py from
lab_web/tools/build_search.py ``arena_problem()`` (coco_config's
TARGET_REGIONS, A* travel on the Nav2 map, the mission's ASSUMED detection
0.9, a uniform prior) and coco_config's TARGETS. WORLD frame (the Arena's
map frame is world + (2, 0)). Do not edit: regenerate;
lab_web/tools/test_fetch_problem.py checks it.
"""

'''


def py(o, depth=0):
    """Return ``o`` as Python source with 4-space hanging indents."""
    pad, end = '    ' * (depth + 1), '    ' * depth
    if isinstance(o, dict):
        if not o:
            return '{}'
        return '{\n' + ''.join(f'{pad}{k!r}: {py(v, depth + 1)},\n'
                               for k, v in o.items()) + end + '}'
    if isinstance(o, (list, tuple)) and any(isinstance(v, (dict, list, tuple)) for v in o):
        return '[\n' + ''.join(f'{pad}{py(v, depth + 1)},\n' for v in o) + end + ']'
    if isinstance(o, tuple):
        return repr(list(o))
    return repr(o)


def main():
    p = build_search.arena_problem()
    robot = build_search._robot()
    layout, nominal = {}, {}
    for t in robot.TARGETS:
        reg = [r for r in robot.TARGET_REGIONS if abs(r.bay_y - t.lane_y) < 1e-9]
        layout[t.colour] = reg[0].region_id
    for r in robot.TARGET_REGIONS:
        nominal[r.region_id] = [float(v) for v in r.target_nominal]
    with open(OUT, 'w') as f:
        f.write(HEAD)
        f.write(f'PROBLEM = {py(p.to_dict())}\n\n')
        f.write('#: the world: which bay each colour stands in (never the prior)\n')
        f.write(f'LAYOUT = {py(layout)}\n\n')
        f.write("#: each bay's target, (x, y, z) world (z: the grasp height)\n")
        f.write(f'TARGET_NOMINAL = {py(nominal)}\n\n')
        f.write(f'SPAWN_XY = {list(robot.SPAWN_XY)!r}\n')
    print(OUT, p.ids, layout)


if __name__ == '__main__':
    main()
