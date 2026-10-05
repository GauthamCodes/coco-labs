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

"""Pose-graph SLAM: SE(2), the optimiser on known graphs, ICP, loops."""

import math
import random

from coco_lab import kalman, map_teaching, mapeval, mapping, mapworld
from coco_lab import posegraph as pg
from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

poses = st.tuples(st.floats(-20, 20), st.floats(-20, 20),
                  st.floats(-math.pi, math.pi))


def _close(a, b, tol=1e-9):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol and \
        abs(math.remainder(a[2] - b[2], 2 * math.pi)) < tol


@given(poses, poses)
@settings(max_examples=1000, deadline=None)
def test_se2_identities(a, b):
    assert _close(pg.compose(a, pg.inverse(a)), (0.0, 0.0, 0.0), 1e-8)
    assert _close(pg.compose(a, pg.between(a, b)), b, 1e-8)
    assert _close(pg.edge_error(a, b, pg.between(a, b)), (0, 0, 0), 1e-8)


@given(poses, poses, poses)
@settings(max_examples=300, deadline=None)
def test_the_jacobians_are_the_errors_derivatives(xi, xj, z):
    A, B = pg._jacobians(xi, xj, z)
    h = 1e-6
    for which, J in ((0, A), (1, B)):
        for c in range(3):
            def e(d):
                p = [list(xi), list(xj)]
                p[which][c] += d
                return pg.edge_error(tuple(p[0]), tuple(p[1]), z)
            ep, em = e(h), e(-h)
            for r in range(3):
                d = ep[r] - em[r]
                if r == 2:
                    d = math.remainder(d, 2 * math.pi)
                assert J[r][c] == pytest.approx(d / (2 * h), abs=2e-5)


def _info(sxy=0.1, syaw=0.05):
    return pg._diag(sxy, syaw)


def _square_graph(noise, seed):
    """Four nodes round a 4 m square, odometry edges and one loop edge."""
    truth = [(0.0, 0.0, 0.0), (4.0, 0.0, math.pi / 2),
             (4.0, 4.0, math.pi), (0.0, 4.0, -math.pi / 2)]
    rnd = random.Random(seed)
    edges = []
    for i, j in ((0, 1), (1, 2), (2, 3), (3, 0)):
        z = pg.between(truth[i], truth[j])
        z = (z[0] + rnd.gauss(0, noise), z[1] + rnd.gauss(0, noise),
             z[2] + rnd.gauss(0, noise / 4))
        edges.append(pg.Edge(i, j, z, _info(), 'loop' if j == 0 else 'odom'))
    return truth, edges


def test_a_consistent_graph_is_solved_exactly_from_a_bad_start():
    truth, edges = _square_graph(0.0, 0)
    start = [truth[0]] + [(x + 0.7, y - 0.5, th + 0.3)
                          for x, y, th in truth[1:]]
    out, hist = pg.optimise(start, edges, iterations=20)
    for a, b in zip(out, truth):
        assert _close(a, b, 1e-6)
    assert hist[-1] < 1e-10


def test_chi2_never_rises_on_noisy_squares():
    for seed in range(30):
        truth, edges = _square_graph(0.2, seed)
        init = [truth[0]]
        for e in edges[:3]:
            init.append(pg.compose(init[-1], e.z))
        _, hist = pg.optimise(init, edges, iterations=15)
        for a, b in zip(hist, hist[1:]):
            assert b <= a * (1 + 1e-9) + 1e-12


