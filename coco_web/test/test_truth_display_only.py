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
Ground truth reaches the BROWSER, never the mission, through this layer.

The web layer subscribes to the simulator's model odometry to draw a truth
ghost (Phase 2). Everything it can send toward the robot is a closed list:
PUBLISH_ALLOWLIST and CALL_ALLOWLIST. These tests pin that the truth is
written in exactly one callback and read in exactly one function, the
telemetry builder, and that no publisher, service call or intent carries
it.

Scope, stated honestly: mission_executive subscribes to
/model/coco/odometry ITSELF, for its ground-truth arrival gates
(C2-NAV.44/45). That is pre-existing and outside this package. What is
proved here is that the web layer adds no path from truth to the mission.
"""

import ast
import os

from coco_web import protocol, safety

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, '..', 'coco_web', 'platform_server.py')


def _functions_mentioning(word):
    """Map 'Class.method' -> True for every function whose body names it."""
    tree = ast.parse(open(SERVER).read())
    found = set()
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            for node in ast.walk(fn):
                text = None
                if isinstance(node, ast.Constant) and isinstance(
                        node.value, str):
                    text = node.value
                elif isinstance(node, ast.Attribute):
                    text = node.attr
                if text is not None and word in text.split('_') + [text]:
                    found.add(f'{cls.name}.{fn.name}')
                    break
    return found


def test_truth_is_written_once_and_read_once():
    """_on_truth writes it, refresh() sends it; __init__ wires it up."""
    assert _functions_mentioning('truth') == {
        'CocoWebNode.__init__',       # the `truth` parameter, the callback
        'CocoWebNode._on_truth',      # the one writer
        'Platform.refresh',           # the one reader: robot.truth
    }


def test_no_command_path_touches_the_truth():
    """Every way out toward the robot, by name, is truth-free."""
    tree = ast.parse(open(SERVER).read())
    outbound = ('publish_', 'call_', 'engage_stop', 'release_stop',
                'hold_zero', 'on_mission_mode', '_dispatch')
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith(
                    outbound):
                names = {n.attr for n in ast.walk(fn)
                         if isinstance(n, ast.Attribute)}
                names |= {n.value for n in ast.walk(fn)
                          if isinstance(n, ast.Constant)
                          and isinstance(n.value, str)}
                assert not any('truth' in n for n in names), fn.name


def test_the_outbound_surface_is_unchanged_by_the_truth():
    """No allowlisted topic or service is the simulator's, or carries it."""
    outbound = [topic for topic, _ in safety.PUBLISH_ALLOWLIST.values()]
    outbound += [srv for srv, _ in safety.CALL_ALLOWLIST.values()]
    assert '/model/coco/odometry' not in outbound
    assert not any('truth' in name or 'model' in name for name in outbound)


def test_no_client_frame_can_carry_a_truth():
    """The only client pose is nav_goal's x/y, which a person clicked."""
    for kind, fields in protocol._CLIENT_SCHEMA.items():
        assert not any('truth' in f for f in fields), kind
