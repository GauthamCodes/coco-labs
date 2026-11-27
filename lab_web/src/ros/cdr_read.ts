// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.2: ROS 2 messages FROM CDR bytes (little endian, XCDR1), the inverse of src/ros/cdr.ts: what
 * foxglove_bridge sends for a LIVE stack's topics (encoding "cdr"). Each type is read field by
 * field in its .msg order, with the writer's alignment rule (counted from the end of the 4-byte
 * encapsulation header). Tested by round trips through the writer, whose bytes equal rclpy's
 * (test/g2_cdr.test.ts), and on hand-built bytes for the types the writer does not have.
 * Evidence: what this decodes is LIVE data only while a real stack is connected.
 */

import type { Header, LaserScan, Odometry, OccupancyGrid, Path, Pose, Quat, TFMessage, Time, TransformStamped, Twist, TwistStamped, Vec3 } from './shapes';
import type { JointState } from './cdr';

export interface PoseWithCovarianceStamped { header: Header; pose: { pose: Pose; covariance: number[] } }

const dec = new TextDecoder();

export class CdrReader {
  private view: DataView;
  private pos = 4;

  constructor(private bytes: Uint8Array) {
    if (bytes.length < 4) throw new Error('CDR: shorter than its encapsulation header');
    // 0x0001 = CDR little endian (what ROS 2 Jazzy's rmw writes); big endian is refused, not guessed
    if (bytes[0] !== 0x00 || bytes[1] !== 0x01) throw new Error(`CDR: unsupported encapsulation 0x${bytes[0].toString(16)}${bytes[1].toString(16)}`);
    this.view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  }

  private align(n: number) { this.pos += (n - ((this.pos - 4) % n)) % n; }
  private need(n: number) { if (this.pos + n > this.bytes.length) throw new Error(`CDR: truncated at byte ${this.pos} (need ${n})`); }

  int8() { this.need(1); const v = this.view.getInt8(this.pos); this.pos += 1; return v; }
  int32() { this.align(4); this.need(4); const v = this.view.getInt32(this.pos, true); this.pos += 4; return v; }
  uint32() { this.align(4); this.need(4); const v = this.view.getUint32(this.pos, true); this.pos += 4; return v; }
  float32() { this.align(4); this.need(4); const v = this.view.getFloat32(this.pos, true); this.pos += 4; return v; }
  float64() { this.align(8); this.need(8); const v = this.view.getFloat64(this.pos, true); this.pos += 8; return v; }
  string() {
    const n = this.uint32();                 // length including the terminating NUL
    if (n === 0) return '';
    this.need(n);
    const s = dec.decode(this.bytes.subarray(this.pos, this.pos + n - 1));
    this.pos += n;
    return s;
  }
  seq<T>(each: () => T): T[] {
    const n = this.uint32();
    if (n > this.bytes.length) throw new Error(`CDR: a sequence of ${n} in ${this.bytes.length} bytes`);
    const out: T[] = new Array(n);
    for (let k = 0; k < n; k++) out[k] = each();
    return out;
  }
  /** a float32 sequence as a typed array (LaserScan.ranges: hundreds per message, 10 Hz) */
  float32Seq(): Float32Array {
    const n = this.uint32();
    this.align(4);
    this.need(n * 4);
    const out = new Float32Array(n);
    for (let k = 0; k < n; k++) out[k] = this.view.getFloat32(this.pos + 4 * k, true);
    this.pos += n * 4;
    return out;
  }
  /** an int8 sequence (OccupancyGrid.data) */
  int8Seq(): Int8Array {
    const n = this.uint32();
    this.need(n);
    const out = new Int8Array(this.bytes.buffer.slice(this.bytes.byteOffset + this.pos, this.bytes.byteOffset + this.pos + n));
    this.pos += n;
    return out;
  }
  get offset() { return this.pos; }
}

