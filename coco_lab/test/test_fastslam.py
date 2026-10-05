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

"""Grid FastSLAM: determinism, the particle invariants, the ancestry."""

import math

from coco_lab import loc_teaching, mapeval, mapping, mapworld, slam
from coco_lab.fastslam import FastSlamParams
from coco_lab.sketch import Noise, Scenario
import pytest

ROUTE = loc_teaching.LANDMARKS_ROUTE[:4]


def _world(seed=2, scale=3.0, sigma=0.02):
    m = loc_teaching.landmarks_map()
    sc = Scenario(start=(1.5, 1.5, 0.0), route=ROUTE, seed=seed,
                  noise=Noise(odom_alphas=(0.02 * scale,) * 4,
                              range_sigma=sigma))
    return m, mapworld.from_sketch(m, sc)


def _run(m, w, **kw):
    kw.setdefault('alphas', (0.06,) * 4)
    kw.setdefault('particles', 12)
    return mapping.run('fastslam', w.inputs(), m, FastSlamParams(**kw))


@pytest.fixture(scope='module')
def world():
    return _world()


@pytest.fixture(scope='module')
def trace(world):
    return _run(*world)


def test_the_same_seed_gives_the_same_run_bit_for_bit(world, trace):
    again = _run(*world)
    assert again.columns == trace.columns
    assert again.arrays == trace.arrays
    assert again.maps == trace.maps


def test_another_seed_gives_another_run(world, trace):
    other = _run(*world, seed=1)
    assert other.arrays['particles.x'] != trace.arrays['particles.x']


def test_weights_are_normalised_and_neff_is_in_range(trace):
    off = trace.arrays['particles.offset'][1]
    w = trace.arrays['particles.w'][1]
    n = trace.header['params']['particles']
    for k in range(len(off) - 1):
        ws = w[off[k]:off[k + 1]]
        assert len(ws) == n
        assert sum(ws) == pytest.approx(1.0, abs=1e-5)  # f32 on the wire
        neff = trace.columns['neff'][k]
        assert 1.0 - 1e-9 <= neff <= n + 1e-9


def test_resampling_happens_only_below_the_neff_threshold(trace):
    n = trace.header['params']['particles']
    frac = trace.header['params']['neff_fraction']
    for k, (neff, r) in enumerate(zip(trace.columns['neff'],
                                      trace.columns['resampled'])):
        if r:
            assert k > 0 and neff < frac * n
        elif k > 0:
            assert neff >= frac * n


def test_the_estimate_is_the_heaviest_particle(trace):
    off = trace.arrays['particles.offset'][1]
    px, w = trace.arrays['particles.x'][1], trace.arrays['particles.w'][1]
    for k in range(len(off) - 1):
        ws = w[off[k]:off[k + 1]]
        best = trace.columns['best'][k]
        assert ws[best] == max(ws)
        assert trace.columns['est_x'][k] == pytest.approx(
            px[off[k] + best], abs=1e-4)


def test_the_final_trajectory_is_one_particles_ancestry(trace):
    """Every final pose is a particle that existed at that update."""
    off = trace.arrays['particles.offset'][1]
    px = trace.arrays['particles.x'][1]
    py = trace.arrays['particles.y'][1]
    fin = trace.final_trajectory()
    for k, (x, y, _) in enumerate(fin):
        here = list(zip(px[off[k]:off[k + 1]], py[off[k]:off[k + 1]]))
        assert any(math.hypot(x - a, y - b) < 1e-4 for a, b in here)
    # and it ends where the heaviest particle is
    assert fin[-1][0] == pytest.approx(trace.columns['est_x'][-1])


def test_a_noise_free_world_is_mapped_where_it_is():
    m, w = _world(scale=0.0, sigma=0.0)
    tr = _run(m, w, alphas=(0.001,) * 4, particles=5)
    a = mapeval.ate(tr.estimates(), w.true_poses(), align=False)
    assert a['rmse'] < 0.10  # within one 0.10 m cell


def test_fastslam_beats_odometry_on_the_landmarks_room(world, trace):
    m, w = world
    tp = w.true_poses()
    odo = mapping.run('odometry', w.inputs(), m)
    assert mapeval.ate(trace.final_trajectory(), tp, False)['rmse'] < \
        mapeval.ate(odo.estimates(), tp, False)['rmse']


def test_the_slams_cannot_read_the_truth():
    """No field of the SLAMs' inputs could carry it."""
    fields = set(slam.SlamInputs.__dataclass_fields__)
    assert not fields & {'gt', 'truth', 'true_poses', 'gt_x'}
    assert fields == {'rows', 't', 'odom', 'ranges', 'lidar', 'start',
                      'landmarks', 'landmark_sensor'}
