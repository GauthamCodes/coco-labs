// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Share links, format v1. A link names a catalog bundle and, optionally,
 * the settings (indices into the catalog's `settings` lists) and the map
 * edits (run-length, relative to that bundle's map), plus a 12-hex prefix
 * of the resulting trace's digest. Opening it reruns coco_lab in the
 * worker on the SAME inputs and compares digests, so the page can say
 * whether it reproduced the exact trace.
 *
 *   ?v=1&bundle=<id>&s=<alg>.<heu>.<conn>.<tie>.<weight>&e=<runs>&h=<12 hex>
 *
 * `e` is base64url of unsigned LEB128 varints, two per run of consecutive
 * changed cells (row-major index): the gap since the previous run's end,
 * then `(length - 1) * 2 + value` (value 0 = free, 1 = occupied). A link is
 * untrusted input: every count and index is bounded before it is used.
 */

import type { SettingsAnalysis } from '../bundle/load';
import { TRACE_COLUMNS, type DecodedBundle } from '../bundle/model';
import { concatBytes, sha256Hex } from '../bundle/sha256';
import type { Stroke } from '../worker/protocol';
import type { SearchSettings } from './settings';

export const SHARE_VERSION = '1';

export class ShareError extends Error {}

export interface EditRun {
  start: number; // row-major cell index
  length: number;
  value: 0 | 1;
}

export interface ShareState {
  bundle: string;
  settings: SearchSettings | null;
  runs: EditRun[];
  digest: string | null; // 12 hex, or null
}

// -- edits --------------------------------------------------------------------

/** The cells where `cur` differs from `base`, as runs. `cur` must be 0/1 there. */
export function diffRuns(base: Uint8Array, cur: Uint8Array): EditRun[] {
  if (base.length !== cur.length) throw new ShareError('the maps differ in size');
  const runs: EditRun[] = [];
  for (let i = 0; i < cur.length; i++) {
    if (cur[i] === base[i]) continue;
    const v = cur[i];
    if (v !== 0 && v !== 1) throw new ShareError(`cell ${i} became ${v}; only free (0) and occupied (1) can be shared`);
    const last = runs[runs.length - 1];
    if (last && last.start + last.length === i && last.value === v) last.length++;
    else runs.push({ start: i, length: 1, value: v });
  }
  return runs;
}

/** The runs as the worker's strokes: free cells, then occupied cells. */
export function runsToStrokes(runs: EditRun[], width: number): Stroke[] {
  const free: Array<[number, number]> = [];
  const occ: Array<[number, number]> = [];
  for (const r of runs) {
    for (let i = r.start; i < r.start + r.length; i++) {
      (r.value === 1 ? occ : free).push([Math.floor(i / width), i % width]);
    }
  }
  const out: Stroke[] = [];
  if (free.length) out.push({ value: 'free', cells: free });
  if (occ.length) out.push({ value: 'occupied', cells: occ });
  return out;
}

function pushVarint(out: number[], n: number): void {
  if (!Number.isSafeInteger(n) || n < 0) throw new ShareError(`cannot encode ${n}`);
  do {
    let b = n % 128;
    n = Math.floor(n / 128);
    if (n > 0) b |= 128;
    out.push(b);
  } while (n > 0);
}

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

function toBase64url(bytes: number[]): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] ?? 0) << 8) | (bytes[i + 2] ?? 0);
    const k = Math.min(3, bytes.length - i) + 1;
    for (let j = 0; j < k; j++) s += B64[(n >> (18 - 6 * j)) & 63];
  }
  return s;
}

function fromBase64url(s: string): number[] {
  if (!/^[A-Za-z0-9_-]*$/.test(s) || s.length % 4 === 1) throw new ShareError('the edits are not base64url');
  const out: number[] = [];
  for (let i = 0; i < s.length; i += 4) {
    const chunk = s.slice(i, i + 4);
    let n = 0;
    for (let j = 0; j < 4; j++) n = (n << 6) | (j < chunk.length ? B64.indexOf(chunk[j]) : 0);
    const k = chunk.length - 1;
    for (let j = 0; j < k; j++) out.push((n >> (16 - 8 * j)) & 255);
  }
  return out;
}

export function encodeRuns(runs: EditRun[]): string {
  const bytes: number[] = [];
  let end = 0;
  for (const r of runs) {
    if (r.start < end || r.length < 1) throw new ShareError('runs must be sorted and non-empty');
    pushVarint(bytes, r.start - end);
    pushVarint(bytes, (r.length - 1) * 2 + r.value);
    end = r.start + r.length;
  }
  return toBase64url(bytes);
}

