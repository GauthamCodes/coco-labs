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

"""The Arena's map subsystem: Lab 3's mapping and SLAM, live (M2.4)."""

import collections
import copy
import os

from coco_lab import map_arena
from coco_lab.arena import Arena, ArenaError, InputEvent, replay
from coco_lab.fastslam import FastSlam
from coco_lab.occgrid import OccupancyGrid
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'),
          encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)

CFG = lambda t, c: InputEvent(t, 'config', choice=c)  # noqa: E731
#: a 2 m square from the start: the pose graph closes loops on it
SQUARE = [(2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0), (1.0, 0.0)]


def tour(a, route, first=(), max_ticks=1500):
    """Drive ``route`` as successive goals; return the ticks."""
    pending = list(first) + [InputEvent(a.tick, 'goal', x=route[0][0],
                                        y=route[0][1])]
    nxt, ticks = 1, []
    while len(ticks) < max_ticks:
        t = a.step([e for e in pending if e.tick == a.tick])
        ticks.append(t)
        if t.mode == 'idle':
            if nxt >= len(route):
                break
            pending = [InputEvent(a.tick, 'goal', x=route[nxt][0],
                                  y=route[nxt][1])]
            nxt += 1
    return ticks


def recorder():
    seen = collections.defaultdict(list)

    def fam(channel, tick, cols, scalars):
        seen[channel].append((tick, cols, scalars))
    return seen, fam


def test_the_map_subsystem_is_registered_by_its_pack():
    assert map_arena.SUBSYSTEMS['map'] is map_arena.ArenaMapper


@pytest.mark.parametrize('bad', ['map.algorithm=gmapping', 'map.poses=gps',
                                 'map.fastslam.particles=0',
                                 'map.pose_graph.loop_closure=maybe',
                                 'map.grid=1'])
def test_a_bad_setting_is_refused(bad):
    a = Arena(SPEC, seed=1)
    with pytest.raises(ArenaError):
        a.step([CFG(0, bad)])


def test_known_pose_occupancy_is_lab_3s_grid_fed_the_same_scans(monkeypatch):
    fed = []

    class Spy(OccupancyGrid):

        def integrate(self, pose, z, *rest):
            fed.append((pose, list(z), rest))
            return super().integrate(pose, z, *rest)
    monkeypatch.setattr(map_arena, 'OccupancyGrid', Spy)
    a = Arena(SPEC, seed=3)
    tour(a, [(3.0, 0.0), (3.0, 2.0)], first=[
        CFG(0, 'map.algorithm=occupancy')], max_ticks=300)
    m = a.subsystems['map']
    assert len(fed) > 20
    g = OccupancyGrid.like(m.like, m.grid_params)
    for pose, z, rest in fed:
        g.integrate(pose, z, *rest)
    assert g.logodds == m.grid.logodds
    assert all(abs(p[0] - q[0]) < 1e-12 for p, q in
               zip([f[0] for f in fed], m.true_hist))


def test_fastslam_in_the_arena_is_lab_3s_class_draw_for_draw(monkeypatch):
    calls, made = [], []

    class Spy(FastSlam):

        def __init__(self, start, lidar, like, params, gp, rng):
            made.append((start, lidar, like, copy.deepcopy(params), gp,
                         copy.deepcopy(rng)))
            super().__init__(start, lidar, like, params, gp, rng)

        def update(self, odom, z):
            calls.append((odom, list(z)))
            out = super().update(odom, z)
            calls[-1] += (out['est'],)
            return out
    monkeypatch.setattr(map_arena, 'FastSlam', Spy)
    a = Arena(SPEC, seed=4)
    tour(a, [(3.0, 0.0), (3.0, 2.0)], first=[
        CFG(0, 'map.algorithm=fastslam'),
        CFG(0, 'map.fastslam.particles=8')], max_ticks=250)
    assert len(made) == 2 and len(calls) > 15  # two configs: two starts
    start, lidar, like, params, gp, rng = made[-1]
    f = FastSlam(start, lidar, like, params, gp, rng)
    for odom, z, est in calls:
        assert f.update(odom, z)['est'] == est


def test_ekf_slam_is_labelled_idealised_in_the_data():
    seen, fam = recorder()
    a = Arena(SPEC, seed=5, on_family=fam)
    tour(a, [(3.0, 0.0)], first=[CFG(0, 'map.algorithm=ekf_slam')],
         max_ticks=120)
    (_, _, head), = seen['coco.map.slam.header.v1']
    assert head['sensor'] == 'landmarks'
    assert 'IDEALISED' in head['sensor_label']
    assert 'COCO has none' in head['sensor_label']
    assert seen['coco.map.slam.landmarks.v1']


