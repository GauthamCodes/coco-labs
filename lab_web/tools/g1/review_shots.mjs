// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1.13 review: the surfaces as they stand, on the laptop GPU (G1_GPU), desktop 1440 x 900, for the
 * written review (docs/v2/g1/G1_REVIEW.md): title; Play (Fetch Rush) chase, Robot vision on, tactical
 * camera, the "what is real here" sheet; Compare; Research (Recordings); M5's Arena (?view=arena).
 *
 *   G1_GPU=nvidia node tools/g1/review_shots.mjs SITE OUTDIR
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { launchOptions, renderer } from './gpu.mjs';
const [site, out] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
const shots = [];
const snap = async (name) => { await p.screenshot({ path: `${out}/${name}.png` }); shots.push(name); };
await p.goto(site); await p.getByTestId('title').waitFor({ timeout: 120000 }); await p.waitForTimeout(3000); await snap('01-title');
await p.goto(`${site}?view=play`); await p.waitForTimeout(2500); await snap('02-modes');
await p.goto(`${site}?view=play&game=fetch_rush&seed=1&tier=high`);
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 300000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 5, null, { timeout: 120000 });
await p.keyboard.down('KeyW'); await p.waitForTimeout(2500); await p.keyboard.up('KeyW'); await p.waitForTimeout(1500);
await snap('03-play-chase');
await p.keyboard.press('KeyV'); await p.waitForTimeout(5000); await snap('04-play-robot-vision');
await p.keyboard.press('KeyC'); await p.waitForTimeout(2500); await snap('05-play-tactical-vision');
await p.keyboard.press('KeyC'); await p.waitForTimeout(1500);
await p.keyboard.press('KeyV'); await p.waitForTimeout(500);
await p.getByRole('button', { name: 'What is real here' }).click(); await p.waitForTimeout(800); await snap('06-play-what-is-real');
await p.goto(`${site}?view=compare`); await p.waitForSelector('[data-ready="true"]', { timeout: 180000 }); await p.waitForTimeout(4000); await snap('07-compare');
await p.goto(`${site}?view=research`); await p.waitForTimeout(5000); await snap('08-research');
await p.goto(`${site}?view=arena`); await p.waitForTimeout(12000); await snap('09-m5-arena');
writeFileSync(`${out}/shots.json`, JSON.stringify({ site, renderer: await renderer(p), shots, when: new Date().toISOString() }, null, 1) + '\n');
await b.close();
