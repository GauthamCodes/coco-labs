// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: screenshots for Gautham's look review (a soft gate): a named page set at desktop 1440x1000 and
 * the EMULATED Nothing Phone (1) in both orientations (never the real phone). Records page errors
 * and whether the page scrolls sideways (a phone-layout regression a screenshot can hide).
 *
 *   node tools/r4/screens.mjs SITE OUT_DIR SET      SET: before | course | lesson | teacher | all
 *
 * Writes OUT_DIR/<device>-<page>.png and OUT_DIR/screens.json; exit 1 on a page error or a
 * missing selector.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, set = 'before'] = process.argv.slice(2);
if (!site || !out) { console.error('usage: screens.mjs SITE OUT_DIR SET'); process.exit(2); }
mkdirSync(out, { recursive: true });
const SETS = {
  before: [
    ['learn', '?view=learn', '[data-testid="learn-page"] h1, [data-testid="course"]'],
    ['tours', '?view=compare&tour=', '[data-testid="mission-list"]'],
    ['tour-1-predict', '?view=compare&tour=find-a-path&beat=1', '[data-testid="beat"]'],
  ],
  course: [
    ['learn', '?view=learn', '[data-testid="course"]'],
    ['module-1', '?view=learn&module=find-a-path', '[data-testid="course-module"]'],
    ['module-2', '?view=learn&module=costmaps', '[data-testid="course-module"]'],
    ['glossary', '?view=learn&page=glossary', '[data-testid="glossary"]'],
  ],
  lesson: [
    ['lesson-predict', '?view=learn&lesson=astar-vs-dijkstra&step=predict', '[data-testid="lesson-step"]'],
    ['lesson-explain', '?view=learn&lesson=astar-vs-dijkstra&step=explain', '[data-testid="lesson-step"]'],
    ['lesson-try-code', '?view=learn&lesson=write-the-heuristic&step=try', '[data-testid="lesson-step"]'],
    ['lesson-ros2', '?view=learn&lesson=astar-vs-dijkstra&step=ros2', '[data-testid="lesson-step"]'],
  ],
  teacher: [
    ['teacher', '?view=learn&page=teacher', '[data-testid="teacher"]'],
    ['progress', '?view=learn&page=progress', '[data-testid="progress"]'],
  ],
};
SETS.all = [...SETS.course, ...SETS.lesson, ...SETS.teacher];
const pages = SETS[set];
if (!pages) { console.error(`unknown set ${set}`); process.exit(2); }

const report = { site, set, device_note: 'desktop 1440x1000; phone = EMULATED Nothing Phone (1) (viewport, DPR 2.625, touch, UA)', shots: [] };
let failed = false;
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
try {
  const devices = [
    ['desktop', { viewport: { width: 1440, height: 1000 } }],
    ['phone-landscape', nothingPhone1(true)],
    ['phone-portrait', nothingPhone1(false)],
  ];
  for (const [dev, opts] of devices) {
    const ctx = await browser.newContext({ ...opts, serviceWorkers: 'block' });
    for (const [name, q, sel] of pages) {
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
      let ok = true;
      try {
        await page.goto(site + q, { waitUntil: 'domcontentloaded' });
        await page.waitForSelector(sel, { timeout: 60000 });
        await page.waitForTimeout(1200);
      } catch (e) { ok = false; errors.push(String(e).slice(0, 300)); }
      const file = `${dev}-${name}.png`;
      await page.screenshot({ path: join(out, file), fullPage: true });
      const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
      if (!ok || errors.length) failed = true;
      report.shots.push({ device: dev, page: name, query: q, file, ok, sideways_scroll: sideways, errors });
      console.log(`${ok && !errors.length ? 'OK  ' : 'FAIL'} ${file}${sideways ? ' (scrolls sideways)' : ''}`);
      await page.close();
    }
    await ctx.close();
  }
} finally {
  await browser.close();
  report.taken = new Date().toISOString();
  writeFileSync(join(out, 'screens.json'), JSON.stringify(report, null, 1) + '\n');
}
process.exit(failed ? 1 : 0);
