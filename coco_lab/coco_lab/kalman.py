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
The (extended) Kalman filter's two steps, on plain lists, standard library only.

Matrices are lists of rows. The functions are small and literal on purpose:
they are what the EKF localiser (:mod:`coco_lab.localise`) runs, and what
``test_kalman.py`` checks against closed-form results -- a linear Gaussian
problem whose exact posterior is known, where the EKF must agree with it
to rounding.

- :func:`predict` -- ``mu' = f(mu)``, ``P' = F P F^T + Q``
- :func:`update` -- the Joseph-form measurement update for a vector
  measurement, with the innovation and its covariance returned so callers
  can gate on the normalised innovation squared.

For a linear model (``f(x) = F x``, ``h(x) = H x``) these ARE the Kalman
filter; :func:`batch_posterior` computes the same posterior in one solve
(information form) so the two can be compared.
"""

from typing import Callable, List, Sequence, Tuple

Matrix = List[List[float]]
Vector = List[float]


def zeros(n: int, m: int) -> Matrix:
    """Return an ``n x m`` zero matrix."""
    return [[0.0] * m for _ in range(n)]


def eye(n: int) -> Matrix:
    """Return the ``n x n`` identity."""
    out = zeros(n, n)
    for i in range(n):
        out[i][i] = 1.0
    return out


def transpose(a: Matrix) -> Matrix:
    """Return ``a^T``."""
    return [list(r) for r in zip(*a)]


def matmul(a: Matrix, b: Matrix) -> Matrix:
    """Return ``a b``."""
    bt = transpose(b)
    return [[sum(x * y for x, y in zip(row, col)) for col in bt] for row in a]


def matvec(a: Matrix, v: Sequence[float]) -> Vector:
    """Return ``a v``."""
    return [sum(x * y for x, y in zip(row, v)) for row in a]


def add(a: Matrix, b: Matrix) -> Matrix:
    """Return ``a + b``."""
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def sub(a: Matrix, b: Matrix) -> Matrix:
    """Return ``a - b``."""
    return [[x - y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def symmetrise(a: Matrix) -> Matrix:
    """Return ``(a + a^T) / 2``: removes rounding asymmetry."""
    n = len(a)
    return [[0.5 * (a[i][j] + a[j][i]) for j in range(n)] for i in range(n)]


def inverse(a: Matrix) -> Matrix:
    """
    Return ``a^-1`` by Gauss-Jordan elimination with partial pivoting.

    Raises ``ValueError`` for a singular (or numerically singular) matrix.
    """
    n = len(a)
    m = [list(row) + [1.0 if i == j else 0.0 for j in range(n)]
         for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-300:
            raise ValueError('singular matrix')
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0.0:
                f = m[r][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [row[n:] for row in m]


def predict(mu: Sequence[float], P: Matrix,
            f: Callable[[Sequence[float]], Vector], F: Matrix,
            Q: Matrix) -> Tuple[Vector, Matrix]:
    """Return ``(f(mu), F P F^T + Q)``."""
    mu2 = list(f(mu))
    P2 = add(matmul(matmul(F, P), transpose(F)), Q)
    return mu2, symmetrise(P2)


def update(mu: Sequence[float], P: Matrix, z: Sequence[float],
           zhat: Sequence[float], H: Matrix, R: Matrix,
           residual: Callable[[float, float], float] = None
           ) -> Tuple[Vector, Matrix, Vector, Matrix]:
    """
    Return ``(mu', P', nu, S)`` after measuring ``z`` with prediction ``zhat``.

    ``nu = z - zhat`` (or ``residual(z_i, zhat_i)`` per component, for an
    angle), ``S = H P H^T + R``, ``K = P H^T S^-1``, ``mu' = mu + K nu`` and
    the Joseph form ``P' = (I - K H) P (I - K H)^T + K R K^T``, which stays
    symmetric positive semi-definite under rounding where ``(I - K H) P``
    need not.
    """
    if residual is None:
        nu = [a - b for a, b in zip(z, zhat)]
    else:
        nu = [residual(a, b) for a, b in zip(z, zhat)]
    Ht = transpose(H)
    S = add(matmul(matmul(H, P), Ht), R)
    K = matmul(matmul(P, Ht), inverse(S))
    mu2 = [m + d for m, d in zip(mu, matvec(K, nu))]
    IKH = sub(eye(len(mu)), matmul(K, H))
    P2 = add(matmul(matmul(IKH, P), transpose(IKH)),
             matmul(matmul(K, R), transpose(K)))
    return mu2, symmetrise(P2), nu, S


def batch_posterior(mu0: Sequence[float], P0: Matrix,
                    observations: Sequence[Tuple[Matrix, Sequence[float],
                                                 Matrix]]
                    ) -> Tuple[Vector, Matrix]:
    """
    Return the exact Gaussian posterior of a static linear problem.

    Prior ``N(mu0, P0)``, observations ``z_k = H_k x + v_k``,
    ``v_k ~ N(0, R_k)``, independent. In information form:
    ``P^-1 = P0^-1 + sum H_k^T R_k^-1 H_k`` and
    ``P^-1 mu = P0^-1 mu0 + sum H_k^T R_k^-1 z_k`` -- one solve, no
    recursion. A Kalman filter run over the same observations, in any
    order, must reach this.
    """
    info = inverse(P0)
    vec = matvec(info, mu0)
    for H, z, R in observations:
        Ht = transpose(H)
        Ri = inverse(R)
        info = add(info, matmul(matmul(Ht, Ri), H))
        add_v = matvec(matmul(Ht, Ri), z)
        vec = [a + b for a, b in zip(vec, add_v)]
    P = inverse(info)
    return matvec(P, vec), symmetrise(P)


def random_walk_steady_variance(q: float, r: float) -> float:
    """
    Return the steady-state posterior variance of a scalar random walk.

    ``x_k = x_{k-1} + w``, ``w ~ N(0, q)``; ``z_k = x_k + v``,
    ``v ~ N(0, r)``. The Riccati recursion's fixed point solves
    ``P = (P + q) r / (P + q + r)``, i.e. ``P^2 + q P - q r = 0``:
    ``P = (-q + sqrt(q^2 + 4 q r)) / 2``.
    """
    return (-q + (q * q + 4.0 * q * r) ** 0.5) / 2.0
