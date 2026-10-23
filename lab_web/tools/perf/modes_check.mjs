// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * One app, three modes (M5.5), in a browser:
 *
 *   node tools/perf/modes_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Play, Compare and Research retain every legacy home. Desktop and both
 * emulated Nothing Phone (1) orientations use the shared harness. Live and
 * the archive are reached from About; no mode loses its evidence label.
 * Nothing scrolls sideways and no page logs a console error.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4214/coco-labs/';
const OUT = args.out ?? 'modes-out';
mkdirSync(OUT, { recursive: true });
const LAUNCH = args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};

const PAGES = [
  ['learn', '?view=learn', 'MODEL'],
  ['learn', '?view=learn&mission=why-did-it-fail&beat=0', 'STACK'],
  ['learn', '?view=learn&mission=find-a-path&beat=0', 'MODEL'],
  ['play', '?view=play', 'MODEL'],
  ['play', '?view=play&c=beat-the-planner&l=bog', 'MODEL'],
  ['play', '?view=play&c=case-file-detective&l=kidnapped', 'STACK'],
  ['play', '?view=arena', 'MODEL'],
  ['learn', '?view=arena&lens=map&level=explain', 'MODEL'],
  ['casefiles', '?view=casefiles', 'STACK'],
  ['casefiles', '?view=casefiles&case=run15', 'STACK'],
  ['casefiles', '?view=arena&casefile=lab5_mislocalised_dwb_1', 'STACK'],
];
const SIZES = { desktop: { viewport: { width: 1440, height: 900 } }, phone_portrait:nothingPhone1(false), phone_landscape:nothingPhone1(true) };

const browser = await chromium.launch(LAUNCH);
const rows = [];
for (const [size, ctx] of Object.entries(SIZES)) {
  for (const [mode, q, evidence] of PAGES) {
    const context = await browser.newContext(ctx);
    const page = await context.newPage();
    if (size.startsWith('phone')) await throttlePhone(context, page);
    const errors = [];
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('pageerror', (e) => errors.push(String(e)));
    const row = { size, device:size.startsWith('phone') ? DEVICE_NAME : 'laptop Chromium', mode, page:q, evidence, errors };
    try {
      await page.goto(`${SITE}${q}`);
      await page.getByTestId('mode-head').waitFor({ timeout: 60_000 });
      await page.waitForTimeout(2500);
      Object.assign(row, await page.evaluate(() => {
        const head = document.querySelector('[data-testid=mode-head]');
        const badge = document.querySelector('[data-testid=evidence-badge]');
        const b = badge?.getBoundingClientRect();
        return {
          modes: [...head.querySelectorAll('nav.modes a')].map((a) => a.textContent),
          current: head.querySelector('nav.modes a[aria-current=page]')?.textContent ?? null,
          badge: badge?.textContent ?? null,
          badge_visible: !!b && b.width > 0 && b.height > 0 && b.left >= 0 && b.right <= window.innerWidth,
          live_link: !!head.querySelector('[data-testid=live-link]'),
          live_is_a_mode: [...head.querySelectorAll('nav.modes a')].some((a) => /live/i.test(a.textContent)),
          scroll: document.documentElement.scrollWidth, view: window.innerWidth,
        };
      }));
      if (size.startsWith('phone')) await page.screenshot({ path: join(OUT, `${size}_${mode}_${rows.length}.png`), scale:'css' });
      const want = { learn: 'Compare', play: 'Play', sandbox: 'Play', casefiles: 'Research' }[mode];
      row.ok = errors.length === 0 && row.modes.join('|') === 'Play|Compare|Research' && row.current === want
        && row.badge === (evidence === 'MODEL' ? 'MODEL · kinematic' : evidence) && row.badge_visible && !row.live_link && !row.live_is_a_mode && row.scroll <= row.view;
    } catch (e) { row.ok = false; row.failure = String(e); }
    rows.push(row);
    console.log(`${row.ok ? 'ok  ' : 'FAIL'} ${size} ${mode} ${q || '(bare)'}: current ${row.current}, badge ${row.badge}${row.badge_visible ? '' : ' (not visible)'}, scroll ${row.scroll}/${row.view}${row.failure ? ' ' + row.failure : ''}${errors.length ? ' errors: ' + errors.join(' | ') : ''}`);
    await context.close();
  }
}
// the Case Files comparison: one header on the page; each pane shows only its badge
{
  const context = await browser.newContext(SIZES.desktop);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const q = '?view=casefiles&case=run15&file=lab5_mislocalised_dwb_1';
  await page.goto(`${SITE}${q}`);
  await page.waitForTimeout(8000);
  const panes = [];
  for (const f of page.frames().filter((x) => x !== page.mainFrame())) {
    panes.push(await f.evaluate(() => ({ heads: document.querySelectorAll('[data-testid=mode-head]').length,
      badge: document.querySelector('[data-testid=evidence-badge]')?.textContent ?? null })));
  }
  const heads = await page.locator('[data-testid=mode-head]').count();
  const row = { size: 'desktop', mode: 'casefiles', page: `${q} (panes)`, heads, panes, errors,
    ok: heads === 1 && panes.length === 2 && panes.every((p) => p.heads === 0) && panes.map((p) => p.badge).sort().join() === 'MODEL · kinematic,STACK' && !errors.length };
  rows.push(row);
  console.log(`${row.ok ? 'ok  ' : 'FAIL'} comparison: ${heads} header on the page, panes ${JSON.stringify(panes)}`);
  await context.close();
}
await browser.close();
const out = { site: SITE, rows, summary: { pages: rows.length, ok: rows.filter((r) => r.ok).length } };
writeFileSync(join(OUT, 'modes_check.json'), JSON.stringify({ ...out, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(out.summary));
process.exit(out.summary.ok === rows.length ? 0 : 1);
