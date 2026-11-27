// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * R5.5: a world-editor level in a link. `#level=v1.<base64url(deflate-raw(JSON))>`: the World Spec and the
 * editor's goals, nothing else (no names, no tracking; the link is the visitor's to share). The version
 * prefix stays so an older link keeps meaning what it meant. Decoding refuses anything that is not a
 * World Spec v3 with goals; the Python reader then validates the level as it validates every spec.
 */

export const LINK_VERSION = 'v1';
const MAX_JSON = 512 * 1024;                     // a level's JSON is a few kB; refuse anything absurd
const MAX_TOKEN = 128 * 1024;                    // the link itself (a URL fragment)

/** `editor`: the editor's own state, so a shared link opens again for editing (Play ignores it) */
export interface EditorLevel { spec: Record<string, unknown>; goals: [number, number][]; editor?: unknown }

const b64url = (b: Uint8Array) => btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64url = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));

async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Response(new Blob([bytes as Uint8Array<ArrayBuffer>]).stream().pipeThrough(stream));
  return new Uint8Array(await out.arrayBuffer());
}

export async function encodeLevel(level: EditorLevel): Promise<string> {
  const json = new TextEncoder().encode(JSON.stringify({ spec: level.spec, goals: level.goals, ...(level.editor ? { editor: level.editor } : {}) }));
  return `${LINK_VERSION}.${b64url(await pipe(json, new CompressionStream('deflate-raw')))}`;
}

/** Inflate, refusing as soon as the output passes `max` bytes: a few-kB deflate bomb never reaches memory. */
async function inflateCapped(bytes: Uint8Array, max: number): Promise<Uint8Array> {
  const reader = new Blob([bytes as Uint8Array<ArrayBuffer>]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
  const chunks: Uint8Array[] = [];
  let n = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    n += value.length;
    if (n > max) { await reader.cancel().catch(() => undefined); throw new Error('the level link is too large'); }
    chunks.push(value);
  }
  const out = new Uint8Array(n);
  let at = 0;
  for (const c of chunks) { out.set(c, at); at += c.length; }
  return out;
}

export async function decodeLevel(token: string): Promise<EditorLevel> {
  const dot = token.indexOf('.');
  if (dot < 0 || token.slice(0, dot) !== LINK_VERSION) throw new Error(`not a ${LINK_VERSION} level link`);
  if (token.length > MAX_TOKEN) throw new Error('the level link is too large');
  const raw = await inflateCapped(unb64url(token.slice(dot + 1)), MAX_JSON);
  const doc = JSON.parse(new TextDecoder().decode(raw)) as { spec?: Record<string, unknown>; goals?: unknown; editor?: unknown };
  if (!doc.spec || doc.spec.spec_version !== 'coco.world_spec.v3') throw new Error('the link holds no World Spec v3');
  const goals = Array.isArray(doc.goals) ? doc.goals : [];
  if (!goals.every((g) => Array.isArray(g) && g.length === 2 && g.every((v) => typeof v === 'number' && Number.isFinite(v)))) throw new Error('the link\'s goals are not [x, y] pairs');
  return { spec: doc.spec, goals: goals as [number, number][], ...(doc.editor ? { editor: doc.editor } : {}) };
}

/** The level from the page's `#level=` hash, if there is one. */
export async function levelFromHash(hash: string): Promise<EditorLevel | null> {
  const m = /(?:^#|&)level=([A-Za-z0-9._-]+)/.exec(hash);
  return m ? decodeLevel(m[1]) : null;
}
