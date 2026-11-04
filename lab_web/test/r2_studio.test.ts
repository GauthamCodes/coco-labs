// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R2.2-R2.5: the Algorithm Studio's page side -- links, contracts, the lockdown, the watchdog. */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { codeFragment, LINK_LIMIT, readCodeFragment } from '../src/studio/codelink';
import { capMemory, lockdown, probe, REMOVED_GLOBALS } from '../src/studio/lockdown';
import { Sandbox } from '../src/studio/sandbox';
import { codeSha256, kindOf, TEMPLATES } from '../src/studio/templates';

beforeAll(() => { (globalThis as { location?: unknown }).location ??= { href: 'https://example.test/coco-labs/' }; });
afterEach(() => { vi.useRealTimers(); });

describe('code links (R2.5)', () => {
  it('carry the file in the fragment and read back exactly', async () => {
    const code = TEMPLATES[0].source;
    const frag = await codeFragment({ code, file: 'planner_astar.py', suite: 'depot-nav-100', index: 7 });
    expect(frag.startsWith('code=')).toBe(true);
    const back = await readCodeFragment(`#${frag}`);
    expect(back).toEqual({ v: 1, code, file: 'planner_astar.py', suite: 'depot-nav-100', index: 7, template: undefined });
  });
  it('refuse a file past the limit, with a clear message', async () => {
    let s = 0x2545f491;
    const noise = Array.from({ length: 120_000 }, () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return String.fromCharCode(33 + ((s >>> 8) % 90)); }).join('');
    await expect(codeFragment({ code: `# ${noise}\n`, file: 'big.py' })).rejects.toThrow(/at most 64 KB.*Download the \.py/);
    expect(LINK_LIMIT).toBe(65536);
  });
  it('ignore other fragments, sanitise the file name, refuse damage', async () => {
    expect(await readCodeFragment('#expz=abc')).toBeNull();
    const frag = await codeFragment({ code: 'x', file: '../../etc/passwd' });
    expect((await readCodeFragment(`#${frag}`))!.file).toBe('.._.._etc_passwd');
    await expect(readCodeFragment('#code=AAAA')).rejects.toThrow();
  });
});

