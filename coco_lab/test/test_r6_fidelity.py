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
R6.B1: the fidelity knobs -- LiDAR dropout, odometry presets, command latency, acceleration limits.

Each is a config input, deterministic and seeded, off unless set; off leaves every hash as it was
(the goldens in test_numerics_v3 / test_state_hash_v2 / test_golden_traces are the proof of that).
"""
import os

from coco_lab.arena import Arena, ArenaError, InputEvent, ODOM_PRESETS
from coco_lab.sketch import wrap
import pytest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
with open(os.path.join(REPO, 'worlds', 'coco_arena_v1.yaml'), encoding='utf-8') as _f:
    SPEC = yaml.safe_load(_f)


def run(arena, inputs, ticks):
    by = {}
    for e in inputs:
        by.setdefault(e.tick, []).append(e)
    return [arena.step(by.get(arena.tick, ())) for _ in range(ticks)]


def cfg(*pairs):
    return [InputEvent(0, 'config', choice=c) for c in pairs]


def test_off_is_the_arena_as_it_was_and_on_is_deterministic():
    """No knob set: the same hashes as before; set: the same run twice."""
    plain = [t.state_hash for t in run(Arena(SPEC, seed=3, hash_version=3),
                                       [InputEvent(0, 'teleop', linear=0.3, angular=0.2)], 30)]
    again = [t.state_hash for t in run(Arena(SPEC, seed=3, hash_version=3),
                                       [InputEvent(0, 'teleop', linear=0.3, angular=0.2)], 30)]
    assert plain == again
    knobs = cfg('arena.lidar_dropout=0.1', 'arena.cmd_latency=3', 'arena.linear_accel=0.5',
                'arena.odom_preset=stack_uncalibrated')
    a = [t.state_hash for t in run(Arena(SPEC, seed=3, hash_version=3),
                                   knobs + [InputEvent(0, 'teleop', linear=0.3, angular=0.2)], 30)]
    b = [t.state_hash for t in run(Arena(SPEC, seed=3, hash_version=3),
                                   knobs + [InputEvent(0, 'teleop', linear=0.3, angular=0.2)], 30)]
    assert a == b and a != plain


def test_lidar_dropout_removes_about_that_share_of_echoes():
    a, b = Arena(SPEC, seed=1), Arena(SPEC, seed=1)
    run(b, cfg('arena.lidar_dropout=0.2'), 1)
    run(a, [], 1)
    seen_a = sum(1 for z in a.ranges if z != float('inf'))
    lost = seen_a - sum(1 for z in b.ranges if z != float('inf'))
    assert 0.12 * seen_a < lost < 0.28 * seen_a          # 480 beams: 0.2 +- a wide margin


def test_command_latency_delays_the_wheels_and_stop_still_wins_at_once():
    a = Arena(SPEC, seed=1)
    ticks = run(a, cfg('arena.cmd_latency=5') + [InputEvent(0, 'teleop', linear=0.5)], 12)
    assert all(t.v == 0.0 for t in ticks[:5]) and ticks[7].v > 0.0
    run(a, [InputEvent(a.tick, 'stop')], 1)
    assert all(t.v == 0.0 for t in run(a, [], 8))          # nothing delayed survives STOP


def test_acceleration_limits_set_the_ramp():
    a, b = Arena(SPEC, seed=1), Arena(SPEC, seed=1)
    ta = run(a, [InputEvent(0, 'teleop', linear=0.5)], 3)
    tb = run(b, cfg('arena.linear_accel=0.5') + [InputEvent(0, 'teleop', linear=0.5)], 3)
    assert tb[0].v == pytest.approx(0.05) and tb[0].v < ta[0].v   # 0.5 m/s^2 x 0.1 s


def test_an_odometry_preset_overreports_turns_by_its_measured_factor():
    a = Arena(SPEC, seed=1)
    run(a, cfg('arena.odom_alphas=0,0,0,0', 'arena.odom_preset=stack_uncalibrated')
        + [InputEvent(0, 'teleop', angular=0.5)], 40)
    truth = wrap(a.pose[2] - a.start[2])
    assert a.odom[2] / truth == pytest.approx(ODOM_PRESETS['stack_uncalibrated'][1], rel=1e-6)


@pytest.mark.parametrize('bad', ['arena.lidar_dropout=1.0', 'arena.lidar_dropout=-0.1',
                                 'arena.cmd_latency=99', 'arena.linear_accel=0',
                                 'arena.odom_preset=perfect'])
def test_out_of_range_knobs_are_refused(bad):
    with pytest.raises(ArenaError):
        run(Arena(SPEC, seed=1), cfg(bad), 1)
