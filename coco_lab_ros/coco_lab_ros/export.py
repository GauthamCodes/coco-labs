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

r"""
lab_export: one real run's rosbag2 -> a 1.1 recorded-run bundle + metrics.

The bundle is built from what the BAG holds, not from the node's files:
the trace from ``/lab/trace_gz``, the map from ``/lab/costmap_snapshot``,
the run inputs from ``/lab/status``, the streams from the recorded topics.
The node's own glass-box bundle (``<plan_dir>/plan_bundle``) is then
compared with it, trace and map, as a cross-check.

Usage::

    lab_export --bag BAG --plan-dir DIR --out BUNDLE --metrics RUN.json \\
        --run-id ID [--world-to-map 2 0] [--checks CHECKS.json]

``--world-to-map`` is the offset that takes ``/model/coco/odometry``'s
world pose into the map frame (``navigation_world.json``
``world_to_map``). Timestamps: poses use their header stamps (sim time);
wheel commands and status lines use the bag's receive time, which is sim
time because the runner records with ``--use-sim-time``.

**Bag hash.** SHA-256 over the lines ``<relative path> <file sha256>\\n``
of every file in the bag directory, sorted by path. The same definition
hashes a bundle directory.
"""

import argparse
import gzip
import hashlib
import json
import os
import sys

from coco_lab.bundle import (Bundle, git_provenance, load_bundle,
                             make_provenance, write_bundle)
from coco_lab.trace import Trace

from . import run_analysis as ra
from .costmap import Snapshot
from .metrics import path_length
from .pathing import quaternion_to_yaw
from .safety import WHEEL_TOPIC

BEHAVIOR_ACTIONS = ('spin', 'backup', 'drive_on_heading', 'wait',
                    'assisted_teleop')


def file_sha256(path):
    """Return a file's hex SHA-256."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def dir_sha256(root):
    """Return the directory hash defined in the module doc, and its size."""
    lines, size = [], 0
    for dirpath, _, files in os.walk(root):
        for name in files:
            p = os.path.join(dirpath, name)
            lines.append(f'{os.path.relpath(p, root)} {file_sha256(p)}\n')
            size += os.path.getsize(p)
    return hashlib.sha256(''.join(sorted(lines)).encode()).hexdigest(), size


def read_bag(bag):
    """Return ``{topic: [(t_bag_s, msg)]}`` and ``{topic: type}``."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    import yaml
    with open(os.path.join(bag, 'metadata.yaml')) as f:
        storage = yaml.safe_load(f)['rosbag2_bagfile_information'][
            'storage_identifier']
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id=storage),
                rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    classes = {}
    out = {}
    while reader.has_next():
        topic, data, t = reader.read_next()
        if topic not in classes:
            classes[topic] = get_message(types[topic])
        out.setdefault(topic, []).append(
            (t * 1e-9, deserialize_message(data, classes[topic])))
    return out, types


def stamp(msg, fallback):
    """Return a header stamp in seconds, or ``fallback`` if it is zero."""
    st = msg.header.stamp
    s = st.sec + st.nanosec * 1e-9
    return s if s > 0 else fallback


def pose_samples(entries, kind):
    """Return ``[(t, x, y, yaw)]`` from Odometry or PoseWithCovariance."""
    out = []
    for t, m in entries:
        p = m.pose.pose
        q = p.orientation
        out.append((stamp(m, t), p.position.x, p.position.y,
                    quaternion_to_yaw(q.x, q.y, q.z, q.w)))
    out.sort(key=lambda s: s[0])
    return out


