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
Lab 5 (Move): everything a controller comparison holds fixed.

The controller overlay, the scenarios, the frozen paths and the actors.
"""

import hashlib
import json
import math
import os
import threading
import time

from coco_lab import movemetrics as mm
from coco_lab_ros import actors, params, safety
from coco_lab_ros.planner_node import load_path_file
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
MISSION = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')
MOVE = os.path.join(PKG, 'config', 'nav2_move_overlay.yaml')
SCENARIOS = os.path.join(PKG, 'config', 'lab5_scenarios.json')
PATHS = os.path.join(PKG, 'config', 'lab5_paths')
WORLD = os.path.join(REPO, 'gazebo_models', 'config',
                     'navigation_world.json')
MISSION_SHA256 = \
    '06c308aff78d4e7327212bbca280f62be7a7baef604ae41676e886b72301db8c'
DOMAIN = 88


def merged(tmp_path):
    out = tmp_path / 'merged.yaml'
    info = params.merge_files(MISSION, MOVE, str(out))
    return info, params.load(str(out))


def world():
    with open(WORLD) as f:
        return json.load(f)


# -- the controller overlay ----------------------------------------------------

def test_the_mission_file_is_untouched():
    with open(MISSION, 'rb') as f:
        assert hashlib.sha256(f.read()).hexdigest() == MISSION_SHA256


def test_the_overlay_adds_two_controllers_and_changes_nothing_else(tmp_path):
    info, m = merged(tmp_path)
    pre = 'controller_server.ros__parameters.'
    for k in info['differing_keys']:
        assert k == pre + 'controller_plugins' or \
            k.startswith(pre + 'MPPI.') or k.startswith(pre + 'RPP.'), k
    cs = m['controller_server']['ros__parameters']
    base = params.load(MISSION)['controller_server']['ros__parameters']
    assert cs['controller_plugins'] == ['FollowPath', 'MPPI', 'RPP']
    assert cs['FollowPath'] == base['FollowPath']        # DWB untouched
    assert cs['FollowPath']['plugin'] == 'dwb_core::DWBLocalPlanner'
    assert cs['FollowPath']['debug_trajectory_details'] is True
    assert cs['MPPI']['plugin'] == 'nav2_mppi_controller::MPPIController'
    assert cs['RPP']['plugin'] == ('nav2_regulated_pure_pursuit_controller'
                                   '::RegulatedPurePursuitController')
    for k in ('controller_frequency', 'goal_checker', 'progress_checker'):
        assert cs[k] == base[k]


def test_no_controller_gets_a_faster_or_more_agile_robot(tmp_path):
    _, m = merged(tmp_path)
    cs = m['controller_server']['ros__parameters']
    dwb, mppi, rpp = cs['FollowPath'], cs['MPPI'], cs['RPP']
    assert dwb['max_vel_x'] == mppi['vx_max'] == rpp['desired_linear_vel']
    assert dwb['min_vel_x'] == mppi['vx_min'] == 0.0
    assert rpp['allow_reversing'] is False
    assert dwb['max_vel_theta'] == mppi['wz_max'] == \
        rpp['rotate_to_heading_angular_vel']
    assert dwb['acc_lim_x'] == mppi['ax_max']
    assert dwb['decel_lim_x'] == mppi['ax_min']
    assert dwb['acc_lim_theta'] == mppi['az_max'] == rpp['max_angular_accel']
    # MPPI's model step is the shared controller period
    assert mppi['model_dt'] == pytest.approx(1.0 / cs['controller_frequency'])
    assert mppi['visualize'] is True


# -- scenarios and frozen paths ------------------------------------------------

def scenarios():
    return actors.load_scenarios(SCENARIOS)


def test_the_scenarios_are_the_five_lab5_names():
    assert sorted(scenarios()) == ['crossing', 'mislocalised', 'oncoming',
                                   'parked', 'static_room']


def test_the_parked_person_never_moves_and_is_within_marking_range():
    a = scenarios()['parked']['actors'][0]
    # the trigger cannot fire anywhere on the map (y >= -8.9)
    assert a['trigger'] == {'axis': 'y', 'op': '<', 'value': -100.0}
    assert actors.actor_pose(a, None, 1e6) == actors.actor_pose(a, None, 0)
    x, y, _ = actors.actor_pose(a, None, 0)
    # the lidar sits at (-0.09, +0.10) from the robot at (0, 0, yaw 0)
    assert math.hypot(x + 0.09, y - 0.10) < 2.5     # obstacle_max_range
    assert abs(math.atan2(y - 0.10, x + 0.09)) < 4.1888 / 2   # in view


@pytest.mark.parametrize('sid', ['crossing', 'mislocalised', 'oncoming',
                                 'parked', 'static_room'])
def test_each_scenario_names_a_frozen_path_that_matches_it(sid):
    sc = scenarios()[sid]
    poses, frame, sha = load_path_file(os.path.join(PATHS, sc['path']))
    assert frame == 'map'
    assert sc['start'] == [0.0, 0.0, 0.0]            # the spawn
    assert math.hypot(poses[0][0], poses[0][1]) < 1e-3
    assert math.hypot(poses[-1][0] - sc['goal'][0],
                      poses[-1][1] - sc['goal'][1]) < 1e-3
    assert poses[-1][2] == pytest.approx(sc['goal'][2], abs=1e-3)


def test_the_paths_share_one_file_where_the_scenarios_share_a_route():
    sc = scenarios()
    assert sc['crossing']['path'] == sc['oncoming']['path'] == \
        sc['mislocalised']['path']


@pytest.mark.parametrize('name', ['lab5_path_apron.json',
                                  'lab5_path_room.json'])
def test_every_path_pose_clears_the_arena_boxes(name):
    poses, _, _ = load_path_file(os.path.join(PATHS, name))
    w = world()
    boxes = mm.boxes_in_map(w['boxes'], w['world_to_map'])
    gt = [(i, x, y, yaw) for i, (x, y, yaw) in enumerate(poses)]
    c = mm.clearance(gt, boxes)
    assert c['static']['min_m'] > 0.2, c       # the footprint, 0.2 m free


def test_the_path_files_carry_their_provenance():
    for name in os.listdir(PATHS):
        with open(os.path.join(PATHS, name)) as f:
            d = json.load(f)
        assert d['schema'] == 'coco_lab_ros.lab5_path'
        assert d['planner_id'] == 'GridBased'
        assert d['costmap_sha256'].startswith('sha256:')


# -- actors --------------------------------------------------------------------

def test_the_apron_bounds_are_derived_from_the_world():
    w = world()
    dx, dy = w['world_to_map']
    x0, x1 = actors.APRON['x']
    y0, y1 = actors.APRON['y']
    inside, west, east = [], [], []
    for b in w['boxes']:
        cx, cy = b['pose'][0] + dx, b['pose'][1] + dy
        hx, hy = b['size'][0] / 2, b['size'][1] / 2
        if cx + hx > x0 + 1e-9 and cx - hx < x1 - 1e-9 and \
                cy + hy > y0 + 1e-9 and cy - hy < y1 - 1e-9:
            inside.append(b['name'])
        if abs((cx + hx) - x0) < 1e-6:
            west.append(b['name'])
        if abs((cx - hx) - x1) < 1e-6:
            east.append(b['name'])
    assert inside == []                          # nothing on the apron
    assert west and all('west_corridor_landmark' in n for n in west)
    assert east and all('approach' in n for n in east)


@pytest.mark.parametrize('bad, match', [
    ({'waypoints': [[3.0, 0.0], [0.0, 0.0]]}, 'off the apron'),
    ({'waypoints': [[0.0, 0.0]]}, 'two waypoints'),
    ({'waypoints': [[0.0, 0.0], [0.0, 0.0]]}, 'repeated'),
    ({'speed': 0.5}, 'speed'),
    ({'speed': 0.1}, 'speed'),
    ({'trigger': {'axis': 'z', 'op': '<', 'value': 0}}, 'trigger'),
    ({'id': ''}, 'id'),
])
def test_actors_off_the_design_are_refused(bad, match):
    a = {'id': 'a', 'waypoints': [[0.0, -1.0], [0.0, -2.0]], 'speed': 0.25,
         'trigger': {'axis': 'y', 'op': '<', 'value': 0.0}}
    a.update(bad)
    with pytest.raises(actors.ScenarioError, match=match):
        actors.validate_actor(a)


def test_an_actor_holds_then_walks_then_parks():
    a = {'id': 'a', 'waypoints': [[-1.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
         'speed': 0.25, 'trigger': {'axis': 'y', 'op': '<', 'value': -1}}
    assert actors.actor_pose(a, None, 100.0) == (-1.0, 0.0, 0.0)
    assert actors.actor_pose(a, 10.0, 9.0) == (-1.0, 0.0, 0.0)
    x, y, yaw = actors.actor_pose(a, 10.0, 14.0)            # 1 m along
    assert (x, y, yaw) == pytest.approx((0.0, 0.0, 0.0))
    x, y, yaw = actors.actor_pose(a, 10.0, 20.0)            # 2.5 m along
    assert (x, y, yaw) == pytest.approx((1.0, 0.5, math.pi / 2))
    assert actors.actor_pose(a, 10.0, 99.0) == pytest.approx(
        (1.0, 1.0, math.pi / 2))
    assert actors.walk_duration(a) == pytest.approx(12.0)


def test_the_schedule_is_a_pure_function_of_the_trigger_time():
    a = scenarios()['crossing']['actors'][0]
    assert actors.schedule(a, 50.0, 70.0) == actors.schedule(a, 50.0, 70.0)
    s = actors.schedule(a, 50.0, 70.0, dt=0.05)
    assert len(s) == 401 and s[0][0] == 50.0
    # shifting the trigger shifts the schedule and nothing else
    s2 = actors.schedule(a, 60.0, 80.0, dt=0.05)
    assert [r[1:] for r in s] == [r[1:] for r in s2]


def test_triggers_read_the_robot_position():
    t = {'axis': 'y', 'op': '<', 'value': -1.8}
    assert not actors.triggered(t, (0.0, -1.7))
    assert actors.triggered(t, (0.0, -1.9))
    assert actors.triggered({'axis': 'x', 'op': '>', 'value': 1}, (2, 0))


def test_the_actor_has_no_collision_geometry():
    sdf = actors.model_sdf('lab_actor_0')
    assert '<visual' in sdf and '<collision' not in sdf
    assert '<gravity>false</gravity>' in sdf
    assert f'<radius>{actors.RADIUS:.4f}</radius>' in sdf
    assert f'<length>{actors.HEIGHT:.4f}</length>' in sdf


def test_the_actor_straddles_the_scan_plane_and_is_detectable():
    # M7_DESIGN 2.6 (derived): the lidar sits at 0.2135 m; its angular
    # step is 4.1888 / 479 rad, so a width w gives >= 4 returns out to
    # w / (4 step). For 0.30 m that is 8.58 m -- past the costmaps' 2.5 m
    # marking range, which is where the controllers can react to it. (The
    # design's "whole apron" claim was for its 8.38 m apron; this apron is
    # 17.8 m long, so the far end is NOT covered and nothing claims it.)
    assert actors.HEIGHT > 0.2135
    step = 4.1888 / 479
    reach = 2 * actors.RADIUS / (4 * step)
    assert reach == pytest.approx(8.576, abs=0.001)
    assert reach > 2.5


class FakeGz:
    """Records what the node asks Gazebo to do."""

    def __init__(self):
        self.created, self.poses = [], []

    def create(self, sdf, x=0.0, y=0.0):
        self.created.append((sdf, x, y))
        return True

    def set_pose(self, name, x, y, yaw):
        self.poses.append((name, x, y, yaw))
        return True


def test_the_actor_node_publishes_only_its_record_and_moves_on_trigger():
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.parameter import Parameter
    from std_msgs.msg import String
    from coco_lab_ros.actor_node import LabActors

    ctx = rclpy.Context()
    rclpy.init(context=ctx, domain_id=DOMAIN)
    gz = FakeGz()
    node = LabActors(gz=gz, context=ctx, parameter_overrides=[
        Parameter('scenarios_file', Parameter.Type.STRING, SCENARIOS),
        Parameter('scenario', Parameter.Type.STRING, 'crossing')])
    fake = rclpy.create_node('fake_sim', context=ctx)
    odom = fake.create_publisher(Odometry, '/model/coco/odometry', 10)
    lines = []
    fake.create_subscription(String, '/lab/actors',
                             lambda m: lines.append(json.loads(m.data)), 50)
    ex = MultiThreadedExecutor(num_threads=3, context=ctx)
    ex.add_node(node)
    ex.add_node(fake)
    threading.Thread(target=ex.spin, daemon=True).start()
    try:
        def at(y_map):
            m = Odometry()
            m.pose.pose.position.x = -2.0          # world = map - (2, 0)
            m.pose.pose.position.y = y_map
            odom.publish(m)
        for _ in range(10):
            at(-1.0)
            time.sleep(0.1)
        assert node.t_trigger['actor_0'] is None
        for _ in range(10):
            at(-2.0)
            time.sleep(0.1)
        assert node.t_trigger['actor_0'] is not None
        pubs = node.get_publisher_names_and_types_by_node('lab_actors', '/')
        assert safety.violations(pubs, safety.ACTOR_TOPICS) == []
        assert {t for t, _ in pubs} - set(safety.INFRASTRUCTURE_TOPICS) == \
            {'/lab/actors'}
        assert len(gz.created) == 1 and '<collision' not in gz.created[0][0]
        # spawned at its first waypoint, in the WORLD frame
        assert gz.created[0][1:] == pytest.approx((-1.5 - 2.0, -4.5))
        assert gz.poses and all(p[0] == 'lab_actor_0' for p in gz.poses)
        assert lines and lines[-1]['trigger']['actor_0'] is not None
    finally:
        ex.shutdown()
        node.destroy_node()
        fake.destroy_node()
        rclpy.shutdown(context=ctx)


# -- the launch file's overlay choice -------------------------------------------

def test_lab_stack_knows_both_overlays_and_refuses_others():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'lab_stack', os.path.join(PKG, 'launch', 'lab_stack.launch.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.OVERLAYS == ('nav2_lab_overlay.yaml', 'nav2_move_overlay.yaml')
    for name in mod.OVERLAYS:
        assert os.path.exists(os.path.join(PKG, 'config', name))
    from launch import LaunchContext
    ctx = LaunchContext()
    ctx.launch_configurations['params_file'] = ''
    ctx.launch_configurations['overlay'] = 'nav2_params.yaml'
    with pytest.raises(RuntimeError, match='overlay'):
        mod.merged_params(ctx)
