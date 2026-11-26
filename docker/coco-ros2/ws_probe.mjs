#!/usr/bin/env node
// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.1: the coco-ros2 bridge seen from outside the container, as a browser will see it.
 *
 *   node docker/coco-ros2/ws_probe.mjs ws://127.0.0.1:8765 OUT.json [--seconds 10] [--container NAME]
 *
 * Node >= 22 (a global WebSocket; lab_web pins 24.21.0); no packages. Speaks the Foxglove WebSocket
 * protocol: reads serverInfo and the advertised channels, subscribes to the acceptance topics and
 * counts the messages that arrive, follows the connection graph, then advertises the wheel topic
 * (the bridge must refuse: docker/coco-ros2/foxglove_bridge.yaml whitelists only inputs that go
 * through cmd_vel_arbiter or Nav2) and the arbiter's teleop input (allowed). With --container, the
 * in-container check (`coco-ros2 check`) runs while both are advertised, so the wheel topic's
 * publishers are read from ROS itself too. Nothing is published: no message moves the robot.
 *
 * Everything seen is written to OUT.json, so a protocol detail this got wrong shows in the
 * artifact. Exit 0 only if every acceptance topic is advertised, /scan, /odom and /tf deliver
 * messages, the server offers neither `parameters` nor `services`, and the wheel topic gains no
 * publisher. Evidence class: LIVE (a Gazebo simulation running now; never hardware).
 */
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const opt = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : dflt; };
const [url, outPath] = args;
if (!url || !outPath || typeof WebSocket === 'undefined') {
  console.error('usage: node ws_probe.mjs ws://HOST:PORT OUT.json [--seconds N] [--container NAME] (Node >= 22)');
  process.exit(2);
}
const seconds = Number(opt('--seconds', '10'));
const container = opt('--container', null);
const WANT = ['/scan', '/odom', '/tf', '/map', '/plan', '/cmd_vel'];
const MUST_FLOW = ['/scan', '/odom', '/tf'];
const WHEELS = '/diff_drive_controller/cmd_vel';
const TELEOP = '/cmd_vel_teleop';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const rec = {
  schema: 'coco_ros2.ws_probe', version: 1, url, utc: new Date().toISOString(),
  evidence_class: "LIVE (COCO's ROS 2 stack running now: a Gazebo simulation, never hardware)",
  node: process.version, protocol: null, server_info: null, channels: [], messages: {}, bytes: {},
  statuses: [], graph_updates: 0, other_ops: [], binary_other: 0, errors: [],
};
const channels = new Map();
const subs = new Map();
const graph = new Map();
const pubs = (topic) => [...(graph.get(topic) ?? [])].sort();

// foxglove_bridge 3.x (the Foxglove SDK server) accepts only 'foxglove.sdk.v1' ("expected
// sec-websocket-protocol header foxglove.sdk.v1", its own error, CI run 45862342162); older bridges speak
// 'foxglove.websocket.v1'. Offer both: the server's choice is recorded as rec.protocol.
const ws = new WebSocket(url, ['foxglove.sdk.v1', 'foxglove.websocket.v1']);
ws.binaryType = 'arraybuffer';
const opened = new Promise((resolve, reject) => {
  ws.onopen = resolve;
  ws.onerror = () => reject(new Error(`could not open ${url}`));
});
ws.onclose = (e) => { rec.closed = { code: e.code, reason: e.reason }; };
ws.onmessage = (ev) => {
  if (typeof ev.data === 'string') {
    let m;
    try { m = JSON.parse(ev.data); } catch { rec.errors.push('a text frame that is not JSON'); return; }
    switch (m.op) {
      case 'serverInfo': rec.server_info = m; break;
      case 'advertise': for (const c of m.channels ?? []) channels.set(c.id, c); break;
      case 'unadvertise': for (const id of m.channelIds ?? []) channels.delete(id); break;
      case 'status': rec.statuses.push({ at_ms: Date.now(), level: m.level, message: m.message }); break;
      case 'connectionGraphUpdate':
        rec.graph_updates++;
        for (const t of m.publishedTopics ?? []) graph.set(t.name, new Set(t.publisherIds ?? []));
        for (const name of m.removedTopics ?? []) graph.delete(name);
        break;
      default: if (!rec.other_ops.includes(m.op)) rec.other_ops.push(m.op);
    }
    return;
  }
  const dv = new DataView(ev.data);
  // opcode 1 = message data: subscription id (u32 LE), receive time (u64 LE), payload
  if (dv.byteLength >= 13 && dv.getUint8(0) === 1) {
    const topic = subs.get(dv.getUint32(1, true));
    if (topic) {
      rec.messages[topic] = (rec.messages[topic] ?? 0) + 1;
      rec.bytes[topic] = (rec.bytes[topic] ?? 0) + dv.byteLength - 13;
    }
  } else rec.binary_other++;
};

