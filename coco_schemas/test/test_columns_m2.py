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
coco_lab's M2 column tables ARE the M2 schemas (ADR 0001, M2.1).

``coco_lab.columns`` declares every whole-loop ``*Batch`` message without
protobuf; here each table is held to the generated descriptor -- names,
order, kinds, per-batch scalars -- and a batch filled through
``coco_lab.columns.Batch`` must survive protobuf's encode and decode.
"""

import math
import random

from coco_lab.columns import Batch, CLOCKS, FLAT, TABLES
from coco_schemas.channels import CHANNELS, M2_FAMILIES, message_class
from google.protobuf.descriptor import FieldDescriptor as FD
import pytest

KIND = {
    'Q': {FD.TYPE_UINT64}, 'd': {FD.TYPE_DOUBLE}, 'f': {FD.TYPE_FLOAT},
    'I': {FD.TYPE_UINT32}, 'i': {FD.TYPE_INT32, FD.TYPE_SINT32},
    'B': {FD.TYPE_BOOL}, 's': {FD.TYPE_STRING},
}
# stream messages encoded another way: the snapshot is one bytes blob
NOT_COLUMNAR = {'coco.map.v1.MapGridSnapshotBatch'}
M2_STREAMS = sorted({c.message for c in CHANNELS
                     if c.family in M2_FAMILIES and c.stream})


def test_every_m2_family_has_a_channel():
    assert {c.family for c in CHANNELS if c.family in M2_FAMILIES} == \
        set(M2_FAMILIES)


def test_every_m2_stream_message_has_a_column_table():
    assert sorted(TABLES) == sorted(set(M2_STREAMS) - NOT_COLUMNAR)


@pytest.mark.parametrize('message', sorted(TABLES))
def test_the_table_is_the_messages_fields(message):
    d = message_class(message).DESCRIPTOR
    fields = sorted(d.fields, key=lambda f: f.number)
    cols, scalars = TABLES[message]
    repeated = [f for f in fields if f.label == FD.LABEL_REPEATED]
    single = [f for f in fields if f.label != FD.LABEL_REPEATED]
    assert [f.name for f in repeated] == [n for n, _ in CLOCKS + cols]
    for f, (_, t) in zip(repeated, CLOCKS + cols):
        assert f.type in KIND[t], (message, f.name)
    assert [f.name for f in single] == [n for n, _ in scalars]
    for f, (_, t) in zip(single, scalars):
        assert f.type in KIND[t], (message, f.name)


def _value(t, rng):
    if t == 'd':
        return rng.choice([rng.uniform(-50, 50), 0.0, math.inf])
    if t == 'f':
        return float(rng.randint(-64, 64)) / 4.0   # exact in float32
    if t in 'QI':
        return rng.randint(0, 5000)
    if t == 'i':
        return rng.randint(-5000, 5000)
    if t == 'B':
        return rng.random() < 0.5
    return rng.choice(['', 'collision', 'ok', 'α-β'])


@pytest.mark.parametrize('message', sorted(TABLES))
def test_a_filled_batch_survives_protobuf(message):
    rng = random.Random(message)
    cols, scalars = TABLES[message]
    b = Batch(message, **{n: _value(t, rng) for n, t in scalars})
    for k in range(17):
        b.add(k // 3, k * 0.1,
              **{n: _value(t, rng) for n, t in cols if n not in FLAT})
    for n, t in cols:
        if n in FLAT:
            b.extend_flat(n, [_value(t, rng) for _ in range(29)])
    columns, sc = b.drain()
    plain = {n: [bool(x) for x in v] if t == 'B' else list(v)
             for n, t in CLOCKS + cols for v in [columns[n]]}
    cls = message_class(message)
    msg = cls(**plain, **sc)
    back = cls.FromString(msg.SerializeToString())
    for n, _ in CLOCKS + cols:
        assert list(getattr(back, n)) == plain[n], n
    for n, _ in scalars:
        assert getattr(back, n) == sc[n], n
    assert len(b) == 0 and b.seq == 17


def test_batches_refuse_unknown_scalars_and_flat_columns():
    with pytest.raises(KeyError):
        Batch('coco.estimate.v1.EstimateBatch', nope=1)
    with pytest.raises(KeyError):
        Batch('coco.nope.v1.X')
    b = Batch('coco.control.v1.CandidateBatch')
    with pytest.raises(KeyError):
        b.extend_flat('v', [1.0])


def test_the_committed_cross_language_vectors_are_current():
    """make_vectors_m2.py regenerates m2_batches.json byte for byte."""
    import importlib.util
    import json
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        'make_vectors_m2', os.path.join(here, '..', 'scripts',
                                        'make_vectors_m2.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = json.dumps(mod.vectors(), indent=1, ensure_ascii=False) + '\n'
    with open(os.path.join(here, 'vectors', 'm2_batches.json'),
              encoding='utf-8') as f:
        assert f.read() == text
