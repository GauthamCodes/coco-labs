// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2: GAME and SIM views of the same moment, for review (screenshots catch regressions;
 * Gautham judges the look). Desktop 1440 x 900 and the emulated Nothing Phone (1) in
 * landscape, on the GPU G1_GPU names (tools/g1/gpu.mjs). Fetch Rush seed 1: drive forward,
 * AUTO (so there is a plan), then GAME, then V -> SIM, then a few SIM displays' close-up.
 *
 *   G1_GPU=nvidia node tools/g2/sim_shots.mjs SITE OUTDIR
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { launchOptions, renderer } from '../g1/gpu.mjs';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await chromium.launch(launchOptions());
const report = { site, when: new Date().toISOString(), renderer: null, shots: [], errors: [] };
for (const [profile, options] of [['desktop', { viewport: { width: 1440, height: 900 } }], ['phone-landscape', nothingPhone1(true)]]) {
  const ctx = await b.newContext({ ...options, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  p.on('pageerror', (e) => report.errors.push(`${profile}: ${e}`));
  p.on('console', (m) => { if (m.type() === 'error') report.errors.push(`${profile} console: ${m.text()}`); });
  await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
  await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  await p.click('[data-testid="g1-play"]');
  await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
  report.renderer ??= await renderer(p).catch(() => null);
  await p.keyboard.down('KeyW'); await p.waitForTimeout(2500); await p.keyboard.up('KeyW');
  await p.click('[data-testid="hud-autonomy"]');
  await p.waitForTimeout(4000);
  const snap = async (name) => { await p.screenshot({ path: `${out}/${profile}-${name}.png` }); report.shots.push(`${profile}-${name}`); };
  await snap('1-game');
  await p.click('[data-testid="g2-view-sim"]');
  await p.waitForTimeout(5000);
  await snap('2-sim');
  // G2.4: the panels, each tab, over SIM view
  await p.click('[data-testid="g2-panels-button"]');
  for (const tab of ['displays', 'graph', 'echo', 'plot']) {
    await p.click(`[data-testid="g2-tab-${tab}"]`);
    await p.waitForTimeout(1200);
    await snap(`4-panel-${tab}`);
  }
  await p.click('[data-testid="g2-learn"]');
  await p.waitForTimeout(300);
  await snap('5-panel-learn');
  report[`${profile}_panel_vs_stop`] = await p.evaluate(() => {
    const a = document.querySelector('[data-testid="g2-panels"]')?.getBoundingClientRect(), b = document.querySelector('[data-testid="hud-stop"], [data-testid="hud-release"]')?.getBoundingClientRect();
    return a && b ? { overlap: Math.min(a.right, b.right) > Math.max(a.left, b.left) && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top), panel: [a.left, a.top, a.right, a.bottom], stop: [b.left, b.top, b.right, b.bottom] } : null;
  });
  await p.click('[data-testid="g2-panels-button"]');
  report[`${profile}_state`] = await p.evaluate(() => ({ view: document.querySelector('[data-testid="g2-view"]')?.getAttribute('data-view'), tick: window.__cocoGame?.tick?.tick, ros: !!window.__cocoGame?.tick?.ros }));
  await p.click('[data-testid="g2-view-game"]');
  await p.waitForTimeout(1500);
  await snap('3-game-again');
  await ctx.close();
}
await b.close();
writeFileSync(`${out}/shots.json`, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ shots: report.shots.length, errors: report.errors, renderer: report.renderer, d: report.desktop_state, ph: report['phone-landscape_state'], stop: [report['desktop_panel_vs_stop'], report['phone-landscape_panel_vs_stop']] }));
