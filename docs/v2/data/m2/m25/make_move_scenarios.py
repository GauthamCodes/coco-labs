"""
Write coco_lab/coco_lab/move_scenarios.py from Lab 5's definitions (M2.5).

    python3 docs/v2/data/m2/m25/make_move_scenarios.py

The Arena rebuilds Lab 5's scenarios from their world definitions:
``coco_lab_ros/config/lab5_scenarios.json`` (start, goal, actors, the
mislocalised injection) and the two FROZEN SmacPlanner2D paths in
``coco_lab_ros/config/lab5_paths/`` every Lab 5 controller drove. coco_lab
cannot read the ROS package's files in the browser, so this copies them
into a module, poses rounded to 1e-6 m / rad, with each source file's
SHA-256; ``coco_lab/test/test_move_arena.py`` checks the copy against the
files.
"""

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..', '..'))
CFG = os.path.join(REPO, 'coco_lab_ros', 'config')
OUT = os.path.join(REPO, 'coco_lab', 'coco_lab', 'move_scenarios.py')

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
Lab 5's scenarios and frozen paths, for the Arena (M2.5). GENERATED.

Written by docs/v2/data/m2/m25/make_move_scenarios.py from
coco_lab_ros/config/lab5_scenarios.json and config/lab5_paths/ (map frame
= world + (2, 0), the Arena's map frame); poses rounded to 1e-6. Do not
edit: regenerate. test_move_arena.py checks it against the files.
"""

'''


def py(o, depth=0):
    """Return ``o`` as Python source with 4-space hanging indents."""
    pad, end = '    ' * (depth + 1), '    ' * depth
    if isinstance(o, dict):
        if not o:
            return '{}'
        body = ''.join(f'{pad}{k!r}: {py(v, depth + 1)},\n' for k, v in o.items())
        return '{\n' + body + end + '}'
    if isinstance(o, list) and any(isinstance(v, (dict, list)) for v in o):
        return '[\n' + ''.join(f'{pad}{py(v, depth + 1)},\n' for v in o) + end + ']'
    return repr(o)


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    sc_path = os.path.join(CFG, 'lab5_scenarios.json')
    with open(sc_path) as f:
        doc = json.load(f)
    paths, sources = {}, {'lab5_scenarios.json': sha(sc_path)}
    scen = {}
    for s in doc['scenarios']:
        if s['id'] == 'parked':
            continue  # Experiment C's snapshot only; the robot never moves
        name = s['path']
        if name not in paths:
            p = os.path.join(CFG, 'lab5_paths', name)
            with open(p) as f:
                d = json.load(f)
            paths[name] = [tuple(round(v, 6) for v in q) for q in d['poses']]
            sources[name] = sha(p)
        scen[s['id']] = {
            'title': s['title'], 'path': name, 'start': list(s['start']),
            'goal': list(s['goal']),
            'actors': [{'id': a['id'], 'waypoints': [list(w) for w in a['waypoints']],
                        'speed': a['speed'], 'trigger': dict(a['trigger'])}
                       for a in s['actors']],
            'inject': dict(s['inject']) if 'inject' in s else None}
    lines = [HEAD, f'SOURCES = {py(sources)}\n\n',
             f'SCENARIOS = {py(scen)}\n\n', 'PATHS = {\n']
    for name, poses in paths.items():
        lines.append(f'    {name!r}: (\n')
        for q in poses:
            lines.append(f'        ({q[0]!r}, {q[1]!r}, {q[2]!r}),\n')
        lines.append('    ),\n')
    lines.append('}\n')
    txt = ''.join(lines)
    with open(OUT, 'w') as f:
        f.write(txt)
    print(OUT, sum(len(p) for p in paths.values()), 'poses,', len(scen), 'scenarios')


if __name__ == '__main__':
    main()
