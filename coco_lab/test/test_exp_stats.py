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

"""R1: the experiment statistics against hand-computed values and brute force."""

from itertools import product
import math as libm
import random

from coco_lab import exp_stats as st
import pytest


def test_wilson_matches_hand_computed_values():
    # 8 of 10: centre (0.8 + 1.92/20) / 1.384, half-width as in Wilson (1927)
    w = st.wilson(8, 10)
    assert w['rate'] == 0.8
    assert abs(w['low'] - 0.4901624) < 1e-6 and abs(w['high'] - 0.9433178) < 1e-6
    assert st.wilson(0, 10)['low'] == 0.0 and abs(st.wilson(0, 10)['high'] - 0.2775328) < 1e-6
    assert st.wilson(10, 10)['high'] == 1.0
    assert st.wilson(0, 0) is None


def test_quantiles_are_type_7():
    xs = [1.0, 2.0, 3.0, 4.0]
    assert st.quantile(xs, 0.25) == 1.75 and st.quantile(xs, 0.5) == 2.5
    assert st.quantile(xs, 0.75) == 3.25 and st.quantile([5.0], 0.5) == 5.0
    d = st.describe([3.0, None, 1.0, 2.0, 4.0])
    assert d['n'] == 4 and d['median'] == 2.5 and d['iqr'] == 1.5
    assert st.describe([None])['n'] == 0


def test_midranks():
    assert st.ranks([10.0, 20.0, 20.0, 30.0]) == [1.0, 2.5, 2.5, 4.0]


def _brute_p(d):
    """Two-sided exact p by enumerating every sign pattern (zeros dropped, midranks)."""
    nz = [v for v in d if v != 0]
    r = st.ranks([abs(v) for v in nz])
    w = sum(rk for rk, v in zip(r, nz) if v > 0)
    sums = [sum(rk for rk, s in zip(r, signs) if s) for signs in product((0, 1), repeat=len(r))]
    lo = sum(1 for s in sums if s <= w + 1e-9)
    hi = sum(1 for s in sums if s >= w - 1e-9)
    return min(1.0, 2 * min(lo, hi) / len(sums))


def test_exact_wilcoxon_equals_enumeration_with_ties_and_zeros():
    rng = random.Random(11)
    for _ in range(60):
        n = rng.randrange(6, 13)
        a = [rng.choice([1.0, 2.0, 3.0, 4.0, 5.0]) for _ in range(n)]
        b = [rng.choice([1.0, 2.0, 3.0, 4.0, 5.0]) for _ in range(n)]
        res = st.wilcoxon(a, b)
        if res['p'] is None:
            assert res['reason']
            continue
        assert res['method'] == 'exact'
        assert abs(res['p'] - _brute_p([x - y for x, y in zip(a, b)])) < 1e-12


def test_wilcoxon_hand_computed_case_and_effect_sizes():
    res = st.wilcoxon([2.0, 3.0, 4.0, 5.0, 6.0, 7.0], [1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    assert res['w_plus'] == 21 and res['w_minus'] == 0
    assert res['p'] == 2 / 64 and res['rank_biserial'] == 1.0
    assert res['hodges_lehmann'] == 3.5 and res['median_diff'] == 3.5
    swapped = st.wilcoxon([1.0] * 6, [2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    assert swapped['p'] == res['p'] and swapped['rank_biserial'] == -1.0


def test_wilcoxon_says_why_when_it_cannot_test():
    assert 'all paired differences are 0' in st.wilcoxon([1.0] * 8, [1.0] * 8)['reason']
    assert 'too few' in st.wilcoxon([1.0, 2.0], [0.0, 0.0])['reason']
    res = st.wilcoxon([1.0, None, 3.0], [0.0, 2.0, None])
    assert res['n_pairs'] == 1 and res['n_excluded'] == 2
    assert st.wilcoxon([], [])['reason'] == 'no pairs'


def test_normal_approximation_tracks_the_exact_test(monkeypatch):
    rng = random.Random(5)
    for _ in range(5):
        d = [rng.gauss(0.3, 1.0) for _ in range(50)]
        exact = st.wilcoxon(d, [0.0] * 50)
        monkeypatch.setattr(st, 'EXACT_MAX', 10)
        approx = st.wilcoxon(d, [0.0] * 50)
        monkeypatch.setattr(st, 'EXACT_MAX', 50)
        assert exact['method'] == 'exact' and approx['method'] == 'normal_approximation'
        assert abs(exact['p'] - approx['p']) < 0.005


def test_erfc_accuracy():
    for x in [0.0, 0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, -0.7, -2.0]:
        assert abs(st.erfc(x) - libm.erfc(x)) <= 1.2e-7 * max(libm.erfc(x), 1e-300) + 1e-15


def test_mcnemar_exact():
    a = [True] * 8 + [False] * 2 + [True] * 5
    b = [False] * 8 + [True] * 2 + [True] * 5
    res = st.mcnemar(a, b)
    assert res['a_only'] == 8 and res['b_only'] == 2
    assert res['p'] == 2 * (1 + 10 + 45) / 1024
    assert res['risk_difference'] == 6 / 15
    assert 'no discordant' in st.mcnemar([True, False], [True, False])['reason']


def test_holm():
    assert st.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert st.holm([None, 0.5]) == [None, 0.5]
    assert st.verdict(0.2) == 'no significant difference'
    assert st.verdict(0.01) == 'significant difference' and st.verdict(None) == 'no test'
