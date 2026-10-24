// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.5: the rosbag2 export (src/ros/bag.ts). A bag written from the parity fixture's session
 * (real model ticks, Free Drive on the Depot) must equal the committed test/fixtures/g2_model_bag.mcap
 * byte for byte (so the ROS 2 test -- coco_lab_ros/test/test_g2_bag_export.py, which opens it with
 * rosbag2_py and deserialises every message into Jazzy's classes -- reads what the browser writes),
 * and must say what it is: profile ros2, cdr channels with QoS and type hashes, MODEL.
 * Regenerate the fixture with G2_UPDATE_BAG=1.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { McapStreamReader } from '@mcap/core';
import { describe, expect, it } from 'vitest';
import { BAG_TOPICS, writeBag } from '../src/ros/bag';
import type { Frame } from '../src/ros/recorder';
import type { RosInfo, TFMessage } from '../src/ros/shapes';

interface Row { page: { tick: number; t_world: number; v: number; w: number; ros: { tf: TFMessage }; plan: [number, number][] | null }; ranges?: (number | null)[] }
const F = JSON.parse(readFileSync(new URL('./fixtures/ros_shapes_parity.json', import.meta.url), 'utf-8')) as { info: RosInfo; ticks: Row[]; map: { width: number; height: number; resolution: number; origin: [number, number]; occupancy_rle: [number, number][] } };
const OUT = new URL('./fixtures/g2_model_bag.mcap', import.meta.url);
export const FILE = 'g2_model_bag.mcap';

/** the session as the page records it: each tick's frame (ranges: the last full scan on file) */
function frames(): Frame[] {
  let ranges = new Float32Array(480);
  return F.ticks.map((r, k) => {
    if (r.ranges) ranges = Float32Array.from(r.ranges.map((x) => (x === null ? Infinity : x)));
    const p = r.page;
    const pose: [number, number, number] = [p.ros.tf.transforms[1].transform.translation.x, p.ros.tf.transforms[1].transform.translation.y, 0];
    return { tick: p.tick, t: p.t_world, pose, v: p.v, w: p.w, source: k < 10 ? 'teleop' : 'planner', tf: p.ros.tf, ranges, plan: p.plan, goal: null, teleop: null,
      arm: k === 3 ? { joint1: 0.1, joint2: -0.2, finger_left: 0.3, finger_right: -0.3 } : null };
  });
}
function occupancy(): Uint8Array {
  const out: number[] = [];
  for (const [v, n] of F.map.occupancy_rle) for (let k = 0; k < n; k++) out.push(v);
  return Uint8Array.from(out);
}
export async function makeBag() {
  return writeBag(frames(), F.info, F.map, occupancy(), { game: 'free', seed: 0, world: 'depot', hashVersion: 3, app: 'G2 test', ticks: F.ticks.length, dropped: 0 }, FILE);
}

describe('Save as rosbag2 (MCAP)', () => {
  it('is deterministic and equals the committed fixture the ROS 2 test reads', async () => {
    const a = await makeBag(), b = await makeBag();
    expect(Buffer.from(a).equals(Buffer.from(b))).toBe(true);
    if (process.env.G2_UPDATE_BAG || !existsSync(OUT)) writeFileSync(OUT, a);
    expect(Buffer.from(a).equals(readFileSync(OUT)), 'test/fixtures/g2_model_bag.mcap is stale: G2_UPDATE_BAG=1').toBe(true);
  });

  it('is a rosbag2 MCAP file, labelled MODEL inside', async () => {
    const r = new McapStreamReader({ validateCrcs: true });
    r.append(await makeBag());
    const schemas = new Map<number, string>(), channels = new Map<number, { topic: string; meta: Map<string, string>; enc: string; schema: number }>();
    const meta = new Map<string, Map<string, string>>();
    const perTopic = new Map<string, bigint[]>();
    let profile = '';
    for (let rec; (rec = r.nextRecord());) {
      if (rec.type === 'Header') profile = rec.profile;
      if (rec.type === 'Schema') { schemas.set(rec.id, rec.name); expect(rec.encoding).toBe('ros2msg'); }
      if (rec.type === 'Channel') channels.set(rec.id, { topic: rec.topic, meta: rec.metadata, enc: rec.messageEncoding, schema: rec.schemaId });
      if (rec.type === 'Metadata') meta.set(rec.name, rec.metadata);
      if (rec.type === 'Message') {
        const c = channels.get(rec.channelId)!;
        expect(rec.logTime).toBe(rec.publishTime);
        // the CDR's header stamp is the log time (sim time)
        const v = new DataView(rec.data.buffer, rec.data.byteOffset);
        if (c.topic !== '/tf' && c.topic !== '/tf_static') expect(BigInt(v.getInt32(4, true)) * 1_000_000_000n + BigInt(v.getUint32(8, true))).toBe(rec.logTime);
        perTopic.set(c.topic, [...(perTopic.get(c.topic) ?? []), rec.logTime]);
      }
    }
    expect(profile).toBe('ros2');
    expect([...channels.values()].map((c) => c.topic).sort()).toEqual(BAG_TOPICS.map((t) => t.name).sort());
    for (const c of channels.values()) {
      expect(c.enc).toBe('cdr');
      expect(c.meta.get('topic_type_hash')).toMatch(/^RIHS01_/);
      expect(c.meta.get('offered_qos_profiles')).toContain(c.topic === '/map' || c.topic === '/tf_static' ? 'durability: transient_local' : 'durability: volatile');
    }
    expect(perTopic.get('/scan')!.length).toBe(F.ticks.length);
    expect(perTopic.get('/map')!.length).toBe(1);
    expect(perTopic.get('/joint_states')!.length).toBe(1);
    expect(meta.get('coco')!.get('evidence')).toBe('MODEL');
    expect(meta.get('coco')!.get('source')).toContain('no ROS 2 ran');
    expect(meta.get('rosbag2')!.get('serialized_metadata')).toContain('storage_identifier: mcap');
  });
});
