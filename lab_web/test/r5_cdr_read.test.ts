// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.2: the browser's CDR READER (src/ros/cdr_read.ts) decodes ROS 2 Jazzy's own bytes: every
 * rclpy golden the writer is held to (test/fixtures/cdr_goldens.json) plus the LIVE-only types
 * (test/fixtures/cdr_goldens_r5.json, rclpy on the laptop) decode back to the message they came from,
 * and the writer's output round-trips. Malformed bytes are refused, never guessed.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { serialize } from '../src/ros/cdr';
import { deserialize, READABLE } from '../src/ros/cdr_read';

type Golden = { samples: { type: string; what: string; msg: unknown; cdr: string }[] };
const G = JSON.parse(readFileSync(new URL('./fixtures/cdr_goldens.json', import.meta.url), 'utf-8')) as Golden;
const G5 = JSON.parse(readFileSync(new URL('./fixtures/cdr_goldens_r5.json', import.meta.url), 'utf-8')) as Golden;

const inf = (x: unknown): unknown => (x === null ? Infinity : Array.isArray(x) ? x.map(inf) : x && typeof x === 'object' ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, inf(v)])) : x);
const unhex = (h: string) => Uint8Array.from(h.match(/../g) ?? [], (b) => parseInt(b, 16));
/** typed arrays as plain arrays, and float32 fields compared at float32 precision */
const plain = (x: unknown): unknown => (ArrayBuffer.isView(x) ? Array.from(x as unknown as ArrayLike<number>) : Array.isArray(x) ? x.map(plain)
  : x && typeof x === 'object' ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, plain(v)])) : x);
const F32 = new Set(['angle_min', 'angle_max', 'angle_increment', 'time_increment', 'scan_time', 'range_min', 'range_max', 'resolution', 'ranges', 'intensities']);
const f32 = (x: unknown, key = ''): unknown => (Array.isArray(x) ? x.map((v) => f32(v, key)) : typeof x === 'number' && F32.has(key) ? Math.fround(x)
  : x && typeof x === 'object' ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, f32(v, k)])) : x);

describe('the CDR reader decodes ROS 2 Jazzy\'s bytes', () => {
  for (const s of [...G.samples, ...G5.samples]) {
    it(`${s.type}: ${s.what}`, () => {
      const got = plain(deserialize(s.type, unhex(s.cdr)));
      expect(got).toEqual(f32(inf(s.msg)));
    });
  }

  it('reads every type the writer writes, and AMCL\'s pose', () => {
    for (const s of G.samples) expect(READABLE).toContain(s.type);
    expect(READABLE).toContain('geometry_msgs/msg/PoseWithCovarianceStamped');
  });

  it('round-trips the writer', () => {
    for (const s of G.samples) {
      const bytes = serialize(s.type, inf(s.msg));
      expect(plain(deserialize(s.type, bytes))).toEqual(f32(inf(s.msg)));
    }
  });

  it('refuses truncated bytes, big-endian encapsulation and unknown types', () => {
    const s = G.samples.find((x) => x.type === 'nav_msgs/msg/Odometry')!;
    const b = unhex(s.cdr);
    expect(() => deserialize(s.type, b.subarray(0, b.length - 8))).toThrow(/truncated/);
    const be = b.slice(); be[1] = 0x00;
    expect(() => deserialize(s.type, be)).toThrow(/encapsulation/);
    expect(() => deserialize('std_msgs/msg/Nope', b)).toThrow(/no CDR reader/);
  });
});
