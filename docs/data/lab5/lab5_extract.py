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
Condense one Lab 5 run's two bags into ``run.json`` (needs ROS to read).

  lab5_extract.py RUN_DIR [--rollout-hz 2] [--samples 40]

Reads ``RUN_DIR/bag`` (slim) and ``RUN_DIR/heavy`` (DWB ``/evaluation``,
MPPI ``/trajectories``) plus the runner's JSON files, and writes
``RUN_DIR/run.json``. Every series is on the SIMULATOR clock (message
header stamps) and in the MAP frame:

- ground truth: ``/model/coco/odometry`` (world) + ``world_to_map``;
- anything a controller published in ``odom`` (DWB candidates and its
  chosen ``/local_plan``, MPPI rollouts and ``/optimal_trajectory``, RPP's
  ``/lookahead_point`` and ``/lookahead_collision_arc``) through the
  ``map -> odom`` transform AMCL published at or before that stamp -- so
  it is drawn where the ROBOT BELIEVED it was, which is the point of the
  mislocalised scenario.

Candidates are SAMPLED for the browser: every control cycle's counts are
kept (``eval``: t, n, n_valid, the critic that rejected each invalid one);
at ``--rollout-hz`` the candidates themselves are kept, at most
``--samples`` evenly spaced by index plus the best. Nothing is invented: a
controller that publishes no candidates (RPP) has none.

