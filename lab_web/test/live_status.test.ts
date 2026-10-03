// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// The public Live tab's "is a session live?" logic (src/live/status.ts), the
// session roles it reads, and the site configuration behind both. Every
// network answer is injected; nothing here touches the network.

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  DOCKER_QUICKSTART_URL, LIVE_CONNECT_SRC_LOCAL, LIVE_REMOTE, liveConnectSrc, remoteConnectSrc,
} from '../site.config';
import { controlHolder, refusalWords, role } from '../src/live/labels';
import type { Telemetry } from '../src/live/protocol';
import scheduleDoc from '../src/live/schedule.json';
import {
  classify, healthUrl, loadSchedule, nextSession, probe, statusWords, type LiveVerdict,
} from '../src/live/status';
import { LAB_WEB, REPO } from './helpers';

const WS = 'wss://coco.example.net/ws';

/** A /healthz body as coco_web's HealthHandler builds it. */
function health(live: Record<string, unknown> | undefined, protocol = 'coco.v1') {
  return { state: 'ready', protocol, ...(live ? { live } : {}) };
}
const LIVE = { access: 'code', driver: false, clients: 2, max_clients: 25, session_left_s: 900, over: null };

function answering(status: number, body: unknown) {
  const calls: string[] = [];
  const f = async (url: string) => {
    calls.push(url);
    return { status, json: async () => body };
  };
  return { f, calls };
}

describe('the probe says "live" only when the server says so', () => {
  it('live available: 200, coco.v1, an open code session', async () => {
    const { f, calls } = answering(200, health(LIVE));
    const v = await probe(WS, f);
    expect(v).toEqual({ state: 'live', driver: false, leftS: 900, clients: 2 });
    expect(calls).toEqual(['https://coco.example.net/healthz']);
    expect(statusWords(v, null).live).toBe(true);
    expect(statusWords(v, null).headline).toMatch(/^Live now, 15 min left\./);
  });

  it('live, with a driver: watchers are told so', async () => {
    const { f } = answering(200, health({ ...LIVE, driver: true }));
    expect(statusWords(await probe(WS, f), null).headline).toContain('Someone is driving');
  });

  it('live unavailable: the stack is still starting (503)', async () => {
    const { f } = answering(503, health(LIVE));
    const v = await probe(WS, f);
    expect(v.state).toBe('starting');
    expect(statusWords(v, null).live).toBe(false);
    // A 503 may also be a component lost mid-session: never claim "starting" only.
    expect(statusWords(v, null).headline).toContain('or a component is down');
  });

  it('a negative or non-numeric time left or count is dropped, not shown', async () => {
    const { f } = answering(200, health({ ...LIVE, session_left_s: -5, clients: 'many' }));
    const v = await probe(WS, f);
    expect(v).toEqual({ state: 'live', driver: false, leftS: null, clients: null });
    expect(statusWords(v, null).headline).not.toMatch(/-\d|min left/);
  });

  it('live unavailable: the session has ended (expired or killed)', async () => {
    const { f } = answering(200, health({ ...LIVE, over: 'killed' }));
    const v = await probe(WS, f);
    expect(v.state).toBe('ended');
    expect(statusWords(v, null).live).toBe(false);
  });

  it('an OPEN (local appliance) server is never a public session', async () => {
    const { f } = answering(200, health({ access: 'open', role: 'open', over: null }));
    expect((await probe(WS, f)).state).toBe('offline');
  });

  it('a server too old to report `live` is not live', async () => {
    const { f } = answering(200, health(undefined));
    expect((await probe(WS, f)).state).toBe('offline');
  });

  it.each([
    ['not JSON', 200, Symbol('unparseable')],
    ['not an object', 200, 'ready'],
    ['another protocol', 200, health(LIVE, 'coco.v2')],
    ['an HTML error page', 502, null],
  ])('malformed endpoint answer (%s) is offline', async (_label, status, body) => {
    const f = async () => ({
      status,
      json: async () => { if (typeof body === 'symbol') throw new SyntaxError('bad'); return body; },
    });
    const v = await probe(WS, f);
    expect(v.state).toBe('offline');
    expect(statusWords(v, null).live).toBe(false);
  });

  it('unreachable endpoint (network error) is offline, and never throws', async () => {
    const v = await probe(WS, async () => { throw new TypeError('Failed to fetch'); });
    expect(v).toEqual({ state: 'offline', why: 'the endpoint is unreachable' });
  });

  it('an endpoint that never answers times out as offline', async () => {
    const hang = (_u: string, init?: { signal?: AbortSignal }) => new Promise<never>((_r, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    });
    const v = await probe(WS, hang, 20);
    expect(v.state).toBe('offline');
  });

  it.each(['', 'not a url', 'http://coco.example.net/ws', 'ftp://x/ws', 'wss://user:pw@coco.example.net/ws'])(
    'malformed endpoint configuration %j is never probed', async (bad) => {
      const { f, calls } = answering(200, health(LIVE));
      const v = await probe(bad, f);
      expect(v.state === 'offline' || v.state === 'unconfigured').toBe(true);
      expect(calls).toEqual([]);
    });

  it('no endpoint configured: unconfigured, and nothing is fetched', async () => {
    const { f, calls } = answering(200, health(LIVE));
    expect(await probe(null, f)).toEqual({ state: 'unconfigured' });
    expect(calls).toEqual([]);
  });

  it('healthz sits on the same host as the socket', () => {
    expect(healthUrl('wss://a.example:8443/ws')).toBe('https://a.example:8443/healthz');
    expect(healthUrl('ws://localhost:8080/ws')).toBe('http://localhost:8080/healthz');
    expect(healthUrl('https://a.example/ws')).toBeNull();
  });

  it('classify needs every condition, not any one', () => {
    expect(classify(200, health({ ...LIVE, access: 'code', over: null })).state).toBe('live');
    expect(classify(200, { protocol: 'coco.v1', live: 'yes' }).state).toBe('offline');
    expect(classify(200, null).state).toBe('offline');
  });
});

