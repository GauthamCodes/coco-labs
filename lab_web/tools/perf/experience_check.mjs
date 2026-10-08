// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Arena experience in a real browser (M1.8), as a visitor uses it:
 *
 *   1. attract: the recording moves before the live model is ready;
 *   2. a click on the map takes over: live model, goal, drive, arrival card
 *      with totals, heatmap on;
 *   3. keyboard teleop (W held) and the on-screen joystick (a drag) move it;
 *   4. compare two planners on one goal: both panes fill, both totals shown;
 *   5. share the run, open the link in a new page: it replays and reports
 *      whether the hash chain matched;
 *   6. a phone-sized viewport: a TAP gives a goal.
 *
 * Every step is checked, screenshotted, and console errors are counted.
 *
 *   node tools/perf/experience_check.mjs --site URL --out DIR
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, devices } from 'playwright';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4174/coco-labs/';
const OUT = args.out ?? 'experience-out';
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const out = { site: SITE, steps: {}, errors: [] };
const ok = (name, pass, detail = {}) => { out.steps[name] = { pass: !!pass, ...detail }; console.log(`${pass ? 'PASS' : 'FAIL'} ${name} ${JSON.stringify(detail)}`); };

function watch(page) {
  page.on('console', (m) => { if (m.type() === 'error') out.errors.push(m.text()); });
  page.on('pageerror', (e) => out.errors.push(String(e)));
}

/** Screen point of a map point (toWorld is affine: solve it from three samples). */
async function screenOf(page, x, y) {
  return page.evaluate(([x, y]) => {
    const r = window.__cocoArena.renderer;
    const b = r.canvas.getBoundingClientRect();
    const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
    const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
    const ax = (px[0] - p0[0]) / 100; const ay = (py[1] - p0[1]) / 100;
    return [cx + (x - p0[0]) / ax, cy + (y - p0[1]) / ay];
  }, [x, y]);
}

const pose = (page) => page.evaluate(() => window.__cocoArena.session()?.shownTick?.pose ?? null);
const mode = (page) => page.evaluate(() => window.__cocoArena.mode());

