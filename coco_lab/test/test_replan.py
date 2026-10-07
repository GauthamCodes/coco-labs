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
The replanning episode (coco_lab.replan): a robot that learns the map.

The claims Lab 5 shows, each a test here:

- every round's D* Lite cost equals A* from scratch on the same map
  (``test_every_round_agrees_with_astar_from_scratch``, 1,000 seeded
  worlds);
- with an optimistic map the robot reaches the goal whenever the world
  has a route, and never enters a cell that is blocked in the world
  (``test_an_optimistic_robot_arrives_iff_the_world_has_a_route``);
- the same world gives the same episode, byte for byte
  (``test_an_episode_is_deterministic``).
"""

import math
import random

from coco_lab.dstarlite import ReplanError
from coco_lab.grid import Grid
from coco_lab.replan import ReplanWorld, run_replan, sketch_world
from coco_lab.search import search
from hypothesis import given, HealthCheck, settings, strategies as st
import pytest

WORLDS = settings(max_examples=1000, derandomize=True, database=None,
                  deadline=None,
                  suppress_health_check=[HealthCheck.too_slow])


def random_world(seed, sense):
    """Return a seeded optimistic world (the map lacks some obstacles)."""
    rng = random.Random(seed)
    w, h = rng.randint(4, 18), rng.randint(4, 18)
    truth = [rng.random() < rng.choice([0.1, 0.25, 0.4]) for _ in range(w * h)]
    known = [t and rng.random() < 0.5 for t in truth]
    start = (rng.randrange(h), rng.randrange(w))
    goal = (rng.randrange(h), rng.randrange(w))
    while goal == start:
        goal = (rng.randrange(h), rng.randrange(w))
    for r, c in (start, goal):
        truth[r * w + c] = known[r * w + c] = False
    conn = rng.choice([4, 8])
    return ReplanWorld(w, h, known, truth, start, goal, sense_radius=sense,
                       connectivity=conn,
                       heuristic='octile' if conn == 8 else 'manhattan')


@WORLDS
@given(seed=st.integers(0, 2 ** 31),
       sense=st.sampled_from([1.5, 2.5, 4.0, None]))
def test_every_round_agrees_with_astar_from_scratch(seed, sense):
    res = run_replan(random_world(seed, sense))
    s = res.summary()
    assert s['costs_agree']
    for r in res.rounds:
        assert (r.cost is None) == (not r.found)
        if r.found:
            assert r.path[0] == r.robot and r.path[-1] == res.world.goal


@WORLDS
@given(seed=st.integers(0, 2 ** 31),
       sense=st.sampled_from([1.5, 2.5, None]))
def test_an_optimistic_robot_arrives_iff_the_world_has_a_route(seed, sense):
    world = random_world(seed, sense)
    res = run_replan(world)
    truth = world.grid(world.truth)
    route = search(truth, world.start, world.goal, 'dijkstra').found
    assert res.status == ('reached' if route else 'no_path')
    for a, b in zip(res.walk, res.walk[1:]):
        assert b in list(truth.neighbours(a)), (a, b)
    assert res.walk[0] == world.start
    if route:
        assert res.walk[-1] == world.goal


def test_an_episode_is_deterministic():
    a, b = run_replan(sketch_world(5)), run_replan(sketch_world(5))
    assert a.walk == b.walk
    assert a.trace.columns == b.trace.columns
    assert a.summary() == b.summary()


def test_sketch_worlds_are_seeded_and_differ():
    assert sketch_world(1).truth == sketch_world(1).truth
    assert sketch_world(1).truth != sketch_world(2).truth
    w = sketch_world(3)
    # optimistic: nothing is blocked on the map that is free in the world
    assert not any(k and not t for k, t in zip(w.known, w.truth))


@pytest.mark.parametrize('seed', range(8))
def test_the_closed_door_forces_at_least_one_replan(seed):
    res = run_replan(sketch_world(seed))
    s = res.summary()
    assert s['status'] == 'reached'
    assert s['replans'] >= 1
    assert s['walked_length'] >= s['first_cost'] - 1e-9


def test_a_scheduled_change_is_seen_and_replanned():
    # a corridor; at step 2 the world closes the cell ahead
    grid_known = [False] * 12
    w = ReplanWorld(12, 1, grid_known, list(grid_known), (0, 0), (0, 11),
                    sense_radius=2.5, connectivity=4,
                    heuristic='manhattan', schedule=[(2, [(0, 5, True)])])
    res = run_replan(w)
    assert res.status == 'no_path'
    assert [r.step for r in res.rounds] == [0, 3]
    assert res.walk == [(0, 0), (0, 1), (0, 2), (0, 3)]


def test_global_sensing_learns_every_change_at_once():
    known = [False] * 25
    truth = list(known)
    truth[12] = True
    w = ReplanWorld(5, 5, known, truth, (2, 0), (2, 4), sense_radius=None,
                    connectivity=4, heuristic='manhattan')
    res = run_replan(w)
    # sensed at the start: the first plan already avoids (2, 2)
    assert (2, 2) not in res.rounds[0].path
    assert res.summary()['replans'] == 0


def test_step_limit():
    w = sketch_world(0)
    w.max_steps = 3
    assert run_replan(w).status == 'step_limit'


@pytest.mark.parametrize('bad, match', [
    ({'sense_radius': 1.0}, 'sense_radius'),
    ({'start': (0, 1)}, 'blocked'),
    ({'goal': (9, 9)}, 'off the grid'),
    ({'schedule': [(2, []), (1, [])]}, 'increase'),
    ({'schedule': [(1, [(0, 0, True)])]}, 'start or the goal'),
    ({'max_steps': 0}, 'max_steps'),
])
def test_bad_worlds_are_refused(bad, match):
    known = [False, True, False, False, False, False, False, False, False]
    kw = {'width': 3, 'height': 3, 'known': known, 'truth': list(known),
          'start': (0, 0), 'goal': (2, 2), 'connectivity': 4,
          'heuristic': 'manhattan'}
    kw.update(bad)
    with pytest.raises(ReplanError, match=match):
        run_replan(ReplanWorld(**kw))


def test_the_cost_layer_is_honoured():
    cost = [0.0] * 9
    # entering the centre costs 1 + 2 x 400 / 252 = 4.17, so through it is
    # 5.17 and around it is 4 (at 252 the two would tie at 4)
    cost[4] = 400.0
    w = ReplanWorld(3, 3, [False] * 9, [False] * 9, (1, 0), (1, 2),
                    sense_radius=None, connectivity=4,
                    heuristic='manhattan', cost=cost)
    res = run_replan(w)
    assert (1, 1) not in res.rounds[0].path
    g = Grid(3, 3, [False] * 9, cost, connectivity=4)
    assert math.isclose(res.rounds[0].cost,
                        search(g, (1, 0), (1, 2), 'dijkstra').cost)