function inContainer() {
  if (!container) return null;
  let text;
  try {
    text = execFileSync('docker', ['exec', container, 'coco-ros2', 'check', '--json', '--window', '2'],
      { encoding: 'utf8', timeout: 120000 });
  } catch (e) {
    text = e.stdout ?? '';           // the check exits 1 when it fails; its JSON is still printed
  }
  try {
    const r = JSON.parse(text);
    return { pass: r.pass, wheel_topic_publishers: r.required_also.wheel_topic_publishers,
             teleop_publishers: r.recorded.teleop_publishers ?? null };
  } catch {
    return { error: 'no JSON from coco-ros2 check', text: String(text).slice(0, 400) };
  }
}

let code = 1;
try {
  await Promise.race([opened, sleep(15000).then(() => { throw new Error(`no connection to ${url} in 15 s`); })]);
  rec.protocol = ws.protocol;
  await sleep(3000);                                   // serverInfo and the channel advertisements
  rec.channels = [...channels.values()].map((c) => ({ id: c.id, topic: c.topic, schemaName: c.schemaName, encoding: c.encoding }))
    .sort((a, b) => a.topic.localeCompare(b.topic));
  const byTopic = new Map([...channels.values()].map((c) => [c.topic, c]));
  const subscriptions = [];
  for (const t of [...WANT, '/amcl_pose', '/clock']) {
    const c = byTopic.get(t);
    if (c) { const id = subscriptions.length + 1; subs.set(id, t); subscriptions.push({ id, channelId: c.id }); }
  }
  ws.send(JSON.stringify({ op: 'subscribe', subscriptions }));
  const caps = rec.server_info?.capabilities ?? [];
  if (caps.includes('connectionGraph')) ws.send(JSON.stringify({ op: 'subscribeConnectionGraph' }));
  await sleep(seconds * 1000);
  rec.window_s = seconds;
  rec.graph_publishers_before = { [WHEELS]: pubs(WHEELS), [TELEOP]: pubs(TELEOP) };

  if (caps.includes('clientPublish')) {
    const t0 = Date.now();
    ws.send(JSON.stringify({ op: 'advertise', channels: [
      { id: 901, topic: WHEELS, encoding: 'cdr', schemaName: 'geometry_msgs/msg/TwistStamped' },
      { id: 902, topic: TELEOP, encoding: 'cdr', schemaName: 'geometry_msgs/msg/TwistStamped' }] }));
    await sleep(4000);
    rec.while_advertised = {
      graph_publishers: { [WHEELS]: pubs(WHEELS), [TELEOP]: pubs(TELEOP) },
      in_container: inContainer(),
      statuses: rec.statuses.filter((s) => s.at_ms >= t0),
    };
    ws.send(JSON.stringify({ op: 'unadvertise', channelIds: [901, 902] }));
    await sleep(1000);
  }
  ws.close();
  await sleep(500);

  const advertised = Object.fromEntries(WANT.map((t) => [t, byTopic.has(t)]));
  const flowing = Object.fromEntries(MUST_FLOW.map((t) => [t, (rec.messages[t] ?? 0) > 0]));
  const w = rec.while_advertised;
  // node names as the bridge's graph spells them (with or without a leading slash)
  const isArbiter = (n) => String(n).replace(/^\/+/, '') === 'cmd_vel_arbiter';
  const graphWheels = w && rec.graph_updates > 0 ? w.graph_publishers[WHEELS] : null;
  const rosWheels = w?.in_container?.wheel_topic_publishers ?? null;
  // at least one real observation of the wheel topic's publishers, and every one the arbiter alone
  const noBypass = w !== undefined && (graphWheels !== null || rosWheels !== null)
    && (graphWheels === null || graphWheels.every(isArbiter))
    && (rosWheels === null || (rosWheels.length === 1 && isArbiter(rosWheels[0])));
  rec.acceptance = {
    topics_advertised: advertised, messages_arrive: flowing,
    no_parameters_or_services: !caps.includes('parameters') && !caps.includes('services'),
    wheel_topic_gains_no_publisher: caps.includes('clientPublish') ? noBypass : 'no clientPublish capability (nothing to test)',
  };
  rec.pass = Object.values(advertised).every(Boolean) && Object.values(flowing).every(Boolean)
    && rec.acceptance.no_parameters_or_services && rec.acceptance.wheel_topic_gains_no_publisher !== false;
  code = rec.pass ? 0 : 1;
} catch (e) {
  rec.errors.push(String(e?.message ?? e));
  rec.pass = false;
}
writeFileSync(outPath, JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify({ pass: rec.pass, protocol: rec.protocol, capabilities: rec.server_info?.capabilities,
  channels: rec.channels.length, messages: rec.messages, acceptance: rec.acceptance, errors: rec.errors }, null, 1));
process.exit(code);
