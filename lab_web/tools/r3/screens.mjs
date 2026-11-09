// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R3.9: screenshots of what R3 changed, for Gautham's look review (a soft gate), and the checks a
 * reviewer would make by eye: the Leaderboard's control/localisation boards and Contacts column, the
 * Model vs ROS 2 tab, About's Cite and "Reproduce this paper". Desktop 1440x1000 and the emulated
 * Nothing Phone (1) in both orientations (never the real phone).
 *
 *   node tools/r3/screens.mjs SITE OUT_DIR
 *
 * Writes OUT_DIR/*.png and OUT_DIR/screens.json; exit 1 when a check fails.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out] = process.argv.slice(2);
if (!site || !out) { console.error('usage: screens.mjs SITE OUT_DIR'); process.exit(2); }
mkdirSync(out, { recursive: true });
const report = { site, steps: [] };
const step = (name, ok, detail = {}) => { report.steps.push({ name, ok: !!ok, ...detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const PAGES = [
  ['leaderboard', '?view=workbench&tab=leaderboard', '[data-testid="leaderboard"] h2'],
  ['model-vs-ros2', '?view=workbench&tab=gap', '[data-testid="model-vs-ros2"] h2, [data-testid="gap-pending"]'],
  ['about', '?view=about', '[data-testid="reproduce-paper"]'],
];
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
try {
  const desk = await browser.newContext({ viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block' });
  const page = await desk.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  for (const [name, q, sel] of PAGES) {
    await page.goto(site + q, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector(sel, { timeout: 120000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(out, `desktop-${name}.png`), fullPage: true });
    if (name === 'leaderboard') {
      const boards = await page.$$eval('[data-testid="leaderboard"] h2', (hs) => hs.map((h) => h.textContent));
      const contacts = await page.$$eval('th', (ths) => ths.filter((t) => /Contacts/.test(t.textContent)).length);
      const tiers = await page.$$('[data-testid="lb-tiers"]');
      const submit = await page.$('[data-testid="lb-submit"]');
      step('leaderboard: control and localisation boards shown', boards.some((b) => /control/i.test(b)) && boards.some((b) => /locali/i.test(b)), { boards });
      step('leaderboard: a Contacts column on every control board', contacts >= 1 && contacts === boards.filter((b) => /control/i.test(b)).length, { contacts });
      step('leaderboard: tiers and the Submit guide present', tiers.length > 0 && !!submit, { tiers: tiers.length });
    }
    if (name === 'model-vs-ros2') {
      const pending = await page.$('[data-testid="gap-pending"]');
      const tables = await page.$$('[data-testid="model-vs-ros2"] table');
      step('model vs ROS 2: paired tables shown (not the pending note)', !pending && tables.length > 0, { tables: tables.length });
    }
    if (name === 'about') {
      const href = await page.getAttribute('[data-testid="reproduce-paper"]', 'href');
      step('about: the Reproduce link is a same-site experiment link', /^\/coco-labs\/\?/.test(href ?? ''), { href });
    }
  }
  step('desktop: no page errors', errors.length === 0, { errors });
  for (const landscape of [true, false]) {
    const tag = landscape ? 'phone-landscape' : 'phone-portrait';
    const pc = await browser.newContext({ ...nothingPhone1(landscape), serviceWorkers: 'block' });
    const p = await pc.newPage();
    for (const [name, q, sel] of PAGES) {
      await p.goto(site + q, { waitUntil: 'domcontentloaded' });
      await p.waitForSelector(sel, { timeout: 120000 });
      await p.waitForTimeout(1500);
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      step(`${tag} (emulated) ${name}: no sideways page scroll`, overflow <= 1, { overflow });
      await p.screenshot({ path: join(out, `${tag}-${name}.png`) });
    }
    await pc.close();
  }
} finally {
  await browser.close();
  report.passed = report.steps.every((s) => s.ok);
  writeFileSync(join(out, 'screens.json'), JSON.stringify(report, null, 1) + '\n');
}
console.log(report.passed ? 'R3 SCREENS PASS' : 'R3 SCREENS FAIL');
process.exit(report.passed ? 0 : 1);
