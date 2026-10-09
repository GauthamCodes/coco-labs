// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M0.3 baseline: the v1 site's timings, measured with Playwright against a
 * local PRODUCTION build (`npm run build`, served by `vite preview`).
 *
 *   node tools/perf/baseline.mjs --site http://127.0.0.1:4173/coco-labs/ \
 *       --runs 5 --out ../docs/v2/data/m0/perf
 *
 * Every run is a FRESH browser (empty HTTP cache), so a "cold" edit
 * downloads Pyodide from its pinned CDN exactly as a first visitor does.
 *
 * What is measured, with the page's own `?perf` marks (src/ui/perf.ts):
 *  - edit: Lab 1 (Plan) on the 0.10 m arena, paint ONE cell with the 1x1
 *    brush. Cold = edit 1 (click -> first frame, includes the Pyodide
 *    download/start and wheel install); warm = edits 2-4. The same flow
 *    as Phase 1D's tools/browser/check.py `edit`, so numbers compare.
 *  - fps: each view's own player is started and the browser's
 *    requestAnimationFrame callbacks are timestamped for WINDOW_S seconds:
 *    that is the frame rate the page achieved while playing back (a view
 *    that blocks the main thread drops rAF callbacks). Long tasks
 *    (> 50 ms) are counted. Lab 1 additionally reports its own draw time
 *    per frame (perfFrame). Live has no playback without a running stack.
 *  - console errors per page.
 * Nothing here computes an algorithm; it drives the page and reads clocks.
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
const SITE = args.site ?? 'http://127.0.0.1:4173/coco-labs/';
const RUNS = Number(args.runs ?? 5);
const OUT = args.out ?? 'perf-out';
const ONLY = (args.only ?? 'edit,fps,load').split(',');
const WINDOW_S = Number(args.window ?? 5);
const HEADED = args.headed === '1';
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const summary = (xs) => (xs.length ? { n: xs.length, median: round(median(xs)), min: round(Math.min(...xs)), max: round(Math.max(...xs)) } : { n: 0 });
const round = (x) => Math.round(x * 10) / 10;

async function fresh() {
  const browser = await chromium.launch({ headless: !HEADED });
  const context = await browser.newContext({ viewport: { width: 1400, height: 1000 } });
  // Mark the picture "dirty" on any 2D-canvas draw call or any DOM/SVG
  // mutation, so the probe can count the frames in which the VIEW changed
  // (rAF alone runs at the display rate whether or not anything is drawn).
  await context.addInitScript(() => {
    window.__m0 = { dirty: false };
    const P = CanvasRenderingContext2D.prototype;
    for (const name of ['clearRect', 'fillRect', 'strokeRect', 'drawImage', 'putImageData', 'fill', 'stroke', 'fillText']) {
      const orig = P[name];
      P[name] = function patched(...a) { window.__m0.dirty = true; return orig.apply(this, a); };
    }
    new MutationObserver(() => { window.__m0.dirty = true; })
      .observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  });
  const page = await context.newPage();
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  return { browser, page, errors };
}

// Predicates are FUNCTIONS, not strings: the site's CSP forbids eval, and
// Playwright evaluates a string predicate with it (measured: EvalError).
const READY = () => {
  const c = document.querySelector('[data-testid=map-canvas]');
  return !!(c && c.width > 0 && window.__cocoLabPerf && window.__cocoLabPerf.marks['bundle-first-frame']);
};
const EDIT_IDLE = () => {
  const e = document.querySelector('[data-testid=edit-status]');
  return !!e && !e.classList.contains('busy');
};
const EDIT_FRAME = () => !!(window.__cocoLabPerf.marks['edit-first-frame']
  || document.querySelector('[data-testid=edit-status].error'));

async function editRun(i) {
  const { browser, page, errors } = await fresh();
  try {
    await page.goto(`${SITE}?view=plan&perf&bundle=arena_0_10m`);
    await page.waitForFunction(READY, null, { timeout: 120_000 });
    const cat = await page.evaluate(`fetch('${SITE}generated/catalog.json').then(r => r.json())`);
    const entry = cat.bundles.find((e) => e.id === 'arena_0_10m');
    const manifest = await page.evaluate(`fetch('${SITE}generated/${entry.path}manifest.json').then(r => r.json())`);
    const W = manifest.map.width; const H = manifest.map.height;
    await page.getByTestId('tool-paint').click();
    const cells = [[H >> 1, W >> 1], [(H >> 1) + 3, (W >> 1) + 5], [(H >> 1) - 4, (W >> 1) - 6], [(H >> 1) + 1, (W >> 1) - 2]];
    const edits = [];
    for (const [k, [r, c]] of cells.entries()) {
      await page.evaluate('window.scrollTo(0, 0)');
      await page.evaluate(`(() => { const p = window.__cocoLabPerf; p.frames.length = 0; p.frameTimes.length = 0; p.marks = {}; })()`);
      const box = await page.getByTestId('map-canvas').boundingBox();
      const t0 = Date.now();
      await page.mouse.click(box.x + box.width * (c + 0.5) / W, box.y + box.height * (r + 0.5) / H);
      await page.waitForFunction(EDIT_IDLE, null, { timeout: 300_000, polling: 50 });
      await page.waitForFunction(EDIT_FRAME, null, { timeout: 30_000, polling: 50 });
      const marks = await page.evaluate('window.__cocoLabPerf.marks');
      const status = await page.getByTestId('edit-status').innerText();
      edits.push({
        edit: k + 1, cell: [r, c], wall_ms: Date.now() - t0,
        click_to_first_frame_ms: marks['edit-first-frame'] != null ? round(marks['edit-first-frame'] - marks['edit-click']) : null,
        status,
      });
    }
    return { run: i + 1, edits, console_errors: errors };
  } finally { await browser.close(); }
}

