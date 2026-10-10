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

"""The ROS-to-event adapter on short committed fixture bags (M3.1, docs/v2/ADAPTER.md)."""

import ast
import collections
import hashlib
import json
import math
import os
from types import SimpleNamespace as NS

from coco_lab_ros import adapter as A
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
BAGS = os.path.join(HERE, 'fixtures', 'bags')
LAB5 = os.path.join(BAGS, 'lab5_crossing_dwb_1')
LAB4 = os.path.join(BAGS, 'lab4_a1_fixed_red')
LAB2 = os.path.join(BAGS, 'lab2_kidnap_recovery_k1')
RL = os.path.join(BAGS, 'lab2_rl_fidelity_s1')
CASE = {'id': 'fixture', 'title': 'a fixture', 'controller': 'DWB', 'world_to_map': [2, 0]}


def decode(data):
    from coco_schemas import mcap_read
    from coco_schemas.channels import message_class
    out = collections.defaultdict(list)
    for m in mcap_read.read_messages(data):
        out[m.channel].append((m.log_time, message_class(m.schema).FromString(m.data)))
    return out


def raw(bag, topic):
    return [(m, log) for _, m, log in A.read_bag(bag, [topic])]


@pytest.fixture(scope='module')
def lab5_full():
    data, summary = A.convert(LAB5, CASE, 'full', source_root=BAGS)
    return data, summary, decode(data)


# -- the conversion is pure -------------------------------------------------------

def test_the_adapter_runs_no_algorithm():
    tree = ast.parse(open(A.__file__).read())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or '').split('.')[0])
    assert mods <= {'argparse', 'bisect', 'hashlib', 'json', 'math', 'os', 'typing',
                    'rosbag2_py', 'rclpy', 'rosidl_runtime_py', 'yaml', 'coco_schemas',
                    'coco_lab_ros'}, mods
    # ...and of this package only safety.py's names of the recorded command topics
    lab = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
           and (n.module or '').startswith('coco_lab_ros')]
    assert [(n.module, [a.name for a in n.names]) for n in lab] == \
        [('coco_lab_ros.safety', ['RECORDED_COMMANDS'])]


# -- small helpers ---------------------------------------------------------------------

def test_parse_kv_reads_the_missions_status_line():
    kv = A.parse_kv('state=LOCALIZE prev=IDLE event=enter reason=-- result=--')
    assert kv == {'state': 'LOCALIZE', 'prev': 'IDLE', 'event': 'enter', 'reason': '',
                  'result': ''}


def test_the_sim_clock_interpolates_and_extends_at_slope_one():
    c = A.SimClock([(1_000_000_000, 10.0), (3_000_000_000, 11.0)])
    assert c(2_000_000_000) == pytest.approx(10.5)
    assert c(500_000_000) == pytest.approx(9.5) and c(4_000_000_000) == pytest.approx(12.0)
    with pytest.raises(ValueError):
        A.SimClock([])


def test_thinning_keeps_the_first_in_each_interval_and_text_on_change():
    th = A.Thin('summary')
    kept = [t for t in (0.0, 0.2, 0.49, 0.5, 0.7, 1.0) if th.keep('/scan', t)]
    assert kept == [0.0, 0.5, 1.0]
    assert A.Thin('full').keep('/scan', 0.0) and A.Thin('full').keep('/scan', 0.0)
    th = A.Thin('summary')
    assert [th.keep_text('/s', t, x) for t, x in ((0, 'a'), (0.1, 'a'), (0.2, 'b'), (1.3, 'b'))] \
        == [True, False, True, True]
    with pytest.raises(ValueError):
        A.Thin('everything')


def test_yaw_of_a_quarter_turn():
    q = NS(x=0.0, y=0.0, z=math.sin(math.pi / 4), w=math.cos(math.pi / 4))
    assert A.yaw(q) == pytest.approx(math.pi / 2)


# -- Lab 5: the full Nav2 picture ------------------------------------------------------

def test_lab5_truth_is_the_simulators_odometry_moved_to_the_map_frame(lab5_full):
    _, _, ch = lab5_full
    rows = [(t, x, y, th) for _, b in ch['coco.truth.pose.v1']
            for t, x, y, th in zip(b.t_world, b.x, b.y, b.theta)]
    odom = raw(LAB5, '/model/coco/odometry')
    assert len(rows) == len(odom) == 101
    for (t, x, y, th), (m, _) in zip(rows, odom):
        p = m.pose.pose
        assert t == A.stamp_s(m)
        assert (x, y) == (p.position.x + 2.0, p.position.y + 0.0)
        assert th == A.yaw(p.orientation)


def test_lab5_scans_come_back_beam_for_beam(lab5_full):
    _, _, ch = lab5_full
    scans = raw(LAB5, '/scan')
    batches = [b for _, b in ch['coco.sensor.scan.lidar.v1']]
    assert sum(len(b.count) for b in batches) == len(scans) == 20
    got = [r for b in batches for r in b.ranges]
    want = [r for m, _ in scans for r in m.ranges]
    assert len(got) == len(want)
    assert all((a == b) or (math.isinf(a) and math.isinf(b)) or (math.isnan(a) and math.isnan(b))
               for a, b in zip(got, want))
    assert batches[0].angle_min[0] == pytest.approx(scans[0][0].angle_min)


