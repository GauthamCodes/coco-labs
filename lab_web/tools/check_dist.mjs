// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Static checks on a production build (`dist/`), for CI and for 1D-8.
 *
 *   node tools/check_dist.mjs [--base /coco-labs/] [--expect-hash HEX]
 *
 * 1. Every src/href in dist/index.html is under the base path (or data:).
 * 2. The CSP names exactly the pinned Pyodide CDN directory.
 * 3. No external URL appears in any built file except the pinned Pyodide
 *    directory, and a short, justified list of strings that are never
 *    fetched (XML namespace identifiers, React's error-page link text).
 * 4. Prints a sha256 over the whole tree (sorted paths + bytes), so two
 *    builds can be compared (`--expect-hash`).
 * The site's own text (catalog, bundles) is checked too: it names no URL.
 */

import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const here = new URL('..', import.meta.url).pathname;
const dist = join(here, 'dist');
const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };

const siteConfig = readFileSync(join(here, 'site.config.ts'), 'utf-8');
const base = opt('--base') ?? process.env.LAB_BASE ??
  siteConfig.match(/DEFAULT_BASE = '([^']+)'/)[1];
const version = siteConfig.match(/PYODIDE_VERSION = '([^']+)'/)[1];
const pyodide = `https://cdn.jsdelivr.net/pyodide/v${version}/full/`;

/** URL-shaped strings that are identifiers, not requests. */
const NOT_FETCHED = [
  /^http:\/\/www\.w3\.org\/(2000\/svg|1999\/xlink|1998\/Math\/MathML|XML\/1998\/namespace|1999\/xhtml)$/,
  /^https:\/\/react\.dev\/errors\/$/, // React builds an error message with this link text
  /^http:\/\/www\.apache\.org\/licenses\/LICENSE-2\.0$/, // the licence header of the embedded recompute.py
  // Phase 2 Part C: a hyperlink a visitor may follow from the Live tab when
  // no session is live (site.config DOCKER_QUICKSTART_URL). Navigation, not
  // a request the page makes.
  /^https:\/\/github\.com\/GauthamCodes\/coco-labs\/blob\/main\/docs\/DOCKER\.md$/,
];

const failures = [];
const walk = (d) => readdirSync(d).sort().flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
const files = walk(dist);

// 1 + 2: index.html
const html = readFileSync(join(dist, 'index.html'), 'utf-8');
for (const m of html.matchAll(/\s(?:src|href)="([^"]+)"/g)) {
  if (!(m[1].startsWith(base) || m[1].startsWith('data:'))) failures.push(`index.html: ${m[1]} is not under ${base}`);
}
const csp = html.match(/Content-Security-Policy"\s+content="([^"]+)"/)?.[1] ?? '';
if (!csp.includes(`script-src 'self' 'wasm-unsafe-eval' ${pyodide};`)) failures.push(`CSP does not pin ${pyodide}: ${csp}`);
// Phase 2 Part C: a configured remote session adds exactly its own host,
// as wss: (the socket) and https: (the /healthz probe). Unset: neither.
const remoteWs = siteConfig.match(/LIVE_REMOTE[^=]*= \{ ws: '(wss:\/\/[^/']+)[^']*' \}/)?.[1] ?? null;
if (!remoteWs && !/LIVE_REMOTE[^=]*= null;/.test(siteConfig)) failures.push('LIVE_REMOTE is neither null nor { ws: \'wss://...\' }');
const remoteHttps = remoteWs ? remoteWs.replace(/^wss:/, 'https:') : null;
// M0 fix A.2: the Live tab asks a LOCAL stack's /healthz before opening its
// socket, so LIVE_CONNECT_SRC_LOCAL may name loopback http: origins -- only
// loopback, and only exactly those listed there.
const liveListed = [...(siteConfig.match(/LIVE_CONNECT_SRC[^=]*= \[([^\]]*)\]/)?.[1] ?? '').matchAll(/'([^']+)'/g)]
  .map((m) => m[1]);
