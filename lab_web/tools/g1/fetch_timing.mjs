// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.11: does Fetch Rush ever pause for planning? A Fetch Rush session played through the
 * page's own keys (fetch_play.mjs's AUTO / GRAB / AUTO / DROP loop), measured:
 *
 *   - model ticks: the wall gap between consecutive ticks reaching the page (any worker
 *     stall shows here: a tick that plans, a query that searches), and the worker's own
 *     per-tick step time;
 *   - the "clock waits" banner (data-testid="g1-busy"): how often it appeared, for how long;
 *   - main-thread JavaScript per animation frame (the frame callbacks' time; in this
 *     container the GPU is SwiftShader, so drawn frame rates are not measured here).
 *
 *   node tools/g1/fetch_timing.mjs SITE OUT.json [--deliveries N] [--profile desktop|phone] [--label L]
 *
 * Run against the build before G1.11 and after, same machine, same harness.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';
import { GPU, launchOptions, renderer, assertGpu, machine } from './gpu.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const WANT = Number(opt('--deliveries', '3'));
const profile = opt('--profile', 'desktop');
// G1.13: G1_GPU=nvidia|intel launches on the laptop's GPU (gpu.mjs); software is the default
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext(profile === 'phone' ? nothingPhone1(true) : { viewport: { width: 1280, height: 720 } });
const p = await ctx.newPage();
const errors = [], log = [];
p.on('pageerror', (e) => errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
await p.addInitScript(() => {
  try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ }
  const g = window.__g111 = { on: false, js: [], slow: [], tickAt: [], lastTick: -1, busy: { shown: 0, ms: 0, since: null } };
  const raf = window.requestAnimationFrame.bind(window);
  let pending = 0, spent = 0;
  window.requestAnimationFrame = (fn) => raf((t) => {
    if (pending === 0) spent = 0;
    pending++;
    const t0 = performance.now();
    try { fn(t); } finally {
      spent += performance.now() - t0;
      if (--pending === 0 && g.on) {
        g.js.push(spent);
        if (spent > 50) g.slow.push({ at: performance.now(), ms: spent, tick: window.__cocoGame?.tick?.tick ?? null });
        const k = window.__cocoGame?.tick?.tick;
        if (k !== undefined && k !== g.lastTick) { const t = window.__cocoGame.tick; g.lastTick = k; g.tickAt.push([performance.now(), k, t.source, t.v]); }
        const busy = !!document.querySelector('[data-testid="g1-busy"]');
        if (busy && g.busy.since === null) { g.busy.since = performance.now(); g.busy.shown++; }
        if (!busy && g.busy.since !== null) { g.busy.ms += performance.now() - g.busy.since; g.busy.since = null; }
      }
    }
  });
});
if (profile === 'phone') await throttlePhone(ctx, p);
await p.goto(`${site}?view=play&game=fetch_rush&seed=${opt('--seed', '1')}&tier=low${opt('--mode', '') ? `&mode=${opt('--mode', '')}` : ''}`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
const rendererString = await renderer(p);
assertGpu(rendererString);
await p.click('[data-testid="g1-play"]');
const state = () => p.evaluate(() => { const t = window.__cocoGame.tick; const pr = document.querySelector('[data-testid="hud-primary"]'); return t ? { tick: t.tick, mode: t.mode, source: t.source, a: t.game?.assist, f: t.game?.fetch, primary: pr?.getAttribute('aria-label'), enabled: pr?.getAttribute('aria-disabled') === 'false' } : null; });
const until = async (fn, label, ms = 900000) => { const t0 = Date.now(); for (;;) { const s = await state(); if (s && fn(s)) { log.push([label, s.tick]); return s; } if (Date.now() - t0 > ms) { log.push([label + ' TIMEOUT', s?.tick]); return s; } await p.waitForTimeout(250); } };
await until((s) => s.tick > 2, 'started');
// G1.12: tick arrivals time-stamped as the worker's message arrives (not at the next frame,
// whose interval under a software renderer would hide the gap), with the worker's step time
await p.evaluate(() => {
  const g = window.__g111; g.msg = [];
  window.__cocoGame.session.client.worker.addEventListener('message', (m) => {
    const d = m.data; if (d && d.type === 'tick') g.msg.push([performance.now(), d.tick.tick, d.tick.source, d.tick.v, d.stepMs]);
  });
  g.on = true;
});
const t0 = Date.now();
const presses = [];
async function auto(label) {
  for (let tries = 0; tries < 3; tries++) {
    presses.push({ label, at: await p.evaluate(() => performance.now()) });
    await p.keyboard.press('KeyF');
    const s2 = await until((x) => x.mode === 'goal' || x.f?.over, label + ' (AUTO taken)', 8000);
    if (s2?.mode === 'goal' || s2?.f?.over) return;
  }
}
let s;
for (let k = 0; k < WANT; k++) {
  await auto(`order ${k + 1}: to the object`);
  s = await until((x) => x.f?.over || (x.tick > 5 && x.source !== 'planner' && x.enabled && /GRAB/.test(x.primary)), `order ${k + 1}: GRAB lit`);
  if (s.f?.over) break;
  const before = (await state())?.a?.attempt ?? 0;
  await p.keyboard.press('KeyG');
  // a refusal counts only from THIS attempt (the last order's "released ..." is still on the HUD)
  s = await until((x) => x.f?.over || !!x.a?.carried || (x.a?.phase === 'idle' && (x.a?.attempt ?? 0) !== before && x.a?.reason && !/ok|holds|released/.test(x.a.reason)), `order ${k + 1}: carried`);
  if (!s.a?.carried) break;
  await p.waitForTimeout(500);
  await auto(`order ${k + 1}: to the drop`);
  s = await until((x) => x.f?.over || (x.enabled && /DROP/.test(x.primary)), `order ${k + 1}: DROP lit`);
  if (s.f?.over) break;
  await p.keyboard.press('KeyG');
  s = await until((x) => x.f?.over || x.f?.deliveries > k, `order ${k + 1}: delivered`);
  // the next order appears here: keep measuring through it (where the old ghost search ran)
  await p.waitForTimeout(3000);
}
const g = await p.evaluate(() => { const g = window.__g111; if (g.busy.since !== null) g.busy.ms += performance.now() - g.busy.since; return g; });
const steps = await p.evaluate(() => [...(window.__cocoPerf?.steps ?? [])]);
const gaps = g.tickAt.slice(1).map(([t, k], i) => ({ ms: t - g.tickAt[i][0], ticks: k - g.tickAt[i][1], at_tick: k }));
const sorted = (a) => [...a].sort((x, y) => x - y);
const q = (a, f) => (a.length ? sorted(a)[Math.min(a.length - 1, Math.floor(f * a.length))] : null);
const perTick = gaps.filter((x) => x.ticks === 1).map((x) => x.ms);
// G1.12: each AUTO press -> the first tick the planner drives (|v| > 0.01): wall time, and the
// longest gap between tick arrivals from the press to then (the tick period is 100 ms)
const T = g.msg;
const auto_presses = presses.map(({ label, at }) => {
  const i = T.findIndex(([t]) => t > at);
  const j = T.findIndex(([t, , src, v], n) => n >= i && i >= 0 && (src === 'planner' || src === 'mission') && Math.abs(v) > 0.01);
  if (i < 0 || j < 0) return { label, motion: false };
  let gap = 0, step = 0;
  for (let n = Math.max(1, i); n <= j; n++) { gap = Math.max(gap, T[n][0] - T[n - 1][0]); step = Math.max(step, T[n][4]); }
  return { label, motion: true, press_to_motion_ms: Math.round(T[j][0] - at), ticks: T[j][1] - T[i][1] + 1, max_tick_gap_ms: Math.round(gap), over_period_ms: Math.max(0, Math.round(gap - 100)), max_worker_step_ms: Math.round(step) };
});
const msgGaps = T.slice(1).map(([t, k], n) => ({ ms: t - T[n][0], ticks: k - T[n][1] }));
const msgSteps = T.map((x) => x[4]);
const report = {
  label: opt('--label', ''), site, profile, wall_s: (Date.now() - t0) / 1000, final: s, log, errors,
  renderer: GPU === 'software' ? `SwiftShader (no GPU): drawn frame rates are not measured; frame times are main-thread JS (${rendererString})` : rendererString,
  gpu: GPU, machine: machine(), ended: new Date().toISOString(),
  deliveries: s?.f?.deliveries ?? null, orders: s?.f?.orders ?? null, seconds: s?.f?.seconds ?? null,
  tick_gap_ms: { max: gaps.length ? Math.max(...gaps.map((x) => x.ms)) : null, p95_single: q(perTick, 0.95), median_single: q(perTick, 0.5),
    over_800: gaps.filter((x) => x.ms > 800).map((x) => ({ ms: Math.round(x.ms), at_tick: x.at_tick })) },
  worker_step_ms: { max: steps.length ? Math.max(...steps) : null, p95: q(steps, 0.95), median: q(steps, 0.5), kept: steps.length },
  busy_banner: { shown: g.busy.shown, total_ms: Math.round(g.busy.ms) },
  tick_arrival_ms: { note: 'time-stamped on the worker message (G1.12); tick_gap_ms above is sampled per animation frame',
    max: msgGaps.length ? Math.max(...msgGaps.map((x) => x.ms)) : null, p95: q(msgGaps.map((x) => x.ms), 0.95), median: q(msgGaps.map((x) => x.ms), 0.5),
    over_150: msgGaps.filter((x) => x.ms > 150).length, ticks: T.length },
  worker_step_all_ms: { max: msgSteps.length ? Math.max(...msgSteps) : null, p95: q(msgSteps, 0.95), median: q(msgSteps, 0.5) },
  auto_presses,
  auto_max_tick_gap_ms: auto_presses.filter((x) => x.motion).reduce((m, x) => Math.max(m, x.max_tick_gap_ms), 0),
  frame_js_ms: { max: g.js.length ? Math.max(...g.js) : null, p95: q(g.js, 0.95), median: q(g.js, 0.5), frames: g.js.length, over_50: g.slow.length, slow: g.slow.slice(0, 20) },
};
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ label: report.label, deliveries: report.deliveries, orders: report.orders, seconds: report.seconds, tick_gap_ms: { max: report.tick_gap_ms.max, over_800: report.tick_gap_ms.over_800.length }, busy: report.busy_banner, arrival: { max: report.tick_arrival_ms.max, p95: report.tick_arrival_ms.p95 }, step_max: report.worker_step_all_ms.max, auto_max_gap: report.auto_max_tick_gap_ms, auto: auto_presses.map((x) => x.max_tick_gap_ms), frame_js: { max: report.frame_js_ms.max, over_50: report.frame_js_ms.over_50 }, errors: errors.length }));
await b.close();
