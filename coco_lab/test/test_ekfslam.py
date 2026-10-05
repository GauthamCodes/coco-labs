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

"""EKF-SLAM: prediction, update and the closed-form linear case."""

import math
import random

from coco_lab import kalman, landmarks, loc_teaching, mapping, mapworld, slam
from coco_lab.ekfslam import EKFSlam, EKFSlamParams
from coco_lab.localise import _motion_jacobians
from coco_lab.sketch import LidarSpec, Noise, Scenario, SketchMap
import pytest


def _filter_with_two_landmarks(model='range_bearing'):
    f = EKFSlam((1.0, 2.0, 0.3), EKFSlamParams(model=model))
    f.add_landmark(7, (2.0, 0.4) if model == 'range_bearing' else (1.5, 1.0))
    f.add_landmark(9, (3.0, -0.6) if model == 'range_bearing'
                   else (2.5, -1.5))
    return f


def test_prediction_moves_the_pose_and_leaves_the_landmarks_alone():
    f = _filter_with_two_landmarks()
    mu0, P0 = list(f.mu), [row[:] for row in f.P]
    f.predict(0.2, 0.5, -0.1)
    assert f.mu[3:] == mu0[3:]
    for i in range(3, f.n):
        for j in range(3, f.n):
            assert f.P[i][j] == P0[i][j]
    G, Q = _motion_jacobians(mu0[:3], 0.2, 0.5, -0.1, f.p.alphas)
    for j in range(3, f.n):
        for i in range(3):
            want = sum(G[i][k] * P0[k][j] for k in range(3))
            assert f.P[i][j] == pytest.approx(want, abs=1e-15)
            assert f.P[j][i] == f.P[i][j]
    GPG = kalman.add(kalman.matmul(kalman.matmul(
        G, [r[:3] for r in P0[:3]]), kalman.transpose(G)), Q)
    for i in range(3):
        for j in range(3):
            assert f.P[i][j] == pytest.approx(GPG[i][j], abs=1e-15)


def test_a_new_landmark_inherits_the_robots_uncertainty():
    f = EKFSlam((0.0, 0.0, 0.0), EKFSlamParams(start_sigma_xy=0.5))
    f.add_landmark(1, (2.0, 0.0))
    j = f.slot[1]
    assert f.mu[j:j + 2] == pytest.approx([2.0, 0.0])
    # it is at least as uncertain as the robot, and correlated with it
    assert f.P[j][j] >= f.P[0][0]
    assert f.P[0][j] == pytest.approx(f.P[0][0])


def test_the_update_equals_the_generic_kalman_update():
    """EKF-SLAM's sparse update is kalman.update with the full Jacobian."""
    for model in ('range_bearing', 'relative_xy'):
        f = _filter_with_two_landmarks(model)
        f.predict(0.1, 0.4, 0.05)
        mu, P = list(f.mu), [row[:] for row in f.P]
        j = f.slot[9]
        zhat, Hr, Hl = f._h(j)
        H = [[0.0] * f.n for _ in range(2)]
        for a in range(2):
            H[a][0:3] = Hr[a]
            H[a][j:j + 2] = Hl[a]
        z = (zhat[0] + 0.03, zhat[1] - 0.02)
        res = (lambda a, b: math.remainder(a - b, 2 * math.pi)) \
            if model == 'range_bearing' else None
        mu2, P2, _, _ = kalman.update(mu, P, z, zhat, H,
                                      [list(r) for r in f.R], res)
        f.update(9, z)
        for a, b in zip(f.mu, mu2):
            assert math.remainder(a - b, 2 * math.pi) == pytest.approx(
                0.0, abs=1e-12)
        for i in range(f.n):
            for k in range(f.n):
                assert f.P[i][k] == pytest.approx(P2[i][k], abs=1e-12)


