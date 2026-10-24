// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.5 proof, step 1: a real browser run saved with "Save as rosbag2 (MCAP)" from the pause menu.
 * Fetch Rush seed 1 on the Depot: drive, then AUTO (so there is a plan) for SECONDS of wall time,
 * pause, press the button, keep the downloaded file.
 *
 *   G1_GPU=nvidia node tools/g2/bag_proof.mjs SITE OUT.mcap [SECONDS]
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
import { launchOptions } from '../g1/gpu.mjs';

const [site, out, secs = '45'] = process.argv.slice(2);
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true, serviceWorkers: 'block' });
const p = await ctx.newPage();
const errors = [];
p.on('pageerror', (e) => errors.push(String(e)));
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play&game=fetch_rush&seed=1`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
await p.keyboard.down('KeyW'); await p.waitForTimeout(3000); await p.keyboard.up('KeyW');
await p.click('[data-testid="hud-autonomy"]');
await p.waitForTimeout(Number(secs) * 1000);
const tick = await p.evaluate(() => window.__cocoGame.tick.tick);
await p.keyboard.press('Escape');
await p.waitForSelector('[data-testid="g1-pause-menu"]');
const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 60000 }), p.click('[data-testid="g2-save-bag"]')]);
await dl.saveAs(out);
const status = await p.textContent('[data-testid="g2-save-bag-status"]');
await b.close();
writeFileSync(`${out}.json`, JSON.stringify({ site, tick, suggested_name: dl.suggestedFilename(), status, errors, when: new Date().toISOString() }, null, 1) + '\n');
console.log(JSON.stringify({ tick, name: dl.suggestedFilename(), status, errors }));
