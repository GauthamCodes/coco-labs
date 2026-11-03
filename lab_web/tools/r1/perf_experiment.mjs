// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.8: an experiment's wall time in the Workbench, on this laptop or (emulated / real) phone.
 *
 *   node tools/r1/perf_experiment.mjs SITE OUT.json --case laptop|phone [--cdp http://127.0.0.1:9222]
 *
 * laptop: 4 planners (A*, Dijkstra, greedy, weighted A*) x depot-nav-100 = 400 runs, the
 *         page's own worker pool, real GPU (G1_GPU) and CPU.
 * phone:  2 planners x 20 seeded Proving Ground pairs = 40 runs; on the emulated Nothing Phone
 *         (1) (viewport, touch, 4x CPU throttle; labelled emulated), or the real phone over
 *         CDP when --cdp is given (Chrome on the device; adb forward tcp:9222).
 * Timed from pressing Run to the digest being shown (statistics included); the digest is
 * recorded too, so the counts can be checked against a native run of the same spec.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { conditions } from '../perf/conditions.mjs';
import { GPU, launchOptions, machine, renderer } from '../g1/gpu.mjs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : d; };
const which = opt('--case', 'laptop'), cdp = opt('--cdp', null);
const SPECS = {
  laptop: { schema: 'coco.experiment.v1', title: 'R1.8: four planners on depot-nav-100', world: 'coco_depot_v1', family: 'planning', seed: 1,
    algorithms: [{ name: 'astar' }, { name: 'dijkstra' }, { name: 'greedy' }, { name: 'weighted_astar' }], scenarios: { kind: 'suite', id: 'depot-nav-100' } },
  phone: { schema: 'coco.experiment.v1', title: 'R1.8: two planners, 20 pairs', world: 'coco_arena_v1', family: 'planning', seed: 1,
    algorithms: [{ name: 'astar' }, { name: 'dijkstra' }], scenarios: { kind: 'sampled', n: 20, seed: 8, min_separation_m: 3 } },
};
const spec = SPECS[which];
const browser = cdp ? await chromium.connectOverCDP(cdp) : await chromium.launch(launchOptions());
const ctx = cdp ? browser.contexts()[0] : await browser.newContext({ ...(which === 'phone' ? nothingPhone1(true) : { viewport: { width: 1440, height: 900 } }), serviceWorkers: 'block' });
const page = await ctx.newPage();
if (which === 'phone' && !cdp) await throttlePhone(ctx, page);
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
const report = { site, case: which, device: cdp ? 'real phone over CDP' : which === 'phone' ? 'emulated Nothing Phone (1): viewport, touch, 4x CPU throttle on this laptop' : 'laptop',
  gpu: GPU, machine: machine(), conditions: conditions(), when: new Date().toISOString(), spec };
try {
  await page.goto(`${site}?view=workbench`);
  report.renderer = await renderer(page).catch(() => null);
  report.page = await page.evaluate(() => ({ cores: navigator.hardwareConcurrency, memory_gb: navigator.deviceMemory ?? null, ua: navigator.userAgent }));
  await page.locator('.wb-text summary').click();
  await page.locator('.wb-text textarea').fill(JSON.stringify(spec));
  await page.getByRole('button', { name: 'Apply the text' }).click();
  const t0 = Date.now();
  await page.locator('.wb-runbar button[type=submit]').click();
  await page.locator('[data-testid="wb-digest"]').waitFor({ timeout: 3600000 });
  report.wall_s = (Date.now() - t0) / 1000;
  const d = await page.locator('[data-testid="wb-digest"]').innerText();
  report.digest_prefix = d.split(' ')[1]; report.workers = Number(/(\d+) worker/.exec(d)?.[1]);
  report.runs = (await page.locator('[data-testid="wb-runs"] caption').count()) ? Number(/of (\d+) runs/.exec(await page.locator('.wb-results h2').innerText())?.[1]) : null;
} catch (e) { report.error = String(e); }
report.errors = errors;
report.conditions_end = conditions();
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ case: which, wall_s: report.wall_s, workers: report.workers, digest: report.digest_prefix, error: report.error }));
await (cdp ? page.close() : browser.close());
