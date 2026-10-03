// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Is a remote COCO Live session on right now, and when is the next one?
 *
 * Pure: the fetch and the clock are injected, so every verdict is tested
 * (`test/live_status.test.ts`). The page says "live now" ONLY when the
 * configured endpoint answers /healthz as coco.v1 with an open code-access
 * session -- never because an endpoint is configured, or a session is on
 * the schedule. Anything else fails safe to "not live".
 *
 * Who may drive is decided by the server (coco_web/control.py). Nothing here
 * grants or refuses control.
 */

export type LiveVerdict =
  | { state: 'live'; driver: boolean; leftS: number | null; clients: number | null }
  | { state: 'starting' }
  | { state: 'ended' }
  | { state: 'offline'; why: string }
  | { state: 'unconfigured' };

/** The /healthz URL on the same host as a wss:// coco.v1 endpoint, or null. */
export function healthUrl(ws: string | null | undefined): string | null {
  if (!ws) return null;
  let u: URL;
  try {
    u = new URL(ws);
  } catch {
    return null;
  }
  if (u.protocol !== 'wss:' && u.protocol !== 'ws:') return null;
  if (u.username || u.password) return null;
  return `${u.protocol === 'wss:' ? 'https:' : 'http:'}//${u.host}/healthz`;
}

/** Read a /healthz body (already parsed) into a verdict. */
export function classify(status: number, body: unknown): LiveVerdict {
  if (!body || typeof body !== 'object') return { state: 'offline', why: 'not a coco.v1 health document' };
  const b = body as Record<string, unknown>;
  if (b.protocol !== 'coco.v1') return { state: 'offline', why: 'not a coco.v1 server' };
  const live = b.live as Record<string, unknown> | undefined;
  if (!live || typeof live !== 'object' || live.access !== 'code') {
    // An open (local-appliance) server is never a public session.
    return { state: 'offline', why: 'no public session on this server' };
  }
  if (live.over) return { state: 'ended' };
  if (status !== 200) return { state: 'starting' };
  // Counts and times are never negative; a value that is, is not trusted.
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null);
  return { state: 'live', driver: live.driver === true, leftS: num(live.session_left_s), clients: num(live.clients) };
}

type FetchLike = (url: string, init?: { signal?: AbortSignal; cache?: RequestCache; credentials?: RequestCredentials })
  => Promise<{ status: number; json(): Promise<unknown> }>;

/** Probe the endpoint once. Never throws; anything unexpected is "offline". */
export async function probe(ws: string | null | undefined, fetchFn: FetchLike, timeoutMs = 4000): Promise<LiveVerdict> {
  if (!ws) return { state: 'unconfigured' };
  const url = healthUrl(ws);
  if (!url) return { state: 'offline', why: 'the configured endpoint is not a ws(s):// URL' };
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetchFn(url, { signal: ctl.signal, cache: 'no-store', credentials: 'omit' });
    let body: unknown = null;
    try {
      body = await r.json();
    } catch {
      return { state: 'offline', why: 'the endpoint did not answer with JSON' };
    }
    return classify(r.status, body);
  } catch {
    return { state: 'offline', why: 'the endpoint is unreachable' };
  } finally {
    clearTimeout(timer);
  }
}

export interface Session { start: Date; minutes: number; note: string }

/** Validate the repo's schedule file. Bad entries are dropped, not guessed. */
export function loadSchedule(doc: unknown): Session[] {
  if (!doc || typeof doc !== 'object' || (doc as { version?: unknown }).version !== 1) return [];
  const raw = (doc as { sessions?: unknown }).sessions;
  if (!Array.isArray(raw)) return [];
  const out: Session[] = [];
  for (const s of raw) {
    if (!s || typeof s !== 'object') continue;
    const { start, minutes, note } = s as Record<string, unknown>;
    // An explicit offset (Z or ±hh:mm) is required: a bare local time would
    // mean a different instant for every visitor.
    if (typeof start !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(start)) continue;
    const d = new Date(start);
    if (Number.isNaN(d.getTime())) continue;
    if (typeof minutes !== 'number' || !(minutes > 0) || minutes > 24 * 60) continue;
    out.push({ start: d, minutes, note: typeof note === 'string' ? note : '' });
  }
  return out.sort((a, b) => a.start.getTime() - b.start.getTime());
}

/** The session in progress at `now`, else the next one, else null. */
export function nextSession(sessions: Session[], now: Date): { session: Session; inProgress: boolean } | null {
  for (const s of sessions) {
    const end = s.start.getTime() + s.minutes * 60_000;
    if (end <= now.getTime()) continue;
    return { session: s, inProgress: s.start.getTime() <= now.getTime() };
  }
  return null;
}

/** What the public Live tab says, in words. Never "live" unless the probe said so. */
export function statusWords(v: LiveVerdict, next: ReturnType<typeof nextSession>): { headline: string; live: boolean } {
  const when = next ? `${next.session.start.toUTCString()} (${next.session.minutes} min)` : null;
  switch (v.state) {
    case 'live': {
      const left = v.leftS != null ? `, ${Math.floor(v.leftS / 60)} min left` : '';
      return { live: true, headline: `Live now${left}. ${v.driver ? 'Someone is driving; you can watch.' : 'Nobody is driving yet; the host has the control code.'}` };
    }
    // /healthz 503 means "a required component is not up": the stack may be
    // starting, or something went down mid-session. Say only what is known.
    case 'starting': return { live: false, headline: 'A session is open, but the robot stack is not ready (starting, or a component is down).' };
    case 'ended': return { live: false, headline: `The last session has ended.${when ? ` Next: ${when}.` : ' No session is scheduled.'}` };
    default:
      return { live: false, headline: `No live session right now.${when ? ` ${next!.inProgress ? 'One is scheduled now but not reachable' : 'Next scheduled'}: ${when}.` : ' No session is scheduled.'}` };
  }
}
