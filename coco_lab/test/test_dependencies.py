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
