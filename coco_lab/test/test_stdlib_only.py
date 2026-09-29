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
coco_lab's runtime is the Python standard library, and nothing else.

That is what lets Pyodide load it as a pure-Python wheel with no
dependency resolution (docs/ROADMAP.md section 3.1). numpy may be added
later if a lab measurably needs it; this test is where that decision will
have to be made explicitly.
"""

import ast
import os
import sys

import coco_lab

PACKAGE_DIR = os.path.dirname(coco_lab.__file__)


def runtime_sources():
    for name in sorted(os.listdir(PACKAGE_DIR)):
        if name.endswith('.py'):
            yield os.path.join(PACKAGE_DIR, name)


def test_every_import_is_stdlib_or_coco_lab():
    sources = list(runtime_sources())
    assert len(sources) >= 6
    offenders = []
    for path in sources:
        with open(path) as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative: inside coco_lab
                    continue
                roots = [node.module.split('.')[0]]
            else:
                continue
            for root in roots:
                if root != 'coco_lab' and root not in sys.stdlib_module_names:
                    offenders.append(f'{os.path.basename(path)}: {root}')
    assert not offenders, offenders


def test_setup_declares_no_runtime_requirements():
    setup_py = os.path.join(os.path.dirname(__file__), '..', 'setup.py')
    with open(setup_py) as f:
        assert 'install_requires=[]' in f.read()
