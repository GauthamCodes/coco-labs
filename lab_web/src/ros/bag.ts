// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.5: "Save as rosbag2 (MCAP)" -- the run's model messages as a rosbag2 file that
 * `ros2 bag info`, `ros2 bag play` and Foxglove open.
 *
 * Written as `ros2 bag record -s mcap` writes one (compared with a recorded Stack bag,
 * coco_lab_ros/test/fixtures/bags): MCAP profile `ros2`; each schema the type's `ros2msg`
 * definition (src/ros/msgdefs.json, from ROS 2 Jazzy); each channel `cdr` with its
 * `offered_qos_profiles` (latched /map and /tf_static are transient local, so `ros2 bag play`
 * re-offers them to a late RViz) and its type hash; a `rosbag2` metadata record. Every message's
 * log and publish time is its header stamp: the model's sim time (from 0, as a Gazebo bag's
 * /clock starts). The bag says what it is: a `coco` metadata record with evidence MODEL --
 * written by the browser model, not recorded from ROS 2.
 */

import { McapWriter, TempBuffer } from '@mcap/core';
import DEFS from './msgdefs.json';
import { serialize, type JointState } from './cdr';
import type { Frame } from './recorder';
import { header, laserScan, occupancyGrid, odometry, path, twistStamped, type RosInfo } from './shapes';

/** the arm's model joints -> COCO's URDF joint names (as GameRenderer's ARM_JOINTS maps them) */
const ARM_URDF: [string, string][] = [['joint1', 'm_link1_Revolute-6'], ['joint2', 'm_link2_Revolute-7'], ['finger_left', 'm_link3_Revolute-8'], ['finger_right', 'm_link3_Revolute-9']];

const NEVER = { sec: 9223372036, nsec: 854775807 };
function qosYaml(durability: 'volatile' | 'transient_local', depth: number): string {
  return ['- history: keep_last', `  depth: ${depth}`, '  reliability: reliable', `  durability: ${durability}`,
    '  deadline:', `    sec: ${NEVER.sec}`, `    nsec: ${NEVER.nsec}`, '  lifespan:', `    sec: ${NEVER.sec}`, `    nsec: ${NEVER.nsec}`,
    '  liveliness: automatic', '  liveliness_lease_duration:', `    sec: ${NEVER.sec}`, `    nsec: ${NEVER.nsec}`,
    '  avoid_ros_namespace_conventions: false'].join('\n');
}

interface Topic { name: string; type: keyof typeof DEFS; latched?: boolean }
export const BAG_TOPICS: Topic[] = [
  { name: '/scan', type: 'sensor_msgs/msg/LaserScan' }, { name: '/odom', type: 'nav_msgs/msg/Odometry' },
  { name: '/tf', type: 'tf2_msgs/msg/TFMessage' }, { name: '/tf_static', type: 'tf2_msgs/msg/TFMessage', latched: true },
  { name: '/map', type: 'nav_msgs/msg/OccupancyGrid', latched: true }, { name: '/plan', type: 'nav_msgs/msg/Path' },
  { name: '/cmd_vel', type: 'geometry_msgs/msg/TwistStamped' }, { name: '/joint_states', type: 'sensor_msgs/msg/JointState' },
];

export interface BagMeta { game: string; seed: number; mode?: string; rules?: number; world: string; hashVersion: number; app: string; ticks: number; dropped: number }

const ns = (t: number) => BigInt(Math.round(t * 1e9));

/** rosbag2's own metadata (as `ros2 bag record` writes into an MCAP file), in YAML. */
function rosbag2Yaml(file: string, counts: Map<string, number>, start: bigint, end: bigint): string {
  const n = [...counts.values()].reduce((a, b) => a + b, 0);
  const lines = ['version: 9', 'storage_identifier: mcap', 'duration:', `  nanoseconds: ${end - start}`, 'starting_time:', `  nanoseconds_since_epoch: ${start}`,
    `message_count: ${n}`, 'topics_with_message_count:'];
  for (const t of BAG_TOPICS) {
    const d = DEFS[t.type];
    lines.push('  - topic_metadata:', `      name: ${t.name}`, `      type: ${t.type}`, '      serialization_format: cdr', '      offered_qos_profiles:',
      ...qosYaml(t.latched ? 'transient_local' : 'volatile', t.latched ? 1 : 10).split('\n').map((l) => `        ${l}`),
      `      type_description_hash: ${d.type_hash}`, `    message_count: ${counts.get(t.name) ?? 0}`);
  }
  lines.push('compression_format: ""', 'compression_mode: ""', 'relative_file_paths:', `  - ${file}`, 'files:', `  - path: ${file}`, '    starting_time:',
    `      nanoseconds_since_epoch: ${start}`, '    duration:', `      nanoseconds: ${end - start}`, `    message_count: ${n}`, 'custom_data: ~', 'ros_distro: jazzy');
  return lines.join('\n');
}

