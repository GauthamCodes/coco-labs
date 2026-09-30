// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * The ONE place the site's deployment constants live.
 *
 * `DEFAULT_BASE` is the GitHub Pages project path (the repository's name).
 * `vite.config.ts` uses it unless the environment variable `LAB_BASE`
 * overrides it (e.g. `LAB_BASE=/ npm run build` for a root-served copy).
 * Application code never writes a path prefix: it uses Vite's
 * `import.meta.env.BASE_URL`, which is this value at build time.
 *
 * The Pyodide pin is here too, because both `index.html`'s CSP and the
 * worker must name exactly the same CDN directory (a test asserts it).
 */
export const DEFAULT_BASE = '/coco-robot-jazzy-2.0/';

/** Looked up 2026-09-30 (GitHub releases + npm); Python 3.14.2 inside. */
export const PYODIDE_VERSION = '314.0.7';
export const PYODIDE_INDEX_URL =
  `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