try {
  // -- 1..5 on a laptop viewport ------------------------------------------
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1100 } });
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write']);
  const page = await ctx.newPage();
  watch(page);
  const t0 = Date.now();
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.attract_ready, null, { timeout: 60_000 });
  const marks0 = await page.evaluate(() => ({ ...window.__cocoPerf.marks, nav_start: window.__cocoPerf.navStart }));
  await page.waitForTimeout(1500);
  const a1 = await pose(page);
  await page.waitForTimeout(1500);
  const a2 = await pose(page);
  const attractMoved = !!a1 && !!a2 && Math.hypot(a2[0] - a1[0], a2[1] - a1[1]) > 0.01;
  // the ?perf panel shows these marks ON SCREEN (a mark the panel does not name reads "—")
  const panel = { recording: await page.getByTestId('perf-attract_ready').textContent(),
    computation: await page.getByTestId('perf-first_computation_shown').textContent() };
  ok('attract_plays', (await mode(page)) === 'attract' && attractMoved && /\d/.test(panel.recording) && /\d/.test(panel.computation), {
    panel,
    attract_ready_ms: Math.round(marks0.attract_ready - marks0.nav_start), first_computation_ms: marks0.first_computation_shown
      ? Math.round(marks0.first_computation_shown - marks0.nav_start) : null, arena_ready_yet: !!marks0.arena_ready });
  await page.screenshot({ path: join(OUT, '1_attract.png') });

  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await page.getByTestId('planner-dijkstra').click();
  const [gx, gy] = [6.0, 4.0];
  const [sx, sy] = await screenOf(page, gx, gy);
  await page.mouse.click(sx, sy);
  await page.waitForTimeout(500);
  ok('click_takes_over', (await mode(page)) === 'live', { clicked: [Math.round(sx), Math.round(sy)] });
  await page.getByTestId('run-card').waitFor({ timeout: 90_000 });
  const totals = await page.getByTestId('run-totals').textContent();
  const heat = await page.getByTestId('layer-heatmap').isChecked();
  const end = await pose(page);
  ok('goal_arrives_with_totals', /expansions/.test(totals) && /path cost/.test(totals) && heat
    && Math.hypot(end[0] - gx, end[1] - gy) < 0.5, { totals: totals.trim(), heatmap: heat, end });
  await page.screenshot({ path: join(OUT, '2_arrived_heatmap.png') });
  await page.getByRole('button', { name: 'OK' }).click();

  const k0 = await pose(page);
  await page.keyboard.down('w');
  await page.waitForTimeout(1200);
  await page.keyboard.up('w');
  await page.waitForTimeout(400);
  const k1 = await pose(page);
  ok('keyboard_teleop', Math.hypot(k1[0] - k0[0], k1[1] - k0[1]) > 0.05, { moved_m: Math.hypot(k1[0] - k0[0], k1[1] - k0[1]) });
  await page.keyboard.press('Space');

  const joy = await page.getByTestId('arena-joystick').boundingBox();
  const j0 = await pose(page);
  await page.mouse.move(joy.x + joy.width / 2, joy.y + joy.height / 2);
  await page.mouse.down();
  await page.mouse.move(joy.x + joy.width * 0.75, joy.y + joy.height * 0.15, { steps: 5 });
  await page.waitForTimeout(1200);
  await page.mouse.up();
  await page.waitForTimeout(400);
  const j1 = await pose(page);
  ok('joystick_teleop', Math.hypot(j1[0] - j0[0], j1[1] - j0[1]) > 0.05 || Math.abs(j1[2] - j0[2]) > 0.1,
    { moved_m: Math.hypot(j1[0] - j0[0], j1[1] - j0[1]), turned_rad: j1[2] - j0[2] });

  await page.getByTestId('compare-a').selectOption('astar');
  await page.getByTestId('compare-b').selectOption('bfs');
  await page.getByTestId('compare-pick').click();
  const [cx, cy] = await screenOf(page, 2.5, 2.0);
  await page.mouse.click(cx, cy);
  await page.getByTestId('compare-A-totals').waitFor({ timeout: 60_000 });
  await page.getByTestId('compare-B-totals').waitFor({ timeout: 60_000 });
  await page.waitForTimeout(3000); // let both panes reveal
  const ta = (await page.getByTestId('compare-A-totals').textContent()).trim();
  const tb = (await page.getByTestId('compare-B-totals').textContent()).trim();
  const exp = (s) => Number(/([\d,]+) expansions/.exec(s)?.[1].replace(/,/g, ''));
  // each pane is the planner that was CHOSEN (not a default captured at load)
  const na = (await page.locator('[data-testid=compare-A] figcaption b').textContent()).trim();
  const nb = (await page.locator('[data-testid=compare-B] figcaption b').textContent()).trim();
  ok('compare_two_planners', na === 'astar' && nb === 'bfs' && exp(ta) > 0 && exp(tb) > exp(ta) && (await mode(page)) === 'live',
    { A: `${na} ${ta}`, B: `${nb} ${tb}` });
  await page.getByTestId('compare').screenshot({ path: join(OUT, '3_compare.png') });
  await page.getByTestId('compare-close').click();

  await page.getByTestId('share-make').click();
  const url = await page.getByTestId('share-url').inputValue();
  // what the LINK says (the live model keeps running after Share is pressed)
  const enc = new URL(url).searchParams.get('run');
  const link = JSON.parse(Buffer.from(enc.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf-8'));
  const before = { tick: link.t, chain: link.c, inputs: link.i.length };
  ok('share_link_made', url.includes('run='), { url_chars: url.length, ...before });
  const p2 = await ctx.newPage();
  watch(p2);
  await p2.goto(url.replace(/^https?:\/\/[^/]+\/coco-labs\//, SITE));
  await p2.waitForFunction(() => /reproduced exactly|DIFFERS/.test(document.querySelector('[data-testid=arena-mode]')?.textContent ?? ''),
    null, { timeout: 180_000 });
  const verdict = await p2.getByTestId('arena-mode').textContent();
  const after = await p2.evaluate(() => ({ tick: window.__cocoArena.last.tick, chain: window.__cocoArena.last.chain }));
  ok('share_link_reproduces', /reproduced exactly/.test(verdict) && after.chain === before.chain && after.tick === before.tick,
    { verdict: verdict.trim(), after });
  await p2.screenshot({ path: join(OUT, '4_shared_replay.png') });
  out.laptop_ms = Date.now() - t0;
  await ctx.close();

  // -- 6. a phone: tap a goal ------------------------------------------------
  const phone = await browser.newContext({ ...devices['Pixel 7'] });
  const pp = await phone.newPage();
  watch(pp);
  await pp.goto(`${SITE}?view=arena`);
  await pp.waitForFunction(() => window.__cocoArena?.client.world, null, { timeout: 120_000 });
  await pp.waitForTimeout(500);
  const [tx, ty] = await screenOf(pp, 6.0, 4.0);
  await pp.touchscreen.tap(tx, ty);
  await pp.waitForTimeout(3000);
  const ph = await pp.evaluate(() => ({ mode: window.__cocoArena.mode(), goal: window.__cocoArena.log().find((r) => r.kind === 'goal') ?? null,
    width: document.documentElement.scrollWidth, vw: window.innerWidth }));
  ok('phone_tap_goal', ph.mode === 'live' && !!ph.goal && ph.width <= ph.vw, ph);
  await pp.screenshot({ path: join(OUT, '5_phone.png'), fullPage: true });
  await phone.close();
} finally {
  await browser.close();
}
out.pass = Object.values(out.steps).every((s) => s.pass) && out.errors.length === 0;
console.log(JSON.stringify({ pass: out.pass, errors: out.errors.length, first: out.errors.slice(0, 3) }));
writeFileSync(join(OUT, 'experience_check.json'), JSON.stringify(out, null, 1) + '\n');
process.exit(out.pass ? 0 : 1);
