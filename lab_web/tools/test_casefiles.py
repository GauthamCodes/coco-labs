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

"""The Case Files (M3.3): the evidence check extended to them, the inventory, the budget."""

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import casefiles as C  # noqa: E402
import missions  # noqa: E402


@pytest.fixture(scope='module')
def loaded():
    return C.load()


def test_every_case_file_passes_the_check(loaded):
    doc, index = loaded
    assert C.text_problems(doc) == []
    assert C.inventory_problems(doc, index) == []


def test_a_sentence_without_evidence_fails_the_check(loaded):
    doc, _ = loaded
    bad = copy.deepcopy(doc)
    bad['groups'][0]['explain'].append({'label': 'MEASURED', 'text': 'a claim', 'evidence': []})
    assert any('cites nothing' in p for p in C.text_problems(bad))
    bad['groups'][0]['explain'][-1]['evidence'] = ['docs/RESULTS.md "No such heading anywhere"']
    assert any('0 headings' in p for p in C.text_problems(bad))


def test_an_unresolved_question_stays_unresolved(loaded):
    doc, _ = loaded
    bad = copy.deepcopy(doc)
    g = next(g for g in bad['groups'] if g.get('unresolved'))
    g['unresolved'][0]['label'] = 'MEASURED'
    assert any('must stay labelled UNRESOLVED' in p for p in C.text_problems(bad))


def test_a_label_outside_the_learner_set_fails(loaded):
    doc, _ = loaded
    bad = copy.deepcopy(doc)
    bad['groups'][0]['explain'][0]['label'] = 'PROVEN'
    assert any('not a learner label' in p for p in C.text_problems(bad))


def test_a_missing_recording_or_an_oversized_file_fails(loaded):
    doc, index = loaded
    bad = copy.deepcopy(index)
    gone = bad['casefiles'].pop(0)
    assert any(gone['id'] in p for p in C.inventory_problems(doc, bad))
    bad = copy.deepcopy(index)
    bad['casefiles'][0]['bytes'] = C.PER_FILE_BUDGET + 1
    assert any('over the per-file budget' in p for p in C.inventory_problems(doc, bad))


def test_the_inventory_is_every_recording_the_committed_data_names(loaded):
    doc, index = loaded
    groups = {}
    for e in index['casefiles']:
        groups.setdefault(e['group'], []).append(e)
    assert len(groups['lab4-search']) == 16 + 1          # the matrix and its void
    assert len(groups['lab5-move']) == 54
    assert len(groups['lab1-runs']) == 3
    assert len(groups['lab2-kidnap']) == 23               # 20 valid + 3 void, as the record holds
    assert index['total_bytes'] <= C.TOTAL_BUDGET


def test_every_cited_checksum_was_checked_by_its_labs_definition(loaded):
    _, index = loaded
    for e in index['casefiles']:
        if e['group'] in ('lab4-search', 'lab5-move', 'lab1-runs') and not e['case'].get('void'):
            assert e['checksum']['checked'], e['id']
            assert e['checksum']['definition'] in ('p05_sha_dir', 'lab5_bag_0', 'export_dir_sha256')


def test_every_generated_fact_cites_committed_evidence(loaded):
    doc, index = loaded
    heads = missions.headings()
    n = 0
    for e in index['casefiles']:
        for f in C.facts(doc, e):
            assert f['label'] in C.LABELS and f['evidence']
            for r in f['evidence']:
                missions.resolve(r, heads)
            n += 1
    assert n >= len(index['casefiles'])


def test_run15_is_its_nine_reproductions(loaded):
    site = C.site_json(*loaded)
    g = next(g for g in site['groups'] if g['id'] == 'run15')
    assert len(g['members']) == 9 and all('mislocalised' in m for m in g['members'])
    assert any('UNRESOLVED' == u['label'] for u in g['unresolved'])


def test_the_model_side_names_the_same_scenario(loaded):
    site = C.site_json(*loaded)
    lab5 = next(g for g in site['groups'] if g['id'] == 'lab5-move')
    c = next(c for c in lab5['casefiles'] if c['id'] == 'lab5_crossing_dwb_1')
    assert 'cfg=move.scenario=crossing' in c['compare'] and 'cfg=move.controller=dwa' in c['compare']
    lab4 = next(g for g in site['groups'] if g['id'] == 'lab4-search')
    c = next(c for c in lab4['casefiles'] if c['id'] == 'lab4_a1_fixed_red')
    assert 'cfg=mission.truth=bay_1' in c['compare'] and 'cfg=mission.start=red' in c['compare']
