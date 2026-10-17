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
The ROS-shaped model (M6F.7; README §1 "ROS 2 at its core", invariant 2).

The browser robot speaks ROS 2 message *shapes*: plain dicts with exactly the
fields and nesting of ``sensor_msgs/LaserScan``, ``nav_msgs/OccupancyGrid``,
``geometry_msgs/Twist`` (and ``TwistStamped``, which COCO's ``cmd_vel_arbiter``
publishes), ``nav_msgs/Path``, ``nav_msgs/Odometry`` and ``tf2_msgs/TFMessage``.
The frames are ``map -> odom -> base_footprint -> base_link -> lidar_link``:
COCO's own URDF names, as a recorded Stack bag carries them (the laser frame is
``lidar_link``). Nothing here imports ROS (``coco_lab`` never does, invariant 1);
``coco_lab_ros/test/test_m6f_ros_shapes.py`` fills the real Jazzy message classes
from these dicts, field for field, and compares them with a recorded Stack bag.

:func:`ros_graph` is the machine-readable graph the UI's "ROS graph" panel will
draw: nodes, the topics between them, message types and rates. These names
*teach*; they are never a control path (invariant 2: nothing here reaches COCO's
Stack).

Frames: ``map`` is the Arena's map frame; ``odom`` is where the robot started
(the model's wheel odometry, ``Arena.odom``, once the whole loop is on; else the
truth relative to the start pose); ``base_footprint`` is the robot; ``base_link``
sits ``robot.ground_clearance`` above it and ``lidar_link`` at ``robot.lidar.mount``
in ``base_link`` (``coco_robo2.xacro``'s joints, as recorded).
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .maps import FREE, OCCUPIED

#: the frames, as COCO's URDF and a recorded Stack bag name them
FRAMES = ('map', 'odom', 'base_footprint', 'base_link', 'lidar_link')
LASER_FRAME = 'lidar_link'
#: nav_msgs/OccupancyGrid's cell values (map_server's trinary mode)
GRID_FREE, GRID_OCCUPIED, GRID_UNKNOWN = 0, 100, -1


def stamp(t: float) -> Dict[str, int]:
    """Return a builtin_interfaces/Time for ``t`` seconds (model time)."""
    sec = math.floor(t)
    nanosec = int(round((t - sec) * 1e9))
    if nanosec >= 1_000_000_000:
        sec, nanosec = sec + 1, nanosec - 1_000_000_000
    return {'sec': int(sec), 'nanosec': nanosec}


def header(t: float, frame_id: str) -> Dict[str, object]:
    """Return a std_msgs/Header."""
    return {'stamp': stamp(t), 'frame_id': frame_id}


def quaternion(yaw: float, pitch: float = 0.0, roll: float = 0.0) -> Dict[str, float]:
    """Return a geometry_msgs/Quaternion for ZYX Euler angles (REP-103)."""
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    return {'x': sr * cp * cy - cr * sp * sy, 'y': cr * sp * cy + sr * cp * sy,
            'z': cr * cp * sy - sr * sp * cy, 'w': cr * cp * cy + sr * sp * sy}


def point(x: float, y: float, z: float = 0.0) -> Dict[str, float]:
    """Return a geometry_msgs/Point (or Vector3: the same fields)."""
    return {'x': float(x), 'y': float(y), 'z': float(z)}


def pose(x: float, y: float, yaw: float, z: float = 0.0) -> Dict[str, object]:
    """Return a geometry_msgs/Pose."""
    return {'position': point(x, y, z), 'orientation': quaternion(yaw)}


# -- the messages ---------------------------------------------------------------------

def laser_scan(a, t: Optional[float] = None) -> Dict[str, object]:
    """
    Return the Arena's current scan as a sensor_msgs/LaserScan (frame ``lidar_link``).

    ``time_increment`` and ``scan_time`` are 0, as Gazebo's LiDAR publishes them
    (recorded); ``intensities`` is empty: the model computes none (the Stack's are
    480 values).
    """
    li = a.lidar
    n = len(a.ranges)
    inc = (li.angle_max - li.angle_min) / (n - 1) if n > 1 else 0.0
    return {'header': header(a.t_world if t is None else t, LASER_FRAME),
            'angle_min': li.angle_min, 'angle_max': li.angle_max, 'angle_increment': inc,
            'time_increment': 0.0, 'scan_time': 0.0,
            'range_min': li.range_min, 'range_max': li.range_max,
            'ranges': [float(r) for r in a.ranges], 'intensities': []}


def occupancy_grid(lab_map, t: float = 0.0) -> Dict[str, object]:
    """
    Return a LabMap as a nav_msgs/OccupancyGrid (frame ``map``).

    ROS's grid is row-major from the cell at the origin, y growing with the row;
    a LabMap's row 0 is the top, so the rows are flipped.
    """
    w, h = lab_map.width, lab_map.height
    occ = lab_map.occupancy
    val = {FREE: GRID_FREE, OCCUPIED: GRID_OCCUPIED}
    data = []
    for row in range(h - 1, -1, -1):
        data.extend(val.get(c, GRID_UNKNOWN) for c in occ[row * w:(row + 1) * w])
    ox, oy = lab_map.origin
    return {'header': header(t, 'map'),
            'info': {'map_load_time': stamp(t), 'resolution': lab_map.resolution,
                     'width': w, 'height': h, 'origin': pose(ox, oy, 0.0)},
            'data': data}


def twist(v: float, w: float) -> Dict[str, object]:
    """Return a geometry_msgs/Twist: COCO only drives forward and turns in place."""
    return {'linear': point(v, 0.0, 0.0), 'angular': point(0.0, 0.0, w)}


def twist_stamped(v: float, w: float, t: float) -> Dict[str, object]:
    """Return a geometry_msgs/TwistStamped as cmd_vel_arbiter publishes it (empty frame)."""
    return {'header': header(t, ''), 'twist': twist(v, w)}


def path(points: Sequence[Tuple[float, float]], t: float,
         yaws: Optional[Sequence[float]] = None) -> Dict[str, object]:
    """
    Return a nav_msgs/Path (frame ``map``).

    Each pose faces the next point unless ``yaws`` is given (the last faces as
    the one before it).
    """
    poses = []
    for i, (x, y) in enumerate(points):
        if yaws is not None:
            yaw = yaws[i]
        elif i + 1 < len(points):
            yaw = math.atan2(points[i + 1][1] - y, points[i + 1][0] - x)
        elif i > 0:
            yaw = math.atan2(y - points[i - 1][1], x - points[i - 1][0])
        else:
            yaw = 0.0
        poses.append({'header': header(t, 'map'), 'pose': pose(x, y, yaw)})
    return {'header': header(t, 'map'), 'poses': poses}


def _cov(diag: Sequence[float]) -> List[float]:
    c = [0.0] * 36
    for i, d in enumerate(diag):
        c[i * 7] = float(d)
    return c


def odom_pose(a) -> Tuple[float, float, float]:
    """Return the robot in the ``odom`` frame: wheel odometry, or truth from the start."""
    if a.loop:
        return a.odom
    sx, sy, sth = a.start
    x, y, th = a.pose
    c, s = math.cos(sth), math.sin(sth)
    dx, dy = x - sx, y - sy
    return (c * dx + s * dy, -s * dx + c * dy,
            math.atan2(math.sin(th - sth), math.cos(th - sth)))


def odometry(a) -> Dict[str, object]:
    """
    Return a nav_msgs/Odometry (``odom`` -> ``base_footprint``).

    The model publishes no covariance it has not computed: both are zero.
    """
    x, y, th = odom_pose(a)
    return {'header': header(a.t_world, 'odom'), 'child_frame_id': 'base_footprint',
            'pose': {'pose': pose(x, y, th), 'covariance': _cov([0.0] * 6)},
            'twist': {'twist': twist(a.v, a.w), 'covariance': _cov([0.0] * 6)}}


def transform(parent: str, child: str, t: float, x: float, y: float, yaw: float,
              z: float = 0.0) -> Dict[str, object]:
    """Return a geometry_msgs/TransformStamped."""
    return {'header': header(t, parent), 'child_frame_id': child,
            'transform': {'translation': point(x, y, z), 'rotation': quaternion(yaw)}}


def tf(a) -> Dict[str, object]:
    """
    Return the dynamic frames as a tf2_msgs/TFMessage: map -> odom -> base_footprint.

    ``map -> odom`` places the odometry pose on the robot's pose in the map (the
    belief, when a localiser runs: what AMCL would publish).
    """
    t = a.t_world
    ox, oy, oth = odom_pose(a)
    bx, by, bth = a.belief()
    mth = bth - oth
    c, s = math.cos(mth), math.sin(mth)
    mx, my = bx - (c * ox - s * oy), by - (s * ox + c * oy)
    mth = math.atan2(math.sin(mth), math.cos(mth))
    return {'transforms': [transform('map', 'odom', t, mx, my, mth),
                           transform('odom', 'base_footprint', t, ox, oy, oth)]}


def tf_static(a) -> Dict[str, object]:
    """Return ``base_footprint -> base_link -> lidar_link`` as a tf2_msgs/TFMessage."""
    mx, my, mz = a.spec['robot']['lidar']['mount']
    gc = a.spec['robot']['ground_clearance']
    return {'transforms': [transform('base_footprint', 'base_link', 0.0, 0.0, 0.0, 0.0, gc),
                           transform('base_link', LASER_FRAME, 0.0, mx, my, 0.0, mz)]}


# -- the graph the panel draws ----------------------------------------------------------------

def ros_graph(dt: float = 0.1) -> Dict[str, object]:
    """
    Return the model's ROS graph: nodes, topics, types and rates.

    Rates are the model's: one tick is ``dt`` (10 Hz); ``/map`` and
    ``/tf_static`` are latched (transient local) and published once; ``/plan``
    on each new plan; teleop on each input. Node names are the Stack's roles.
    """
    hz = round(1.0 / dt, 9)
    topics = [
        ('/scan', 'sensor_msgs/msg/LaserScan', 'lidar', ['slam_or_amcl', 'local_controller'],
         hz, LASER_FRAME),
        ('/odom', 'nav_msgs/msg/Odometry', 'diff_drive', ['slam_or_amcl', 'local_controller'],
         hz, 'odom'),
        ('/map', 'nav_msgs/msg/OccupancyGrid', 'map_server', ['global_planner'], None, 'map'),
        ('/plan', 'nav_msgs/msg/Path', 'global_planner', ['local_controller'], 'on_plan',
         'map'),
        ('/cmd_vel', 'geometry_msgs/msg/TwistStamped', 'cmd_vel_arbiter', ['diff_drive'], hz,
         ''),
        ('/cmd_vel_nav', 'geometry_msgs/msg/TwistStamped', 'local_controller',
         ['cmd_vel_arbiter'], hz, ''),
        ('/cmd_vel_teleop', 'geometry_msgs/msg/TwistStamped', 'teleop', ['cmd_vel_arbiter'],
         'on_input', ''),
        ('/tf', 'tf2_msgs/msg/TFMessage', 'slam_or_amcl', ['global_planner', 'local_controller'],
         hz, None),
        ('/tf_static', 'tf2_msgs/msg/TFMessage', 'robot_state_publisher',
         ['slam_or_amcl', 'local_controller'], None, None),
    ]
    nodes = sorted({t[2] for t in topics} | {s for t in topics for s in t[3]})
    return {'schema': 'coco_lab.ros_graph', 'version': 1, 'evidence': 'MODEL',
            'note': 'ROS-shaped: the model speaks these message shapes; nothing here is '
                    'a ROS connection (README invariant 2)',
            'frames': list(FRAMES),
            'tf_tree': [['map', 'odom'], ['odom', 'base_footprint'],
                        ['base_footprint', 'base_link'], ['base_link', LASER_FRAME]],
            'nodes': nodes,
            'topics': [{'name': n, 'type': ty, 'publisher': p, 'subscribers': subs,
                        'rate_hz': r if isinstance(r, float) else None,
                        'when': 'latched' if r is None
                        else ('periodic' if isinstance(r, float) else r),
                        'frame_id': f} for n, ty, p, subs, r, f in topics]}
