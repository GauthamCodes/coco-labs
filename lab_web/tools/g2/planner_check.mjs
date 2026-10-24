// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * The AUTO planner choice in a browser (owner request 2026-10-24): the mode select offers the
 * planners, a pick is saved and carried into the round's link, AUTO's plans come from that planner
 * (the model's own plan summary), and A* sends no planner input (its plans say astar).
 *
 *   node tools/g2/planner_check.mjs SITE OUT_DIR
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';

const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const rows = [];
for (const planner of ['greedy', 'astar']) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
  await p.goto(`${site}?view=play`);
  await p.click(`[data-testid="planner-${planner}"]`);
  await p.waitForTimeout(800);
  const on = await p.evaluate(() => [...document.querySelectorAll('[data-testid^="planner-"][aria-checked="true"]')].map((e) => e.getAttribute('data-testid')));
  const href = await p.getAttribute('[data-testid="mode-fetch-rush"]', 'href');
  const saved = await p.evaluate(() => localStorage.getItem('coco.prefs.v1.planner'));
  if (planner === 'greedy') await p.screenshot({ path: `${out}/modes-planner-greedy.png`, timeout: 180000 });
  await p.click('[data-testid="mode-fetch-rush"]');
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  await p.click('[data-testid="g1-play"]');
  await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
  await p.click('[data-testid="hud-autonomy"]');
  const plans = await p.waitForFunction(() => { const t = window.__cocoGame?.tick; return t?.plans?.length ? t.plans.map((x) => x.planner) : null; }, null, { timeout: 240000 }).then((h) => h.jsonValue()).catch(() => null);
  await p.waitForTimeout(3000);
  if (planner === 'greedy') await p.screenshot({ path: `${out}/auto-greedy.png`, timeout: 180000 });
  const ok = (planner === 'astar' ? !href.includes('planner=') : href.includes(`planner=${planner}`)) && saved === JSON.stringify(planner)
    && Array.isArray(plans) && plans.every((x) => x === planner) && errors.length === 0;
  rows.push({ planner, ok: ok && on.length === 1 && on[0] === `planner-${planner}`, checked: on, href, saved, plans, errors });
  console.log(planner, rows.at(-1).ok ? 'ok' : 'FAILED', JSON.stringify({ checked: on, href, saved, plans, errors }));
  await ctx.close();
}
await b.close();
writeFileSync(`${out}/planner_check.json`, JSON.stringify({ site, passed: rows.every((r) => r.ok), rows }, null, 1) + '\n');
process.exitCode = rows.every((r) => r.ok) ? 0 : 1;
