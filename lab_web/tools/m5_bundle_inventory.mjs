// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Loaded built JavaScript per route; byte inventory, not a startup-time measurement. */
import { chromium } from 'playwright';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { conditions } from './perf/conditions.mjs';
const web = join(dirname(fileURLToPath(import.meta.url)), '..');
const [out, site = 'http://127.0.0.1:4176/coco-labs/'] = process.argv.slice(2);
const start = conditions();
const browser = await chromium.launch();
const rows = [];
try {
  for (const route of ['arena', 'learn', 'play', 'casefiles', 'live']) {
    const page = await browser.newPage();
    const urls = new Set();
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname;
      if (path.includes('/assets/') && path.endsWith('.js')) urls.add(path.split('/').at(-1));
    });
    await page.goto(site + '?view=' + route);
    await page.waitForTimeout(5000);
    const assets = [...urls].map((file) => {
      const bytes = readFileSync(join(web, 'dist', 'assets', file));
      return { file, bytes: bytes.length, gzip_bytes: gzipSync(bytes).length };
    });
    rows.push({ route, assets, gzip_bytes: assets.reduce((sum, asset) => sum + asset.gzip_bytes, 0) });
    await page.close();
  }
} finally { await browser.close(); }
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify({ label: 'Built asset inventory; gzip level 6; excludes Python/WASM data', conditions: { start, end: conditions() }, rows }, null, 2) + '\n');
console.log(rows.map((row) => `${row.route}: ${row.gzip_bytes} gzip bytes`).join('\n'));
