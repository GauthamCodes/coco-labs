// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Move lens in a real browser (M2.5):
 *
 *   node tools/perf/move_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Takes over the live model, selects the Move lens (its pack loads; the
 * DWA sampler takes the wheels through a config input), then runs Lab 5's
 * scenarios from the scenario picker: run 15 ("mislocalised": the local
 * window drawn around the BELIEVED pose, 3.4 m from the given path, the
 * controller with no path in its window and 0 candidates) for each of the
 * three controllers, and the crossing (candidates, the chosen trajectory
 * and the actor's body drawn). Exit 0 only with 0 console errors, 0
 * three.js warnings and every step seen.
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
const OUT = args.out ?? 'move-out';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
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
const lastCommand = () => page.evaluate(() => {
  const b = window.__cocoArena.session().families.latest('coco.control.local.command.v1', 1e9);
  return b ? { tick: b.tick, status: b.columns.status[0], n: b.columns.n_candidates[0], controller: b.scalars.controller_id } : null;
});
const commandsSince = (tick) => page.evaluate((t) => window.__cocoArena.session().families.before('coco.control.local.command.v1', 1e9)
  .filter((b) => b.tick > t).map((b) => ({ tick: b.tick, status: b.columns.status[0], n: b.columns.n_candidates[0], controller: b.scalars.controller_id })), tick);

try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  const [gx, gy] = await toScreen(2.0, 0.0);
  await page.mouse.click(gx, gy);
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live', null, { timeout: 30_000 });
  await page.getByTestId('lens-move').click();
  await page.waitForFunction(() => !!window.__cocoArena.session()?.headers.get('coco.control.local.header.v1'), null, { timeout: 60_000 });
  out.steps.controls = await page.getByTestId('move-controls').isVisible();

  // run 15, for each controller
  out.steps.run15 = {};
  for (const ctrl of ['dwa', 'rpp', 'mppi']) {
    await page.getByTestId('move-controller').selectOption(ctrl);
    const before = (await lastCommand())?.tick ?? 0;
    await page.getByTestId('move-scenario').selectOption('none');
    await page.getByTestId('move-scenario').selectOption('mislocalised');
    await page.waitForFunction((t) => window.__cocoArena.session().families.before('coco.control.local.command.v1', 1e9).some((b) => b.tick > t && b.columns.status[0] === 'invalid_path'), before, { timeout: 30_000 });
    // from the tick the scenario was applied (the run's input log), not from the earlier goal's cycles
    const applied = await page.evaluate(() => window.__cocoArena.log().filter((r) => r.kind === 'config' && r.choice === 'move.scenario=mislocalised').at(-1)?.tick ?? 0);
    const cmds = await commandsSince(applied - 1);
    const rec = await page.evaluate(() => window.__cocoArena.last);
    out.steps.run15[ctrl] = { commands: cmds, belief: rec.pose, truth: rec.truth ?? null, mode: rec.mode };
    if (ctrl === 'dwa') {
      await page.getByTestId('level-explain').click();
      await page.waitForTimeout(600);
      out.steps.run15_layers = await page.evaluate(() => window.__cocoArena.layerIds());
      await page.screenshot({ path: join(OUT, 'move_run15_explain.png') });
    }
  }

  // the crossing with DWA: candidates, the chosen one, the actor
  await page.getByTestId('move-controller').selectOption('dwa');
  await page.getByTestId('move-scenario').selectOption('crossing');
  await page.waitForFunction(() => (window.__cocoArena.last?.actors ?? []).length > 0 && window.__cocoArena.last.pose[1] < -3.2, null, { timeout: 90_000 });
  await page.waitForTimeout(300);
  out.steps.crossing_layers = await page.evaluate(() => window.__cocoArena.layerIds());
  out.steps.crossing_command = await lastCommand();
  out.steps.actor = await page.evaluate(() => window.__cocoArena.last.actors);
  await page.getByTestId('level-inspect').click();
  await page.waitForTimeout(800);
  out.steps.inspector = await page.evaluate(() => document.querySelector('[data-testid="lens-inspector"]')?.textContent?.slice(0, 400) ?? null);
  await page.screenshot({ path: join(OUT, 'move_crossing_inspect.png'), fullPage: true });
  await page.waitForFunction(() => window.__cocoArena.last?.mode === 'idle', null, { timeout: 90_000 });
  out.steps.crossing_outcome = await page.evaluate(() => window.__cocoArena.session().families.series('outcome.succeeded', 1e9).length > 0 ? 'succeeded' : 'not succeeded');
} finally {
  await browser.close();
}
const r15 = out.steps.run15 ?? {};
const each = ['dwa', 'rpp', 'mppi'].every((c) => r15[c]?.commands?.length === 1 && r15[c].commands[0].status === 'invalid_path'
  && r15[c].commands[0].n === 0 && r15[c].commands[0].controller === c && r15[c].mode === 'idle'
  && Math.abs(Math.hypot(r15[c].belief[0] - r15[c].truth[0], r15[c].belief[1] - r15[c].truth[1]) - 3.4) < 1e-6);
const cl = out.steps.crossing_layers ?? [];
out.pass = errors.length === 0 && warnings.length === 0 && out.steps.controls === true && each
  && (out.steps.run15_layers ?? []).includes('local_window') && (out.steps.run15_layers ?? []).includes('given_path')
  && ['candidates', 'chosen', 'actors', 'local_window'].every((id) => cl.includes(id))
  && out.steps.crossing_outcome === 'succeeded';
writeFileSync(join(OUT, 'move_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, run15: Object.fromEntries(Object.entries(r15).map(([k, v]) => [k, v.commands])), crossing: out.steps.crossing_outcome, errors: errors.length, warnings: warnings.length }));
process.exit(out.pass ? 0 : 1);
