// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.5: code in a link. The file (and what to run it on) is deflate-compressed into the URL
 * fragment, `#code=<base64url>`, so it never reaches a server (fragments are not sent). Past
 * LINK_LIMIT characters the link is refused with a clear message: download the .py instead.
 * Opening such a link only SHOWS the code; nothing runs until the reader presses
 * "Run this code" (ADR 0012).
 */
export const LINK_LIMIT = 64 * 1024;
export const LINK_VERSION = 1;

export interface CodeLink { v: number; code: string; file: string; suite?: string; index?: number; template?: string }

function b64url(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function unb64url(s: string): Uint8Array {
  const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}
async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Response(new Blob([bytes as Uint8Array<ArrayBuffer>]).stream().pipeThrough(stream));
  return new Uint8Array(await out.arrayBuffer());
}

/** The fragment for a file; throws past the limit (say so; offer the .py). */
export async function codeFragment(link: Omit<CodeLink, 'v'>): Promise<string> {
  const json = new TextEncoder().encode(JSON.stringify({ v: LINK_VERSION, ...link }));
  const frag = `code=${b64url(await pipe(json, new CompressionStream('deflate-raw')))}`;
  if (frag.length > LINK_LIMIT) {
    throw new Error(`This file makes a ${Math.round(frag.length / 1024)} KB link; links carry at most ${LINK_LIMIT / 1024} KB. Download the .py and share the file instead.`);
  }
  return frag;
}

/** Read `#code=...` (null when the fragment has none); throws on a damaged link. */
export async function readCodeFragment(hash: string): Promise<CodeLink | null> {
  const m = /^#?code=([A-Za-z0-9_-]+)$/.exec(hash);
  if (!m) return null;
  if (m[1].length > LINK_LIMIT) throw new Error('This link is longer than COCO Lab accepts.');
  const json = new TextDecoder().decode(await pipe(unb64url(m[1]), new DecompressionStream('deflate-raw')));
  const o = JSON.parse(json) as Partial<CodeLink>;
  if (o.v !== LINK_VERSION || typeof o.code !== 'string' || typeof o.file !== 'string') throw new Error('This code link is not one COCO Lab can read.');
  return { v: o.v, code: o.code, file: o.file.replace(/[^\w.-]/g, '_').slice(0, 64) || 'algorithm.py',
    suite: typeof o.suite === 'string' ? o.suite : undefined, index: Number.isInteger(o.index) ? o.index : undefined,
    template: typeof o.template === 'string' ? o.template : undefined };
}
