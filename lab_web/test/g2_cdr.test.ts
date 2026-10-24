// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.5: the browser's CDR writer (src/ros/cdr.ts) gives exactly the bytes ROS 2 Jazzy's
 * rclpy.serialization.serialize_message gives, for every message type the rosbag2 export writes
 * (goldens: tools/g2/gen_msgdefs.py, test/fixtures/cdr_goldens.json).
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { serialize, SERIALIZE } from '../src/ros/cdr';

const G = JSON.parse(readFileSync(new URL('./fixtures/cdr_goldens.json', import.meta.url), 'utf-8')) as { samples: { type: string; what: string; msg: unknown; cdr: string }[] };
const DEFS = JSON.parse(readFileSync(new URL('../src/ros/msgdefs.json', import.meta.url), 'utf-8')) as Record<string, { encoding: string; text: string; type_hash: string }>;

/** null in the fixture is a no-return beam: +inf (JSON has no infinity) */
const inf = (x: unknown): unknown => (x === null ? Infinity : Array.isArray(x) ? x.map(inf) : x && typeof x === 'object' ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, inf(v)])) : x);
const hex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');

describe('CDR bytes equal ROS 2 Jazzy\'s', () => {
  it('covers every type the export writes, each with a definition and a type hash', () => {
    expect(Object.keys(SERIALIZE).sort()).toEqual(Object.keys(DEFS).sort());
    for (const [t, d] of Object.entries(DEFS)) {
      expect(d.encoding, t).toBe('ros2msg');
      expect(d.type_hash, t).toMatch(/^RIHS01_[0-9a-f]{64}$/);
    }
    expect(new Set(G.samples.map((s) => s.type))).toEqual(new Set(Object.keys(DEFS)));
  });

  for (const s of G.samples) {
    it(`${s.type}: ${s.what}`, () => {
      expect(hex(serialize(s.type, inf(s.msg)))).toBe(s.cdr);
    });
  }
});
