// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The public site after a merge (M1 review A.5; reused at every milestone
 * exit), in headless Chromium:
 *
 *   node tools/perf/public_check.mjs [--site https://gauthamcodes.github.io/coco-labs/] --out FILE.json
 *
 * 1. The BARE URL: it must open the Arena; the live model must become ready;
 *    a real mouse click on open floor must produce that goal's search, drawn
 *    on screen (the page's own perf records: the click, then the first frame
 *    that drew the search planned for those goal coordinates).
 * 2. Each v1 view (`?view=plan|live|localise|map|search|move`) in a fresh
 *    page: since M2.10 the five lab views land on their Learn mission and
 *    Live on the Live view (src/landing.ts); each must land there and log 0
 *    console errors and 0 page errors over a settle window that covers
 *    Live's probe backoff. (Every other v1 URL form: v1_links_check.mjs.)
 * Every page's console errors, page errors and cross-origin requests are
 * recorded. Exit 0 only if everything passes.
 */

import { writeFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'https://gauthamcodes.github.io/coco-labs/';
const SETTLE_MS = Number(args.settle ?? 8000);
const VIEWS = ['plan', 'live', 'localise', 'map', 'search', 'move'];
// where each lands since M2.10 (src/landing.ts MISSION_FOR_VIEW)
const LANDS = { plan: 'mission:find-a-path', localise: 'mission:where-it-is', map: 'mission:build-a-map',
  search: 'mission:where-to-look', move: 'mission:avoid-things', live: 'live' };
const GOAL = [6.0, 4.0]; // open floor in the map frame (responsiveness.mjs's first goal)

const browser = await chromium.launch();
const origin = new URL(SITE).origin;
const out = { site: SITE, bare: null, views: [], pass: false };

function watch(page) {
  const rec = { console_errors: [], page_errors: [], cross_origin: [] };
  page.on('console', (m) => { if (m.type() === 'error') rec.console_errors.push(m.text()); });
  page.on('pageerror', (e) => rec.page_errors.push(String(e)));
  page.on('request', (r) => { if (!r.url().startsWith(origin) && !r.url().startsWith('data:') && !r.url().startsWith('blob:')) rec.cross_origin.push(r.url()); });
  return rec;
}

try {
  // 1. the bare URL
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    const page = await ctx.newPage();
    const rec = watch(page);
    const t0 = Date.now();
    await page.goto(SITE);
    await page.waitForFunction(() => !!document.querySelector('[data-testid=arena]'), null, { timeout: 60_000 });
    const opened = 'arena';
    await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 180_000 });
    // the page's marks are wall-clock (performance.timeOrigin + now): make them ms since navigation
    const marks = await page.evaluate(() => Object.fromEntries(Object.entries(window.__cocoPerf.marks).map(([k, v]) => [k, Math.round(v - performance.timeOrigin)])));
    const [sx, sy] = await page.evaluate(([x, y]) => {
      const r = window.__cocoArena.renderer;
      const b = r.canvas.getBoundingClientRect();
      const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
      const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
      return [cx + (x - p0[0]) / ((px[0] - p0[0]) / 100), cy + (y - p0[1]) / ((py[1] - p0[1]) / 100)];
    }, GOAL);
    const nClicks = await page.evaluate(() => window.__cocoPerf.goalClicks.length);
    await page.mouse.click(sx, sy);
    const handle = await page.waitForFunction(([gx, gy]) => {
      for (const h of window.__cocoArena.session()?.history ?? []) {
        for (const p of h.plans) if (Math.hypot(p.goal[0] - gx, p.goal[1] - gy) < 0.1) return { id: p.search_id, status: p.status, expansions: p.summary?.expansions ?? null };
      }
      return false;
    }, GOAL, { timeout: 60_000, polling: 50 });
    const plan = await handle.jsonValue();
    await page.waitForTimeout(1500);
    const shown = await page.evaluate(([n, id]) => ({
      click: window.__cocoPerf.goalClicks[n] ?? null,
      drawn: window.__cocoPerf.firstDraw.get(id) ?? null,
      cursor: window.__cocoArena.session()?.shownSearch?.cursor ?? 0,
      mode: window.__cocoArena.mode(),
    }), [nClicks, plan.id]);
    out.bare = {
      opened, ms_since_navigation: marks, wall_ms_to_ready: Date.now() - t0, goal: GOAL, plan,
      click_to_drawn_ms: shown.drawn !== null && shown.click !== null ? shown.drawn - shown.click : null,
      shown_cursor: shown.cursor, mode: shown.mode, ...rec,
    };
    out.bare.pass = opened === 'arena' && shown.drawn !== null && shown.cursor > 0 && rec.console_errors.length === 0 && rec.page_errors.length === 0;
    console.log(`bare: ${out.bare.pass ? 'PASS' : 'FAIL'} arena ready ${marks.arena_ready} ms; goal search ${plan.id} (${plan.status}) drawn ${out.bare.click_to_drawn_ms} ms after the click; errors ${rec.console_errors.length}`);
    await ctx.close();
  }
  // 2. the six v1 views
  for (const v of VIEWS) {
    const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const page = await ctx.newPage();
    const rec = watch(page);
    await page.goto(`${SITE}?view=${v}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(SETTLE_MS);
    const app = await page.evaluate(() => {
      const m = document.querySelector('[data-testid=mission]');
      if (m) return `mission:${m.getAttribute('data-mission')}`;
      if (document.querySelector('[data-testid=nav-arena]')) return 'live';
      return document.querySelector('[data-testid=arena]') ? 'arena' : 'other';
    });
    const one = { view: v, opened: app, url: page.url(), ...rec };
    one.pass = app === LANDS[v] && rec.console_errors.length === 0 && rec.page_errors.length === 0;
    out.views.push(one);
    console.log(`${v}: ${one.pass ? 'PASS' : 'FAIL'} opened ${app}; console ${rec.console_errors.length}, page ${rec.page_errors.length}, cross-origin ${rec.cross_origin.length}`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
out.browser = 'chromium (Playwright, headless)';
out.pass = !!out.bare?.pass && out.views.length === VIEWS.length && out.views.every((x) => x.pass);
if (args.out) writeFileSync(args.out, JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass }));
process.exit(out.pass ? 0 : 1);
