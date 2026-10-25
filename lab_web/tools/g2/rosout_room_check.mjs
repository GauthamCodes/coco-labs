// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.8: the collapsed /rosout console never runs under the telemetry strip beside it. Seen on the
 * real Nothing Phone (1) (full screen 803 x 361, 2026-10-25): a long WARN, wrapped to two lines,
 * ran under the fixed-width strip. Plays Fetch Rush shift 1 at the phone's full-screen CSS size
 * (touch, Android UA; viewport only -- looks, not a measurement), puts a long WARN in the collapsed
 * line (the longest the model writes, doubled), and checks the console's box against the strip's,
 * in GAME and in SIM view, and at the desktop size; and that the collapsed line shows two lines and
 * no part of a third (the clamp needs overflow hidden). Exit 1 on any overlap, leak or page error.
 *
 *   node tools/g2/rosout_room_check.mjs SITE [OUT.json]
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { launchOptions } from '../g1/gpu.mjs';

const [site, out] = process.argv.slice(2);
const LONG = 'WARN local_controller: blocked: obstacle 0.26 m ahead, holding for the forklift; blocked: obstacle 0.26 m ahead, holding for the forklift';
const PROFILES = [
  ['real-phone-full-screen-803x361', { viewport: { width: 803, height: 361 }, deviceScaleFactor: 1.25, isMobile: true, hasTouch: true,
    userAgent: 'Mozilla/5.0 (Linux; Android 15; A063) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36' }],
  ['desktop-1440x900', { viewport: { width: 1440, height: 900 } }],
];
const b = await chromium.launch(launchOptions());
const rows = [];
for (const [name, ctxOpts] of PROFILES) {
  const ctx = await b.newContext({ ...ctxOpts, serviceWorkers: 'block' });
  const p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e).slice(0, 160)));
  await p.goto(`${site}?view=play&game=fetch_rush&seed=1&tier=low`, { timeout: 120000 });
  // as tools/g1/chase_hud_check.mjs: PLAY once it is enabled, then the model's ticks
  await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
  await p.click('[data-testid="g1-play"]');
  await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 3, null, { timeout: 120000 });
  await p.waitForSelector('[data-testid="g2-rosout"]', { timeout: 30000 });
  await p.waitForTimeout(1500);
  for (const view of ['game', 'sim']) {
    if (view === 'sim') { await p.click('[data-testid="g2-view-sim"]').catch(() => {}); await p.waitForTimeout(2000); }
    const r = await p.evaluate((long) => {
      const box = document.querySelector('[data-testid="g2-rosout"]'), strip = document.querySelector('[data-testid="g2-telemetry"]');
      const line = box?.querySelector('.head .line, .head .title');
      if (line) line.textContent = long;
      return new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(() => {
        const A = box.getBoundingClientRect(), B = strip.getBoundingClientRect();
        const w = Math.min(A.right, B.right) - Math.max(A.left, B.left), h = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
        // the collapsed line shows two lines and no part of a third (the clamp hides the rest)
        // (the clamped element must have no padding: overflow clips at the padding edge, and a padded
        // clamp shows the top of the next line through its padding -- the real phone, G2.8)
        const text = box.querySelector('.head > span'), cs = getComputedStyle(text), lh = parseFloat(getComputedStyle(box).lineHeight);
        const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
        res({ rosout: [A.left, A.top, A.right, A.bottom].map(Math.round), strip: [B.left, B.top, B.right, B.bottom].map(Math.round),
          overlap_px: w > 1 && h > 1 ? Math.round(w) : 0, gap_px: Math.round(B.left - A.right),
          shown_lines: Math.round((text.clientHeight / lh) * 100) / 100, clamped: cs.overflow === 'hidden' && pad === 0 });
      })));
    }, LONG);
    const ok = r.overlap_px === 0 && r.clamped && r.shown_lines <= 2.05 && errors.length === 0;
    rows.push({ profile: name, view, ok, ...r, errors: [...errors] });
    console.log(name, view, ok ? 'ok' : 'FAILED', JSON.stringify(r));
  }
  await ctx.close();
}
await b.close();
const passed = rows.every((r) => r.ok);
if (out) writeFileSync(out, JSON.stringify({ site, passed, note: 'viewport/UA emulation of the real phone\'s full-screen size: looks, not a measurement', rows }, null, 1) + '\n');
process.exitCode = passed ? 0 : 1;
