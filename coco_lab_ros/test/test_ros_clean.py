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
Everything coco_lab_ros starts can be swept by ros_clean.sh (CLAUDE.md §5).

"Anything added to a launch file must be added to ros_clean.sh": its
patterns are process names, and a new node's command line does not
contain its launch file's name. For every console script, every launch
file and the conformance script this checks that a bracketed pattern
matches a realistic command line and cannot match its own text, and one
decoy process proves ``ros_clean.sh --list`` really sees it (it kills
nothing).
"""

import ast
import os
import re
import subprocess
import sys
import time
import uuid

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
SCRIPT = os.path.join(REPO, 'gazebo_models', 'scripts', 'ros_clean.sh')
SCRIPTS = ('lab1c_conformance.py', 'lab1c_watch.py')


def patterns():
    with open(SCRIPT, encoding='utf-8') as f:
        text = f.read()
    body = text[text.index('PATTERNS=('):]
    body = body[:body.index('\n)\n')]
    return re.findall(r"^\s*'([^']+)'", body, re.M)


def console_scripts():
    with open(os.path.join(PKG, 'setup.py'), encoding='utf-8') as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == \
                        'console_scripts':
                    return [s.split('=')[0].strip()
                            for s in ast.literal_eval(v)]
    raise AssertionError('no console_scripts in setup.py')


def launch_files():
    return sorted(f for f in os.listdir(os.path.join(PKG, 'launch'))
                  if f.endswith('.launch.py'))


def command_lines():
    lines = [f'/home/u/ws/install/coco_lab_ros/lib/coco_lab_ros/{s} '
             f'--ros-args -r __node:=x' for s in console_scripts()]
    lines += [f'/usr/bin/python3 /opt/ros/jazzy/bin/ros2 launch coco_lab_ros '
              f'{f} gui:=false' for f in launch_files()]
    lines += [f'python3 -P /repo/docs/data/lab1c/{s} --out x' for s in SCRIPTS]
    return lines


def test_the_package_declares_what_this_test_covers():
    assert set(console_scripts()) == {'lab_planner', 'lab_params',
                                      'lab_export'}
    assert launch_files() == ['lab_stack.launch.py',
                              'lab_static_smoke.launch.py']
    for s in SCRIPTS:
        assert os.path.exists(os.path.join(REPO, 'docs', 'data', 'lab1c', s))


@pytest.mark.parametrize('line', command_lines())
def test_a_bracketed_pattern_matches_every_new_process(line):
    hits = [p for p in patterns() if re.search(p, line)]
    assert hits, f'no ros_clean.sh pattern matches {line!r}'
    for p in hits:
        assert '[' in p, f'{p!r} is not bracketed'
        assert not re.search(p, p), f'{p!r} matches its own text'


def test_a_shell_that_only_mentions_the_name_is_not_swept():
    for name in console_scripts():
        text = f'bash -c "until grep -q {name} run.log; do sleep 1; done"'
        lab = [p for p in patterns() if 'coco_lab_ros/' in p]
        assert not any(re.search(p, text) for p in lab), name


def test_ros_clean_list_sees_a_lab_planner():
    nonce = uuid.uuid4().hex[:8]
    fake = (f'/tmp/install/coco_lab_ros/lib/coco_lab_ros/lab_planner '
            f'--nonce {nonce}')
    proc = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(120)', fake],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        seen = False
        deadline = time.time() + 30
        while time.time() < deadline and not seen:
            out = subprocess.run(['bash', SCRIPT, '--list'],
                                 capture_output=True, text=True,
                                 timeout=120).stdout
            seen = str(proc.pid) in re.findall(r'^\s+(\d+)\s', out, re.M)
            time.sleep(0.5)
        assert seen, 'ros_clean.sh --list did not report the decoy'
    finally:
        proc.kill()
        proc.wait()
