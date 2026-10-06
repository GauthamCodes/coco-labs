#!/usr/bin/env python3
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
mission_search — the mission's side of Lab 4: which bay to look in next.

Pure, like ``mission_states``: no rclpy, no clock, no topics. The search
decision itself is ``coco_lab.regionsearch`` — the same code the browser
runs in Lab 4 and CI proves — and this module only holds the mission's
copy of its state: the belief, the regions searched, where the robot is,
and every observation, in order.

What it is built from, and what it is NOT
-----------------------------------------
- the four regions of ``coco_config.robot.TARGET_REGIONS`` (static world
  geometry — the bays exist whatever an episode puts in them);
- travel costs measured by coco_lab's own A* on the robot's OWN map, the
  Nav2 map it localises against;
- a detection probability (an assumption, labelled as one: see
  ``DEFAULT_DETECTION``);
- a UNIFORM prior.

Never from an episode manifest, a region map, ``lane_for_colour`` or the
simulator's truth. The prior is uniform on purpose: the frozen colour->bay
table is exactly what the TOLD mission used, and a prior built from it
would be telling the robot the answer by another name. The requested
colour does not enter this module at all, so the search order cannot
depend on it (``test_mission_search.py`` asserts all of the above).

The observation that ends a survey comes from ``/perception/status`` —
target_finder's ``found``/``seen`` and, on a find, its base_footprint point.
That line also carries ``lane=``, which is ``lane_for_colour`` (the told
lane, a FIXED-only field). Nothing here reads it.
"""

import os

from coco_config.robot import CLIMB_END_X, SPAWN_XY, TARGET_REGIONS

from coco_lab import regionsearch as rs

#: P(target_finder reports found | the target is on the platform surveyed).
#: ASSUMED, not measured: the phase's Gazebo matrix counts finds on the
#: target's bay, which is the measurement this stands in for until then.
#: It is below 1 on purpose -- the p03c episodes lost thin targets at
#: SEARCH_TARGET (2 of 10, not attributed) -- and the value changes the
#: arena order (coco_lab test_regionsearch: at 1.0 the order is
#: nearest-first).
DEFAULT_DETECTION = 0.9

#: Nav2's global costmap inflates by the robot radius; coco_lab's A* runs
#: on the same map inflated by the same amount.
ROBOT_RADIUS = 0.20

#: map = world + (2, 0): the map's origin is the spawn point.
WORLD_TO_MAP = (-SPAWN_XY[0], -SPAWN_XY[1])

#: Policies the mission accepts: the robot's own, or an order it is given
#: (a learner's, held fixed for a comparison).
MISSION_POLICIES = ('expected_cost', 'given')


def default_map_yaml():
    """Return the Nav2 map the stack localises against (installed share)."""
    from ament_index_python.packages import get_package_share_directory
    return os.path.join(get_package_share_directory('gazebo_models'),
                        'maps', 'coco_navigation.yaml')


def build_problem(map_yaml, detection=DEFAULT_DETECTION, travel=None):
    """
    Return the coco_lab problem over COCO's four bays.

    ``travel`` None measures it on ``map_yaml`` (about 2.5 s); a table can
    be passed instead, which is how the tests hold it fixed.
    """
    regions = rs.bay_regions(TARGET_REGIONS, CLIMB_END_X)
    if travel is None:
        from coco_lab.maps import load_nav2
        lab_map = load_nav2(map_yaml, 'coco_navigation')
        travel = rs.travel_costs(
            lab_map, rs.places_of(regions, SPAWN_XY),
            [r.id for r in regions], ROBOT_RADIUS, offset=WORLD_TO_MAP)
    return rs.bay_problem(regions, SPAWN_XY, travel, detection,
                          meta={'map': os.path.basename(str(map_yaml)),
                                'detection_is': 'assumed'})


def parse_order(text, problem):
    """
    Parse ``'bay_4,bay_1'`` to region indices; raise ValueError if bad.

    Every name must be a region, none twice. A partial order is allowed:
    a learner may choose to stop early, and that is what the challenge
    then scores.
    """
    names = [n.strip() for n in (text or '').split(',') if n.strip()]
    if not names:
        return ()
    if len(set(names)) != len(names):
        raise ValueError(f'search order repeats a region: {text!r}')
    try:
        return tuple(problem.index(n) for n in names)
    except rs.SearchError as exc:
        raise ValueError(str(exc)) from None


class SearchSession:
    """
    One mission's search: the belief, the bookkeeping, the observations.

    ``select`` asks coco_lab for the next region; ``observe`` records what
    the survey of the current region saw and updates the belief by Bayes'
    rule. Every observation is kept, in order, for the log and the Lab 4
    replay.
    """

    def __init__(self, problem, policy='expected_cost', given_order=()):
        if policy not in MISSION_POLICIES:
            raise ValueError(f'search policy must be one of '
                             f'{MISSION_POLICIES}, not {policy!r}')
        if policy == 'given' and not given_order:
            raise ValueError('a given search order is empty')
        problem.validate()
        self.problem = problem
        self.policy = policy
        self.given_order = tuple(given_order)
        self.belief = tuple(problem.prior)
        self.searched = ()
        self.location = problem.start
        self.current = None           # index of the region being surveyed
        self.order = []               # indices, in the order surveyed
        self.observations = []        # dicts, in order
        self.discovered = None        # index, once found
        self.selections = []          # (index, candidate costs) per select

    # ── decisions ────────────────────────────────────────────────────────
    def view(self):
        """Return what the policy may see: no truth, no colour."""
        return rs.SearchView(self.belief, self.searched, self.location,
                             self.given_order)

    def select(self):
        """Choose the next region and make it current; None when none left."""
        view = self.view()
        nxt = rs.choose(self.policy, self.problem, view)
        self.current = nxt
        if nxt is not None:
            self.selections.append(
                (nxt, rs.candidate_costs(self.problem, view)))
        return None if nxt is None else self.problem.ids[nxt]

    def remaining(self):
        """Return how many regions this policy would still survey."""
        if self.policy == 'given':
            return sum(1 for i in self.given_order if i not in self.searched)
        return len(self.view().remaining(self.problem.n))

    def observe(self, found, seen=(), point=None, stamp=None, lines=0):
        """
        Record the survey of the current region and update the belief.

        ``found`` is perception's verdict; ``seen`` the colours it saw;
        ``point`` the base_footprint (x, y, z) it reported on a find;
        ``lines`` how many fresh status lines the verdict rests on.
        """
        i = self.current
        if i is None:
            raise ValueError('observe() with no region being surveyed')
        d = self.problem.detection[i]
        self.order.append(i)
        self.observations.append({
            'region': self.problem.ids[i], 'found': bool(found),
            'seen': sorted(set(seen)), 'point': point, 'stamp': stamp,
            'lines': int(lines)})
        if found:
            self.belief = rs.update(self.belief, i, True, d)
            self.discovered = i
        else:
            if self.belief[i] * d < 1.0:
                self.belief = rs.update(self.belief, i, False, d)
            self.searched = self.searched + (i,)
        self.location = self.problem.ids[i]
        self.current = None if not found else i

    # ── reporting ────────────────────────────────────────────────────────
    def region_id(self):
        """Return the id of the region being surveyed, or None."""
        return None if self.current is None else self.problem.ids[self.current]

    def driven(self):
        """Return metres planned so far (derived from the travel table)."""
        total, at = 0.0, self.problem.start
        for i in self.order:
            total += self.problem.leg(at, i)
            at = self.problem.ids[i]
        return total

    def status_line(self):
        """
        Return ``/mission/search``'s payload: one key=value line.

        Same shape as every other status topic, so ``parse_kv`` reads it.
        No value contains a space.
        """
        ids = self.problem.ids

        def names(idx):
            return ','.join(ids[i] for i in idx) or '--'
        seen = self.observations[-1]['seen'] if self.observations else []
        return (
            f'mode=discover policy={self.policy} '
            f'regions={",".join(ids)} '
            f'order={names(self.order)} '
            f'current={self.region_id() or "--"} '
            f'searched={names(self.searched)} '
            f'belief={",".join(f"{p:.4f}" for p in self.belief)} '
            f'discovered='
            f'{"--" if self.discovered is None else ids[self.discovered]} '
            f'surveys={len(self.order)} '
            f'seen={",".join(seen) or "--"} '
            f'driven={self.driven():.2f} '
            f'detection={self.problem.detection[0]:.2f}')


#: What /mission/search says when the mission is the told one.
TOLD_LINE = 'mode=told'
