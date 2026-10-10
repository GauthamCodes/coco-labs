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

"""The Arena model core (M1.3), on the COCO arena's World Spec."""

import math
import os
import random

from coco_lab.arena import (Arena, ArenaError, InputEvent, is_free, PLANNERS,
                            replay)
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SPEC_PATH = os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml')

with open(SPEC_PATH, encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)


@pytest.fixture(scope='module')
def arena0():
    return Arena(SPEC, seed=1)


def run(arena, inputs, ticks):
    by = {}
    for e in inputs:
        by.setdefault(e.tick, []).append(e)
    return [arena.step(by.get(arena.tick, ())) for _ in range(ticks)]


def test_the_robot_starts_at_the_specs_start_in_the_map_frame(arena0):
    # start (-2, 0) in the world; world_to_map (2, 0)
    assert arena0.start == (0.0, 0.0, 0.0)
    assert arena0.dt == 0.1
    assert len(arena0.ranges) == 480


def test_teleop_ramps_at_the_accel_limit_and_clamps():
    a = Arena(SPEC, seed=1)
    ticks = run(a, [InputEvent(0, 'teleop', linear=5.0, angular=0.0)], 5)
    # 2.0 m/s^2 x 0.1 s = 0.2 m/s per tick, clamped at teleop 0.5 m/s
    assert [round(t.v, 9) for t in ticks] == [0.2, 0.4, 0.5, 0.5, 0.5]
    assert ticks[-1].pose[0] == pytest.approx(0.02 + 0.04 + 0.05 * 3)
    assert ticks[-1].mode == 'teleop'


def test_stop_is_immediate_and_clears_the_goal():
    a = Arena(SPEC, seed=1)
    run(a, [InputEvent(0, 'teleop', linear=0.5)], 4)
    t = a.step([InputEvent(4, 'stop')])
    assert (t.v, t.w, t.mode) == (0.0, 0.0, 'idle')


def test_a_goal_is_planned_driven_and_reached():
    a = Arena(SPEC, seed=1)
    goal = (1.5, 1.0)
    assert is_free(a, *goal)
    ticks = run(a, [InputEvent(0, 'goal', x=goal[0], y=goal[1])], 400)
    plan = ticks[0].plans[0]
    assert plan.result.status == 'found' and plan.planner == 'astar'
    assert plan.result.trace.summary['expansions'] > 0
    done = [t for t in ticks if t.arrived]
    assert done, 'the robot never arrived'
    x, y, _ = done[0].pose
    assert math.hypot(x - goal[0], y - goal[1]) < 0.15
    assert ticks[-1].mode == 'idle'


def test_the_robot_never_enters_a_wall():
    a = Arena(SPEC, seed=1)
    # drive straight at the nearest wall for 30 s
    ticks = run(a, [InputEvent(0, 'teleop', linear=0.5, angular=0.3)], 300)
    assert any(t.blocked for t in ticks)
    for t in ticks:
        assert a.smap.clearance(t.pose[0], t.pose[1]) >= a.radius * 0.5


def test_switching_planner_replans_a_running_goal():
    a = Arena(SPEC, seed=1)
    run(a, [InputEvent(0, 'goal', x=3.0, y=1.0)], 3)
    t = a.step([InputEvent(3, 'planner', choice='dijkstra')])
    assert [p.planner for p in t.plans] == ['dijkstra']
    assert t.plans[0].result.trace.header['algorithm'] == 'dijkstra'


def test_every_planner_runs(arena0):
    for name in PLANNERS:
        a = Arena(SPEC, seed=1, planner=name)
        t = a.step([InputEvent(0, 'goal', x=2.0, y=-1.0)])
        assert t.plans[0].result.status == 'found', name


def test_reset_returns_to_the_start():
    a = Arena(SPEC, seed=1)
    run(a, [InputEvent(0, 'teleop', linear=0.5)], 10)
    t = a.step([InputEvent(10, 'reset')])
    assert t.pose == a.start and t.mode == 'idle'


