#!/usr/bin/env node
// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The `coco` command (M3.6). One subcommand so far:
 *
 *   coco verify <link>...            re-score Play challenge links, no browser
 *   coco verify --file FILE.json     a file of links or submissions
 *
 * From lab_web: `npx coco verify ...` (package.json "bin"), or
 * `node tools/coco.mjs verify ...`.
 */

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === 'verify') {
  const { main } = await import('./verify.mjs');
  process.exit(await main(rest));
}
console.error('usage: coco verify <link>... | coco verify --file FILE.json [--out OUT.json]');
process.exit(2);
