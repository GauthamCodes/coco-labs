// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/*
 * R5.2: Play connected to a running coco-ros2 container, end to end, in a real browser.
 *
 *   node tools/r5/live_e2e.mjs SITE OUT_DIR BROWSER CODE [--video]
 *   e.g. node tools/r5/live_e2e.mjs http://127.0.0.1:4184/coco-labs/ out chromium AB23CD45 --video
 *
 * The page: Free drive on the Depot -> PLAY -> Connect to ROS 2 (ws://localhost:8765, the control
 * code) -> the evidence chip says LIVE -> drive (W, 2 s) -> a goal (a click ahead, G) -> STOP (Space)
 * -> release (R) -> Disconnect -> the chip says MODEL. What happened is read from the STACK, not the
 * page: a spectator connection to the coco.v1 gateway (no code: it can watch, never command) records
 * Gazebo's truth, the arbiter, the STOP latch and Nav2's goal status. Evidence class: LIVE (a Gazebo
 * simulation running now, never hardware). Exit 0 only if every step passes.
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, firefox } from 'playwright';

const [site, out, browserName, code, ...rest] = process.argv.slice(2);
if (!site || !out || !browserName || !code) { console.error('usage: live_e2e.mjs SITE OUT BROWSER CODE [--video]'); process.exit(2); }
const video = rest.includes('--video');
// --lose CONTAINER: stop that container mid-session (the lost-connection case; it ends the run)
const lose = rest.includes('--lose') ? rest[rest.indexOf('--lose') + 1] : null;
const BRIDGE = 'ws://localhost:8765', GATEWAY = 'ws://localhost:8766/ws';
mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = { schema: 'coco_lab.r5.live_e2e', version: 1, site, browser: browserName, utc: new Date().toISOString(),
  evidence_class: "LIVE (COCO's ROS 2 stack running now: a Gazebo simulation, never hardware)", steps: {}, page_errors: [], console_errors: [] };

// the observer: a spectator on the gateway, as any second browser tab would be
let last = null;
const seen = [];
const obs = new WebSocket(GATEWAY);
await new Promise((res, rej) => { obs.onopen = res; obs.onerror = () => rej(new Error('the gateway did not answer')); });
obs.onmessage = (e) => { if (typeof e.data !== 'string') return; const m = JSON.parse(e.data); if (m.type === 'telemetry') { last = m; seen.push({ t: Date.now(), truth: m.robot?.truth, active: m.platform?.arbiter?.active, latched: m.platform?.stop?.latched, goal: m.nav?.goal?.status ?? null, path: m.nav?.path?.length ?? 0 }); } };
obs.send(JSON.stringify({ type: 'hello', client: 'r5-live-e2e observer', binary: false }));
const truth = () => (last?.robot?.truth ? [last.robot.truth.x, last.robot.truth.y] : null);
const d = (a, b) => (a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : null);
const until = async (f, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (f()) return true; await sleep(100); } return false; };