// One entry per public view: how to reach its player, which control plays.
const VIEWS = [
  { view: 'plan', query: '?view=plan&perf&bundle=arena_native', sub: null, play: 'play', note: 'Lab 1: full-arena native Dijkstra trace (283k events), default speed' },
  { view: 'localise', query: '?view=localise', sub: 'loc-sub-lab', play: 'loc-play', note: 'Lab 2: default Sketch bundle' },
  { view: 'map', query: '?view=map', sub: 'map-sub-replay', play: 'map-play', note: "Lab 3: COCO's recorded tour (Replay)" },
  { view: 'search', query: '?view=search', sub: 'search-sub-replay', play: 'search-replay-play', note: 'Lab 4: recorded Gazebo search (Replay)' },
  { view: 'move', query: '?view=move', sub: 'move-sub-drive', play: 'move-drive-play', note: 'Lab 5: static room, three controllers (Replay)' },
  { view: 'live', query: '?view=live', sub: null, play: null, note: 'Live: no playback without a running stack; load only' },
];

const RAF_PROBE = `(() => new Promise((res) => {
  const times = []; const longs = []; const updates = [];
  let obs = null;
  try { obs = new PerformanceObserver((l) => { for (const e of l.getEntries()) longs.push(e.duration); });
        obs.observe({ type: 'longtask', buffered: false }); } catch (e) { /* not supported */ }
  const end = performance.now() + ${WINDOW_S * 1000};
  window.__m0.dirty = false;
  const tick = (t) => {
    times.push(t);
    if (window.__m0.dirty) { updates.push(t); window.__m0.dirty = false; }
    if (t < end) requestAnimationFrame(tick); else { if (obs) obs.disconnect(); res({ times, longs, updates }); }
  };
  requestAnimationFrame(tick);
}))()`;

async function fpsRun(v, i) {
  const { browser, page, errors } = await fresh();
  try {
    await page.goto(`${SITE}${v.query}`);
    await page.waitForLoadState('networkidle', { timeout: 120_000 });
    if (v.view === 'plan') await page.waitForFunction(READY, null, { timeout: 120_000 });
    if (v.sub) await page.getByTestId(v.sub).click({ timeout: 60_000 });
    let played = false; let frames = null;
    if (v.play) {
      const btn = page.getByTestId(v.play).first();
      await btn.waitFor({ state: 'visible', timeout: 60_000 });
      await btn.scrollIntoViewIfNeeded();
      await sleep(500);
      if (v.view === 'plan') await page.evaluate(`(() => { const p = window.__cocoLabPerf; p.frames.length = 0; p.frameTimes.length = 0; })()`);
      await btn.click();
      played = true;
      const { times, longs, updates } = await page.evaluate(RAF_PROBE);
      const gaps = times.slice(1).map((t, k) => t - times[k]);
      const dur = (times[times.length - 1] - times[0]) / 1000;
      const s = [...gaps].sort((a, b) => a - b);
      frames = {
        view_updates_per_s: round(updates.length / dur),
        raf_fps: round((times.length - 1) / dur),
        gap_ms_median: round(median(gaps)), gap_ms_p95: round(s[Math.floor(0.95 * (s.length - 1))]), gap_ms_max: round(s[s.length - 1]),
        gaps_over_25ms: gaps.filter((g) => g > 25).length, long_tasks: longs.length, long_task_ms_total: round(longs.reduce((a, b) => a + b, 0)),
      };
      if (v.view === 'plan') {
        const perf = await page.evaluate('window.__cocoLabPerf');
        const d = [...perf.frames].sort((a, b) => a - b);
        frames.drawn_frames = perf.frames.length;
        frames.draw_ms_median = d.length ? round(median(d)) : null;
        frames.draw_ms_p95 = d.length ? round(d[Math.floor(0.95 * (d.length - 1))]) : null;
      }
      const label = await btn.innerText();
      frames.play_label_after = label; // "Pause" while still playing at the end of the window
    }
    return { run: i + 1, played, frames, console_errors: errors };
  } finally { await browser.close(); }
}

