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

"""coco_lab.rng is xoshiro256** seeded by SplitMix64, bit for bit."""

import json
import os
import statistics

from coco_lab.rng import MASK, Rng, splitmix64
import pytest

VECTORS = os.path.join(os.path.dirname(__file__), 'rng_vectors.json')


def cases():
    with open(VECTORS) as f:
        return json.load(f)['cases']


@pytest.mark.parametrize('case', cases(), ids=lambda c: c['seed'])
def test_matches_the_reference_c_implementation(case):
    """Vectors from docs/v2/data/m1/rng/xoshiro_reference.c (gcc 13.3)."""
    r = Rng(int(case['seed']))
    assert [str(r.next_u64()) for _ in range(8)] == case['first']


def test_splitmix64_first_output_from_zero():
    # the generator's published first output for state 0
    assert splitmix64(0)[0] == 0xE220A8397B1DCDAF


def test_random_is_in_unit_interval_and_gauss_is_standard():
    r = Rng(7)
    u = [r.random() for _ in range(20000)]
    assert 0.0 <= min(u) and max(u) < 1.0
    assert abs(statistics.fmean(u) - 0.5) < 0.01
    g = [r.gauss() for _ in range(20000)]
    assert abs(statistics.fmean(g)) < 0.03
    assert abs(statistics.pstdev(g) - 1.0) < 0.03


def test_gauss_always_consumes_two_draws():
    a, b = Rng(3), Rng(3)
    a.gauss()
    b.random()
    b.random()
    assert a.state == b.state


def test_split_streams_are_independent_and_repeatable():
    a = Rng(11).split()
    b = Rng(11).split()
    assert [a.next_u64() for _ in range(4)] == [b.next_u64() for _ in range(4)]
    parent = Rng(11)
    child = parent.split()
    assert child.next_u64() != parent.next_u64()


@pytest.mark.parametrize('seed', [-1, MASK + 1, 1.0, '1', True, None])
def test_bad_seeds_are_refused(seed):
    with pytest.raises(ValueError):
        Rng(seed)