/** The run as a rosbag2 MCAP file (bytes). `file` is the name it will be saved under. */
export async function writeBag(frames: Frame[], info: RosInfo, map: { width: number; height: number; resolution: number; origin: [number, number] }, occupancy: ArrayLike<number>, meta: BagMeta, file: string): Promise<Uint8Array> {
  if (!frames.length) throw new Error('nothing to save: the run has no ticks yet');
  const buf = new TempBuffer();
  const w = new McapWriter({ writable: buf, chunkSize: 1 << 20 });
  await w.start({ profile: 'ros2', library: 'COCO Lab browser model (lab_web/src/ros/bag.ts) -- MODEL, not recorded from ROS 2' });
  const ch = new Map<string, number>(), seq = new Map<string, number>(), counts = new Map<string, number>();
  for (const t of BAG_TOPICS) {
    const d = DEFS[t.type];
    const sid = await w.registerSchema({ name: t.type, encoding: 'ros2msg', data: new TextEncoder().encode(d.text) });
    ch.set(t.name, await w.registerChannel({ topic: t.name, schemaId: sid, messageEncoding: 'cdr',
      metadata: new Map([['offered_qos_profiles', qosYaml(t.latched ? 'transient_local' : 'volatile', t.latched ? 1 : 10)], ['topic_type_hash', d.type_hash]]) }));
  }
  const put = async (topic: string, type: string, msg: unknown, t: number, size?: number) => {
    const s = seq.get(topic) ?? 0;
    seq.set(topic, s + 1); counts.set(topic, (counts.get(topic) ?? 0) + 1);
    await w.addMessage({ channelId: ch.get(topic)!, sequence: s, logTime: ns(t), publishTime: ns(t), data: serialize(type, msg, size) });
  };
  const t0 = frames[0].t;
  await put('/tf_static', 'tf2_msgs/msg/TFMessage', { transforms: info.tf_static.transforms.map((x) => ({ ...x, header: header(t0, x.header.frame_id) })) }, t0);
  await put('/map', 'nav_msgs/msg/OccupancyGrid', occupancyGrid(map, occupancy, t0), t0, map.width * map.height + 256);
  let lastArm: string | null = null;
  for (const f of frames) {
    await put('/scan', 'sensor_msgs/msg/LaserScan', laserScan(info.scan, f.ranges, f.t), f.t, f.ranges.length * 4 + 128);
    if (f.tf) {
      await put('/odom', 'nav_msgs/msg/Odometry', odometry(f.tf, f.v, f.w), f.t, 800);
      await put('/tf', 'tf2_msgs/msg/TFMessage', f.tf, f.t);
    }
    await put('/cmd_vel', 'geometry_msgs/msg/TwistStamped', twistStamped(f.v, f.w, f.t), f.t);
    if (f.plan) await put('/plan', 'nav_msgs/msg/Path', path(f.plan, f.t), f.t, f.plan.length * 72 + 64);
    if (f.arm) {
      const key = JSON.stringify(f.arm);
      if (key !== lastArm) {
        lastArm = key;
        const js: JointState = { header: header(f.t, ''), name: ARM_URDF.map(([, u]) => u), position: ARM_URDF.map(([k]) => f.arm![k] ?? 0), velocity: [], effort: [] };
        await put('/joint_states', 'sensor_msgs/msg/JointState', js, f.t);
      }
    }
  }
  const end = frames[frames.length - 1].t;
  await w.addMetadata({ name: 'rosbag2', metadata: new Map([['serialized_metadata', rosbag2Yaml(file, counts, ns(t0), ns(end))]]) });
  await w.addMetadata({ name: 'coco', metadata: new Map([
    ['evidence', 'MODEL'],
    ['source', 'COCO Lab browser model (coco_lab, kinematic) -- message shapes of COCO\'s ROS 2 stack, written by the browser; no ROS 2 ran'],
    ['game', meta.game], ['seed', String(meta.seed)], ['mode', meta.mode ?? ''], ['rules', meta.rules === undefined ? '' : String(meta.rules)],
    ['world', meta.world], ['hash_version', String(meta.hashVersion)], ['app', meta.app],
    ['ticks', String(meta.ticks)], ['ticks_dropped_from_start', String(meta.dropped)],
    ['time', 'every stamp is the model\'s sim time (s from the run\'s start), not wall-clock time'],
  ]) });
  await w.end();
  return buf.get();
}
