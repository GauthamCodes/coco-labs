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

"""The channel registry, against the generated schemas."""

import ast
import os

from coco_schemas.channels import (BY_NAME, CHANNELS, FAMILIES, message_class,
                                   parse)
from conftest import PKG
from google.protobuf.descriptor import FieldDescriptor as FD
import pytest

CLOCKS = ((1, 'seq', FD.TYPE_UINT64), (2, 'tick', FD.TYPE_UINT64),
          (3, 't_world', FD.TYPE_DOUBLE))


def test_every_m1_family_has_a_channel():
    assert {c.family for c in CHANNELS} == set(FAMILIES) | {'envelope'}


@pytest.mark.parametrize('ch', CHANNELS, ids=lambda c: c.name)
def test_names_follow_coco_family_name_major(ch):
    family, _, major = parse(ch.name)
    assert family == ch.family
    # the name's major is the message package's major
    pkg = ch.message.rsplit('.', 1)[0]
    assert pkg.endswith(f'.v{major}'), (ch.name, ch.message)
    assert pkg.startswith('coco.')


@pytest.mark.parametrize('ch', CHANNELS, ids=lambda c: c.name)
def test_every_channel_message_exists(ch):
    cls = message_class(ch.message)
    assert cls.DESCRIPTOR.full_name == ch.message


@pytest.mark.parametrize('ch', CHANNELS, ids=lambda c: c.name)
def test_stream_messages_carry_the_three_clocks(ch):
    """Every event carries t_world, tick and seq: fields 1-3 of a batch."""
    d = message_class(ch.message).DESCRIPTOR
    assert ch.stream == d.name.endswith('Batch'), ch
    if not ch.stream:
        return
    by_number = d.fields_by_number
    for number, name, typ in CLOCKS:
        f = by_number[number]
        assert (f.name, f.type, f.label) == (name, typ, FD.LABEL_REPEATED)
    # every other repeated field is a column of the same length (scan's
    # `ranges` excepted: it is the concatenation of every scan's beams)
    for f in d.fields:
        if f.number > 3 and f.label != FD.LABEL_REPEATED:
            assert f.name == 'search_id', (ch.name, f.name)


def test_names_are_unique_and_parse_rejects_others():
    assert len(BY_NAME) == len(CHANNELS)
    for bad in ('coco.plan.v1', 'coco.nofamily.x.v1', 'plan.search.events.v1',
                'coco.plan.search.events.x.v1', 'coco.world.grid.v'):
        with pytest.raises(ValueError):
            parse(bad)


def test_the_package_never_imports_ros():
    for d, _, names in os.walk(os.path.join(PKG, 'coco_schemas')):
        for n in names:
            if not n.endswith('.py'):
                continue
            with open(os.path.join(d, n)) as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                mods = ([a.name for a in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ''] if isinstance(
                            node, ast.ImportFrom) else [])
                for m in mods:
                    assert not m.split('.')[0].startswith(('rclpy', 'rosidl')), n
