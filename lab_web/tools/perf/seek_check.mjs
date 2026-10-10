// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Seek on a 5-minute fetch-mission recording (M2 B.3 "Responsiveness":
 * seek <= 100 ms), in a real browser:
 *
 *   node tools/perf/seek_check.mjs --site URL --out DIR [--ticks 3000] [--gpu 1]
 *
 * Opens the Arena on the Decide lens with the fetch mission's whole loop
 * (MCL, an occupancy map from its belief, DWA; the Learn missions' cfg
 * lines), runs the model at speed 4 until the world has 3,000 ticks
 * (5 minutes at dt 0.1 s; a new fetch is started whenever one ends, so the
 * mission families span the recording), pauses, then seeks to ten ticks
 * spread over the recording, out of order. Each seek is timed twice: the
 * `seekTick` call alone, and from the call to the end of the second
 * animation frame after it -- the frame in which every lens has redrawn at
 * the new tick. Exit 0 only with every seek <= 100 ms both ways and 0
 * console errors.
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
const OUT = args.out ?? 'seek-out';
const TICKS = Number(args.ticks ?? 3000);
mkdirSync(OUT, { recursive: true });
const CFG = ['arena.range_sigma=0.02', 'localise.filter=mcl', 'map.algorithm=occupancy', 'map.poses=belief',
  'move.controller=dwa', 'mission.start=red'];
const COLOURS = ['green', 'blue', 'yellow', 'red'];

const browser = await chromium.launch(args.gpu === '1' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, ticks_wanted: TICKS, cfg: CFG, errors };
const t0 = Date.now();
try {
  await page.goto(`${SITE}?view=arena&perf&lens=decide&${CFG.map((c) => `cfg=${encodeURIComponent(c)}`).join('&')}`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  await page.waitForFunction(() => window.__cocoArena.mode() === 'live', null, { timeout: 60_000 });
  await page.getByTestId('tl-speed').selectOption('4');
  const fetches = [{ colour: 'red', started_tick: 0 }];
  for (;;) {
    const st = await page.evaluate(() => {
      const s = window.__cocoArena.session();
      const b = s.families.latest('coco.mission.fsm.transition.v1', 1e9);
      return { tick: s.head, state: b ? b.columns.to_state.at(-1) : null };
    });
    if (st.tick >= TICKS) break;
    if (st.state === 'done' || st.state === 'failed') {
      fetches.at(-1).ended = st;
      const colour = COLOURS[(fetches.length - 1) % COLOURS.length];
      await page.evaluate((c) => window.__cocoArena.queue.push({ kind: 'config', choice: `mission.start=${c}` }), colour);
      fetches.push({ colour, started_tick: st.tick });
      await page.waitForFunction(() => {
        const b = window.__cocoArena.session().families.latest('coco.mission.fsm.transition.v1', 1e9);
        return b && !['done', 'failed'].includes(b.columns.to_state.at(-1));
      }, null, { timeout: 30_000 });
    }
    if (Date.now() - t0 > 20 * 60_000) throw new Error(`recording too slow: tick ${st.tick} after 20 min`);
    await page.waitForTimeout(500);
  }
  out.record_wall_s = (Date.now() - t0) / 1000;
  out.fetches = fetches;
  // pause as a learner does (the Timeline's play button), then let the last step land
  if (await page.evaluate(() => window.__cocoArena.session().playing)) await page.getByTestId('tl-play').click();
  await page.waitForTimeout(1000);
  out.recorded = await page.evaluate(() => {
    const s = window.__cocoArena.session();
    const counts = {};
    for (const ch of s.families.channels()) counts[ch] = s.families.before(ch, 1e9).length;
    return { latest_tick: s.head, family_batches: counts };
  });
  const last = out.recorded.latest_tick;
  const targets = [0.5, 0.05, 0.95, 0.25, 0.75, 0.1, 0.9, 0.33, 0.66, 0.0].map((f) => Math.max(1, Math.floor(f * last)));
  out.seeks = [];
  for (const t of targets) {
    out.seeks.push(await page.evaluate((tick) => new Promise((resolve) => {
      const s = window.__cocoArena.session();
      const a = performance.now();
      s.seekTick(tick);
      const call = performance.now() - a;
      requestAnimationFrame(() => requestAnimationFrame(() => resolve({ to: tick, call_ms: call, to_frame_ms: performance.now() - a, view_tick: s.viewTick })));
    }), t));
  }
  await page.screenshot({ path: join(OUT, 'seek_after.png') });
  out.call_ms_max = Math.max(...out.seeks.map((x) => x.call_ms));
  out.to_frame_ms_max = Math.max(...out.seeks.map((x) => x.to_frame_ms));
  out.ok = errors.length === 0 && out.recorded.latest_tick >= TICKS && out.to_frame_ms_max <= 100 && out.call_ms_max <= 100
    && out.seeks.every((x) => x.view_tick === x.to);
} catch (e) {
  out.ok = false;
  out.failure = String(e);
}
writeFileSync(join(OUT, 'seek_check.json'), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
await browser.close();
console.log(JSON.stringify({ ok: out.ok, failure: out.failure, ticks: out.recorded?.latest_tick, fetches: out.fetches?.length,
  call_ms_max: out.call_ms_max, to_frame_ms_max: out.to_frame_ms_max, record_wall_s: out.record_wall_s, errors: errors.length }));
process.exit(out.ok ? 0 : 1);
