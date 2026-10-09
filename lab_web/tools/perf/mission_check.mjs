// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Decide lens and the fetch mission in a real browser (M2.6):
 *
 *   node tools/perf/mission_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Takes over the live model, selects the Decide lens (its pack loads), puts
 * the red target in Bay 3 and starts a red fetch: the robot chooses a bay
 * by expected cost, drives, looks, grasps (the arm inset animates; the
 * magnet holds) and comes home -- result "fetch". Then, after a reset, the
 * robot is told it is 4 m south of where it is and fetches again: the
 * camera sees Bay 4 while the robot believes it is at Bay 3, and the miss
 * is booked against Bay 3 -- localisation's error reaching the search.
 * Exit 0 only with 0 console errors, 0 three.js warnings and every step.
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
const OUT = args.out ?? 'mission-out';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1100 } });
const errors = [];
const warnings = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); else if (m.type() === 'warning' && m.text().includes('THREE')) warnings.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, steps: {}, errors, warnings };

const toScreen = (x, y) => page.evaluate(([x, y]) => {
  const r = window.__cocoArena.renderer;
  const b = r.canvas.getBoundingClientRect();
  const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
  const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
  return [cx + (x - p0[0]) / ((px[0] - p0[0]) / 100), cy + (y - p0[1]) / ((py[1] - p0[1]) / 100)];
}, [x, y]);
const transitions = () => page.evaluate(() => window.__cocoArena.session().families.before('coco.mission.fsm.transition.v1', 1e9)
  .flatMap((b) => b.columns.to_state.map((s, i) => ({ tick: b.tick, to: s, event: b.columns.event[i], reason: b.columns.reason[i], result: b.columns.result[i] }))));
const waitState = (states, timeout) => page.waitForFunction((st) => {
  const b = window.__cocoArena.session()?.families.latest('coco.mission.fsm.transition.v1', 1e9);
  return b && st.includes(b.columns.to_state.at(-1));
}, states, { timeout });

try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  const [gx, gy] = await toScreen(1.0, 0.0);
  await page.mouse.click(gx, gy);
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live', null, { timeout: 30_000 });
  await page.getByTestId('lens-decide').click();
  await page.waitForFunction(() => document.querySelector('[data-testid="decide-controls"]'), null, { timeout: 60_000 });
  await page.getByTestId('decide-truth').selectOption('bay_3');
  await page.getByTestId('decide-colour').selectOption('red');
  await page.getByTestId('decide-start').click();
  await waitState(['go_to_bay'], 60_000);
  await page.waitForTimeout(3000);
  await page.screenshot({ path: join(OUT, 'decide_go_to_bay.png') });
  await waitState(['grasp'], 120_000);
  // the magnet's phase, however slowly the page runs
  await page.waitForFunction(() => /magnet on/.test(document.querySelector('[data-testid="arm-inset"]')?.getAttribute('aria-label') ?? ''), null, { timeout: 60_000 });
  out.steps.arm_inset = await page.getByTestId('arm-inset').getAttribute('aria-label');
  await page.screenshot({ path: join(OUT, 'decide_grasp.png'), fullPage: true });
  await waitState(['done', 'failed'], 180_000);
  out.steps.fetch = await transitions();
  out.steps.belief_table = await page.getByTestId('mission-belief').textContent();

  // the same fetch, mislocalised by 4 m
  await page.evaluate(() => window.__cocoArena.queue.push({ kind: 'reset' }));
  await page.waitForTimeout(500);
  const before = out.steps.fetch.length;
  await page.getByTestId('decide-truth').selectOption('bay_1');
  await page.getByTestId('decide-mislocalise').click();
  await page.getByTestId('decide-start').click();
  await page.waitForFunction((n) => {
    const all = window.__cocoArena.session().families.before('coco.mission.fsm.transition.v1', 1e9).flatMap((b) => b.columns.event);
    return all.length > n && all.slice(n).some((e) => e === 'miss' || e === 'no_progress' || e === 'navigation_failed');
  }, before, { timeout: 120_000 });
  out.steps.mislocalised = (await transitions()).slice(before);
  out.steps.loc_text = await page.getByTestId('mission-loc').textContent();
  await page.getByTestId('level-inspect').click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: join(OUT, 'decide_mislocalised_inspect.png'), fullPage: true });
} finally {
  await browser.close();
}
const f = out.steps.fetch ?? [];
const m = out.steps.mislocalised ?? [];
out.pass = errors.length === 0 && warnings.length === 0
  && f.at(-1)?.to === 'done' && f.at(-1)?.result === 'fetch' && f.some((t) => t.to === 'grasp')
  && /magnet on/.test(out.steps.arm_inset ?? '')
  && m.some((t) => t.event === 'miss' && t.reason.includes('the camera saw Bay 4 (the robot believes it is at Bay 3)'));
writeFileSync(join(OUT, 'mission_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, fetch: f.map((t) => t.to).join('>'), mislocalised: m.map((t) => `${t.to}:${t.event}`).join(' '), arm: out.steps.arm_inset, errors: errors.length, warnings: warnings.length }));
process.exit(out.pass ? 0 : 1);
