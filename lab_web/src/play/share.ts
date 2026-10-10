// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play's challenge-a-friend links (M3.5): a level, its hash and the whole
 * input log -- plus the result hash it scored, so the page that opens it
 * can say whether the score REPRODUCED exactly rather than claim it.
 *
 *   ?view=play&c=<challenge>&l=<level>&s=<base64url(JSON {v, h, i, r})>
 *
 * Decoding refuses anything malformed; it never guesses. `coco verify`
 * (lab_web/tools/verify.mjs) reads the same links.
 */

export interface Submission {
  v: 1;
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

const HEX64 = /^[0-9a-f]{64}$/;
const ID = /^[a-z0-9-]{1,64}$/;
const b64url = (s: string) => btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64url = (s: string) => atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (s.length % 4)) % 4));

function utf8b64(json: string): string {
  const bytes = new TextEncoder().encode(json);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return b64url(s);
}

export function encodeScore(x: SharedScore): string {
  const s = x.submission;
  return `?view=play&c=${s.challenge}&l=${s.level}&s=${utf8b64(JSON.stringify({ v: 1, h: s.level_hash, i: s.inputs, r: x.result_hash }))}`;
}

export function decodeScore(params: URLSearchParams): SharedScore | null {
  const c = params.get('c'); const l = params.get('l'); const s = params.get('s');
  if (!c || !l || !s || !ID.test(c) || !ID.test(l)) return null;
  try {
    const bin = unb64url(s);
    const j = JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (ch) => ch.charCodeAt(0)))) as Record<string, unknown>;
    if (j.v !== 1 || typeof j.h !== 'string' || !HEX64.test(j.h) || typeof j.r !== 'string' || !HEX64.test(j.r) || j.i === undefined) return null;
    return { submission: { v: 1, challenge: c, level: l, level_hash: j.h, inputs: j.i }, result_hash: j.r };
  } catch {
    return null;
  }
}
