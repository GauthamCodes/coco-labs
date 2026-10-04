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
The Kalman steps agree with closed-form results on linear Gaussian problems.

The EKF localiser runs :func:`coco_lab.kalman.predict` and
:func:`coco_lab.kalman.update`. On a linear model those ARE the Kalman
filter, whose answer is known in closed form:

- a static state observed linearly: the batch information-form posterior
  (:func:`kalman.batch_posterior`), one solve, no recursion;
- a scalar random walk: the Riccati recursion's fixed point
  ``P = (-q + sqrt(q^2 + 4 q r)) / 2``;
- a 1D constant-velocity problem solved twice, once as a dynamic filter
  and once as a static batch over the initial state.

Plus the EKF localiser's motion Jacobians against finite differences.
"""

import math
import random

from coco_lab import kalman
from coco_lab.localise import _motion_jacobians
from coco_lab.sketch import apply_delta
from hypothesis import given, settings, strategies as st


def _close(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _spd(rng, n, scale=1.0):
    A = [[rng.gauss(0, 1) for _ in range(n)] for _ in range(n)]
    S = kalman.matmul(A, kalman.transpose(A))
    for i in range(n):
        S[i][i] += scale
    return S


@settings(max_examples=300, derandomize=True, database=None,
          deadline=None)
@given(st.integers(0, 2 ** 32 - 1), st.integers(1, 4), st.integers(1, 12))
def test_sequential_updates_equal_the_batch_posterior(seed, n, k):
    """A KF over k linear observations reaches the one-solve posterior."""
    rng = random.Random(seed)
    mu0 = [rng.gauss(0, 3) for _ in range(n)]
    P0 = _spd(rng, n, 1.0)
    obs = []
    for _ in range(k):
        m = rng.randint(1, 3)
        H = [[rng.gauss(0, 1) for _ in range(n)] for _ in range(m)]
        R = _spd(rng, m, 0.5)
        z = [rng.gauss(0, 5) for _ in range(m)]
        obs.append((H, z, R))
    mu, P = list(mu0), P0
    for H, z, R in obs:
        mu, P, _, _ = kalman.update(mu, P, z, kalman.matvec(H, mu), H, R)
    mu_b, P_b = kalman.batch_posterior(mu0, P0, obs)
    for i in range(n):
        assert _close(mu[i], mu_b[i], 1e-7)
        for j in range(n):
            assert _close(P[i][j], P_b[i][j], 1e-7)


def test_observation_order_does_not_matter():
    rng = random.Random(7)
    mu0, P0 = [0.0, 0.0], _spd(rng, 2)
    obs = [([[1.0, 0.5]], [rng.gauss(0, 1)], [[0.3]]) for _ in range(6)]
    a, Pa = [mu0, P0][0], P0
    for H, z, R in obs:
        a, Pa, _, _ = kalman.update(a, Pa, z, kalman.matvec(H, a), H, R)
    b, Pb = mu0, P0
    for H, z, R in reversed(obs):
        b, Pb, _, _ = kalman.update(b, Pb, z, kalman.matvec(H, b), H, R)
    assert all(_close(x, y, 1e-9) for x, y in zip(a, b))


@settings(max_examples=200, derandomize=True, database=None,
          deadline=None)
@given(st.floats(1e-3, 10.0), st.floats(0.01, 100.0))
def test_random_walk_variance_reaches_the_riccati_fixed_point(r, ratio):
    # q / r in [0.01, 100] keeps the steady gain >= ~0.1, so 400 steps
    # reach the fixed point to rounding (at q / r = 1e-4 the gain is 0.01
    # and 400 steps are not enough -- a property of the recursion, found
    # by hypothesis, not of the filter)
    q = r * ratio
    P = [[100.0]]
    mu = [0.0]
    for _ in range(400):
        mu, P = kalman.predict(mu, P, lambda m: list(m), [[1.0]], [[q]])
        mu, P, _, _ = kalman.update(mu, P, [0.0], mu, [[1.0]], [[r]])
    want = kalman.random_walk_steady_variance(q, r)
    assert _close(P[0][0], want, 1e-9)


def test_the_fixed_point_formula_is_the_fixed_point():
    for q, r in ((1.0, 1.0), (0.01, 4.0), (3.0, 0.2)):
        p = kalman.random_walk_steady_variance(q, r)
        assert _close(p, (p + q) * r / (p + q + r), 1e-12)


def test_a_noiseless_dynamic_filter_equals_the_batch_over_its_start():
    """
    Constant velocity with no process noise is a static problem in x0.

    ``x_k = F^k x0``, so observing ``H x_k`` is observing ``H F^k x0``.
    The filter's final state must be ``F^K`` times the batch posterior
    mean of ``x0``, and its covariance ``F^K P F^K^T``.
    """
    rng = random.Random(3)
    dt = 0.5
    F = [[1.0, dt], [0.0, 1.0]]
    H = [[1.0, 0.0]]
    R = [[0.25]]
    mu0 = [0.0, 1.0]
    P0 = [[4.0, 0.0], [0.0, 1.0]]
    Q = [[0.0, 0.0], [0.0, 0.0]]
    zs = [[rng.gauss(0.7 * k * dt, 0.5)] for k in range(1, 11)]
    mu, P = list(mu0), P0
    Fk = kalman.eye(2)
    obs = []
    for z in zs:
        mu, P = kalman.predict(mu, P, lambda m: kalman.matvec(F, m), F, Q)
        Fk = kalman.matmul(F, Fk)
        mu, P, _, _ = kalman.update(mu, P, z, kalman.matvec(H, mu), H, R)
        obs.append((kalman.matmul(H, Fk), z, R))
    x0, Px0 = kalman.batch_posterior(mu0, P0, obs)
    want_mu = kalman.matvec(Fk, x0)
    want_P = kalman.matmul(kalman.matmul(Fk, Px0), kalman.transpose(Fk))
    assert all(_close(a, b, 1e-8) for a, b in zip(mu, want_mu))
    assert all(_close(P[i][j], want_P[i][j], 1e-8)
               for i in range(2) for j in range(2))


def test_inverse_round_trip_and_singular_refusal():
    rng = random.Random(1)
    A = _spd(rng, 4)
    I4 = kalman.matmul(A, kalman.inverse(A))
    assert all(_close(I4[i][j], 1.0 if i == j else 0.0, 1e-9)
               for i in range(4) for j in range(4))
    try:
        kalman.inverse([[1.0, 2.0], [2.0, 4.0]])
    except ValueError:
        pass
    else:
        raise AssertionError('a singular matrix was inverted')


@settings(max_examples=200, derandomize=True, database=None,
          deadline=None)
@given(st.floats(-3, 3), st.floats(-3, 3), st.floats(-3.1, 3.1),
       st.floats(-1.5, 1.5), st.floats(0.0, 1.0), st.floats(-1.5, 1.5))
def test_motion_jacobian_matches_finite_differences(x, y, th, r1, t, r2):
    G, _ = _motion_jacobians([x, y, th], r1, t, r2, (0.1, 0.1, 0.1, 0.1))
    eps = 1e-6
    base = [x, y, th]
    for j in range(3):
        p = list(base)
        m = list(base)
        p[j] += eps
        m[j] -= eps
        fp = apply_delta(tuple(p), r1, t, r2)
        fm = apply_delta(tuple(m), r1, t, r2)
        for i in range(3):
            d = fp[i] - fm[i]
            if i == 2:
                d = math.atan2(math.sin(d), math.cos(d))
            assert abs(d / (2 * eps) - G[i][j]) < 1e-5
