// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R5.2: the read-only foxglove_bridge client (src/ros/foxglove.ts) against a fake socket that
 * speaks what CI recorded from foxglove_bridge 3.6.3 (docs/v2/r5/data/r52/ci/probe.json): the
 * subprotocol, serverInfo, advertise, the connection graph and binary MessageData frames. It never
 * advertises or publishes, and each failure (nothing listening, a different server, a dropped
 * connection) is reported once, in words.
 */
import { describe, expect, it } from 'vitest';
import { FoxgloveClient, failureWords, normaliseUrl, type FoxgloveFailure, type SocketLike } from '../src/ros/foxglove';
import { serialize } from '../src/ros/cdr';
import { deserialize } from '../src/ros/cdr_read';

class FakeSocket implements SocketLike {
  binaryType = 'blob';
  protocol = '';
  sent: Record<string, unknown>[] = [];
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  onclose: ((ev: { code: number; reason: string }) => void) | null = null;
  constructor(readonly url: string, readonly offered: string[]) {}
  send(d: string) { this.sent.push(JSON.parse(d)); }
  close() { this.onclose?.({ code: 1000, reason: '' }); }
  open(protocol: string) { this.protocol = protocol; this.onopen?.({}); }
  json(m: unknown) { this.onmessage?.({ data: JSON.stringify(m) }); }
  binary(b: Uint8Array) { this.onmessage?.({ data: b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) }); }
}

function messageData(sub: number, ns: bigint, payload: Uint8Array) {
  const b = new Uint8Array(13 + payload.length);
  const v = new DataView(b.buffer);
  b[0] = 1; v.setUint32(1, sub, true); v.setBigUint64(5, ns, true); b.set(payload, 13);
  return b;
}

const odom = {
  header: { stamp: { sec: 7, nanosec: 0 }, frame_id: 'odom' }, child_frame_id: 'base_footprint',
  pose: { pose: { position: { x: 1, y: 2, z: 0 }, orientation: { x: 0, y: 0, z: 0, w: 1 } }, covariance: new Array(36).fill(0) },
  twist: { twist: { linear: { x: 0.15, y: 0, z: 0 }, angular: { x: 0, y: 0, z: 0.1 } }, covariance: new Array(36).fill(0) },
};

function setup() {
  let sock: FakeSocket | null = null;
  const got: { topic: string; type: string; payload: Uint8Array; ns: bigint }[] = [];
  const failures: FoxgloveFailure[] = [];
  const graphs: string[][] = [];
  const c = new FoxgloveClient('ws://localhost:8765', {
    onMessage: (topic, type, payload, ns) => got.push({ topic, type, payload, ns }),
    onFailure: (f) => failures.push(f),
    onGraph: (g) => graphs.push(g.publishers.get('/diff_drive_controller/cmd_vel') ?? []),
  }, (url, protocols) => (sock = new FakeSocket(url, protocols)));
  c.connect();
  return { c, sock: () => sock!, got, failures, graphs };
}

describe('the foxglove_bridge client', () => {
  it('offers foxglove.sdk.v1 first, subscribes to wanted CDR topics, decodes MessageData', () => {
    const { c, sock, got } = setup();
    expect(sock().offered).toEqual(['foxglove.sdk.v1', 'foxglove.websocket.v1']);
    sock().open('foxglove.sdk.v1');
    c.subscribe(['/odom', '/scan']);
    sock().json({ op: 'serverInfo', name: '', capabilities: ['connectionGraph', 'time'] });
    sock().json({ op: 'advertise', channels: [
      { id: 3, topic: '/odom', encoding: 'cdr', schemaName: 'nav_msgs/msg/Odometry' },
      { id: 4, topic: '/rosout', encoding: 'cdr', schemaName: 'rcl_interfaces/msg/Log' }] });
    const subs = sock().sent.filter((m) => m.op === 'subscribe');
    expect(subs).toEqual([{ op: 'subscribe', subscriptions: [{ id: 1, channelId: 3 }] }]);
    expect(sock().sent.some((m) => m.op === 'subscribeConnectionGraph')).toBe(true);
    sock().binary(messageData(1, 123n, serialize('nav_msgs/msg/Odometry', odom)));
    expect(got).toHaveLength(1);
    expect(got[0].topic).toBe('/odom');
    expect(got[0].ns).toBe(123n);
    const m = deserialize<typeof odom>(got[0].type, got[0].payload);
    expect(m.twist.twist.linear.x).toBe(0.15);
    // a later advertisement of a wanted topic is subscribed too
    sock().json({ op: 'advertise', channels: [{ id: 9, topic: '/scan', encoding: 'cdr', schemaName: 'sensor_msgs/msg/LaserScan' }] });
    expect(sock().sent.filter((x) => x.op === 'subscribe').at(-1)).toEqual({ op: 'subscribe', subscriptions: [{ id: 2, channelId: 9 }] });
  });

  it('reports the real ROS graph (publishers per topic)', () => {
    const { sock, graphs } = setup();
    sock().open('foxglove.sdk.v1');
    sock().json({ op: 'serverInfo', capabilities: ['connectionGraph'] });
    sock().json({ op: 'connectionGraphUpdate', publishedTopics: [{ name: '/diff_drive_controller/cmd_vel', publisherIds: ['/cmd_vel_arbiter'] }] });
    expect(graphs.at(-1)).toEqual(['/cmd_vel_arbiter']);
  });

  it('never advertises, publishes or calls services', () => {
    const { c, sock } = setup();
    sock().open('foxglove.sdk.v1');
    c.subscribe(['/odom']);
    sock().json({ op: 'serverInfo', capabilities: ['connectionGraph', 'clientPublish', 'services'] });
    sock().json({ op: 'advertise', channels: [{ id: 3, topic: '/odom', encoding: 'cdr', schemaName: 'nav_msgs/msg/Odometry' }] });
    const ops = new Set(sock().sent.map((m) => m.op));
    for (const forbidden of ['advertise', 'publish', 'callService', 'setParameters', 'unadvertise']) expect(ops.has(forbidden)).toBe(false);
  });

  it('reports each failure once, in words', () => {
    const a = setup(); a.sock().onclose?.({ code: 1006, reason: '' });
    expect(a.failures).toEqual([expect.objectContaining({ kind: 'unreachable' })]);
    expect(failureWords(a.failures[0])).toMatch(/docker run --rm -p 8765:8765 -p 8766:8766/);
    const b = setup(); b.sock().open('json'); b.sock().onclose?.({ code: 1000, reason: '' });
    expect(b.failures.map((f) => f.kind)).toEqual(['mismatch']);
    const d = setup(); d.sock().open('foxglove.sdk.v1'); d.sock().onclose?.({ code: 1006, reason: '' });
    expect(d.failures.map((f) => f.kind)).toEqual(['lost']);
    expect(failureWords(d.failures[0])).toMatch(/MODEL/);
    const e = setup(); e.sock().open('foxglove.sdk.v1'); e.c.close();
    expect(e.failures).toEqual([]);                    // a close the visitor asked for is not a failure
  });

  it('normalises typed URLs', () => {
    expect(normaliseUrl('localhost:8765')).toBe('ws://localhost:8765');
    expect(normaliseUrl(' ws://127.0.0.1:8765/ ')).toBe('ws://127.0.0.1:8765');
    expect(() => normaliseUrl('http://localhost:8765')).toThrow(/not a WebSocket URL/);
  });
});