def test_inputs_are_validated_and_must_match_their_tick():
    with pytest.raises(ArenaError):
        InputEvent(0, 'fly')
    with pytest.raises(ArenaError):
        InputEvent(-1, 'stop')
    with pytest.raises(ArenaError):
        InputEvent(0, 'goal', x=math.nan)
    a = Arena(SPEC, seed=1)
    with pytest.raises(ArenaError):
        a.step([InputEvent(5, 'stop')])
    with pytest.raises(ArenaError):
        a.step([InputEvent(0, 'planner', choice='rrt')])


def random_inputs(rng, ticks):
    out = []
    for k in range(0, ticks, 7):
        r = rng.random()
        if r < 0.3:
            out.append(InputEvent(k, 'teleop', linear=rng.uniform(-0.5, 0.5),
                                  angular=rng.uniform(-1.2, 1.2)))
        elif r < 0.45:
            out.append(InputEvent(k, 'goal', x=rng.uniform(-1, 4),
                                  y=rng.uniform(-3, 3)))
        elif r < 0.5:
            out.append(InputEvent(k, 'stop'))
        elif r < 0.55:
            out.append(InputEvent(k, 'planner',
                                  choice=rng.choice(list(PLANNERS))))
    return out


def safe(inputs, arena):
    """Drop goals that land in blocked cells (the UI refuses those)."""
    return [e for e in inputs
            if e.kind != 'goal' or is_free(arena, e.x, e.y)]


def test_same_spec_seed_and_inputs_give_the_same_hashes_tick_for_tick(arena0):
    rng = random.Random(5)
    for session in range(3):
        inputs = safe(random_inputs(rng, 120), arena0)
        a = replay(SPEC, session, inputs, 120, range_sigma=0.01)
        b = replay(SPEC, session, inputs, 120, range_sigma=0.01)
        assert a == b
        assert len(set(a)) > 1


def test_the_hash_sees_the_seed_the_noise_and_the_inputs(arena0):
    inputs = [InputEvent(0, 'teleop', linear=0.3)]
    base = replay(SPEC, 1, inputs, 5)
    assert replay(SPEC, 2, inputs, 5) != base           # RNG state differs
    assert replay(SPEC, 1, inputs, 5, range_sigma=0.01) != base
    assert replay(SPEC, 1, [InputEvent(0, 'teleop', linear=0.31)], 5) != base


def test_the_state_layout_has_the_documented_size(arena0):
    n = len(arena0.ranges)
    assert len(arena0.state_bytes()) == 8 + 5 * 8 + 3 + 2 * 8 + 2 * 4 \
        + 32 + 32 + 4 + 4 * n


def test_streaming_plan_batches_changes_nothing_and_carries_the_trace():
    """on_plan_batch sees the search as it runs; the state is unaffected."""
    batches = []
    inputs = [InputEvent(0, 'goal', x=6.0, y=4.0),
              InputEvent(30, 'planner', choice='dijkstra')]
    a = Arena(SPEC, seed=4, on_plan_batch=lambda c, m: batches.append((c, m)),
              plan_batch_size=500)
    ticks = run(a, inputs, 40)
    assert [t.state_hash for t in ticks] == replay(SPEC, 4, inputs, 40)
    plans = [p for t in ticks for p in t.plans]
    assert [m['search_id'] for _, m in batches if m['final']] == [0, 1]
    for p, sid in zip(plans, (0, 1)):
        mine = [c for c, m in batches if m['search_id'] == sid]
        assert all(len(c['seq']) <= 500 for c in mine)
        kinds = [k for c in mine for k in c['kind']]
        assert kinds == [k + 1 for k in p.result.trace.events['kind']]
        rows = [r for c in mine for r in c['row']]
        assert rows == list(p.result.trace.events['row'])


# -- M2.0: one search per tick, after all its inputs; slices and amends -------

