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

"""The fast v2 encoder is byte-identical, including mutation and alias coverage."""
import json
from pathlib import Path
from types import SimpleNamespace

from coco_lab import state_v2
from coco_lab.compare_loop import LoopComparison
import pytest
import yaml


def same(arena):
    encoded = state_v2.snapshot(arena)
    assert encoded == state_v2.snapshot(arena, memo_vectors=False)
    return encoded


def test_float_vectors_detect_values_types_signed_zero_and_token_collisions():
    values = [float(i) / 8 for i in range(2048)]
    values[:4] = [-0.0, float('inf'), float('-inf'), float('nan')]
    arena = SimpleNamespace(_v2_world='test', data=values, alias=values,
                            text='@coco-v2-vector@0', text2='@@coco-v2-vector@0')
    before = same(arena)
    values[10] = 3.125
    assert same(arena) != before
    values[10] = 1.25
    assert same(arena) == before
    values[10] = 1
    assert same(arena) != before  # int and float must never share an encoding
    values[10] = 1.25
    values[0] = 0.0
    assert same(arena) != before
    values[0] = -0.0
    assert same(arena) == before


def test_integer_cell_vectors_keep_all_external_and_internal_aliases():
    cells = [(i, i % 17) for i in range(2048)]
    arena = SimpleNamespace(_v2_world='test', cells=cells, z_alias=cells[27])
    same(arena)
    arena.a_earlier_alias = cells[27]
    same(arena)
    del arena.a_earlier_alias
    cells[500] = cells[27]
    same(arena)
    cells[500] = (500.0, 7)
    same(arena)


def test_float_cache_is_bounded_and_content_keyed():
    state_v2._FLOAT_ENCODINGS.clear()
    for i in range(state_v2._MAX_FLOAT_ENCODINGS + 3):
        same(SimpleNamespace(_v2_world='test', values=[float(i)] * 1024))
    assert len(state_v2._FLOAT_ENCODINGS) == state_v2._MAX_FLOAT_ENCODINGS


@pytest.mark.parametrize('index', [0, 1])
def test_saved_pre_optimization_mcl_and_ekf_hashes_stay_unchanged(index):
    repo = Path(__file__).resolve().parents[2]
    path = repo / 'docs/v2/data/m5/compare/v2-reference-hashes-before-cache.json'
    record = json.loads(path.read_text())
    spec = yaml.safe_load((repo / 'worlds/coco_arena_v1.yaml').read_text())
    case = record['cases'][index]
    comparison = LoopComparison(spec, case['request'])
    for expected in case['hashes']:
        assert [row['hash'] for row in comparison.advance()] == expected
        for arm in comparison.arms:
            same(arm)
