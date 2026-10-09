// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M0.6 exit check: the honesty copy is on screen, and no "real robot" text
 * is visible, in the Live and Search views, at laptop and phone width.
 *   node tools/perf/copycheck.mjs --site http://127.0.0.1:4173/coco-labs/ --out DIR
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const SITE = arg('site', 'http://127.0.0.1:4173/coco-labs/');
const OUT = arg('out', 'copycheck-out');
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const out = [];
for (const [w, h] of [[1400, 1000], [390, 844]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  for (const view of ['live', 'search', 'plan', 'localise', 'map', 'move']) {
    await page.goto(`${SITE}?view=${view}`);
    await page.waitForLoadState('networkidle');
    if (view === 'search') await page.getByTestId('search-sub-replay').click();
    await page.waitForTimeout(800);
    const text = await page.evaluate('document.body.innerText');
    const overflow = await page.evaluate('document.documentElement.scrollWidth > window.innerWidth');
    const row = {
      view, width: w,
      has_live_stack_simulated: text.includes('Live Stack (simulated)'),
      has_scheduled_demo: /scheduled demo/i.test(text),
      has_full_stack_simulated: text.includes('full ROS 2 stack (simulated)'),
      visible_real_robot: /real robot/i.test(text),
      horizontal_overflow: overflow,
    };
    out.push(row);
    console.log(JSON.stringify(row));
    if (view === 'live' || view === 'search') await page.screenshot({ path: join(OUT, `${view}_${w}.png`) });
  }
  await page.close();
}
await browser.close();
writeFileSync(join(OUT, 'copycheck.json'), `${JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1)}\n`);
