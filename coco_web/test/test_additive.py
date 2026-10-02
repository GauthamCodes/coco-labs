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
coco.v1 changes are ADDITIVE ONLY: nothing frozen here may disappear.

The frozen surface is coco.v1 as it stood on main 54133fe (2026-10-02),
before Phase 2 Part B. A removal, a rename, or a field that a P0.2 client
sends being refused is a breaking change and needs `coco.v2`. Adding a
frame type, an optional field, a refusal code or a telemetry key is not.
Do not edit a frozen set to make this test pass.
"""

import json

from coco_web import protocol
import pytest

#: Client frame types and the fields each accepted at 54133fe.
FROZEN_CLIENT = {
    'hello': {'protocol', 'client', 'binary'},
    'ping': {'t'},
    'drive': {'linear', 'angular'},
    'stop': set(),
    'set_mode': {'mode'},
    'select_target': {'colour'},
    'mission': {'action'},
    'nav_goal': {'x', 'y'},
    'set_arm': {'shoulder', 'elbow'},
    'set_gripper': {'grip'},
    'subscribe': {'streams'},
    'unsubscribe': {'streams'},
    'set_stream': {'stream', 'fps', 'quality', 'scale'},
}

#: One valid P0.2 frame of every type: each must still decode.
FROZEN_FRAMES = [
    {'type': 'hello', 'protocol': 'coco.v1', 'client': 'p02', 'binary': True},
    {'type': 'ping', 't': 12.5},
    {'type': 'drive', 'linear': 0.2, 'angular': -0.4},
    {'type': 'stop'},
    {'type': 'set_mode', 'mode': 'teleop'},
    {'type': 'set_mode', 'mode': 'auto'},
    {'type': 'set_mode', 'mode': 'stop'},
    {'type': 'select_target', 'colour': 'blue'},
    {'type': 'mission', 'action': 'start'},
    {'type': 'mission', 'action': 'abort'},
    {'type': 'nav_goal', 'x': 1.0, 'y': -0.5},
    {'type': 'set_arm', 'shoulder': 0.1, 'elbow': -0.2},
    {'type': 'set_gripper', 'grip': 0.3},
    {'type': 'subscribe', 'streams': ['camera']},
    {'type': 'unsubscribe', 'streams': ['camera']},
    {'type': 'set_stream', 'stream': 'camera', 'fps': 5},
]

FROZEN_UI_MODES = {'teleop', 'auto', 'stop'}
FROZEN_REFUSALS = {'not_in_control', 'stopped'}
FROZEN_WELCOME = {'type', 'protocol', 'session', 'streams', 'limits',
                  'commands'}
FROZEN_TELEMETRY = {'type', 'seq', 't', 'robot', 'mission', 'nav',
                    'sensors', 'platform'}
FROZEN_SECTIONS = {
    'robot': {'pose', 'frame', 'localised', 'velocity', 'online'},
    'nav': {'online', 'path', 'active_source'},
    'sensors': {'lidar', 'perception', 'grasp', 'streams'},
    'platform': {'session', 'arbiter', 'perf', 'connection', 'health',
                 'pilot', 'stop'},
}


def test_the_version_is_still_coco_v1():
    """An additive change never bumps the version."""
    assert protocol.PROTOCOL_VERSION == 'coco.v1'


@pytest.mark.parametrize('kind', sorted(FROZEN_CLIENT))
def test_every_frozen_frame_type_keeps_its_fields(kind):
    """A type may gain optional fields, never lose one."""
    assert kind in protocol._CLIENT_SCHEMA
    assert FROZEN_CLIENT[kind] <= protocol._CLIENT_SCHEMA[kind]


@pytest.mark.parametrize('frame', FROZEN_FRAMES,
                         ids=[f['type'] for f in FROZEN_FRAMES])
def test_every_frozen_frame_still_decodes(frame):
    """What a P0.2 client sends is still accepted, unchanged in meaning."""
    out = protocol.decode(json.dumps(frame))
    assert out['type'] == frame['type']
    for key, value in frame.items():
        if key != 'type':
            assert out[key] == value


def test_modes_and_refusal_codes_are_kept():
    """Modes a client may send, codes a client may branch on."""
    assert FROZEN_UI_MODES <= set(protocol.UI_MODES)
    assert FROZEN_REFUSALS <= set(protocol.REFUSAL_CODES)


def test_welcome_and_telemetry_builders_keep_their_keys():
    """The builders' own keys; the sections are checked on a live server."""
    welcome = protocol.welcome({}, {}, {})
    assert FROZEN_WELCOME <= set(welcome)
    frame = protocol.telemetry(1, 0.0, {}, {}, {}, {}, {})
    assert FROZEN_TELEMETRY <= set(frame)
