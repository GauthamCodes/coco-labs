// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Localise lens in a real browser (M2.3):
 *
 *   node tools/perf/localise_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Takes over the live model with a goal, selects the Localise lens (its
 * pack loads; MCL and the EKF switch on through config inputs), waits for
 * particle sets, estimates and error metrics to arrive, screenshots Watch
 * and Inspect, then DRAGS the robot to kidnap it and records MCL's error
 * before and after -- all read from what the model emitted. Exit 0 only
 * with 0 console errors and every step seen.
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
const OUT = args.out ?? 'localise-out';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, steps: {}, errors };

const toScreen = (x, y) => page.evaluate(([x, y]) => {
  const r = window.__cocoArena.renderer;
  const b = r.canvas.getBoundingClientRect();
  const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
  const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
  return [cx + (x - p0[0]) / ((px[0] - p0[0]) / 100), cy + (y - p0[1]) / ((py[1] - p0[1]) / 100)];
}, [x, y]);
const series = (name) => page.evaluate((n) => window.__cocoArena.session().families.series(n, 1e9), name);

try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  const [gx, gy] = await toScreen(6.0, 4.0);
  await page.mouse.click(gx, gy);
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live', null, { timeout: 30_000 });
  await page.getByTestId('lens-localise').click();
  await page.waitForFunction(() => window.__cocoArena.session()?.families.channels().includes('coco.localise.particles.set.v1'), null, { timeout: 60_000 });
  out.steps.channels = await page.evaluate(() => window.__cocoArena.session().families.channels().sort());
  out.steps.controls = await page.getByTestId('localise-controls').isVisible();
  await page.waitForTimeout(4000);
  await page.screenshot({ path: join(OUT, 'localise_watch.png') });
  const before = (await series('err_xy.mcl')).at(-1);
  out.steps.err_before_kidnap = before;
  // drag the robot (its true pose) about 4 m away
  const truth = await page.evaluate(() => { const t = window.__cocoArena.last; return t.truth ?? t.pose; });
  const [sx, sy] = await toScreen(truth[0], truth[1]);
  const [tx, ty] = await toScreen(2.5, -2.0);
  await page.mouse.move(sx, sy);
  await page.mouse.down();
  await page.mouse.move((sx + tx) / 2, (sy + ty) / 2, { steps: 5 });
  await page.mouse.move(tx, ty, { steps: 5 });
  await page.mouse.up();
  await page.waitForFunction(() => window.__cocoArena.log().some((r) => r.kind === 'kidnap'), null, { timeout: 10_000 });
  out.steps.kidnap_logged = await page.evaluate(() => window.__cocoArena.log().filter((r) => r.kind === 'kidnap'));
  // the robot keeps driving on its (now wrong) belief; the filter updates as odometry moves
  await page.waitForFunction((n) => (window.__cocoArena.session().families.series('err_xy.mcl', 1e9).length > n + 2), (await series('err_xy.mcl')).length, { timeout: 60_000 }).catch(() => {});
  const after = (await series('err_xy.mcl')).at(-1);
  out.steps.err_after_kidnap = after;
  out.steps.truth_after = await page.evaluate(() => window.__cocoArena.last.truth ?? null);
  out.steps.belief_after = await page.evaluate(() => window.__cocoArena.last.pose);
  await page.getByTestId('level-inspect').click();
  await page.waitForTimeout(800);
  out.steps.inspector = await page.evaluate(() => document.querySelector('[data-testid="lens-inspector"]')?.textContent?.slice(0, 400) ?? null);
  await page.screenshot({ path: join(OUT, 'localise_inspect_after_kidnap.png'), fullPage: true });
} finally {
  await browser.close();
}
out.steps.kidnap_landed_m = out.steps.kidnap_logged?.length ? Math.hypot(out.steps.kidnap_logged[0].x - 2.5, out.steps.kidnap_logged[0].y + 2.0) : null;
out.pass = errors.length === 0 && !!out.steps.err_after_kidnap && out.steps.kidnap_logged?.length === 1 && out.steps.kidnap_landed_m < 0.3
  && out.steps.channels?.includes('coco.estimate.pose.v1') && out.steps.channels?.includes('coco.localise.ekf.update.v1');
writeFileSync(join(OUT, 'localise_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, before: out.steps.err_before_kidnap, after: out.steps.err_after_kidnap, errors: errors.length }));
process.exit(out.pass ? 0 : 1);
