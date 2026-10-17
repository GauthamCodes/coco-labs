#!/usr/bin/env python3
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
Write the Grasp Assist golden traces (M6F.5).

    make_grasp_golden.py [--check]

Runs every scenario of ``coco_lab/test/fixtures/m6f/grasp_scenarios.json`` with
``coco_lab.grasp_assist.run_scenario`` and writes ``grasp_golden.json`` beside it:
each scenario's stage log, the sha256 chain of its per-tick state hashes, and its
last hash. ``test_grasp_assist.py`` diffs a fresh run against it. Regenerate only
for a deliberate, reviewed change to Grasp Assist, and say so in the commit.
"""

import json
import os
import sys

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'coco_lab'))
from coco_lab.grasp_assist import run_scenario  # noqa: E402, I100

FIX = os.path.join(REPO, 'coco_lab', 'test', 'fixtures', 'm6f')


def golden():
    with open(os.path.join(FIX, 'grasp_scenarios.json'), encoding='utf-8') as f:
        sc = json.load(f)
    with open(os.path.join(REPO, sc['spec']), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    out = {'schema': 'coco_lab.m6f.grasp_golden', 'version': 1, 'results': {}}
    for s in sc['scenarios']:
        r = run_scenario(spec, s)
        out['results'][s['name']] = {k: r[k] for k in ('stages', 'hash_chain', 'last_hash',
                                                       'carried')}
    return json.dumps(out, indent=1, sort_keys=True) + '\n'


def main():
    text = golden()
    path = os.path.join(FIX, 'grasp_golden.json')
    if '--check' in sys.argv:
        with open(path, encoding='utf-8') as f:
            same = f.read() == text
        print('golden traces current' if same else 'golden traces DIFFER')
        return 0 if same else 1
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
