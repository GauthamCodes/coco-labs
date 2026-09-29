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
hypothesis and networkx are test-only, pinned, and declared both ways.

For pip: ``requirements-test.txt`` pins them with ``==`` and ``setup.py``
exposes it as the ``test`` extra. For rosdep: ``package.xml`` declares the
keys ``python3-hypothesis`` and ``python3-networkx`` as ``test_depend``.
Both keys were verified with ``rosdep resolve`` rather than assumed; that
is a machine fact, recorded in docs/RESULTS.md, not re-run here.
"""

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.join(os.path.dirname(__file__), '..')


def pins():
    with open(os.path.join(HERE, 'requirements-test.txt')) as f:
        lines = [ln.strip() for ln in f
                 if ln.strip() and not ln.startswith('#')]
    return dict(ln.split('==') for ln in lines)


def test_test_dependencies_are_pinned_exactly():
    with open(os.path.join(HERE, 'requirements-test.txt')) as f:
        lines = [ln.strip() for ln in f
                 if ln.strip() and not ln.startswith('#')]
    assert all(re.fullmatch(r'[\w-]+==[\d.]+', ln) for ln in lines), lines
    assert {'hypothesis', 'networkx'} <= set(pins())


def test_package_xml_declares_them_as_test_depends_only():
    root = ET.parse(os.path.join(HERE, 'package.xml')).getroot()
    test_deps = {e.text for e in root.findall('test_depend')}
    assert {'python3-hypothesis', 'python3-networkx'} <= test_deps
    runtime = {e.text for tag in ('depend', 'exec_depend', 'build_depend')
               for e in root.findall(tag)}
    assert not runtime, f'coco_lab declares runtime deps: {runtime}'
    assert root.find('export/build_type').text == 'ament_python'


def test_setup_py_runs_through_a_symlink(tmp_path):
    """
    ``colcon build --symlink-install`` runs setup.py via a symlink.

    scripts/build_overlay.sh requires --symlink-install, and colcon then
    executes ``<build>/coco_lab/setup.py``, a symlink to the source file,
    from a directory with no requirements-test.txt. With ``abspath`` the
    extra's pins were looked for beside the link and the overlay build
    failed (measured, Phase 1C-0); ``realpath`` follows the link.
    """
    link = tmp_path / 'setup.py'
    link.symlink_to(os.path.realpath(os.path.join(HERE, 'setup.py')))
    out = subprocess.run([sys.executable, str(link), '--name'],
                         cwd=str(tmp_path), capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == 'coco_lab'
