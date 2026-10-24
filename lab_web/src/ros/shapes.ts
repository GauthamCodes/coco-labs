// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.2: the ROS-shaped model, on the page (MODEL). A second implementation of
 * coco_lab/coco_lab/ros_shapes.py (M6F.7) for what the page already has: each function
 * builds exactly the dict ros_shapes builds, field for field (test/g2_ros_shapes.test.ts
 * checks them against Python's on a recorded session, lab_web/test/fixtures/ros_shapes_parity.json).
 *
 * These are ROS 2 message SHAPES -- the fields of sensor_msgs/LaserScan, nav_msgs/Odometry,
 * ... with COCO's real frame names -- built from the browser model's own state. Nothing here
 * is ROS 2 or talks to it (README invariant 2). The dynamic frames come from the worker, where
 * ros_shapes computes them (arena_glue `ros.tf`); the page never re-derives a pose.
 */

export interface Time { sec: number; nanosec: number }
export interface Header { stamp: Time; frame_id: string }
export interface Vec3 { x: number; y: number; z: number }
export interface Quat { x: number; y: number; z: number; w: number }
export interface Pose { position: Vec3; orientation: Quat }
export interface TransformStamped { header: Header; child_frame_id: string; transform: { translation: Vec3; rotation: Quat } }
export interface TFMessage { transforms: TransformStamped[] }
export interface LaserScan { header: Header; angle_min: number; angle_max: number; angle_increment: number; time_increment: number; scan_time: number; range_min: number; range_max: number; ranges: number[]; intensities: number[] }
export interface Twist { linear: Vec3; angular: Vec3 }
export interface TwistStamped { header: Header; twist: Twist }
export interface PoseStamped { header: Header; pose: Pose }
export interface Path { header: Header; poses: PoseStamped[] }
export interface Odometry { header: Header; child_frame_id: string; pose: { pose: Pose; covariance: number[] }; twist: { twist: Twist; covariance: number[] } }
export interface MapMetaData { map_load_time: Time; resolution: number; width: number; height: number; origin: Pose }
export interface OccupancyGrid { header: Header; info: MapMetaData; data: number[] }

/** What the worker sends once (arena_glue `_ros_info`): from ros_shapes itself. */
export interface RosTopic { name: string; type: string; publisher: string; subscribers: string[]; rate_hz: number | null; when: string; frame_id: string | null }
export interface RosGraph { schema: string; version: number; evidence: 'MODEL'; note: string; frames: string[]; tf_tree: [string, string][]; nodes: string[]; topics: RosTopic[] }
export interface RosInfo {
  graph: RosGraph; tf_static: TFMessage; frames: string[];
  scan: { frame_id: string; angle_min: number; angle_max: number; range_min: number; range_max: number };
}

/** nav_msgs/OccupancyGrid's cell values (map_server's trinary mode); a LabMap's codes (coco_lab.maps) */
export const GRID_FREE = 0, GRID_OCCUPIED = 100, GRID_UNKNOWN = -1;
const LAB_FREE = 0, LAB_OCCUPIED = 1;

/** Python's round(): halves to even. */
function roundHalfEven(x: number): number {
  const f = Math.floor(x), d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

/** builtin_interfaces/Time for `t` seconds of model time (ros_shapes.stamp). */
export function stamp(t: number): Time {
  let sec = Math.floor(t);
  let nanosec = roundHalfEven((t - sec) * 1e9);
  if (nanosec >= 1_000_000_000) { sec += 1; nanosec -= 1_000_000_000; }
  return { sec, nanosec };
}

export const header = (t: number, frame_id: string): Header => ({ stamp: stamp(t), frame_id });

/** geometry_msgs/Quaternion for a yaw (pitch and roll 0, as COCO's planar model has them). */
export function quaternion(yaw: number): Quat {
  // ros_shapes.quaternion with pitch = roll = 0 (cp = cr = 1, sp = sr = 0): x and y are zero
  // (Python may write -0.0 there; numerically the same, and the parity test compares numbers)
  const cy = Math.cos(yaw / 2), sy = Math.sin(yaw / 2);
  return { x: 0, y: 0, z: sy, w: cy };
}

export const point = (x: number, y: number, z = 0): Vec3 => ({ x, y, z });
export const pose = (x: number, y: number, yaw: number, z = 0): Pose => ({ position: point(x, y, z), orientation: quaternion(yaw) });

/** sensor_msgs/LaserScan (frame lidar_link): the model's ranges; no intensities (it computes none). */
export function laserScan(info: RosInfo['scan'], ranges: ArrayLike<number>, t: number): LaserScan {
  const n = ranges.length;
  const inc = n > 1 ? (info.angle_max - info.angle_min) / (n - 1) : 0;
  return { header: header(t, info.frame_id), angle_min: info.angle_min, angle_max: info.angle_max, angle_increment: inc,
    time_increment: 0, scan_time: 0, range_min: info.range_min, range_max: info.range_max,
    ranges: Array.from(ranges, Number), intensities: [] };
}

/** nav_msgs/OccupancyGrid (frame map) from the world's LabMap: rows flipped (ROS's row 0 is at the origin). */
export function occupancyGrid(map: { width: number; height: number; resolution: number; origin: [number, number] }, occupancy: ArrayLike<number>, t = 0): OccupancyGrid {
  const { width: w, height: h } = map;
  const data = new Array<number>(w * h);
  let k = 0;
  for (let row = h - 1; row >= 0; row--) {
    for (let c = 0; c < w; c++) {
      const v = occupancy[row * w + c];
      data[k++] = v === LAB_FREE ? GRID_FREE : v === LAB_OCCUPIED ? GRID_OCCUPIED : GRID_UNKNOWN;
    }
  }
  return { header: header(t, 'map'), info: { map_load_time: stamp(t), resolution: map.resolution, width: w, height: h, origin: pose(map.origin[0], map.origin[1], 0) }, data };
}

export const twist = (v: number, w: number): Twist => ({ linear: point(v, 0, 0), angular: point(0, 0, w) });
/** geometry_msgs/TwistStamped as cmd_vel_arbiter publishes it (empty frame). */
export const twistStamped = (v: number, w: number, t: number): TwistStamped => ({ header: header(t, ''), twist: twist(v, w) });

/** nav_msgs/Path (frame map): each pose faces the next point (the last faces as the one before). */
export function path(points: [number, number][], t: number): Path {
  const poses: PoseStamped[] = points.map(([x, y], i) => {
    let yaw = 0;
    if (i + 1 < points.length) yaw = Math.atan2(points[i + 1][1] - y, points[i + 1][0] - x);
    else if (i > 0) yaw = Math.atan2(y - points[i - 1][1], x - points[i - 1][0]);
    return { header: header(t, 'map'), pose: pose(x, y, yaw) };
  });
  return { header: header(t, 'map'), poses };
}

const ZERO36 = () => new Array<number>(36).fill(0);

/**
 * nav_msgs/Odometry (odom -> base_footprint): the pose is the worker's odom -> base_footprint
 * transform (ros_shapes.odom_pose), the twist the tick's (v, w); no covariance (the model computes none).
 */
export function odometry(tf: TFMessage, v: number, w: number): Odometry {
  const ob = tf.transforms.find((x) => x.header.frame_id === 'odom' && x.child_frame_id === 'base_footprint')!;
  const tr = ob.transform;
  return { header: ob.header, child_frame_id: 'base_footprint',
    pose: { pose: { position: { ...tr.translation }, orientation: { ...tr.rotation } }, covariance: ZERO36() },
    twist: { twist: twist(v, w), covariance: ZERO36() } };
}

/** A frame's pose in `map` (x, y, yaw), composing the planar transforms map -> ... -> frame. */
export function framePose(frame: string, tf: TFMessage, tfStatic: TFMessage): [number, number, number] | null {
  const all = [...tf.transforms, ...tfStatic.transforms];
  const chain: TransformStamped[] = [];
  let at = frame;
  while (at !== 'map') {
    const t = all.find((x) => x.child_frame_id === at);
    if (!t) return null;
    chain.unshift(t);
    at = t.header.frame_id;
  }
  let x = 0, y = 0, th = 0;
  for (const t of chain) {
    const { translation: p, rotation: q } = t.transform;
    const c = Math.cos(th), s = Math.sin(th);
    x += c * p.x - s * p.y; y += s * p.x + c * p.y;
    th += 2 * Math.atan2(q.z, q.w);
  }
  return [x, y, Math.atan2(Math.sin(th), Math.cos(th))];
}

/** Yaw of a planar quaternion (rad). */
export const yawOf = (q: Quat) => 2 * Math.atan2(q.z, q.w);
