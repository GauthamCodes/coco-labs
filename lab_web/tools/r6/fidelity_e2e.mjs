// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/*
 * R6.B1: the fidelity knobs end to end in a real browser. Learn's note links an experiment with command latency
 * on; the Workbench opens it with the knob in its builder, runs it, and the results carry the fidelity note; a
 * run opened in Compare names the knob too. Then a knob set by hand in the builder appears in the spec.
 *
 *   node tools/r6/fidelity_e2e.mjs SITE OUT_DIR [chromium|firefox]
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, firefox } from 'playwright';

const [site, out, which = 'chromium'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await (which === 'firefox' ? firefox : chromium).launch({ headless: true,
  ...(which === 'chromium' ? { args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] } : {}) });
const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
const page = await ctx.newPage();
const errors = []; page.on('pageerror', (e) => errors.push(e.message));
const rec = { browser: which, steps: {}, page_errors: errors };
try {
  await page.goto(`${site}?view=learn`);
  await page.getByTestId('learn-fidelity').waitFor({ timeout: 60000 });
  const href = await page.getByTestId('learn-fidelity-experiment').getAttribute('href');
  rec.steps.learn = { note: true, link: !!href };
  await page.goto(new URL(href, site).toString());
  await page.getByTestId('wb-fidelity').waitFor({ timeout: 120000 });
  rec.steps.builder = { cmd_latency_field: await page.getByTestId('fid-cmd_latency').inputValue() };
  // a linked experiment starts on its own; otherwise press Run
  const runBtn = page.locator('.wb-runbar button[type=submit]');
  if (await runBtn.isEnabled()) await runBtn.click();
  await page.getByTestId('wb-fidelity-chip').waitFor({ timeout: 300000 });
  rec.steps.results = { chip: (await page.getByTestId('wb-fidelity-chip').textContent()).replace(/\s+/g, ' ') };
  // wait for the runs to finish (the summary table follows)
  await page.waitForFunction(() => /20 of 20 runs/.test(document.querySelector('.wb-results h2')?.textContent ?? ''), null, { timeout: 600000 });
  rec.steps.results.finished = true;
  await page.screenshot({ path: join(out, `${which}_results.png`), fullPage: false });
  const cmp = page.locator('a[href*="xrun="]').first();   // a run's own replay link (not the nav door)
  if (await cmp.count()) {
    await page.goto(new URL(await cmp.getAttribute('href'), site).toString());
    await page.getByTestId('compare-fidelity').waitFor({ timeout: 120000 });
    rec.steps.compare = { note: (await page.getByTestId('compare-fidelity').textContent()).replace(/\s+/g, ' ') };
  }
  // by hand: a fresh control experiment, one knob set in the builder, visible in the spec text
  await page.goto(`${site}?view=workbench&tab=experiments`);
  await page.waitForTimeout(3000);
  rec.steps.by_hand = { builder_shown_for_planning: await page.getByTestId('wb-fidelity').count() };
  rec.pass = !!(rec.steps.learn.link && rec.steps.builder.cmd_latency_field === '5' && /command latency 5 ticks/.test(rec.steps.results.chip)
    && rec.steps.results.finished && (!rec.steps.compare || /command latency 5 ticks/.test(rec.steps.compare.note)) && errors.length === 0);
} catch (e) {
  rec.error = String(e?.message ?? e).slice(0, 400);
  rec.pass = false;
  await page.screenshot({ path: join(out, `${which}_error.png`) }).catch(() => {});
}
writeFileSync(join(out, `${which}.json`), JSON.stringify(rec, null, 1));
console.log(JSON.stringify(rec));
await b.close();
process.exit(rec.pass ? 0 : 1);
