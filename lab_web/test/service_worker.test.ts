// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
// @ts-expect-error build tool runs as Node JavaScript
import { buildServiceWorker } from '../tools/build_service_worker.mjs';
it('static allowlist/content version change together, never include old archive or source maps',()=>{
 const root=mkdtempSync(join(tmpdir(),'coco-cache-test-'));mkdirSync(join(root,'assets'));mkdirSync(join(root,'v1'));
 writeFileSync(join(root,'index.html'),'<html><head></head></html>');writeFileSync(join(root,'assets','app-a.js'),'version one');writeFileSync(join(root,'assets','app-a.js.map'),'map');writeFileSync(join(root,'v1','index.html'),'frozen');
 const template=readFileSync(new URL('../src/offline/sw.template.js',import.meta.url),'utf8');const first=buildServiceWorker(root,template);const again=buildServiceWorker(root,template);expect(again.version).toBe(first.version);expect(first.assets['v1/index.html']).toBeUndefined();expect(first.assets['assets/app-a.js.map']).toBeUndefined();
 writeFileSync(join(root,'assets','app-a.js'),'version two');const second=buildServiceWorker(root,template);expect(second.version).not.toBe(first.version);expect(second.assets['assets/app-a.js']).not.toBe(first.assets['assets/app-a.js']);expect(readFileSync(join(root,'sw.js'),'utf8')).not.toContain('/*__COCO_MANIFEST__*/');
});
