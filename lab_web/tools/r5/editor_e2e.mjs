// R5.5: the world editor end to end in a real browser: a small level built from scratch by mouse, checked
// live, used in an experiment, played (Free drive on it, AUTO to its goal), downloaded as a ROS 2 package.
//   node tools/r5/editor_e2e.mjs SITE OUT_DIR [chromium|firefox]
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { chromium, firefox } from 'playwright';
const [site, out, which = 'chromium'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const B = which === 'firefox' ? firefox : chromium;
const b = await B.launch({ headless: true, ...(which === 'chromium' ? { args: ['--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist'] } : {}) });
// tall enough that the whole 12 x 9 m canvas is on screen (a pointer outside the viewport reaches nothing)
const ctx = await b.newContext({ viewport: { width: 1280, height: 1400 }, acceptDownloads: true });
await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
const page = await ctx.newPage();
const rec = { browser: which, steps: {}, page_errors: [] };
page.on('pageerror', (e) => rec.page_errors.push(String(e.message ?? e)));
await page.goto(`${site}?view=workbench&tab=editor`);
const cv = page.getByTestId('r5-canvas');
await page.waitForFunction(() => /checking|valid|not/.test(document.querySelector('[data-testid="r5-check"]')?.textContent ?? ''), null, { timeout: 120000 });
// world (x, y) -> page pixel, from the canvas's own geometry (12 x 9 m level, 20 px margin)
const px = async (x, y) => { const r = await cv.boundingBox(); const s = await cv.evaluate((c) => [c.width, c.height]); const scale = (s[0] - 40) / 12;
  return [r.x + (20 + x * scale) * r.width / s[0], r.y + (20 + (9 - y) * scale) * r.height / s[1]]; };
const tool = (t) => page.getByTestId(`r5-tool-${t}`).click();
const click = async (x, y) => { const [a, c] = await px(x, y); await page.mouse.click(a, c); await page.waitForTimeout(150); };
await tool('wall'); { const [a, c] = await px(6, 0); const [d, e] = await px(6, 9); await page.mouse.move(a, c); await page.mouse.down(); await page.mouse.move(d, e, { steps: 8 }); await page.mouse.up(); }
await tool('door'); await click(6, 4.5);
await tool('bench'); await click(9, 2);
await tool('rack'); await click(3, 6.5);
await tool('start'); await click(2, 2);
await tool('goal'); await click(10, 7); await click(3, 3.5);
await page.getByTestId('r5-title').fill('Two rooms');
const ok = await page.waitForFunction(() => /valid/.test(document.querySelector('[data-testid="r5-check"]')?.textContent ?? ''), null, { timeout: 60000 }).then(() => true, () => false);
rec.steps.build = { check_ok: ok, check: await page.getByTestId('r5-check').textContent(), goals: await page.getByTestId('r5-goals').textContent() };
await page.screenshot({ path: join(out, `${which}_1_level.png`) });
// a broken edit is said in words: a goal inside the closed rack's footprint is still reachable by snapping; instead block the door
// (an experiment)
await page.getByTestId('r5-experiment').click();
await page.waitForFunction(() => document.querySelector('[data-testid="r5-exp"]') || /could not|add a goal/.test(document.querySelector('[data-testid="r5-status"]')?.textContent ?? ''), null, { timeout: 180000 });
rec.steps.experiment_status = await page.getByTestId('r5-status').textContent();
rec.steps.experiment = { rows: await page.locator('[data-testid="r5-exp"] tbody tr').allTextContents() };
// play it
const [play] = await Promise.all([ctx.waitForEvent('page'), page.getByTestId('r5-play').click()]);
play.on('pageerror', (e) => rec.page_errors.push('play: ' + String(e.message ?? e)));
const ready = await play.waitForFunction(() => { const b = document.querySelector('[data-testid="g1-play"]'); return (b && !b.hasAttribute('disabled')) || document.querySelector('[role="alert"]'); }, null, { timeout: 180000 }).then(() => true, () => false);
const alert = await play.locator('[role="alert"]').allTextContents();
if (alert.length) { rec.steps.play = { error: alert.join(' | ').slice(0, 1500), url: play.url().slice(0, 120) }; writeFileSync(join(out, `${which}.json`), JSON.stringify(rec, null, 1)); console.log(JSON.stringify(rec)); process.exit(1); }
await play.getByTestId('g1-play').click(); await play.waitForTimeout(1500);
const primary = await play.getByTestId('hud-primary').getAttribute('aria-label');
const title = await play.getByTestId('objective').textContent();
await play.getByTestId('hud-primary').click();                      // GO (the on-screen button G presses)
const auto = await play.waitForFunction(() => /AUTO/i.test(document.querySelector('[data-testid="mode-chip"]')?.textContent ?? ''), null, { timeout: 15000 }).then(() => true, () => false);
await play.waitForTimeout(4000);
const speed = await play.getByTestId('speed').textContent();
const rosout = await play.getByTestId('g2-rosout').textContent().catch(() => null);
const primaryAfter = await play.getByTestId('hud-primary').getAttribute('aria-label');
rec.steps.play = { url_has_level: /#level=v1\./.test(play.url()), url: play.url(), title, primary_at_start: primary, auto, speed, rosout, primary_after: primaryAfter };
await play.screenshot({ path: join(out, `${which}_2_play.png`) });
await play.close();
// the package
const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 120000 }), page.getByTestId('r5-package').click()]);
await dl.saveAs(join(out, `${which}_${dl.suggestedFilename()}`));
rec.steps.package = { file: dl.suggestedFilename() };
// a broken level is refused in words: block the door with a box
await page.bringToFront(); await cv.scrollIntoViewIfNeeded();
await tool('box'); await click(6, 4.5);
rec.steps.box_pieces = await page.locator('.r5-ed-list').textContent();
await page.screenshot({ path: join(out, `${which}_2b_box.png`) });
await page.waitForFunction(() => /not reachable|not fit|refus|overlap/i.test(document.querySelector('[data-testid="r5-check"]')?.textContent ?? ''), null, { timeout: 30000 }).catch(() => {});
rec.steps.broken = { check: await page.getByTestId('r5-check').textContent() };
await page.getByTestId('r5-undo').click(); await page.waitForTimeout(800);
rec.steps.undo = { check: await page.getByTestId('r5-check').textContent() };
await page.screenshot({ path: join(out, `${which}_3_after_undo.png`) });
rec.pass = rec.steps.build.check_ok && rec.steps.experiment.rows.length === 4 && rec.steps.play.url_has_level && rec.steps.play.auto
  && /TWO ROOMS/.test(rec.steps.play.title ?? '') && !!rec.steps.package.file && /valid/.test(rec.steps.undo.check ?? '') && !/valid/.test(rec.steps.broken.check ?? '') && rec.page_errors.length === 0;
writeFileSync(join(out, `${which}.json`), JSON.stringify(rec, null, 1) + '\n');
console.log(JSON.stringify(rec));
await b.close();
