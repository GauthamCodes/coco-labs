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

"""Compare arms hold the declared world, inputs and non-compared settings fixed."""
import os

from coco_lab.compare_loop import LoopComparison
import pytest
import yaml

with open(os.path.join(os.path.dirname(__file__), '..', '..', 'worlds',
                       'coco_arena_v1.yaml'), encoding='utf-8') as stream:
    SPEC = yaml.safe_load(stream)


def request(family, names, steps=200):
    return {'family': family, 'names': names, 'steps': steps, 'goal': [2.5, 2],
            'inflation': {'inflation_radius': .5, 'cost_scaling_factor': 10,
                          'robot_radius': .25}}


def test_localization_arms_get_the_same_truth_commands_scan_and_relocation():
    c = LoopComparison(SPEC, request('localise', ['mcl', 'mcl_augmented', 'ekf', 'mcl']))
    rows = c.advance()
    assert all(row['truth'] == rows[0]['truth'] for row in rows)
    assert all(arm.ranges == c.arms[0].ranges for arm in c.arms)
    assert all(arm.subsystems['localise'].mcl_params.beams == 12 for arm in c.arms)
    assert all(arm.subsystems['localise'].ekf_params.beams == 12 for arm in c.arms)
    assert c.arms[0].subsystems['localise'].mcl_params.injection == 'none'
    assert c.arms[1].subsystems['localise'].mcl_params.injection == 'augmented'
    c.tick = 50  # exercise the shared intervention without a long benchmark
    rows = c.advance()
    assert all(row['truth'] == rows[0]['truth'] for row in rows)
    assert rows[0]['truth'][:2] == [2.5, 2]
    assert rows[0]['particles'] and not rows[2]['particles']


def test_control_arms_use_existing_engines_and_a_common_planning_graph():
    c = LoopComparison(SPEC, request('control', ['dwa', 'rpp', 'mppi', 'dwa']))
    c.advance()
    rows = c.advance()
    assert all(arm.grid is c.grid for arm in c.arms)
    assert [arm.subsystems['move'].engine.kind for arm in c.arms] == ['dwa', 'rpp', 'mppi', 'dwa']
    assert all(row['summary']['compute_ms'] >= 0 for row in rows)
    assert all(row['summary']['path_cost'] is None for row in rows)
    assert all(arm.subsystems['move'].window_params.inscribed == pytest.approx(.25)
               for arm in c.arms)


def test_window_is_bounded_before_and_during_execution():
    with pytest.raises(ValueError):
        LoopComparison(SPEC, request('control', ['dwa', 'rpp'], steps=201))
    c = LoopComparison(SPEC, request('control', ['dwa', 'rpp'], steps=1))
    c.advance()
    with pytest.raises(ValueError):
        c.advance()