const localHttp = liveListed.filter((o) => o.startsWith('http'));
for (const o of localHttp) {
  if (!/^http:\/\/(localhost|127\.0\.0\.1):\*$/.test(o)) failures.push(`LIVE_CONNECT_SRC_LOCAL names a non-loopback http origin: ${o}`);
  if (!csp.split(/[\s;]+/).includes(o)) failures.push(`CSP lacks the local probe origin ${o}`);
}
if ((csp.match(/https?:\/\//g) ?? []).length !== 2 + (remoteHttps ? 1 : 0) + localHttp.length) failures.push(`CSP names another origin: ${csp}`);
if (remoteHttps && !csp.includes(` ${remoteHttps}`)) failures.push(`CSP lacks the remote probe origin ${remoteHttps}`);

// 5 (Phase 2): the Live tab may open WebSockets ONLY to LIVE_CONNECT_SRC
const live = liveListed.filter((o) => /^wss?:/.test(o)).concat(remoteWs ? [remoteWs] : []).sort();
const wsInCsp = (csp.match(/wss?:\/\/[^\s;]+/g) ?? []).sort();
if (!live.length || JSON.stringify(wsInCsp) !== JSON.stringify(live)) {
  failures.push(`CSP WebSocket origins ${JSON.stringify(wsInCsp)} != LIVE_CONNECT_SRC ${JSON.stringify(live)}`);
}

// 6 (Phase 2): the Live tab ships coco_web's own frame decoder, byte for byte
const frameSrc = readFileSync(join(here, '..', 'coco_web', 'web', 'frame.js'));
let frameDist = null;
try { frameDist = readFileSync(join(dist, 'coco', 'frame.js')); } catch { /* reported below */ }
if (!frameDist) failures.push('dist/coco/frame.js is missing');
else if (!frameDist.equals(frameSrc)) failures.push('dist/coco/frame.js differs from coco_web/web/frame.js');

// 3: external URLs anywhere in the build
const found = new Map();
for (const f of files) {
  if (!/\.(html|js|css|json|txt|map)$/.test(f)) continue;
  const text = readFileSync(f, 'utf-8');
  for (const m of text.matchAll(/https?:\/\/[^\s"'`)<>\\]+/g)) {
    const url = m[0];
    const ok = url.startsWith(pyodide) || (url === pyodide.slice(0, -1)) ||
      NOT_FETCHED.some((re) => re.test(url)) || url.startsWith('https://cdn.jsdelivr.net/pyodide/v${') ||
      // the configured remote session's probe origin, named in the CSP
      (remoteHttps !== null && f.endsWith('index.html') && url.replace(/;$/, '') === remoteHttps) ||
      // a local stack's /healthz origin, named in the CSP (checked above)
      (f.endsWith('index.html') && localHttp.includes(url.replace(/;$/, '')));
    const key = `${relative(dist, f)}: ${url}`;
    found.set(key, ok);
    if (!ok) failures.push(`external URL ${key}`);
  }
}
// the worker builds its URL from the pinned constant; make sure it is in the bundle
const workerFile = files.find((f) => /pyodide\.worker-.*\.js$/.test(f));
if (!workerFile) failures.push('no pyodide worker chunk in dist');
// M1.5: the page is code-split (main.tsx loads the v1 App or the Arena), so
// the pinned URL lives in an app chunk, not necessarily in index-*.js.
const pageJs = files.filter((f) => /assets\/[^/]+\.js$/.test(f) && !/\.worker-/.test(f))
  .map((f) => readFileSync(f, 'utf-8')).join('');
if (!pageJs.includes(pyodide)) failures.push(`the page bundle does not contain the pinned ${pyodide}`);
// M1.5: the Arena runs on the SELF-HOSTED Pyodide copy, which must be here
for (const f of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'pyodide-lock.json', 'python_stdlib.zip']) {
  if (!files.some((p) => p.endsWith(`generated/pyodide/${f}`))) failures.push(`self-hosted Pyodide lacks ${f}`);
}
if (!files.some((f) => /arena\.worker-.*\.js$/.test(f))) failures.push('no arena worker chunk in dist');
if (/document\.cookie\s*=|localStorage\.setItem|sessionStorage\.setItem|indexedDB\.open/.test(
  files.filter((f) => f.endsWith('.js')).map((f) => readFileSync(f, 'utf-8')).join(''))) {
  failures.push('the build writes a cookie or browser storage');
}

// 4: tree hash
const h = createHash('sha256');
for (const f of files) {
  h.update(relative(dist, f) + '\0');
  h.update(readFileSync(f));
  h.update('\0');
}
const tree = h.digest('hex');
const expect = opt('--expect-hash');
if (expect && expect !== tree) failures.push(`dist tree ${tree} != expected ${expect}`);

console.log(JSON.stringify({
  base, pyodide, files: files.length, bytes: files.reduce((s, f) => s + statSync(f).size, 0),
  urls: Object.fromEntries(found), tree_sha256: tree, failures,
}, null, 1));
process.exit(failures.length ? 1 : 0);
