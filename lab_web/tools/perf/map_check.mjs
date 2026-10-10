// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The Map lens in a real browser (M2.4):
 *
 *   node tools/perf/map_check.mjs --site URL --out DIR [--gpu 1]
 *
 * Takes over the live model, selects the Map lens (its pack loads; an
 * occupancy grid from known poses starts through a config input), waits
 * for map keyframes and scores, then switches to the pose graph and drives
 * a 2 m square by clicking goals until a loop closure is emitted -- the
 * graph before AND after optimising, both drawn -- then switches to
 * EKF-SLAM and checks the IDEALISED-sensor label is on screen. Exit 0 only
 * with 0 console errors and every step seen.
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
const OUT = args.out ?? 'map-out';
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
const channels = () => page.evaluate(() => window.__cocoArena.session().families.channels().sort());
const goTo = async (x, y) => {
  const [sx, sy] = await toScreen(x, y);
  await page.mouse.click(sx, sy);
  await page.waitForFunction(() => window.__cocoArena.last?.mode !== 'idle', null, { timeout: 10_000 }).catch(() => {});
  await page.waitForFunction(() => window.__cocoArena.last?.mode === 'idle', null, { timeout: 90_000 });
};
const layers = () => page.evaluate(() => window.__cocoArena.layerIds());

try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await goTo(2.0, 0.0);
  await page.getByTestId('lens-map').click();
  const t0 = Date.now();
  await page.waitForFunction(() => !!window.__cocoArena.session()?.headers.get('coco.map.grid.header.v1'), null, { timeout: 60_000 });
  out.steps.map_started_ms = Date.now() - t0;
  out.steps.controls = await page.getByTestId('map-controls').isVisible();
  await goTo(0.5, -1.5);
  await page.waitForFunction(() => window.__cocoArena.session().families.channels().includes('coco.map.grid.snapshot.v1'), null, { timeout: 30_000 });
  out.steps.occupancy_channels = await channels();
  out.steps.occupancy_layers = await layers();
  await page.screenshot({ path: join(OUT, 'map_occupancy_watch.png') });

  // the pose graph, driven round a 2 m square from the start
  await goTo(0.0, 0.0);
  await page.getByTestId('map-algorithm').selectOption('pose_graph');
  for (const [x, y] of [[2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0], [1.0, 0.0]]) await goTo(x, y);
  out.steps.closures = await page.evaluate(() => {
    const s = window.__cocoArena.session().families;
    return s.before('coco.map.slam.nodes.v1', 1e9).filter((b) => b.scalars.stage === 'optimised').map((b) => ({ tick: b.tick, chi2_after: b.scalars.chi2 }));
  });
  await page.getByTestId('level-inspect').click();
  await page.waitForTimeout(800);
  out.steps.pose_graph_layers = await layers();
  // show the last closure: seek the timeline is not needed -- the latest batch is drawn
  await page.screenshot({ path: join(OUT, 'map_pose_graph_inspect.png'), fullPage: true });
  out.steps.ate_f1 = await page.evaluate(() => {
    const s = window.__cocoArena.session().families;
    return { ate: s.series('ate', 1e9).at(-1) ?? null, f1: s.series('f1', 1e9).at(-1) ?? null };
  });

  // EKF-SLAM: the landmark sensor is labelled IDEALISED on screen
  await page.getByTestId('map-algorithm').selectOption('ekf_slam');
  await goTo(2.5, 2.0);
  await page.waitForFunction(() => window.__cocoArena.session().families.channels().includes('coco.map.slam.landmarks.v1'), null, { timeout: 30_000 });
  out.steps.idealised_on_screen = await page.locator('.lens-hint', { hasText: 'IDEALISED' }).isVisible();
  out.steps.ekf_slam_layers = await layers();
  await page.screenshot({ path: join(OUT, 'map_ekf_slam_inspect.png'), fullPage: true });
} finally {
  await browser.close();
}
const lyr = out.steps.pose_graph_layers ?? [];
out.pass = errors.length === 0 && warnings.length === 0 && out.steps.controls === true
  && out.steps.occupancy_channels?.includes('coco.map.grid.snapshot.v1')
  && (out.steps.occupancy_layers ?? []).includes('built_map')
  && out.steps.closures?.length >= 1 && lyr.includes('graph') && lyr.includes('graph_before')
  && out.steps.idealised_on_screen === true;
writeFileSync(join(OUT, 'map_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
console.log(JSON.stringify({ pass: out.pass, closures: out.steps.closures?.length, errors: errors.length, warnings: warnings.length, layers: lyr }));
process.exit(out.pass ? 0 : 1);
