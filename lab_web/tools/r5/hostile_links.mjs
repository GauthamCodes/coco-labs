// R5.6 security: hostile #level= links in Play and the World editor. Each must fail in words (or be ignored),
// run no script, open no dialog, and leave the page working.
//   node tools/r5/hostile_links.mjs SITE OUT.json [chromium|firefox]
import { writeFileSync } from 'node:fs';
import { deflateRawSync } from 'node:zlib';
import { chromium, firefox } from 'playwright';
const [site, out, which = 'chromium'] = process.argv.slice(2);
const tok = (obj, pad = 0) => 'v1.' + deflateRawSync(Buffer.from(JSON.stringify(obj) + ' '.repeat(pad))).toString('base64url');
const XSS = '<img src=x onerror="window.__pwned=1">';
const spec = { spec_version: 'coco.world_spec.v3', id: 'editor_x', title: XSS, frame: 'world', world_to_map: [0, 0],
  bounds: { x_min: 0, x_max: 10, y_min: 0, y_max: 8 }, start: { x: 2, y: 2, theta: 0 }, kit: [] };
const CASES = [
  ['deflate bomb (8 MB of JSON in a few kB)', tok({ spec, goals: [] }, 8 * 1024 * 1024)],
  ['not base64', 'v1.%%%%'], ['wrong version', 'v9.abc'], ['huge token', 'v1.' + 'A'.repeat(300000)],
  ['script in the title, invalid spec', tok({ spec, goals: [[1, 1]] })],
  ['broken editor state', tok({ spec, goals: [], editor: { title: XSS, w: 'x', pieces: 'boom' } })],
  ['goals not numbers', tok({ spec, goals: [['a', 'b']] })],
];
const b = await (which === 'firefox' ? firefox : chromium).launch({ headless: true });
const res = { browser: which, cases: [], pass: true };
for (const [name, t] of CASES) {
  for (const view of ['play', 'editor']) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 720 } });
    await ctx.addInitScript(() => { try { localStorage.setItem('coco.prefs.v1.tutorial', 'true'); } catch {} });
    const page = await ctx.newPage();
    const errs = []; let dialog = false;
    page.on('pageerror', (e) => errs.push(e.message)); page.on('dialog', (d) => { dialog = true; void d.dismiss(); });
    const url = view === 'play' ? `${site}?view=play&game=free#level=${t}` : `${site}?view=workbench&tab=editor#level=${t}`;
    await page.goto(url); await page.waitForTimeout(view === 'play' ? 8000 : 9000);
    const text = (await page.locator('body').innerText()).replace(/\s+/g, ' ');
    const pwned = await page.evaluate(() => window.__pwned === 1);
    const alive = await page.evaluate(() => document.body.children.length > 0 && !!document.querySelector('#root, main, [data-testid]'));
    const words = view === 'play' ? (text.match(/(level link[^.]*|no level in this link|not a v1[^.]*|holds no World Spec[^.]*|goals are not[^.]*|could not[^.]{0,80}|refus[^.]{0,80}|boot: \w*Error: [^\n]{0,120})/i)?.[0] ?? null) : (/World editor/.test(text) ? 'editor open' : null);
    const ok = !pwned && !dialog && alive && errs.length === 0 && !!words;
    res.pass &&= ok;
    res.cases.push({ name, view, ok, words, pwned, dialog, page_errors: errs.slice(0, 3) });
    await ctx.close();
  }
}
await b.close();
writeFileSync(out, JSON.stringify(res, null, 1));
console.log(JSON.stringify({ browser: which, pass: res.pass, failed: res.cases.filter((c) => !c.ok) }));
process.exit(res.pass ? 0 : 1);
