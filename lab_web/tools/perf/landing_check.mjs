// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The landing page (M1.10): the site's bare URL opens the Arena; every v1
 * link -- a named view, a v1 share link (`?bundle=`, `?v=`) -- still opens v1
 * exactly as before; the Arena's "v1 labs" link reaches v1. 0 console errors.
 *
 *   node tools/perf/landing_check.mjs --site URL --out DIR
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
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const OUT = args.out ?? 'landing-out';
mkdirSync(OUT, { recursive: true });

// [query, expected app]. Every v1 URL form (M1 review, 2026-10-09: the M1.10
// version covered plan, exhibit, live and move only, and called its 9 cases
// "9 v1 links" although 3 of them are Arena URLs).
const CASES = [
  ['', 'arena'], ['?perf', 'arena'], ['?view=arena', 'arena'], ['?view=arena&replay=lab1c_astar', 'arena'],
  ['?view=plan', 'v1'], ['?view=live', 'v1'], ['?view=localise', 'v1'], ['?view=map', 'v1'],
  ['?view=search', 'v1'], ['?view=move', 'v1'], ['?view=exhibit', 'v1'],
  ['?bundle=astar_open', 'v1'], ['?bundle=astar_open&v=1', 'v1'], ['?v=1', 'v1'],
];

const browser = await chromium.launch();
const out = { site: SITE, cases: [], errors: [] };
try {
  for (const [query, want] of CASES) {
    const page = await browser.newPage();
    const errs = [];
    page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('pageerror', (e) => errs.push(String(e)));
    await page.goto(`${SITE}${query}`);
    await page.waitForFunction(() => !!document.querySelector('#root')?.firstElementChild, null, { timeout: 60_000 });
    await page.waitForTimeout(1500);
    const got = await page.evaluate(() => (document.querySelector('[data-testid=arena]') ? 'arena' : 'v1'));
    let link = null;
    if (got === 'arena' && query === '') {
      await page.getByTestId('v1-labs-link').click();
      await page.waitForTimeout(1500);
      link = await page.evaluate(() => (document.querySelector('[data-testid=arena]') ? 'arena' : 'v1'));
    }
    const pass = got === want && (link === null || link === 'v1') && errs.length === 0;
    out.cases.push({ query: query || '(bare)', want, got, v1_link_opens: link, errors: errs, pass });
    out.errors.push(...errs);
    console.log(`${pass ? 'PASS' : 'FAIL'} ${query || '(bare)'} -> ${got}${link ? ` (v1 labs link -> ${link})` : ''}`);
    await page.close();
  }
} finally {
  await browser.close();
}
out.pass = out.cases.every((c) => c.pass);
writeFileSync(join(OUT, 'landing_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, errors: out.errors.length }));
process.exit(out.pass ? 0 : 1);
