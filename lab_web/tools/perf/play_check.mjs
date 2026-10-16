// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Play in a browser (M3.5):
 *
 *   node tools/perf/play_check.mjs --site URL --out DIR [--gpu 1] [--browser chromium|firefox|webkit]
 *
 * 1. ?view=play lists the five challenges, 0 errors.
 * 2. Each challenge, played as a learner would (clicks on the page), with a
 *    reference answer the level itself publishes -- A*'s path, A*'s
 *    expansions, the optimal order, the divergence tick -- must score 3 stars;
 *    Map the arena drives a short live drive and must score a valid result.
 * 3. Each result's challenge link, opened in a FRESH browser context, is
 *    re-scored from its inputs and must say "Reproduced exactly" (the same
 *    result hash).
 * Times: the scorer's boot (Pyodide + coco_lab + the play pack) and each
 * scoring, on the page's own clock.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, firefox, webkit } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'play-out';
const ENGINE = { chromium, firefox, webkit }[args.browser ?? 'chromium'];
const LAUNCH = args.gpu === '1' && ENGINE === chromium ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
if (args['webkit-exe']) LAUNCH.executablePath = args['webkit-exe'];
mkdirSync(OUT, { recursive: true });
const levels = JSON.parse(readFileSync(new URL('../../play/levels.json', import.meta.url), 'utf-8'));

const browser = await ENGINE.launch(LAUNCH);
const out = { site: SITE, browser: args.browser ?? 'chromium', rows: [] };

async function open(url) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(url);
  return { context, page, errors };
}

async function result(page, timeout = 180_000) {
  const t0 = Date.now();
  const el = page.getByTestId('play-result');
  await el.waitFor({ timeout });
  return { ms: Date.now() - t0, hash: await el.getAttribute('data-hash'), stars: Number(await el.getAttribute('data-stars')),
    valid: (await el.getAttribute('data-valid')) === 'true', score: await page.getByTestId('play-score').textContent() };
}

async function reproduce(link) {
  const { context, page, errors } = await open(link);
  const t0 = Date.now();
  try {
    await page.getByTestId('play-reproduced').waitFor({ timeout: 300_000 });
    const text = await page.getByTestId('play-reproduced').textContent();
    const r = await result(page, 10_000);
    return { ms: Date.now() - t0, exact: /Reproduced exactly/.test(text), hash: r.hash, stars: r.stars, errors };
  } finally { await context.close(); }
}

async function clickCell(page, [r, c]) {
  const cv = page.getByTestId('grid-board');
  const px = Number(await cv.getAttribute('data-px'));
  await cv.click({ position: { x: c * px + px / 2, y: r * px + px / 2 } });
}

