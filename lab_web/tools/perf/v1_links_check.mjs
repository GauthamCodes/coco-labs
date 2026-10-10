// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Every v1 URL form still resolves (M2.10, B.3 "Links"):
 *
 *   node tools/perf/v1_links_check.mjs --site URL --out DIR
 *
 * Opens each form a v1 page understood -- the six views, the deep links
 * into a lab, Lab 1's bundle links and share links (plain, with settings,
 * with map edits), the bare URL and the archive itself -- and asserts where
 * it lands (a Learn mission, a converted run in the Arena, the Live view,
 * or the frozen v1 build at v1/ with its query intact) and what renders
 * there, with 0 console errors and 0 page errors on every one. The site
 * must be served with the v1 archive at v1/ (lab_web/tools/build_v1_archive.sh).
 *
 * Then each of the archive's six views (v1/?view=..., Lab 1 Plan, Localise,
 * Map, Search, Move, Live Stack (simulated)) opens with 0 console and 0 page
 * errors and none of them says "real robot" (M2 review, 2026-10-10: the
 * archive is built from 9f58b83, which carries M0's public fixes).
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
const SITE = args.site ?? 'http://127.0.0.1:4194/coco-labs/';
const OUT = args.out ?? 'v1-links-out';
mkdirSync(OUT, { recursive: true });

// a share link with settings (weighted A*, Manhattan, 4-connected, FIFO, w 2.25 -- indices into the
// catalog's lists) and one with a map edit (cell 189 made occupied: LEB128 gap 189, then (1-1)*2+1)
const SETTINGS = '4.1.4.1.9';
const EDIT = Buffer.from([0xbd, 0x01, 0x01]).toString('base64url');

const mission = (id) => ({ kind: 'mission', id });
const v1 = (pressed) => ({ kind: 'v1', pressed });
const FORMS = [
  ['', { kind: 'arena', mode: ['attract', 'live'] }],
  ['?view=plan', mission('find-a-path')],
  ['?view=localise', mission('where-it-is')],
  ['?view=map', mission('build-a-map')],
  ['?view=search', mission('where-to-look')],
  ['?view=move', mission('avoid-things')],
  ['?view=plan&perf', mission('find-a-path')],
  ['?view=live', { kind: 'live' }],
  ['?view=exhibit', v1('view-exhibit')], // the README links here; v1 opens the exhibit once its catalog loads
  ['?view=localise&loc=exhibits', v1('view-localise')],
  ['?view=map&scene=map_loop', v1('view-map')],
  ['?view=move&move=replan', v1('view-move')],
  ['?view=search&search=matrix', v1('view-search')],
  ['?bundle=astar_open', { kind: 'replay', id: 'astar_open' }],
  ['?bundle=astar_open&v=1', { kind: 'replay', id: 'astar_open' }],
  ['?view=plan&bundle=astar_open&v=1', { kind: 'replay', id: 'astar_open' }],
  ['?bundle=lab1c_astar', { kind: 'replay', id: 'lab1c_astar' }],
  ['?v=1', v1('view-lab')],
  [`?v=1&bundle=astar_open&s=${SETTINGS}`, v1('view-lab')],
  [`?v=1&bundle=astar_open&e=${EDIT}`, v1('view-lab')],
  ['?bundle=not_a_bundle', v1('view-lab')],
  ['v1/', v1('view-lab')],
];

// the archive's own six views, each opened directly
const ARCHIVE_VIEWS = [
  ['v1/', 'view-lab'], ['v1/?view=localise', 'view-localise'], ['v1/?view=map', 'view-map'],
  ['v1/?view=search', 'view-search'], ['v1/?view=move', 'view-move'], ['v1/?view=live', 'view-live'],
];

const browser = await chromium.launch();
const out = { site: SITE, forms: [], archive_views: [], conditions: null };
let failed = 0;
for (const [form, want] of FORMS) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const row = { form, want, errors };
  try {
    await page.goto(`${SITE}${form}`);
    if (want.kind === 'mission') {
      await page.waitForSelector(`[data-testid="mission"][data-mission="${want.id}"]`, { timeout: 30_000 });
    } else if (want.kind === 'replay') {
      await page.waitForFunction(() => document.querySelector('[data-testid="arena-mode"]')?.dataset.mode === 'recording', null, { timeout: 60_000 });
      if (!page.url().includes(`replay=${want.id}`)) throw new Error(`landed on ${page.url()}`);
    } else if (want.kind === 'arena') {
      await page.waitForSelector('[data-testid="arena"]', { timeout: 60_000 });
    } else if (want.kind === 'live') {
      await page.waitForSelector('[data-testid="nav-arena"]', { timeout: 30_000 });
      row.badge = await page.getByTestId('mode-badge').textContent();
    } else {
      await page.waitForURL((u) => u.pathname.endsWith('/coco-labs/v1/'), { timeout: 30_000 });
      await page.waitForSelector(`[data-testid="${want.pressed}"][aria-pressed="true"]`, { timeout: 60_000 });
      // the query must survive the forward intact
      const q = form.startsWith('v1/') ? form.slice(3) : form;
      if (new URL(page.url()).search !== q) throw new Error(`query ${new URL(page.url()).search} != ${q}`);
    }
    await page.waitForTimeout(2500); // late errors: a v1 share link recomputes in its worker
    row.landed = page.url().replace(SITE, '');
    row.ok = errors.length === 0;
  } catch (e) {
    row.ok = false;
    row.failure = String(e);
    row.landed = page.url().replace(SITE, '');
  }
  if (!row.ok) failed++;
  out.forms.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${form || '(bare)'} -> ${row.landed}${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await page.close();
}
for (const [form, pressed] of ARCHIVE_VIEWS) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const row = { form, pressed, errors };
  try {
    await page.goto(`${SITE}${form}`);
    await page.waitForSelector(`[data-testid="${pressed}"][aria-pressed="true"]`, { timeout: 60_000 });
    await page.waitForTimeout(5000); // the Live view's probe, a lab's worker: late errors
    const text = await page.evaluate(() => document.body.innerText);
    row.real_robot = (text.match(/real robot/gi) ?? []).length;
    row.live_label = await page.getByTestId('view-live').textContent();
    row.ok = errors.length === 0 && row.real_robot === 0 && row.live_label === 'Live Stack (simulated)';
  } catch (e) {
    row.ok = false;
    row.failure = String(e);
  }
  if (!row.ok) failed++;
  out.archive_views.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${form} [${pressed}] real_robot=${row.real_robot} live="${row.live_label}"${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
  await page.close();
}
await browser.close();
out.ok = failed === 0;
writeFileSync(join(OUT, 'v1_links_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ ok: out.ok, forms: FORMS.length, archive_views: ARCHIVE_VIEWS.length, failed }));
process.exit(out.ok ? 0 : 1);
