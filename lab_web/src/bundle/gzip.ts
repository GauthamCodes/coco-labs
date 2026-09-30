// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { fail } from './errors';
import { concatBytes } from './sha256';

/**
 * Inflate a gzip file, keeping at most `expected + 1` bytes: the same
 * gzip-bomb bound as `coco_lab.bundle._bounded_gunzip`. A result of
 * `expected + 1` bytes is then refused by the length check, exactly as in
 * Python.
 *
 * The file must start with the gzip magic `1f 8b`. If it does not, the
 * most likely cause is a server that sent `arrays.bin.gz` with
 * `Content-Encoding: gzip`, so the browser already inflated it. That is
 * refused, never repaired.
 */
export async function boundedGunzip(file: Uint8Array, expected: number): Promise<Uint8Array> {
  if (file.length < 2 || file[0] !== 0x1f || file[1] !== 0x8b) {
    fail('compression', 'cannot read arrays.bin.gz: no gzip magic (did the server decode ' +
      'it with Content-Encoding: gzip?)');
  }
  const limit = expected + 1;
  const stream = new Blob([file as Uint8Array<ArrayBuffer>]).stream()
    .pipeThrough(new DecompressionStream('gzip'));
  const reader = stream.getReader();
  const parts: Uint8Array[] = [];
  let total = 0;
  try {
    while (total < limit) {
      const { done, value } = await reader.read();
      if (done) break;
      const take = Math.min(value.length, limit - total);
      parts.push(take === value.length ? value : value.subarray(0, take));
      total += take;
    }
  } catch (exc) {
    fail('compression', `cannot read arrays.bin.gz: ${(exc as Error).message}`);
  } finally {
    reader.cancel().catch(() => undefined);
  }
  return concatBytes(parts);
}