The heavy bag is hashed here (``heavy.sha256``, bytes, message counts)
so it can be deleted afterwards with its identity recorded.
"""

import argparse
import bisect
import hashlib
import json
import math
import os
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

SCHEMA = 'coco_lab.lab5_run'
VERSION = '1.0'


def stamp(h):
    """Return a header stamp as float seconds."""
    return h.stamp.sec + h.stamp.nanosec * 1e-9


def yaw_of(q):
    """Return the yaw of a quaternion."""
    return math.atan2(2 * (q.w * q.z + q.x * q.y),
                      1 - 2 * (q.y * q.y + q.z * q.z))


def read(bag, topics, keep=None):
    """
    Yield ``(topic, msg, log_time_s)`` for ``topics`` in a bag.

    ``keep(topic, log_time_s)``, if given, decides BEFORE deserialising
    (MPPI's marker arrays take ~0.1 s each to decode in Python).
    """
    if not os.path.isdir(bag):
        return
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id='mcap'),
           rosbag2_py.ConverterOptions('cdr', 'cdr'))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    want = [t for t in topics if t in types]
    if not want:
        return
    r.set_filter(rosbag2_py.StorageFilter(topics=want))
    cls = {t: get_message(types[t]) for t in want}
    while r.has_next():
        t, data, ts = r.read_next()
        if keep is not None and not keep(t, ts * 1e-9):
            continue
        yield t, deserialize_message(data, cls[t]), ts * 1e-9


class Frames:
    """map -> odom (AMCL) and odom -> base_footprint, by time."""

    def __init__(self):
        """Start empty."""
        self.map_odom = []      # (t, x, y, yaw)
        self.odom_base = []     # (t, x, y, yaw)

    def add_tf(self, msg):
        """Collect map -> odom and odom -> base_footprint transforms."""
        for tr in msg.transforms:
            pair = (tr.header.frame_id, tr.child_frame_id)
            if pair in (('map', 'odom'), ('odom', 'base_footprint')):
                p, q = tr.transform.translation, tr.transform.rotation
                (self.map_odom if pair[0] == 'map' else self.odom_base
                 ).append((stamp(tr.header), p.x, p.y, yaw_of(q)))

    def finish(self):
        """Sort by time."""
        self.map_odom.sort()
        self.odom_base.sort()
        self._ts = [s[0] for s in self.map_odom]
        self._tb = [s[0] for s in self.odom_base]

    @staticmethod
    def _apply(tf, pts):
        _, x, y, yaw = tf
        c, s = math.cos(yaw), math.sin(yaw)
        return [[x + c * px - s * py, y + s * px + c * py] for px, py in pts]

    def odom_to_map(self, t, pts):
        """Transform odom-frame points at time ``t`` (latest at or before)."""
        if not self.map_odom:
            return None
        i = bisect.bisect_right(self._ts, t) - 1
        return self._apply(self.map_odom[max(i, 0)], pts)

    def to_map(self, frame, t, pts):
        """Transform points from map, odom or base_footprint to the map."""
        if frame == 'map':
            return [list(p) for p in pts]
        if frame == 'odom':
            return self.odom_to_map(t, pts)
        if frame == 'base_footprint' and self.odom_base:
            i = bisect.bisect_right(self._tb, t) - 1
            return self.odom_to_map(t, self._apply(self.odom_base[max(i, 0)],
                                                   pts))
        return None


def r6(v):
    """Round for the record (micrometres / microseconds)."""
    return round(float(v), 6)


def pts6(pts):
    """Round a point list."""
    return [[r6(a), r6(b)] for a, b in pts]


def heavy_identity(run_dir):
    """Return the heavy bag's files, bytes and sha256 (of the mcap)."""
    d = os.path.join(run_dir, 'heavy')
    if not os.path.isdir(d):
        return None
    out = {'files': {}}
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for chunk in iter(lambda: f.read(1 << 20), b''):
                h.update(chunk)
        out['files'][name] = {'bytes': os.path.getsize(p),
                              'sha256': h.hexdigest()}
    return out


def extract(run_dir, rollout_hz=2.0, samples=40):
    """Return the run.json dict for ``run_dir``."""
    meta = json.load(open(os.path.join(run_dir, 'meta.json')))
    w2m = meta['world_to_map']
    plan = json.load(open(os.path.join(run_dir, 'plan', 'plan.json')))
    status = json.load(open(os.path.join(run_dir, 'status.json')))
    rp = os.path.join(run_dir, 'plan', 'result.json')
    result = json.load(open(rp)) if os.path.exists(rp) else None
    following = [s for s in status if s['phase'] == 'following']
    last = status[-1] if status else None
    t0 = following[0]['t_sim'] if following else None
    t1 = last['t_sim'] if last and last['phase'] in (
        'succeeded', 'follow_failed') else None
    frames = Frames()
    gt, amcl, cmd_nav, cmd_wheel, monitor = [], [], [], [], []
    chosen, lookahead, actors, trigger = [], [], {}, {}
    slim = os.path.join(run_dir, 'bag')
    for topic, m, _ in read(slim, ['/tf']):
        frames.add_tf(m)
    frames.finish()
    for topic, m, lt in read(slim, [
            '/model/coco/odometry', '/amcl_pose', '/cmd_vel_nav',
            '/diff_drive_controller/cmd_vel', '/collision_monitor_state',
            '/local_plan', '/optimal_trajectory', '/lookahead_point',
            '/lookahead_collision_arc', '/lab/actors']):
        if topic == '/model/coco/odometry':
            p = m.pose.pose
            gt.append([r6(stamp(m.header)), r6(p.position.x + w2m[0]),
                       r6(p.position.y + w2m[1]), r6(yaw_of(p.orientation))])
        elif topic == '/amcl_pose':
            p = m.pose.pose
            amcl.append([r6(stamp(m.header)), r6(p.position.x),
                         r6(p.position.y), r6(yaw_of(p.orientation))])
        elif topic == '/cmd_vel_nav':
            cmd_nav.append([r6(stamp(m.header)), r6(m.twist.linear.x),
                            r6(m.twist.angular.z)])
        elif topic == '/diff_drive_controller/cmd_vel':
            cmd_wheel.append([r6(stamp(m.header)), r6(m.twist.linear.x),
                              r6(m.twist.angular.z)])
        elif topic == '/collision_monitor_state':
            monitor.append([r6(lt), int(m.action_type), m.polygon_name])
        elif topic in ('/local_plan', '/optimal_trajectory',
                       '/lookahead_collision_arc'):
            t = stamp(m.header)
            pts = frames.to_map(m.header.frame_id, t,
                                [(q.pose.position.x, q.pose.position.y)
                                 for q in m.poses])
            if pts is not None:
                chosen.append([r6(t), topic.strip('/'), pts6(pts)])
        elif topic == '/lookahead_point':
            t = stamp(m.header)
            pts = frames.to_map(m.header.frame_id, t,
                                [(m.point.x, m.point.y)])
            if pts:
                lookahead.append([r6(t)] + [r6(v) for v in pts[0]])
        elif topic == '/lab/actors':
            d = json.loads(m.data)
            for k, v in d['poses'].items():
                actors.setdefault(k, []).append(
                    [r6(d['t']), r6(v[0]), r6(v[1]), r6(v[2])])
            for k, v in d['trigger'].items():
                if v is not None:
                    trigger[k] = r6(v)
    for series in (gt, amcl, cmd_nav, cmd_wheel, chosen, lookahead):
        series.sort(key=lambda r: r[0])

    heavy = os.path.join(run_dir, 'heavy')
    evals, rollouts, next_t = [], [], -math.inf
    due = {'t': -math.inf}

    def keep(topic, lt):
        # every DWB evaluation is decoded (its counts are kept at full
        # rate); an MPPI marker array only when a sample is due. The log
        # time (sim clock, --use-sim-time) stands in for the stamp here.
        if topic != '/trajectories':
            return True
        if lt < due['t']:
            return False
        due['t'] = lt + 1.0 / rollout_hz
        return True
    for topic, m, lt in read(heavy, ['/evaluation', '/trajectories'], keep):
        if topic == '/evaluation':
            t = stamp(m.header)
            n = len(m.twists)
            rej = {}
            for s in m.twists:
                if s.total < 0:
                    who = [c.name for c in s.scores if c.raw_score < 0]
                    k = who[-1] if who else 'unknown'
                    rej[k] = rej.get(k, 0) + 1
            n_valid = n - sum(rej.values())
            evals.append([r6(t), n, n_valid, rej])
            if t >= next_t and n:
                next_t = t + 1.0 / rollout_hz
                step = max(1, n // samples)
                idx = sorted(set(range(0, n, step)) | (
                    {m.best_index} if n_valid else set()))
                cands = []
                for i in idx:
                    s = m.twists[i]
                    pts = frames.to_map(m.header.frame_id, t,
                                        [(p.x, p.y) for p in s.traj.poses])
                    if pts is None:
                        continue
                    cands.append({'pts': pts6(pts), 'total': r6(s.total),
                                  'valid': s.total >= 0,
                                  'v': r6(s.traj.velocity.x),
                                  'w': r6(s.traj.velocity.theta),
                                  'best': i == m.best_index and n_valid > 0})
                rollouts.append({'t': r6(t), 'source': 'dwb_evaluation',
                                 'n': n, 'n_valid': n_valid,
                                 'candidates': cands})
        else:
            # MPPI's TrajectoryVisualizer (Nav2 1.3.11): ONE SPHERE marker
            # per sampled point, ns "Candidate Trajectories", ids in publish
            # order; within a trajectory the colour runs green = j / steps
            # from 0, so a marker with green == 0 starts the next sampled
            # trajectory (verified on the smoke run: 400 x 10 points).
            # MPPI publishes no per-sample cost, so none is invented here.
            if not m.markers:
                continue
            # MPPI leaves the markers' stamps at zero (measured on the
            # smoke run), so the bag's log time -- the sim clock under
            # --use-sim-time -- is the frame's time.
            t = stamp(m.markers[0].header) or lt
            frame = m.markers[0].header.frame_id
            trajs, cur = [], None
            for mk in sorted((k for k in m.markers
                              if k.ns == 'Candidate Trajectories'),
                             key=lambda k: k.id):
                if mk.color.g == 0.0 or cur is None:
                    cur = []
                    trajs.append(cur)
                cur.append((mk.pose.position.x, mk.pose.position.y))
            cands = []
            for raw in trajs[::max(1, len(trajs) // samples)]:
                pts = frames.to_map(frame, t, raw)
                if pts is not None:
                    cands.append({'pts': pts6(pts), 'total': None,
                                  'valid': None, 'v': None, 'w': None,
                                  'best': False})
            rollouts.append({'t': r6(t), 'source': 'mppi_trajectories',
                             'n': len(trajs), 'n_valid': None,
                             'candidates': cands})
    keep = {k: meta.get(k) for k in (
        'run_id', 'scenario', 'controller', 'controller_id', 'git_commit',
        'git_dirty_paths', 'lab_source', 'started_utc', 'ended_utc',
        'loadavg_start', 'loadavg_end', 'void_reason',
        'runner_checks_failed', 'sha256', 'packages', 'world_to_map',
        'scenario_def')}
    return {
        'schema': SCHEMA, 'version': VERSION, 'meta': keep,
        'outcome': last['phase'] if last else None,
        'result': result, 'window': [t0, t1],
        'path': plan.get('poses'),
        'path_sha256': plan.get('path_sha256'),
        'belief_at_start': plan.get('start_world'),
        'gt': gt, 'amcl': amcl, 'map_odom': [
            [r6(v) for v in s] for s in frames.map_odom],
        'cmd_nav': cmd_nav, 'cmd_wheel': cmd_wheel, 'monitor': monitor,
        'chosen': chosen, 'lookahead': lookahead,
        'actors': actors, 'actor_trigger': trigger,
        'eval': evals, 'rollouts': rollouts,
        'heavy': heavy_identity(run_dir),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument('run_dir')
    ap.add_argument('--rollout-hz', type=float, default=2.0)
    ap.add_argument('--samples', type=int, default=40)
    a = ap.parse_args()
    out = extract(a.run_dir, a.rollout_hz, a.samples)
    with open(os.path.join(a.run_dir, 'run.json'), 'w') as f:
        json.dump(out, f, sort_keys=True, separators=(',', ':'))
    print(f'{a.run_dir}: outcome {out["outcome"]}, gt {len(out["gt"])}, '
          f'cmd {len(out["cmd_nav"])}, eval {len(out["eval"])}, rollout '
          f'frames {len(out["rollouts"])}, chosen {len(out["chosen"])}, '
          f'actors {sorted(out["actors"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