describe('templates and contracts (R2.3)', () => {
  it('every starter defines exactly one contract', () => {
    for (const t of TEMPLATES) expect(kindOf(t.source), t.id).toBe(t.kind);
    expect(kindOf('def plan(a, b, c, ctx):\n  pass\ndef control(a, b, c, ctx):\n  pass\n')).toBeNull();
    expect(TEMPLATES.filter((t) => t.teaching).map((t) => t.id)).toEqual(['teach_heuristic', 'teach_tune_dwa']);
  });
  it('the page names a file by the sha256 of its UTF-8 bytes (as coco_lab does)', async () => {
    expect(await codeSha256('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  });
});

describe('the lockdown (R2.2)', () => {
  it('deletes and pins every way out, own or inherited', async () => {
    const proto: Record<string, unknown> = { fetch: () => 1, WebSocket: class {}, indexedDB: {} };
    const g = Object.create(proto) as Record<string, unknown>;
    g.XMLHttpRequest = class {};
    g.importScripts = () => 0;
    g.navigator = { userAgent: 'UA', storage: {}, locks: {}, hardwareConcurrency: 8 };
    g.eval = () => { throw new EvalError('CSP'); };
    const removed = lockdown(g);
    for (const n of REMOVED_GLOBALS) expect(g[n], n).toBeUndefined();
    expect(removed).toEqual(expect.arrayContaining(['fetch', 'WebSocket', 'indexedDB', 'XMLHttpRequest', 'importScripts']));
    expect(() => { g.fetch = () => 2; }).toThrow(TypeError);   // pinned: it cannot be put back
    expect(g.fetch).toBeUndefined();
    expect((g.navigator as Record<string, unknown>).storage).toBeUndefined();
    expect((g.navigator as Record<string, unknown>).hardwareConcurrency).toBe(8);
    const p = await probe(g);
    expect(p.fetch).toBe('blocked');
    expect(p['navigator.storage']).toBe('blocked');
    expect(p.eval).toMatch(/^blocked/);
  });
  it('caps WebAssembly memory growth', () => {
    const grown: number[] = [];
    class Mem { buffer = { byteLength: 1000 * 65536 }; }
    Object.defineProperty(Mem.prototype, 'grow', { value(d: number) { grown.push(d); return 1000; }, configurable: true, writable: true });
    capMemory(1100 * 65536, { WebAssembly: { Memory: Mem } } as unknown as { WebAssembly: typeof WebAssembly });
    const m = new Mem() as unknown as { grow(d: number): number };
    expect(m.grow(50)).toBe(1000);
    expect(() => m.grow(200)).toThrow(/memory ceiling/);
    expect(grown).toEqual([50]);
  });
});

/** A fake worker the test drives: it answers boot with ready, and lets the test post messages. */
class FakeWorker {
  listeners: Record<string, ((e: unknown) => void)[]> = {};
  posted: Record<string, unknown>[] = [];
  terminated = false;
  addEventListener(t: string, f: (e: unknown) => void) { (this.listeners[t] ??= []).push(f); }
  removeEventListener(t: string, f: (e: unknown) => void) { this.listeners[t] = (this.listeners[t] ?? []).filter((x) => x !== f); }
  postMessage(m: Record<string, unknown>) {
    this.posted.push(m);
    if (m.type === 'boot') queueMicrotask(() => this.emit({ type: 'ready', memory: 100 * 2 ** 20, removed: ['fetch'] }));
  }
  emit(data: unknown) { for (const f of this.listeners.message ?? []) f({ data }); }
  terminate() { this.terminated = true; }
}

describe('the watchdog (R2.2)', () => {
  it('ends a silent call at the family limit and restarts the worker', async () => {
    vi.useFakeTimers();
    const made: FakeWorker[] = [];
    const sb = new Sandbox(() => { const w = new FakeWorker(); made.push(w); return w as unknown as Worker; }, '/');
    expect(await sb.start()).toEqual(['fetch']);
    const run = sb.run({ op: 'scenario' }, 'control');
    await vi.advanceTimersByTimeAsync(0);
    made[0].emit({ type: 'beat', calls: 3, memory: 100 * 2 ** 20 });
    await vi.advanceTimersByTimeAsync(4000);
    made[0].emit({ type: 'beat', calls: 4, memory: 100 * 2 ** 20 });   // beats keep it alive
    await vi.advanceTimersByTimeAsync(4900);
    await vi.advanceTimersByTimeAsync(200);                              // 5 s of silence: stopped
    const e = await run;
    expect(e).toMatchObject({ ok: false, reason: 'time_limit', calls: 4 });
    expect(made[0].terminated).toBe(true);
    const again = sb.run({ op: 'check' }, 'planning');                   // a fresh worker boots
    await vi.advanceTimersByTimeAsync(0);
    expect(made.length).toBe(2);
    const id = (made[1].posted.find((m) => m.type === 'run') as { id: number }).id;
    made[1].emit({ type: 'done', id, result: '{"ok":true}', ms: 3 });
    expect(await again).toEqual({ ok: true, result: '{"ok":true}', ms: 3 });
  });
  it('ends a run past the memory ceiling and ignores malformed messages', async () => {
    const made: FakeWorker[] = [];
    const sb = new Sandbox(() => { const w = new FakeWorker(); made.push(w); return w as unknown as Worker; }, '/');
    const run = sb.run({ op: 'runs' }, 'planning');
    await new Promise((r) => setTimeout(r, 0));
    made[0].emit('not an object');
    made[0].emit({ type: 42 });
    made[0].emit({ type: 'done', id: 'x', result: 7 });
    made[0].emit({ type: 'beat', calls: 1, memory: (100 + 1025) * 2 ** 20 });
    expect(await run).toMatchObject({ ok: false, reason: 'memory_limit' });
    expect(made[0].terminated).toBe(true);
  });
});
