// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

import { DEFAULT_BASE, PYODIDE_INDEX_URL, PYODIDE_VERSION } from './site.config.ts';

const base = process.env.LAB_BASE ?? DEFAULT_BASE;

export default defineConfig({
  base,
  plugins: [
    react(),
    {
      // index.html's CSP names the pinned Pyodide directory; fill it from
      // site.config.ts so the two can never disagree.
      name: 'coco-lab-csp',
      transformIndexHtml: (html: string) => html.replaceAll('%PYODIDE_INDEX_URL%', PYODIDE_INDEX_URL),
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
