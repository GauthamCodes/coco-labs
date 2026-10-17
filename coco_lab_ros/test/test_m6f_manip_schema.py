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
The manip.grasp family (M6F.5): coco_lab's emitter is the coco_schemas proto.

``coco_lab.grasp_assist.TABLES`` declares the CandidateBatch and StageBatch
columns (coco_lab never imports protobuf); ``envelope()`` is the GraspEnvelope
header. Here, where coco_schemas is importable, every column is held to its
field -- name, order and kind -- and a filled batch encodes and decodes.
"""

import math

from coco_lab import grasp_assist as ga
from coco_schemas.channels import BY_NAME, message_class, parse
from google.protobuf.descriptor import FieldDescriptor as FD
import pytest

KIND = {'Q': FD.TYPE_UINT64, 'd': FD.TYPE_DOUBLE, 'I': FD.TYPE_UINT32,
        'B': FD.TYPE_BOOL, 's': FD.TYPE_STRING}


def test_the_channels_are_registered_in_the_manip_grasp_family():
    for name, message, stream in (
            (ga.CH_ENVELOPE, 'coco.manip.v1.GraspEnvelope', False),
            (ga.CH_CANDIDATES, 'coco.manip.v1.CandidateBatch', True),
            (ga.CH_STAGES, 'coco.manip.v1.StageBatch', True)):
        ch = BY_NAME[name]
        assert (ch.family, ch.message, ch.stream) == ('manip.grasp', message, stream)
        assert parse(name)[0] == 'manip.grasp'


@pytest.mark.parametrize('message', sorted(ga.TABLES))
def test_the_table_is_the_messages_fields(message):
    fields = sorted(message_class(message).DESCRIPTOR.fields, key=lambda f: f.number)
    cols = (('seq', 'Q'), ('tick', 'Q'), ('t_world', 'd')) + ga.TABLES[message]
    assert [(f.name, f.type, f.label) for f in fields] == \
        [(n, KIND[t], FD.LABEL_REPEATED) for n, t in cols]


def test_the_envelope_header_is_the_grasp_envelope_message():
    env = ga.envelope()
    d = message_class('coco.manip.v1.GraspEnvelope').DESCRIPTOR
    assert [f.name for f in sorted(d.fields, key=lambda f: f.number)] == list(env)
    m = message_class('coco.manip.v1.GraspEnvelope')(**env)
    assert m.badge == 'MODEL · MoveIt-style' and m.headings == ga.HEADINGS


def test_a_filled_batch_round_trips_through_protobuf():
    b = ga.GraspBatch('coco.manip.v1.StageBatch')
    b.add(3, 0.3, attempt=1, stage='reach', object_id='obj', robot_x=1.0, robot_y=2.0,
          robot_theta=0.5, ahead=0.15375, left=0.0, ik_joint1=0.3, ik_joint2=0.58,
          outcome='ok')
    b.add(4, 0.4, attempt=1, stage='refused', object_id='', robot_x=1.0, robot_y=2.0,
          robot_theta=0.5, ahead=math.nan, left=math.nan, ik_joint1=math.nan,
          ik_joint2=math.nan, outcome='blocked')
    cols, _ = b.drain()
    cls = message_class('coco.manip.v1.StageBatch')
    m = cls(**{k: list(v) for k, v in cols.items()})
    back = cls.FromString(m.SerializeToString())
    assert list(back.stage) == ['reach', 'refused'] and list(back.seq) == [0, 1]
    assert back.ahead[0] == 0.15375 and math.isnan(back.ahead[1])
