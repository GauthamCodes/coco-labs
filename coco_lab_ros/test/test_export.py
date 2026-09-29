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
lab_export on a real rosbag2 file written here.

The bag holds the lab node's own messages from a fake-FollowPath run
(status lines, trace, snapshot, plan) plus synthetic ground truth and AMCL
along the plan. Wheel commands are deliberately NOT recorded: the bundle
must list ``cmd`` as missing, not zero-fill it (plan F-7).
"""

import gzip
import json
import math

from coco_lab import bundle
from coco_lab_ros import export
import pytest
from test_planner_node import costmap_msg, run_planner


def write_bag(path, snap, statuses, trace_gz, plan_path, t0):
    import rosbag2_py
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    from rclpy.serialization import serialize_message
    from std_msgs.msg import String, UInt8MultiArray
    import array

    w = rosbag2_py.SequentialWriter()
    w.open(rosbag2_py.StorageOptions(uri=str(path), storage_id='mcap'),
           rosbag2_py.ConverterOptions('', ''))
    topics = {'/lab/status': 'std_msgs/msg/String',
              '/lab/trace_gz': 'std_msgs/msg/UInt8MultiArray',
              '/lab/costmap_snapshot': 'nav2_msgs/msg/Costmap',
              '/lab/plan': 'nav_msgs/msg/Path',
              '/model/coco/odometry': 'nav_msgs/msg/Odometry',
              '/amcl_pose': 'geometry_msgs/msg/PoseWithCovarianceStamped'}
    for i, (name, typ) in enumerate(topics.items()):
        w.create_topic(rosbag2_py.TopicMetadata(
            id=i, name=name, type=typ, serialization_format='cdr'))

    def put(topic, msg, t):
        w.write(topic, serialize_message(msg), int(t * 1e9))
    put('/lab/costmap_snapshot', costmap_msg(snap), t0)
    put('/lab/trace_gz', UInt8MultiArray(data=array.array('B', trace_gz)),
        t0)
    put('/lab/plan', plan_path, t0)
    for i, s in enumerate(statuses):
        put('/lab/status', String(data=json.dumps(s)), t0 + 0.01 * i)
    poses = plan_path.poses
    acc = next(s for s in statuses if s['phase'] == 'following')['t_sim']
    end = next(s for s in statuses if s['phase'] == 'succeeded')['t_sim']
    for i, p in enumerate(poses):
        t = acc + (end - acc) * i / max(1, len(poses) - 1)
        o = Odometry()
        o.header.stamp.sec = int(t)
        o.header.stamp.nanosec = int((t - int(t)) * 1e9)
        # ground truth is WORLD frame: map minus the (2, 0) offset
        o.pose.pose.position.x = p.pose.position.x - 2.0
        o.pose.pose.position.y = p.pose.position.y + 0.01
        o.pose.pose.orientation.w = 1.0
        put('/model/coco/odometry', o, t)
        if i % 5 == 0:
            a = PoseWithCovarianceStamped()
            a.header = o.header
            a.pose.pose.position.x = p.pose.position.x + 0.03
            a.pose.pose.position.y = p.pose.position.y
            a.pose.pose.orientation.w = 1.0
            put('/amcl_pose', a, t)
    if hasattr(w, 'close'):         # otherwise it closes when collected
        w.close()


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('exp')
    plan_dir = tmp / 'plan'
    snap, outcome, goals, statuses, traces = run_planner(plan_dir, (36, 26))
    assert outcome['phase'] == 'succeeded'
    bag = tmp / 'bag'
    write_bag(bag, snap, statuses, traces[-1], goals[0].path,
              t0=statuses[0]['t_sim'])
    out = tmp / 'bundle'
    m = export.export(str(bag), str(plan_dir), str(out), 'test-run')
    return m, out, snap, statuses, traces


def test_the_bundle_is_1_1_loads_and_lists_the_missing_stream(exported):
    m, out, snap, _, _ = exported
    b = bundle.load_bundle(str(out))
    assert b.version == '1.1'
    assert b.provenance['source_kind'] == 'recorded-run'
    assert b.provenance['rosbag']['sha256'] == m['bag']['sha256']
    assert b.recording['missing'] == ['cmd']
    assert sorted(b.streams) == ['amcl', 'gt', 'plan']
    assert m['streams_missing'] == ['cmd']
    assert b.lab_map.content_hash() == snap.to_labmap().content_hash()
    with pytest.raises(bundle.BundleError):
        bundle.replay(b)


def test_the_bag_and_the_node_agree(exported):
    m, _, _, _, traces = exported
    c = m['consistency']
    assert c == {'trace_sha256_matches_status': True,
                 'snapshot_hash_matches_status': True,
                 'glass_box_trace_equal': True,
                 'glass_box_map_equal': True}
    assert json.loads(gzip.decompress(traces[-1]))['header']['algorithm'] \
        == 'astar'


def test_the_metrics(exported):
    m, _, _, _, _ = exported
    assert m['accepted'] and m['result']['phase'] == 'succeeded'
    # GT was placed 0.01 m off the plan, in the WORLD frame: the export
    # must have applied world_to_map, or this would be ~2 m.
    assert m['tracking_error_m']['max'] == pytest.approx(0.01, abs=1e-6)
    assert m['belief_gap_m']['mean'] == pytest.approx(
        math.hypot(0.03, 0.01), abs=1e-6)
    assert m['endpoint_error_m'] == pytest.approx(0.01, abs=1e-6)
    assert m['recoveries_total'] == 0
    assert m['recovery_topics_recorded'] == []
    assert m['bundle']['loads_and_validates'] is True


def test_dir_hash_is_order_and_time_independent(tmp_path):
    a = tmp_path / 'a'
    a.mkdir()
    (a / 'x').write_bytes(b'1')
    (a / 'y').write_bytes(b'2')
    h1, size = export.dir_sha256(str(a))
    (a / 'x').touch()
    assert export.dir_sha256(str(a)) == (h1, size) and size == 2
    (a / 'y').write_bytes(b'3')
    assert export.dir_sha256(str(a))[0] != h1
