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
The Learn missions' evidence check (M2.8), run in CI.

Content without evidence references fails here (README rule 5, "from M2
on"): every claim of every mission must cite something that resolves, and
every claim the v1 Lab 1-5 pages showed must be carried by some mission.
"""

import copy
import os
import re

from coco_lab.arena import Arena, ArenaError, InputEvent
import coco_lab.loc_arena  # noqa: F401 -- registers the subsystems
import coco_lab.map_arena  # noqa: F401
import coco_lab.mission_arena  # noqa: F401
import coco_lab.move_arena  # noqa: F401
import missions
import pytest
import yaml

MS = missions.load()
HEADS = missions.headings()


def _arena():
    with open(os.path.join(missions.REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as f:
        return Arena(yaml.safe_load(f), 1)


# -- the gate ---------------------------------------------------------------

def test_there_are_six_missions_numbered_in_order():
    assert [m['number'] for m in MS] == [1, 2, 3, 4, 5, 6]
    assert len({m['id'] for m in MS}) == 6


def test_every_claims_evidence_resolves():
    assert missions.evidence_problems(MS) == []


def test_every_v1_claim_is_carried_by_a_mission():
    where, uncovered, unknown = missions.coverage(MS)
    assert uncovered == [] and unknown == []
    assert len(where) == len(missions.v1_claims()) == 98


def test_the_coverage_document_is_current():
    with open(missions.COVERAGE, encoding='utf-8') as f:
        assert f.read() == missions.coverage_markdown(MS) + '\n', \
            'run: python3 lab_web/tools/missions.py --write'


def test_no_claim_says_real_robot():
    # no physical robot exists (CLAUDE.md): "real" is the stack in Gazebo
    for m in MS:
        for c in m['claims']:
            assert c['label'] != 'REAL ROBOT RESULT'
            assert not re.search(r'\breal robot\b', c['text'], re.I), (m['id'], c['id'])


def test_every_predict_reveal_cites_a_claim():
    for m in MS:
        for b in m['beats']:
            if b['beat'] in ('predict', 'reveal', 'explain', 'stack'):
                assert b.get('claims'), (m['id'], b['beat'])


# -- what a beat links to is something that exists -------------------------------

def test_every_arena_link_names_a_lens_and_level_the_page_has():
    src = open(os.path.join(missions.REPO, 'lab_web', 'src', 'arena', 'lens', 'registry.ts'), encoding='utf-8').read()
    lenses = re.findall(r"'(\w+)'", re.search(r'export type LensId = ([^;]+);', src).group(1))
    levels = re.findall(r"'(\w+)'", re.search(r'export type Level = ([^;]+);', src).group(1))
    for m in MS:
        assert m['lens'] in lenses
        for b in m['beats']:
            a = b.get('arena')
            if a and 'lens' in a:
                assert a['lens'] in lenses and a['level'] in levels, (m['id'], b['beat'])


def test_every_arena_config_line_is_accepted_by_the_arena():
    # a misspelled key raises ArenaError in the Arena itself; apply each
    # beat's lines to a fresh Arena, exactly as the page sends them
    n = 0
    for m in MS:
        for b in m['beats']:
            cfg = (b.get('arena') or {}).get('cfg', [])
            if cfg:
                a = _arena()
                a.step([InputEvent(0, 'config', choice=c) for c in cfg])
                n += len(cfg)
    assert n >= 10


def test_a_config_line_the_arena_does_not_know_is_refused():
    a = _arena()
    with pytest.raises(ArenaError):
        a.step([InputEvent(0, 'config', choice='localise.filtre=mcl')])


def test_replay_ids_have_the_viewers_form():
    for m in MS:
        for b in m['beats']:
            r = (b.get('arena') or {}).get('replay')
            if r:
                assert re.fullmatch(r'[a-z0-9_]{1,64}', r), r


# -- the resolver ---------------------------------------------------------------

def test_a_heading_reference_must_match_exactly_one_heading():
    assert missions.resolve('docs/RESULTS.md "COCO Lab Phase 6"', HEADS).startswith('docs/RESULTS.md > COCO Lab Phase 6')
    with pytest.raises(missions.MissionError, match='headings begin'):
        missions.resolve('docs/RESULTS.md "COCO Lab Phase"', HEADS)  # ambiguous
    with pytest.raises(missions.MissionError, match='0 headings'):
        missions.resolve('docs/RESULTS.md "No such heading anywhere"', HEADS)


def test_a_bold_paragraph_is_not_a_heading():
    # v1 cited this sentence as if it were a heading; it is a bold paragraph
    with pytest.raises(missions.MissionError):
        missions.resolve('docs/RESULTS.md "Global relocalization converges to an unplannable pose"', HEADS)


def test_a_test_reference_needs_the_file_and_the_function():
    ok = 'coco_lab/test/test_replan.py::test_every_round_agrees_with_astar_from_scratch'
    assert missions.resolve(ok, HEADS) == ok
    with pytest.raises(missions.MissionError, match='no function'):
        missions.resolve('coco_lab/test/test_replan.py::test_that_does_not_exist', HEADS)
    with pytest.raises(missions.MissionError, match='no such committed file'):
        missions.resolve('coco_lab/test/test_nothing.py', HEADS)
    with pytest.raises(missions.MissionError, match='not a reference'):
        missions.resolve('../outside.txt', HEADS)


# -- the shape -----------------------------------------------------------------

def _broken(edit):
    m = copy.deepcopy(MS[0])
    edit(m)
    with pytest.raises(missions.MissionError):
        missions.check(m, 'broken.yaml')


def test_the_seven_beats_are_required_in_order():
    _broken(lambda m: m['beats'].reverse())
    _broken(lambda m: m['beats'].pop())


def test_the_challenge_is_a_stub_until_m3():
    _broken(lambda m: m['beats'][-1].pop('stub'))


def test_a_predict_needs_a_valid_answer():
    _broken(lambda m: m['beats'][1].update(answer=99))


def test_the_v1_link_is_the_archive():
    _broken(lambda m: m.update(v1='?view=plan'))
    assert all(m['v1'].startswith('v1/?view=') for m in MS)


def test_a_claim_with_no_evidence_or_an_unknown_label_is_refused():
    _broken(lambda m: m['claims'][0].update(evidence=[]))
    _broken(lambda m: m['claims'][0].update(label='TRUST ME'))


def test_a_claim_no_beat_shows_is_refused():
    _broken(lambda m: m['claims'].append(dict(m['claims'][0], id='orphan')))


def test_an_unquoted_heading_with_a_colon_is_caught():
    # YAML reads `- docs/RESULTS.md "The one failure: run 15..."` as a mapping
    _broken(lambda m: m['claims'][0]['evidence'].append({'docs/RESULTS.md "The one failure': 'run 15"'}))


def test_the_site_json_carries_each_resolved_reference():
    s = missions.site_json(MS)
    assert s['schema'] == 'lab_web.missions'
    for m in s['missions']:
        for c in m['claims']:
            assert len(c['resolved']) == len(c['evidence'])
