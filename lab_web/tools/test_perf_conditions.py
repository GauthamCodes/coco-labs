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
Every perf harness records the machine's measurement conditions.

Owner's rule (2026-10-09, docs/STATUS.md plan-change log): power profile,
AC or battery, CPU governor and load average go next to every harness's
results. M1.10 measured in power-saver without noticing; M1.5 recorded
nothing, so its numbers could not be compared with M1.10's.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

PERF = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'perf')
# Harnesses that produce no measurement output.
NOT_HARNESSES = {'conditions.mjs', 'serve_dist.mjs', 'stdlib_usage.mjs'}
RECORDS = 'conditions: { start: CONDITIONS_AT_START, end: conditions() }'


def _harnesses():
    return sorted(f for f in os.listdir(PERF)
                  if f.endswith('.mjs') and f not in NOT_HARNESSES)


@pytest.mark.parametrize('name', _harnesses())
def test_every_json_output_of_the_harness_records_conditions(name):
    src = open(os.path.join(PERF, name), encoding='utf-8').read()
    assert "import { conditions } from './conditions.mjs';" in src
    outputs = re.findall(r'(?:writeFileSync|console\.log)\([^\n]*JSON\.stringify\([^\n]*null, 1\)', src)
    assert outputs, f'{name} writes no JSON result: list it in NOT_HARNESSES'
    for line in outputs:
        assert RECORDS in line, f'{name}: a JSON result without conditions: {line[:120]}'


def test_conditions_reports_power_ac_governor_and_load():
    node = shutil.which('node')
    assert node, 'node is needed to run conditions.mjs'
    js = ("import('" + os.path.join(PERF, 'conditions.mjs') +
          "').then((m) => console.log(JSON.stringify(m.conditions())))")
    out = json.loads(subprocess.run([node, '--input-type=module', '-e', js],
                                    check=True, capture_output=True,
                                    text=True).stdout)
    for key in ('at_utc', 'power_profile', 'ac_power', 'battery',
                'cpu_governor', 'load_average', 'cpu', 'threads', 'standard'):
        assert key in out, key
    assert set(out['load_average']) == {'1m', '5m', '15m'}
    assert out['standard'] == (out['power_profile'] == 'balanced'
                               and out['ac_power'] is True)
