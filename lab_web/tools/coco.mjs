#!/usr/bin/env node
// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The `coco` command (M3.6; R1 adds `experiment`):
 *
 *   coco verify <link>...            re-score Play challenge links, no browser
 *   coco verify --file FILE.json     a file of links or submissions
 *   coco experiment run SPEC.json|yaml --out DIR [--workers N]
 *                                    run an experiment natively (CPython: coco_lab.experiments)
 *   coco experiment verify DIR [--sample F]   re-run an export's runs and compare
 *   coco experiment summarise DIR
 *
 * `experiment` hands its arguments to `python -m coco_lab.experiments` (PYTHON, else
 * python3; coco_lab installed, or this checkout's on PYTHONPATH), with COCO_WORLDS at this
 * checkout's worlds/. A YAML spec is read here (coco_lab is standard library only) and
 * passed on as JSON. From lab_web: `npx coco ...` (package.json "bin"), or
 * `node tools/coco.mjs ...`.
 */
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === 'verify') {
  const { main } = await import('./verify.mjs');
  process.exit(await main(rest));
}
if (cmd === 'experiment') {
  const repo = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
  const args = [...rest];
  if (args[0] === 'run' && /\.ya?ml$/i.test(args[1] ?? '')) {
    const { parse } = await import('yaml');
    const json = join(mkdtempSync(join(tmpdir(), 'coco-exp-')), 'spec.json');
    writeFileSync(json, JSON.stringify(parse(readFileSync(args[1], 'utf-8'))));
    args[1] = json;
  }
  const env = { ...process.env, COCO_WORLDS: process.env.COCO_WORLDS ?? join(repo, 'worlds') };
  env.PYTHONPATH = [join(repo, 'coco_lab'), process.env.PYTHONPATH].filter(Boolean).join(':');
  const r = spawnSync(process.env.PYTHON ?? 'python3', ['-m', 'coco_lab.experiments', ...args], { stdio: 'inherit', env });
  process.exit(r.status ?? 1);
}
console.error('usage: coco verify <link>... | coco verify --file FILE.json [--out OUT.json]\n'
  + '       coco experiment run SPEC.json|SPEC.yaml --out DIR [--workers N] | coco experiment verify DIR | coco experiment summarise DIR');
process.exit(2);
