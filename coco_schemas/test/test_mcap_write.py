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

"""The Python run-file writer round-trips through the reader (M3.1)."""

from coco_schemas import mcap_read, mcap_write
from coco_schemas.channels import message_class
from google.protobuf import descriptor_pb2
import pytest

Manifest = message_class('coco.envelope.v1.Manifest')
TruthPoseBatch = message_class('coco.truth.v1.TruthPoseBatch')
ScanBatch = message_class('coco.sensor.v1.ScanBatch')


def sample():
    w = mcap_write.RunWriter()
    m = Manifest(run_id='abc', spec_format='test', tier=2, evidence_class=2)
    w.add('coco.envelope.manifest.v1', m, 0)
    p = TruthPoseBatch(seq=[0, 1], tick=[0, 1], t_world=[0.0, 0.1], x=[1.0, 1.1],
                       y=[2.0, 2.1], theta=[0.0, 0.05])
    w.add('coco.truth.pose.v1', p, 0, sequence=0)
    s = ScanBatch(seq=[2], tick=[1], t_world=[0.1], angle_min=[-3.14], angle_increment=[0.01],
                  range_min=[0.15], range_max=[12.0], count=[3], ranges=[1.0, 2.0, float('inf')])
    w.add('coco.sensor.scan.lidar.v1', s, 100_000_000, sequence=2)
    w.add('coco.truth.pose.v1', TruthPoseBatch(seq=[3], tick=[2], t_world=[0.2], x=[1.2],
                                               y=[2.2], theta=[0.1]), 200_000_000, sequence=3)
    return w, m, p, s


def test_every_message_comes_back_byte_for_byte_in_order():
    w, m, p, s = sample()
    msgs = mcap_read.read_messages(w.finish('abc'))
    assert [x.channel for x in msgs] == ['coco.envelope.manifest.v1', 'coco.truth.pose.v1',
                                         'coco.sensor.scan.lidar.v1', 'coco.truth.pose.v1']
    assert [x.schema for x in msgs] == [
        'coco.envelope.v1.Manifest', 'coco.truth.v1.TruthPoseBatch',
        'coco.sensor.v1.ScanBatch', 'coco.truth.v1.TruthPoseBatch']
    assert [x.log_time for x in msgs] == [0, 0, 100_000_000, 200_000_000]
    assert [x.sequence for x in msgs] == [0, 0, 2, 3]
    assert msgs[1].data == p.SerializeToString()
    back = ScanBatch.FromString(msgs[2].data)
    assert list(back.ranges)[:2] == [1.0, 2.0] and back.count == [3]
    assert Manifest.FromString(msgs[0].data).run_id == 'abc'


def test_the_schema_carries_the_message_file_and_its_dependencies():
    fds = descriptor_pb2.FileDescriptorSet.FromString(
        mcap_write.file_descriptor_set(Manifest.DESCRIPTOR))
    names = [f.name for f in fds.file]
    assert names[-1] == Manifest.DESCRIPTOR.file.name
    for dep in Manifest.DESCRIPTOR.file.dependencies:
        assert names.index(dep.name) < len(names) - 1   # dependencies come first


def test_a_channel_cannot_change_its_message_type():
    w = mcap_write.RunWriter()
    w.add('coco.truth.pose.v1', TruthPoseBatch(), 0)
    with pytest.raises(ValueError, match='another message type'):
        w.add('coco.truth.pose.v1', ScanBatch(), 1)


def test_a_negative_log_time_is_refused():
    with pytest.raises(ValueError, match='negative'):
        mcap_write.RunWriter().add('coco.truth.pose.v1', TruthPoseBatch(), -1)


def test_the_file_is_framed_like_an_mcap_file():
    w, *_ = sample()
    b = w.finish('abc')
    assert b[:8] == mcap_write.MAGIC and b[-8:] == mcap_write.MAGIC
    assert b[8] == mcap_write.OP_HEADER