def export(bag, plan_dir, out, run_id, world_to_map=(2.0, 0.0),
           checks=None):
    """Export one run; return its metrics dict."""
    msgs, types = read_bag(bag)
    counts = {k: len(v) for k, v in msgs.items()}
    statuses = [(t, json.loads(m.data))
                for t, m in msgs.get('/lab/status', [])]
    by_phase = {}
    for _, s in statuses:
        by_phase.setdefault(s['phase'], s)
    planned = by_phase.get('planned')
    if planned is None:
        raise SystemExit(f'{bag}: no planned status -- nothing to export '
                         f'(phases: {sorted(by_phase)})')
    trace_json = gzip.decompress(bytes(msgs['/lab/trace_gz'][-1][1].data))
    trace_sha = hashlib.sha256(trace_json).hexdigest()
    trace = Trace.from_json(trace_json.decode('utf-8'))
    snap = Snapshot.from_msg(msgs['/lab/costmap_snapshot'][-1][1],
                             planned['snapshot']['source_topic'])
    consistency = {
        'trace_sha256_matches_status': trace_sha == planned['trace_sha256'],
        'snapshot_hash_matches_status':
            snap.content_hash() == planned['snapshot']['content_hash'],
    }
    lab_map = snap.to_labmap('costmap_raw')
    gb_path = os.path.join(plan_dir, 'plan_bundle')
    if os.path.isdir(gb_path):
        gb = load_bundle(gb_path)
        consistency['glass_box_trace_equal'] = gb.trace == trace
        consistency['glass_box_map_equal'] = \
            gb.lab_map.content_hash() == lab_map.content_hash()
    else:
        consistency['glass_box_trace_equal'] = None
        consistency['glass_box_map_equal'] = None
    start = list(snap.to_lab(*planned['start_cell']))
    goal = list(snap.to_lab(*planned['goal_cell']))
    h = trace.header
    run = {'algorithm': h['algorithm'], 'heuristic': h['heuristic'],
           'weight': h['weight'], 'tie_break': h['tie_break'],
           'start': start, 'goal': goal, 'graph': dict(h['graph']),
           'model': dict(planned['model']),
           'map_hash': lab_map.content_hash()}

    dx, dy = world_to_map
    gt = ra.to_map(pose_samples(msgs.get('/model/coco/odometry', []), 'gt'),
                   dx, dy)
    amcl = pose_samples(msgs.get('/amcl_pose', []), 'amcl')
    plan_msgs = msgs.get('/lab/plan', [])
    plan = []
    if plan_msgs:
        for p in plan_msgs[-1][1].poses:
            q = p.pose.orientation
            plan.append((p.pose.position.x, p.pose.position.y,
                         quaternion_to_yaw(q.x, q.y, q.z, q.w)))
    cmd = []
    for t, m in msgs.get(WHEEL_TOPIC, []):
        tw = getattr(m, 'twist', m)
        cmd.append((t, tw.linear.x, tw.angular.z))

    accept = by_phase.get('following')
    final = next((s for _, s in statuses if s['phase'] in
                  ('succeeded', 'follow_failed', 'failed', 'error')), None)
    t0 = accept['t_sim'] if accept else None
    t1 = final['t_sim'] if final else None
    goal_xy = tuple(planned['goal_world'][:2])
    plan_xy = [(x, y) for x, y, _ in plan]
    metrics = {
        'run_id': run_id,
        'algorithm': h['algorithm'], 'heuristic': h['heuristic'],
        'graph': planned['graph'], 'tie_break': h['tie_break'],
        'result': final, 'accepted': accept is not None,
        'planned': {k: planned[k] for k in (
            'start_world', 'goal_world', 'start_cell', 'goal_cell',
            'summary', 'plan_wall_s', 'path_cells', 'path_L_m',
            'trace_sha256', 'snapshot', 'model')},
        'consistency': consistency,
        'topic_counts': counts, 'topic_types': types,
    }
    if t0 is not None and t1 is not None:
        gw = ra.window(gt, t0, t1)
        metrics.update({
            'window_sim': [t0, t1],
            'duration_sim_s': t1 - t0,
            'duration_wall_s': final['t_wall'] - accept['t_wall'],
            'tracking_error_m': ra.tracking_error(gw, plan_xy),
            'endpoint_error_m': ra.endpoint_error(gt, t1, goal_xy),
            'belief_gap_m': ra.belief_gap(ra.window(amcl, t0, t1), gt),
            'gt_path_length_m': path_length([(s[1], s[2]) for s in gw]),
        })
    recov = {}
    for name in BEHAVIOR_ACTIONS:
        ids = set()
        for _, m in msgs.get(f'/{name}/_action/status', []):
            for st in m.status_list:
                ids.add(bytes(st.goal_info.goal_id.uuid).hex())
        recov[name] = len(ids)
    metrics['recoveries'] = recov
    metrics['recoveries_total'] = sum(recov.values())
    metrics['recovery_topics_recorded'] = sorted(
        n for n in BEHAVIOR_ACTIONS if f'/{n}/_action/status' in types)
    metrics['arbiter_timeline'] = ra.arbiter_timeline(
        [(t, m.data) for t, m in msgs.get('/cmd_vel_arbiter/status', [])])
    metrics['collision_monitor_timeline'] = ra.timeline(
        [(t, (int(m.action_type), str(m.polygon_name)))
         for t, m in msgs.get('/collision_monitor_state', [])])
    metrics['wheel_commands'] = {
        'n': len(cmd),
        'max_abs_v': max((abs(c[1]) for c in cmd), default=None),
        'max_abs_w': max((abs(c[2]) for c in cmd), default=None)}

    bag_sha, bag_size = dir_sha256(bag)
    all_t = [t for v in msgs.values() for t, _ in v]
    rosbag = {'sha256': bag_sha, 'sim_time_start': min(all_t),
              'sim_time_end': max(all_t)}
    metrics['bag'] = dict(rosbag, size_bytes=bag_size, path=bag)

    groups, missing, streams = {}, [], {}
    for name, rows, frame, source, cols in (
            ('gt', gt, 'map', '/model/coco/odometry', ('t', 'x', 'y', 'yaw')),
            ('amcl', amcl, 'map', '/amcl_pose', ('t', 'x', 'y', 'yaw')),
            ('plan', plan, snap.frame_id, '/lab/plan', ('x', 'y', 'yaw')),
            ('cmd', cmd, 'base_footprint', WHEEL_TOPIC, ('t', 'v', 'w'))):
        if rows:
            groups[name] = {'frame': frame, 'source': source,
                            'count': len(rows)}
            streams[name] = {c: [float(r[i]) for r in rows]
                             for i, c in enumerate(cols)}
        else:
            missing.append(name)
    metrics['streams_missing'] = missing
    meta = {k: metrics[k] for k in (
        'result', 'consistency', 'recoveries', 'arbiter_timeline',
        'collision_monitor_timeline', 'wheel_commands')}
    for k in ('window_sim', 'duration_sim_s', 'duration_wall_s',
              'tracking_error_m', 'endpoint_error_m', 'belief_gap_m'):
        if k in metrics:
            meta[k] = metrics[k]
    meta['world_to_map'] = list(world_to_map)
    meta['checks'] = checks
    recording = {'groups': groups, 'missing': missing, 'run_id': run_id,
                 'meta': json.loads(json.dumps(meta))}
    git = git_provenance(os.path.dirname(os.path.realpath(__file__)))
    prov = make_provenance('recorded-run', git=git, rosbag=rosbag,
                           tool='coco_lab_ros.lab_export')
    b = Bundle(prov, run, lab_map, trace, recording, streams)
    b.validate()
    write_bundle(b, out, compression='gzip')
    back = load_bundle(out)
    out_hash, out_size = dir_sha256(out)
    metrics['bundle'] = {
        'path': out, 'version': b.version,
        'content_hash': back.manifest('gzip')['content_hash'],
        'dir_sha256': out_hash, 'size_bytes': out_size,
        'loads_and_validates': back == b}
    return metrics


def main(argv=None):
    """Command-line entry point."""
    ap = argparse.ArgumentParser(prog='lab_export', description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument('--bag', required=True)
    ap.add_argument('--plan-dir', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--metrics', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--world-to-map', nargs=2, type=float,
                    default=[2.0, 0.0])
    ap.add_argument('--checks', default=None)
    a = ap.parse_args(argv)
    checks = None
    if a.checks:
        with open(a.checks) as f:
            checks = json.load(f)
    m = export(a.bag, a.plan_dir, a.out, a.run_id, tuple(a.world_to_map),
               checks)
    with open(a.metrics, 'w') as f:
        json.dump(m, f, sort_keys=True, indent=1)
    print(json.dumps({k: m.get(k) for k in (
        'run_id', 'duration_sim_s', 'tracking_error_m', 'recoveries_total',
        'streams_missing')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
