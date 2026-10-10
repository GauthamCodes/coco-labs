# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
Play's committed levels (M3.5): lab_web/play/levels.json and
docs/v2/CHALLENGES.md are what make_play_levels.py computes, every level's
references set its stars apart, and the map challenge re-simulates a drive
by its rules.
"""

import copy
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import make_play_levels as mk  # noqa: E402
from coco_lab import play  # noqa: E402

with open(mk.OUT, encoding='utf-8') as f:
    LEVELS = json.load(f)
SPEC = mk.spec()
MAP = LEVELS['challenges']['map-the-arena']['levels']


def _sub(challenge, lv, inputs):
    return {'v': 1, 'challenge': challenge, 'level': lv['id'], 'level_hash': play.level_hash(lv), 'inputs': inputs}


def test_the_committed_levels_and_challenges_doc_are_current():
    # re-runs every reference algorithm and re-simulates every reference drive
    r = subprocess.run([sys.executable, mk.__file__, '--check'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_five_challenges_and_every_levels_stars_mean_something():
    # the file's keys are sorted; the page shows them in this order
    assert tuple(LEVELS['order']) == play.CHALLENGES and set(LEVELS['challenges']) == set(play.CHALLENGES)
    for cid, c in LEVELS['challenges'].items():
        assert len(c['levels']) >= 2
        for lv in c['levels']:
            mk.check(cid, lv)
    ids = [(cid, lv['id']) for cid, c in LEVELS['challenges'].items() for lv in c['levels']]
    assert len(ids) == len(set(ids))


def test_the_detectives_moments_are_the_committed_derived_ones():
    with open(mk.MOMENTS, encoding='utf-8') as f:
        m = json.load(f)
    for lv in LEVELS['challenges']['case-file-detective']['levels']:
        assert lv['moment']['tick'] == m['casefiles'][lv['casefile']]['divergence']['tick']
        assert lv['ticks'] == m['casefiles'][lv['casefile']]['ticks']


def test_a_reference_drive_scores_exactly_its_reference_and_its_stars():
    lv = MAP[1]
    ref = lv['reference']
    weak, strong = sorted(('out_and_back', 'tour'), key=lambda k: ref[k]['f1'])
    for name, stars in ((weak, 1), (strong, 3)):
        d = lv['drives'][name]
        r = play.score(LEVELS, _sub('map-the-arena', lv, {'ticks': d['ticks'], 'log': d['inputs']}), SPEC)
        got = {m['name']: m['value'] for m in r['metrics']}
        assert (got['f1'], got['ate']) == (ref[name]['f1'], ref[name]['ate'])
        assert r['stars'] == stars


def test_inputs_after_the_budget_is_spent_change_nothing():
    lv = MAP[1]
    d = lv['drives']['tour']
    base = play.map_drive(SPEC, lv, d['inputs'], d['ticks'])
    late = d['inputs'] + [{'tick': d['ticks'] + 5, 'kind': 'goal', 'x': 12.0, 'y': 6.0}]
    after = play.map_drive(SPEC, lv, late, d['ticks'] + 400)
    assert after == base and base['path_m'] >= lv['budget_m']


@pytest.mark.parametrize('edit', [
    lambda log: log.insert(2, {'tick': 0, 'kind': 'config', 'choice': 'map.poses=truth'}),   # a better pose source
    lambda log: log.pop(0),                                                                  # the level's config dropped
    lambda log: log.append({'tick': 50, 'kind': 'kidnap', 'x': 6.0, 'y': 4.0, 'theta': 0.0, 'has_theta': True}),
    lambda log: log.append({'tick': 50, 'kind': 'reset'}),
])
def test_a_drive_may_only_drive(edit):
    lv = MAP[1]
    log = copy.deepcopy(lv['drives']['tour']['inputs'])
    edit(log)
    with pytest.raises(play.PlayError):
        play.score(LEVELS, _sub('map-the-arena', lv, {'ticks': 100, 'log': log}), SPEC)


def test_the_levels_config_may_land_a_few_ticks_in_but_never_after_driving():
    lv = MAP[1]
    log = copy.deepcopy(lv['drives']['tour']['inputs'])
    goals = [r for r in log if r['kind'] == 'goal']
    late = [dict(r, tick=4) if r['kind'] == 'config' else r for r in log]
    for g in goals:
        g['tick'] += 4
    late = [r for r in late if r['kind'] == 'config'] + goals
    play.map_drive(SPEC, lv, late, 30)                   # the page's way: configs at tick 4, then the goal
    after = [dict(r, tick=goals[0]['tick'] + 1) if r['kind'] == 'config' else r for r in late]
    with pytest.raises(play.PlayError, match='before it drives'):
        play.map_drive(SPEC, lv, after, 30)


def test_the_map_challenge_needs_its_world_spec():
    lv = MAP[0]
    other = copy.deepcopy(SPEC)
    other['start']['x'] = -1.5
    for spec in (None, other):
        with pytest.raises(play.PlayError, match='World Spec'):
            play.score(LEVELS, _sub('map-the-arena', lv, {'ticks': 10, 'log': lv['drives']['tour']['inputs'][:2]}), spec)
