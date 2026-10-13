// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * `coco verify` (M3.6): re-score a Play submission, with no browser and no server.
 *
 *   node tools/coco.mjs verify <link> [<link> ...]
 *   node tools/coco.mjs verify --file FILE.json [--out RESULT.json]
 *
 * A link is a Play challenge link (?view=play&c=..&l=..&s=..; src/play/share.ts).
 * FILE.json holds {"links": [...]} or {"submissions": [...]}. Each submission
 * is re-scored by coco_lab.play.score -- the SAME Python the page runs in its
 * worker -- under Pyodide in Node, on the site's own coco_lab packs, the
 * committed levels (lab_web/play/levels.json) and the World Spec. A link
 * carries the result hash it scored; verify says whether the recomputed
 * result has that hash, and exits 1 if any does not.
 *
 * Needs the site's generated assets (npm run arena-assets, or the build).
 */

import { inflateRawSync } from 'node:zlib';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..');
const GEN = join(WEB, 'public', 'generated');

/** Decode a challenge link (the inverse of src/play/share.ts's encodeScore). */
export function decodeLink(link) {
  const q = new URL(link, 'https://x/').searchParams;
  const c = q.get('c'); const l = q.get('l'); const s = q.get('s'); const z = q.get('z');
  if (!c || !l || !(s || z)) throw new Error(`not a Play challenge link: ${link.slice(0, 80)}`);
  // z (M4.8): the payload deflated (src/play/share.ts); s: the same JSON, plain
  const raw = Buffer.from((z ?? s).replace(/-/g, '+').replace(/_/g, '/'), 'base64');
  const j = JSON.parse(Buffer.from(z ? inflateRawSync(raw, { maxOutputLength: 4 * 1024 * 1024 }) : raw).toString('utf-8'));
  if (j.v !== 1 || !/^[0-9a-f]{64}$/.test(j.h ?? '') || !/^[0-9a-f]{64}$/.test(j.r ?? '')) throw new Error('a malformed challenge link');
  return { submission: { v: 1, challenge: c, level: l, level_hash: j.h, inputs: j.i }, result_hash: j.r };
}

/** Boot Pyodide in Node with coco_lab and every pack; return score(submission). */
export async function scorer() {
  const { loadPyodide } = await import('pyodide');
  const py = await loadPyodide({ indexURL: join(WEB, 'node_modules', 'pyodide') + '/', stdLibURL: join(GEN, 'pyodide', 'python_stdlib.zip') });
  py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', 'coco_lab.zip'))), 'zip', { extractDir: '/home/pyodide' });
  const mf = JSON.parse(readFileSync(join(GEN, 'arena', 'manifest.json'), 'utf-8'));
  for (const p of Object.values(mf.packs ?? {})) py.unpackArchive(new Uint8Array(readFileSync(join(GEN, 'arena', p.file))), 'zip', { extractDir: '/home/pyodide' });
  py.runPython("import sys\nif '/home/pyodide' not in sys.path: sys.path.insert(0, '/home/pyodide')\nimport json\nfrom coco_lab import play");
  const levels = readFileSync(join(WEB, 'play', 'levels.json'), 'utf-8');
  const spec = readFileSync(join(GEN, 'arena', 'coco_arena_v1.json'), 'utf-8');
  py.globals.set('LEVELS_JSON', levels);
  py.globals.set('SPEC_JSON', spec);
  py.runPython('LEVELS = json.loads(LEVELS_JSON)\nSPEC = json.loads(SPEC_JSON)');
  const run = py.runPython('lambda s: json.dumps(play.score(LEVELS, json.loads(s), SPEC))');
  const view = py.runPython('lambda c, l: json.dumps(play.view(LEVELS, c, l))');
  return {
    version: `Pyodide ${py.version}, Node ${process.version}`,
    levels: JSON.parse(levels),
    score(submission) { return JSON.parse(run(JSON.stringify(submission))); },
    /** coco_lab.play.view: the level, its hash and what the page draws */
    view(challenge, level) { return JSON.parse(view(challenge, level)); },
  };
}

export async function main(argv) {
  const opt = (k) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : null; };
  let items = [];
  const file = opt('--file');
  if (file) {
    const j = JSON.parse(readFileSync(file, 'utf-8'));
    if (j.links) items = j.links.map((l) => ({ link: l, ...decodeLink(l) }));
    else items = (j.submissions ?? []).map((s) => ({ submission: s, result_hash: null }));
  } else {
    items = argv.filter((a) => !a.startsWith('--') && a !== opt('--out')).map((l) => ({ link: l, ...decodeLink(l) }));
  }
  if (!items.length) { console.error('usage: coco verify <link>... | --file FILE.json [--out OUT.json]'); return 2; }
  const s = await scorer();
  const t0 = Date.now();
  const rows = [];
  for (const it of items) {
    const t = Date.now();
    let r; let error = null;
    try { r = s.score(it.submission); } catch (e) { error = String(e.message ?? e).split('\n').slice(-2).join(' '); }
    const row = { challenge: it.submission.challenge, level: it.submission.level, ms: Date.now() - t,
      hash: r?.hash ?? null, stars: r?.stars ?? null, valid: r?.valid ?? null, score: r?.score ?? null,
      expected: it.result_hash, matches: it.result_hash ? r?.hash === it.result_hash : null, error };
    rows.push(row);
    console.log(`${row.matches === false || error ? 'MISMATCH' : row.matches ? 'verified' : 'scored  '} ${row.challenge}/${row.level}: `
      + `${error ?? `${row.score?.name} ${row.score?.value}, ${row.stars} stars, hash ${row.hash.slice(0, 12)}`} (${row.ms} ms)`);
  }
  const bad = rows.filter((r) => r.matches === false || r.error).length;
  const out = { tool: 'coco verify (lab_web/tools/verify.mjs)', engine: s.version, seconds: (Date.now() - t0) / 1000,
    checked: rows.filter((r) => r.matches !== null).length, matched: rows.filter((r) => r.matches).length, failures: bad, rows };
  if (opt('--out')) writeFileSync(opt('--out'), JSON.stringify(out, null, 1) + '\n');
  console.log(`${rows.length} re-scored on ${s.version}: ${out.matched} of ${out.checked} links matched, ${bad} failures`);
  return bad ? 1 : 0;
}
