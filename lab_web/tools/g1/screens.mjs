// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.0 / G1.10: before and after screenshots of the four surfaces (title,
 * Play, Compare, Recordings) at 1440 x 900 and on the emulated Nothing
 * Phone (1) in landscape and portrait. Screenshots catch regressions only;
 * Gautham judges the look (README §9 rule 8).
 *
 *   node tools/g1/screens.mjs SITE OUTDIR [--play QUERY] [--play-click SEL] [--compare QUERY]
 *
 * --play-click: a button to press once it is enabled before Play counts as ready (G1's
 * Play opens on its mode select; G1.10's after shot presses PLAY into a running game).
 *
 * SITE is a served build (tools/perf/serve_dist.mjs). The emulated phone is
 * viewport, touch and a 4x CPU throttle; the GPU is whatever this machine
 * renders with (recorded in OUTDIR/shots.json), never a phone's.
 */
import { chromium } from 'playwright';
import { GPU, launchOptions, machine } from './gpu.mjs';
import { mkdirSync, writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : d; };
const SURFACES = {
  title: { query: '', ready: '[data-testid="title"] canvas[data-scene-ready="true"], [data-g1="title"][data-ready="true"]' },
  play: { query: opt('--play', '?view=arena'), click: opt('--play-click', null), ready: 'canvas[data-scene-ready="true"], [data-g1="play"][data-ready="true"]', settle: 4000 },
  compare: { query: opt('--compare', '?view=compare'), ready: '[data-testid="compare-workspace"][data-ready="true"]' },
  recordings: { query: opt('--recordings', '?view=research'), ready: '.recording-card' },
};
const PROFILES = [['desktop', { viewport: { width: 1440, height: 900 } }], ['phone-landscape', nothingPhone1(true)], ['phone-portrait', nothingPhone1(false)]];
mkdirSync(out, { recursive: true });
// G1.13: G1_GPU=nvidia|intel renders on the laptop's GPU (gpu.mjs); software is the default
const browser = await chromium.launch(launchOptions());
const report = { site, when: new Date().toISOString(), gpu: GPU, machine: machine(), renderer: null, shots: [] };
for (const [profile, options] of PROFILES) {
  for (const [name, s] of Object.entries(SURFACES)) {
    const ctx = await browser.newContext({ ...options, serviceWorkers: 'block' });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    if (profile.startsWith('phone')) await throttlePhone(ctx, page);
    await page.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* storage may be off */ } });
    const t0 = Date.now();
    let ready = true;
    try {
      await page.goto(site + s.query, { waitUntil: 'load' });
      if (s.click) { await page.waitForSelector(`${s.click}:not([disabled])`, { timeout: 180000 }); await page.click(s.click); }
      await page.waitForSelector(s.ready, { timeout: 180000 });
      await page.evaluate(() => window.dispatchEvent(new Event('coco:skip-tutorial')));
      await page.waitForTimeout(s.settle ?? 1500);
    } catch (e) { ready = false; errors.push('not ready: ' + String(e).split('\n')[0]); }
    if (!report.renderer) report.renderer = await page.evaluate(() => { const g = document.createElement('canvas').getContext('webgl2'); const d = g?.getExtension('WEBGL_debug_renderer_info'); return d ? g.getParameter(d.UNMASKED_RENDERER_WEBGL) : null; }).catch(() => null);
    const file = `${profile}-${name}.png`;
    await page.screenshot({ path: `${out}/${file}`, scale: 'css' });
    report.shots.push({ profile, surface: name, query: s.query, file, ready, ms: Date.now() - t0, errors });
    console.log(profile, name, ready ? 'ok' : 'NOT READY', errors.length ? errors.slice(0, 2) : '');
    await ctx.close();
  }
}
await browser.close();
report.note = 'Emulated Nothing Phone (1): viewport, touch, 4x CPU throttle; rendered by this machine (see renderer). Not a phone measurement.';
writeFileSync(`${out}/shots.json`, JSON.stringify(report, null, 1) + '\n');
