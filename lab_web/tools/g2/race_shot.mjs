// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.6 / G2.7: Race Nav2 and the results screen, for review. Fetch Rush (phone) SEED with
 * race=nav2: the mode select offers it, the STACK ghost (a recorded Gazebo + Nav2 run) drives
 * beside COCO, AUTO drives COCO; at the round's end the results show the planner inset (MODEL)
 * and the three-way comparison (you, the model's planner, Nav2 in Gazebo).
 *
 *   G1_GPU=nvidia node tools/g2/race_shot.mjs SITE OUTDIR [SEED]
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { launchOptions } from '../g1/gpu.mjs';

const [site, out, seed = '2'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
const errors = [];
p.on('pageerror', (e) => errors.push(String(e)));
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play`);
await p.waitForTimeout(2500);
const offered = await p.locator('[data-testid="mode-race-nav2"]').count();
await p.screenshot({ path: `${out}/1-modes.png` });
await p.goto(`${site}?view=play&game=fetch_rush&seed=${seed}&race=nav2`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
await p.click('[data-testid="hud-autonomy"]');
await p.waitForTimeout(12000);
const chip = await p.locator('[data-testid="g2-race-chip"]').textContent().catch(() => null);
await p.screenshot({ path: `${out}/2-racing.png` });
await p.waitForSelector('[data-testid="g1-results"]', { timeout: 600000 });
await p.waitForTimeout(3000);
await p.screenshot({ path: `${out}/3-results.png`, fullPage: true });
const three = await p.locator('[data-testid="g2-threeway"]').textContent().catch(() => null);
const inset = await p.locator('[data-testid="g2-planner-inset"]').count();
await b.close();
const rep = { site, seed, offered_on_mode_select: offered > 0, race_chip: chip, threeway: three, inset: inset > 0, errors };
writeFileSync(`${out}/race.json`, JSON.stringify(rep, null, 1) + '\n');
console.log(JSON.stringify(rep));