const time = (r: CdrReader): Time => ({ sec: r.int32(), nanosec: r.uint32() });
const header = (r: CdrReader): Header => ({ stamp: time(r), frame_id: r.string() });
const vec3 = (r: CdrReader): Vec3 => ({ x: r.float64(), y: r.float64(), z: r.float64() });
const quat = (r: CdrReader): Quat => ({ x: r.float64(), y: r.float64(), z: r.float64(), w: r.float64() });
const pose = (r: CdrReader): Pose => ({ position: vec3(r), orientation: quat(r) });
const twist = (r: CdrReader): Twist => ({ linear: vec3(r), angular: vec3(r) });
const cov36 = (r: CdrReader): number[] => { const c = new Array(36); for (let k = 0; k < 36; k++) c[k] = r.float64(); return c; };
const transformStamped = (r: CdrReader): TransformStamped => {
  const h = header(r); const child = r.string();
  return { header: h, child_frame_id: child, transform: { translation: vec3(r), rotation: quat(r) } };
};

/** LaserScan whose ranges/intensities are typed arrays (shapes.LaserScan's fields are ArrayLike-compatible) */
export type LaserScanIn = Omit<LaserScan, 'ranges' | 'intensities'> & { ranges: Float32Array; intensities: Float32Array };
export type OccupancyGridIn = Omit<OccupancyGrid, 'data'> & { data: Int8Array };

export const DESERIALIZE: Record<string, (r: CdrReader) => unknown> = {
  'sensor_msgs/msg/LaserScan': (r): LaserScanIn => {
    const h = header(r);
    const [angle_min, angle_max, angle_increment, time_increment, scan_time, range_min, range_max] =
      [r.float32(), r.float32(), r.float32(), r.float32(), r.float32(), r.float32(), r.float32()];
    return { header: h, angle_min, angle_max, angle_increment, time_increment, scan_time, range_min, range_max,
      ranges: r.float32Seq(), intensities: r.float32Seq() };
  },
  'nav_msgs/msg/Odometry': (r): Odometry => {
    const h = header(r); const child = r.string();
    const p = pose(r); const pc = cov36(r);
    const t = twist(r); const tc = cov36(r);
    return { header: h, child_frame_id: child, pose: { pose: p, covariance: pc }, twist: { twist: t, covariance: tc } };
  },
  'geometry_msgs/msg/TwistStamped': (r): TwistStamped => ({ header: header(r), twist: twist(r) }),
  'geometry_msgs/msg/PoseWithCovarianceStamped': (r): PoseWithCovarianceStamped => {
    const h = header(r); const p = pose(r);
    return { header: h, pose: { pose: p, covariance: cov36(r) } };
  },
  'nav_msgs/msg/Path': (r): Path => {
    const h = header(r);
    return { header: h, poses: r.seq(() => { const ph = header(r); return { header: ph, pose: pose(r) }; }) };
  },
  'tf2_msgs/msg/TFMessage': (r): TFMessage => ({ transforms: r.seq(() => transformStamped(r)) }),
  'nav_msgs/msg/OccupancyGrid': (r): OccupancyGridIn => {
    const h = header(r);
    const map_load_time = time(r); const resolution = r.float32(); const width = r.uint32(); const height = r.uint32();
    const origin = pose(r);
    return { header: h, info: { map_load_time, resolution, width, height, origin }, data: r.int8Seq() };
  },
  'sensor_msgs/msg/JointState': (r): JointState => {
    const h = header(r);
    return { header: h, name: r.seq(() => r.string()), position: r.seq(() => r.float64()),
      velocity: r.seq(() => r.float64()), effort: r.seq(() => r.float64()) };
  },
};

/** The ROS 2 types this reader can decode. */
export const READABLE = Object.keys(DESERIALIZE);

/** One `type` message from CDR bytes (the encapsulation header first). */
export function deserialize<T = unknown>(type: string, bytes: Uint8Array): T {
  const f = DESERIALIZE[type];
  if (!f) throw new Error(`no CDR reader for ${type}`);
  return f(new CdrReader(bytes)) as T;
}
