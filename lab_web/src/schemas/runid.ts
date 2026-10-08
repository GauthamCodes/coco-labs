// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `coco_schemas.runid` in TypeScript: the run identity, identical to
 * Python's (vectors: coco_schemas/test/vectors/run_id.json).
 *
 *   spec_sha256 = sha256(spec bytes)
 *   run_id      = sha256("coco.run_id.v1\n" + canonical JSON of
 *                 {"engines": [[name, version]...] sorted, "seed": n, "spec_sha256": h})
 *
 * Canonical JSON is Python's (sorted keys, no spaces, ensure_ascii), the
 * same as `bundle/canonical.ts`. The seed is a decimal integer in
 * [0, 2^64): taken as a bigint or decimal string, so it is never rounded.
 */

import { compareCodePoints, pyString } from '../bundle/canonical';
import { concatBytes, sha256Hex } from '../bundle/sha256';

const DOMAIN = new TextEncoder().encode('coco.run_id.v1\n');
const U64 = 2n ** 64n;

export function seedOf(seed: bigint | number | string): bigint {
  let s: bigint;
  if (typeof seed === 'bigint') s = seed;
  else if (typeof seed === 'number' && Number.isSafeInteger(seed)) s = BigInt(seed);
  else if (typeof seed === 'string' && /^(0|[1-9]\d*)$/.test(seed)) s = BigInt(seed);
  else throw new RangeError(`seed must be an integer, got ${String(seed)}`);
  if (s < 0n || s >= U64) throw new RangeError(`seed must be in [0, 2^64), got ${s}`);
  return s;
}

export async function specSha256(spec: Uint8Array): Promise<string> {
  return sha256Hex(spec);
}

export async function runId(spec: Uint8Array, seed: bigint | number | string,
  engines: ReadonlyArray<readonly [string, string]>): Promise<string> {
  const pairs = engines.map(([n, v]) => [String(n), String(v)] as const)
    .sort((a, b) => compareCodePoints(a[0], b[0]) || compareCodePoints(a[1], b[1]));
  if (new Set(pairs.map(([n]) => n)).size !== pairs.length) throw new Error('engine named twice');
  const identity = `{"engines":[${pairs.map(([n, v]) => `[${pyString(n)},${pyString(v)}]`).join(',')}],`
    + `"seed":${seedOf(seed).toString()},"spec_sha256":${pyString(await specSha256(spec))}}`;
  return sha256Hex(concatBytes([DOMAIN, new TextEncoder().encode(identity)]));
}
