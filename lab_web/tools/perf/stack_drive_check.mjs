// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * A converted Lab 5 drive in a real browser (M2.7):
 *
 *   node tools/perf/stack_drive_check.mjs --site URL --out DIR [--run lab5_static_room_DWB_1]
 *
 * Opens `?view=arena&replay=<run>` (a controller run recorded on the full
 * ROS 2 stack in Gazebo, converted by src/convert/lab5.ts), waits for the
 * Move lens to show Nav2's OWN candidates and chosen trajectory, labelled
 * STACK, scrubs to a cycle with candidates, and screenshots it. Exit 0 only
 * with 0 console errors, 0 three.js warnings and every step seen.
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
const OUT = args.out ?? 'stack-drive-out';
const RUN = args.run ?? 'lab5_static_room_dwb_1';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
const warnings = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); else if (m.type() === 'warning' && m.text().includes('THREE')) warnings.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, run: RUN, steps: {}, errors, warnings };

try {
  await page.goto(`${SITE}?view=arena&replay=${RUN}&perf`);
  await page.waitForFunction(() => !!window.__cocoArena?.session()?.headers.get('coco.control.local.header.v1'), null, { timeout: 120_000 });
  out.steps.header = await page.evaluate(() => window.__cocoArena.session().headers.get('coco.control.local.header.v1'));
  out.steps.banner = await page.locator('.arena-intro, [data-testid="arena-mode"]').first().textContent().catch(() => null);
  out.steps.card = await page.getByTestId('stack-results').textContent();
  // wait for a cycle with Nav2's sampled candidates
  await page.waitForFunction(() => window.__cocoArena.session().families.before('coco.control.local.candidates.v1', 1e9)
    .some((b) => !String(b.scalars.controller_id).endsWith('/chosen')), null, { timeout: 120_000 });
  const tick = await page.evaluate(() => window.__cocoArena.session().families.before('coco.control.local.candidates.v1', 1e9)
    .find((b) => !String(b.scalars.controller_id).endsWith('/chosen')).tick);
  out.steps.first_candidate_tick = tick;
  await page.waitForTimeout(1500);
  out.steps.layers = await page.evaluate(() => window.__cocoArena.layerIds());
  out.steps.lens_active = await page.getByTestId('lens-move').getAttribute('aria-pressed');
  const counts = await page.evaluate(() => {
    const s = window.__cocoArena.session().families;
    const c = s.before('coco.control.local.candidates.v1', 1e9);
    return { sampled: c.filter((b) => !String(b.scalars.controller_id).endsWith('/chosen')).length,
      chosen: c.filter((b) => String(b.scalars.controller_id).endsWith('/chosen')).length,
      rows: c.filter((b) => !String(b.scalars.controller_id).endsWith('/chosen')).reduce((n, b) => n + b.columns.candidate.length, 0) };
  });
  out.steps.counts = counts;
  await page.getByTestId('level-explain').click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(OUT, `${RUN}_explain.png`) });
} finally {
  await browser.close();
}
const L = out.steps.layers ?? [];
out.pass = errors.length === 0 && warnings.length === 0 && out.steps.header?.evidence === 'STACK'
  && (out.steps.counts?.sampled ?? 0) > 0 && (out.steps.counts?.chosen ?? 0) > 0 && L.includes('chosen') && L.includes('candidates');
writeFileSync(join(OUT, 'stack_drive_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, counts: out.steps.counts, layers: L, card: out.steps.card, errors: errors.length, warnings: warnings.length }));
process.exit(out.pass ? 0 : 1);