def test_the_linear_case_equals_the_exact_gaussian_posterior():
    """
    EKF-SLAM in the linear case equals the exact Gaussian posterior.

    Heading known exactly, odometry exact, the relative-xy sensor: every
    model is linear, so EKF-SLAM must reach kalman.batch_posterior's exact
    answer for the static unknowns (start x, y and the landmarks).
    """
    rnd = random.Random(5)
    marks = {1: (3.0, 1.0), 2: (5.0, -1.5), 3: (8.0, 0.5)}
    sigma = 0.1
    p = EKFSlamParams(alphas=(0.0, 0.0, 0.0, 0.0), sigma_range=sigma,
                      model='relative_xy', start_sigma_xy=0.3,
                      start_sigma_yaw=0.0)
    f = EKFSlam((0.0, 0.0, 0.0), p)
    x = 0.0  # odometry is exact; heading stays 0
    obs_list = []
    order = []
    for step in range(12):
        if step:
            f.predict(0.0, 0.5, 0.0)
            x += 0.5
        for lid, (lx, ly) in marks.items():
            if abs(lx - x) > 4.0:
                continue
            z = (lx - x + rnd.gauss(0, sigma), ly + rnd.gauss(0, sigma))
            f.update(lid, z)
            obs_list.append((lid, x, z))
            if lid not in order:
                order.append(lid)
    # the static problem: unknowns (x0, y0, l_a, l_b, l_c) in the filter's
    # landmark order; z = l - (p0 + (x, 0)); a flat prior on landmarks
    n = 2 + 2 * len(order)
    P0 = [[0.0] * n for _ in range(n)]
    P0[0][0] = P0[1][1] = 0.3 ** 2
    for i in range(2, n):
        P0[i][i] = 1e12
    obs = []
    for lid, xk, z in obs_list:
        j = 2 + 2 * order.index(lid)
        H = [[0.0] * n for _ in range(2)]
        H[0][0], H[1][1] = -1.0, -1.0
        H[0][j], H[1][j + 1] = 1.0, 1.0
        R = [[sigma ** 2, 0.0], [0.0, sigma ** 2]]
        obs.append((H, [z[0] + xk, z[1]], R))
    mu, P = kalman.batch_posterior([0.0] * n, P0, obs)
    # the filter's pose is p0 + (x, 0); its landmarks are the unknowns
    assert f.mu[0] - x == pytest.approx(mu[0], abs=1e-5)
    assert f.mu[1] == pytest.approx(mu[1], abs=1e-5)
    for k, lid in enumerate(order):
        j = f.slot[lid]
        assert f.mu[j] == pytest.approx(mu[2 + 2 * k], abs=1e-5)
        assert f.mu[j + 1] == pytest.approx(mu[3 + 2 * k], abs=1e-5)
        assert f.P[j][j] == pytest.approx(P[2 + 2 * k][2 + 2 * k], rel=1e-4)


def _world(seed=13, scale=3.0, route=None):
    m = loc_teaching.landmarks_map()
    lm = list(loc_teaching.LANDMARKS_ROUTE)
    sc = Scenario(start=(1.5, 1.5, 0.0), route=route or lm, seed=seed,
                  noise=Noise(odom_alphas=(0.02 * scale,) * 4,
                              range_sigma=0.02))
    return m, mapworld.from_sketch(m, sc)


def test_ekf_slam_beats_odometry_on_the_landmarks_room():
    m, w = _world()
    inp, tp = w.inputs(), w.true_poses()
    from coco_lab import mapeval
    ekf = mapping.run('ekf_slam', inp, m, EKFSlamParams(
        alphas=(0.06,) * 4))
    odo = mapping.run('odometry', inp, m)
    e1 = mapeval.ate(ekf.estimates(), tp, align=False)['rmse']
    e2 = mapeval.ate(odo.estimates(), tp, align=False)['rmse']
    assert e1 < 0.5 * e2


def test_landmark_uncertainty_never_grows():
    """A landmark's marginal variance only shrinks: it never moves."""
    m, w = _world()
    tr = mapping.run('ekf_slam', w.inputs(), m, EKFSlamParams(
        alphas=(0.06,) * 4))
    off = tr.arrays['lm.offset'][1]
    ids = tr.arrays['lm.id'][1]
    cxx = tr.arrays['lm.cxx'][1]
    cyy = tr.arrays['lm.cyy'][1]
    last = {}
    for k in range(len(off) - 1):
        for i in range(off[k], off[k + 1]):
            v = cxx[i] + cyy[i]
            if ids[i] in last:
                assert v <= last[ids[i]] + 1e-12
            last[ids[i]] = v


def test_ekf_slam_needs_the_idealised_sensor():
    inp = slam.SlamInputs([0], [0.0], [(0, 0, 0)], [[1.0]],
                          LidarSpec(1, 0.0, 0.0, 0.1, 5.0), (0, 0, 0))
    with pytest.raises(slam.SlamError, match='idealised'):
        mapping.run('ekf_slam', inp, loc_teaching.landmarks_map())


def test_the_sensor_is_idealised_known_ids_and_line_of_sight():
    m = loc_teaching.landmarks_map()
    smap = SketchMap(m)
    marks = landmarks.corners(m)
    assert marks and [lid for lid, _, _ in marks] == list(range(len(marks)))
    sens = landmarks.LandmarkSensor(max_range=30.0, sigma_range=0.0,
                                    sigma_bearing=0.0)
    pose = (1.5, 1.5, 0.0)
    obs = landmarks.observe(smap, pose, marks, sens, random.Random(0))
    for lid, r, b in obs:
        _, lx, ly = marks[lid]
        assert r == pytest.approx(math.hypot(lx - 1.5, ly - 1.5))
        # no wall between the robot and the corner
        assert smap.cast(1.5, 1.5, b, 30.0) >= r - 0.15 - 1e-9
    # the partition hides at least one corner from this pose
    assert len(obs) < len(marks)


def test_corner_extraction_is_deterministic_and_separated():
    m = loc_teaching.landmarks_map()
    a = landmarks.corners(m, 1.0)
    assert a == landmarks.corners(m, 1.0)
    for i, (_, x1, y1) in enumerate(a):
        for _, x2, y2 in a[i + 1:]:
            assert math.hypot(x1 - x2, y1 - y2) >= 1.0
