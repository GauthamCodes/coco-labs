# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
"""
G2.2: the ROS-shaped model's parity fixture is current.

lab_web/test/g2_ros_shapes.test.ts compares the page's shapes (src/ros/shapes.ts) with
coco_lab.ros_shapes on lab_web/test/fixtures/ros_shapes_parity.json; this regenerates that
fixture from today's glue and coco_lab (tools/g2/make_ros_parity_fixture.py --check), so a
change to either cannot leave the comparison running on stale data.
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_the_ros_parity_fixture_is_current():
    r = subprocess.run([sys.executable, str(REPO / 'tools/g2/make_ros_parity_fixture.py'), '--check'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_glue_adds_ros_frames_without_touching_the_model():
    """A game tick carries ros.tf; the same inputs give the same state hashes with or without reading it."""
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('g2_parity_glue_t', REPO / 'lab_web/src/arena/arena_glue.py')
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    world, _ = g.game_init((REPO / 'worlds/coco_depot_v1.json').read_text(), 'free', 0, 1, lambda *_: None, hash_version=3)
    info = json.loads(world)['game']
    assert info['ros']['graph']['evidence'] == 'MODEL'
    g.begin(json.dumps(info['setup']))
    while not g.advance(4096):
        pass
    t = json.loads(g.finish()[0])
    frames = [(x['header']['frame_id'], x['child_frame_id']) for x in t['ros']['tf']['transforms']]
    assert frames == [('map', 'odom'), ('odom', 'base_footprint')]
    # the plain Arena (no game shell) on the same inputs: the same hash
    from coco_lab.arena import Arena, InputEvent
    a = Arena(json.loads((REPO / 'worlds/coco_depot_v1.json').read_text()), 1, hash_version=3)
    st = a.step([InputEvent(**dict(e, tick=0)) for e in info['setup']])
    assert st.state_hash == t['hash']
