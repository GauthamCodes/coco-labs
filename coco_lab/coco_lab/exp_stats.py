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
Honest statistics for experiments (R1), standard library only.

The browser's trimmed standard library has no ``statistics`` module, and an
experiment's summary must be byte-identical in CPython and in Pyodide, so
everything here is written from basic IEEE operations, ``math.sqrt`` (correctly
rounded everywhere) and, for the one transcendental the normal approximation
needs, :func:`coco_lab.numerics.exp` (fdlibm, deterministic: ADR 0010).

- :func:`wilson`: a success rate's Wilson score 95% interval.
- :func:`quantile`: linear interpolation between order statistics (Hyndman and
  Fan's type 7, numpy's and pandas' default, so the notebook reproduces it).
- :func:`describe`: N, median, IQR, min and max of the defined values.
- :func:`wilcoxon`: the Wilcoxon signed-rank test on paired differences. Zero
  differences are dropped (Wilcoxon's own treatment); ties get midranks. The
  p-value is exact (the conditional distribution of the signed-rank sum, by
  dynamic programming over doubled ranks, with integer counts) for up to
  :data:`EXACT_MAX` non-zero pairs; above that it is the normal approximation
  with tie and continuity corrections. Effect sizes come with every p-value:
  the matched-pairs rank-biserial correlation (Kerby 2014) and the
  Hodges-Lehmann estimate of the shift (the median of the Walsh averages).
- :func:`mcnemar`: paired success/failure, the exact (binomial) McNemar test.
  Wilcoxon is wrong for a binary outcome; the risk difference is the effect size.
- :func:`holm`: Holm's step-down adjustment when more than two algorithms are
  compared pairwise.

Nothing here guesses: a test that cannot be computed returns a ``reason``
instead of a number.
"""

from typing import Dict, List, Optional, Sequence

from .numerics import exp as _exp
from .numerics import math as _m

#: two-sided 95% normal quantile
Z95 = 1.959963984540054
#: the significance level the words "significant difference" use
ALPHA = 0.05
#: exact Wilcoxon p-values up to this many non-zero differences
EXACT_MAX = 50
#: fewer non-zero pairs than this: no test (the smallest exact two-sided p
#: with n = 5 is 0.0625, so a test could never reject at 0.05)
MIN_PAIRS = 6
#: Hodges-Lehmann from all Walsh averages up to this many pairs, else the
#: median difference (stated in the result)
HL_MAX = 2000


def wilson(k: int, n: int, z: float = Z95) -> Optional[Dict[str, float]]:
    """Return ``{rate, low, high}`` for ``k`` successes in ``n``, or None for n = 0."""
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = z * _m.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    # the bounds are exactly 0 and 1 at k = 0 and k = n; rounding must not move them
    low = 0.0 if k == 0 else max(0.0, centre - half)
    high = 1.0 if k == n else min(1.0, centre + half)
    return {'rate': p, 'low': low, 'high': high}


def quantile(xs: Sequence[float], q: float) -> Optional[float]:
    """Return the type-7 quantile of the sorted values ``xs`` (None when empty)."""
    n = len(xs)
    if n == 0:
        return None
    h = (n - 1) * q
    lo = int(h)
    if lo >= n - 1:
        return xs[-1]
    return xs[lo] + (h - lo) * (xs[lo + 1] - xs[lo])


def describe(values: Sequence[Optional[float]]) -> Dict[str, object]:
    """Return N, median, quartiles, IQR, min and max of the defined values."""
    xs = sorted(v for v in values if v is not None)
    n = len(xs)
    if n == 0:
        return {'n': 0, 'median': None, 'q1': None, 'q3': None, 'iqr': None,
                'min': None, 'max': None}
    q1, med, q3 = quantile(xs, 0.25), quantile(xs, 0.5), quantile(xs, 0.75)
    return {'n': n, 'median': med, 'q1': q1, 'q3': q3, 'iqr': q3 - q1,
            'min': xs[0], 'max': xs[-1]}


def _median(xs: List[float]) -> float:
    xs = sorted(xs)
    return quantile(xs, 0.5)


def ranks(values: Sequence[float]) -> List[float]:
    """Return 1-based midranks of ``values`` (ties share their mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j + 2) / 2
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def erfc(x: float) -> float:
    """
    Return the complementary error function (fractional error < 1.2e-7).

    Numerical Recipes' Chebyshev fit (``erfcc``), computed with fdlibm's ``exp``
    so CPython and Pyodide agree bit for bit. Used only for the normal
    approximation's tail probability, whose own error is far larger.
    """
    z = abs(x)
    t = 1.0 / (1.0 + 0.5 * z)
    r = t * _exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (
        0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (
            1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))))
    return r if x >= 0 else 2.0 - r


def _exact_signed_rank_p(doubled: List[int], w2: int) -> float:
    """Two-sided exact p for the doubled positive-rank sum ``w2``."""
    total = sum(doubled)
    counts = [0] * (total + 1)
    counts[0] = 1
    top = 0
    for r in doubled:
        for s in range(top, -1, -1):
            if counts[s]:
                counts[s + r] += counts[s]
        top += r
    n_ways = 1 << len(doubled)
    lower = sum(counts[:w2 + 1])
    upper = sum(counts[w2:])
    tail = min(lower, upper)
    return min(1.0, 2 * tail / n_ways)


