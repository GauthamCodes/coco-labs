// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * SHA-256 through WebCrypto (`crypto.subtle`), which needs a secure context:
 * GitHub Pages (https), localhost and Node >= 20 all are. SubtleCrypto has
 * no incremental API, so a caller hashing several parts concatenates them
 * first (peak memory ~ 2 x the input; see BUNDLE_FORMAT "Readers").
 */
export async function sha256Hex(data: Uint8Array): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('SHA-256 needs a secure context (https or localhost)');
  const digest = await subtle.digest('SHA-256', data as Uint8Array<ArrayBuffer>);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    out.set(p, off);
    off += p.length;
  }
  return out;
}
