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
The static conformance smoke test: real Nav2 planners, no simulator.

``lab_static_smoke.launch.py`` runs map_server + planner_server on the
lab-merged parameters (``use_sim_time`` off, nothing else changed) over a
small committed map, on a private ROS domain; this process provides the
``map -> base_footprint`` transform. It proves, before any Gazebo run:

- ``costmap_raw`` arrives and settles, and the adapter reads it;
- the overlay registered all three planners (GridBased, NavFn,
  NavFnAStar), each answering ``ComputePathToPose``;
- ``/unsmoothed_plan`` is published for a GridBased request once it has a
  subscriber (owner decision D-3), and not for NavFn;
- Smac 2D's poses sit on cell CORNERS (``getWorldCoords``, noted from
  source at 1C-0) -- measured here on the real binary;
- Smac's raw path is 8-connected over free C1 cells, so E is defined,
  and E(Smac raw) >= E*(C1): a THEOREM when the two graphs are the same,
  so a violation would mean the adapter's graph is not Smac's.

It does NOT assert E(Smac raw) == E*(C1). That equality is the plan's
pre-registered hypothesis, measured by the conformance experiment, not
presumed by a test. The measured values are printed.
"""

import json
import os
import signal
import subprocess
import time

from coco_lab_ros import metrics, params
from coco_lab_ros.costmap import Snapshot
from coco_lab_ros.pathing import cells_from_poses
from coco_lab_ros.planning import Planner
import pytest
import smoke_map

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
REPO = os.path.dirname(PKG)
MISSION = os.path.join(REPO, 'gazebo_models', 'config', 'nav2_params.yaml')
OVERLAY = os.path.join(PKG, 'config', 'nav2_lab_overlay.yaml')
DOMAIN = 86


def test_the_committed_map_is_what_its_maker_makes():
    y, p = smoke_map.make()
    with open(os.path.join(smoke_map.DIR, smoke_map.YAML)) as f:
        assert f.read() == y
    with open(os.path.join(smoke_map.DIR, smoke_map.PGM), 'rb') as f:
        assert f.read() == p


def smoke_params(tmp_path):
    merged = tmp_path / 'merged.yaml'
    params.merge_files(MISSION, OVERLAY, str(merged))
    doc = params.load(str(merged))
    for path in (('planner_server',), ('global_costmap', 'global_costmap'),
                 ('map_server',)):
        node = doc
        for k in path:
            node = node[k]
        node['ros__parameters']['use_sim_time'] = False
    out = tmp_path / 'smoke_params.yaml'
    out.write_text(params.dump(doc))
    return str(out)


@pytest.fixture(scope='module')
def stack(tmp_path_factory):
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from coco_lab_ros.nav2_client import Nav2Probe
    from geometry_msgs.msg import TransformStamped
    from tf2_ros import StaticTransformBroadcaster

    tmp = tmp_path_factory.mktemp('smoke')
    env = dict(os.environ, ROS_DOMAIN_ID=str(DOMAIN))
    launch = subprocess.Popen(
        ['ros2', 'launch', 'coco_lab_ros', 'lab_static_smoke.launch.py',
         f'params_file:={smoke_params(tmp)}',
         f'map:={os.path.join(smoke_map.DIR, smoke_map.YAML)}'],
        env=env, stdout=open(tmp / 'launch.log', 'w'),
        stderr=subprocess.STDOUT, start_new_session=True)
    ctx = rclpy.Context()
    rclpy.init(context=ctx, domain_id=DOMAIN)
    probe = Nav2Probe(context=ctx)
    tf_node = rclpy.create_node('lab_smoke_tf', context=ctx)
    t = TransformStamped()
    t.header.frame_id, t.child_frame_id = 'map', 'base_footprint'
    t.transform.translation.x, t.transform.translation.y = smoke_map.START
    t.transform.rotation.w = 1.0
    broadcaster = StaticTransformBroadcaster(tf_node)
    broadcaster.sendTransform(t)
    ex = MultiThreadedExecutor(num_threads=4, context=ctx)
    ex.add_node(probe)
    ex.add_node(tf_node)
    import threading
    spin = threading.Thread(target=ex.spin, daemon=True)
    spin.start()
    try:
        yield probe, tmp
    finally:
        ex.shutdown()
        probe.destroy_node()
        tf_node.destroy_node()
        rclpy.shutdown(context=ctx)
        try:
            os.killpg(launch.pid, signal.SIGINT)
            launch.wait(20)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            os.killpg(launch.pid, signal.SIGKILL)
            launch.wait(10)


def test_the_pipeline_on_real_planners(stack):
    probe, tmp = stack
    assert probe.wait_for_planner(90.0), \
        'planner_server never came up:\n' + (tmp / 'launch.log').read_text()
    msg, h = probe.wait_settled(repeats=2, timeout=90.0)
    assert msg is not None, 'costmap_raw never settled'
    snap = Snapshot.from_msg(msg, probe.costmap_topic)
    assert (snap.width, snap.height) == (smoke_map.W, smoke_map.H)
    assert snap.resolution == smoke_map.RES
    assert {254, 253} <= set(snap.data) and 0 in set(snap.data)
    deadline = time.monotonic() + 10
    while probe.raw_subscribed() < 1 and time.monotonic() < deadline:
        time.sleep(0.1)
    assert probe.raw_subscribed() >= 1, 'no unsmoothed_plan publisher'

    start = smoke_map.START + (0.0,)
    goal = smoke_map.GOAL + (0.0,)
    res = {pid: probe.compute(pid, start, goal)
           for pid in ('GridBased', 'NavFn', 'NavFnAStar')}
    for pid, r in res.items():
        assert r['ok'], (pid, r['error_code'], r['error_msg'])
    assert probe.latest_costmap()[1] == h, 'the costmap changed mid-test'

    smac = res['GridBased']
    assert smac['raw'], 'no unsmoothed_plan for a GridBased request'
    assert res['NavFn']['raw'] is None and res['NavFnAStar']['raw'] is None

    cells, residual = cells_from_poses(smac['raw'], snap, 'corner')
    assert residual < 1e-3, f'Smac poses are not on cell corners ({residual})'
    planner = Planner(snap)
    grid = planner.grid('C1')
    e_smac, why = metrics.edge_sum(metrics.lab_cells_of(cells, snap), grid)
    assert why is None, why
    s_cell = snap.world_to_cell(*smoke_map.START)
    g_cell = snap.world_to_cell(*smoke_map.GOAL)
    assert cells[0] == s_cell
    best = planner.plan_cells(s_cell, g_cell, 'dijkstra', 'zero', 'C1')
    assert best.found
    assert e_smac >= best.result.cost * (1 - 1e-6), \
        'Smac found a path cheaper than the C1 optimum: graphs differ'
    record = {
        'costmap_hash': h, 'smac_raw_cells': len(cells),
        'smac_endpoint_ok': cells[-1] == g_cell,
        'E_smac_raw': e_smac, 'E_c1_dijkstra': best.result.cost,
        'E_rel_gap': (e_smac - best.result.cost) / best.result.cost,
        'corner_residual_cells': residual,
        'L': {pid: metrics.path_length([p[:2] for p in r['poses']])
              for pid, r in res.items()},
    }
    print('SMOKE', json.dumps(record, sort_keys=True))