describe('the schedule file', () => {
  it('the committed schedule loads (and is empty until the owner fills it)', () => {
    expect(loadSchedule(scheduleDoc)).toEqual([]);
  });

  it('loads valid sessions in time order and drops anything ambiguous', () => {
    const s = loadSchedule({
      version: 1,
      sessions: [
        { start: '2026-10-10T15:00:00Z', minutes: 20, note: 'second' },
        { start: '2026-10-09T18:30:00+05:30', minutes: 30, note: 'first' },
        { start: '2026-10-11T15:00:00', minutes: 20 },          // no offset
        { start: 'soon', minutes: 20 },
        { start: '2026-10-12T15:00:00Z', minutes: 0 },
        { start: '2026-10-12T15:00:00Z', minutes: '20' },
        null,
      ],
    });
    expect(s.map((x) => x.note)).toEqual(['first', 'second']);
    expect(s[0].start.toISOString()).toBe('2026-10-09T13:00:00.000Z');
  });

  it.each([null, {}, { version: 2, sessions: [] }, { version: 1, sessions: 'x' }])(
    'a malformed schedule document %j is no sessions', (doc) => {
      expect(loadSchedule(doc)).toEqual([]);
    });

  it('the next session: in progress, upcoming, or none', () => {
    const s = loadSchedule({ version: 1, sessions: [
      { start: '2026-10-10T15:00:00Z', minutes: 20 }, { start: '2026-10-12T15:00:00Z', minutes: 20 }] });
    expect(nextSession(s, new Date('2026-10-10T15:10:00Z'))?.inProgress).toBe(true);
    expect(nextSession(s, new Date('2026-10-10T15:20:00Z'))?.session.start.toISOString())
      .toBe('2026-10-12T15:00:00.000Z');
    expect(nextSession(s, new Date('2026-10-13T00:00:00Z'))).toBeNull();
  });
});

