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

"""The committed generated Python is exactly what protoc makes today."""

import os
import subprocess
import sys

from conftest import PKG

GEN = os.path.join(PKG, 'scripts', 'generate.py')


def test_generated_python_is_current():
    # TypeScript is checked by lab_web's CI job (it needs node_modules).
    r = subprocess.run([sys.executable, GEN, '--lang', 'py', '--check'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_proto_has_generated_python():
    protos = []
    for d, _, names in os.walk(os.path.join(PKG, 'proto')):
        protos += [os.path.relpath(os.path.join(d, n), os.path.join(PKG, 'proto'))
                   for n in names if n.endswith('.proto')]
    for p in protos:
        gen = os.path.join(PKG, 'coco_schemas', 'gen',
                           p.replace('.proto', '_pb2.py'))
        assert os.path.exists(gen), p
