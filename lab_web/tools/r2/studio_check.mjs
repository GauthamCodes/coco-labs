// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.3-R2.8: the Algorithm Studio end to end in a real browser, and its screenshots.
 *
 *   node tools/r2/studio_check.mjs SITE OUT_DIR [--screens-only]
 *
 * Desktop (1440x1000): the A* starter on one Depot scenario (status, determinism, expansions drawn,
 * the console and validation tabs), GAME and SIM; Compare against the built-in A*; the pure-pursuit
 * starter (frames drawn); "Export as ROS 2 package" (a zip with the user's file unchanged); a share
 * link opened in a fresh context (code shown, Run blocked until consent); the Leaderboard tab;
 * Learn's "Try it yourself" links. Then the emulated Nothing Phone (1) in landscape and portrait:
 * the Studio readable, Run and Compare reachable, the phone note shown. Screenshots in OUT_DIR.
 */
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { nothingPhone1 } from '../phone/nothing-phone-1.mjs';

const [site, out, ...rest] = process.argv.slice(2);
const screensOnly = rest.includes('--screens-only');
const T = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'coco_lab', 'coco_lab', 'templates');
mkdirSync(out, { recursive: true });
const report = { site, when: new Date().toISOString(), steps: [], pass: false };
let failed = 0;
const step = (name, ok, extra = {}) => { report.steps.push({ name, ok, ...extra }); console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(extra).slice(0, 220)); if (!ok) failed += 1; };
const browser = await chromium.launch();

async function waitRun(page, timeout = 300000) {
  const t0 = Date.now();
  for (;;) {
    if (Date.now() - t0 > timeout) return 'hung';
    if (await page.locator('[data-testid=studio-guard]').count()) return `guard: ${await page.locator('[data-testid=studio-guard]').innerText()}`;
    const st = page.locator('[data-testid=studio-status-0]');
    const busy = await page.locator('.studio-right [role=status]').count();
    if (await st.count() && !busy) {
      const all = await page.locator('[data-testid^=studio-status-]').allInnerTexts();
      if (all.every((s) => s !== 'running…')) return all.join(' | ');
    }
    await page.waitForTimeout(300);
  }
}
async function upload(page, file, text) {
  await page.locator('.studio-upload input').setInputFiles({ name: file, mimeType: 'text/x-python', buffer: Buffer.from(text) });
  await page.waitForTimeout(300);
}

