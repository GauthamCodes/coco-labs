// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R2.2: the sandbox escape tests (ADR 0012), through the real Algorithm Studio in a real browser.
 * Each hostile file is uploaded and run exactly as a visitor would; every one must FAIL SAFELY
 * (refused by the guard, stopped by the lockdown, ended by the time or memory limit, or capped),
 * the page must keep working, and a normal file must still run afterwards. Any escape that
 * succeeds is an R2 stop condition: the script exits 1.
 *
 *   node tools/r2/escape_check.mjs SITE OUT.json [--browser chromium|firefox|webkit] [--webkit-exe PATH]
 */
import { chromium, firefox, webkit } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [site, out, ...rest] = process.argv.slice(2);
const which = rest.includes('--browser') ? rest[rest.indexOf('--browser') + 1] : 'chromium';
const webkitExe = rest.includes('--webkit-exe') ? rest[rest.indexOf('--webkit-exe') + 1] : null;
const TEMPLATES = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'coco_lab', 'coco_lab', 'templates');
const P = 'from coco_lab.api import Pose2D, Twist\n';

/** [name, the prompt's category, file, what failing safely looks like] */
const CASES = [
  ['network: import js, fetch', 'network calls', `import js\n${P}def plan(c, s, g, ctx):\n    js.fetch('https://example.com/steal')\n    return None\n`, 'guard'],
  ['network: pyodide.http', 'network calls', `from pyodide.http import pyfetch\n${P}def plan(c, s, g, ctx):\n    return None\n`, 'guard'],
  ['network: urllib', 'network calls', `import urllib.request\ndef plan(c, s, g, ctx):\n    return None\n`, 'guard'],
  ['escape: object graph to sys', 'import js', `def plan(c, s, g, ctx):\n    return ().__class__.__base__.__subclasses__()\n`, 'guard'],
  ['escape: __import__("js")', 'import js', `def plan(c, s, g, ctx):\n    return __import__('js')\n`, 'guard'],
  ['escape: getattr dunder', 'import js', `def plan(c, s, g, ctx):\n    return getattr(ctx, '__class__')\n`, 'error'],
  ['escape: import js', 'import js', `import js\ndef plan(c, s, g, ctx):\n    return None\n`, 'guard'],
  ['escape: pyodide.ffi', 'import js', `import pyodide.ffi\ndef plan(c, s, g, ctx):\n    return None\n`, 'guard'],
  ['escape: generator frame', 'import js', `def plan(c, s, g, ctx):\n    gen = (i for i in [1])\n    return gen.gi_frame.f_globals\n`, 'guard'],
  ['DOM: document', 'DOM access', `def plan(c, s, g, ctx):\n    document.title = 'owned'\n    return None\n`, 'error'],
  ['DOM: js.document', 'DOM access', `import js\ndef plan(c, s, g, ctx):\n    js.document.body.innerHTML = 'owned'\n    return None\n`, 'guard'],
  ['storage: open a file', 'DOM access', `def plan(c, s, g, ctx):\n    open('/tmp/x', 'w').write('x')\n    return None\n`, 'error'],
  ['infinite loop (controller)', 'infinite loops', `${P}def control(state, scan, path, ctx):\n    while True:\n        pass\n`, 'time_limit'],
  ['memory: one huge allocation', 'memory blow-ups', `def plan(c, s, g, ctx):\n    x = bytearray(1536 * 1024 * 1024)\n    return None\n`, 'memory'],
  ['memory: a huge list', 'memory blow-ups', `def plan(c, s, g, ctx):\n    x = [0] * (400 * 1024 * 1024)\n    return None\n`, 'memory'],
  ['memory: growing list', 'memory blow-ups', `def plan(c, s, g, ctx):\n    keep = []\n    while True:\n        keep.append(bytearray(64 * 1024 * 1024))\n`, 'memory'],
  ['huge output: print', 'huge outputs', `def plan(c, s, g, ctx):\n    for i in range(300000):\n        print('x' * 60)\n    return None\n`, 'console_capped'],
  ['huge output: events', 'huge outputs', `def plan(c, s, g, ctx):\n    for i in range(400000):\n        ctx.emit('expand', x=s.x, y=s.y)\n    return None\n`, 'events_capped|time_limit'],
  ['huge output: path', 'huge outputs', `${P}def plan(c, s, g, ctx):\n    return [Pose2D(s.x, s.y)] * 250000\n`, 'invalid_output'],
];

