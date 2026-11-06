// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.2 (ADR 0012): what the user-code worker takes away from itself before any user code
 * loads. Every way out of a worker -- network, storage, other contexts, devices,
 * notifications -- is deleted from the global object and its prototype chain, then pinned to
 * `undefined` so it cannot be put back by assignment. `postMessage` (to the page, which treats
 * every message as data) stays. `eval`, `Function` and a dynamic `import()` of new code are
 * stopped by the CSP the worker inherits from the page (it starts from a `blob:` URL), not here;
 * probe() checks that too.
 */

/** Globals no algorithm needs and every escape uses. */
export const REMOVED_GLOBALS = [
  'fetch', 'fetchLater', 'XMLHttpRequest', 'XMLHttpRequestUpload', 'WebSocket', 'WebSocketStream', 'WebTransport',
  'EventSource', 'importScripts', 'Worker', 'SharedWorker', 'ServiceWorker', 'BroadcastChannel', 'MessageChannel',
  'indexedDB', 'IDBFactory', 'caches', 'CacheStorage', 'Notification', 'RTCPeerConnection', 'webkitRTCPeerConnection',
  'RTCDataChannel', 'RTCRtpScriptTransform', 'requestFileSystem', 'webkitRequestFileSystem', 'requestFileSystemSync',
  'webkitRequestFileSystemSync', 'FileSystemHandle', 'FileSystemDirectoryHandle', 'FileSystemFileHandle',
  'FileSystemSyncAccessHandle', 'StorageManager', 'LockManager', 'Serial', 'USB', 'HID', 'Bluetooth',
  'NavigatorUAData', 'PushManager', 'BackgroundFetchManager', 'cookieStore', 'CookieStore',
] as const;

type Bag = Record<string, unknown>;

function pin(g: Bag, name: string): void {
  try {
    Object.defineProperty(g, name, { value: undefined, writable: false, configurable: false, enumerable: false });
  } catch { /* already pinned */ }
}

/** Take every way out away from `g` (a worker's `self`); return what was there. */
export function lockdown(g: Bag): string[] {
  const removed: string[] = [];
  for (const name of REMOVED_GLOBALS) {
    let had = false;
    for (let o: Bag | null = g; o && o !== Object.prototype; o = Object.getPrototypeOf(o) as Bag | null) {
      const d = Object.getOwnPropertyDescriptor(o, name);
      if (!d) continue;
      had = true;
      if (d.configurable) delete o[name];
    }
    pin(g, name);
    if (had) removed.push(name);
  }
  // navigator: only the harmless facts stay (no storage, locks, devices, service worker)
  const nav = (g.navigator ?? {}) as { userAgent?: string; hardwareConcurrency?: number; language?: string };
  const safe = Object.freeze({ userAgent: String(nav.userAgent ?? ''), hardwareConcurrency: Number(nav.hardwareConcurrency ?? 1),
    language: String(nav.language ?? '') });
  for (let o: Bag | null = g; o && o !== Object.prototype; o = Object.getPrototypeOf(o) as Bag | null) {
    const d = Object.getOwnPropertyDescriptor(o, 'navigator');
    if (d?.configurable) delete o.navigator;
  }
  try { Object.defineProperty(g, 'navigator', { value: safe, writable: false, configurable: false }); } catch { /* pinned */ }
  removed.push('navigator (replaced)');
  return removed;
}

/**
 * A hard memory ceiling: Emscripten grows its memory through `WebAssembly.Memory.prototype.grow`,
 * so refusing a grow past `ceilingBytes` makes the allocation fail inside the call (Python
 * raises MemoryError) instead of the tab running out of memory.
 */
export function capMemory(ceilingBytes: number, g: { WebAssembly: typeof WebAssembly } = globalThis): void {
  const proto = g.WebAssembly.Memory.prototype as unknown as { grow(delta: number): number };
  const grow = proto.grow;
  Object.defineProperty(proto, 'grow', {
    configurable: false, writable: false,
    value(this: WebAssembly.Memory, delta: number) {
      if (this.buffer.byteLength + delta * 65536 > ceilingBytes) {
        throw new RangeError(`the algorithm's memory ceiling (${Math.round(ceilingBytes / 2 ** 20)} MiB)`);
      }
      return grow.call(this, delta);
    },
  });
}

/** What is still reachable after lockdown (fixed probes, no user input): every value should say blocked. */
export async function probe(g: Bag): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  for (const name of [...REMOVED_GLOBALS, 'document', 'window', 'localStorage', 'sessionStorage', 'parent', 'top', 'opener']) {
    out[name] = g[name] === undefined ? 'blocked' : `REACHABLE (${typeof g[name]})`;
  }
  const nav = g.navigator as Bag | undefined;
  for (const n of ['storage', 'locks', 'serviceWorker', 'usb', 'serial', 'hid', 'bluetooth', 'sendBeacon']) {
    out[`navigator.${n}`] = nav?.[n] === undefined ? 'blocked' : 'REACHABLE';
  }
  const evalFn = g.eval as ((s: string) => unknown) | undefined;
  try { evalFn?.('1'); out.eval = evalFn ? 'REACHABLE' : 'blocked'; } catch (e) { out.eval = `blocked (${(e as Error).name})`; }
  try {
    const F = (function () { /* any function */ }).constructor as FunctionConstructor;
    F('return 1')();
    out.Function = 'REACHABLE';
  } catch (e) { out.Function = `blocked (${(e as Error).name})`; }
  for (const [label, url] of [['import(remote)', 'https://example.invalid/x.mjs'], ['import(data:)', 'data:text/javascript,export default 1']]) {
    try { await import(/* @vite-ignore */ url); out[label] = 'REACHABLE'; } catch (e) { out[label] = `blocked (${(e as Error).name})`; }
  }
  return out;
}
