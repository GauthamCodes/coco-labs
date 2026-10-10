// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Arena cold start (M1.5 / M1.10), in headless Chromium, n fresh browsers.
 *
 *   node tools/perf/coldstart.mjs --site http://127.0.0.1:4173/coco-labs/
 *        [--runs 10] [--pyodide self|cdn] [--throttle none|wifi|4g] [--gl swiftshader|gpu]
 *        [--out FILE.json]
 *
 * Each run: a new browser and context (empty cache), open `?view=arena&perf`,
 * read the page's own marks (window.__cocoPerf: wall-clock ms), then send a
 * goal and time the first plan batch to reach the page. Also: console
 * errors, page errors, every request's bytes (encoded, as transferred).
 *
 * Throttling uses Chromium's network emulation on the page AND its workers
 * (CDP per target), so same-origin and CDN requests pay the same link:
 *   wifi: 30 Mbit/s down, 15 up, 20 ms latency
 *   4g:   9 Mbit/s down, 1.5 up, 170 ms latency (a fair mobile-data link)
 * The phone itself is measured by Gautham (docs/v2/PHONE_MEASURE.md).
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';
const CONDITIONS_AT_START = conditions();

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4173/coco-labs/';
const RUNS = Number(args.runs ?? 10);
// --gl gpu: the laptop's GPU through ANGLE, as a real browser renders; default
// is headless Chromium's software GL (SwiftShader), which runs on the CPU
const GL = args.gl === 'gpu' ? 'gpu' : 'swiftshader';
// --no-attract 1: an A/B arm, the attract recording's request refused, so the
// page boots as it did before M1.8 (it logs that one failed fetch)
const NO_ATTRACT = args['no-attract'] === '1';
// --attract POLICY (M2.0): when the page starts its attract recording (eager, low, after_pyodide, after_live)
const ATTRACT = args.attract ?? null;
const LAUNCH = GL === 'gpu' ? { args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] } : {};
const SOURCE = args.pyodide ?? 'self';
const THROTTLE = args.throttle ?? 'none';
const PROFILES = {
  none: null,
  wifi: { downloadThroughput: 30e6 / 8, uploadThroughput: 15e6 / 8, latency: 20 },
  '4g': { downloadThroughput: 9e6 / 8, uploadThroughput: 1.5e6 / 8, latency: 170 },
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const summary = (xs) => (xs.length ? { n: xs.length, median: Math.round(median(xs)), min: Math.round(Math.min(...xs)), max: Math.round(Math.max(...xs)) } : { n: 0 });

async function throttle(context, page) {
  const p = PROFILES[THROTTLE];
  if (!p) return;
  const apply = async (target) => {
    const cdp = await context.newCDPSession(target);
    await cdp.send('Network.enable');
    await cdp.send('Network.emulateNetworkConditions', { offline: false, ...p });
  };
  await apply(page);
  page.on('worker', (w) => { void apply(w).catch(() => {}); });
}

async function run(i) {
  const browser = await chromium.launch(LAUNCH);
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  if (NO_ATTRACT) await context.route('**/generated/arena/attract.mcap', (r) => r.abort());
  const page = await context.newPage();
  await throttle(context, page);
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  const bytes = { total: 0, requests: 0, byHost: {} };
  page.on('requestfinished', async (r) => {
    try {
      const s = await r.sizes();
      const host = new URL(r.url()).host;
      bytes.total += s.responseBodySize + s.responseHeadersSize;
      bytes.requests += 1;
      bytes.byHost[host] = (bytes.byHost[host] ?? 0) + s.responseBodySize;
    } catch { /* aborted */ }
  });
  // workers' requests are not page requests: count them from the worker side
  context.on('requestfinished', () => {});
  try {
    await page.goto(`${SITE}?view=arena&perf${SOURCE === 'cdn' ? '&pyodide=cdn' : ''}${ATTRACT ? `&attract=${ATTRACT}` : ''}`);
    const t0 = Date.now();
    await page.waitForFunction(() => !!window.__cocoPerf?.marks.arena_ready, null, { timeout: 180_000, polling: 50 });
    const readyMarks = await page.evaluate(() => ({ ...window.__cocoPerf.marks, navStart: window.__cocoPerf.navStart }));
    // one goal, sent at the next tick; time the first plan events back
    const goalAt = await page.evaluate(() => {
      const at = performance.timeOrigin + performance.now();
      // as a click does: hands the attract recording over to the live model (M1.8)
      window.__cocoArena.goal(6.0, 4.0);
      return at;
    });
    await page.waitForFunction(() => window.__cocoPerf.firstPlanBatchAt !== null, null, { timeout: 60_000, polling: 10 });
    const first = await page.evaluate(() => window.__cocoPerf.firstPlanBatchAt);
    await sleep(300);
    const nav = readyMarks.navStart;
    const rel = (k) => (readyMarks[k] ? readyMarks[k] - nav : null);
    return {
      run: i + 1,
      wall_to_ready_ms: Date.now() - t0,
      ms_since_navigation: {
        worker_create: rel('worker_create'), pyodide_module: rel('pyodide_module'),
        pyodide_ready: rel('pyodide_ready'), coco_lab_ready: rel('coco_lab_ready'),
        arena_ready: rel('arena_ready'), first_frame: rel('first_frame'),
        // M1.8: the attract recording plays before the live model is ready; its
        // first drawn search is the page's FIRST VISIBLE COMPUTATION
        attract_ready: rel('attract_ready'), first_computation_shown: rel('first_computation_shown'),
      },
      // includes waiting for the next 100 ms tick boundary (dt): the goal is
      // applied at the start of a tick, by design
      goal_to_first_plan_events_ms: Math.round(first - goalAt),
      console_errors: errors,
      page_requests: bytes.requests, page_bytes: bytes.total, page_body_bytes_by_host: bytes.byHost,
    };
  } finally {
    await browser.close();
  }
}

const runs = [];
for (let i = 0; i < RUNS; i += 1) {
  const r = await run(i);
  runs.push(r);
  console.log(JSON.stringify({ run: r.run, arena_ready: r.ms_since_navigation.arena_ready, pyodide_ready: r.ms_since_navigation.pyodide_ready, goal_to_first: r.goal_to_first_plan_events_ms, errors: r.console_errors.length }));
}
const b = await chromium.launch();
const result = {
  meta: {
    site: SITE, runs: RUNS, pyodide: SOURCE, throttle: THROTTLE, profile: PROFILES[THROTTLE], gl: GL, no_attract: NO_ATTRACT, attract: ATTRACT ?? 'default',
    browser: `chromium ${b.version()} (Playwright, headless)`, cpu: os.cpus()[0].model,
    at_utc: new Date().toISOString(), load1: Math.round(os.loadavg()[0] * 10) / 10,
    // CPU speed decides these numbers: record the laptop's power state (M1.10 found power-saver)
    power_profile: (() => { try { return execFileSync('powerprofilesctl', ['get']).toString().trim(); } catch { return 'unknown'; } })(),
    governor: (() => { try { return readFileSync('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'utf-8').trim(); } catch { return 'unknown'; } })(),
  },
  first_computation_shown_ms: summary(runs.map((r) => r.ms_since_navigation.first_computation_shown).filter((x) => x !== null)),
  arena_ready_ms: summary(runs.map((r) => r.ms_since_navigation.arena_ready)),
  pyodide_ready_ms: summary(runs.map((r) => r.ms_since_navigation.pyodide_ready)),
  goal_to_first_plan_events_ms: summary(runs.map((r) => r.goal_to_first_plan_events_ms)),
  console_errors_total: runs.reduce((n, r) => n + r.console_errors.length, 0),
  runs,
};
await b.close();
console.log(JSON.stringify({ first_computation_ms: result.first_computation_shown_ms, arena_ready_ms: result.arena_ready_ms,
  goal_to_first: result.goal_to_first_plan_events_ms }));
if (args.out) writeFileSync(args.out, JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...result }, null, 1) + '\n');