def test_lab5_amcl_is_the_estimate_and_the_robot_with_its_covariance(lab5_full):
    _, _, ch = lab5_full
    est = [b for _, b in ch['coco.estimate.pose.v1']]
    assert {b.estimator for b in est} == {'amcl'}
    amcl = raw(LAB5, '/amcl_pose')
    assert sum(len(b.x) for b in est) == len(amcl) == 4
    m = amcl[0][0]
    assert est[0].x[0] == m.pose.pose.position.x and est[0].cov_tt[0] == m.pose.covariance[35]
    assert sum(len(b.x) for _, b in ch['coco.robot.state.v1']) == 4


def test_lab5_plans_commands_and_the_local_plan_in_the_map_frame(lab5_full):
    _, _, ch = lab5_full
    paths = [b for _, b in ch['coco.plan.path.poses.v1']]
    assert collections.Counter(b.search_id for b in paths) == {1: 1, 2: 26}
    cmd = [b for _, b in ch['coco.control.local.command.v1']]
    nav = raw(LAB5, '/cmd_vel_nav')
    assert [v for b in cmd for v in b.v] == [m.twist.linear.x for m, _ in nav]
    cands = [b for _, b in ch['coco.control.local.candidates.v1']]
    assert len(cands) == 25 and all(b.controller_id == 'FollowPath/local_plan' for b in cands)
    local = raw(LAB5, '/local_plan')
    assert local[0][0].header.frame_id == 'odom'
    # the robot is on its local plan: the plan's first point is near the truth, in MAP coordinates
    truth = [(x, y) for _, b in ch['coco.truth.pose.v1'] for x, y in zip(b.x, b.y)]
    c0 = cands[-1]
    assert min(math.hypot(c0.traj_x[0] - x, c0.traj_y[0] - y) for x, y in truth) < 0.5
    hdr = [b for _, b in ch['coco.control.local.header.v1']]
    assert len(hdr) == 1 and hdr[0].kind == 'DWB' and hdr[0].evidence == 'STACK'


def test_lab5_actors_strings_and_metrics(lab5_full):
    _, _, ch = lab5_full
    actors = [b for _, b in ch['coco.truth.actors.v1']]
    assert sum(len(b.x) for b in actors) == 41
    ann = [b for _, b in ch['coco.annotation.text.v1']]
    sources = collections.Counter(s for b in ann for s in b.source)
    assert sources == {'/lab/status': 2, '/cmd_vel_arbiter/status': 6}
    names = collections.Counter(n for _, b in ch['coco.metrics.values.v1'] for n in b.name)
    assert names['wheels.cmd.v'] == names['wheels.cmd.w'] == 57


def test_lab5_manifest_cites_the_source_bag_by_checksum(lab5_full):
    data, summary, ch = lab5_full
    (_, m), = ch['coco.envelope.manifest.v1']
    assert m.evidence_class == A.EVIDENCE_STACK and m.tier == A.TIER_STACK
    spec = json.loads(m.spec)
    files = {f['name']: f for f in spec['source']['files']}
    mcap = [n for n in files if n.endswith('.mcap')][0]
    with open(os.path.join(LAB5, mcap), 'rb') as f:
        assert files[mcap]['sha256'] == hashlib.sha256(f.read()).hexdigest()
    assert spec['source']['bag'] == 'lab5_crossing_dwb_1'
    from coco_schemas import runid
    assert m.run_id == runid.run_id(m.spec, 0, [(A.ADAPTER, A.ADAPTER_VERSION), ('ros', 'jazzy')])
    assert {c.name for c in m.channels} >= {'coco.truth.pose.v1', 'coco.sensor.scan.lidar.v1'}


def test_records_are_in_log_time_order_and_the_file_is_reproducible(lab5_full):
    data, _, _ = lab5_full
    from coco_schemas import mcap_read
    times = [m.log_time for m in mcap_read.read_messages(data)]
    assert times == sorted(times)
    again, _ = A.convert(LAB5, CASE, 'full', source_root=BAGS)
    assert again == data


def test_the_golden_file_the_site_reads_is_this_conversion(lab5_full):
    # lab_web/test/casefile_adapter.test.ts decodes and repacks this file in TypeScript;
    # regenerate it with the adapter (not by hand) if the conversion changes on purpose
    data, _, _ = lab5_full
    golden = os.path.join(HERE, 'fixtures', 'golden', 'lab5_crossing_dwb_1.full.mcap')
    with open(golden, 'rb') as f:
        assert f.read() == data