const report = { site, browser: which, when: new Date().toISOString(), probe: null, cases: [], normal: [], page_errors: [], pass: false };
const engine = { chromium, firefox, webkit }[which];
const browser = await engine.launch(which === 'webkit' && webkitExe ? { executablePath: webkitExe } : {});
let failed = 0;
try {
  const ctx = await browser.newContext({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => report.page_errors.push(String(e)));
  const requests = [];
  page.on('request', (r) => requests.push(r.url()));
  await page.goto(`${site}?view=workbench&tab=studio`);
  await page.locator('[data-testid=studio-editor] .cm-content').waitFor({ timeout: 120000 });

  // 1. the lockdown's own probes
  await page.locator('[data-testid=studio-probe] summary').click();
  await page.locator('[data-testid=studio-probe-run]').click();
  await page.locator('[data-testid^="probe-"]').first().waitFor({ timeout: 180000 });
  const rows = await page.locator('[data-testid=studio-probe] tr').allInnerTexts();
  report.probe = Object.fromEntries(rows.map((r) => r.split('\t')));
  const reachable = Object.entries(report.probe).filter(([, v]) => !/^blocked/.test(v));
  console.log(reachable.length ? 'FAIL' : 'ok  ', `lockdown probes: ${rows.length} checked, ${reachable.length} reachable`, JSON.stringify(reachable));
  if (reachable.length) failed += 1;

  const upload = async (name, text) => {
    await page.locator('.studio-upload input').setInputFiles({ name, mimeType: 'text/x-python', buffer: Buffer.from(text) });
    await page.waitForTimeout(300);
  };
  const runAndWait = async (timeout = 240000) => {
    await page.locator('[data-testid=studio-run]').click();
    const t0 = Date.now();
    for (;;) {
      if (Date.now() - t0 > timeout) return { kind: 'hung' };
      if (await page.locator('[data-testid=studio-guard]').count()) return { kind: 'guard', text: await page.locator('[data-testid=studio-guard]').innerText() };
      const st = page.locator('[data-testid=studio-status-0]');
      if (await st.count()) {
        const s = await st.innerText();
        if (s !== 'running…' && !(await page.locator('.studio-right [role=status]').count())) {
          await page.getByRole('tab', { name: 'Validation' }).click();
          const val = await page.locator('.studio-right').innerText();
          await page.getByRole('tab', { name: 'Console' }).click();
          const con = await page.locator('[data-testid=studio-console]').innerText().catch(() => '');
          await page.getByRole('tab', { name: 'Results' }).click();
          return { kind: 'status', status: s, validation: val, console: con };
        }
      }
      await page.waitForTimeout(250);
    }
  };
  const runTemplate = async (file) => { await upload(file, readFileSync(join(TEMPLATES, file), 'utf8')); return runAndWait(); };

  for (const [name, category, code, want] of CASES) {
    const before = requests.length;
    await upload(`${name.replace(/\W+/g, '_')}.py`, code);
    const t0 = Date.now();
    const got = await runAndWait();
    const ms = Date.now() - t0;
    const external = requests.slice(before).filter((u) => !u.startsWith(site) && !u.startsWith('blob:') && !u.startsWith('data:'));
    const blob = `${got.text ?? ''} ${got.status ?? ''} ${got.validation ?? ''} ${got.console ?? ''}`;
    const accept = (w) => ({
      guard: got.kind === 'guard' && /not allowed|may be imported|SyntaxError/.test(got.text),
      error: got.kind === 'status' && /^error/.test(got.status),
      time_limit: got.kind === 'status' && /time_limit/.test(got.status),
      memory: got.kind === 'status' && (/memory_limit/.test(got.status) || /MemoryError/.test(blob)),
      console_capped: got.kind === 'status' && /more characters not kept/.test(got.console),
      events_capped: got.kind === 'status' && /not drawn|dropped/.test(got.validation),
      invalid_output: got.kind === 'status' && /^invalid_output/.test(got.status),
    })[w];
    const ok = external.length === 0 && got.kind !== 'hung' && want.split('|').some(accept);
    report.cases.push({ name, category, expected: want, ok, ms, outcome: got.kind === 'guard' ? `guard: ${got.text.slice(0, 160)}` : `status: ${got.status}`, external_requests: external });
    console.log(ok ? 'ok  ' : 'FAIL', `${category} · ${name} → ${got.kind === 'guard' ? 'refused by the guard' : got.status} (${ms} ms)`);
    if (!ok) failed += 1;
  }
  // the sandbox still works: the starter planner and controller run normally after all of that
  for (const file of ['planner_astar.py', 'controller_pure_pursuit.py']) {
    const got = await runTemplate(file);
    const ok = got.kind === 'status' && /^(found|succeeded)/.test(got.status) && /identical hash chains/.test(await page.locator('[data-testid=studio-det-0]').innerText());
    report.normal.push({ file, ok, status: got.status });
    console.log(ok ? 'ok  ' : 'FAIL', `after the escapes: ${file} → ${got.status}`);
    if (!ok) failed += 1;
  }
  if (report.page_errors.length) { console.log('FAIL page errors', report.page_errors); failed += 1; }
} finally {
  await browser.close();
}
report.pass = failed === 0;
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(report, null, 1) + '\n');
console.log(report.pass ? 'ESCAPE TESTS PASS: every escape failed safely' : `ESCAPE TESTS: ${failed} problem(s)`);
process.exit(report.pass ? 0 : 1);
