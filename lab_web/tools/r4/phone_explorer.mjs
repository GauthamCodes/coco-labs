// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4.6: the Explorer track on the EMULATED Nothing Phone (1) in landscape (viewport, DPR, touch, UA,
 * 4x CPU throttle; never the real phone): one Explorer lesson played end to end by taps -- predict,
 * observe, explain, try (the tune exercise, graded in the phone's sandbox), check, In real ROS 2 --
 * with no sideways scroll on any step. Records the time the first check took (it boots Python).
 *
 *   node tools/r4/phone_explorer.mjs SITE OUT.json
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { nothingPhone1, throttlePhone, DEVICE_NAME } from '../phone/nothing-phone-1.mjs';

const [site, out] = process.argv.slice(2);
const report = { site, device: `${DEVICE_NAME}, landscape, 4x CPU throttle (EMULATED)`, steps: [] };
const step = (name, ok, detail = {}) => { report.steps.push({ name, ok: !!ok, ...detail }); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });
try {
  const ctx = await browser.newContext({ ...nothingPhone1(true), serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await throttlePhone(ctx, page);
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
  const sideways = () => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  await page.goto(site + '?view=learn&track=explorer', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="lesson-astar-vs-dijkstra"]', { timeout: 120000 });
  step('home: the Explorer track lists the lesson', true, { sideways: await sideways() });
  await page.tap('[data-testid="lesson-astar-vs-dijkstra"]');
  await page.waitForSelector('[data-testid="option-2"]', { timeout: 60000 });
  await page.tap('[data-testid="option-2"]');
  const verdict = await page.textContent('[data-testid="verdict"]');
  step('predict: tap an answer, see the verdict', /Yes/.test(verdict ?? ''), { sideways: await sideways() });
  const seen = {};
  for (const s of ['observe', 'explain', 'try']) {
    await page.tap('[data-testid="next"]');
    await page.waitForSelector(`[data-testid="lesson-step"][data-step="${s}"]`, { timeout: 30000 });
    seen[s] = !(await sideways());
  }
  step('observe, explain, try: reached by taps, none scrolls sideways', Object.values(seen).every(Boolean), { seen });
  const slider = page.locator('[data-testid="slider-heuristic_weight"]');
  await slider.focus();
  for (let i = 0; i < 20; i++) await page.keyboard.press('ArrowRight');   // 1.0 -> 3.0
  const shown = await page.textContent('[data-testid="value-heuristic_weight"]');
  const t0 = Date.now();
  await page.tap('[data-testid="check"]');
  await page.waitForSelector('[data-testid="check-result"] [data-testid="verdict"]', { timeout: 15 * 60000 });
  const seconds = Math.round((Date.now() - t0) / 1000);
  const passed = await page.getAttribute('[data-testid="check-result"] [data-testid="verdict"]', 'data-passed');
  step('try: the tune exercise graded on the phone (first check boots Python)', passed === 'true', { weight: shown, seconds, sideways: await sideways() });
  await page.tap('[data-testid="next"]');
  await page.waitForSelector('[data-testid="lesson-step"][data-step="ros2"]', { timeout: 30000 });
  step('In real ROS 2: reached, no sideways scroll', !(await sideways()));
  step('no page errors', errors.length === 0, { errors });
} catch (e) {
  step('ran to the end', false, { error: String(e).slice(0, 300) });
} finally {
  await browser.close();
  report.finished = new Date().toISOString();
  writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
}
process.exit(report.steps.every((s) => s.ok) ? 0 : 1);