def wilcoxon(a: Sequence[Optional[float]], b: Sequence[Optional[float]]) -> Dict[str, object]:
    """
    Wilcoxon signed-rank test of paired ``a`` and ``b`` (difference ``a - b``).

    Pairs where either value is undefined (None) are excluded and counted.
    Returns the counts, the statistics, the p-value and its method, the effect
    sizes, and ``reason`` when no p-value can honestly be given.
    """
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    excluded = len(a) - len(pairs)
    d = [x - y for x, y in pairs]
    nz = [v for v in d if v != 0]
    out = {'test': 'wilcoxon_signed_rank', 'n_pairs': len(d), 'n_excluded': excluded,
           'n_zero': len(d) - len(nz), 'n_nonzero': len(nz),
           'median_diff': _median(d) if d else None,
           'w_plus': None, 'w_minus': None, 'p': None, 'method': None,
           'rank_biserial': None, 'hodges_lehmann': None, 'hl_method': None,
           'reason': None}
    if d:
        if len(d) <= HL_MAX:
            walsh = [(d[i] + d[j]) / 2 for i in range(len(d)) for j in range(i, len(d))]
            out['hodges_lehmann'], out['hl_method'] = _median(walsh), 'walsh_averages'
        else:
            out['hodges_lehmann'], out['hl_method'] = out['median_diff'], 'median_difference'
    if not nz:
        out['reason'] = ('no pairs' if not d else
                         'all paired differences are 0: no difference, test undefined')
        return out
    r = ranks([abs(v) for v in nz])
    w_plus = sum(rk for rk, v in zip(r, nz) if v > 0)
    w_minus = sum(rk for rk, v in zip(r, nz) if v < 0)
    out['w_plus'], out['w_minus'] = w_plus, w_minus
    out['rank_biserial'] = (w_plus - w_minus) / (w_plus + w_minus)
    n = len(nz)
    if n < MIN_PAIRS:
        out['reason'] = f'too few non-zero pairs for a test ({n} < {MIN_PAIRS})'
        return out
    if n <= EXACT_MAX:
        doubled = [int(round(2 * rk)) for rk in r]
        out['p'] = _exact_signed_rank_p(doubled, int(round(2 * w_plus)))
        out['method'] = 'exact'
    else:
        mean = n * (n + 1) / 4
        ties = {}
        for rk in r:
            ties[rk] = ties.get(rk, 0) + 1
        var = n * (n + 1) * (2 * n + 1) / 24 - sum(t * t * t - t for t in ties.values()) / 48
        if var <= 0:
            out['reason'] = 'zero variance of the signed-rank sum'
            return out
        diff = w_plus - mean
        cc = 0.5 if diff > 0 else (-0.5 if diff < 0 else 0.0)
        z = (diff - cc) / _m.sqrt(var)
        out['p'] = min(1.0, erfc(abs(z) / _m.sqrt(2.0)))
        out['method'] = 'normal_approximation'
        out['z'] = z
    return out


def mcnemar(a: Sequence[Optional[bool]], b: Sequence[Optional[bool]]) -> Dict[str, object]:
    """
    Exact McNemar test of paired successes ``a`` and ``b``.

    ``b10``: A succeeded where B failed; ``b01``: the reverse. The p-value is
    two-sided binomial on the discordant pairs; the effect size is the risk
    difference (rate A - rate B over the pairs).
    """
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    b10 = sum(1 for x, y in pairs if x and not y)
    b01 = sum(1 for x, y in pairs if y and not x)
    out = {'test': 'mcnemar_exact', 'n_pairs': n, 'n_excluded': len(a) - n,
           'a_only': b10, 'b_only': b01,
           'risk_difference': (b10 - b01) / n if n else None,
           'p': None, 'reason': None}
    m = b10 + b01
    if n == 0:
        out['reason'] = 'no pairs'
    elif m == 0:
        out['reason'] = 'no discordant pairs: identical outcomes, test undefined'
    else:
        k = min(b10, b01)
        tail = sum(_comb(m, i) for i in range(k + 1))
        out['p'] = min(1.0, 2 * tail / (1 << m))
    return out


def _comb(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    c = 1
    for i in range(k):
        c = c * (n - i) // (i + 1)
    return c


def holm(ps: Sequence[Optional[float]]) -> List[Optional[float]]:
    """Return Holm-adjusted p-values (None stays None and is not counted)."""
    idx = [i for i, p in enumerate(ps) if p is not None]
    m = len(idx)
    order = sorted(idx, key=lambda i: (ps[i], i))
    out: List[Optional[float]] = [None] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * ps[i])
        running = max(running, adj)
        out[i] = running
    return out


def verdict(p: Optional[float], alpha: float = ALPHA) -> str:
    """Return the plain words for a (possibly adjusted) p-value."""
    if p is None:
        return 'no test'
    return 'significant difference' if p < alpha else 'no significant difference'