async function loadRun(v) {
  // M0 exit criterion: every public view loads with no console errors.
  const { browser, page, errors } = await fresh();
  try {
    const t0 = Date.now();
    await page.goto(`${SITE}${v.query.replace('&perf', '')}`);
    await page.waitForLoadState('networkidle', { timeout: 120_000 });
    await sleep(1500);
    const title = await page.title();
    const heading = await page.evaluate(`(() => { const b = document.querySelector('[data-testid=mode-badge]'); return b ? b.textContent : null; })()`);
    const text = await page.evaluate('document.body.innerText.length');
    return { view: v.view, ms_to_network_idle: Date.now() - t0, title, mode_badge: heading, body_text_chars: text, console_errors: errors };
  } finally { await browser.close(); }
}

async function weightRun() {
  // Every response the page AND its Pyodide worker receive, from a cold
  // load through one edit (so the Pyodide assets are included), with the
  // body size Chromium reports for each.
  const { browser, page, errors } = await fresh();
  const seen = [];
  page.on('requestfinished', async (req) => {
    const s = await req.sizes().catch(() => null);
    seen.push({ url: req.url(), type: req.resourceType(), body: s ? s.responseBodySize : null,
      headers: s ? s.responseHeadersSize : null });
  });
  try {
    await page.goto(`${SITE}?view=plan&perf&bundle=arena_0_10m`);
    await page.waitForFunction(READY, null, { timeout: 120_000 });
    await page.waitForLoadState('networkidle');
    const beforeEdit = seen.length;
    await page.getByTestId('tool-paint').click();
    const box = await page.getByTestId('map-canvas').boundingBox();
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForFunction(EDIT_IDLE, null, { timeout: 300_000, polling: 50 });
    await page.waitForLoadState('networkidle');
    await sleep(1000);
    const first = seen.slice(0, beforeEdit); const edit = seen.slice(beforeEdit);
    const sum = (xs) => xs.reduce((a, r) => a + (r.body ?? 0), 0);
    const cdn = seen.filter((r) => !r.url.startsWith(new URL(SITE).origin));
    return {
      initial_load: { requests: first.length, body_bytes: sum(first) },
      through_first_edit: { requests: edit.length, body_bytes: sum(edit) },
      pyodide_cdn: { requests: cdn.length, body_bytes: sum(cdn), files: cdn },
      all: seen, console_errors: errors,
    };
  } finally { await browser.close(); }
}

const meta = {
  site: SITE, runs: RUNS, window_s: WINDOW_S, browser: `chromium ${chromium.name()} (Playwright)`,
  started_utc: new Date().toISOString(), headless: !HEADED,
};
const result = { meta };
{
  const b = await chromium.launch(); meta.browser_version = b.version(); await b.close();
}

if (ONLY.includes('load')) {
  result.load = [];
  for (const v of VIEWS) { result.load.push(await loadRun(v)); console.log('load', v.view, JSON.stringify(result.load.at(-1))); }
}
if (ONLY.includes('edit')) {
  result.edit = { runs: [] };
  for (let i = 0; i < RUNS; i += 1) { const r = await editRun(i); result.edit.runs.push(r); console.log('edit', JSON.stringify(r.edits.map((e) => e.click_to_first_frame_ms))); }
  const cold = result.edit.runs.map((r) => r.edits[0].click_to_first_frame_ms).filter((x) => x != null);
  const warm = result.edit.runs.flatMap((r) => r.edits.slice(1).map((e) => e.click_to_first_frame_ms)).filter((x) => x != null);
  result.edit.cold_ms = summary(cold);
  result.edit.warm_ms = summary(warm);
}
if (ONLY.includes('fps')) {
  result.fps = {};
  for (const v of VIEWS) {
    const runs = [];
    for (let i = 0; i < RUNS; i += 1) {
      const r = await fpsRun(v, i); runs.push(r);
      console.log('fps', v.view, JSON.stringify(r.frames));
    }
    const f = runs.filter((r) => r.frames).map((r) => r.frames.raf_fps);
    const u = runs.filter((r) => r.frames).map((r) => r.frames.view_updates_per_s);
    result.fps[v.view] = { note: v.note, play: v.play, sub: v.sub, view_updates_per_s: summary(u), raf_fps: summary(f), runs };
  }
}
if (ONLY.includes('weight')) {
  const w = await weightRun();
  console.log('weight', JSON.stringify({ initial: w.initial_load, edit: w.through_first_edit, cdn: { requests: w.pyodide_cdn.requests, body_bytes: w.pyodide_cdn.body_bytes } }));
  writeFileSync(join(OUT, 'weight.json'), `${JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...{ meta, ...w } }, null, 1)}\n`);
}
meta.finished_utc = new Date().toISOString();
if (ONLY.some((o) => o !== 'weight')) {
  writeFileSync(join(OUT, 'baseline.json'), `${JSON.stringify({ conditions: { start: CONDITIONS_AT_START, end: conditions() }, ...result }, null, 1)}\n`);
  console.log('wrote', join(OUT, 'baseline.json'));
}
