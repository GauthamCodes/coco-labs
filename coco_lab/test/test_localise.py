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
MCL and EKF localisation: the properties the Localise lab teaches with.

- low-variance resampling copies particle ``i`` ``floor(N w_i)`` or
  ``ceil(N w_i)`` times (hypothesis, 500 weight vectors);
- weights are normalised at every update, ``1 <= n_eff <= N``;
- seeded determinism, and the world never depends on the filter;
- the filters never read the truth (scored by it only);
- tracking: both filters stay within 0.2 m on the landmarks room;
- **convergence on a map with unique features**: from a uniform cloud,
  MCL converges in at least 7 of 10 seeded runs on ``landmarks``;
- injection: after a kidnap, MCL with injection off recovers in 0 of 4
  seeds, with augmented MCL in 4 of 4 (Sketch, measured and pinned);
- the EKF cannot recover a kidnap and cannot localise globally on the
  same inputs (the race's lesson, pinned so the exhibit cannot drift).
"""

import copy
import math
import random

from coco_lab import loc_teaching, localise as L, sketch
from hypothesis import given, settings, strategies as st
import pytest

MAPS = loc_teaching.teaching_maps()
SMAPS = {k: sketch.SketchMap(v) for k, v in MAPS.items()}
SCEN = loc_teaching.scenarios()
_WORLDS = {}


def world(sid):
    if sid not in _WORLDS:
        mid, sc, _ = SCEN[sid]
        _WORLDS[sid] = sketch.simulate(SMAPS[mid], sc)
    return _WORLDS[sid]


def smap(sid):
    return SMAPS[SCEN[sid][0]]


@settings(max_examples=500, derandomize=True, database=None,
          deadline=None)
@given(st.lists(st.floats(0.0, 1.0), min_size=1, max_size=200),
       st.floats(0.0, 0.999999))
def test_low_variance_resampling_copies_floor_or_ceil(raw, u):
    tot = sum(raw)
    if tot <= 0:
        return
    w = [v / tot for v in raw]
    n = len(w)
    idx = L.low_variance_resample(w, u)
    assert len(idx) == n
    assert idx == sorted(idx)
    for i, wi in enumerate(w):
        k = idx.count(i)
        # float accumulation can move a tooth across a boundary by 1 ulp
        assert math.floor(n * wi) - 1 <= k <= math.ceil(n * wi) + 1
        if abs(n * wi - round(n * wi)) > 1e-9:
            assert math.floor(n * wi) <= k <= math.ceil(n * wi)


def test_uniform_weights_resample_to_every_particle_once():
    assert L.low_variance_resample([0.25] * 4, 0.5) == [0, 1, 2, 3]


def test_weights_are_normalised_and_neff_bounded_every_update():
    for agg in ('amcl', 'product'):
        tr = L.run_mcl(smap('tracking'), world('tracking'),
                       L.MCLParams(particles=120, aggregate=agg,
                                   resample='neff'))
        off, w = tr.particles['offset'], tr.particles['w']
        for k in range(len(tr)):
            ws = w[off[k]:off[k + 1]]
            assert abs(sum(ws) - 1.0) < 1e-9
            assert all(v >= 0 for v in ws)
            assert 1.0 - 1e-9 <= tr.columns['n_eff'][k] <= 120 + 1e-9
        # with neff resampling some updates keep their weights
        assert 0 < sum(tr.columns['resampled']) < len(tr)


def test_mcl_is_deterministic_for_a_seed():
    p = L.MCLParams(particles=80, seed=3)
    a = L.run_mcl(smap('tracking'), world('tracking'), p)
    b = L.run_mcl(smap('tracking'), world('tracking'), p)
    assert a.columns == b.columns and a.particles == b.particles
    c = L.run_mcl(smap('tracking'), world('tracking'),
                  L.MCLParams(particles=80, seed=4))
    assert c.particles != a.particles


def test_ekf_is_deterministic():
    a = L.run_ekf(smap('tracking'), world('tracking'), L.EKFParams())
    b = L.run_ekf(smap('tracking'), world('tracking'), L.EKFParams())
    assert a.columns == b.columns


def test_the_world_never_depends_on_the_filter():
    """Filters read a world; changing a filter cannot change it."""
    mid, sc, _ = SCEN['kidnap']
    w1 = sketch.simulate(SMAPS[mid], sc)
    L.run_mcl(SMAPS[mid], w1, L.MCLParams(particles=50, seed=9))
    w2 = sketch.simulate(SMAPS[mid], sc)
    assert (w1.gt, w1.odom, w1.ranges) == (w2.gt, w2.odom, w2.ranges)


@pytest.mark.parametrize('kind', ['mcl', 'ekf'])
def test_the_filters_never_read_the_truth(kind):
    """Replace the truth with nonsense: only the error columns change."""
    w = world('kidnap')
    fake = copy.copy(w)
    fake.gt = [(99.0, -99.0, 1.0)] * len(w.gt)
    run = {'mcl': lambda ww: L.run_mcl(smap('kidnap'), ww,
                                       L.MCLParams(particles=60)),
           'ekf': lambda ww: L.run_ekf(smap('kidnap'), ww, L.EKFParams())}
    a, b = run[kind](w), run[kind](fake)
    for name in a.column_names():
        if name in ('err_xy', 'err_yaw'):
            assert a.columns[name] != b.columns[name]
        else:
            assert a.columns[name] == b.columns[name], name
    assert not hasattr(L._Inputs(w), 'gt')


def test_both_filters_track_a_known_start():
    m = L.run_mcl(smap('tracking'), world('tracking'), L.MCLParams())
    e = L.run_ekf(smap('tracking'), world('tracking'), L.EKFParams())
    assert max(m.columns['err_xy']) < 0.2
    assert max(e.columns['err_xy']) < 0.2
    assert m.summary['converged_s'] == 0.0


def test_mcl_converges_from_a_uniform_cloud_on_unique_features():
    """The phase gate's convergence test: landmarks room, global start."""
    converged = 0
    for seed in range(10):
        tr = L.run_mcl(smap('global'), world('global'),
                       L.MCLParams(init='global', particles=1000,
                                   seed=seed))
        if tr.summary['converged_s'] is not None:
            converged += 1
            assert tr.summary['final_err_xy'] < 0.15
    assert converged >= 7


def test_injection_is_what_recovers_a_kidnap():
    w = world('kidnap')
    off = [L.run_mcl(smap('kidnap'), w, L.MCLParams(seed=s))
           for s in range(4)]
    aug = [L.run_mcl(smap('kidnap'), w,
                     L.MCLParams(injection='augmented', seed=s))
           for s in range(4)]
    assert [t.summary['recovered'] for t in off] == [False] * 4
    assert sum(t.columns['injected'][-1] for t in off) == 0
    assert [t.summary['recovered'] for t in aug] == [True] * 4
    for t in aug:
        k = next(i for i, r in enumerate(t.columns['row'])
                 if r >= w.kidnap_row)
        assert sum(t.columns['injected'][k:]) > 0


def test_injection_off_never_injects_and_alpha_zero_is_off():
    t = L.run_mcl(smap('kidnap'), world('kidnap'),
                  L.MCLParams(injection='augmented', alpha_slow=0.0,
                              alpha_fast=0.0))
    assert sum(t.columns['injected']) == 0
    assert set(t.columns['p_inject']) == {0.0}


def test_the_ekf_cannot_recover_a_kidnap_or_start_globally():
    e = L.run_ekf(smap('kidnap'), world('kidnap'), L.EKFParams())
    assert e.summary['recovered'] is False
    g = L.run_ekf(smap('global'), world('global'), L.EKFParams(init='global'))
    assert g.summary['converged_s'] is None


def test_summary_definitions():
    w = world('kidnap')
    t = L.run_mcl(smap('kidnap'), w, L.MCLParams(injection='augmented'))
    s = t.summary
    assert s['ok_xy'] == 0.5 and s['ok_yaw'] == 0.3 and s['ok_hold'] == 5
    assert abs(s['kidnap_s'] - w.t[w.kidnap_row]) < 1e-12
    k = next(i for i, r in enumerate(t.columns['row'])
             if t.columns['t'][i] >= s['kidnap_s'] + s['recovery_s'] - 1e-9)
    for i in range(k, k + L.OK_HOLD):
        assert t.columns['err_xy'][i] < 0.5
        assert t.columns['err_yaw'][i] < 0.3


def test_trace_validation_refuses_bad_traces():
    t = L.run_mcl(smap('tracking'), world('tracking'),
                  L.MCLParams(particles=30))
    for mutate, msg in (
            (lambda x: x.header.update(version='2.0'), 'major'),
            (lambda x: x.header.update(filter='ukf'), 'filter'),
            (lambda x: x.particles['w'].__setitem__(0, 5.0), 'sum'),
            (lambda x: x.columns['err_xy'].__setitem__(0, math.nan),
             'finite'),
            (lambda x: x.columns['row'].__setitem__(1, 0), 'increase'),
            (lambda x: x.columns.pop('n_eff'), 'columns')):
        bad = copy.deepcopy(t)
        mutate(bad)
        with pytest.raises(L.LocError, match=msg):
            bad.validate()


def test_params_are_checked():
    for bad in (L.MCLParams(particles=0), L.MCLParams(injection='x'),
                L.MCLParams(alpha_slow=2.0), L.MCLParams(aggregate='x'),
                L.MCLParams(alphas=(1, 2, 3))):
        with pytest.raises(L.LocError):
            bad.check()
    with pytest.raises(L.LocError):
        L.EKFParams(gate=0).check()


def test_the_twins_room_aliases():
    """A global start there converges to the twin in some seeds."""
    twin_ends = 0
    for seed in range(10):
        t = L.run_mcl(smap('twins'), world('twins'),
                      L.MCLParams(init='global', particles=1000, seed=seed))
        if t.summary['final_err_xy'] > 2.0:
            twin_ends += 1
    assert 1 <= twin_ends <= 9


def test_a_random_free_pose_is_free():
    rng = random.Random(0)
    sm = smap('tracking')
    free = sm.free_cells(margin=0.11)
    for _ in range(200):
        x, y, th = L._random_free_pose(free, sm, rng)
        assert not sm.is_blocked(x, y) and -math.pi <= th < math.pi