def test_the_linear_case_is_the_least_squares_solution():
    """
    Gauss-Newton on a linear graph is weighted least squares.

    Every yaw measurement 0 and nailed down (sigma 1e-5 rad): the headings
    stay 0, the errors are linear in the positions, and Gauss-Newton must
    land on the dense weighted least-squares answer. (With free headings
    the position residuals pull the yaws, and the problem is not linear.)
    """
    rnd = random.Random(3)
    n = 6
    edges = []
    for i in range(n - 1):
        edges.append(pg.Edge(i, i + 1, (1.0 + rnd.gauss(0, 0.1),
                                        rnd.gauss(0, 0.1), 0.0),
                             _info(0.1 + 0.05 * i, 1e-5), 'odom'))
    edges.append(pg.Edge(0, n - 1, (5.0 + rnd.gauss(0, 0.1),
                                    rnd.gauss(0, 0.1), 0.0),
                         _info(0.05, 1e-5), 'loop'))
    init = [(float(i), 0.0, 0.0) for i in range(n)]
    out, _ = pg.optimise(init, edges, iterations=3)
    # dense LS for x (and y) of nodes 1..n-1 with node 0 fixed at 0
    for axis in (0, 1):
        m = n - 1
        Hm = [[0.0] * m for _ in range(m)]
        b = [0.0] * m
        for e in edges:
            w = e.info[axis][axis]
            i, j = e.i - 1, e.j - 1
            z = e.z[axis]
            # residual (x_j - x_i - z)
            for (a, sa) in ((i, -1.0), (j, 1.0)):
                if a < 0:
                    continue
                b[a] += sa * w * z
                for (c, sc) in ((i, -1.0), (j, 1.0)):
                    if c >= 0:
                        Hm[a][c] += sa * sc * w
        sol = kalman.matvec(kalman.inverse(Hm), b)
        for k in range(m):
            assert out[k + 1][axis] == pytest.approx(sol[k], abs=1e-6)


def test_pcg_solves_a_chain_with_loops_like_a_dense_solve():
    rnd = random.Random(11)
    n = 25
    truth = [(0.0, 0.0, 0.0)]
    for _ in range(n - 1):
        truth.append(pg.compose(truth[-1], (0.5, 0.0, rnd.uniform(-0.6,
                                                                  0.6))))
    edges = [pg.Edge(i, i + 1, pg.between(truth[i], truth[i + 1]),
                     _info(), 'odom') for i in range(n - 1)]
    for i, j in ((0, 12), (3, 20), (7, 24)):
        edges.append(pg.Edge(i, j, pg.between(truth[i], truth[j]), _info(),
                             'loop'))
    noisy = [truth[0]] + [(x + rnd.gauss(0, 0.2), y + rnd.gauss(0, 0.2),
                           th + rnd.gauss(0, 0.05))
                          for x, y, th in truth[1:]]
    Hd, Hoff, b = pg.linear_system(noisy, edges)
    x, it = pg.pcg(Hd, Hoff, [-v for v in b], n, tol=1e-12)
    # dense
    N = 3 * n
    H = [[0.0] * N for _ in range(N)]
    for i in range(n):
        for a in range(3):
            for c in range(3):
                H[3 * i + a][3 * i + c] = Hd[i][a][c]
    for (i, j), B in Hoff.items():
        for a in range(3):
            for c in range(3):
                H[3 * i + a][3 * j + c] = B[a][c]
                H[3 * j + c][3 * i + a] = B[a][c]
    dense = kalman.matvec(kalman.inverse(H), [-v for v in b])
    for u, v in zip(x, dense):
        assert u == pytest.approx(v, abs=1e-6)
    # the chain preconditioner leaves only the 3 loops' low-rank part
    assert it <= 6 * 3 + 2


def _corner_scan(n=40):
    pts = [(1.0 + 0.05 * i, -1.0) for i in range(n)]
    pts += [(1.0, -1.0 + 0.05 * i) for i in range(1, n)]
    return pts


def _move(pts, T):
    return [pg.compose(T, (x, y, 0.0))[:2] for x, y in pts]


def test_icp_recovers_a_known_motion_on_a_corner():
    ref = _corner_scan()
    T = (0.12, -0.08, 0.06)
    cur = _move(ref, pg.inverse(T))
    r = pg.icp(ref, cur, (0.0, 0.0, 0.0), max_dist=0.5)
    assert r.converged
    assert _close(r.pose, T, 2e-3)
    assert r.rmse < 1e-3  # it stops at 0.1 mm steps


