// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Responsiveness (M1 B.4): "first frontier node visible within 100 ms of a
 * goal click (warm)", measured the way a visitor causes it -- a real mouse
 * click on the map -- with the page's own records: the click
 * (perf.goalClicks) to the first rendered frame that drew THAT GOAL'S search
 * (perf.firstDraw of the last search planned after the click). Not "the first
 * new search": after a planner change that can be the re-plan, not the goal's.
 *
 * The first goal (which also hands attract mode over to the live model) is
 * reported apart; the warm goals are the criterion. Each goal is clicked
 * while the robot drives the previous one, and goals alternate planners.
 *
 * A planner change while a goal runs RE-PLANS that goal at once (arena.py,
 * by design). By default the harness lets that re-plan finish before the
 * goal click, so the click is measured, not the queue behind it;
 * `--immediate 1` clicks the goal right after the planner change, the
 * other case a visitor can cause, reported separately.
 *
 *   node tools/perf/responsiveness.mjs --site URL --out DIR [--n 25] [--gpu 1] [--immediate 0]
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
const OUT = args.out ?? 'responsiveness-out';
const N = Number(args.n ?? 25);
const GPU = args.gpu !== '0';
const IMMEDIATE = args.immediate === '1';
mkdirSync(OUT, { recursive: true });

// fixed goals in the map frame (all in open floor), cycled
const GOALS = [[6.0, 4.0], [2.5, 2.0], [0.5, -2.5], [-1.5, 1.0], [12.0, 5.5], [9.0, -4.0], [14.0, -6.0], [3.0, -6.5]];
const PLANNERS = ['astar', 'dijkstra', 'greedy', 'bfs', 'weighted_astar'];

const browser = await chromium.launch(GPU ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {});
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(String(e)));
const out = { site: SITE, gpu: GPU, n: N, immediate: IMMEDIATE, errors };

async function screenOf(x, y) {
  return page.evaluate(([x, y]) => {
    const r = window.__cocoArena.renderer;
    const b = r.canvas.getBoundingClientRect();
    const cx = b.left + b.width / 2; const cy = b.top + b.height / 2;
    const p0 = r.toWorld(cx, cy); const px = r.toWorld(cx + 100, cy); const py = r.toWorld(cx, cy + 100);
    return [cx + (x - p0[0]) / ((px[0] - p0[0]) / 100), cy + (y - p0[1]) / ((py[1] - p0[1]) / 100)];
  }, [x, y]);
}

const lat = [];
try {
  await page.goto(`${SITE}?view=arena&perf`);
  await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 120_000 });
  out.renderer = await page.evaluate(() => {
    const gl = document.createElement('canvas').getContext('webgl2');
    const ext = gl?.getExtension('WEBGL_debug_renderer_info');
    return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown';
  });
  for (let i = 0; i <= N; i += 1) {
    if (i > 0) {
      await page.getByTestId(`planner-${PLANNERS[i % PLANNERS.length]}`).click();
      if (!IMMEDIATE) {
        // a re-plan of the running goal, if any, finishes first
        await page.waitForTimeout(300);
        await page.waitForFunction(() => { const st = window.__cocoArena.session()?.shownSearch; return !st || st.final; }, null, { timeout: 60_000 });
        await page.waitForTimeout(500);
      }
    }
    const before = await page.evaluate(() => ({ n: window.__cocoPerf.goalClicks.length,
      // the live model's searches only (before the takeover the session shown is the recording's)
      ids: window.__cocoArena.mode() === 'live' ? Math.max(-1, ...window.__cocoArena.session().searches.keys()) : -1 }));
    const [gx, gy] = GOALS[i % GOALS.length];
    const [sx, sy] = await screenOf(gx, gy);
    await page.mouse.click(sx, sy);
    // the goal's search: the plan the model reports for THIS goal (its coordinates), made after the click
    const handle = await page.waitForFunction(([b, gx, gy]) => {
      const s = window.__cocoArena.session();
      for (const h of s?.history ?? []) {
        for (const p of h.plans) {
          // an object, not the id: search 0 is falsy and would read as "not yet"
          if (p.search_id > b.ids && Math.hypot(p.goal[0] - gx, p.goal[1] - gy) < 0.1) return { id: p.search_id };
        }
      }
      return false;
    }, [before, gx, gy], { timeout: 60_000, polling: 50 });
    const { id } = await handle.jsonValue();
    const one = await page.evaluate(([n, id]) => ({ click: window.__cocoPerf.goalClicks[n], drawn: window.__cocoPerf.firstDraw.get(id) ?? null }),
      [before.n, id]);
    if (one.drawn === null || one.drawn < one.click) throw new Error(`goal ${i}: search ${id} was never drawn after the click`);
    lat.push(one.drawn - one.click);
    // the robot starts driving: the next click lands mid-drive
    await page.waitForTimeout(1200);
  }
  const all = lat;
  const warm = all.slice(1);
  const sorted = [...warm].sort((a, b) => a - b);
  const q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  Object.assign(out, { first_goal_ms: all[0], warm_ms: warm, warm_n: warm.length, median_ms: q(0.5), p95_ms: q(0.95), max_ms: sorted.at(-1),
    min_ms: sorted[0], under_100: warm.filter((x) => x < 100).length });
} finally {
  await browser.close();
}
console.log(JSON.stringify({ first: out.first_goal_ms, n: out.warm_n, median: out.median_ms, p95: out.p95_ms, max: out.max_ms,
  under_100: out.under_100, renderer: out.renderer, errors: errors.length }));
writeFileSync(join(OUT, `responsiveness_${GPU ? 'gpu' : 'swiftshader'}${IMMEDIATE ? '_planner_then_goal' : ''}.json`), JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...out }, null, 1) + '\n');
