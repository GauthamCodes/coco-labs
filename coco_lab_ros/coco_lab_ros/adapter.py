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
The ROS-to-event adapter (M3.1; docs/v2/ADAPTER.md).

Reads a rosbag2 recording of the full ROS 2 stack in Gazebo and writes the
same run as COCO events -- a coco run file (MCAP, protobuf, the families of
``coco_schemas``) the Arena viewer replays as a Case File, evidence class
STACK. It is a PURE CONVERSION: every value written is a value recorded,
re-expressed (units, frames, layout). No algorithm runs: no filter, no
planner, no controller, no smoothing, no estimate is computed here, and a
test refuses any import of ``coco_lab``'s algorithms.

The re-expressions, each listed in ADAPTER.md:

* **Clock.** ``t_world`` is the recording's simulation time: a message's
  header stamp when it has one; otherwise its bag log time mapped onto
  simulation time through the recorded ``/model/coco/odometry`` (header
  stamp against log time, piecewise linear). Recordings made with
  ``--use-sim-time`` make that map the identity; Lab 4's, logged in wall
  time, need it. ``tick`` = floor((t_world - t0) / 0.1 s), t0 the window's
  start; ``seq`` counts rows per channel.
* **Frames.** Gazebo's world frame becomes the Arena's map frame by the
  run's own ``world_to_map`` offset (its ``meta.json``, else the Case File
  spec). Paths recorded in ``odom`` (Nav2's local plan) are put in ``map``
  by the latest recorded ``map -> odom`` transform from ``/tf``.
* **Detail.** ``full`` keeps every message. ``summary`` (the Case Files on
  the site) keeps a recorded message no more often than the rate in
  :data:`DETAIL` per topic -- always the first in each interval, never an
  interpolated one -- and a string topic's message only when its text
  changes or once a second.
"""

import bisect
import hashlib
import json
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

from coco_lab_ros.safety import RECORDED_COMMANDS

#: the recorded command topics (read, never published; named in safety.py)
CMD_NAV, CMD_WHEELS, CMD_TELEOP = (RECORDED_COMMANDS['nav'], RECORDED_COMMANDS['wheels'],
                                   RECORDED_COMMANDS['teleop'])

ADAPTER = 'coco_lab_ros.adapter'
ADAPTER_VERSION = '1'
TICK = 0.1
SPEC_FORMAT = 'coco_lab_ros.case_spec.v1+json'
EVIDENCE_STACK = 2
TIER_STACK = 2

#: per-topic minimum interval in seconds for ``summary`` (None: every message)
DETAIL = {
    'full': {},
    'summary': {
        '/model/coco/odometry': 0.1, '/odometry/filtered': 0.1,
        '/diff_drive_controller/odom': 0.1, '/scan': 0.5, '/local_plan': 0.5,
        '/optimal_trajectory': 0.5, '/received_global_plan': 1.0,
        CMD_NAV: 0.1, CMD_WHEELS: 0.1, '/lab/actors': 0.1, CMD_TELEOP: 0.1,
    },
}
#: string topics: written on a change of text, else at most once a second (summary)
STRING_PERIOD = 1.0

#: plan topics -> the PathBatch search_id that names them (ADAPTER.md)
PLAN_IDS = {'/lab/plan': 1, '/received_global_plan': 2, '/plan': 3}
#: string topics carried as annotations (source = the topic)
ANNOTATED = ('/lab/status', '/mission/search', '/mission/search_region',
             '/perception/status', '/approach/status', '/grasp/status',
             '/ramp/status', '/cmd_vel_arbiter/status')
TOPICS = ('/model/coco/odometry', '/amcl_pose', '/odometry/filtered',
          '/diff_drive_controller/odom', '/scan', '/tf', '/local_plan',
          '/optimal_trajectory', CMD_NAV, CMD_WHEELS, CMD_TELEOP, '/mission/state',
          '/lab/actors',
          '/collision_monitor_state') + tuple(PLAN_IDS) + ANNOTATED

CH = {
    'manifest': 'coco.envelope.manifest.v1',
    'robot': 'coco.robot.state.v1',
    'truth': 'coco.truth.pose.v1',
    'actors': 'coco.truth.actors.v1',
    'scan': 'coco.sensor.scan.lidar.v1',
    'estimate': 'coco.estimate.pose.v1',
    'path': 'coco.plan.path.poses.v1',
    'ctl_header': 'coco.control.local.header.v1',
    'candidates': 'coco.control.local.candidates.v1',
    'command': 'coco.control.local.command.v1',
    'fsm_header': 'coco.mission.fsm.header.v1',
    'transition': 'coco.mission.fsm.transition.v1',
    'metrics': 'coco.metrics.values.v1',
    'annotation': 'coco.annotation.text.v1',
}


# -- small pure helpers (unit-tested without ROS) -----------------------------

def yaw(q) -> float:
    """Return the yaw of a quaternion with fields x, y, z, w."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def stamp_s(msg) -> float:
    """Return a message's header stamp in seconds (0.0 if it has none or it is zero)."""
    h = getattr(msg, 'header', None)
    if h is None:
        return 0.0
    return h.stamp.sec + h.stamp.nanosec * 1e-9


def parse_kv(text: str) -> Dict[str, str]:
    """Split ``key=value`` words (the mission's status lines); ``--`` means empty."""
    out = {}
    for word in text.split():
        k, sep, v = word.partition('=')
        if sep:
            out[k] = '' if v == '--' else v
    return out


class SimClock:
    """Bag log time (ns) -> simulation time (s), from (log, stamp) pairs; piecewise linear."""

    def __init__(self, pairs: Sequence[Tuple[int, float]]):
        """Keep the pairs sorted by log time (at least one is needed)."""
        pts = sorted(pairs)
        if not pts:
            raise ValueError('no reference stamps to map log time onto simulation time')
        self.log = [p[0] for p in pts]
        self.sim = [p[1] for p in pts]

    def __call__(self, log_ns: int) -> float:
        """Map one log time; outside the reference span, extend at slope 1."""
        i = bisect.bisect_left(self.log, log_ns)
        if i == 0:
            return self.sim[0] + (log_ns - self.log[0]) * 1e-9
        if i >= len(self.log):
            return self.sim[-1] + (log_ns - self.log[-1]) * 1e-9
        l0, l1, s0, s1 = self.log[i - 1], self.log[i], self.sim[i - 1], self.sim[i]
        return s0 + (s1 - s0) * (log_ns - l0) / (l1 - l0) if l1 != l0 else s0


class Thin:
    """The summary detail's rule: keep a topic's message if its interval has passed."""

    def __init__(self, detail: str):
        """Use the per-topic intervals of ``DETAIL[detail]``."""
        if detail not in DETAIL:
            raise ValueError(f'detail must be one of {sorted(DETAIL)}')
        self.every = DETAIL[detail]
        self.summary = detail == 'summary'
        self.last: Dict[str, float] = {}
        self.text: Dict[str, str] = {}

    def keep(self, topic: str, t: float) -> bool:
        """Return whether a numeric topic's message at ``t`` is kept."""
        dt = self.every.get(topic)
        if dt is None:
            return True
        if t < self.last.get(topic, -math.inf) + dt - 1e-9:
            return False
        self.last[topic] = t
        return True

    def keep_text(self, topic: str, t: float, text: str) -> bool:
        """Keep a string topic's message: always in full; in summary on change or each second."""
        if not self.summary:
            return True
        changed = self.text.get(topic) != text
        if changed or t >= self.last.get(topic, -math.inf) + STRING_PERIOD - 1e-9:
            self.text[topic] = text
            self.last[topic] = t
            return True
        return False


def file_sha256(path: str) -> str:
    """Return a file's sha256 (streamed)."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def source_files(bag: str) -> List[Dict[str, object]]:
    """Return each file of a bag directory with its sha256 and size (the Case File's citation)."""
    out = []
    for name in sorted(os.listdir(bag)):
        p = os.path.join(bag, name)
        if os.path.isfile(p):
            out.append({'name': name, 'sha256': file_sha256(p), 'bytes': os.path.getsize(p)})
    return out


# -- reading the bag (needs rosbag2_py / rclpy) ---------------------------------

def read_bag(bag: str, topics: Sequence[str]):
    """Yield ``(topic, msg, log_ns)`` for the recorded ``topics``, in log-time order."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message
    import yaml
    with open(os.path.join(bag, 'metadata.yaml')) as f:
        storage = yaml.safe_load(f)['rosbag2_bagfile_information']['storage_identifier']
    r = rosbag2_py.SequentialReader()
    r.open(rosbag2_py.StorageOptions(uri=bag, storage_id=storage),
           rosbag2_py.ConverterOptions('', ''))
    types = {t.name: t.type for t in r.get_all_topics_and_types()}
    want = [t for t in topics if t in types]
    if not want:
        return
    r.set_filter(rosbag2_py.StorageFilter(topics=want))
    cls = {t: get_message(types[t]) for t in want}
    rows = []
    while r.has_next():
        t, data, log_ns = r.read_next()
        rows.append((log_ns, t, data))
    rows.sort(key=lambda x: x[0])   # without an index the reader returns file order
    for log_ns, t, data in rows:
        yield t, deserialize_message(data, cls[t]), log_ns


def recorded_topics(bag: str) -> Dict[str, str]:
    """Return ``{topic: type}`` of a bag."""
    import rosbag2_py
    info = rosbag2_py.Info().read_metadata(bag, 'mcap')
    return {t.topic_metadata.name: t.topic_metadata.type for t in info.topics_with_message_count}


# -- the conversion ----------------------------------------------------------------

class _Rows:
    """Rows of one channel, grouped into one batch per tick."""

    def __init__(self):
        self.by_tick: Dict[int, List[Tuple[float, dict]]] = {}

    def add(self, tick: int, t: float, row: dict) -> None:
        self.by_tick.setdefault(tick, []).append((t, row))


def convert(bag: str, case: dict, detail: str = 'summary',
            window: Optional[Tuple[float, float]] = None,
            world_to_map: Optional[Tuple[float, float]] = None,
            log_window: Optional[Tuple[int, int]] = None,
            source_root: Optional[str] = None, git_sha: str = '') -> Tuple[bytes, dict]:
    """
    Convert one recording; return ``(run file bytes, summary)``.

    ``case`` is the Case File's spec (its id, title, lab, controller ...),
    written into the manifest as given. ``window`` keeps only messages with
    ``t_world`` in ``[start, end]`` (simulation seconds). ``log_window``
    first keeps only messages, and clock-reference pairs, with a bag LOG time
    in ``[start, end]`` (ns): a recorder that outlived its run and caught the
    next run's fresh simulator (whose clock restarts) is cut by it.
    ``world_to_map`` defaults to the run directory's ``meta.json``.
    """
    from coco_schemas import mcap_write, runid
    from coco_schemas.channels import message_class

    M = {k: message_class(n) for k, n in {
        'Manifest': 'coco.envelope.v1.Manifest',
        'RobotStateBatch': 'coco.robot.v1.RobotStateBatch',
        'TruthPoseBatch': 'coco.truth.v1.TruthPoseBatch',
        'ActorPoseBatch': 'coco.truth.v1.ActorPoseBatch',
        'ScanBatch': 'coco.sensor.v1.ScanBatch',
        'EstimateBatch': 'coco.estimate.v1.EstimateBatch',
        'PathBatch': 'coco.plan.v1.PathBatch',
        'ControllerHeader': 'coco.control.v1.ControllerHeader',
        'CandidateBatch': 'coco.control.v1.CandidateBatch',
        'CommandBatch': 'coco.control.v1.CommandBatch',
        'MissionHeader': 'coco.mission.v1.MissionHeader',
        'TransitionBatch': 'coco.mission.v1.TransitionBatch',
        'MetricBatch': 'coco.metrics.v1.MetricBatch',
        'AnnotationBatch': 'coco.annotation.v1.AnnotationBatch',
    }.items()}

    run_dir = os.path.dirname(os.path.abspath(bag))
    if world_to_map is None:
        meta = os.path.join(run_dir, 'meta.json')
        if os.path.isfile(meta):
            with open(meta) as f:
                world_to_map = tuple(json.load(f).get('world_to_map', ()))
        if not world_to_map:
            world_to_map = tuple(case.get('world_to_map', ()))
        if not world_to_map:
            raise ValueError(f'no world_to_map for {bag}: none in meta.json or the case spec')
    dx, dy = float(world_to_map[0]), float(world_to_map[1])

    types = recorded_topics(bag)
    used = [t for t in TOPICS if t in types]

    # pass 1: the clock reference (odometry stamps against log times)
    def in_log(log_ns):
        return log_window is None or log_window[0] <= log_ns <= log_window[1]

    ref = [(log_ns, stamp_s(m)) for _, m, log_ns in read_bag(bag, ['/model/coco/odometry'])
           if stamp_s(m) > 0 and in_log(log_ns)]
    clock = SimClock(ref) if ref else None

    thin = Thin(detail)
    rows: Dict[str, _Rows] = {k: _Rows() for k in CH}
    seq: Dict[str, int] = {}
    t0 = window[0] if window else None
    map_odom: Optional[Tuple[float, float, float]] = None
    last_state: Optional[str] = None
    states: List[str] = []
    counts: Dict[str, int] = {}

    def when(msg, log_ns) -> float:
        s = stamp_s(msg)
        if s > 0:
            return s
        if clock is None:
            return log_ns * 1e-9
        return clock(log_ns)

    def put(ch: str, t: float, row: dict) -> None:
        nonlocal t0
        if t0 is None:
            t0 = t
        tick = max(0, int(math.floor((t - t0) / TICK + 1e-9)))
        k = seq.get(ch, 0)
        seq[ch] = k + 1
        row = dict(row, seq=k, tick=tick, t_world=t)
        rows[ch].add(tick, t, row)
        counts[ch] = counts.get(ch, 0) + 1

    def to_map(x, y):
        return x + dx, y + dy

    def odom_to_map(x, y, th):
        if map_odom is None:
            return None
        ox, oy, ot = map_odom
        c, s = math.cos(ot), math.sin(ot)
        return ox + c * x - s * y, oy + s * x + c * y, th + ot

    for topic, m, log_ns in read_bag(bag, used):
        if not in_log(log_ns):
            continue
        t = when(m, log_ns)
        if window and not (window[0] <= t <= window[1]):
            if topic == '/tf':           # keep the transform current even before the window
                pass
            else:
                continue
        if topic == '/tf':
            for tr in m.transforms:
                if tr.header.frame_id == 'map' and tr.child_frame_id == 'odom':
                    q = tr.transform.rotation
                    map_odom = (tr.transform.translation.x, tr.transform.translation.y, yaw(q))
            continue
        if topic == '/model/coco/odometry':
            if not thin.keep(topic, t):
                continue
            p = m.pose.pose
            x, y = to_map(p.position.x, p.position.y)
            put('truth', t, {'x': x, 'y': y, 'theta': yaw(p.orientation)})
        elif topic == '/amcl_pose':
            p = m.pose.pose
            c = m.pose.covariance
            th = yaw(p.orientation)
            put('estimate', t, {'x': p.position.x, 'y': p.position.y, 'theta': th,
                                'cov_xx': c[0], 'cov_xy': c[1], 'cov_xt': c[5], 'cov_yy': c[7],
                                'cov_yt': c[11], 'cov_tt': c[35], 'estimator': 'amcl'})
            put('robot', t, {'x': p.position.x, 'y': p.position.y, 'theta': th,
                             'v': math.nan, 'omega': math.nan})
        elif topic in ('/odometry/filtered', '/diff_drive_controller/odom'):
            if not thin.keep(topic, t):
                continue
            p = m.pose.pose
            c = m.pose.covariance
            name = 'robot_localization' if topic == '/odometry/filtered' else 'wheel_odometry'
            x, y, th, frame = p.position.x, p.position.y, yaw(p.orientation), m.header.frame_id
            if frame == 'odom' and map_odom is not None:
                x, y, th = odom_to_map(x, y, th)
                frame = 'map'   # by the recorded map -> odom transform (ADAPTER.md)
            put('estimate', t, {'x': x, 'y': y, 'theta': th, 'cov_xx': c[0], 'cov_xy': c[1],
                                'cov_xt': c[5], 'cov_yy': c[7], 'cov_yt': c[11], 'cov_tt': c[35],
                                'estimator': f'{name}@{frame}'})
        elif topic == '/scan':
            if not thin.keep(topic, t):
                continue
            put('scan', t, {'angle_min': m.angle_min, 'angle_increment': m.angle_increment,
                            'range_min': m.range_min, 'range_max': m.range_max,
                            'ranges': list(m.ranges)})
        elif topic in PLAN_IDS:
            if not thin.keep(topic, t):
                continue
            pts = [(q.pose.position.x, q.pose.position.y, yaw(q.pose.orientation))
                   for q in m.poses]
            if m.header.frame_id == 'odom':
                pts = [odom_to_map(*q) for q in pts]
                if any(q is None for q in pts):
                    continue
            put('path', t, {'search_id': PLAN_IDS[topic], 'poses': pts})
        elif topic in ('/local_plan', '/optimal_trajectory'):
            if not thin.keep(topic, t):
                continue
            pts = [(q.pose.position.x, q.pose.position.y) for q in m.poses]
            if m.header.frame_id == 'odom':
                pts = [odom_to_map(x, y, 0.0) for x, y in pts]
                if any(q is None for q in pts):
                    continue
                pts = [(q[0], q[1]) for q in pts]
            put('candidates', t, {'source': topic, 'traj': pts})
        elif topic == CMD_NAV:
            if not thin.keep(topic, t):
                continue
            put('command', t, {'v': m.twist.linear.x, 'w': m.twist.angular.z})
        elif topic in (CMD_WHEELS, CMD_TELEOP):
            if not thin.keep(topic, t):
                continue
            name = 'wheels' if topic == CMD_WHEELS else 'teleop'
            put('metrics', t, {'name': f'{name}.cmd.v', 'value': m.twist.linear.x, 'unit': 'm/s'})
            put('metrics', t, {'name': f'{name}.cmd.w', 'value': m.twist.angular.z,
                               'unit': 'rad/s'})
        elif topic == '/collision_monitor_state':
            put('metrics', t, {'name': 'collision_monitor.action_type',
                               'value': float(m.action_type), 'unit': ''})
        elif topic == '/mission/state':
            kv = parse_kv(m.data)
            state = kv.get('state', '')
            if state and state != last_state:
                put('transition', t, {'from_state': last_state or kv.get('prev', ''),
                                      'to_state': state, 'event': kv.get('event', ''),
                                      'reason': kv.get('reason', ''),
                                      'result': kv.get('result', '')})
                last_state = state
                if state not in states:
                    states.append(state)
        elif topic == '/lab/actors':
            if not thin.keep(topic, t):
                continue
            d = json.loads(m.data)
            for aid, pose in sorted((d.get('poses') or {}).items()):
                if pose is None:
                    continue
                x, y = to_map(pose[0], pose[1])
                put('actors', t, {'actor_id': aid, 'x': x, 'y': y, 'theta': pose[2],
                                  'radius': float(case.get('actor_radius', math.nan))})
        elif topic in ANNOTATED:
            if not thin.keep_text(topic, t, m.data):
                continue
            put('annotation', t, {'text': m.data, 'source': topic})

    # -- encode: one batch per channel per tick --------------------------------------
    records: List[Tuple[float, int, str, object]] = []
    order = 0

    def emit(ch: str, t: float, msg) -> None:
        nonlocal order
        records.append((t, order, CH[ch], msg))
        order += 1

    def clocks(rs):
        return {'seq': [r['seq'] for _, r in rs], 'tick': [r['tick'] for _, r in rs],
                't_world': [r['t_world'] for _, r in rs]}

    def cols(rs, *names):
        return {n: [r[n] for _, r in rs] for n in names}

    simple = {
        'truth': ('TruthPoseBatch', ('x', 'y', 'theta')),
        'robot': ('RobotStateBatch', ('x', 'y', 'theta', 'v', 'omega')),
        'actors': ('ActorPoseBatch', ('actor_id', 'x', 'y', 'theta', 'radius')),
        'metrics': ('MetricBatch', ('name', 'value', 'unit')),
        'transition': ('TransitionBatch', ('from_state', 'to_state', 'event', 'reason',
                                           'result')),
    }
    for ch, (msgname, names) in simple.items():
        for tick, rs in sorted(rows[ch].by_tick.items()):
            extra = {'mission_id': 'stack'} if ch == 'transition' else {}
            emit(ch, rs[0][0], M[msgname](**clocks(rs), **cols(rs, *names), **extra))
    for tick, rs in sorted(rows['estimate'].by_tick.items()):
        by = {}
        for t, r in rs:
            by.setdefault(r['estimator'], []).append((t, r))
        for est, group in sorted(by.items()):
            emit('estimate', group[0][0], M['EstimateBatch'](
                **clocks(group), **cols(group, 'x', 'y', 'theta', 'cov_xx', 'cov_xy', 'cov_xt',
                                        'cov_yy', 'cov_yt', 'cov_tt'), estimator=est))
    for tick, rs in sorted(rows['scan'].by_tick.items()):
        emit('scan', rs[0][0], M['ScanBatch'](
            **clocks(rs), **cols(rs, 'angle_min', 'angle_increment', 'range_min', 'range_max'),
            count=[len(r['ranges']) for _, r in rs],
            ranges=[v for _, r in rs for v in r['ranges']]))
    for tick, rs in sorted(rows['path'].by_tick.items()):
        for t, r in rs:
            n = len(r['poses'])
            emit('path', t, M['PathBatch'](
                seq=[r['seq']] * n, tick=[r['tick']] * n, t_world=[t] * n,
                x=[p[0] for p in r['poses']], y=[p[1] for p in r['poses']],
                theta=[p[2] for p in r['poses']], search_id=r['search_id']))
    controller = case.get('controller', '')
    if counts.get('candidates') or counts.get('command'):
        emit('ctl_header', -1.0, M['ControllerHeader'](
            controller_id='FollowPath', kind=controller, evidence='STACK'))
    cycle = 0
    for tick, rs in sorted(rows['candidates'].by_tick.items()):
        for t, r in rs:
            n = len(r['traj'])
            emit('candidates', t, M['CandidateBatch'](
                seq=[r['seq']], tick=[r['tick']], t_world=[t], candidate=[0],
                v=[math.nan], w=[math.nan], valid=[True], rejection=[''], cost=[math.nan],
                traj_offset=[0], traj_len=[n], traj_x=[p[0] for p in r['traj']],
                traj_y=[p[1] for p in r['traj']], cycle=cycle,
                controller_id=f'FollowPath{r["source"]}'))
            cycle += 1
    for tick, rs in sorted(rows['command'].by_tick.items()):
        n = len(rs)
        emit('command', rs[0][0], M['CommandBatch'](
            **clocks(rs), cycle=[0] * n, chosen=[-1] * n, **cols(rs, 'v', 'w'),
            status=['cmd_vel_nav'] * n, n_candidates=[0] * n, n_valid=[0] * n,
            lookahead_x=[math.nan] * n, lookahead_y=[math.nan] * n,
            controller_id='FollowPath'))
    if states:
        emit('fsm_header', -1.0, M['MissionHeader'](mission_id='stack', states=states,
                                                    evidence='STACK'))
    for tick, rs in sorted(rows['annotation'].by_tick.items()):
        n = len(rs)
        emit('annotation', rs[0][0], M['AnnotationBatch'](
            **clocks(rs), text=[r['text'] for _, r in rs], level=[1] * n,
            has_position=[False] * n, x=[math.nan] * n, y=[math.nan] * n,
            source=[r['source'] for _, r in rs]))

    records.sort(key=lambda r: (r[0], r[1]))
    start = t0 if t0 is not None else 0.0
    rel = os.path.relpath(os.path.abspath(bag), source_root) if source_root else bag
    spec = {
        'case': case,
        'source': {'bag': rel, 'files': source_files(bag)},
        'adapter': {'name': ADAPTER, 'version': ADAPTER_VERSION, 'detail': detail,
                    'topics': used, 'world_to_map': [dx, dy],
                    'window': list(window) if window else None,
                    'log_window_ns': list(log_window) if log_window else None, 't0': start,
                    'clock': 'header stamps; log time via /model/coco/odometry'
                             if clock else 'header stamps; log time as is'},
    }
    spec_bytes = runid.canonical_json(spec)
    engines = [(ADAPTER, ADAPTER_VERSION), ('ros', 'jazzy')]
    rid = runid.run_id(spec_bytes, 0, engines)
    channels = sorted({r[2] for r in records} | {CH['manifest']})
    msgname_of = {r[2]: r[3].DESCRIPTOR.full_name for r in records}
    manifest = M['Manifest'](
        run_id=rid, spec_format=SPEC_FORMAT, spec=spec_bytes,
        spec_sha256=runid.spec_sha256(spec_bytes), seed=0, tier=TIER_STACK,
        evidence_class=EVIDENCE_STACK,
        engines=[{'name': n, 'version': v} for n, v in engines],
        channels=[{'name': c, 'message': msgname_of.get(c, 'coco.envelope.v1.Manifest')}
                  for c in channels],
        provenance={'tool': f'{ADAPTER} {ADAPTER_VERSION}', 'git_sha': git_sha,
                    'source': f'rosbag2 {rel}', 'note': f'detail={detail}'})
    w = mcap_write.RunWriter()
    w.add(CH['manifest'], manifest, 0)
    for t, _, ch, msg in records:
        seq0 = msg.seq[0] if 'seq' in msg.DESCRIPTOR.fields_by_name and len(msg.seq) else 0
        w.add(ch, msg, int(round(max(t, 0.0) * 1e9)), sequence=seq0)
    data = w.finish(rid)
    summary = {'run_id': rid, 'bytes': len(data), 'messages': w.count, 'rows': counts,
               't0': start, 'source_files': spec['source']['files'], 'topics': used}
    return data, summary


def main(argv=None) -> int:
    """Run ``python3 -m coco_lab_ros.adapter BAG OUT.mcap --case CASE.json [--detail D]``."""
    import argparse
    ap = argparse.ArgumentParser(description='ROS-to-event adapter (M3.1)')
    ap.add_argument('bag')
    ap.add_argument('out')
    ap.add_argument('--case', required=True, help='the Case File spec (JSON)')
    ap.add_argument('--detail', default='summary', choices=sorted(DETAIL))
    ap.add_argument('--window', nargs=2, type=float, metavar=('START', 'END'))
    ap.add_argument('--log-window', nargs=2, type=int, metavar=('START_NS', 'END_NS'))
    ap.add_argument('--source-root', default=os.path.expanduser('~/coco_lab_runs'))
    ap.add_argument('--git-sha', default='')
    a = ap.parse_args(argv)
    with open(a.case) as f:
        case = json.load(f)
    data, summary = convert(a.bag, case, a.detail, tuple(a.window) if a.window else None,
                            log_window=tuple(a.log_window) if a.log_window else None,
                            source_root=a.source_root, git_sha=a.git_sha)
    with open(a.out, 'wb') as f:
        f.write(data)
    print(json.dumps({k: summary[k] for k in ('run_id', 'bytes', 'messages', 'rows')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