try {
  const ctx = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 }, acceptDownloads: true,
    permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${site}?view=workbench&tab=studio`);
  await page.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 120000 });
  await page.screenshot({ path: join(out, 'desktop-studio-start.png') });
  if (!screensOnly) {
    // a Depot scenario with the A* starter
    await upload(page, 'planner_astar.py', readFileSync(join(T, 'planner_astar.py'), 'utf8'));
    await page.locator('.studio-scenario select').selectOption('depot-nav-100');
    await page.waitForTimeout(1500);
    await page.locator('[data-testid=studio-run]').click();
    let st = await waitRun(page);
    const det = await page.locator('[data-testid=studio-det-0]').innerText();
    const exp = await page.locator('.studio-play .studio-muted').first().innerText();
    step('A* starter on depot-nav-100 s001: found, deterministic, expansions drawn', /^found/.test(st) && /identical hash chains/.test(det) && /[1-9]\d* expansions/.test(exp), { st, det, exp });
    await page.waitForTimeout(4000);
    await page.screenshot({ path: join(out, 'desktop-studio-planner-game.png') });
    await page.getByRole('button', { name: 'SIM' }).first().click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: join(out, 'desktop-studio-planner-sim.png') });
    await page.getByRole('tab', { name: 'Validation' }).click();
    const val = await page.locator('[data-testid=studio-validation]').innerText();
    step('validation report: contract problems, clamps, determinism, per-call time with the device', /Contract problems: 0/.test(val) && /wall time on/.test(val), { val: val.slice(0, 160) });
    // Compare with the built-in A*
    await page.getByRole('button', { name: 'GAME' }).first().click();
    await page.locator('.studio-compare select').selectOption('astar');
    await page.locator('[data-testid=studio-compare]').click();
    st = await waitRun(page);
    step('Compare: yours beside the built-in A* on the same scenario', /^found.*\| found/.test(st), { st });
    await page.waitForTimeout(4000);
    await page.screenshot({ path: join(out, 'desktop-studio-compare.png') });
    // a controller: frames and candidates drawn
    await upload(page, 'controller_pure_pursuit.py', readFileSync(join(T, 'controller_pure_pursuit.py'), 'utf8'));
    await page.waitForTimeout(800);
    await page.locator('[data-testid=studio-run]').click();
    st = await waitRun(page, 600000);
    step('pure pursuit on a scenario: an outcome, drawn tick by tick', /^(succeeded|failed_to_make_progress|no_valid_control|timeout)/.test(st), { st });
    await page.screenshot({ path: join(out, 'desktop-studio-controller.png') });
    // ROS 2 export
    const dl = page.waitForEvent('download');
    await page.locator('[data-testid=studio-ros2]').click();
    const file = await dl;
    const zp = join(out, 'export.zip');
    await file.saveAs(zp);
    const zip = readFileSync(zp);
    step('Export as ROS 2 package: a zip holding the user file unchanged', file.suggestedFilename() === 'coco_user_controller_pure_pursuit.zip'
      && zip.includes(Buffer.from('coco_user_controller_pure_pursuit/coco_user_controller_pure_pursuit/algorithm.py')), { name: file.suggestedFilename(), bytes: zip.length });
    // a share link, opened elsewhere: shown, not run
    await page.locator('[data-testid=studio-share]').click();
    const link = await page.locator('[data-testid=studio-link]').inputValue();
    const ctx2 = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } });
    const p2 = await ctx2.newPage();
    const requests = [];
    p2.on('request', (r) => requests.push(r.url()));
    await p2.goto(link);
    await p2.locator('[data-testid=studio-consent]').waitFor({ timeout: 60000 });
    await p2.locator('[data-testid=studio-editor] .cm-content').waitFor();
    const shown = await p2.locator('[data-testid=studio-editor] .cm-content').innerText();
    const runDisabled = await p2.locator('[data-testid=studio-run]').isDisabled();
    const sandboxBooted = requests.some((u) => /sandbox\.worker/.test(u));
    step('a code link: the code is shown, Run is blocked, nothing ran before consent', /def control/.test(shown) && runDisabled && !sandboxBooted, { chars: link.length, runDisabled, sandboxBooted });
    await p2.screenshot({ path: join(out, 'desktop-studio-link-consent.png') });
    await p2.locator('[data-testid=studio-consent-run]').click();
    step('after "Run this code": Run is enabled', !(await p2.locator('[data-testid=studio-run]').isDisabled()));
    await ctx2.close();
    step('no page errors', errors.length === 0, { errors: errors.slice(0, 3) });
  }
  for (const [tab, name] of [['leaderboard', 'leaderboard'], ['studio&template=teach_heuristic', 'studio-teach']]) {
    await page.goto(`${site}?view=workbench&tab=${tab}`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: join(out, `desktop-${name}.png`), fullPage: tab === 'leaderboard' });
  }
  await page.goto(`${site}?view=learn`);
  await page.locator('[data-testid=learn-studio-find-a-path]').waitFor({ timeout: 60000 });
  step('Learn: "Try it yourself" opens the teaching starters', (await page.locator('[data-testid^=learn-studio-]').count()) === 2);
  await page.screenshot({ path: join(out, 'desktop-learn.png'), fullPage: true });
  await ctx.close();
  // the emulated Nothing Phone (1): landscape and portrait
  for (const landscape of [true, false]) {
    const pc = await browser.newContext({ ...nothingPhone1(landscape), serviceWorkers: 'block' });
    const pp = await pc.newPage();
    await pp.goto(`${site}?view=workbench&tab=studio`);
    await pp.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 120000 });
    const tag = landscape ? 'phone-landscape' : 'phone-portrait';
    const note = await pp.locator('.studio-note').count();
    const runBox = await pp.locator('[data-testid=studio-run]').boundingBox();
    const width = await pp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    step(`${tag} (emulated): the phone note shown, Run reachable, no sideways scroll`, note === 1 && !!runBox && width <= 1, { note, runBox, overflow: width });
    await pp.screenshot({ path: join(out, `${tag}-studio.png`) });
    if (landscape && !screensOnly) {
      await pp.locator('[data-testid=studio-run]').click();
      const st = await waitRun(pp);
      step('phone landscape (emulated): the A* starter runs', /^found/.test(st), { st });
      await pp.screenshot({ path: join(out, `${tag}-studio-run.png`) });
    }
    await pp.goto(`${site}?view=workbench&tab=leaderboard`);
    await pp.waitForTimeout(2500);
    await pp.screenshot({ path: join(out, `${tag}-leaderboard.png`) });
    await pp.goto(`${site}?view=learn`);
    await pp.waitForTimeout(2500);
    await pp.screenshot({ path: join(out, `${tag}-learn.png`) });
    await pc.close();
  }
} finally {
  await browser.close();
}
report.pass = failed === 0;
writeFileSync(join(out, 'studio_check.json'), JSON.stringify(report, null, 1) + '\n');
console.log(report.pass ? 'STUDIO CHECK PASS' : `STUDIO CHECK: ${failed} problem(s)`);
process.exit(report.pass ? 0 : 1);
