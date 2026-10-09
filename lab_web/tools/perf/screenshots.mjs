// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Screenshot tests for the Arena (M1 B.4, Hygiene): the map canvas of
 * fixed, deterministic scenes -- recorded runs and the attract recording,
 * paused at a set tick with the search fully revealed -- compared with
 * committed baselines (lab_web/test/screenshots/).
 *
 *   node tools/perf/screenshots.mjs make  --site URL   (write baselines)
 *   node tools/perf/screenshots.mjs check --site URL [--out DIR]
 *
 * Rendering is Chromium's default software GL (SwiftShader), as on CI's
 * runners; only the canvas is captured, so no system font is in the image.
 * Two images match when at most MAX_BAD of the pixels differ by more than
 * CHANNEL_TOL in any channel (antialiasing may differ by a few pixels across
 * machines; a missing layer, a moved robot or a wrong colour does not pass).
 * The decode and the comparison run in the page (createImageBitmap), so no
 * PNG library is needed.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const web = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const BASE = join(web, 'test', 'screenshots');
const [mode, ...rest] = process.argv.slice(2);
const args = Object.fromEntries(rest.reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const OUT = args.out ?? join(web, 'screenshots-out');
const CHANNEL_TOL = 40;
const MAX_BAD = 0.005;

/** [name, query, tick to show (null: the last), layers to switch off] */
const SCENES = [
  ['trace_bfs_no_path', 'replay=bfs_no_path', null],
  ['trace_costmap_astar', 'replay=costmap_0_10m', null],
  ['stack_lab1c_astar_t400', 'replay=lab1c_astar', 400],
  ['stack_lab1c_greedy_t300', 'replay=lab1c_greedy', 300],
  ['attract_t200', '', 200],
];

async function shoot(page, query, tick) {
  await page.goto(`${SITE}?view=arena${query ? `&${query}` : ''}`);
  await page.waitForFunction(() => !!window.__cocoArena?.session()?.shownTick, null, { timeout: 120_000 });
  await page.evaluate(() => window.__cocoArena.session().setSpeed(4));
  await page.waitForFunction((t) => {
    const s = window.__cocoArena.session();
    const st = s.shownSearch;
    return (t === null || s.head >= t) && (!st || (st.final && st.cursor >= st.received));
  }, tick, { timeout: 180_000, polling: 250 });
  await page.evaluate((t) => {
    const s = window.__cocoArena.session();
    s.playing = false;
    if (t !== null) s.seekTick(t);
    const st = s.shownSearch;
    if (st) s.seekSeq(st.received);
  }, tick);
  await page.waitForTimeout(3000); // a few frames, even on software GL
  return page.getByTestId('arena-canvas').screenshot();
}

async function compare(page, a, b) {
  return page.evaluate(async ([a, b]) => {
    const load = async (b64) => {
      // no fetch(): the site's CSP does not allow data: URLs, and needs not to
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const bmp = await createImageBitmap(new Blob([bytes], { type: 'image/png' }));
      const c = new OffscreenCanvas(bmp.width, bmp.height);
      const g = c.getContext('2d');
      g.drawImage(bmp, 0, 0);
      return g.getImageData(0, 0, bmp.width, bmp.height);
    };
    const [x, y] = await Promise.all([load(a), load(b)]);
    if (x.width !== y.width || x.height !== y.height) return { size: [x.width, x.height, y.width, y.height], bad: 1 };
    let bad = 0;
    for (let i = 0; i < x.data.length; i += 4) {
      if (Math.max(Math.abs(x.data[i] - y.data[i]), Math.abs(x.data[i + 1] - y.data[i + 1]),
        Math.abs(x.data[i + 2] - y.data[i + 2])) > 40) bad += 1;
    }
    return { size: [x.width, x.height], bad: bad / (x.width * x.height) };
  }, [a.toString('base64'), b.toString('base64')]);
}

const browser = await chromium.launch(); // default GL: SwiftShader, as on CI
const page = await browser.newPage({ viewport: { width: 1000, height: 900 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const results = {};
try {
  mkdirSync(mode === 'make' ? BASE : OUT, { recursive: true });
  if (mode !== 'make') {
    // a check that passes on "no difference" must first show it can see one:
    // two different scenes (two recorded runs, different ticks) must FAIL
    await page.goto(`${SITE}?view=plan`);
    const a = readFileSync(join(BASE, 'stack_lab1c_astar_t400.png'));
    const b = readFileSync(join(BASE, 'stack_lab1c_greedy_t300.png'));
    const c = await compare(page, a, b);
    results.self_test = { pass: c.bad > MAX_BAD, differing_fraction: c.bad, compared: 'stack_lab1c_astar_t400 vs stack_lab1c_greedy_t300' };
    console.log('self_test', JSON.stringify(results.self_test));
  }
  for (const [name, query, tick] of SCENES) {
    const png = await shoot(page, query, tick);
    if (mode === 'make') {
      writeFileSync(join(BASE, `${name}.png`), png);
      results[name] = { bytes: png.length };
    } else {
      const ref = join(BASE, `${name}.png`);
      if (!existsSync(ref)) { results[name] = { pass: false, error: 'no baseline' }; continue; }
      writeFileSync(join(OUT, `${name}.png`), png);
      const c = await compare(page, png, readFileSync(ref));
      results[name] = { pass: c.bad <= MAX_BAD, differing_fraction: c.bad, size: c.size };
    }
    console.log(name, JSON.stringify(results[name]));
  }
} finally {
  await browser.close();
}
const pass = mode === 'make' || (Object.values(results).every((r) => r.pass) && errors.length === 0);
const report = { mode, site: SITE, renderer: 'chromium default (SwiftShader)', channel_tol: CHANNEL_TOL, max_bad: MAX_BAD, results, errors, pass };
writeFileSync(join(mode === 'make' ? BASE : OUT, mode === 'make' ? 'baselines.json' : 'screenshots.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...report }, null, 1) + '\n');
console.log(JSON.stringify({ pass, errors: errors.length }));
process.exit(pass ? 0 : 1);
