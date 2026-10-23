// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.8, update isolation, the page's half (sw.template.js is the worker's).
 *
 * A page is the build of the index it loaded (`<meta name="coco-build">`). It tells the
 * service worker so ('hello'), and the worker answers it from that build's cache even
 * after a newer build takes over. The page's workers name the build in their URLs
 * (`pinnedBase()`: `<base>__b/<build>/`), because a worker's requests carry no page.
 * When a newer build is ready the page shows "New version ready" with Save run and
 * Reload, and never reloads by itself: a run in progress is the player's.
 */
const BASE = import.meta.env.BASE_URL;
const BUILD = /^[0-9a-f]{64}$/;

let pins = false;
let latest: string | null = null;
const listeners = new Set<() => void>();
type Saved = { name: string; data: unknown } | null;
let saver: (() => Saved | Promise<Saved>) | null = null;

/** This page's build, or null (the dev server has none). */
export function documentBuild(): string | null {
  if (typeof document === 'undefined') return null;
  const v = document.querySelector('meta[name="coco-build"]')?.getAttribute('content') ?? '';
  return BUILD.test(v) ? v : null;
}

/** The base a worker loads runtime and data from: pinned to this page's build once the service worker can serve it. */
export function pinnedBase(): string {
  const b = documentBuild();
  return pins && b ? `${BASE}__b/${b}/` : BASE;
}

/** A build other than this page's is installed and ready. */
export function updateReady(): boolean {
  const b = documentBuild();
  return !!(b && latest && latest !== b);
}

export function onUpdate(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

function saw(version: unknown) {
  if (typeof version !== 'string' || !BUILD.test(version) || version === latest) return;
  latest = version;
  listeners.forEach((f) => f());
}

async function hello(worker: ServiceWorker | null) {
  const build = documentBuild();
  if (!worker || !build) return;
  const ch = new MessageChannel();
  const reply = new Promise<unknown>((resolve) => { ch.port1.onmessage = (e) => resolve(e.data); window.setTimeout(() => resolve(null), 3000); });
  worker.postMessage({ type: 'hello', build }, [ch.port2]);
  const d = await reply as { version?: unknown; pins?: unknown } | string | null;
  // a worker from before G1.8 answers nothing (or a bare version) and knows no pinned paths
  if (d && typeof d === 'object') { if (d.pins === true) pins = true; saw(d.version); }
}

/** Start: say which build this page is, listen for newer ones, look for one when the page comes back. */
export function initUpdates(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;
  const sw = navigator.serviceWorker;
  void hello(sw.controller).catch(() => {});
  sw.addEventListener('controllerchange', () => { void hello(sw.controller).catch(() => {}); });
  sw.addEventListener('message', (e) => { if (e.data?.type === 'coco-build') saw(e.data.version); });
  let last = Date.now();
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible' || Date.now() - last < 5 * 60_000) return;
    last = Date.now();
    void sw.getRegistration().then((r) => r?.update()).catch(() => {});
  });
}

/** The view with a run in progress says how to save it (the game: its record; the Arena: its input log). */
export function registerRunSaver(fn: () => Saved | Promise<Saved>): () => void {
  saver = fn;
  return () => { if (saver === fn) saver = null; };
}

export const hasRunSaver = (): boolean => saver !== null;

/** Download the run in progress as JSON; false if there is none. */
export async function saveRun(): Promise<boolean> {
  const r = await saver?.();
  if (!r) return false;
  const url = URL.createObjectURL(new Blob([JSON.stringify(r.data, null, 1) + '\n'], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url; a.download = r.name; a.rel = 'noopener';
  document.body.appendChild(a); a.click(); a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  return true;
}
