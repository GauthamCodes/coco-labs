// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.10: the phone-width layout (README §7 M4 acceptance, Hygiene: "phone-width layout checked").
 *
 *   node tools/perf/layout_check.mjs --out DIR [--site URL]
 *
 * Each view at a phone in portrait (390 x 844) and landscape (844 x 390), touch and mobile,
 * and a laptop (1280 x 800): no horizontal scroll (scrollWidth <= innerWidth), and on the
 * Arena the HUD's STOP button reachable (inside the viewport once the canvas is in view).
 * The phone here is a viewport in Chromium (EMULATED), never a phone. Records page errors.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';

const CONDITIONS_AT_START = conditions();
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const OUT = args.out ?? 'layout-check';
mkdirSync(OUT, { recursive: true });
const VIEWPORTS = [
  { name: 'phone_portrait', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  { name: 'phone_landscape', viewport: { width: 844, height: 390 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 },
  { name: 'laptop', viewport: { width: 1280, height: 800 } },
];
const VIEWS = [
  ['arena (3D)', '?view=arena', true], ['arena terrain', '?view=arena&world=v2', true],
  ['race', '?view=arena&play=race-the-ghost&pl=warm-up&camera=follow&seed=1', true],
  ['case file (3D)', '?view=arena&casefile=lab4_b1_colours_s5_red', false],
  ['learn', '?view=learn', false], ['play', '?view=play', false], ['case files', '?view=casefiles', false],
];
const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const rows = [];
for (const vp of VIEWPORTS) {
  for (const [name, q, live] of VIEWS) {
    const ctx = await b.newContext({ viewport: vp.viewport, isMobile: vp.isMobile, hasTouch: vp.hasTouch, deviceScaleFactor: vp.deviceScaleFactor });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    const row = { viewport: vp.name, view: name };
    try {
      await page.goto(`${SITE}${q}`);
      await page.waitForLoadState('networkidle', { timeout: 120_000 }).catch(() => {});
      await page.waitForTimeout(2500);
      if (live) {
        // a first touch takes over the live model, so the live HUD shows
        const cv = page.locator('canvas').first();
        await cv.scrollIntoViewIfNeeded();
        await page.keyboard.press('KeyS').catch(() => {});
        await page.waitForTimeout(1500);
      }
      Object.assign(row, await page.evaluate(() => {
        const stop = document.querySelector('[data-testid=hud-stop-btn]');
        const r = stop?.getBoundingClientRect();
        return { scroll_width: document.documentElement.scrollWidth, inner_width: innerWidth,
          stop: stop ? { visible: r.width > 0 && r.height > 0, within: r.right <= innerWidth && r.left >= 0 } : null };
      }));
      row.no_horizontal_scroll = row.scroll_width <= row.inner_width;
      await page.screenshot({ path: join(OUT, `${vp.name}_${name.replace(/[^a-z0-9]+/g, '_')}.png`) });
    } catch (e) {
      row.failure = String(e).split('\n')[0];
    }
    row.errors = errors;
    rows.push(row);
    console.log(JSON.stringify([vp.name, name, row.no_horizontal_scroll, row.stop, errors.length, row.failure ?? '']));
    await ctx.close();
  }
}
await b.close();
const verdict = {
  no_horizontal_scroll: rows.every((r) => r.no_horizontal_scroll),
  stop_reachable_on_touch: rows.filter((r) => r.viewport !== 'laptop' && r.stop).every((r) => r.stop.visible && r.stop.within),
  no_page_errors: rows.every((r) => r.errors.length === 0 && !r.failure),
};
const result = { criterion: 'M4.10: phone-width layout (EMULATED viewports)', verdict, rows };
writeFileSync(join(OUT, 'layout_check.json'), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(verdict));