def multi_inputs(rng, ticks, arena):
    """Ticks with one to three inputs each (goals, planner changes, stops)."""
    out = []
    for k in range(0, ticks, 5):
        for _ in range(rng.randint(1, 3)):
            r = rng.random()
            if r < 0.45:
                out.append(InputEvent(k, 'goal', x=rng.uniform(-1, 8),
                                      y=rng.uniform(-3, 5)))
            elif r < 0.75:
                out.append(InputEvent(k, 'planner',
                                      choice=rng.choice(list(PLANNERS))))
            elif r < 0.85:
                out.append(InputEvent(k, 'stop'))
            else:
                out.append(InputEvent(k, 'teleop', linear=0.3, angular=0.4))
    return safe(out, arena)


def test_a_goal_and_a_planner_change_in_one_tick_make_one_search():
    a = Arena(SPEC, seed=1)
    t = a.step([InputEvent(0, 'goal', x=6.0, y=4.0),
                InputEvent(0, 'planner', choice='dijkstra')])
    assert [p.planner for p in t.plans] == ['dijkstra']
    b = Arena(SPEC, seed=1)
    u = b.step([InputEvent(0, 'planner', choice='dijkstra'),
                InputEvent(0, 'goal', x=6.0, y=4.0)])
    assert t.state_hash == u.state_hash
    # a goal cancelled by a STOP in the same tick is never searched
    c = Arena(SPEC, seed=1)
    v = c.step([InputEvent(0, 'goal', x=6.0, y=4.0), InputEvent(0, 'stop')])
    assert v.plans == [] and v.mode == 'idle'


def test_sliced_and_amended_steps_equal_whole_steps(arena0):
    """Whatever the slicing, and however a tick's inputs arrive, same hashes."""
    rng = random.Random(11)
    for session in range(3):
        inputs = multi_inputs(rng, 60, arena0)
        whole = replay(SPEC, session, inputs, 60)
        a = Arena(SPEC, session, on_plan_batch=lambda c, m: None,
                  plan_batch_size=64)
        got = []
        for _ in range(60):
            mine = [e for e in inputs if e.tick == a.tick]
            # first input at begin, the rest one by one as amendments,
            # each after a few events of the search in flight
            a.begin_step(mine[:1])
            for e in mine[1:]:
                a.advance(rng.randint(0, 40))
                a.amend([e])
            while not a.advance(rng.randint(1, 97)):
                pass
            got.append(a.finish_step().state_hash)
        assert got == whole


def test_an_amendment_cancels_the_search_in_flight_and_ids_never_repeat():
    seen = []
    a = Arena(SPEC, seed=2, on_plan_batch=lambda c, m: seen.append(dict(m)),
              plan_batch_size=50)
    a.step([InputEvent(0, 'goal', x=6.0, y=4.0)])           # search 0
    a.begin_step([InputEvent(1, 'planner', choice='bfs')])  # re-plan: 1
    a.advance(120)
    a.amend([InputEvent(1, 'goal', x=2.5, y=2.0)])           # cancels 1
    t = a.finish_step()
    assert any(m['search_id'] == 1 and m.get('cancelled') for m in seen)
    assert [(p.planner, p.goal) for p in t.plans] == [('bfs', (2.5, 2.0))]
    finals = [m['search_id'] for m in seen
              if m['final'] and not m.get('cancelled')]
    assert finals == [0, 2]
    assert not any(m['search_id'] == 2 and m.get('cancelled') for m in seen)


def test_a_refused_amendment_leaves_the_tick_as_it_was():
    a = Arena(SPEC, seed=3)
    b = Arena(SPEC, seed=3)
    ev = [InputEvent(0, 'goal', x=6.0, y=4.0)]
    a.begin_step(ev)
    with pytest.raises(ArenaError):
        a.amend([InputEvent(0, 'planner', choice='no_such_planner')])
    with pytest.raises(ArenaError):
        a.amend([InputEvent(5, 'stop')])                     # wrong tick
    assert a.finish_step().state_hash == b.step(ev).state_hash


def test_step_calls_out_of_order_are_refused():
    a = Arena(SPEC, seed=1)
    for call in (lambda: a.advance(1), lambda: a.amend([]), a.finish_step):
        with pytest.raises(ArenaError):
            call()
    a.begin_step([])
    with pytest.raises(ArenaError):
        a.begin_step([])
    a.finish_step()