def test_a_corridor_constrains_nothing_along_its_axis():
    """Two parallel walls: the Hessian is blind along them; the prior holds."""
    ref = [(0.1 * i, 1.0) for i in range(-40, 41)] + \
        [(0.1 * i, -1.0) for i in range(-40, 41)]
    cur = _move(ref, pg.inverse((0.3, 0.0, 0.0)))
    r = pg.icp(ref, cur, (0.0, 0.0, 0.0), max_dist=0.5,
               prior=_info(), sigma=0.05)
    assert r.min_eig_per_point() < 1e-6
    # along the axis the MAP answer stays at the guess (0), not at 0.3
    assert abs(r.pose[0]) < 1e-6
    assert abs(r.pose[1]) < 1e-6 and abs(r.pose[2]) < 1e-6


def _scene(sid):
    m, sc = map_teaching.scene_scenario(sid)  # the scene as the lab shows it
    return m, mapworld.from_sketch(m, sc)


#: the loop room's worlds 0..19: what the lab's 20-world count rests on
LOOP_SEEDS = range(20)


@pytest.fixture(scope='module')
def loop_worlds():
    """Pose graph with and without loop closure on 20 loop-room worlds."""
    out = []
    specs = {i: p for i, _, p in map_teaching.run_specs()}
    for seed in LOOP_SEEDS:
        m, sc = map_teaching.scene_scenario('map_loop')
        sc.seed = seed
        w = mapworld.from_sketch(m, sc)
        inp, tp = w.inputs(), w.true_poses()
        on = mapping.run('pose_graph', inp, m, specs['pose_graph'])
        off = mapping.run('pose_graph', inp, m, specs['pose_graph_noloop'])
        out.append((seed, tp, on, off))
    return out


@pytest.fixture(scope='module')
def loop_runs(loop_worlds):
    """One world where a loop was closed (the first such seed)."""
    for _, tp, on, off in loop_worlds:
        if len(on.arrays['loops.k'][1]):
            return tp, on, off
    raise AssertionError('no loop-room world closed a loop')


def test_loop_closure_usually_closes_the_loop_room(loop_worlds):
    """
    The lab's claim, over 20 worlds (Sketch), as the page states it.

    Loop closure was found in at least 15 of 20 worlds, and in every world
    where it was found it lowered the final trajectory error. Exact counts:
    docs/data/lab3/sketch_counts.json.
    """
    closed = [(tp, on, off) for _, tp, on, off in loop_worlds
              if len(on.arrays['loops.k'][1])]
    assert len(closed) >= 15
    for tp, on, off in closed:
        assert mapeval.ate(on.final_trajectory(), tp, False)['rmse'] < \
            mapeval.ate(off.final_trajectory(), tp, False)['rmse']
    for _, _, _, off in loop_worlds:
        assert len(off.arrays['loops.k'][1]) == 0


def test_every_optimisation_lowers_chi2(loop_runs):
    _, on, _ = loop_runs
    for a, b in zip(on.arrays['opt.chi2_before'][1],
                    on.arrays['opt.chi2_after'][1]):
        assert b <= a


def test_the_final_trajectory_is_the_optimised_graph(loop_runs):
    _, on, off = loop_runs
    assert on.final_trajectory() != on.estimates()
    assert off.final_trajectory() == off.estimates()


def test_edges_are_a_chain_plus_loops(loop_runs):
    _, on, _ = loop_runs
    ei, ej = on.arrays['edges.i'][1], on.arrays['edges.j'][1]
    kinds = on.arrays['edges.kind'][1]
    n = len(on)
    chain = [(i, j) for i, j, k in zip(ei, ej, kinds)
             if k != pg.EDGE_KINDS.index('loop')]
    assert chain == [(k - 1, k) for k in range(1, n)]
    loops = [(i, j) for i, j, k in zip(ei, ej, kinds)
             if k == pg.EDGE_KINDS.index('loop')]
    assert loops == list(zip(on.arrays['loops.j'][1],
                             on.arrays['loops.k'][1]))
