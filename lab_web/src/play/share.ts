// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play's challenge-a-friend links (M3.5): a level, its hash and the whole
 * input log -- plus the result hash it scored, so the page that opens it
 * can say whether the score REPRODUCED exactly rather than claim it.
 *
 *   ?view=play&c=<challenge>&l=<level>&z=<base64url(deflate-raw(JSON {v, h, i, r}))>
 *
 * M4.8: the payload is deflated (`z`): a race's input log made links of up to 18 KB,
 * past what a server accepts in a URL (measured: HTTP 431 at 17.9 KB). Links made
 * before (`s`: the same JSON, base64url) still read exactly. Decoding refuses anything
 * malformed, or larger than LIMITS; it never guesses. `coco verify`
 * (lab_web/tools/verify.mjs) reads both forms.
 */

import { deflateSync } from 'three/addons/libs/fflate.module.js';

/** A link's compressed payload, and what it may inflate to, at most (bytes). */
export { LIMITS } from '../links/bounds.mjs';
import { decodeChallenge } from '../links/bounds.mjs';

export interface Submission {
  v: 1;
  hash_version?: 1 | 2;
  challenge: string;
  level: string;
  level_hash: string;
  inputs: unknown;
}

export interface SharedScore {
  submission: Submission;
  /** the result's hash when it was made */
  result_hash: string;
}

const b64url = (s: string) => btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

function bytesB64(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return b64url(s);
}

export function encodeScore(x: SharedScore): string {
  const s = x.submission;
  const json = JSON.stringify({ v: 1, ...(s.hash_version ? { hv: s.hash_version } : {}), h: s.level_hash, i: s.inputs, r: x.result_hash });
  return `?view=play&c=${s.challenge}&l=${s.level}&z=${bytesB64(deflateSync(new TextEncoder().encode(json), { level: 9 }))}`;
}

/**
 * Whether a URL carries a shared submission at all, in either form (M3's `s=`, M4.8's deflated `z=`).
 * Kept beside decodeScore: the page once tested `s=` alone and ignored every `z=` link (M4.10).
 */
export function hasSharedScore(params: URLSearchParams): boolean {
  return params.has('s') || params.has('z');
}

export function decodeScore(params: URLSearchParams): SharedScore | null {
  try { return decodeChallenge(params); } catch { return null; }
}

/** Explanation shown before a worker is booted for a rejected link. */
export function scoreLinkError(params: URLSearchParams): string | null {
  if (!hasSharedScore(params)) return null;
  try { decodeChallenge(params); return null; } catch (e) { return String((e as Error).message); }
}
