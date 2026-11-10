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
"""R4: the Learn course's data (lab_web/course/*.yaml) as the site build checks it (course.py)."""
import course
import pytest


@pytest.fixture(scope='module')
def modules():
    return course.load()


def test_ten_modules_and_three_tracks(modules):
    assert [m['number'] for m in modules] == list(range(1, 11))
    tracks = {les['track'] for m in modules for les in m['lessons']}
    assert tracks == set(course.TRACKS)


def test_every_claim_resolves_and_nothing_is_left_unverified(modules):
    assert course.evidence_problems(modules) == []
    assert course.unverified(modules) == []


def test_every_lesson_has_the_six_steps_and_a_short_explain(modules):
    from coco_lab import course as C
    ex = C.exercises()
    for m in modules:
        for les in m['lessons']:
            assert ex[les['predict']]['type'] == 'predict', les['id']
            assert les['try'] in ex, les['id']
            assert course._words(les['explain']['text']) <= course.MAX_EXPLAIN_WORDS, les['id']
            assert les['ros2']['claims'], les['id']


def test_a_bad_reference_is_refused():
    with pytest.raises(course.CourseError):
        course.resolve('docs/v2/r4/SOURCES.md > no-such-source', [], course.source_ids())
    with pytest.raises(course.CourseError):
        course.resolve('no/such/file.md', [], [])


def test_the_glossary_has_every_term_once():
    g = course.glossary()
    assert len(g) >= 50
    assert len({t['term'].lower() for t in g}) == len(g)
