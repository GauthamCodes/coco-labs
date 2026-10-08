// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The quiet Live probe (M0 fix A.2): no socket until /healthz answers as
 * coco.v1, exponential backoff capped at 30 s while nothing answers, and
 * the same LiveClient connection as before once something does.
 *
 * The wiring under test is `openWhenReachable`, the function LiveView.tsx
 * calls, with the real LiveClient behind it. Time is a manual clock, and
 * `WebSocket` is a stub that counts every socket the page tries to open.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { LiveClient } from '../src/live/client';
import { HealthWatch, openWhenReachable, retryDelayMs, type ProbeReport, type Timers } from '../src/live/gate';
import {
  check, demoWindowOpen, isLoopback, lastCheckWords, loadSchedule, nextSession, OFFLINE_HEADLINE, offlineWords, remoteReached,
} from '../src/live/status';

const WS = 'ws://localhost:8080/ws';
const HEALTH = 'http://localhost:8080/healthz';

/** A clock the test moves by hand. */
class ManualTimers implements Timers {
  t = 1_760_000_000_000;
  private q: { at: number; fn: () => void; id: number }[] = [];
  private nextId = 1;
  readonly delays: number[] = [];
  setTimeout(fn: () => void, ms: number): unknown {
    this.delays.push(ms);
    const id = this.nextId++;
    this.q.push({ at: this.t + ms, fn, id });
    return id;
  }
  clearTimeout(h: unknown): void { this.q = this.q.filter((e) => e.id !== h); }
  now(): number { return this.t; }
  get pending(): number { return this.q.length; }
  /** Move the clock forward, firing each due timer and letting its promises settle. */
  async advance(ms: number): Promise<void> {
    const end = this.t + ms;
    for (;;) {
      await flush();
      this.q.sort((a, b) => a.at - b.at);
      const e = this.q[0];
      if (!e || e.at > end) break;
      this.q.shift();
      this.t = e.at;
      e.fn();
    }
    this.t = end;
    await flush();
  }
}

const flush = async () => { for (let i = 0; i < 10; i += 1) await new Promise((r) => setImmediate(r)); };

