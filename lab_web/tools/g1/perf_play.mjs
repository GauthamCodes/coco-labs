// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.9: Play in the Depot for N minutes, driven, and what it costs per frame.
 *
 *   node tools/g1/perf_play.mjs SITE OUTDIR [--profile phone|desktop] [--tier medium]
 *        [--minutes 10] [--label NAME]
 *
 * phone = the emulated Nothing Phone (1) (tools/phone/nothing-phone-1.mjs: 915 x 412
 * landscape, DPR 2.625, touch, 4x CPU throttle); desktop = 1440 x 900, no throttle.
 * Records, per one-second window, the frames DRAWN (counted at the WebGL context's
 * first clear of each animation frame) and, per animation frame, the main-thread time
 * of the page's frame callbacks (the CPU-side cost, which CPU throttling models); then
 * the median, minimum and p95. Also: the title (first paint, title visible, title JS
 * bytes) and the loading stages (the worker's own marks, from PLAY to playable),
 * console errors, page errors and WebGL context losses.
 *
 * In a container without a GPU, Chromium renders with SwiftShader (on the CPU): the
 * drawn-frame rate is then the software rasteriser's, and is labelled so. It is not a
 * phone's frame rate.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const profile = opt('--profile', 'phone'), tier = opt('--tier', 'medium'), minutes = Number(opt('--minutes', '10'));
const label = opt('--label', `${profile}-${tier}-${minutes}min`);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext(profile === 'phone' ? nothingPhone1(true) : { viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
const report = { label, profile, tier, minutes, site, started: new Date().toISOString(), errors: [], console_errors: [], class: 'MODEL in the browser; emulated profile; software GPU (see renderer)' };
p.on('pageerror', (e) => report.errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') report.console_errors.push(m.text()); });
const save = () => writeFileSync(`${out}/${label}.json`, JSON.stringify(report, null, 1) + '\n');
await p.addInitScript(() => {
  try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
  const g = window.__g19 = { serial: 0, drawnAt: -1, drawn: 0, lost: 0, js: [], on: false };
  const raf = window.requestAnimationFrame.bind(window);
  // one animation frame's callbacks: their total main-thread time
  let pending = 0, spent = 0;
  window.requestAnimationFrame = (fn) => raf((t) => {
    if (pending === 0) { g.serial++; spent = 0; }
    pending++;
    const t0 = performance.now();
    try { fn(t); } finally { spent += performance.now() - t0; if (--pending === 0 && g.on) g.js.push(spent); }
  });
  const getContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (...args) {
    const gl = getContext.apply(this, args);
    if (gl && gl.clear && !gl.__g19) {
      gl.__g19 = true;
      this.addEventListener('webglcontextlost', () => { g.lost++; });
      const clear = gl.clear.bind(gl);
      gl.clear = (...v) => { if (g.drawnAt !== g.serial) { g.drawnAt = g.serial; g.drawn++; } return clear(...v); };
    }
    return gl;
  };
});
if (profile === 'phone') await throttlePhone(ctx, p);
// the title
const t0 = Date.now();
await p.goto(site);
await p.getByTestId('title').waitFor({ timeout: 180000 });
report.title = await p.evaluate(() => {
  const paint = Object.fromEntries(performance.getEntriesByType('paint').map((e) => [e.name, e.startTime]));
  const js = performance.getEntriesByType('resource').filter((e) => /\.m?js$/.test(new URL(e.name).pathname)).reduce((s, e) => s + (e.encodedBodySize || 0), 0);
  return { first_paint_ms: paint['first-paint'] ?? null, first_contentful_paint_ms: paint['first-contentful-paint'] ?? null, title_visible_ms: performance.now(), js_transferred_bytes_at_title: js };
});
report.title.wall_ms_to_title = Date.now() - t0;
// mode select -> PLAY -> playable
await p.goto(`${site}?view=play&game=free&world=depot&tier=${tier}`);
await p.waitForSelector('[data-testid="g1-play"]', { timeout: 180000 });
const tPlay = Date.now();
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
report.loading = { mode_select_to_play_enabled_ms: Date.now() - tPlay, perf_marks: await p.evaluate(() => window.__cocoPerf?.marks ?? null) };
const tStart = Date.now();
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 1, null, { timeout: 300000 });
report.loading.play_to_first_tick_ms = Date.now() - tStart;
report.renderer = await p.evaluate(() => { const gl = document.createElement('canvas').getContext('webgl2'); const d = gl?.getExtension('WEBGL_debug_renderer_info'); return d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : null; });
report.software_gpu = /swiftshader|llvmpipe|software/i.test(report.renderer ?? '');
// drive for `minutes`: cycle keys (forward, turns, reverse) and AUTO now and then, sampling every second
await p.evaluate(() => { window.__g19.on = true; window.__g19.js = []; });
const samples = [];
let prev = await p.evaluate(() => ({ n: window.__g19.drawn, t: performance.now() }));
const keys = ['KeyW', 'KeyW', 'KeyA', 'KeyW', 'KeyD', 'KeyW', 'KeyS', 'KeyW'];
const end = Date.now() + minutes * 60_000;
for (let i = 0; Date.now() < end; i++) {
  const k = keys[i % keys.length];
  await p.keyboard.down(k);
  await p.waitForTimeout(1000);
  await p.keyboard.up(k);
  if (i % 45 === 44) await p.keyboard.press('KeyV'); // Robot vision on/off now and then
  const now = await p.evaluate(() => ({ n: window.__g19.drawn, t: performance.now(), tick: window.__cocoGame?.tick?.tick ?? null }));
  samples.push({ s: (now.t - prev.t) / 1000, drawn: now.n - prev.n, fps: ((now.n - prev.n) * 1000) / (now.t - prev.t), tick: now.tick });
  prev = now;
  if (i % 30 === 0) { report.samples = samples; save(); }
}
const js = await p.evaluate(() => window.__g19.js);
const sorted = (a) => [...a].sort((x, y) => x - y);
const q = (a, f) => (a.length ? sorted(a)[Math.min(a.length - 1, Math.floor(f * a.length))] : null);
const fps = samples.map((s) => s.fps);
report.samples = samples;
report.drawn_fps = { median: q(fps, 0.5), minimum: fps.length ? Math.min(...fps) : null, windows: fps.length, note: report.software_gpu ? 'software GPU (SwiftShader): the rasteriser runs on this container\'s CPU' : 'hardware GPU' };
report.frame_js_ms = { median: q(js, 0.5), p95: q(js, 0.95), max: js.length ? Math.max(...js) : null, frames: js.length, budget_60fps_ms: 1000 / 60 };
report.drawn_frame_ms_p95 = (() => { const ms = fps.filter((f) => f > 0).map((f) => 1000 / f); return q(ms, 0.95); })();
report.webgl_context_lost = await p.evaluate(() => window.__g19.lost);
report.last_tick = await p.evaluate(() => window.__cocoGame?.tick?.tick ?? null);
report.ended = new Date().toISOString();
report.passed_no_errors = report.errors.length === 0 && report.console_errors.length === 0 && report.webgl_context_lost === 0;
save();
await p.screenshot({ path: `${out}/${label}.png` });
console.log(JSON.stringify({ label, drawn_fps: report.drawn_fps, frame_js_ms: report.frame_js_ms, lost: report.webgl_context_lost, errors: report.errors.length + report.console_errors.length, title: report.title, loading: report.loading.mode_select_to_play_enabled_ms }));
await browser.close();
