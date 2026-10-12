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

import { deflateSync, inflateSync } from 'three/addons/libs/fflate.module.js';

/** A link's compressed payload, and what it may inflate to, at most (bytes). */
export const LIMITS = { z: 65536, json: 4 * 1024 * 1024 };

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

function bytesB64(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return b64url(s);
}

export function encodeScore(x: SharedScore): string {
  const s = x.submission;
  const json = JSON.stringify({ v: 1, h: s.level_hash, i: s.inputs, r: x.result_hash });
  return `?view=play&c=${s.challenge}&l=${s.level}&z=${bytesB64(deflateSync(new TextEncoder().encode(json), { level: 9 }))}`;
}

export function decodeScore(params: URLSearchParams): SharedScore | null {
  const c = params.get('c'); const l = params.get('l'); const s = params.get('s'); const z = params.get('z');
  if (!c || !l || !(s || z) || !ID.test(c) || !ID.test(l)) return null;
  try {
    let bytes = Uint8Array.from(unb64url((z ?? s)!), (ch) => ch.charCodeAt(0));
    if (z) {
      if (bytes.length > LIMITS.z) return null;
      bytes = inflateSync(bytes, { out: new Uint8Array(LIMITS.json) });
    }
    const j = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
    if (j.v !== 1 || typeof j.h !== 'string' || !HEX64.test(j.h) || typeof j.r !== 'string' || !HEX64.test(j.r) || j.i === undefined) return null;
    return { submission: { v: 1, challenge: c, level: l, level_hash: j.h, inputs: j.i }, result_hash: j.r };
  } catch {
    return null;
  }
}
