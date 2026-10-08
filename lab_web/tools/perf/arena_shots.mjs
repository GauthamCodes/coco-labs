// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Arena screenshots and a smoke check (M1.6): load, give a goal, watch the
 * search, switch to the heatmap, inspect a cell -- at laptop and phone
 * width, light and dark. Records console errors and what the inspector says.
 *
 *   node tools/perf/arena_shots.mjs --site http://127.0.0.1:4174/coco-labs/ --out DIR
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const OUT = args.out ?? 'arena-shots';
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader'] });
const result = { site: SITE, browser: browser.version(), runs: [] };
for (const [w, h, theme] of [[1280, 900, 'light'], [1280, 900, 'dark'], [390, 844, 'light']]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${SITE}?view=arena&perf&theme=${theme}`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await sleep(500);
  await page.screenshot({ path: join(OUT, `arena_${w}_${theme}_ready.png`) });
  await page.evaluate(() => window.__cocoArena.goal(6.0, 4.0));
  await sleep(250);
  await page.screenshot({ path: join(OUT, `arena_${w}_${theme}_searching.png`) });
  await sleep(2500);
  await page.screenshot({ path: join(OUT, `arena_${w}_${theme}_planned.png`) });
  await page.getByTestId('layer-heatmap').check();
  await sleep(300);
  await page.screenshot({ path: join(OUT, `arena_${w}_${theme}_heatmap.png`) });
  // inspect the start's neighbourhood: the robot's cell is expanded first
  await page.getByTestId('inspect-toggle').click();
  const box = await page.getByTestId('arena-canvas').boundingBox();
  const target = await page.evaluate(() => {
    const r = window.__cocoArena.renderer;
    const p = window.__cocoArena.last.pose;
    const rect = r.canvas.getBoundingClientRect();
    // map metres -> client pixels via two toWorld probes
    const a = r.toWorld(rect.left, rect.top);
    const b = r.toWorld(rect.left + 100, rect.top + 100);
    const sx = 100 / (b[0] - a[0]);
    const sy = 100 / (a[1] - b[1]);
    return [rect.left + (p[0] - a[0]) * sx, rect.top + (a[1] - p[1]) * sy];
  });
  void box;
  await page.mouse.click(target[0], target[1]);
  await sleep(300);
  const inspector = await page.getByTestId('inspector').textContent().catch(() => null);
  await page.screenshot({ path: join(OUT, `arena_${w}_${theme}_inspect.png`) });
  const status = await page.getByTestId('arena-tick').textContent();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  result.runs.push({ width: w, theme, errors, status, inspector, horizontal_overflow: overflow,
    webgl2: await page.evaluate(() => !!document.createElement('canvas').getContext('webgl2')) });
  console.log(JSON.stringify(result.runs.at(-1)));
  await page.close();
}
await browser.close();
writeFileSync(join(OUT, 'arena_shots.json'), JSON.stringify(result, null, 1) + '\n');
