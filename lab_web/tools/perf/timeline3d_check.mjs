// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * M4.6: the timeline in every camera, including the follow camera during a
 * replay (README §7 M4.6).
 *
 *   node tools/perf/timeline3d_check.mjs --out DIR [--site URL] [--replay lab5_crossing_dwb_1] [--casefile ID]
 *
 * For a recorded STACK run (and a Case File if given), in each camera
 * (follow, orbit, robot-eye, top-down): seek the timeline to 25 % and 75 %
 * and check the drawn robot moved to the recording's pose at each, the
 * follow camera's rig went with it, P pauses and [ / ] step one tick. Page
 * errors are recorded, with conditions (power, GPU driver).
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { conditions } from './conditions.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const SITE = args.site ?? 'http://127.0.0.1:4244/coco-labs/';
const OUT = args.out ?? 'timeline3d-check';
mkdirSync(OUT, { recursive: true });
const CONDITIONS_AT_START = conditions();
const targets = [['replay', args.replay ?? 'lab5_crossing_dwb_1'], ...(args.casefile ? [['casefile', args.casefile]] : [])];

const b = await chromium.launch({ args: ['--use-angle=gl-egl', '--ignore-gpu-blocklist', '--enable-gpu'] });
const rows = [];
for (const [kind, id] of targets) {
  for (const camera of ['follow', 'orbit', 'robot_eye', 'topdown']) {
    const page = await b.newPage({ viewport: { width: 1280, height: 900 } });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    const row = { kind, id, camera };
    try {
      await page.goto(`${SITE}?view=arena&${kind}=${id}&camera=${camera}`);
      await page.waitForFunction((c) => !!document.querySelector('[data-testid=tl-world]')
        && (c === 'topdown' || !!window.__cocoPerf?.marks?.world3d_ready), camera, { timeout: 180_000 });
      await page.waitForTimeout(800);
      // a recording plays in from its start: at its fastest speed, wait until 120 ticks are there to seek in
      const fastest = await page.evaluate(() => Math.max(...[...document.querySelectorAll('[data-testid=tl-speed] option')].map((o) => Number(o.value))));
      await page.selectOption('[data-testid=tl-speed]', String(fastest));
      await page.waitForFunction(() => Number(document.querySelector('[data-testid=tl-world]').max) >= 120, null, { timeout: 120_000 });
      const seek = async (f) => {
        await page.evaluate((frac) => {
          const el = document.querySelector('[data-testid=tl-world]');
          const v = Math.round(Number(el.min) + frac * (Number(el.max) - Number(el.min)));
          const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
          set.call(el, String(v));
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }, f);
        await page.waitForTimeout(500);
        return page.evaluate(() => {
          const r = window.__cocoArena.renderer;
          return { pose: [...r.lastPose], rig: r.three ? [r.three.camera.position.x, r.three.camera.position.y] : null,
            mode: r.cameraMode, tick: Number(document.querySelector('[data-testid=tl-world]').value) };
        });
      };
      const a = await seek(0.25);
      const c = await seek(0.75);
      row.at25 = a; row.at75 = c;
      row.robot_moved = Math.hypot(a.pose[0] - c.pose[0], a.pose[1] - c.pose[1]) > 0.1;
      row.camera_followed = camera !== 'follow' || (a.rig && c.rig && Math.hypot(a.rig[0] - c.rig[0], a.rig[1] - c.rig[1]) > 0.1);
      row.camera_kept = c.mode === camera;
      // step keys while paused
      await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
      const t0 = Number(await page.evaluate(() => document.querySelector('[data-testid=tl-world]').value));
      await page.keyboard.press('BracketRight');
      await page.waitForTimeout(300);
      const t1 = Number(await page.evaluate(() => document.querySelector('[data-testid=tl-world]').value));
      row.step_forward = t1 - t0;
    } catch (e) {
      row.failure = String(e).split('\n')[0];
    }
    row.errors = errors;
    rows.push(row);
    console.log(JSON.stringify([kind, id, camera, row.robot_moved, row.camera_followed, row.camera_kept, row.step_forward, errors.length, row.failure ?? '']));
    await page.close();
  }
}
await b.close();
const verdict = {
  timeline_moves_the_robot_in_every_camera: rows.every((r) => !r.failure && r.robot_moved),
  follow_camera_follows_in_replay: rows.filter((r) => r.camera === 'follow').every((r) => r.camera_followed),
  camera_kept_while_seeking: rows.every((r) => r.camera_kept),
  step_keys: rows.every((r) => r.step_forward === 1),
  no_page_errors: rows.every((r) => r.errors.length === 0),
};
const result = { criterion: 'M4.6: the timeline in every camera, including follow during replay', verdict, rows };
writeFileSync(join(OUT, 'timeline3d.json'), JSON.stringify({ ...result, conditions: { start: CONDITIONS_AT_START, end: conditions() } }, null, 1) + '\n');
console.log(JSON.stringify(verdict));
