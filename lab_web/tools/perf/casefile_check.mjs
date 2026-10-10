// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Case Files in a browser (M3.3; the M3 B.3 "Case File loading" and
 * "Hygiene" rows):
 *
 *   node tools/perf/casefile_check.mjs --site URL --out DIR [--only ID,ID] [--throttle none|4g] [--gpu 1]
 *
 * 1. The list and every group page (?view=casefiles[&case=G]): they render,
 *    with the STACK badge, every explanation sentence and unresolved question
 *    shown with its label, and 0 console / page errors.
 * 2. Every Case File (or --only), opened in the Arena viewer
 *    (?view=arena&casefile=ID): it plays as a recording (STACK), and
 *    - first frame = the page's `recording_ready` mark minus its
 *      `casefile_fetch_start` mark: the Case File fetched, parsed, every tick
 *      loaded and the first one drawn (the app itself already loaded);
 *    - 10 seeks across the recording, each to the frame that shows it;
 *    - 0 console and page errors.
 * With --throttle 4g the page and its workers get 9 Mbit/s, 1.5 up, 170 ms.
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
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'casefile-out';
const THROTTLE = args.throttle ?? 'none';
const PROFILES = { none: null, '4g': { downloadThroughput: 9e6 / 8, uploadThroughput: 1.5e6 / 8, latency: 170 } };
const LAUNCH = args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch(LAUNCH);
const cases = await (await fetch(`${SITE}generated/casefiles/cases.json`)).json();
const all = cases.groups.flatMap((g) => g.casefiles.map((c) => ({ ...c, group: g.id })));
const only = args.only ? new Set(args.only.split(',')) : null;
const out = { site: SITE, throttle: THROTTLE, profile: PROFILES[THROTTLE], pages: [], casefiles: [] };

async function open(url) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const p = PROFILES[THROTTLE];
  if (p) {
    const apply = async (t) => { const cdp = await context.newCDPSession(t); await cdp.send('Network.enable'); await cdp.send('Network.emulateNetworkConditions', { offline: false, ...p }); };
    await apply(page);
    page.on('worker', (w) => { void apply(w).catch(() => {}); });
  }
  await page.goto(url);
  return { context, page, errors };
}

// 1. the list and every group
for (const g of [null, ...cases.groups]) {
  const url = `${SITE}?view=casefiles${g ? `&case=${g.id}` : ''}`;
  const { context, page, errors } = await open(url);
  const row = { page: g ? g.id : '(list)', errors };
  try {
    await page.waitForSelector(g ? '[data-testid=casefile-group]' : '[data-testid=casefiles]', { timeout: 30_000 });
    row.badge = await page.getByTestId('evidence-badge').first().textContent();
    if (g) {
      row.explained = await page.locator('[data-testid^=explain-] .claim-label').count();
      row.unresolved = await page.locator('[data-testid^=unresolved-] .claim-label').allTextContents();
      row.listed = await page.locator('[data-testid=casefile-list] li').count();
    }
    await page.waitForTimeout(1500);
    row.ok = errors.length === 0 && row.badge === 'STACK' && (!g || (row.explained === g.explain.length
      && row.unresolved.length === g.unresolved.length && row.unresolved.every((x) => x === 'UNRESOLVED')));
  } catch (e) { row.ok = false; row.failure = String(e); }
  out.pages.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} page ${row.page}${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await context.close();
}

// 1b. phone width (390 px, a Pixel 7): no horizontal scroll on the list, a group, a comparison
out.phone = [];
for (const q of ['?view=casefiles', '?view=casefiles&case=lab5-move',
  '?view=casefiles&case=lab5-move&file=lab5_crossing_dwb_1', '?view=casefiles&case=lab3-slam']) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${SITE}${q}`);
  await page.waitForSelector('[data-testid=casefiles], [data-testid=casefile-group]', { timeout: 30_000 });
  await page.waitForTimeout(1500);
  const w = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, view: window.innerWidth }));
  const row = { page: q, ...w, errors, ok: w.scroll <= w.view && errors.length === 0 };
  out.phone.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} phone ${q} scroll ${w.scroll} / ${w.view}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await context.close();
}

// 2. every Case File in the viewer
for (const c of all.filter((x) => !only || only.has(x.id))) {
  const { context, page, errors } = await open(`${SITE}?view=arena&casefile=${c.id}`);
  const row = { id: c.id, group: c.group, bytes: c.bytes, errors };
  try {
    await page.waitForFunction(() => !!window.__cocoPerf?.marks?.recording_ready, null, { timeout: 120_000 });
    const marks = await page.evaluate(() => window.__cocoPerf.marks);
    row.first_frame_ms = marks.recording_ready - marks.casefile_fetch_start;
    row.mode = await page.evaluate(() => window.__cocoArena?.mode?.());
    row.badge = await page.getByTestId('evidence-badge').textContent();
    const last = await page.evaluate(() => window.__cocoArena.session().head);
    row.ticks = last;
    const targets = [0.5, 0.05, 0.95, 0.25, 0.75, 0.1, 0.9, 0.33, 0.66, 0.0].map((f) => Math.max(1, Math.floor(f * last)));
    row.seeks = [];
    for (const t of targets) {
      row.seeks.push(await page.evaluate((tick) => new Promise((resolve) => {
        const s = window.__cocoArena.session();
        s.playing = false;
        const a = performance.now();
        s.seekTick(tick);
        requestAnimationFrame(() => requestAnimationFrame(() => resolve({ to: tick, to_frame_ms: performance.now() - a,
          view_tick: s.shownTick?.tick })));
      }), t));
    }
    row.seek_max_ms = Math.max(...row.seeks.map((x) => x.to_frame_ms));
    await page.waitForTimeout(500);
    row.ok = errors.length === 0 && row.mode === 'recording' && row.badge === 'STACK' && row.ticks > 1
      && row.seeks.every((x) => x.view_tick === x.to || (x.to >= last && x.view_tick === last));
  } catch (e) { row.ok = false; row.failure = String(e); }
  out.casefiles.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${c.id} first ${Math.round(row.first_frame_ms)} ms, seek max ${row.seek_max_ms?.toFixed(1)} ms, ${row.ticks} ticks${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await context.close();
}
await browser.close();
const firsts = out.casefiles.map((r) => r.first_frame_ms).filter(Number.isFinite);
const seeks = out.casefiles.map((r) => r.seek_max_ms).filter(Number.isFinite);
out.summary = {
  pages_ok: out.pages.filter((r) => r.ok).length, pages: out.pages.length,
  casefiles_ok: out.casefiles.filter((r) => r.ok).length, casefiles: out.casefiles.length,
  first_frame_ms_max: Math.max(...firsts), first_frame_ms_median: firsts.sort((a, b) => a - b)[firsts.length >> 1],
  seek_ms_max: Math.max(...seeks), console_errors: [...out.pages, ...out.casefiles].reduce((n, r) => n + r.errors.length, 0),
};
out.summary.phone_ok = out.phone.filter((r) => r.ok).length;
out.ok = out.summary.pages_ok === out.pages.length && out.summary.casefiles_ok === out.casefiles.length && out.summary.phone_ok === out.phone.length;
writeFileSync(join(OUT, `casefile_check_${THROTTLE}.json`), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify(out.summary));
process.exit(out.ok ? 0 : 1);
