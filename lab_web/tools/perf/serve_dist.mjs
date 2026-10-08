// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Serve lab_web/dist the way GitHub Pages does, for cold-start measurement.
 *
 *   node tools/perf/serve_dist.mjs [--port 4174] [--base /coco-labs/] [--host 127.0.0.1]
 *
 * `--host 0.0.0.0` lets a phone on the same Wi-Fi reach it (PHONE_MEASURE.md).
 *
 * `vite preview` sends every file uncompressed; GitHub Pages gzips
 * compressible types -- including application/wasm (measured 2026-10-08 on
 * a Pages-hosted 325 KB .wasm: `content-encoding: gzip`, docs/v2/COLDSTART.md).
 * This server gzips at level 6 when the browser accepts it, for html, js,
 * mjs, css, json, svg, wasm and txt, and sends .zip/.gz/.png as they are.
 * Nothing else is emulated: no CDN edge, no HTTP/2.
 */

import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1]]);
  return acc;
}, []));
const PORT = Number(args.port ?? 4174);
const BASE = args.base ?? '/coco-labs/';
const HOST = args.host ?? '127.0.0.1';
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'dist');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.wasm': 'application/wasm',
  '.txt': 'text/plain', '.zip': 'application/zip', '.gz': 'application/gzip', '.png': 'image/png',
  '.whl': 'application/zip', '.bin': 'application/octet-stream',
};
const COMPRESS = new Set(['.html', '.js', '.mjs', '.css', '.json', '.svg', '.wasm', '.txt']);
const cache = new Map();

createServer((req, res) => {
  const url = decodeURIComponent((req.url ?? '/').split('?')[0]);
  if (!url.startsWith(BASE)) { res.writeHead(404).end(); return; }
  let file = resolve(ROOT, normalize(url.slice(BASE.length)));
  if (!file.startsWith(ROOT + sep) && file !== ROOT) { res.writeHead(403).end(); return; }
  if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
  if (!existsSync(file)) { res.writeHead(404).end(); return; }
  const ext = extname(file);
  const headers = { 'Content-Type': TYPES[ext] ?? 'application/octet-stream', 'Cache-Control': 'no-cache' };
  let body = readFileSync(file);
  if (COMPRESS.has(ext) && /\bgzip\b/.test(req.headers['accept-encoding'] ?? '')) {
    const st = statSync(file);
    const key = `${file}:${st.mtimeMs}:${st.size}`; // a rebuild invalidates it
    if (!cache.has(key)) cache.set(key, gzipSync(body, { level: 6 }));
    body = cache.get(key);
    headers['Content-Encoding'] = 'gzip';
    headers.Vary = 'Accept-Encoding';
  }
  headers['Content-Length'] = body.length;
  res.writeHead(200, headers).end(body);
}).listen(PORT, HOST, () => console.log(`serving ${ROOT} at http://${HOST}:${PORT}${BASE} (gzip like Pages)`));
