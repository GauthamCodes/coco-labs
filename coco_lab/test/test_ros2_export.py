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

"""R2.7: "Run in ROS 2" -- the exported package (coco_lab.ros2_export; no ROS needed here)."""

from pathlib import Path
import xml.etree.ElementTree as ET

from coco_lab.ros2_export import export, ExportError, main
import pytest

TEMPLATES = Path(__file__).resolve().parents[1] / 'coco_lab' / 'templates'


@pytest.mark.parametrize('tmpl,kind', [('planner_astar', 'planner'),
                                       ('controller_pure_pursuit', 'controller'),
                                       ('localiser_particle_filter', 'localiser')])
def test_package_is_complete(tmpl, kind):
    src = (TEMPLATES / f'{tmpl}.py').read_text()
    files = export(src, 'mine', 'A. Person', 'Apache-2.0')
    pkg = 'coco_user_mine'
    assert files[f'{pkg}/{pkg}/algorithm.py'] == src          # the user's file, unchanged
    for rel, text in files.items():
        if rel.endswith('.py'):
            compile(text, rel, 'exec')                         # every Python file parses
        assert '{{' not in text, rel
    xml = ET.fromstring(files[f'{pkg}/package.xml'])
    assert xml.find('name').text == pkg and xml.find('license').text == 'Apache-2.0'
    assert xml.find('export/build_type').text == 'ament_python'
    node = files[f'{pkg}/{pkg}/node.py']
    assert f"KIND = '{kind}'" in node and 'load(src)' in node
    launch = files[f'{pkg}/launch/{pkg}.launch.py']
    bt = files.get(f'{pkg}/bt/navigate_to_pose.xml')
    if kind == 'planner':
        assert 'server_name="user_compute_path_to_pose"' in bt
        assert 'server_name="user_follow_path"' not in bt
    elif kind == 'controller':
        assert 'server_name="user_follow_path"' in bt and "'/cmd_vel_nav'" in node
    else:
        assert bt is None and 'navigation_launch.py' in launch and 'map_server' in launch
    ET.fromstring(bt) if bt else None


def test_controller_feeds_the_arbiter_never_the_wheels():
    files = export((TEMPLATES / 'controller_pure_pursuit.py').read_text(), 'pp')
    text = '\n'.join(files.values())
    assert '/diff_drive_controller/cmd_vel' not in text.replace(
        "'/diff_drive_controller/odom'", '')
    assert 'cmd_vel_arbiter' in text


def test_refusals(tmp_path):
    with pytest.raises(ExportError):
        export('def plan(c, s, g, ctx):\n    return None\n', 'Bad-Name')
    with pytest.raises(ExportError):
        export('def plan(c, s, g, ctx):\n    return None\n', 'ok', licence='GPL-3.0')
    f = tmp_path / 'a.py'
    f.write_text('def plan(c, s, g, ctx):\n    return None\n')
    assert main([str(f), '--name', 'tiny', '--out', str(tmp_path / 'out')]) == 0
    assert (tmp_path / 'out' / 'coco_user_tiny' / 'setup.py').exists()
