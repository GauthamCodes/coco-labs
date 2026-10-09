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

"""Local control in the Arena: the move subsystem and its controllers (M2.5)."""

import collections
import hashlib
import json
import math
import os

from coco_lab import control, move_arena, move_scenarios
from coco_lab.arena import _with_discs, Arena, ArenaError, InputEvent, replay
from coco_lab.rng import Rng
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CFG = os.path.join(REPO, 'coco_lab_ros', 'config')
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'),
          encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)

CFG_IN = lambda t, c: InputEvent(t, 'config', choice=c)  # noqa: E731


def scenario(ctrl, sc, seed=1, ticks=None):
    seen = collections.defaultdict(list)

    def fam(ch, tick, cols, scalars):
        seen[ch].append((tick, cols, scalars))
    a = Arena(SPEC, seed, on_family=fam)
    a.step([CFG_IN(0, f'move.controller={ctrl}'),
            CFG_IN(0, f'move.scenario={sc}')])
    n = 1
    while a.mode == 'goal' and (ticks is None or n < ticks):
        a.step(())
        n += 1
    return a, seen


def test_the_scenarios_are_lab_5s_files():
    def sha(p):
        with open(p, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    assert move_scenarios.SOURCES['lab5_scenarios.json'] == \
        sha(os.path.join(CFG, 'lab5_scenarios.json'))
    with open(os.path.join(CFG, 'lab5_scenarios.json')) as f:
        doc = {s['id']: s for s in json.load(f)['scenarios']}
    for sid, s in move_scenarios.SCENARIOS.items():
        d = doc[sid]
        assert (s['path'], s['start'], s['goal']) == (d['path'], d['start'],
                                                      d['goal'])
        assert [a['waypoints'] for a in s['actors']] == \
            [a['waypoints'] for a in d['actors']]
        assert s['inject'] == d.get('inject')
    for name, poses in move_scenarios.PATHS.items():
        p = os.path.join(CFG, 'lab5_paths', name)
        assert move_scenarios.SOURCES[name] == sha(p)
        with open(p) as f:
            ref = json.load(f)['poses']
        assert len(poses) == len(ref)
        assert max(abs(a - b) for q, r in zip(poses, ref)
                   for a, b in zip(q, r)) <= 5e-7


def test_the_move_subsystem_is_registered_by_its_pack():
    assert move_arena.SUBSYSTEMS['move'] is move_arena.ArenaMover


@pytest.mark.parametrize('bad', ['move.controller=teb', 'move.scenario=park',
                                 'move.belief_offset=1,2', 'move.speed=1'])
def test_a_bad_setting_is_refused(bad):
    with pytest.raises(ArenaError):
        Arena(SPEC, seed=1).step([CFG_IN(0, bad)])


def test_the_builtin_controller_is_m1s_driver():
    goal = InputEvent(0, 'goal', x=3.0, y=2.0)
    plain, moved = Arena(SPEC, seed=2), Arena(SPEC, seed=2)
    plain.step([goal])
    moved.step([goal, CFG_IN(0, 'move.controller=builtin')])
    for _ in range(80):
        assert plain.step(()).pose == moved.step(()).pose


@pytest.mark.parametrize('ctrl', ['dwa', 'rpp', 'mppi'])
def test_run_15_mislocalised_every_controller_has_no_path_in_its_window(ctrl):
    a, seen = scenario(ctrl, 'mislocalised')
    m = a.subsystems['move']
    assert m.outcome == 'invalid_path' and move_arena.CODES[m.outcome] == 103
    assert m.cycle == 1  # the first cycle
    (_, cols, _), = seen['coco.control.local.command.v1']
    assert list(cols['status']) == ['invalid_path']
    assert list(cols['n_candidates']) == [0]  # 0 of 0, as Lab 5 measured
    b = a.belief()
    assert math.hypot(b[0] - a.pose[0], b[1] - a.pose[1]) == \
        pytest.approx(3.4)


def test_the_path_is_pruned_to_the_window_from_the_believed_pose():
    path = [(0.0, -0.05 * k) for k in range(151)]
    tr = control.PathTracker(path)
    near = control.LocalWindow((0.0, 0.0, -1.57), [], [], (0, 0, 0), path)
    assert len(tr.local((0.0, 0.0, -1.57), near)) > 20
    far = control.LocalWindow((0.0, 3.4, -1.57), [], [], (0, 0, 0), path)
    assert control.PathTracker(path).local((0.0, 3.4, -1.57), far) == []


def test_the_local_window_inflates_as_nav2_does():
    p = control.WindowParams()
    assert p.inscribed == pytest.approx(0.255004, abs=1e-6)
    # one beam straight ahead hits at 1.0 m
    w = control.LocalWindow((0.0, 0.0, 0.0), [1.0], [0.0], (0.0, 0.0, 0.0),
                            [], p)
    assert w.cost(1.01, 0.01) == control.LETHAL
    assert w.cost(1.01 - 0.2, 0.01) == control.INSCRIBED
    d = 0.4
    c = w.cost(1.025 - d, 0.025)
    assert c == int(252 * math.exp(-65 * (d - p.inscribed)))
    assert w.cost(0.2, 0.0) == 0
    assert w.cost(1.6, 0.0) == control.OFF  # off the 3 m window
    # beyond the 2.5 m marking range: nothing is marked
    far = control.LocalWindow((0.0, 0.0, 0.0), [2.6], [0.0], (0, 0, 0), [], p)
    assert far.marks == 0


def test_a_lidar_beam_stops_at_a_disc():
    a = Arena(SPEC, seed=1)
    li = a.lidar
    base = [math.inf] * len(a.angles)
    mid = min(range(len(a.angles)), key=lambda k: abs(a.angles[k]))
    out = _with_discs(base, (0.0, 0.0, 0.0), li, a.angles, [(2.0, 0.1, 0.15)])
    sx = li.mount[0]
    expect = math.hypot(2.0 - sx, 0.1 - li.mount[1]) - 0.15
    assert out[mid] == pytest.approx(expect, abs=0.02)
    assert out[0] == math.inf


def test_an_actor_is_solid_and_seen():
    a, _ = scenario('rpp', 'oncoming')
    m = a.subsystems['move']
    ac = m.actors[0]
    assert ac.triggered
    gap = math.hypot(ac.x - a.pose[0], ac.y - a.pose[1])
    assert gap >= a.radius + ac.r - 1e-9  # never inside the robot
    assert a.step(()).actors == [(ac.x, ac.y, ac.r)]


def test_an_actor_waits_until_triggered_by_the_true_pose():
    a, _ = scenario('dwa', 'crossing', ticks=5)
    ac = a.subsystems['move'].actors[0]
    assert not ac.triggered and (ac.x, ac.y) == (-1.5, -4.5)


def test_rpp_refuses_to_drive_into_a_collision_ahead():
    path = [(0.05 * k, 0.0) for k in range(40)]
    angles = [-0.02, 0.0, 0.02]
    w = control.LocalWindow((0.0, 0.0, 0.0), [0.5, 0.5, 0.5], angles,
                            (0, 0, 0), path)
    tr = control.PathTracker(path)
    cy = control.RPP().compute((0.0, 0.0, 0.0), 0.3, 0.0, w,
                               tr.local((0.0, 0.0, 0.0), w), 0.1)
    assert cy.status == 'collision_ahead' and not cy.candidates[0].valid
    clear = control.LocalWindow((0.0, 0.0, 0.0), [], [], (0, 0, 0), path)
    cy = control.RPP().compute((0.0, 0.0, 0.0), 0.3, 0.0, clear,
                               tr.local((0.0, 0.0, 0.0), clear), 0.1)
    assert cy.status == 'ok' and cy.v == pytest.approx(0.3)
    assert cy.lookahead[0] == pytest.approx(0.6, abs=0.05)


def test_dwa_scores_every_sample_and_follows_a_clear_path():
    path = [(0.05 * k, 0.0) for k in range(40)]
    w = control.LocalWindow((0.0, 0.0, 0.0), [], [], (0, 0, 0), path)
    tr = control.PathTracker(path)
    cy = control.DWA().compute((0.0, 0.0, 0.0), 0.2, 0.0, w,
                               tr.local((0.0, 0.0, 0.0), w), 0.1)
    assert cy.status == 'ok' and cy.n_candidates == 11 * 21
    assert cy.v == pytest.approx(0.3) and abs(cy.w) < 1e-9
    assert all(len(c.scores) == 5 for c in cy.candidates if c.valid)


def test_mppi_is_deterministic_for_its_stream():
    path = [(0.05 * k, 0.0) for k in range(40)]
    w = control.LocalWindow((0.0, 0.0, 0.0), [], [], (0, 0, 0), path)
    local = control.PathTracker(path).local((0.0, 0.0, 0.0), w)
    runs = [control.MPPI(Rng(s)).compute((0.0, 0.0, 0.0), 0.0, 0.0, w,
                                         local, 0.1) for s in (5, 5, 6)]
    assert (runs[0].v, runs[0].w) == (runs[1].v, runs[1].w)
    assert (runs[0].v, runs[0].w) != (runs[2].v, runs[2].w)
    assert runs[0].n_candidates == 128 and len(runs[0].candidates) == 25


def test_normals_look_standard():
    xs = control.normals(Rng(1), 20000)
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
    assert abs(m) < 0.03 and abs(sd - 1) < 0.03


def test_the_hairpin_and_the_crossing_reach_their_outcomes():
    a, seen = scenario('rpp', 'static_room')
    assert a.subsystems['move'].outcome == 'succeeded'
    names = set()
    for _, cols, _ in seen['coco.metrics.values.v1']:
        names.update(cols['name'])
    assert {'n_valid', 'cmd_v', 'tracking_error',
            'outcome.succeeded'} <= names
    (_, _, head), = seen['coco.control.local.header.v1']
    assert head['evidence'] == 'MODEL' and head['kind'] == 'rpp'


def test_a_move_run_is_deterministic_and_hashed():
    ins = [CFG_IN(0, 'move.controller=mppi'), CFG_IN(0, 'move.scenario=crossing')]
    h = replay(SPEC, 3, ins, 40)
    assert h == replay(SPEC, 3, ins, 40)
    assert h != replay(SPEC, 4, ins, 40)  # MPPI's noise follows the seed


def test_candidates_carry_one_score_per_critic():
    a, seen = scenario('dwa', 'crossing', ticks=3)
    _, cols, sc = seen['coco.control.local.candidates.v1'][-1]
    n = len(cols['candidate'])
    assert len(cols['critic_scores']) == n * 5
    assert sum(cols['traj_len']) == len(cols['traj_x']) == len(cols['traj_y'])
    assert sc['controller_id'] == 'dwa'
