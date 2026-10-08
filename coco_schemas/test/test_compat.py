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

"""Within a major, changes are compatible; the checker catches each kind."""

import copy
import os
import subprocess
import sys

from coco_schemas.compat import BASELINE, load, problems
from conftest import PKG
from google.protobuf import descriptor_pb2
import pytest

GEN = os.path.join(PKG, 'scripts', 'generate.py')
FDP = descriptor_pb2.FieldDescriptorProto


@pytest.fixture(scope='module')
def current(tmp_path_factory):
    path = str(tmp_path_factory.mktemp('fds') / 'current.binpb')
    subprocess.run([sys.executable, GEN, '--descriptor-set', path], check=True)
    return load(path)


@pytest.fixture(scope='module')
def baseline():
    return load(BASELINE)


def _message(fds, full):
    pkg, name = full.rsplit('.', 1)
    for f in fds.file:
        if f.package == pkg:
            for m in f.message_type:
                if m.name == name:
                    return m
    raise KeyError(full)


def _enum(fds, full):
    pkg, name = full.rsplit('.', 1)
    for f in fds.file:
        if f.package == pkg:
            for e in f.enum_type:
                if e.name == name:
                    return e
    raise KeyError(full)


def test_the_committed_schemas_are_compatible_with_the_v1_baseline(
        baseline, current):
    assert problems(baseline, current) == []


def test_adding_a_field_a_message_and_an_enum_value_is_compatible(baseline):
    new = copy.deepcopy(baseline)
    m = _message(new, 'coco.plan.v1.SearchEventBatch')
    m.field.add(name='extra', number=99, type=FDP.TYPE_DOUBLE,
                label=FDP.LABEL_REPEATED)
    new.file[0].message_type.add(name='Brand_new')
    _enum(new, 'coco.plan.v1.SearchEventKind').value.add(name='X', number=9)
    assert problems(baseline, new) == []


@pytest.mark.parametrize('change', [
    'remove_field', 'retype_field', 'rename_field', 'renumber_enum',
    'remove_message', 'make_optional'])
def test_each_breaking_change_is_caught(baseline, change):
    new = copy.deepcopy(baseline)
    m = _message(new, 'coco.plan.v1.SearchSummary')
    if change == 'remove_field':
        del m.field[2]
    elif change == 'retype_field':
        m.field[2].type = FDP.TYPE_INT32
    elif change == 'rename_field':
        m.field[2].name = 'renamed'
    elif change == 'renumber_enum':
        _enum(new, 'coco.plan.v1.SearchStatus').value[1].number = 7
    elif change == 'remove_message':
        for f in new.file:
            if f.package == 'coco.plan.v1':
                for i, mm in enumerate(f.message_type):
                    if mm.name == 'SearchSummary':
                        del f.message_type[i]
                        break
    elif change == 'make_optional':
        m.field[2].proto3_optional = True
    assert problems(baseline, new), change


def test_a_removal_done_properly_is_compatible(baseline):
    new = copy.deepcopy(baseline)
    m = _message(new, 'coco.plan.v1.SearchSummary')
    gone = m.field[2]
    m.reserved_range.add(start=gone.number, end=gone.number + 1)
    m.reserved_name.append(gone.name)
    del m.field[2]
    assert problems(baseline, new) == []
