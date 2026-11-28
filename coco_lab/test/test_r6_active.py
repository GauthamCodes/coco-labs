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
"""R6.A6: localisation v1.1 -- the robot's own "localised" report and the active scenarios."""
import json
from pathlib import Path

from coco_lab import experiments as ex
from coco_lab.localise import (
    REPORT_CLUSTER_W,
    REPORT_SIGMA_XY,
    REPORT_SIGMA_YAW,
    reports_localised,
)
import pytest

REPO = Path(__file__).resolve().parents[2]
ACTIVE = {'explore': 'rotate', 'angular': 0.5, 'max_s': 60.0}


def test_the_report_rule_is_the_filters_own_spread_and_mcls_cluster_weight():
    assert reports_localised(REPORT_SIGMA_XY, REPORT_SIGMA_YAW)
    assert not reports_localised(REPORT_SIGMA_XY + 0.01, 0.0)
    assert not reports_localised(0.0, REPORT_SIGMA_YAW + 0.01)
    assert reports_localised(0.1, 0.1, REPORT_CLUSTER_W)
    assert not reports_localised(
        0.1, 0.1, REPORT_CLUSTER_W - 0.01
    )  # a tight cluster holding too little


def test_active_survives_an_inline_scenario_and_bad_values_are_refused():
    sc = {
        'id': 'a1',
        'start': [23.0, 6.0, 0.0],
        'goal': [26.0, 6.5],
        'seed': 1,
        'active': dict(ACTIVE),
    }
    got = ex._inline(ex.world('coco_depot_v1'), [sc])
    assert got[0]['active'] == ACTIVE  # the held-out path once dropped it
    for bad in ({'explore': 'fly'}, {'angular': 5.0}, {'max_s': 0}, {'what': 1}, 'rotate'):
        with pytest.raises(ex.SpecError):
            ex._inline(ex.world('coco_depot_v1'), [dict(sc, active=bad)])


def test_every_list_that_copies_scenarios_keeps_active():
    for f, name in (
        ('tools/r3/make_baselines.py', "'kidnap', 'active')"),
        ('tools/r2/leaderboard.py', "'kidnap', 'active')"),
        ('tools/r3/heldout.py', "'kidnap', 'active')"),
    ):
        assert name in (REPO / f).read_text(), f
    assert 'active' in ex.INLINE_KEYS


def test_the_active_suites_carry_active_and_their_own_metrics():
    for sid in ('loc-global-active-20', 'loc-kidnap-active-20'):
        doc = json.loads((REPO / f'coco_lab/coco_lab/benchmarks/{sid}.v1.json').read_text())
        assert all(s['active'] == ACTIVE for s in doc['scenarios'])
        assert 'time_to_localise_s' in doc['metrics']['localisation']
    v1 = json.loads((REPO / 'coco_lab/coco_lab/benchmarks/loc-kidnap-20.v1.json').read_text())
    assert 'time_to_localise_s' not in v1['metrics']['localisation']  # the v1 suites are unchanged
    assert ex.metric_defs('localisation') == ex.METRICS['localisation']