const B = browserName === 'firefox' ? firefox : chromium;
// Chromium on the laptop's GPU: headless Chromium's default SwiftShader drew one Play frame per ~1.1 s and
// starved the 100 ms drive timer past coco_web's 0.5 s dead-man (tools/r5/frame_gaps.mjs); a visitor's
// browser uses its GPU. The renderer is recorded.
const browser = await B.launch({ headless: true, ...(browserName === 'chromium' ? { args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] } : {}) });
const context = await browser.newContext({ viewport: { width: 1280, height: 720 }, ...(video ? { recordVideo: { dir: out, size: { width: 1280, height: 720 } } } : {}) });
// the tutorial has been seen (as tools/r3/live_smoke.mjs): its overlay would cover the HUD
await context.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch { /* none */ } });
const page = await context.newPage();
page.on('pageerror', (e) => rec.page_errors.push(String(e.message ?? e)));
page.on('console', (m) => { if (m.type() === 'error') rec.console_errors.push(m.text().slice(0, 300)); });
let code_ = 1;
try {
  await page.goto(`${site}?view=play&game=free`, { waitUntil: 'domcontentloaded' });
  await page.getByTestId('g1-play').waitFor({ state: 'visible', timeout: 120_000 });
  await page.waitForFunction(() => !document.querySelector('[data-testid="g1-play"]')?.hasAttribute('disabled'), null, { timeout: 180_000 });
  rec.renderer = await page.evaluate(() => { const c = document.createElement('canvas').getContext('webgl'); const x = c?.getExtension('WEBGL_debug_renderer_info'); return x ? c.getParameter(x.UNMASKED_RENDERER_WEBGL) : 'n/a'; });
  await page.getByTestId('g1-play').click();
  await page.getByTestId('r5-live-button').click();
  // the wrong port first: nothing listens on 9 -- the words must say so, and Play stays MODEL
  await page.getByTestId('r5-live-url').fill('ws://localhost:9');
  await page.getByTestId('r5-live-code').fill(code);
  await page.getByTestId('r5-live-connect').click();
  const wrongOk = await page.waitForFunction(() => /Could not connect/.test(document.querySelector('[data-testid="r5-live-status"]')?.textContent ?? ''), null, { timeout: 20_000 }).then(() => true, () => false);
  rec.steps.wrong_port = { words: await page.getByTestId('r5-live-status').textContent().catch(() => null), chip: await page.getByTestId('r5-evidence-chip').textContent(), ok: wrongOk };
  await page.getByTestId('r5-live-url').fill(BRIDGE);
  await page.getByTestId('r5-live-code').fill(code);
  await page.getByTestId('r5-live-connect').click();
  const liveOk = await page.waitForFunction(() => /LIVE/.test(document.querySelector('[data-testid="r5-evidence-chip"]')?.textContent ?? ''), null, { timeout: 45_000 }).then(() => true, () => false);
  rec.steps.connect = { chip_live: liveOk, status: await page.getByTestId('r5-live-status').textContent().catch(() => null) };
  await page.screenshot({ path: join(out, `${browserName}_1_live.png`) });
  await page.getByRole('button', { name: 'Close' }).first().click().catch(() => {});

  // drive: W for 2 s (the page claims with the code, so it is the driver)
  await page.locator('body').click({ position: { x: 640, y: 650 } }).catch(() => {});
  const p0 = truth();
  await page.keyboard.down('KeyW'); await sleep(2000);
  const activeWhile = last?.platform?.arbiter?.mode ?? null;   // the gateway reports `active` as null; `mode` is the arbiter's
  await page.keyboard.up('KeyW'); await sleep(800);
  rec.steps.drive = { moved_m: d(p0, truth()), arbiter_mode_while_driving: activeWhile };
  await page.screenshot({ path: join(out, `${browserName}_2_drive.png`) });

  // a goal: a click ahead of COCO in the chase view, then GO (G)
  const goalBefore = last?.nav?.goal?.sent_at ?? null;   // the gateway keeps the last goal: this one must be new
  // metres ahead, not inside Nav2's 0.25 m goal tolerance (a click at y=300 landed 0.2 m ahead: an instant 'succeeded')
  await page.mouse.click(640, 190); await sleep(400);
  await page.keyboard.press('KeyG');
  const goalOk = await until(() => (last?.nav?.goal?.sent_at ?? null) !== goalBefore && ['executing', 'accepted', 'succeeded'].includes(last?.nav?.goal?.status), 20_000);
  await sleep(1500);
  rec.steps.goal = { nav_status: last?.nav?.goal?.status ?? null, goal: last?.nav?.goal ? [last.nav.goal.x, last.nav.goal.y] : null, path_points: last?.nav?.path?.length ?? 0, ok: goalOk };
  // R5.3: Model vs LIVE -- the card fills both sides (the MODEL run in the page's worker, the LIVE leg to Nav2's verdict)
  const cmpOk = await page.waitForFunction(() => {
    const m = document.querySelector('[data-testid="r5-compare-model"]')?.textContent ?? '';
    const l = document.querySelector('[data-testid="r5-compare-live"]')?.textContent ?? '';
    return /driven/.test(m) && /succeeded|aborted|stopped/.test(l) && !/running/.test(m);
  }, null, { timeout: 60_000 }).then(() => true, () => false);
  rec.steps.compare = { ok: cmpOk, model: await page.getByTestId('r5-compare-model').textContent().catch(() => null),
    live: await page.getByTestId('r5-compare-live').textContent().catch(() => null), gap: await page.getByTestId('r5-compare-gap').textContent().catch(() => null) };
  await page.screenshot({ path: join(out, `${browserName}_3_goal.png`) });

  // the ROS 2 graph panel: the real nodes, from the bridge's connection graph
  await page.keyboard.press('KeyP');
  await page.getByTestId('g2-tab-graph').click();
  await page.getByTestId('r5-live-graph').waitFor({ timeout: 10_000 });
  await sleep(1500);
  const wheelsRow = await page.getByTestId('r5-live-topic-/diff_drive_controller/cmd_vel').textContent().catch(() => null);
  rec.steps.graph = { summary: await page.locator('[data-testid="r5-live-graph"] .g2-learn').textContent().catch(() => null),
    tag: await page.getByTestId('r5-panel-tag-live').textContent().catch(() => null), wheels_row: wheelsRow };
  await page.screenshot({ path: join(out, `${browserName}_3b_graph.png`) });
  await page.keyboard.press('KeyP');

  // STOP (Space): the latch is the gateway's, the wheels the arbiter's
  await page.keyboard.press('Space');
  const latchedOk = await until(() => last?.platform?.stop?.latched === true, 5000);
  await sleep(1000); const s0 = truth(); await sleep(1500); const s1 = truth();
  rec.steps.stop = { latched: latchedOk, arbiter_mode: last?.platform?.arbiter?.mode ?? null, moved_after_stop_m: d(s0, s1) };
  await page.screenshot({ path: join(out, `${browserName}_4_stop.png`) });
  await page.keyboard.press('KeyR');
  rec.steps.release = { released: await until(() => last?.platform?.stop?.latched === false, 5000) };

  // SIM view shows LIVE too
  await page.keyboard.press('KeyV'); await sleep(1500);
  rec.steps.sim = { caption: await page.getByTestId('g2-sim-caption').textContent().catch(() => null) };
  await page.screenshot({ path: join(out, `${browserName}_5_sim.png`) });

  // disconnect: back to MODEL -- by the visitor, or (--lose) because the container went away
  if (lose) execFileSync('docker', ['stop', '-t', '5', lose], { timeout: 60_000 });
  else { await page.getByTestId('r5-live-button').click(); await page.getByTestId('r5-live-disconnect').click(); }
  const modelOk = await page.waitForFunction(() => /MODEL/.test(document.querySelector('[data-testid="r5-evidence-chip"]')?.textContent ?? ''), null, { timeout: 30_000 }).then(() => true, () => false);
  if (lose) await page.getByTestId('r5-live-button').click().catch(() => {});
  rec.steps.disconnect = { how: lose ? 'container stopped' : 'Disconnect button', chip_model: modelOk, status: await page.getByTestId('r5-live-status').textContent().catch(() => null) };
  await page.screenshot({ path: join(out, `${browserName}_6_model.png`) });

  rec.acceptance = {
    wrong_port_said_in_words: rec.steps.wrong_port.ok && /MODEL/.test(rec.steps.wrong_port.chip ?? ''),
    connects_and_says_live: rec.steps.connect.chip_live,
    graph_shows_real_nodes: /cmd_vel_arbiter/.test(rec.steps.graph.wheels_row ?? '') && /LIVE/.test(rec.steps.graph.tag ?? ''),
    drive_moves_coco: (rec.steps.drive.moved_m ?? 0) > 0.1 && rec.steps.drive.arbiter_mode_while_driving === 'teleop',
    goal_reaches_nav2: rec.steps.goal.ok,
    model_vs_live_both_sides: rec.steps.compare.ok,
    stop_latches_and_holds: rec.steps.stop.latched && (rec.steps.stop.moved_after_stop_m ?? 1) < 0.02,
    release_unlatches: rec.steps.release.released,
    sim_says_live: /LIVE/.test(rec.steps.sim.caption ?? ''),
    disconnect_back_to_model: rec.steps.disconnect.chip_model && (!lose || /Lost the connection/.test(rec.steps.disconnect.status ?? '')),
    no_page_errors: rec.page_errors.length === 0,
  };
  rec.pass = Object.values(rec.acceptance).every(Boolean);
  code_ = rec.pass ? 0 : 1;
} catch (e) {
  rec.error = String(e?.message ?? e);
  await page.screenshot({ path: join(out, `${browserName}_error.png`) }).catch(() => {});
}
rec.observer_samples = seen.length;
await context.close();
await browser.close();
obs.close();
writeFileSync(join(out, `${browserName}.json`), JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify({ browser: browserName, pass: rec.pass ?? false, acceptance: rec.acceptance, steps: rec.steps, error: rec.error, page_errors: rec.page_errors }, null, 1));
process.exit(code_);
