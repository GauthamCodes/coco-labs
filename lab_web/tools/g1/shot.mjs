// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1: one screenshot of one URL in one profile, after a ready selector; optional
 * actions (press PLAY, hold W for N ms). A development check, not evidence.
 *   node tools/g1/shot.mjs URL OUT.png [--profile desktop|landscape|portrait] [--ready SEL] [--play] [--drive MS] [--wait MS]
 */
import { chromium } from 'playwright';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';
const [url, out, ...rest] = process.argv.slice(2);
const opt = (k, d) => { const i = rest.indexOf(k); return i >= 0 ? rest[i + 1] : d; };
const has = (k) => rest.includes(k);
const prof = opt('--profile', 'desktop');
const b = await chromium.launch({ ...(process.env.G1_CHROMIUM ? { executablePath: process.env.G1_CHROMIUM } : {}), args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist'] });
const ctx = await b.newContext(prof === 'desktop' ? { viewport: { width: 1440, height: 900 } } : nothingPhone1(prof === 'landscape'));
const p = await ctx.newPage();
const errors = [];
p.on('pageerror', (e) => errors.push(String(e)));
p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
if (!has('--tutorial')) await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(url);
await p.waitForSelector(opt('--ready', 'body'), { timeout: 180000 }).catch((e) => errors.push('ready: ' + e.message.split('\n')[0]));
if (has('--play')) { await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 180000 }); await p.click('[data-testid="g1-play"]'); await p.waitForTimeout(800); }
const drive = Number(opt('--drive', 0));
if (drive) { await p.keyboard.down('KeyW'); await p.waitForTimeout(drive); await p.keyboard.up('KeyW'); }
for (const k of (opt('--keys', '') || '').split(',').filter(Boolean)) { await p.keyboard.press(k); await p.waitForTimeout(400); }
await p.waitForTimeout(Number(opt('--wait', 1500)));
await p.screenshot({ path: out });
console.log(out, errors.length ? errors.slice(0, 3) : 'no errors');
await b.close();