def test_the_pose_graph_shows_each_closure_before_and_after():
    seen, fam = recorder()
    a = Arena(SPEC, seed=7, on_family=fam)
    tour(a, SQUARE, first=[CFG(0, 'map.algorithm=pose_graph')])
    m = a.subsystems['map']
    assert len(m.engine.loop_events) >= 1
    # ATE pairs node i with update i's truth: one node per update, none lost
    assert len(m.engine.poses) == len(m.true_hist) == m.updates
    by_tick = collections.defaultdict(dict)
    for tick, cols, sc in seen['coco.map.slam.nodes.v1']:
        by_tick[tick][sc['stage']] = (cols, sc)
    closures = [d for d in by_tick.values() if 'optimised' in d]
    # several closures found in one update share one optimisation
    assert len(closures) == len({k for k, _ in m.engine.loop_events})
    for d in closures:
        assert 'raw' in d
        assert d['optimised'][1]['chi2'] <= d['raw'][1]['chi2'] + 1e-9
    kinds = set()
    for _, cols, _ in seen['coco.map.slam.edges.v1']:
        kinds.update(cols['kind'])
    assert 'loop' in kinds


def test_without_loop_closure_no_edge_is_a_loop():
    seen, fam = recorder()
    a = Arena(SPEC, seed=7, on_family=fam)
    tour(a, SQUARE, first=[CFG(0, 'map.algorithm=pose_graph'),
                           CFG(0, 'map.pose_graph.loop_closure=off')])
    assert a.subsystems['map'].engine.loop_events == []
    for _, cols, _ in seen['coco.map.slam.edges.v1']:
        assert 'loop' not in cols['kind']


def test_scores_are_ate_and_f1_and_are_emitted_as_metrics():
    seen, fam = recorder()
    a = Arena(SPEC, seed=6, on_family=fam)
    tour(a, [(3.0, 0.0), (3.0, 2.0)], first=[
        CFG(0, 'map.algorithm=occupancy')], max_ticks=300)
    m = a.subsystems['map']
    sc = m.scores()
    assert sc['ate'] == 0.0  # true poses
    assert 0.0 < sc['f1'] <= 1.0 and sc['precision'] == 1.0
    names = set()
    for _, cols, _ in seen['coco.metrics.values.v1']:
        names.update(cols['name'])
    assert {'ate', 'f1', 'precision', 'recall'} <= names


def test_keyframes_carry_the_whole_grid_as_float32():
    seen, fam = recorder()
    a = Arena(SPEC, seed=6, on_family=fam)
    tour(a, [(3.0, 0.0)], first=[CFG(0, 'map.algorithm=occupancy')],
         max_ticks=120)
    (_, _, head), = seen['coco.map.grid.header.v1']
    snaps = seen['coco.map.grid.snapshot.v1']
    assert snaps
    _, cols, sc = snaps[-1]
    assert cols['logodds_f32'].typecode == 'f'
    assert len(cols['logodds_f32']) == head['width'] * head['height']
    assert head['resolution'] == pytest.approx(0.10)
    assert sc['map_id'] == 'occupancy'


def test_dead_reckoning_mapping_drifts_and_true_poses_do_not():
    first = [CFG(0, 'arena.odom_alphas=0.1,0.1,0.1,0.1')]
    known, dead = Arena(SPEC, seed=8), Arena(SPEC, seed=8)
    tour(known, SQUARE, first=first + [CFG(0, 'map.algorithm=occupancy')])
    tour(dead, SQUARE, first=first + [CFG(0, 'map.poses=odometry'),
                                      CFG(0, 'map.algorithm=occupancy')])
    k, d = known.subsystems['map'], dead.subsystems['map']
    assert k.scores()['ate'] == 0.0
    assert d.scores()['ate'] > 0.01
    # the same drive: the mapping does not steer the robot
    assert k.true_hist == d.true_hist


def test_the_map_run_is_deterministic_and_hashed():
    ins = [CFG(0, 'map.algorithm=fastslam'),
           CFG(0, 'map.fastslam.particles=5'),
           InputEvent(0, 'goal', x=3.0, y=0.0)]
    h = replay(SPEC, 3, ins, 60)
    assert h == replay(SPEC, 3, ins, 60)
    other = replay(SPEC, 3, [CFG(0, 'map.algorithm=occupancy')] + ins[2:], 60)
    assert h != other


def test_a_reset_starts_the_map_again():
    a = Arena(SPEC, seed=9)
    tour(a, [(3.0, 0.0)], first=[CFG(0, 'map.algorithm=occupancy')],
         max_ticks=120)
    assert a.subsystems['map'].updates > 0
    a.step([InputEvent(a.tick, 'reset')])
    assert a.subsystems['map'].updates <= 1