describe('no active session: the fallback', () => {
  const none: LiveVerdict[] = [
    { state: 'unconfigured' }, { state: 'offline', why: 'x' }, { state: 'starting' }, { state: 'ended' }];

  it.each(none)('%j is never shown as live', (v) => {
    const w = statusWords(v, null);
    expect(w.live).toBe(false);
    expect(w.headline).not.toMatch(/live now/i);
  });

  it('a scheduled session does not make the site look live', () => {
    const s = loadSchedule({ version: 1, sessions: [{ start: '2026-10-10T15:00:00Z', minutes: 20 }] });
    const w = statusWords({ state: 'offline', why: 'x' }, nextSession(s, new Date('2026-10-10T15:05:00Z')));
    expect(w.live).toBe(false);
    expect(w.headline).toContain('scheduled now but not reachable');
  });

  it('with nothing scheduled it says so instead of inventing a time', () => {
    expect(statusWords({ state: 'unconfigured' }, null).headline)
      .toBe('No live session right now. No session is scheduled.');
  });

  it('the page points to Replay and the Docker quickstart when not live', () => {
    const tsx = readFileSync(join(LAB_WEB, 'src/ui/LiveView.tsx'), 'utf-8');
    expect(tsx).toContain('data-testid="live-fallback-links"');
    expect(tsx).toContain('Replay recorded runs');
    expect(tsx).toContain('DOCKER_QUICKSTART_URL');
    expect(DOCKER_QUICKSTART_URL).toMatch(/^https:\/\/github\.com\/.*\/docs\/DOCKER\.md$/);
    expect(readFileSync(join(REPO, 'docs', 'DOCKER.md'), 'utf-8').length).toBeGreaterThan(0);
  });
});

describe('the endpoint and the CSP', () => {
  it('no remote endpoint is configured until a tunnel exists', () => {
    expect(LIVE_REMOTE).toBeNull();
    expect(liveConnectSrc()).toEqual([...LIVE_CONNECT_SRC_LOCAL]);
  });

  it('a configured endpoint adds exactly its own wss: and https: origins', () => {
    expect(remoteConnectSrc({ ws: 'wss://coco.example.net/ws' }))
      .toEqual(['wss://coco.example.net', 'https://coco.example.net']);
    expect(() => remoteConnectSrc({ ws: 'ws://coco.example.net/ws' })).toThrow();
  });
});

describe('roles are read from the server, never decided here', () => {
  const tele = (control: unknown) => ({ platform: { pilot: null, arbiter: { active: null }, control } }) as unknown as Telemetry;

  it('open, driver, spectator', () => {
    expect(role(tele(undefined), 'me')).toBe('open');
    expect(role(tele({ access: 'open', over: null }), 'me')).toBe('open');
    expect(role(tele({ access: 'code', over: null, driver: true, driver_id: 'me' }), 'me')).toBe('driver');
    expect(role(tele({ access: 'code', over: null, driver: true, driver_id: 'other' }), 'me')).toBe('spectator');
    expect(role(tele({ access: 'code', over: null, driver: false, driver_id: null }), undefined)).toBe('spectator');
  });

  it('names the holder in a code session', () => {
    expect(controlHolder(tele({ access: 'code', over: null, driver: true, driver_id: 'me' }), 'me')).toBe('you (the driver)');
    expect(controlHolder(tele({ access: 'code', over: null, driver: true, driver_id: 'x' }), 'me')).toBe('the driver (another person)');
    expect(controlHolder(tele({ access: 'code', over: 'killed' }), 'me')).toMatch(/ended/);
  });

  it('every server refusal code has words', () => {
    for (const code of ['spectator', 'bad_code', 'driver_present', 'rate_limited', 'session_over', 'session_full', 'stopped']) {
      expect(refusalWords(code, 'raw')).not.toBe('raw');
    }
    expect(refusalWords('something_new', 'raw')).toBe('raw');
  });
});
