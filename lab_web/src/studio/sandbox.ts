// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.2: the page's side of the user-code worker (ADR 0012).
 *
 * - The worker starts from a `blob:` URL that imports the built worker module, so it inherits
 *   this page's CSP (a worker loaded from a same-origin URL would get GitHub Pages' headers,
 *   which carry none).
 * - Every message from it is untrusted data: only known types with the expected field types are
 *   used; text is only ever rendered as text.
 * - The watchdog: the worker posts `beat` after each call of the user's function. A run whose
 *   worker is silent past the family's per-call limit, or reports memory past the ceiling, is
 *   ended by terminating the worker; the next request boots a fresh one.
 */
import sandboxWorkerUrl from './sandbox.worker.ts?worker&url';
import { pinnedBase } from '../offline/updates';

export type Family = 'planning' | 'control' | 'localisation';

/** The hard limit on one call of the user's function (ms), per family. */
export const CALL_LIMIT_MS: Record<Family, number> = { planning: 30_000, control: 5_000, localisation: 5_000 };
/** Booting the interpreter and coco_lab is not a call; it has its own, longer limit. */
export const BOOT_LIMIT_MS = 120_000;

export interface Chunk { events: Record<string, Record<string, unknown>[]>; frames: Frame[] }
export interface Frame {
  tick: number; truth: number[]; belief: number[]; v: number; w: number; contact: boolean;
  candidates: { points: number[][]; valid: boolean }[]; lookahead: number[] | null;
  particles: { x: number[]; y: number[]; theta: number[] } | null; estimate: Record<string, number> | null;
  scan: number[]; waypoints: number[][] | null;
}

export type Ended = { ok: true; result: string; ms: number } |
  { ok: false; reason: 'time_limit' | 'memory_limit' | 'crashed' | 'error'; message: string; calls: number };

interface Pending { family: Family; onChunk?: (c: Chunk) => void; done: (e: Ended) => void; timer: number; calls: number }

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

export function createSandboxWorker(): Worker {
  const url = new URL(sandboxWorkerUrl, globalThis.location.href).href;
  const blob = new Blob([`import ${JSON.stringify(url)};\n`], { type: 'text/javascript' });
  const blobUrl = URL.createObjectURL(blob);
  const w = new Worker(blobUrl, { type: 'module', name: 'coco-algorithm-sandbox' });
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
  return w;
}

export class Sandbox {
  private worker: Worker | null = null;
  private ready: Promise<string[]> | null = null;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  /** The memory the worker reported when it became ready (bytes) and the ceiling above it. */
  bootMemory = 0;
  readonly memoryHeadroom = 1024 * 2 ** 20;
  restarts = 0;

  constructor(private readonly make: () => Worker = createSandboxWorker, private readonly base: string = pinnedBase()) {}

  /** Boot (once); resolves with what the lockdown removed. */
  start(): Promise<string[]> {
    if (this.ready) return this.ready;
    const w = this.make();
    this.worker = w;
    this.ready = new Promise<string[]>((resolve, reject) => {
      const t = setTimeout(() => { this.kill(); reject(new Error('the interpreter did not start in time')); }, BOOT_LIMIT_MS);
      w.addEventListener('message', (ev: MessageEvent) => {
        const m = ev.data as unknown;
        if (!isObj(m) || typeof m.type !== 'string') return;
        if (m.type === 'ready') {
          clearTimeout(t);
          this.bootMemory = typeof m.memory === 'number' ? m.memory : 0;
          resolve(Array.isArray(m.removed) ? m.removed.filter((x): x is string => typeof x === 'string') : []);
        } else if (m.type === 'failed' && m.id === undefined) { clearTimeout(t); reject(new Error(String(m.error))); }
        else this.onMessage(m);
      });
      w.addEventListener('error', (e) => { clearTimeout(t); reject(new Error(e.message || 'the sandbox stopped')); this.crash('crashed', e.message || 'the sandbox stopped'); });
    });
    this.ready.catch(() => {});
    // absolute: a blob: worker cannot resolve a path against its own URL
    const abs = new URL(this.base, globalThis.location.href).href;
    w.postMessage({ type: 'boot', pyodideBase: `${abs}generated/pyodide/`, assetsBase: `${abs}generated/` });
    return this.ready;
  }

