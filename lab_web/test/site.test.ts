// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

// Source-level guarantees the build checks (tools/check_dist.mjs) rely on.

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

import { DEFAULT_BASE, PYODIDE_INDEX_URL, PYODIDE_VERSION } from '../site.config';
import { LAB_WEB } from './helpers';

const walk = (d: string): string[] => readdirSync(d).flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
const src = walk(join(LAB_WEB, 'src')).map((p) => ({ p, text: readFileSync(p, 'utf-8') }));

describe('deployment constants', () => {
  it('the base path is the repository name, defined once', () => {
    expect(DEFAULT_BASE).toBe('/coco-labs/');
    for (const { p, text } of src) expect(text.includes('coco-labs'), p).toBe(false);
    const vite = readFileSync(join(LAB_WEB, 'vite.config.ts'), 'utf-8');
    expect(vite).toMatch(/process\.env\.LAB_BASE \?\? DEFAULT_BASE/);
  });

  it('Pyodide is pinned once and the CSP is filled from the pin', () => {
    expect(PYODIDE_VERSION).toBe('314.0.7');
    expect(PYODIDE_INDEX_URL).toBe('https://cdn.jsdelivr.net/pyodide/v314.0.7/full/');
    const html = readFileSync(join(LAB_WEB, 'index.html'), 'utf-8');
    expect(html).toContain("script-src 'self' 'wasm-unsafe-eval' %PYODIDE_INDEX_URL%");
    expect(html).not.toMatch(/https?:\/\//);
    for (const { p, text } of src) expect(/cdn\.jsdelivr|pyodide\/v\d/.test(text), p).toBe(false);
  });

  it('the Node version is pinned for CI and dev', () => {
    expect(readFileSync(join(LAB_WEB, '.nvmrc'), 'utf-8').trim()).toBe('24.21.0');
    const pkg = JSON.parse(readFileSync(join(LAB_WEB, 'package.json'), 'utf-8'));
    for (const deps of [pkg.dependencies, pkg.devDependencies]) {
      for (const [name, v] of Object.entries<string>(deps)) expect(v, name).toMatch(/^\d+\.\d+\.\d+$/);
    }
  });
});

describe('privacy', () => {
  it('src sets no cookie, uses no browser storage and sends no analytics', () => {
    for (const { p, text } of src) {
      expect(/document\.cookie|localStorage|sessionStorage|indexedDB|sendBeacon|navigator\.userAgent/.test(text), p)
        .toBe(false);
    }
  });

  it('the ONE cross-origin request is the Live probe, to LIVE_REMOTE\'s /healthz only', () => {
    // Phase 2 Part C: "is a session live?" asks the configured endpoint.
    // It is in exactly one place, fed only from site.config's LIVE_REMOTE,
    // and sends no credentials (status.ts). Nothing else leaves the origin.
    const callers = src.filter(({ text }) => /fetch\(u, init\)/.test(text)).map(({ p }) => p);
    expect(callers.map((p) => relative(join(LAB_WEB, 'src'), p))).toEqual([join('ui', 'LiveView.tsx')]);
    const tsx = readFileSync(join(LAB_WEB, 'src/ui/LiveView.tsx'), 'utf-8');
    expect(tsx).toMatch(/probe\(LIVE_REMOTE\?\.ws, \(u, init\) => fetch\(u, init\)\)/);
    const status = readFileSync(join(LAB_WEB, 'src/live/status.ts'), 'utf-8');
    expect(status).toContain("credentials: 'omit'");
    expect(status).toMatch(/\/healthz`/);
  });

  it('every fetch is same-origin, relative to the base URL', () => {
    for (const { p, text } of src) {
      for (const m of text.matchAll(/fetch\(([^,)]+)/g)) {
        expect(/https?:/.test(m[1]), `${p}: ${m[0]}`).toBe(false);
      }
    }
  });
});

describe('the worker glue', () => {
  it('imports only coco_lab and the standard library', () => {
    const py = readFileSync(join(LAB_WEB, 'src/worker/recompute.py'), 'utf-8');
    const imports = [...py.matchAll(/^(?:from|import) ([\w.]+)/gm)].map((m) => m[1].split('.')[0]);
    expect(new Set(imports)).toEqual(new Set(['collections', 'json', 'os', 'shutil', 'sys', 'tempfile', 'time', 'coco_lab']));
    expect(py).toContain("TOOL = 'lab_web/pyodide'");
  });
});
