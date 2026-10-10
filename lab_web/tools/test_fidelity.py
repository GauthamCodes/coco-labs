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

"""Fidelity report v1 and its chips are the committed measurement, rendered (M2.9)."""

import json
import os
import re

from coco_lab import arena as A
import fidelity
import missions

A_, B_ = fidelity.load()


def test_the_report_is_current():
    with open(fidelity.REPORT, encoding='utf-8') as f:
        assert f.read() == fidelity.report(), 'run: python3 lab_web/tools/fidelity.py --write'


def test_the_report_covers_the_three_gaps_the_prompt_names():
    r = fidelity.report()
    for heading in ('## 1. LiDAR at identical poses', '## 2. Odometry, straight and turning',
                    '## 3. Controller tracking against the Lab 5 recordings'):
        assert heading in r
    # straight and turning drives, slip off and on
    drives = {d['drive'] for d in A_['drives']}
    assert {'straight', 'square', 'tour'} <= drives
    for d in A_['drives']:
        assert set(d['arena']) == {'slip_off', 'slip_on'}


def test_each_chip_links_to_a_heading_of_the_report():
    heads = re.findall(r'^## (.*)$', fidelity.report(), re.M)
    slugs = {re.sub(r'\s', '-', re.sub(r'[^\w\s-]', '', h.lower())) for h in heads}
    for g in fidelity.gaps().values():
        assert g['anchor'] in slugs


def test_the_chips_quote_the_measurement():
    g = fidelity.gaps()
    ab = A_['scans']['abs_error_m']
    assert f'{ab["median"] * 1000:.1f} mm' in g['lidar']['text']
    assert f'{A_["scans"]["classes"]["both"]:,} beams' in g['lidar']['text']
    over = [d['yaw_overcount']['gazebo'] for d in A_['drives'] if d['rotation_rad'] >= 1.0]
    assert f'{min(over):.2f}–{max(over):.2f}×' in g['odometry']['text']
    assert f'{1 / A.SLIP_TURN:.2f}×' in g['odometry']['text']


def test_the_measurement_is_of_the_arena_as_shipped():
    assert A_['slip_turn'] == A.SLIP_TURN
    for d in A_['drives']:
        assert d['arena']['slip_off']['default_noise']['alphas'] == list(A.ODOM_ALPHAS)
    # the Arena's world casts exactly as the Stack's saved map
    assert A_['scans']['vs_sketch_on_nav2_map']['beams_different'] == 0
    # and its beams are Lab 2's: the same sessions give the same agreement
    assert A_['scans']['classes']['both'] == B_['scans']['classes']['both']


def test_the_tracking_rows_are_m25s_numbers():
    with open(os.path.join(fidelity.REPO, A_['tracking']['source']), encoding='utf-8') as f:
        m25 = json.load(f)
    for r in A_['tracking']['rows']:
        sc = m25['scenarios'][r['scenario']]
        assert r['stack_tracking_mean_m'] == sc['stack'][r['stack_controller']]['tracking_mean_m']
        assert r['model_tracking_mean_m'] == sc['model'][r['model_controller'].lower()]['summary']['tracking_mean_m']


def test_missions_name_only_measured_gaps():
    named = {g for m in missions.load() for g in m.get('gaps', [])}
    assert named and named <= set(fidelity.GAP_IDS)
    m = {x['id']: x for x in missions.load()}
    assert m['find-a-path'].get('gaps', []) == []  # planning on the true map depends on none
    assert 'lidar' in m['where-it-is']['gaps'] and 'tracking' in m['avoid-things']['gaps']


def test_a_mission_naming_an_unmeasured_gap_is_refused():
    import copy
    import pytest
    bad = copy.deepcopy(missions.load()[2])
    bad['gaps'] = ['friction']
    with pytest.raises(missions.MissionError, match='no model gap'):
        missions.check(bad, 'bad.yaml')