/** Decode `e` for a map of `cells` cells; refuse anything out of bounds. */
export function decodeRuns(s: string, cells: number): EditRun[] {
  const bytes = fromBase64url(s);
  const nums: number[] = [];
  let n = 0;
  let shift = 1;
  for (let i = 0; i < bytes.length; i++) {
    n += (bytes[i] & 127) * shift;
    if (!Number.isSafeInteger(n)) throw new ShareError('an edit number is too large');
    if (bytes[i] & 128) {
      shift *= 128;
      if (i === bytes.length - 1) throw new ShareError('the edits end mid-number');
    } else {
      nums.push(n);
      n = 0;
      shift = 1;
    }
  }
  if (nums.length % 2) throw new ShareError('the edits have an odd count');
  const runs: EditRun[] = [];
  let end = 0;
  for (let i = 0; i < nums.length; i += 2) {
    const start = end + nums[i];
    const length = Math.floor(nums[i + 1] / 2) + 1;
    const value = (nums[i + 1] % 2) as 0 | 1;
    if (start + length > cells) throw new ShareError('an edit lies outside the map');
    runs.push({ start, length, value });
    end = start + length;
  }
  return runs;
}

// -- settings -----------------------------------------------------------------

export function encodeSettings(s: SearchSettings, sa: SettingsAnalysis): string {
  const idx = (list: unknown[], v: unknown, what: string) => {
    const i = list.indexOf(v);
    if (i < 0) throw new ShareError(`${what} ${String(v)} is not in the catalog`);
    return i;
  };
  return [idx(sa.algorithms, s.algorithm, 'algorithm'), idx(sa.heuristics, s.heuristic, 'heuristic'),
    s.connectivity, idx(sa.tie_breaks, s.tieBreak, 'tie-break'), idx(sa.weights, s.weight, 'weight')].join('.');
}

export function decodeSettings(str: string, sa: SettingsAnalysis): SearchSettings {
  const p = str.split('.');
  if (p.length !== 5 || !p.every((x) => /^\d{1,3}$/.test(x))) throw new ShareError('the settings are malformed');
  const [a, h, c, t, w] = p.map(Number);
  const pick = <T>(list: T[], i: number, what: string): T => {
    if (i >= list.length) throw new ShareError(`${what} ${i} is not in the catalog`);
    return list[i];
  };
  if (c !== 4 && c !== 8) throw new ShareError('connectivity must be 4 or 8');
  return {
    algorithm: pick(sa.algorithms, a, 'algorithm'), heuristic: pick(sa.heuristics, h, 'heuristic'),
    connectivity: c, tieBreak: pick(sa.tie_breaks, t, 'tie-break'), weight: pick(sa.weights, w, 'weight'),
  };
}

// -- the link -----------------------------------------------------------------

export function shareQuery(st: ShareState, sa: SettingsAnalysis | undefined): string {
  const q = new URLSearchParams();
  q.set('v', SHARE_VERSION);
  q.set('bundle', st.bundle);
  if (st.settings && sa) q.set('s', encodeSettings(st.settings, sa));
  if (st.runs.length) q.set('e', encodeRuns(st.runs));
  if (st.digest) q.set('h', st.digest);
  return '?' + q.toString();
}

/**
 * Parse a query string. Returns null for a plain link (no `v`), so the
 * old `?bundle=<id>` form keeps working; throws ShareError on a bad link.
 */
export function parseShare(search: string, sa: SettingsAnalysis | undefined,
  cellsOf: (bundleId: string) => number | null): ShareState | null {
  const q = new URLSearchParams(search);
  if (!q.has('v')) return null;
  if (q.get('v') !== SHARE_VERSION) throw new ShareError(`share link version ${q.get('v')} is not supported`);
  const bundle = q.get('bundle') ?? '';
  const cells = cellsOf(bundle);
  if (cells === null) throw new ShareError(`the link names bundle "${bundle}", which this site does not serve`);
  const s = q.get('s');
  if (s && !sa) throw new ShareError('this site has no settings table');
  const h = q.get('h');
  if (h !== null && !/^[0-9a-f]{12}$/.test(h)) throw new ShareError('the digest is malformed');
  return {
    bundle,
    settings: s && sa ? decodeSettings(s, sa) : null,
    runs: q.get('e') ? decodeRuns(q.get('e')!, cells) : [],
    digest: h,
  };
}

// -- the digest ---------------------------------------------------------------

/**
 * sha256 over the trace columns' little-endian bytes, in the bundle's column
 * order: `b''.join(data for name, _, data in bundle.arrays()
 * if name.startswith('trace.'))` in Python (tools/make_share_vectors.py).
 */
export async function traceDigest(b: DecodedBundle): Promise<string> {
  const parts = TRACE_COLUMNS.map((c) => {
    const a = b.trace.events[c];
    return new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
  });
  return sha256Hex(concatBytes(parts));
}
