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
Independent, bounded Compare runs using the existing control/localise model.

Every arm shares World Spec, seed, start, goal and non-compared settings.
Only the declared controller/filter differs. No live Arena state is used.
"""
import copy
from dataclasses import replace
import math
from time import perf_counter

from . import loc_arena, move_arena  # noqa: F401 -- register reference subsystems
from .arena import Arena, InputEvent
from .costmap import build_layers, InflationParams, scan_obstacle_cells
from .grid import Grid

FAMILIES = {'control': ('dwa', 'rpp', 'mppi'),
            'localise': ('mcl', 'mcl_augmented', 'ekf')}


class LoopComparison:
    """Step two or four independent arms in lockstep, yielding real outputs."""

    def __init__(self, spec, request):
        """Validate the bounded experiment before constructing its arms."""
        self.family = request['family']
        self.names = request['names']
        self.steps = request.get('steps', 200)
        self.goal = request['goal']
        if (self.family not in FAMILIES or len(self.names) not in (2, 4) or
                any(name not in FAMILIES[self.family] for name in self.names)):
            raise ValueError('unsupported Compare family or arms')
        if type(self.steps) is not int or not 1 <= self.steps <= 200:
            raise ValueError('Compare loop window is 1..200 ticks')
        if len(self.goal) != 2 or not all(math.isfinite(v) for v in self.goal):
            raise ValueError('finite shared goal required')
        self.params = InflationParams(**request['inflation'])
        self.tick = 0
        self.kidnap_tick = min(50, max(1, self.steps // 3))
        self.arms, self.sensors = [], []
        self.distances, self.clearances, self.times = [], [], []
        for name in self.names:
            spec_copy = copy.deepcopy(spec)
            sensor = {}

            def capture(channel, tick, columns, scalars, sensor=sensor):
                if columns is None:
                    return
                if channel == 'coco.localise.particles.set.v1':
                    sensor['particles'] = [list(columns['x']), list(columns['y'])]
                elif channel == 'coco.control.local.candidates.v1':
                    sensor['candidates'] = columns
                elif channel == 'coco.control.local.command.v1':
                    candidates = sensor.get('candidates')
                    chosen = list(columns['chosen'])
                    if candidates and chosen and chosen[-1] >= 0:
                        ids = list(candidates['candidate'])
                        if chosen[-1] in ids:
                            i = ids.index(chosen[-1])
                            offset = candidates['traj_offset'][i]
                            end = offset + candidates['traj_len'][i]
                            sensor['chosen'] = [list(candidates['traj_x'][offset:end]),
                                                list(candidates['traj_y'][offset:end])]
            arm = Arena(spec_copy, seed=1, on_family=capture, hash_version=2)
            if arm.lab_map.cell_at(*self.goal) is None:
                raise ValueError('goal is outside the existing arena')
            self.arms.append(arm)
            self.sensors.append(sensor)
            self.distances.append(0.0)
            self.clearances.append(math.inf)
            self.times.append(0.0)
        m = self.arms[0].lab_map
        first = self.arms[0]
        hits = scan_obstacle_cells(m, first.belief(), first.ranges, first.angles,
                                   first.lidar.mount, first.lidar.range_min,
                                   first.lidar.range_max)
        self.layers = build_layers(m.width, m.height, m.resolution,
                                   [v != 0 for v in m.occupancy], hits,
                                   params=self.params)
        self.grid = Grid(m.width, m.height,
                         blocked=[v >= 253 for v in self.layers.combined],
                         cost=self.layers.combined, connectivity=8)

    def advance(self):
        """One common simulation tick; return records for every pane."""
        if self.tick >= self.steps:
            raise ValueError('Compare window is complete')
        rows = []
        arms = zip(self.arms, self.names, self.sensors)
        for i, (arm, name, sensor) in enumerate(arms):
            started = perf_counter()
            events = []
            if self.tick == 0:
                if self.family == 'control':
                    choices = ['move.controller=' + name]
                else:
                    injection = 'augmented' if name == 'mcl_augmented' else 'none'
                    filter_name = 'mcl' if name.startswith('mcl') else 'ekf'
                    choices = ['localise.mcl.particles=60',
                               'localise.mcl.beams=12', 'localise.ekf.beams=12',
                               'localise.mcl.injection=' + injection,
                               'localise.filter=' + filter_name]
                events = [InputEvent(arm.tick, 'config', choice=v) for v in choices]
            if self.family == 'control' and self.tick == 1:
                move = arm.subsystems['move']
                move.window_params = replace(
                    move.window_params,
                    robot_radius=self.params.robot_radius / math.cos(math.pi / 16),
                    footprint_padding=0,
                    inflation_radius=self.params.inflation_radius,
                    cost_scaling_factor=self.params.cost_scaling_factor)
                arm.grid = self.grid
                events.append(InputEvent(arm.tick, 'goal', x=self.goal[0], y=self.goal[1]))
            if self.family == 'localise':
                if self.tick == self.kidnap_tick:
                    events.append(InputEvent(arm.tick, 'kidnap', x=self.goal[0], y=self.goal[1]))
                events.append(InputEvent(arm.tick, 'teleop',
                                         linear=.2 if self.tick < self.kidnap_tick else 0,
                                         angular=.08 if self.tick < self.kidnap_tick else 0))
            before = arm.pose
            tick = arm.step(events)
            self.times[i] += (perf_counter() - started) * 1000
            if not (self.family == 'localise' and self.tick == self.kidnap_tick):
                self.distances[i] += math.hypot(tick.pose[0] - before[0],
                                                tick.pose[1] - before[1])
            clearance = arm.smap.clearance(*tick.pose[:2]) - self.params.robot_radius
            self.clearances[i] = min(self.clearances[i], clearance)
            belief = arm.belief()
            error = math.hypot(belief[0] - tick.pose[0], belief[1] - tick.pose[1])
            if self.family == 'control':
                status = arm.subsystems['move'].outcome
                success = status == 'succeeded'
            else:
                success = error <= .5
                status = 'localized' if success else 'not_localized'
            rows.append({'pose': list(belief), 'truth': list(tick.pose),
                         'particles': sensor.get('particles'), 'chosen': sensor.get('chosen'),
                         'hash': tick.state_hash, 'tick': self.tick,
                         'summary': {'expansions': None, 'path_length_m': self.distances[i],
                                     'path_cost': None, 'minimum_clearance_m': self.clearances[i],
                                     'compute_ms': self.times[i], 'pose_error_m': error,
                                     'success': success},
                         'status': status or 'window_incomplete'})
        self.tick += 1
        return rows
