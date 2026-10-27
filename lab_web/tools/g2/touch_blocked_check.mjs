// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.9: a drive input that produces no motion (COCO pushed into a wall: game rules stop it) must not
 * leave ?perf's input -> motion timer armed. Free Drive on the Depot: turn to face a wall, drive until
 * the drawn pose stops changing, push into the wall for 1 s (no motion), pause, back away. Before the
 * fix the back-away was recorded as ~1.3 s (timed from the blocked push); after, it is its own short
 * sample and the push is counted in `inputNoMotion`.
 *
 *   G1_GPU=nvidia node tools/g2/touch_blocked_check.mjs SITE [OUT.json]
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { launchOptions } from '../g1/gpu.mjs';
const [site, out] = process.argv.slice(2);
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
await p.goto(`${site}?view=play&game=free`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
const pose = () => p.evaluate(() => [...window.__cocoGame.renderer.pose].map((v) => +v.toFixed(3)));
const itm = () => p.evaluate(() => [...window.__cocoPerf.inputToMotion].map((v) => Math.round(v)));
console.log('start', await pose());
// turn to face +y or -y (KEY env), then drive forward until the drawn pose stops changing
const turnKey = process.env.TURN || 'KeyA';
await p.keyboard.down(turnKey);
for (let i = 0; i < 100; i++) { await p.waitForTimeout(50); const q = await pose(); if (Math.abs(Math.abs(q[2]) - 1.571) < 0.08) break; }
await p.keyboard.up(turnKey); await p.waitForTimeout(800);
console.log('turned', await pose());
await p.keyboard.down('KeyW');
let last = null, still = 0;
for (let i = 0; i < 150 && still < 5; i++) { await p.waitForTimeout(200); const q = JSON.stringify(await pose()); if (i % 10 === 0) console.log(' driving', q); still = q === last ? still + 1 : 0; last = q; }
await p.keyboard.up('KeyW');
console.log('blocked at', await pose(), 'samples', await itm());
await p.waitForTimeout(500);
const n0 = (await itm()).length;
await p.keyboard.down('KeyW'); await p.waitForTimeout(1000); await p.keyboard.up('KeyW');
console.log('after a 1 s push into the wall: pose', await pose(), 'new samples', (await itm()).slice(n0));
await p.waitForTimeout(200);
await p.keyboard.down('KeyS'); await p.waitForTimeout(600); await p.keyboard.up('KeyS');
const backed = await pose(), fresh = (await itm()).slice(n0);
const noMotion = await p.evaluate(() => window.__cocoPerf.inputNoMotion ?? null);
console.log('after backing away: pose', backed, 'new samples', fresh, 'inputNoMotion', noMotion ?? 'n/a (build has no G2.9 rule)');
const index = await p.evaluate(() => [...document.scripts].map((x) => x.src.split('/').pop()).join(' '));
await b.close();
const passed = noMotion === 1 && fresh.length === 1 && fresh[0] < 500 && backed[1] < 14.79;
console.log(passed ? 'PASS' : 'FAIL');
if (out) writeFileSync(out, JSON.stringify({ site, index, backed_pose: backed, new_samples_ms: fresh, input_no_motion: noMotion, passed }, null, 1) + '\n');
process.exitCode = passed ? 0 : 1;
