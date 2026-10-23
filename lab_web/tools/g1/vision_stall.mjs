// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13: does turning Robot vision on stall the model? Play (Fetch Rush), drive a little, then
 * Robot vision on for N seconds; every model tick is time-stamped on the worker's message.
 * Reports the tick gaps with vision off and on, every gap over 300 ms, the worker's step times
 * (a costmap refresh is not a step: a gap without a long step is the worker busy elsewhere), and
 * the "clock waits" banner. Measured before the fix: ~0.9 s gaps every 4 s on the laptop.
 *
 *   G1_GPU=nvidia node tools/g1/vision_stall.mjs SITE OUT.json [--seconds 20]
 *   node tools/g1/vision_stall.mjs SITE OUT.json --cdp http://127.0.0.1:9222   (a real phone's Chrome)
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { GPU, launchOptions, renderer, machine } from './gpu.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => (rest.includes(k) ? rest[rest.indexOf(k) + 1] : d);
const SECONDS = Number(opt('--seconds', '20')), CDP = opt('--cdp', null);
const b = CDP ? await chromium.connectOverCDP(CDP) : await chromium.launch(launchOptions());
const ctx = CDP ? b.contexts()[0] : await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.evaluate(() => document.querySelector('[data-testid="g1-play"]').click());
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
await p.evaluate(() => {
  const g = window.__vs = { msg: [], busy: 0 };
  window.__cocoGame.session.client.worker.addEventListener('message', (m) => { const d = m.data; if (d?.type === 'tick') g.msg.push([performance.now(), d.stepMs]); });
  setInterval(() => { if (document.querySelector('[data-testid="g1-busy"]')) g.busy++; }, 50);
});
await p.waitForTimeout(8000);
const tv = await p.evaluate(() => performance.now());
await p.evaluate(() => document.querySelector('[data-testid="g1-vision"]').click());
await p.waitForTimeout(SECONDS * 1000);
const r = await p.evaluate(() => window.__vs);
const part = (from, to) => {
  const m = r.msg.filter(([t]) => t >= from && t < to);
  const gaps = m.slice(1).map(([t], i) => t - m[i][0]); const s = [...gaps].sort((a, c) => a - c);
  const steps = m.map((x) => x[1]).sort((a, c) => a - c);
  return { ticks: m.length, gap_median: Math.round(s[Math.floor(s.length / 2)]), gap_p95: Math.round(s[Math.floor(0.95 * s.length)]), gap_max: Math.round(s.at(-1)),
    gaps_over_300: gaps.filter((x) => x > 300).map(Math.round), step_max: Math.round(steps.at(-1)) };
};
const report = { site, gpu: CDP ? 'phone (CDP)' : GPU, renderer: await renderer(p), machine: CDP ? null : machine(), seconds: SECONDS,
  vision_off: part(0, tv), vision_on: part(tv, tv + SECONDS * 1000), clock_waits_banner_samples: r.busy, when: new Date().toISOString() };
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ off: report.vision_off, on: report.vision_on, banner: report.clock_waits_banner_samples, renderer: report.renderer }));
await p.close();
await b.close();