  /** Run one request (JSON for sandbox_glue.run); the watchdog ends it if a call overruns. */
  async run(request: Record<string, unknown>, family: Family, onChunk?: (c: Chunk) => void): Promise<Ended> {
    await this.start();
    const id = this.nextId++;
    return new Promise<Ended>((resolve) => {
      const p: Pending = { family, onChunk, done: resolve, timer: 0, calls: 0 };
      this.pending.set(id, p);
      this.arm(id, p);
      this.worker!.postMessage({ type: 'run', id, request: JSON.stringify({ ...request, id }) });
    });
  }

  /** The lockdown's own probes (fixed; no user input): every entry should read "blocked". */
  async probe(): Promise<{ js: Record<string, string>; python: Record<string, string> }> {
    await this.start();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const on = (ev: MessageEvent) => {
        const m = ev.data as unknown;
        if (isObj(m) && m.type === 'probe' && m.id === id) {
          this.worker?.removeEventListener('message', on);
          resolve({ js: m.js as Record<string, string>, python: m.python as Record<string, string> });
        }
      };
      this.worker!.addEventListener('message', on);
      setTimeout(() => reject(new Error('probe timed out')), 20_000);
      this.worker!.postMessage({ type: 'probe', id });
    });
  }

  terminate(): void { this.kill(); }

  private arm(id: number, p: Pending): void {
    clearTimeout(p.timer);
    p.timer = setTimeout(() => this.end(id, { ok: false, reason: 'time_limit', calls: p.calls,
      message: `a call to your algorithm ran longer than ${CALL_LIMIT_MS[p.family] / 1000} s (the time limit); the sandbox was restarted` }),
    CALL_LIMIT_MS[p.family]) as unknown as number;
  }

  private onMessage(m: Record<string, unknown>): void {
    if (typeof m.memory === 'number' && this.bootMemory && m.memory > this.bootMemory + this.memoryHeadroom) {
      for (const id of [...this.pending.keys()]) {
        this.end(id, { ok: false, reason: 'memory_limit', calls: this.pending.get(id)!.calls,
          message: `your algorithm used more than ${Math.round(this.memoryHeadroom / 2 ** 20)} MiB; the sandbox was restarted` });
      }
      return;
    }
    if (m.type === 'beat') {
      // the beat carries no id: one request runs at a time
      for (const [id, p] of this.pending) { p.calls = typeof m.calls === 'number' ? m.calls : p.calls; this.arm(id, p); }
      return;
    }
    const id = typeof m.id === 'number' ? m.id : -1;
    const p = this.pending.get(id);
    if (!p) return;
    if (m.type === 'chunk') {
      this.arm(id, p);
      if (p.onChunk && isObj(m.events) && Array.isArray(m.frames)) p.onChunk({ events: m.events as Chunk['events'], frames: m.frames as Frame[] });
    } else if (m.type === 'done' && typeof m.result === 'string') {
      clearTimeout(p.timer);
      this.pending.delete(id);
      // a run that ran out of memory leaves memory that never shrinks: start the next one fresh
      if (m.result.includes('"MemoryError"')) this.kill();
      p.done({ ok: true, result: m.result, ms: typeof m.ms === 'number' ? m.ms : 0 });
    } else if (m.type === 'failed') {
      const msg = String(m.error ?? 'failed');
      // a MemoryError past the ceiling surfaces as the run's own error; say what it was
      const mem = /MemoryError|memory ceiling/.test(msg);
      this.end(id, { ok: false, reason: mem ? 'memory_limit' : 'error', calls: p.calls, message: msg.slice(0, 4000) }, mem);
    }
  }

  private end(id: number, e: Ended, restart = true): void {
    const p = this.pending.get(id);
    if (!p) return;
    clearTimeout(p.timer);
    this.pending.delete(id);
    if (restart && !e.ok) this.kill();
    p.done(e);
  }

  private crash(reason: 'crashed', message: string): void {
    for (const id of [...this.pending.keys()]) this.end(id, { ok: false, reason, message, calls: this.pending.get(id)!.calls });
    this.kill();
  }

  private kill(): void {
    if (this.worker) { this.worker.terminate(); this.restarts += 1; }
    this.worker = null;
    this.ready = null;
    for (const id of [...this.pending.keys()]) {
      const p = this.pending.get(id)!;
      clearTimeout(p.timer);
      this.pending.delete(id);
      p.done({ ok: false, reason: 'crashed', message: 'the sandbox was restarted', calls: p.calls });
    }
  }
}
