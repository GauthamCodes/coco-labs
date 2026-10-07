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
The lab never becomes a velocity publisher (COCO Lab platform rule 3).

Checked four ways, because each alone can be fooled:

1. the forbidden-topic list is the arbiter's OWN input list, read from
   ``cmd_vel_arbiter.py`` and ``arbiter.launch.py`` by AST, so it cannot
   drift from what the arbiter actually subscribes to;
2. no coco_lab_ros module imports ``Twist``/``TwistStamped``, and every
   ``create_publisher`` in the package names a declared lab topic;
3. a constructed ``lab_planner`` node's live publisher list holds only
   the lab topics (on a private ROS domain);
4. the checker itself fails on a bad publisher list.

And the layering: coco_lab never imports coco_lab_ros, and the pure
coco_lab_ros modules import with every ROS module poisoned.
"""

import ast
import builtins
import importlib
import os
import sys

from coco_lab_ros import safety
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
SRC = os.path.join(PKG, 'coco_lab_ros')
ARBITER = os.path.join(REPO, 'custom_teleop', 'custom_teleop',
                       'cmd_vel_arbiter.py')
ARBITER_LAUNCH = os.path.join(REPO, 'custom_teleop', 'launch',
                              'arbiter.launch.py')
PURE = ('coco_lab_ros', 'coco_lab_ros.costmap', 'coco_lab_ros.planning',
        'coco_lab_ros.metrics', 'coco_lab_ros.pathing',
        'coco_lab_ros.params', 'coco_lab_ros.safety')
BANNED = ('rclpy', 'rosidl_runtime_py', 'rmw', 'nav2_msgs', 'nav_msgs',
          'geometry_msgs', 'std_msgs', 'tf2_ros', 'rosbag2_py')


def sources():
    for name in sorted(os.listdir(SRC)):
        if name.endswith('.py'):
            path = os.path.join(SRC, name)
            with open(path, encoding='utf-8') as f:
                yield name, ast.parse(f.read(), path)


def declared_defaults(path):
    """Return ``{parameter: default}`` of every declare_parameter call."""
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    out = {}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, 'attr', '') == 'declare_parameter'
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)):
            try:
                out[node.args[0].value] = ast.literal_eval(node.args[1])
            except ValueError:
                out[node.args[0].value] = node.args[1]
    return out


def test_the_forbidden_inputs_are_the_arbiters_own():
    d = declared_defaults(ARBITER)
    with open(ARBITER_LAUNCH, encoding='utf-8') as f:
        launch = f.read()
    # arbiter.launch.py overrides nav_topic; everything else is default.
    assert "'nav_topic': '/cmd_vel_gated'" in launch
    inputs = {d['teleop_topic'], '/cmd_vel_gated', d['rl_topic'],
              d['approach_topic'], d['mode_topic']}
    assert inputs == set(safety.ARBITER_INPUTS)
    assert d['output_topic'] == safety.WHEEL_TOPIC


def test_no_module_imports_a_velocity_type():
    for name, tree in sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name not in ('Twist', 'TwistStamped'), name
            if isinstance(node, ast.Attribute):
                assert node.attr not in ('Twist', 'TwistStamped'), name


#: Each publishing module and the ONLY topics it may publish (Phase 6
#: added the actor driver, with its own allowlist).
PUBLISHERS = {'planner_node.py': safety.LAB_TOPICS,
              'actor_node.py': safety.ACTOR_TOPICS}


def test_every_publisher_names_a_lab_topic():
    found = {}
    for name, tree in sources():
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, 'attr', '') == 'create_publisher'):
                topic = node.args[1]
                assert isinstance(topic, ast.Constant), \
                    f'{name}: a publisher topic must be a literal'
                assert name in PUBLISHERS, f'{name} publishes undeclared'
                assert topic.value in PUBLISHERS[name], (name, topic.value)
                found.setdefault(name, []).append(topic.value)
    assert {n: sorted(t) for n, t in found.items()} == \
        {n: sorted(t) for n, t in PUBLISHERS.items()}
    assert not set(safety.ACTOR_TOPICS) & set(safety.FORBIDDEN_TOPICS)


def test_no_forbidden_topic_is_named_outside_safety():
    for name, tree in sources():
        if name == 'safety.py':
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value not in safety.FORBIDDEN_TOPICS, \
                    (name, node.value)


def test_the_checker_can_fail():
    assert safety.violations([('/lab/plan', ['nav_msgs/msg/Path'])]) == []
    assert safety.violations(
        [('/cmd_vel_gated', ['geometry_msgs/msg/Twist'])])
    assert safety.violations(
        [('/anything', ['geometry_msgs/msg/TwistStamped'])])
    assert safety.violations([('/mission/mode', ['std_msgs/msg/String'])])
    assert safety.violations([('/lab/new', ['std_msgs/msg/String'])])


def test_coco_lab_never_imports_coco_lab_ros():
    import coco_lab
    root = os.path.dirname(os.path.realpath(coco_lab.__file__))
    count = 0
    for dirpath, _, files in os.walk(root):
        for f in files:
            if not f.endswith('.py'):
                continue
            count += 1
            with open(os.path.join(dirpath, f), encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for n in names:
                    assert n.split('.')[0] not in ('coco_lab_ros', 'rclpy'), \
                        (f, n)
    assert count >= 10


@pytest.fixture
def no_ros(monkeypatch):
    for name in list(sys.modules):
        top = name.split('.')[0]
        if top in BANNED or top in ('coco_lab_ros', 'coco_lab'):
            monkeypatch.delitem(sys.modules, name, raising=False)
    real = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split('.')[0] in BANNED:
            raise AssertionError(f'pure module pulled in {name!r}')
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', guarded)
    yield


def test_the_pure_modules_import_without_ros(no_ros):
    for name in PURE:
        importlib.import_module(name)
    with pytest.raises(AssertionError):
        import rclpy  # noqa: F401


@pytest.fixture
def ros_context():
    import rclpy        # a ROS package's suite: never skipped for lack of it
    os.environ.setdefault('ROS_DOMAIN_ID', '83')
    rclpy.init()
    yield rclpy
    rclpy.shutdown()


def test_a_live_node_publishes_only_lab_topics(ros_context):
    from coco_lab_ros.planner_node import LabPlanner
    from rclpy.parameter import Parameter
    node = LabPlanner(parameter_overrides=[
        Parameter('autostart', Parameter.Type.BOOL, False)])
    try:
        pubs = node.get_publisher_names_and_types_by_node(
            node.get_name(), node.get_namespace())
        assert safety.violations(pubs) == []
        topics = {t for t, _ in pubs} - set(safety.INFRASTRUCTURE_TOPICS)
        assert topics == set(safety.LAB_TOPICS)
        for t, types in pubs:
            if t in safety.LAB_TOPICS:
                assert types == [safety.LAB_TOPICS[t]]
    finally:
        node.destroy_node()
