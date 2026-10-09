// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The timeline in a real browser (M1.7): give a goal, let the robot drive,
 * then scrub the world track back, scrub the computation track, step, pause
 * and rejoin live -- timing each seek as the page sees it (the M1
 * responsiveness criterion: seek < 100 ms), with screenshots.
 *
 *   node tools/perf/timeline_check.mjs --site URL --out DIR [--planner dijkstra]
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
const OUT = args.out ?? 'timeline-out';
const PLANNER = args.planner ?? 'dijkstra';
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, planner: PLANNER, errors };
try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await page.getByTestId(`planner-${PLANNER}`).click();
  await page.waitForTimeout(300);
  await page.evaluate(() => window.__cocoArena.goal(6.0, 4.0));
  await page.waitForFunction(() => { const s = window.__cocoArena.session(); const st = s?.shownSearch; return !!st && st.final; }, null, { timeout: 60_000 });
  await page.waitForTimeout(8000); // drive for a while
  out.events = await page.evaluate(() => window.__cocoArena.session().shownSearch.received);
  out.head_before = await page.evaluate(() => window.__cocoArena.session().head);
  await page.screenshot({ path: join(OUT, 'live.png') });
  // world track: back to the tick after planning; the search there is complete
  const seekWorld = await page.evaluate(() => {
    const s = window.__cocoArena.session();
    s.playing = false;
    const t0 = performance.now();
    s.seekTick(15);
    return { ms: performance.now() - t0, shown: s.shownTick.tick, pose: s.shownTick.pose, live: s.live };
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, 'world_tick15.png') });
  // computation track: seeks across the whole search, timed
  const seeks = await page.evaluate(() => {
    const s = window.__cocoArena.session();
    const n = s.shownSearch.received;
    const targets = [Math.floor(n * 0.1), Math.floor(n * 0.9), 3, Math.floor(n / 2), n - 1, Math.floor(n * 0.25)];
    return targets.map((t) => { const t0 = performance.now(); s.seekSeq(t); return { to: t, ms: performance.now() - t0 }; });
  });
  await page.evaluate(() => window.__cocoArena.session().seekSeq(Math.floor(window.__cocoArena.session().shownSearch.received * 0.25)));
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, 'computation_25pct.png') });
  // step buttons and live
  await page.getByTestId('tl-seq-fwd').click();
  const afterStep = await page.evaluate(() => window.__cocoArena.session().shownSearch.cursor);
  await page.getByTestId('tl-live').click();
  await page.waitForTimeout(1500);
  const rejoined = await page.evaluate(() => ({ live: window.__cocoArena.session().live, head: window.__cocoArena.session().head }));
  Object.assign(out, { seek_world: seekWorld, seek_computation: seeks, after_step_cursor: afterStep, rejoined,
    seek_ms_max: Math.max(seekWorld.ms, ...seeks.map((x) => x.ms)) });
} finally {
  await browser.close();
}
console.log(JSON.stringify({ events: out.events, seek_ms_max: out.seek_ms_max, seeks: out.seek_computation?.map((x) => Math.round(x.ms * 10) / 10), rejoined: out.rejoined, errors: errors.length }));
writeFileSync(join(OUT, 'timeline_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
