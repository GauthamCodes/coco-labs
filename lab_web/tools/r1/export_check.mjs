// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.6: a Workbench export is the native export. Run a small control experiment in the
 * browser, download "Export with traces", and require:
 *   - the zip holds results.csv, summary.json, spec.json, runs.jsonl, manifest.json and one
 *     MCAP trace per run (each a valid MCAP with one message per tick);
 *   - the manifest's checksums are those of the files;
 *   - results.csv and summary.json equal `coco experiment run` of the same spec (CPython)
 *     byte for byte once the wall-clock column and statistics are removed.
 *
 *   node tools/r1/export_check.mjs SITE OUT_DIR --python PY
 */
import { chromium } from 'playwright';
import { McapStreamReader } from '@mcap/core';
import { Unzip, UnzipInflate } from 'three/addons/libs/fflate.module.js';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [site, out, ...rest] = process.argv.slice(2);
const python = rest.includes('--python') ? rest[rest.indexOf('--python') + 1] : 'python3';
const repo = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
mkdirSync(out, { recursive: true });
const SPEC = { schema: 'coco.experiment.v1', title: 'Export check: two controllers', world: 'coco_arena_v1', family: 'control', seed: 3,
  algorithms: [{ name: 'builtin' }, { name: 'rpp' }], scenarios: { kind: 'sampled', n: 2, seed: 3, min_separation_m: 2.5 }, limits: { max_ticks: 400 } };
const report = { site, when: new Date().toISOString(), checks: [], pass: false };
const check = (name, ok, extra = {}) => { report.checks.push({ name, ok, ...extra }); console.log(ok ? 'ok  ' : 'FAIL', name, JSON.stringify(extra).slice(0, 160)); };

function unzip(bytes) {
  const files = {};
  const u = new Unzip((f) => { const parts = []; f.ondata = (err, d, final) => { if (err) throw err; parts.push(d); if (final) { const o = new Uint8Array(parts.reduce((n, p) => n + p.length, 0)); let k = 0; for (const p of parts) { o.set(p, k); k += p.length; } files[f.name] = o; } }; f.start(); });
  u.register(UnzipInflate);
  u.push(bytes, true);
  return files;
}
const noTimingCsv = (t) => { const rows = t.trim().split('\n').map((r) => r.split(',')); const k = rows[0].indexOf('compute_ms'); return rows.map((r) => r.filter((_, j) => j !== k).join(',')).join('\n'); };
const noTimingSummary = (s) => { const j = JSON.parse(s); for (const g of j.groups) delete g.metrics.compute_ms; for (const p of j.paired) delete p.metrics.compute_ms; return JSON.stringify(j); };

const b = await chromium.launch();
try {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  await p.goto(`${site}?view=workbench`);
  await p.locator('.wb-text summary').click();
  await p.locator('.wb-text textarea').fill(JSON.stringify(SPEC));
  await p.getByRole('button', { name: 'Apply the text' }).click();
  await p.locator('.wb-runbar button[type=submit]').click();
  await p.locator('[data-testid="wb-digest"]').waitFor({ timeout: 900000 });
  const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 900000 }), p.getByRole('button', { name: 'Export with traces' }).click()]);
  const zipPath = join(out, dl.suggestedFilename());
  await dl.saveAs(zipPath);
  const files = unzip(new Uint8Array(readFileSync(zipPath)));
  const names = Object.keys(files).map((n) => n.split('/').slice(1).join('/')).sort();
  const get = (n) => Object.entries(files).find(([k]) => k.endsWith('/' + n))?.[1];
  const text = (n) => new TextDecoder().decode(get(n));
  check('the zip holds the export set', ['manifest.json', 'results.csv', 'runs.jsonl', 'spec.json', 'summary.json'].every((n) => names.includes(n)), { names });
  const man = JSON.parse(text('manifest.json'));
  check('manifest checksums match', Object.entries(man.files).every(([n, f]) => createHash('sha256').update(get(n)).digest('hex') === f.sha256));
  const mcaps = names.filter((n) => n.endsWith('.mcap'));
  const runs = text('runs.jsonl').trim().split('\n').map((l) => JSON.parse(l));
  let messages = 0, ok = mcaps.length === runs.length;
  for (const n of mcaps) {
    const r = new McapStreamReader(); r.append(get(n)); let rec, count = 0;
    while ((rec = r.nextRecord())) if (rec.type === 'Message') count++;
    const run = runs[Number(/run_(\d+)/.exec(n)[1])];
    ok &&= count === run.metrics.ticks; messages += count;
  }
  check('one valid MCAP per run, one message per tick', ok, { mcaps: mcaps.length, runs: runs.length, messages });
  writeFileSync(join(out, 'spec.json'), JSON.stringify(SPEC));
  const nat = spawnSync(python, ['-m', 'coco_lab.experiments', 'run', join(out, 'spec.json'), '--out', join(out, 'native'), '--workers', '2'],
    { env: { ...process.env, PYTHONPATH: join(repo, 'coco_lab'), COCO_WORLDS: join(repo, 'worlds') }, encoding: 'utf-8' });
  check('native run', nat.status === 0, { stderr: nat.stderr?.slice(-200) });
  check('results.csv = native (wall time removed)', noTimingCsv(text('results.csv')) === noTimingCsv(readFileSync(join(out, 'native', 'results.csv'), 'utf-8')));
  check('summary.json = native (wall time removed)', noTimingSummary(text('summary.json')) === noTimingSummary(readFileSync(join(out, 'native', 'summary.json'), 'utf-8')));
  check('digest = native', man.digest === JSON.parse(readFileSync(join(out, 'native', 'manifest.json'), 'utf-8')).digest, { digest: man.digest });
  report.pass = report.checks.every((c) => c.ok);
} catch (e) { report.error = String(e); console.log('FAIL', String(e)); }
await b.close();
writeFileSync(join(out, 'export_check.json'), JSON.stringify(report, null, 1) + '\n');
process.exit(report.pass ? 0 : 1);
