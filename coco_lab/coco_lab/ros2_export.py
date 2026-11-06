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
"Run in ROS 2" (R2.7): an algorithm file as a ready ``ament_python`` package.

    python -m coco_lab.ros2_export algorithm.py --name my_planner --out DIR

:func:`export` returns the package as ``{path: text}``; the browser's "Export as ROS 2 package"
button calls the same function in the user-code sandbox and zips it, so both give the same
files. The package ``coco_user_<name>`` holds the user's ``algorithm.py`` **unchanged**, a node
(``ros2_package/node.py.tmpl``) that converts the real messages into :mod:`coco_lab.api` types
and calls it through the same guard, a launch file that swaps it into COCO's Nav2 bring-up in
place of the matching Nav2 component, the behaviour tree that names its action server, and a
README. Nothing here imports ROS (README invariant 1): the node is text until it is built.
"""

from pathlib import Path
import re
from typing import Dict

from .user_code import code_sha256, load

TEMPLATES = Path(__file__).parent / 'ros2_package'
ACTIONS = {'planner': 'user_compute_path_to_pose', 'controller': 'user_follow_path',
           'localiser': ''}
ROLES = {
    'planner': 'It serves `nav2_msgs/action/ComputePathToPose` as '
               '`user_compute_path_to_pose`; the '
               "launch file points Nav2's behaviour tree at it instead of `planner_server` "
               '(which still runs, unused). It plans on `/global_costmap/costmap_raw`.',
    'controller': 'It serves `nav2_msgs/action/FollowPath` as `user_follow_path`; the launch '
                  "file points Nav2's behaviour tree at it instead of `controller_server`. "
                  "It publishes `TwistStamped` on `/cmd_vel_nav`, into Nav2's velocity "
                  'smoother, collision monitor, `cmd_vel_relay` and '
                  "COCO's `cmd_vel_arbiter`.",
    'localiser': 'It replaces AMCL: Nav2 starts without it, map_server runs from this launch '
                 'file, and the node publishes `/amcl_pose` and the `map -> odom` transform '
                 'from your estimate.'}
BT_NOTES = {'planner': 'ComputePathToPose names server_name="user_compute_path_to_pose".',
            'controller': 'FollowPath names server_name="user_follow_path".',
            'localiser': 'nothing (the localiser replaces AMCL; the tree is stock).'}
NAME = re.compile(r'^[a-z][a-z0-9_]{1,39}$')


class ExportError(ValueError):
    """The file or the name cannot make a package."""


def export(source: str, name: str, author: str = 'COCO Lab user',
           licence: str = 'MIT') -> Dict[str, str]:
    """Return the package ``coco_user_<name>`` as ``{relative path: text}``."""
    if not NAME.match(name):
        raise ExportError('the name: a lower-case letter, then letters, digits or _ (2-40)')
    if licence not in ('MIT', 'Apache-2.0'):
        raise ExportError('licence: MIT or Apache-2.0')
    kind = load(source).kind
    pkg = f'coco_user_{name}'
    sub = {'NAME': name, 'KIND': kind, 'KIND_TITLE': kind.capitalize(), 'ACTION': ACTIONS[kind],
           'AUTHOR': re.sub(r'[<>&"\']', '', author)[:80], 'LICENCE': licence,
           'SHA': code_sha256(source), 'ROLE': ROLES[kind],
           'BT_NOTE': BT_NOTES[kind],
           'PLANNER_SERVER':
               ' server_name="user_compute_path_to_pose"' if kind == 'planner' else '',
           'CONTROLLER_SERVER':
               ' server_name="user_follow_path"' if kind == 'controller' else ''}

    def fill(t: str) -> str:
        text = (TEMPLATES / t).read_text(encoding='utf-8')
        for k, v in sub.items():
            text = text.replace('{{' + k + '}}', v)
        if '{{' in text:
            raise ExportError(f'{t}: an unfilled placeholder')
        return text
    files = {
        f'{pkg}/package.xml': fill('package.xml.tmpl'),
        f'{pkg}/setup.py': fill('setup.py.tmpl'),
        f'{pkg}/setup.cfg': f'[develop]\nscript_dir=$base/lib/{pkg}\n[install]\n'
                            f'install_scripts=$base/lib/{pkg}\n',
        f'{pkg}/resource/{pkg}': '',
        f'{pkg}/{pkg}/__init__.py': '',
        f'{pkg}/{pkg}/algorithm.py': source,
        f'{pkg}/{pkg}/node.py': fill('node.py.tmpl'),
        f'{pkg}/launch/{pkg}.launch.py': fill('launch.py.tmpl'),
        f'{pkg}/README.md': fill('README.md.tmpl'),
    }
    if kind != 'localiser':
        files[f'{pkg}/bt/navigate_to_pose.xml'] = fill('navigate_to_pose.xml.tmpl')
    return files


def main(argv=None) -> int:
    """``python -m coco_lab.ros2_export FILE --name NAME --out DIR``."""
    import argparse   # here: the browser's trimmed standard library has no argparse
    ap = argparse.ArgumentParser(prog='coco ros2 export',
                                 description='An algorithm file as a ROS 2 package (R2.7).')
    ap.add_argument('file')
    ap.add_argument('--name', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--author', default='COCO Lab user')
    ap.add_argument('--licence', default='MIT')
    a = ap.parse_args(argv)
    files = export(Path(a.file).read_text(encoding='utf-8'), a.name, a.author, a.licence)
    for rel, text in files.items():
        p = Path(a.out) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    print(f'wrote {len(files)} files: {Path(a.out) / f"coco_user_{a.name}"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
