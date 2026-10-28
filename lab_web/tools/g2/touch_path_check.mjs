// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.9: where a drive input's time goes, per build, on the EMULATED Nothing Phone (1) (viewport, touch,
 * 4x CPU throttle; the laptop's GPU): Free Drive on the Depot, N deliberate drives from rest (key down
 * 400 ms, then 1.6 s still), each in a fresh random phase of the tick schedule. Reports ?perf's input ->
 * motion samples (the build's own measure; a short drive in the open never hits a wall) and the model's
 * step time (perf's stepMsMedian, the worker's tick cost).
 *
 *   G1_GPU=nvidia node tools/g2/touch_path_check.mjs SITE OUT.json [--n 40]
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { launchOptions } from '../g1/gpu.mjs';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const N = Number(rest.includes('--n') ? rest[rest.indexOf('--n') + 1] : 40);
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ ...nothingPhone1(true), serviceWorkers: 'block' });
const p = await ctx.newPage();
const cdp = await ctx.newCDPSession(p);
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play&game=free&world=depot`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
await p.waitForTimeout(3000);
const keys = ['KeyW', 'KeyS'];
for (let k = 0; k < N; k++) {
  await p.waitForTimeout(1600 + Math.floor(Math.random() * 100));
  const key = keys[k % 2];                     // forward, back: COCO stays in the open
  await p.keyboard.down(key); await p.waitForTimeout(400); await p.keyboard.up(key);
}
await p.waitForTimeout(1500);
const s = await p.evaluate(() => { const x = window.__cocoPerf; const snap = x.snapshot(); return { itm: [...x.inputToMotion], all: x.__all ?? null, step: snap.stepMsMedian, noMotion: snap.inputNoMotion ?? null, index: [...document.scripts].map((e) => e.src.split('/').pop()).join(' ') }; });
await b.close();
const sorted = [...s.itm].sort((a, b2) => a - b2), med = sorted[sorted.length >> 1];
const rep = { class: 'EMULATED phone (4x CPU throttle, laptop GPU); not a phone measurement', site, index: s.index, n: s.itm.length, input_to_motion_ms: s.itm.map((v) => Math.round(v)), median_ms: med, step_ms_median: s.step, no_motion: s.noMotion };
writeFileSync(out, JSON.stringify(rep, null, 1) + '\n');
console.log(JSON.stringify({ index: rep.index, n: rep.n, median_ms: Math.round(med), step_ms_median: rep.step_ms_median, no_motion: rep.no_motion }));
