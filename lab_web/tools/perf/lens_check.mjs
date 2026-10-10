// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The lens framework in a real browser (M2.2; reused at M2.11):
 *
 *   node tools/perf/lens_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Opens the Arena, waits for the live model, then for every lens: selects
 * it and times its Python pack from the click to the worker's
 * `pack_<name>_ready` mark (COLD: first visit in this browser context),
 * steps through Watch / Explain / Inspect counting the computation layers
 * switched on, toggles Focus, and screenshots. Then a second page in the
 * SAME context (warm HTTP cache) selects every lens again and times the
 * packs (the M2 budget: ready within 3 s of selection, warm cache). Last, a
 * Pixel 7 viewport: the lens bar wraps with no horizontal scroll. Records
 * console errors and page errors throughout; exit 0 only if there are none.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, devices } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4194/coco-labs/';
const OUT = args.out ?? 'lens-out';
const GPU = args.gpu === '1';
mkdirSync(OUT, { recursive: true });
const LENSES = ['plan', 'localise', 'map', 'move', 'decide'];
const PACK = { plan: 'core', localise: 'localise', map: 'map', move: 'move', decide: 'decide' };

const browser = await chromium.launch(GPU ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
const errors = [];
const out = { site: SITE, cold: {}, warm: {}, levels: {}, phone: null, errors };

async function open() {
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  return page;
}

async function timePacks(page, into) {
  for (const l of LENSES) {
    const t0 = await page.evaluate(() => performance.timeOrigin + performance.now());
    await page.getByTestId(`lens-${l}`).click();
    if (PACK[l] === 'core') { into[l] = { pack: 'core', ms: 0 }; continue; }
    await page.waitForFunction((p) => !!window.__cocoPerf.marks[`pack_${p}_ready`], PACK[l], { timeout: 30_000 });
    const at = await page.evaluate((p) => window.__cocoPerf.marks[`pack_${p}_ready`], PACK[l]);
    into[l] = { pack: PACK[l], ms: Math.round(at - t0) };
  }
}

try {
  const page = await open();
  await timePacks(page, out.cold);
  for (const l of LENSES) {
    await page.getByTestId(`lens-${l}`).click();
    out.levels[l] = {};
    for (const v of ['watch', 'explain', 'inspect']) {
      await page.getByTestId(`level-${v}`).click();
      await page.waitForTimeout(150);
      out.levels[l][v] = await page.evaluate((lens) => {
        const own = [...document.querySelectorAll('[data-testid^="lens-layer-"]')].filter((e) => e.checked && e.dataset.role !== 'world').map((e) => e.dataset.testid.slice(11));
        const plan = lens === 'plan' ? ['frontier', 'path', 'closed', 'heatmap'].filter((k) => document.querySelector(`[data-testid="layer-${k}"]`)?.checked) : [];
        return { layers_on: lens === 'plan' ? plan : own, inspect_panel: !!document.querySelector('[data-testid="lens-inspect"]') };
      }, l);
    }
    await page.getByTestId('focus-toggle').check();
    await page.waitForTimeout(150);
    await page.screenshot({ path: join(OUT, `lens_${l}_inspect_focus.png`) });
    await page.getByTestId('focus-toggle').uncheck();
    await page.getByTestId('level-watch').click();
  }
  // Explain: a value label under the mouse (Plan lens, over a search the live model just ran)
  await page.getByTestId('lens-plan').click();
  await page.getByTestId('level-explain').click();
  const toScreen = (x, y) => page.evaluate(([x, y]) => {
    const r = window.__cocoArena.renderer;
    const b = r.canvas.getBoundingClientRect();
    const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
    const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
    return [cx + (x - p0[0]) / ((px[0] - p0[0]) / 100), cy + (y - p0[1]) / ((py[1] - p0[1]) / 100)];
  }, [x, y]);
  const [gx, gy] = await toScreen(6.0, 4.0); // open floor (responsiveness.mjs's first goal)
  await page.mouse.click(gx, gy);
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live' && (window.__cocoArena.session()?.shownSearch?.pathCells?.length ?? 0) > 3, null, { timeout: 30_000 });
  // a cell on the search's path, in the map frame (LabMap rows run top-down)
  const [cx, cy] = await page.evaluate(() => {
    const s = window.__cocoArena.session(); const st = s.shownSearch; const w = window.__cocoArena.client.world;
    const i = st.pathCells[Math.floor(st.pathCells.length / 2)];
    const row = Math.floor(i / w.width); const col = i % w.width;
    return [w.origin[0] + (col + 0.5) * w.resolution, w.origin[1] + (w.height - 1 - row + 0.5) * w.resolution];
  });
  const [sx, sy] = await toScreen(cx, cy);
  await page.mouse.move(sx - 3, sy - 3);
  await page.mouse.move(sx, sy, { steps: 3 });
  await page.waitForTimeout(150);
  out.hover = await page.evaluate(() => document.querySelector('[data-testid="hover-label"]')?.textContent ?? null);
  await page.close();
  // warm: a new page in the same browser context (HTTP cache warm)
  const page2 = await open();
  await timePacks(page2, out.warm);
  await page2.close();
  // phone width
  const phone = await browser.newContext({ ...devices['Pixel 7'] });
  const p3 = await phone.newPage();
  p3.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  p3.on('pageerror', (e) => errors.push(String(e)));
  await p3.goto(`${SITE}?view=arena`);
  await p3.waitForSelector('[data-testid="lens-bar"]');
  await p3.waitForTimeout(1500);
  out.phone = await p3.evaluate(() => ({ overflow_x: document.documentElement.scrollWidth > window.innerWidth + 1,
    width: window.innerWidth, lens_bar_h: document.querySelector('[data-testid="lens-bar"]').getBoundingClientRect().height }));
  await p3.screenshot({ path: join(OUT, 'lens_bar_pixel7.png'), fullPage: true });
  await phone.close();
} finally {
  await browser.close();
}
const coldMax = Math.max(...Object.values(out.cold).map((x) => x.ms));
const warmMax = Math.max(...Object.values(out.warm).map((x) => x.ms));
const watchOk = LENSES.every((l) => (out.levels[l]?.watch?.layers_on.length ?? 9) <= 2);
out.summary = { cold_pack_ms_max: coldMax, warm_pack_ms_max: warmMax, warm_under_3s: warmMax <= 3000, watch_at_most_two: watchOk,
  phone_no_overflow: out.phone && !out.phone.overflow_x, hover_label: out.hover, console_errors: errors.length };
out.pass = errors.length === 0 && watchOk && out.summary.phone_no_overflow && !!out.hover;
writeFileSync(join(OUT, 'lens_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify(out.summary));
process.exit(out.pass ? 0 : 1);
