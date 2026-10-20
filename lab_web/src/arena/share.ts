// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Share links (M1.8): a run is its spec, its seed and its input log (README
 * 5.2), so a link carries exactly those -- plus the tick it ended at and the
 * hash chain it ended with, so the page that opens it can say whether it
 * reproduced the run EXACTLY (same chain) rather than claim it.
 *
 *   ?view=arena&run=<base64url(JSON)>
 *
 * Inputs keep their exact doubles (JSON's shortest round-trip form), and
 * each row keeps the tick it was applied at. Decoding refuses anything that
 * is not a well-formed v1 run; it never guesses.
 */

import { boundedJson, boundedTick, boundedInputs } from '../links/bounds.mjs';

import type { InputRow } from './protocol';

export interface SharedRun {
  v: 1;
  hash_version?: 1 | 2 | 3;
  spec: string;        // sha256 hex of the World Spec's canonical bytes
  seed: number;
  ticks: number;       // the run ended after this many ticks
  chain: string;       // the Arena's hash chain after `ticks`
  inputs: InputRow[];
}

// M2.3 appends kidnap and config, M4.3 autonomy and grasp: an older link's kind indices are unchanged
const KINDS = ['goal', 'teleop', 'stop', 'planner', 'reset', 'kidnap', 'config', 'autonomy', 'grasp'] as const;
type Row = [number, number, ...(number | string)[]];

function toRow(r: InputRow): Row {
  const k = KINDS.indexOf(r.kind);
  if (r.kind === 'goal') return [r.tick, k, r.x ?? 0, r.y ?? 0];
  if (r.kind === 'teleop') return [r.tick, k, r.linear ?? 0, r.angular ?? 0];
  if (r.kind === 'planner' || r.kind === 'config') return [r.tick, k, r.choice ?? ''];
  if (r.kind === 'kidnap') return [r.tick, k, r.x ?? 0, r.y ?? 0, r.theta ?? 0, r.has_theta ? 1 : 0];
  return [r.tick, k];
}

function fromRow(a: unknown): InputRow {
  if (!Array.isArray(a) || a.length < 2) throw new Error('bad input row');
  const [tick, k, p, q, th, ht] = a as [number, number, unknown, unknown, unknown, unknown];
  if (!Number.isInteger(tick) || tick < 0 || !Number.isInteger(k) || k < 0 || k >= KINDS.length) throw new Error('bad input row');
  const kind = KINDS[k];
  const num = (v: unknown) => { if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error('bad number'); return v; };
  if (kind === 'goal') return { tick, kind, x: num(p), y: num(q) };
  if (kind === 'teleop') return { tick, kind, linear: num(p), angular: num(q) };
  if (kind === 'planner' || kind === 'config') { if (typeof p !== 'string') throw new Error(`bad ${kind}`); return { tick, kind, choice: p }; }
  if (kind === 'kidnap') return { tick, kind, x: num(p), y: num(q), theta: num(th), has_theta: ht === 1 };
  return { tick, kind };
}

const b64url = (s: string) => btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export function encodeRun(r: SharedRun): string {
  const json = JSON.stringify({ v: 1, ...(r.hash_version ? { hv: r.hash_version } : {}), s: r.spec, e: r.seed, t: r.ticks, c: r.chain, i: r.inputs.map(toRow) });
  const bytes = new TextEncoder().encode(json);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return b64url(bin);
}

export function decodeRun(param: string): SharedRun {
  const d = boundedJson(param);
  if (![1, 2, 3].includes(d.hv ?? 1)) throw new Error('unknown hash version');
  boundedTick(d.t, 'ticks');
  boundedInputs(d.i, true, d.t as number);
  if (d.v !== 1) throw new Error(`run link version ${String(d.v)} is not 1`);
  if (typeof d.s !== 'string' || !/^[0-9a-f]{64}$/.test(d.s)) throw new Error('the run link has no spec hash');
  if (!Number.isSafeInteger(d.e) || (d.e as number) < 0) throw new Error('the run link has no seed');
  if (!Number.isSafeInteger(d.t) || (d.t as number) < 0) throw new Error('the run link has no tick count');
  if (typeof d.c !== 'string' || !/^[0-9a-f]{64}$/.test(d.c)) throw new Error('the run link has no hash chain');
  if (!Array.isArray(d.i)) throw new Error('the run link has no inputs');
  const inputs = d.i.map(fromRow);
  for (let k = 1; k < inputs.length; k += 1) if (inputs[k].tick < inputs[k - 1].tick) throw new Error('inputs out of order');
  return { v: 1, ...(d.hv ? { hash_version: d.hv as 1 | 2 | 3 } : {}), spec: d.s, seed: d.e as number, ticks: d.t as number, chain: d.c, inputs };
}

/** The share URL for a run, on this page's origin and base. */
export function shareUrl(r: SharedRun, base: string, origin = window.location.origin): string {
  return `${origin}${base}?view=arena&run=${encodeRun(r)}`;
}