def test_summary_detail_keeps_recorded_messages_at_lower_rates(lab5_full):
    _, _, full = lab5_full
    data, _ = A.convert(LAB5, CASE, 'summary', source_root=BAGS)
    ch = decode(data)
    n = {c: sum(len(getattr(b, 't_world', ())) for _, b in v) for c, v in ch.items()}
    assert n['coco.sensor.scan.lidar.v1'] <= 5 and n['coco.truth.pose.v1'] <= 21
    # every summary truth row is one of the full rows, not an interpolation
    full_rows = {(t, x) for _, b in full['coco.truth.pose.v1'] for t, x in zip(b.t_world, b.x)}
    assert {(t, x) for _, b in ch['coco.truth.pose.v1'] for t, x in zip(b.t_world, b.x)} \
        <= full_rows
    assert len(data) < len(A.convert(LAB5, CASE, 'full', source_root=BAGS)[0])


def test_a_window_keeps_only_its_messages():
    data, _ = A.convert(LAB5, CASE, 'full', window=(81.0, 81.5), source_root=BAGS)
    ch = decode(data)
    ts = [t for c, v in ch.items() if c != A.CH['manifest'] for _, b in v
          for t in getattr(b, 't_world', [])]
    assert ts and min(ts) >= 81.0 and max(ts) <= 81.5
    # ticks count from the window's start
    assert min(k for _, b in ch['coco.truth.pose.v1'] for k in b.tick) == 0


# -- Lab 4: wall-clock log time, the mission's status lines -------------------------------

def test_lab4_status_lines_become_transitions_on_simulation_time():
    data, summary = A.convert(LAB4, CASE, 'full', source_root=BAGS)
    ch = decode(data)
    tr = [b for _, b in ch['coco.mission.fsm.transition.v1']]
    states = [s for b in tr for s in b.to_state]
    assert states == ['IDLE', 'LOCALIZE', 'SELECT_SEARCH_REGION', 'NAVIGATE_TO_RAMP']
    froms = [s for b in tr for s in b.from_state]
    assert froms[1:] == states[:-1]
    # the bag was logged in wall time; t_world is the simulator's (the odometry's) clock
    t = [x for b in tr for x in b.t_world]
    truth = [x for _, b in ch['coco.truth.pose.v1'] for x in b.t_world]
    assert max(t) < 1e6 and min(truth) - 1.0 <= min(t) <= max(truth) + 1.0
    (_, hdr), = ch['coco.mission.fsm.header.v1']
    assert list(hdr.states) == states
    assert collections.Counter(s for _, b in ch['coco.annotation.text.v1'] for s in b.source) \
        == {'/mission/search': 7, '/mission/search_region': 2}
    assert summary['rows']['transition'] == 4


def test_a_log_window_cuts_by_bag_time_before_mapping_to_simulation_time():
    # cut after the second transition's log time: what the recorder caught later is gone
    times = [log for _, m, log in A.read_bag(LAB4, ['/mission/state'])
             if A.parse_kv(m.data).get('state') == 'SELECT_SEARCH_REGION']
    data, _ = A.convert(LAB4, CASE, 'full', log_window=(0, times[0]), source_root=BAGS)
    ch = decode(data)
    states = [s for _, b in ch['coco.mission.fsm.transition.v1'] for s in b.to_state]
    assert states == ['IDLE', 'LOCALIZE', 'SELECT_SEARCH_REGION']
    (_, m), = ch['coco.envelope.manifest.v1']
    assert json.loads(m.spec)['adapter']['log_window_ns'] == [0, times[0]]


# -- Lab 2: wheel odometry and robot_localization ------------------------------------------

def test_lab2_wheel_odometry_is_an_estimate_named_with_its_frame():
    data, _ = A.convert(LAB2, CASE, 'full', source_root=BAGS)
    ch = decode(data)
    est = collections.Counter(b.estimator for _, b in ch['coco.estimate.pose.v1']
                              for _ in b.x)
    assert sum(est.values()) == 151 and set(est) <= {'wheel_odometry@map', 'wheel_odometry@odom'}


def test_the_rl_bag_keeps_its_odom_frame_without_a_transform():
    data, _ = A.convert(RL, CASE, 'full', source_root=BAGS)
    ch = decode(data)
    est = [b for _, b in ch['coco.estimate.pose.v1']]
    assert {b.estimator for b in est} == {'robot_localization@odom'}
    assert sum(len(b.x) for b in est) == 50


def test_two_bags_on_one_clock_merge_in_time_order_and_both_are_cited():
    # a session and a replay of it (the robot_localization tour): one Case File
    data, summary = A.convert([LAB2, RL], CASE, 'full', source_root=BAGS)
    ch = decode(data)
    est = collections.Counter(b.estimator for _, b in ch['coco.estimate.pose.v1'] for _ in b.x)
    assert est['robot_localization@odom'] == 50 and sum(est.values()) == 50 + 151
    (_, m), = ch['coco.envelope.manifest.v1']
    spec = json.loads(m.spec)
    assert [x['bag'] for x in spec['source']['bags']] == ['lab2_kidnap_recovery_k1',
                                                          'lab2_rl_fidelity_s1']
    assert len(summary['source_files']) == 4
    with pytest.raises(ValueError, match='one bag'):
        A.convert([LAB2, RL], CASE, 'full', log_window=(0, 1), source_root=BAGS)


def test_a_run_without_world_to_map_is_refused():
    with pytest.raises(ValueError, match='world_to_map'):
        A.convert(RL, {'id': 'x'}, 'full', source_root=BAGS)
