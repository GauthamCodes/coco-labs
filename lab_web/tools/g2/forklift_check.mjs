// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2 rules 5: does a forklift (or walker) ever drive through COCO in the browser? (MODEL)
 *
 * Fetch Rush (Full shift) SEED on the built site SITE; AUTO's goals are sent through the session's goal
 * input (exactly what GO and AUTO send: a `goal` row; the model plans and drives). Three legs:
 *   A  cross the east-west forklift lane next to the dock walker (start -> CROSS_TO);
 *   B  park in the lane (PARK) and wait for the forklift to come;
 *   C  drive on along the lane past the forklift (8 m beyond COCO, on the forklift's side).
 * Every tick the page reports (window.__cocoGame.tick) is logged: COCO's pose and each actor's pose
 * as the model drew it. Overlap = an actor's box (its footprint at that pose) within COCO's radius
 * of COCO's centre (box distance < radius). Reports the minimum clearance, the overlap ticks, the
 * refused (blocked) ticks, the actors' held ticks, AUTO's states and whether each leg arrived, and
 * saves screenshots (desktop) of the first tick a forklift stops for COCO (rules 5 builds).
 *
 *   node tools/g2/forklift_check.mjs SITE OUTDIR [SEED] [LABEL]
 *
 * Run it on the rules-5 build and on a rules-4 build (the before) with the same arguments.
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import { launchOptions, renderer } from '../g1/gpu.mjs';

const [site, out, seed = '2', label = 'run'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const CROSS_TO = [40.0, 15.5];
const PARK = [36.0, 11.0];
const LEG_S = { A: 150, B: 60, C: 150 };

const b = await chromium.launch(launchOptions());
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, serviceWorkers: 'block' });
const p = await ctx.newPage();
p.setDefaultTimeout(600000);
const errors = [];
p.on('pageerror', (e) => errors.push(String(e)));
await p.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
await p.goto(`${site}?view=play&game=fetch_rush&mode=full&seed=${seed}`);   // the Full shift: its timer outlasts the legs
await p.waitForSelector('[data-testid="g1-play"]:not([disabled])', { timeout: 600000 });
await p.click('[data-testid="g1-play"]');
await p.waitForFunction(() => (window.__cocoGame?.tick?.tick ?? 0) > 3, null, { timeout: 300000 });
const gpu = await renderer(p);
// log every tick the page shows
await p.evaluate(() => {
  window.__fk = [];
  let last = -1;
  setInterval(() => {
    const t = window.__cocoGame?.tick;
    if (!t || t.tick === last) return;
    last = t.tick;
    window.__fk.push({ tick: t.tick, pose: t.pose, blocked: t.blocked, arrived: t.arrived, mode: t.mode,
      actors: t.game?.actors ?? [], held: t.game?.actors_held ?? [], avoid: t.game?.avoid?.state ?? null });
  }, 15);
});
const info = await p.evaluate(() => {
  const w = window.__cocoGame.session.world;
  return { radius: w.radius, actors: w.game.actors, rules_setup: w.game.setup.map((r) => r.choice ?? r.kind) };
});
const foot = Object.fromEntries(info.actors.map((a) => [a.id, a.footprint]));
const boxDist = (px, py, [id, x, y, yaw]) => {
  const [L, W] = foot[id];
  const c = Math.cos(yaw), s = Math.sin(yaw), rx = px - x, ry = py - y;
  const lx = c * rx + s * ry, ly = -s * rx + c * ry;
  return Math.hypot(Math.max(Math.abs(lx) - L / 2, 0), Math.max(Math.abs(ly) - W / 2, 0));
};
const goal = (xy) => p.evaluate(([x, y]) => window.__cocoGame.session.goal(x, y), xy);
const tickNow = () => p.evaluate(() => window.__cocoGame.tick.tick);
const legs = {};
let shot = null;

async function leg(name, xy, seconds, waitForHeld = false) {
  const t0 = await tickNow();
  if (xy) await goal(xy);
  const end = Date.now() + seconds * 1000 * 3;     // the page's clock may run slow on a loaded laptop
  let arrived = false;
  while (Date.now() < end) {
    await p.waitForTimeout(250);
    const log = await p.evaluate((k) => window.__fk.filter((r) => r.tick > k), t0);
    const simS = log.length ? (log[log.length - 1].tick - t0) / 10 : 0;
    arrived = arrived || log.some((r) => r.arrived);
    const held = log.find((r) => r.held.some((id) => id.startsWith('forklift')));
    if (held && !shot && label.startsWith('after')) {
      await p.screenshot({ path: `${out}/forklift_stops_${label}_chase.png` });
      await p.evaluate(() => window.__cocoGame.renderer.setGameCamera('tactical'));
      await p.waitForTimeout(600);
      await p.screenshot({ path: `${out}/forklift_stops_${label}_tactical.png` });
      await p.evaluate(() => window.__cocoGame.renderer.setGameCamera('chase'));
      shot = held.tick;
    }
    if (waitForHeld ? (held && simS > 3) || simS >= seconds : (arrived || simS >= seconds)) break;
  }
  legs[name] = { goal: xy, from_tick: t0, to_tick: await tickNow(), arrived };
}

await leg('A', CROSS_TO, LEG_S.A);
await leg('B', PARK, LEG_S.B);
await leg('B_wait', null, LEG_S.B, true);
const here = await p.evaluate(() => window.__cocoGame.tick);
const fk = here.game.actors.find((a) => a[0] === 'forklift_east_west');
const dir = Math.sign(fk[1] - here.pose[0]) || 1;
await leg('C', [Math.min(45, Math.max(17, here.pose[0] + 8 * dir)), 11.0], LEG_S.C);
const log = await p.evaluate(() => window.__fk);
await b.close();

let minClear = Infinity, overlapTicks = 0, blockedTicks = 0, heldTicks = 0, closest = null;
const states = {};
for (const r of log) {
  for (const a of r.actors) {
    const c = boxDist(r.pose[0], r.pose[1], a) - info.radius;
    if (c < minClear) { minClear = c; closest = { tick: r.tick, actor: a[0], clearance_m: c }; }
  }
  if (r.actors.some((a) => boxDist(r.pose[0], r.pose[1], a) < info.radius)) overlapTicks++;
  blockedTicks += r.blocked ? 1 : 0;
  heldTicks += r.held.length ? 1 : 0;
  if (r.avoid) states[r.avoid] = (states[r.avoid] ?? 0) + 1;
}
const ticks = log.map((r) => r.tick);
const missed = ticks.length ? (ticks[ticks.length - 1] - ticks[0] + 1) - ticks.length : 0;
const rep = { site, seed, label, gpu, evidence: 'MODEL', setup: info.rules_setup, radius: info.radius,
  overlap: 'box distance from COCO centre < radius', ticks_logged: log.length, ticks_missed_by_the_poller: missed,
  legs, min_clearance_m: minClear, closest, overlap_ticks: overlapTicks, blocked_ticks: blockedTicks,
  ticks_with_an_actor_held: heldTicks, avoid_states: states, forklift_stop_screenshot_tick: shot, errors };
writeFileSync(`${out}/forklift_check_${label}.json`, JSON.stringify(rep, null, 1) + '\n');
console.log(JSON.stringify(rep));
const after = label.startsWith('after');
if (after && (overlapTicks > 0 || !legs.A.arrived || !legs.C.arrived)) process.exitCode = 1;
