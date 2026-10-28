// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.5: ROS 2 messages as CDR bytes (little endian, XCDR1 -- what rosbag2 stores and
 * `ros2 bag play` publishes), for the browser model's messages (src/ros/shapes.ts). Each type is
 * written field by field in its .msg order (src/ros/msgdefs.json holds the definitions); the
 * bytes must equal rclpy.serialization.serialize_message's (test/g2_cdr.test.ts, goldens from
 * ROS 2 Jazzy). Alignment counts from the end of the 4-byte encapsulation header.
 */

import type { LaserScan, Odometry, OccupancyGrid, Path, Pose, Quat, Time, TFMessage, TransformStamped, TwistStamped, Vec3, Header, Twist } from './shapes';

export interface JointState { header: Header; name: string[]; position: number[]; velocity: number[]; effort: number[] }

const enc = new TextEncoder();

export class CdrWriter {
  private buf: Uint8Array;
  private view: DataView;
  private pos = 4;

  constructor(size = 256) {
    this.buf = new Uint8Array(Math.max(8, size));
    this.view = new DataView(this.buf.buffer);
    this.buf.set([0x00, 0x01, 0x00, 0x00]);   // CDR_LE encapsulation, options 0
  }

  private room(n: number) {
    if (this.pos + n <= this.buf.length) return;
    let size = this.buf.length * 2;
    while (size < this.pos + n) size *= 2;
    const b = new Uint8Array(size);
    b.set(this.buf.subarray(0, this.pos));
    this.buf = b;
    this.view = new DataView(b.buffer);
  }

  private align(n: number) {
    const pad = (n - ((this.pos - 4) % n)) % n;
    this.room(pad);
    for (let k = 0; k < pad; k++) this.buf[this.pos++] = 0;
  }

  int8(v: number) { this.room(1); this.view.setInt8(this.pos, v); this.pos += 1; return this; }
  int32(v: number) { this.align(4); this.room(4); this.view.setInt32(this.pos, v, true); this.pos += 4; return this; }
  uint32(v: number) { this.align(4); this.room(4); this.view.setUint32(this.pos, v, true); this.pos += 4; return this; }
  float32(v: number) { this.align(4); this.room(4); this.view.setFloat32(this.pos, v, true); this.pos += 4; return this; }
  float64(v: number) { this.align(8); this.room(8); this.view.setFloat64(this.pos, v, true); this.pos += 8; return this; }
  string(s: string) {
    const b = enc.encode(s);
    this.uint32(b.length + 1);
    this.room(b.length + 1);
    this.buf.set(b, this.pos);
    this.pos += b.length;
    this.buf[this.pos++] = 0;
    return this;
  }
  /** a sequence: its length, then each element */
  seq<T>(xs: ArrayLike<T>, each: (x: T) => void) { this.uint32(xs.length); for (let k = 0; k < xs.length; k++) each(xs[k]); return this; }

  bytes(): Uint8Array { return this.buf.slice(0, this.pos); }
}

const time = (w: CdrWriter, t: Time) => { w.int32(t.sec); w.uint32(t.nanosec); };
const header = (w: CdrWriter, h: Header) => { time(w, h.stamp); w.string(h.frame_id); };
const vec3 = (w: CdrWriter, v: Vec3) => { w.float64(v.x); w.float64(v.y); w.float64(v.z); };
const quat = (w: CdrWriter, q: Quat) => { w.float64(q.x); w.float64(q.y); w.float64(q.z); w.float64(q.w); };
const pose = (w: CdrWriter, p: Pose) => { vec3(w, p.position); quat(w, p.orientation); };
const twist = (w: CdrWriter, t: Twist) => { vec3(w, t.linear); vec3(w, t.angular); };
const cov36 = (w: CdrWriter, c: number[]) => { if (c.length !== 36) throw new Error('a covariance is 36 values'); for (const x of c) w.float64(x); };
const transformStamped = (w: CdrWriter, t: TransformStamped) => { header(w, t.header); w.string(t.child_frame_id); vec3(w, t.transform.translation); quat(w, t.transform.rotation); };

export const SERIALIZE: Record<string, (w: CdrWriter, m: never) => void> = {
  'sensor_msgs/msg/LaserScan': (w, m: LaserScan) => {
    header(w, m.header);
    for (const x of [m.angle_min, m.angle_max, m.angle_increment, m.time_increment, m.scan_time, m.range_min, m.range_max]) w.float32(x);
    w.seq(m.ranges, (x) => w.float32(x));
    w.seq(m.intensities, (x) => w.float32(x));
  },
  'nav_msgs/msg/Odometry': (w, m: Odometry) => {
    header(w, m.header); w.string(m.child_frame_id);
    pose(w, m.pose.pose); cov36(w, m.pose.covariance);
    twist(w, m.twist.twist); cov36(w, m.twist.covariance);
  },
  'geometry_msgs/msg/TwistStamped': (w, m: TwistStamped) => { header(w, m.header); twist(w, m.twist); },
  'nav_msgs/msg/Path': (w, m: Path) => { header(w, m.header); w.seq(m.poses, (p) => { header(w, p.header); pose(w, p.pose); }); },
  'tf2_msgs/msg/TFMessage': (w, m: TFMessage) => { w.seq(m.transforms, (t) => transformStamped(w, t)); },
  'nav_msgs/msg/OccupancyGrid': (w, m: OccupancyGrid) => {
    header(w, m.header);
    time(w, m.info.map_load_time); w.float32(m.info.resolution); w.uint32(m.info.width); w.uint32(m.info.height); pose(w, m.info.origin);
    w.seq(m.data, (x) => w.int8(x));
  },
  'sensor_msgs/msg/JointState': (w, m: JointState) => {
    header(w, m.header);
    w.seq(m.name, (s) => w.string(s));
    w.seq(m.position, (x) => w.float64(x)); w.seq(m.velocity, (x) => w.float64(x)); w.seq(m.effort, (x) => w.float64(x));
  },
};

/** One message of `type` as CDR bytes (the encapsulation header first). */
export function serialize(type: string, msg: unknown, sizeHint = 256): Uint8Array {
  const f = SERIALIZE[type];
  if (!f) throw new Error(`no CDR writer for ${type}`);
  const w = new CdrWriter(sizeHint);
  (f as (w: CdrWriter, m: unknown) => void)(w, msg);
  return w.bytes();
}
