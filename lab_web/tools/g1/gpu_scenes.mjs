// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: the title and four-pane Compare drawn on a real GPU (gpu.mjs, G1_GPU=nvidia|intel).
 *
 *   G1_GPU=nvidia node tools/g1/gpu_scenes.mjs SITE OUT.json --scene title|compare
 *        [--tier medium|high|low] [--quality auto|high|medium|low] [--seconds 60]
 *
 * title: the root URL (the hero stage; `?tier=` passes to pickTier, and the hero draws at
 * most medium). compare: `?view=compare`, Panes = 4, Replay pressed (M5.11's procedure),
 * `&quality=` for the Arena renderer's tier choice (default auto). Desktop 1440 x 900.
 * Records every drawn frame's time (the first WebGL clear of an animation frame, any
 * canvas): frame interval median / p95 / max, fps per one-second window (median, minimum),
 * WebGL context losses, page and console errors, the renderer string, the machine.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { GPU, launchOptions, renderer, assertGpu, machine } from './gpu.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const scene = opt('--scene', 'title'), tier = opt('--tier', ''), quality = opt('--quality', '');
const seconds = Number(opt('--seconds', '60'));
const report = { scene, tier: tier || 'default', quality: quality || 'default', seconds, gpu: GPU, site,
  machine_start: machine(), started: new Date().toISOString(), errors: [], console_errors: [] };
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
p.on('pageerror', (e) => report.errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
await p.addInitScript(() => {
  try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
  const g = window.__g113 = { serial: 0, drawnAt: -1, at: [], lost: 0, on: false };
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (fn) => raf((t) => { g.serial++; fn(t); });
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const gl = getContext.apply(this, args);
    if (gl && gl.clear && !gl.__g113) {
      gl.__g113 = true;
      this.addEventListener('webglcontextlost', () => { g.lost++; });
      const clear = gl.clear.bind(gl);
      gl.clear = (...v) => { if (g.drawnAt !== g.serial) { g.drawnAt = g.serial; if (g.on) g.at.push(performance.now()); } return clear(...v); };
    }
    return gl;
  };
});
const q = new URLSearchParams();
if (scene === 'compare') q.set('view', 'compare');
if (tier) q.set('tier', tier);
if (quality) q.set('quality', quality);
await p.goto(`${site}${q.toString() ? `?${q}` : ''}`);
if (scene === 'title') {
  await p.getByTestId('title').waitFor({ timeout: 180000 });
} else {
  await p.waitForSelector('[data-ready="true"]', { timeout: 180000 });
  await p.getByRole('combobox', { name: 'Panes', exact: true }).selectOption('4');
  await p.waitForSelector('[data-ready="true"]', { timeout: 180000 });
  await p.getByRole('button', { name: 'Replay', exact: true }).click();
}
report.renderer = await renderer(p);
assertGpu(report.renderer);
await p.waitForTimeout(3000);
await p.evaluate(() => { window.__g113.on = true; });
const t0 = Date.now();
const windows = [];
let prev = await p.evaluate(() => ({ n: window.__g113.at.length, t: performance.now() }));
while (Date.now() - t0 < seconds * 1000) {
  await p.waitForTimeout(1000);
  const now = await p.evaluate(() => ({ n: window.__g113.at.length, t: performance.now() }));
  windows.push(((now.n - prev.n) * 1000) / (now.t - prev.t));
  prev = now;
}
const at = await p.evaluate(() => window.__g113.at);
const iv = at.slice(1).map((t, i) => t - at[i]);
const s = (a) => [...a].sort((x, y) => x - y);
const pc = (a, f) => (a.length ? s(a)[Math.min(a.length - 1, Math.floor(f * a.length))] : null);
report.canvases = await p.evaluate(() => document.querySelectorAll('canvas').length);
report.arena_tier = await p.evaluate(() => window.__cocoArena?.renderer?.quality?.tier ?? document.querySelector('canvas')?.dataset?.qualityTier ?? null);
report.fps = { median: pc(windows, 0.5), minimum: windows.length ? Math.min(...windows) : null, windows: windows.length };
report.frame_interval_ms = { median: pc(iv, 0.5), p95: pc(iv, 0.95), p99: pc(iv, 0.99), max: iv.length ? Math.max(...iv) : null, frames: at.length, over_50: iv.filter((x) => x > 50).length };
report.webgl_context_lost = await p.evaluate(() => window.__g113.lost);
report.machine_end = machine();
report.ended = new Date().toISOString();
report.passed_no_errors = !report.errors.length && !report.console_errors.length && report.webgl_context_lost === 0;
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
await p.screenshot({ path: out.replace(/\.json$/, '.png') });
console.log(JSON.stringify({ scene, gpu: GPU, tier: report.tier, quality: report.quality, renderer: report.renderer, arena_tier: report.arena_tier, fps: report.fps, frame_interval_ms: report.frame_interval_ms, lost: report.webgl_context_lost, errors: report.errors.length + report.console_errors.length }));
await b.close();
