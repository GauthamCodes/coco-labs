// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.9: the Studio's timings on a named device -- one run of the A* starter (its validation
 * report's per-call time) and "Benchmark it": the starter against the built-in A* on all of
 * arena-nav-50 (every user run twice for the determinism check), in the page's own sandboxes.
 *
 *   node tools/r2/perf_studio.mjs SITE OUT.json --case laptop|phone [--cdp http://127.0.0.1:9222]
 *
 * laptop: 1440 x 900, the real GPU (G1_GPU) and CPU; phone: the emulated Nothing Phone (1)
 * (viewport, touch, 4x CPU throttle; labelled emulated), or the real phone over CDP.
 * Timed from pressing the button to the statistics being shown. Wall time on this device,
 * never a ranking metric.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { conditions } from '../perf/conditions.mjs';
import { GPU, launchOptions, machine, renderer } from '../g1/gpu.mjs';
import { nothingPhone1, throttlePhone } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : d; };
const which = opt('--case', 'laptop'), cdp = opt('--cdp', null);
const browser = cdp ? await chromium.connectOverCDP(cdp) : await chromium.launch(launchOptions());
const ctx = cdp ? browser.contexts()[0] : await browser.newContext({ ...(which === 'phone' ? nothingPhone1(true) : { viewport: { width: 1440, height: 900 } }), serviceWorkers: 'block' });
const page = await ctx.newPage();
if (which === 'phone' && !cdp) await throttlePhone(ctx, page);
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
const report = { site, case: which, device: cdp ? 'real phone over CDP' : which === 'phone' ? 'emulated Nothing Phone (1): viewport, touch, 4x CPU throttle on this laptop' : 'laptop',
  gpu: GPU, machine: machine(), conditions: conditions(), when: new Date().toISOString() };
try {
  await page.goto(`${site}?view=workbench&tab=studio`);
  await page.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 120000 });
  report.renderer = await renderer(page).catch(() => null);
  report.page = await page.evaluate(() => ({ cores: navigator.hardwareConcurrency, memory_gb: navigator.deviceMemory ?? null }));
  // one run (the sandbox boots on the first)
  let t0 = Date.now();
  await page.locator('[data-testid=studio-run]').click();
  // done when the status cell no longer says running (as studio_check.mjs waits)
  await page.waitForFunction(() => { const e = document.querySelector('[data-testid=studio-status-0]'); return e && e.textContent && !/running/.test(e.textContent); }, null, { timeout: 600000 });
  report.one_run = { wall_s: (Date.now() - t0) / 1000, status: await page.locator('[data-testid=studio-status-0]').innerText() };
  await page.getByRole('tab', { name: 'Validation' }).click();
  report.one_run.validation = await page.locator('[data-testid=studio-validation]').innerText();
  // Benchmark it: the starter against the built-in A* on the whole suite
  await page.locator('.studio-exp summary', { hasText: 'Benchmark it' }).click();
  const astar = page.locator('.studio-rivals label', { hasText: /^\s*A\*\s*$/ }).locator('input');
  if (await astar.count()) await astar.first().check(); else await page.locator('.studio-rivals input').first().check();
  report.benchmark = { button: await page.locator('[data-testid=studio-experiment]').innerText() };
  t0 = Date.now();
  await page.locator('[data-testid=studio-experiment]').click();
  await page.locator('.studio-exp [data-testid=wb-summary]').waitFor({ timeout: 7200000 });
  report.benchmark.wall_s = (Date.now() - t0) / 1000;
  report.benchmark.heading = await page.locator('.studio-exp .wb-results h2').innerText();
  report.benchmark.summary = await page.locator('.studio-exp [data-testid=wb-summary]').innerText();
} catch (e) { report.error = String(e); }
report.errors = errors;
report.conditions_end = conditions();
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(JSON.stringify({ case: which, one_run_s: report.one_run?.wall_s, benchmark_s: report.benchmark?.wall_s, heading: report.benchmark?.heading, error: report.error }));
await (cdp ? page.close() : browser.close());