async function level(challenge, lv, play) {
  const { context, page, errors } = await open(`${SITE}?view=play&c=${challenge}&l=${lv.id}`);
  const row = { challenge, level: lv.id, errors };
  try {
    const t0 = Date.now();
    await page.waitForFunction(() => !!window.__cocoPlay?.view, null, { timeout: 180_000 });
    row.scorer_ready_ms = Date.now() - t0;
    const view = await page.evaluate(() => window.__cocoPlay.view);
    await play(page, view);
    await page.getByTestId('play-submit').click();
    Object.assign(row, await result(page));
    await page.screenshot({path:join(OUT,challenge+'-'+lv.id+'.png'),scale:'css'});
    row.link = await page.getByTestId('play-link').getAttribute('href');
    row.reproduce = await reproduce(row.link);
    row.ok = errors.length === 0 && row.valid && row.stars === 3 && row.reproduce.exact && row.reproduce.hash === row.hash
      && row.reproduce.errors.length === 0;
  } catch (e) { row.ok = false; row.failure = String(e); }
  await context.close();
  out.rows.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${challenge}/${lv.id} stars ${row.stars} score ${row.score} scorer ${row.scorer_ready_ms} ms, scored in ${row.ms} ms, reproduced ${row.reproduce?.exact} in ${row.reproduce?.ms} ms${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
}

// 1. the list
{
  const { context, page, errors } = await open(`${SITE}?view=play`);
  await page.getByTestId('play').waitFor();
  await page.waitForTimeout(1000);
  const n = await page.locator('[data-testid^=challenge-]').count();
  out.list = { challenges: n, errors, ok: n === levels.order.length && errors.length === 0 };
  console.log(`${out.list.ok ? 'ok  ' : 'FAIL'} list: ${n} challenges`);
  await context.close();
}

// 2-3. every level of the three played on the Play page
const C = levels.challenges;
for (const lv of C['beat-the-planner'].levels) {
  await level('beat-the-planner', lv, async (page, view) => { for (const c of view.optimal_path.slice(1)) await clickCell(page, c); });
}
for (const lv of C['next-node'].levels) {
  await level('next-node', lv, async (page, view) => {
    for (let i = 0; i < view.frames.length; i += 1) {
      await clickCell(page, view.frames[i].expanded);
      if (i < view.frames.length - 1) await page.getByTestId('play-next').click();
    }
  });
}
for (const lv of C['search-the-bays'].levels) {
  await level('search-the-bays', lv, async (page) => { for (const i of lv.reference.optimal_order) await page.getByTestId(`bay-${i}`).click(); });
}

// the two played in the Arena
async function inArena(challenge, lv, url, play) {
  const { context, page, errors } = await open(url);
  const row = { challenge, level: lv.id, errors };
  try {
    await page.getByTestId('play-panel').waitFor({ timeout: 60_000 });
    await play(page);
    await page.getByRole('button',{name:'Settings',exact:true}).click();
    await page.getByRole('button',{name:'Game menu and inspection'}).click();
    await page.locator('[data-testid=play-submit]:not([disabled])').waitFor({ timeout: 180_000 });
    await page.getByTestId('play-submit').click();
    Object.assign(row, await result(page, 300_000));
    await page.screenshot({path:join(OUT,challenge+'-'+lv.id+'.png'),scale:'css'});
    row.link = await page.getByTestId('play-link').getAttribute('href');
    row.reproduce = await reproduce(row.link);
    row.ok = errors.length === 0 && row.valid && row.reproduce.exact && row.reproduce.hash === row.hash
      && row.reproduce.errors.length === 0 && (challenge !== 'case-file-detective' || row.stars === 3);
  } catch (e) { row.ok = false; row.failure = String(e); }
  await context.close();
  out.rows.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${challenge}/${lv.id} stars ${row.stars} score ${row.score} scored in ${row.ms} ms, reproduced ${row.reproduce?.exact} in ${row.reproduce?.ms} ms${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
}

for (const lv of C['case-file-detective'].levels) {
  const url = `${SITE}?view=arena&casefile=${lv.casefile}&lens=localise&level=explain&play=case-file-detective&pl=${lv.id}`;
  await inArena('case-file-detective', lv, url, async (page) => {
    await page.waitForFunction(() => !!window.__cocoPerf?.marks?.recording_ready, null, { timeout: 120_000 });
    await page.evaluate((t) => { const s = window.__cocoArena.session(); s.playing = false; s.seekTick(t); }, lv.moment.tick);
    await page.waitForTimeout(500);
  });
}
{
  const lv = C['map-the-arena'].levels[1];
  const q = new URLSearchParams({ view: 'arena', lens: 'map', level: 'explain', play: 'map-the-arena', pl: lv.id });
  for (const c of lv.config) q.append('cfg', c);
  await inArena('map-the-arena', lv, `${SITE}?${q}`, async (page) => {
    await page.waitForFunction(() => window.__cocoArena?.mode?.() === 'live', null, { timeout: 120_000 });
    await page.waitForFunction(() => /driven/.test(document.querySelector('[data-testid=play-meter]')?.textContent ?? ''), null, { timeout: 120_000 });
    await page.evaluate(() => window.__cocoArena.goal(6.0, 4.0));
    await page.waitForFunction(() => { const m = /driven ([\d.]+)/.exec(document.querySelector('[data-testid=play-meter]')?.textContent ?? ''); return m && Number(m[1]) >= 5; }, null, { timeout: 180_000 });
  });
}

await browser.close();
out.summary = { rows: out.rows.length, ok: out.rows.filter((r) => r.ok).length, list_ok: out.list.ok };
out.ok = out.list.ok && out.rows.every((r) => r.ok);
writeFileSync(join(OUT, `play_check_${out.browser}.json`), JSON.stringify({ ...out, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(out.summary));
process.exit(out.ok ? 0 : 1);
