// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

import { DEFAULT_BASE, liveConnectSrc, PYODIDE_INDEX_URL, PYODIDE_VERSION } from './site.config.ts';

/** coco_web's own binary-frame decoder: shipped as-is, never ported. */
const FRAME_JS = fileURLToPath(new URL('../coco_web/web/frame.js', import.meta.url));

const base = process.env.LAB_BASE ?? DEFAULT_BASE;

/**
 * Serve `*.gz` as the file's own bytes (`application/gzip`, NO
 * `Content-Encoding`). Vite's static server marks `.gz` files
 * `Content-Encoding: gzip`, so the browser would inflate `arrays.bin.gz`
 * before the decoder saw it, and the decoder -- which checks the gzip magic
 * and never repairs -- would refuse every gzipped bundle (measured in 1D-4).
 * This fixes the SERVER, for `vite` and `vite preview`; GitHub Pages is a
 * different server, checked separately.
 */
function gzipAsBytes(root: string) {
  return (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const url = decodeURIComponent((req.url ?? '').split('?')[0]);
    if (!url.startsWith(base) || !url.endsWith('.gz')) return next();
    const file = resolve(root, url.slice(base.length));
    if (!file.startsWith(resolve(root) + sep) || !existsSync(file)) return next();
    res.setHeader('Content-Type', 'application/gzip');
    res.setHeader('Content-Length', statSync(file).size);
    res.setHeader('Cache-Control', 'no-cache');
    createReadStream(file).pipe(res);
  };
}

export default defineConfig({
  base,
  plugins: [
    react(),
    {
      name: 'coco-lab-gzip-as-bytes',
      configureServer: (server) => {
        server.middlewares.use(gzipAsBytes(resolve(server.config.root, 'public')));
      },
      configurePreviewServer: (server) => {
        server.middlewares.use(gzipAsBytes(resolve(server.config.root, 'dist')));
      },
    },
    {
      // index.html's CSP names the pinned Pyodide directory; fill it from
      // site.config.ts so the two can never disagree.
      name: 'coco-lab-csp',
      transformIndexHtml: (html: string) => html.replaceAll('%PYODIDE_INDEX_URL%', PYODIDE_INDEX_URL)
        .replaceAll('%LIVE_CONNECT_SRC%', liveConnectSrc().join(' ')),
    },
    {
      // The Live tab decodes binary sensor frames with coco_web/web/frame.js
      // itself: copied byte for byte into the build (check_dist.mjs compares
      // them) and served from the same path by the dev server.
      name: 'coco-lab-frame-js',
      configureServer: (server) => {
        server.middlewares.use((req, res, next) => {
          if ((req.url ?? '').split('?')[0] !== `${base}coco/frame.js`) return next();
          res.setHeader('Content-Type', 'text/javascript');
          createReadStream(FRAME_JS).pipe(res);
        });
      },
      generateBundle() {
        this.emitFile({ type: 'asset', fileName: 'coco/frame.js', source: readFileSync(FRAME_JS) });
      },
    },
  ],
  define: {
    // The site footer names the commit it was built from. Local builds say
    // "local" so two local builds stay byte-identical.
    __BUILD_COMMIT__: JSON.stringify(process.env.GITHUB_SHA ?? 'local'),
    __PYODIDE_VERSION__: JSON.stringify(PYODIDE_VERSION),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2022',
  },
  worker: {
    format: 'es',
  },
  test: {
    include: ['test/**/*.test.ts', 'test/**/*.test.tsx'],
    environment: 'node',
    testTimeout: 60_000,
  },
});
