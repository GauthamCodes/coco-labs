// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Immutable mesh bytes shared across viewers; a failed fetch can be retried. */
const meshBytes = new Map<string, Promise<ArrayBuffer>>();
export function loadAssetBytes(url: string): Promise<ArrayBuffer> {
  const cached = meshBytes.get(url);
  if (cached) return cached;
  const p = fetch(url, { credentials: 'omit', cache: 'force-cache' }).then(r => {
    if (!r.ok) throw new Error(`Mesh unavailable: ${url}`);
    return r.arrayBuffer();
  }).catch(e => { meshBytes.delete(url); throw e; });
  meshBytes.set(url, p);
  return p;
}
