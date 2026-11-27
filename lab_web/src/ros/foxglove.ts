// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.2: a READ-ONLY client of foxglove_bridge (the Foxglove WebSocket protocol), for LIVE topics.
 *
 * foxglove_bridge 3.x accepts only the subprotocol `foxglove.sdk.v1` (measured: CI run 45862342162,
 * "expected sec-websocket-protocol header foxglove.sdk.v1"); older bridges speak
 * `foxglove.websocket.v1` with the same frames. Both are offered; anything else the server picks is
 * a version mismatch. What this client reads, from the server:
 *   JSON  serverInfo, status, advertise, unadvertise, connectionGraphUpdate;
 *   binary op 0x01 MessageData = [u32 subscriptionId][u64 receive time ns][CDR payload],
 *          op 0x02 Time = [u64 ns] (the server's /clock, when it has the `time` capability).
 * It sends only `subscribe`, `unsubscribe` and `subscribeConnectionGraph`: never `advertise` or
 * `publish` (LIVE control goes through COCO's coco.v1 gateway; README invariants 2 and 3).
 */

export const SUBPROTOCOLS = ['foxglove.sdk.v1', 'foxglove.websocket.v1'] as const;

export interface Channel { id: number; topic: string; encoding: string; schemaName: string; schema?: string }
export interface ServerInfo { name?: string; capabilities: string[]; supportedEncodings?: string[]; metadata?: Record<string, string> }
/** The real ROS graph as the bridge reports it: per topic, the node names publishing and subscribing. */
export interface LiveGraph { publishers: Map<string, string[]>; subscribers: Map<string, string[]> }

/** Why a connection is not (or no longer) usable, in words a visitor can act on. */
export type FoxgloveFailure =
  | { kind: 'unreachable'; detail: string }       // nothing answered: no container running, or the wrong port
  | { kind: 'mismatch'; detail: string }          // something answered, but not a foxglove bridge this client speaks
  | { kind: 'lost'; detail: string };             // it was connected, then the connection dropped

export interface FoxgloveEvents {
  onOpen?(info: ServerInfo, protocol: string): void;
  onChannels?(channels: ReadonlyMap<number, Channel>): void;
  onMessage?(topic: string, schemaName: string, payload: Uint8Array, receiveNs: bigint): void;
  onTime?(ns: bigint): void;
  onGraph?(g: LiveGraph): void;
  onStatus?(level: number, message: string): void;
  onFailure?(f: FoxgloveFailure): void;
}

/** The subset of the browser WebSocket used here (tests pass a fake). */
export interface SocketLike {
  binaryType: string;
  readonly protocol: string;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onclose: ((ev: { code: number; reason: string }) => void) | null;
  send(data: string): void;
  close(): void;
}
export type SocketFactory = (url: string, protocols: string[]) => SocketLike;

const defaultFactory: SocketFactory = (url, protocols) => new WebSocket(url, protocols) as unknown as SocketLike;

/** The URL a visitor typed, normalised: ws:// is assumed, and only ws:// or wss:// are accepted. */
export function normaliseUrl(text: string): string {
  const t = text.trim();
  const u = /^[a-z]+:\/\//i.test(t) ? t : `ws://${t}`;
  const parsed = new URL(u);
  if (parsed.protocol !== 'ws:' && parsed.protocol !== 'wss:') throw new Error(`not a WebSocket URL: ${text}`);
  return parsed.toString().replace(/\/$/, '');
}

export class FoxgloveClient {
  readonly channels = new Map<number, Channel>();
  info: ServerInfo | null = null;
  private ws: SocketLike | null = null;
  private subs = new Map<number, Channel>();        // subscription id -> channel
  private wanted = new Set<string>();
  private nextSub = 1;
  private opened = false;
  private graph: LiveGraph = { publishers: new Map(), subscribers: new Map() };
  private failed = false;

  constructor(readonly url: string, private ev: FoxgloveEvents = {}, private factory: SocketFactory = defaultFactory) {}

  connect(): void {
    const ws = this.factory(this.url, [...SUBPROTOCOLS]);
    this.ws = ws;
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      if (!(SUBPROTOCOLS as readonly string[]).includes(ws.protocol)) {
        this.fail({ kind: 'mismatch', detail: `the server chose subprotocol "${ws.protocol || '(none)'}", not ${SUBPROTOCOLS.join(' or ')}` });
        ws.close();
        return;
      }
      this.opened = true;
    };
    ws.onmessage = (e) => this.receive(e.data);
    ws.onerror = () => { /* the close that follows says what happened */ };
    ws.onclose = (e) => {
      if (this.failed) return;
      if (!this.opened) this.fail({ kind: 'unreachable', detail: `nothing answered at ${this.url} (is the container running, on this port?)` });
      else this.fail({ kind: 'lost', detail: `the connection closed (code ${e.code}${e.reason ? `: ${e.reason}` : ''})` });
    };
  }

  /** Subscribe to these topics now and whenever they are advertised later. */
  subscribe(topics: Iterable<string>): void {
    for (const t of topics) this.wanted.add(t);
    this.syncSubscriptions();
  }

  close(): void {
    this.failed = true;                               // a requested close is not a failure
    this.ws?.close();
    this.ws = null;
  }

  private fail(f: FoxgloveFailure) { if (this.failed) return; this.failed = true; this.ev.onFailure?.(f); }

  private send(op: Record<string, unknown>) { this.ws?.send(JSON.stringify(op)); }

  private syncSubscriptions() {
    if (!this.info) return;
    const have = new Set([...this.subs.values()].map((c) => c.id));
    const add: { id: number; channelId: number }[] = [];
    for (const c of this.channels.values()) {
      if (this.wanted.has(c.topic) && c.encoding === 'cdr' && !have.has(c.id)) {
        const id = this.nextSub++;
        this.subs.set(id, c);
        add.push({ id, channelId: c.id });
      }
    }
    if (add.length) this.send({ op: 'subscribe', subscriptions: add });
  }

  private receive(data: unknown) {
    if (typeof data === 'string') {
      let m: Record<string, unknown>;
      try { m = JSON.parse(data); } catch { return; }
      switch (m.op) {
        case 'serverInfo':
          this.info = { name: m.name as string, capabilities: (m.capabilities as string[]) ?? [],
            supportedEncodings: m.supportedEncodings as string[], metadata: m.metadata as Record<string, string> };
          if (this.info.capabilities.includes('connectionGraph')) this.send({ op: 'subscribeConnectionGraph' });
          this.ev.onOpen?.(this.info, this.ws?.protocol ?? '');
          this.syncSubscriptions();
          break;
        case 'advertise':
          for (const c of (m.channels as Channel[]) ?? []) this.channels.set(c.id, c);
          this.ev.onChannels?.(this.channels);
          this.syncSubscriptions();
          break;
        case 'unadvertise':
          for (const id of (m.channelIds as number[]) ?? []) {
            this.channels.delete(id);
            for (const [s, c] of this.subs) if (c.id === id) this.subs.delete(s);
          }
          this.ev.onChannels?.(this.channels);
          break;
        case 'status':
          this.ev.onStatus?.(Number(m.level ?? 0), String(m.message ?? ''));
          break;
        case 'connectionGraphUpdate': {
          for (const t of (m.publishedTopics as { name: string; publisherIds: string[] }[]) ?? []) this.graph.publishers.set(t.name, [...t.publisherIds]);
          for (const t of (m.subscribedTopics as { name: string; subscriberIds: string[] }[]) ?? []) this.graph.subscribers.set(t.name, [...t.subscriberIds]);
          for (const n of (m.removedTopics as string[]) ?? []) { this.graph.publishers.delete(n); this.graph.subscribers.delete(n); }
          this.ev.onGraph?.(this.graph);
          break;
        }
        default: break;
      }
      return;
    }
    const buf = data instanceof ArrayBuffer ? new Uint8Array(data) : ArrayBuffer.isView(data) ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength) : null;
    if (!buf || buf.length < 1) return;
    const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    if (buf[0] === 0x01 && buf.length >= 13) {
      const sub = this.subs.get(view.getUint32(1, true));
      if (!sub) return;                                 // a late frame for a subscription already dropped
      this.ev.onMessage?.(sub.topic, sub.schemaName, buf.subarray(13), view.getBigUint64(5, true));
    } else if (buf[0] === 0x02 && buf.length >= 9) {
      this.ev.onTime?.(view.getBigUint64(1, true));
    }
  }
}

/** Words for a failure, shown where the visitor connected. */
export function failureWords(f: FoxgloveFailure): string {
  switch (f.kind) {
    case 'unreachable': return `Could not connect: ${f.detail}. Start it with: docker run --rm -p 8765:8765 -p 8766:8766 ghcr.io/gauthamcodes/coco-ros2 --level depot`;
    case 'mismatch': return `Connected, but this is not a COCO ROS 2 bridge this page understands: ${f.detail}.`;
    case 'lost': return `Lost the connection to ROS 2: ${f.detail}. Back to the browser model (MODEL).`;
  }
}