/** Every socket the code under test opens. */
class StubSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static created: StubSocket[] = [];
  readyState = StubSocket.CONNECTING;
  binaryType = 'blob';
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((e: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(readonly url: string) { StubSocket.created.push(this); }
  send(d: string) { this.sent.push(d); }
  close() { this.readyState = 3; }
  /** The server accepts. */
  accept() { this.readyState = StubSocket.OPEN; this.onopen?.(); }
}

const realWebSocket = globalThis.WebSocket;
beforeEach(() => { StubSocket.created = []; (globalThis as { WebSocket: unknown }).WebSocket = StubSocket; });
afterEach(() => { (globalThis as { WebSocket: unknown }).WebSocket = realWebSocket; });

const refused = async (): Promise<never> => { throw new TypeError('Failed to fetch'); };
const cocoOpen = { protocol: 'coco.v1', state: 'ready', live: { access: 'open' } };

describe('backoff', () => {
  it('2 s, doubling, capped at 30 s', () => {
    expect([1, 2, 3, 4, 5, 6, 20].map(retryDelayMs)).toEqual([2000, 4000, 8000, 16000, 30000, 30000, 30000]);
  });
});

describe('offline: no stack reachable', () => {
  it('opens zero sockets, backs off to 30 s, and reports "offline" with the last check', async () => {
    const timers = new ManualTimers();
    const asked: string[] = [];
    const reports: ProbeReport[] = [];
    let clients = 0;
    const cancel = openWhenReachable(WS, async (u) => { asked.push(u); return refused(); },
      () => { clients += 1; new LiveClient(WS, {}).connect(); }, (r) => reports.push(r), timers);
    await timers.advance(5 * 60_000);
    cancel();

    expect(StubSocket.created).toHaveLength(0);
    expect(clients).toBe(0);
    // Once on load, then 2, 4, 8, 16, 30, 30, ... s: 14 checks in 5 minutes.
    expect(timers.delays.slice(0, 7)).toEqual([2000, 4000, 8000, 16000, 30000, 30000, 30000]);
    expect(asked.length).toBe(reports.length);
    expect(new Set(asked)).toEqual(new Set([HEALTH]));
    expect(reports.every((r) => !r.reachable && r.verdict.state === 'offline')).toBe(true);
    const last = reports[reports.length - 1];
    expect(last.failures).toBe(reports.length);
    expect(lastCheckWords({ at: last.at, contacted: HEALTH, reachable: false, nextInMs: last.nextInMs }))
      .toMatch(/^Last checked .+: no answer from http:\/\/localhost:8080\/healthz\. Next check in 30 s\.$/);
  });

  it('stops checking when the view closes (cancel), including a check already in flight', async () => {
    const timers = new ManualTimers();
    let asked = 0;
    let release: (() => void) | null = null;
    const reports: ProbeReport[] = [];
    const cancel = openWhenReachable(WS, () => {
      asked += 1;
      return new Promise((_, reject) => { release = () => reject(new TypeError('Failed to fetch')); });
    }, () => { throw new Error('must not open'); }, (r) => reports.push(r), timers);
    await flush();
    expect(asked).toBe(1);
    cancel();
    release!();
    await timers.advance(10 * 60_000);
    expect(asked).toBe(1);
    expect(reports).toHaveLength(0);
    expect(timers.pending).toBe(0);
    expect(StubSocket.created).toHaveLength(0);
  });

  it('a remote answer that is not coco.v1 (some other server) is not a stack', async () => {
    const r = await check('wss://coco.example.net/ws', async () => ({ status: 200, json: async () => ({ hello: 'world' }) }));
    expect(r.reachable).toBe(false);
  });

  it('a loopback stack is asked opaquely (a local platform_server sends no CORS header)', async () => {
    const inits: unknown[] = [];
    const r = await check(WS, async (_u, init) => {
      inits.push(init);
      // An opaque response: status 0 and an unreadable body, as a browser gives it.
      return { status: 0, json: async () => { throw new SyntaxError('opaque'); } };
    });
    expect(r.reachable).toBe(true);
    expect(inits).toEqual([expect.objectContaining({ mode: 'no-cors', credentials: 'omit', cache: 'no-store' })]);
    const remote: unknown[] = [];
    await check('wss://coco.example.net/ws', async (_u, init) => { remote.push(init); return { status: 200, json: async () => ({}) }; });
    expect(remote[0]).not.toHaveProperty('mode');
  });

  it('loopback means this machine only', () => {
    expect(['localhost', 'LOCALHOST', 'a.localhost', '127.0.0.1', '127.1.2.3', '[::1]'].every(isLoopback)).toBe(true);
    expect(['coco.example.net', '192.168.1.5', '10.0.0.1', 'localhost.example.com', '127.0.0.1.nip.io'].some(isLoopback))
      .toBe(false);
  });
});

describe('recovery: the stack comes up', () => {
  it('after failed checks, a coco.v1 answer opens exactly one socket, which says hello as before', async () => {
    const timers = new ManualTimers();
    let up = false;
    const reports: ProbeReport[] = [];
    let client: LiveClient | null = null;
    const states: string[] = [];
    let asked = 0;
    const cancel = openWhenReachable(WS, async () => {
      asked += 1;
      if (!up) return refused();
      return { status: 503, json: async () => cocoOpen }; // starting: still a coco.v1 server
    }, () => {
      client = new LiveClient(WS, { onState: (s) => states.push(s) });
      client.connect();
    }, (r) => reports.push(r), timers);

    await timers.advance(10_000); // checks at 0, 2, 6 s
    expect(StubSocket.created).toHaveLength(0);
    up = true;
    await timers.advance(20_000); // the 14 s check answers
    expect(reports.map((r) => r.reachable)).toEqual([false, false, false, true]);
    expect(reports[3].nextInMs).toBeNull();
    expect(StubSocket.created).toHaveLength(1);
    expect(StubSocket.created[0].url).toBe(WS);

    // From here it is the unchanged LiveClient: hello on open, as in v1.
    StubSocket.created[0].accept();
    expect(states).toEqual(['connecting', 'open']);
    expect(JSON.parse(StubSocket.created[0].sent[0])).toEqual({ type: 'hello', client: 'coco-lab-live', binary: true, id: 1 });

    // And the probe has finished: no more /healthz once connected.
    const n = asked;
    await timers.advance(5 * 60_000);
    expect(asked).toBe(n);
    cancel();
    client!.close();
  });
});

describe('the scheduled-demo endpoint is asked only while a demo is on', () => {
  const sessions = loadSchedule({ version: 1, sessions: [{ start: '2026-10-10T15:00:00Z', minutes: 60, note: '' }] });

  it('closed before the 10-minute lead, open through the session, closed after', () => {
    const at = (iso: string) => demoWindowOpen(sessions, new Date(iso));
    expect(at('2026-10-10T14:49:59Z')).toBe(false);
    expect(at('2026-10-10T14:50:00Z')).toBe(true);
    expect(at('2026-10-10T15:59:59Z')).toBe(true);
    expect(at('2026-10-10T16:00:00Z')).toBe(false);
    expect(demoWindowOpen([], new Date('2026-10-10T15:30:00Z'))).toBe(false);
  });

  it('the committed (empty) schedule never opens a window', async () => {
    const doc = (await import('../src/live/schedule.json')).default;
    expect(demoWindowOpen(loadSchedule(doc), new Date())).toBe(false);
  });

  it('offline words: the plan\'s sentence, then the next demo or "none scheduled"', () => {
    expect(OFFLINE_HEADLINE).toBe('Live Stack (simulated) is offline — it runs during scheduled demos');
    expect(offlineWords(null)).toBe(`${OFFLINE_HEADLINE}. No demo is scheduled.`);
    const next = nextSession(sessions, new Date('2026-10-09T00:00:00Z'));
    expect(offlineWords(next)).toBe(`${OFFLINE_HEADLINE}. Next: Sat, 10 Oct 2026 15:00:00 GMT (60 min).`);
    expect(lastCheckWords({ at: Date.now(), contacted: null, reachable: false, nextInMs: null }))
      .toMatch(/: no demo is scheduled now, so nothing was contacted\.$/);
  });

  it('the remote card counts live, starting and ended as reached; offline is retried', async () => {
    expect(['live', 'starting', 'ended', 'offline', 'unconfigured'].map((state) =>
      remoteReached({ state, driver: false, leftS: null, clients: null, why: '' } as never).reachable))
      .toEqual([true, true, true, false, false]);
    const timers = new ManualTimers();
    const reports: ProbeReport[] = [];
    const w = new HealthWatch(async () => remoteReached({ state: 'ended' }), (r) => reports.push(r), {}, timers);
    w.start();
    await timers.advance(65_000);
    w.stop();
    // Reached: it keeps refreshing at the v1 card's 30 s, not the backoff.
    expect(timers.delays).toEqual([30_000, 30_000, 30_000]);
    expect(reports).toHaveLength(3);
  });
});

describe('the Live tab is wired through the gate', () => {
  it('only client.ts opens a socket, and LiveView opens one only from openWhenReachable, only when asked', async () => {
    const { readFileSync, readdirSync, statSync } = await import('node:fs');
    const { join } = await import('node:path');
    const files: string[] = [];
    const walk = (d: string) => readdirSync(d).forEach((n) => {
      const p = join(d, n);
      if (statSync(p).isDirectory()) walk(p); else if (/\.tsx?$/.test(n)) files.push(p);
    });
    const src = join(__dirname, '..', 'src');
    walk(src);
    const openers = files.filter((p) => /new WebSocket\(/.test(readFileSync(p, 'utf-8')));
    expect(openers.map((p) => p.slice(src.length + 1))).toEqual([join('live', 'client.ts')]);
    const tsx = readFileSync(join(src, 'ui', 'LiveView.tsx'), 'utf-8');
    expect(tsx.match(/\.connect\(\)/g)).toHaveLength(1);
    expect(tsx).toMatch(/if \(!explicit\) return undefined;[\s\S]*openWhenReachable\(url, \(u, init\) => fetch\(u, init\), \(\) => \{ void open\(\); \}/);
    // The scheduled-demo card asks its endpoint only inside a demo window.
    expect(tsx).toMatch(/if \(!windowOpen\) return undefined;[\s\S]*probe\(LIVE_REMOTE\?\.ws, \(u, init\) => fetch\(u, init\)\)/);
    expect(tsx.match(/fetch\(u, init\)/g)).toHaveLength(2);
  });
});
