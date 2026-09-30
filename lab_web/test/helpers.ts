// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { loadBundleBytes } from '../src/bundle/load';
import type { DecodeOptions } from '../src/bundle/decode';

export const LAB_WEB = new URL('..', import.meta.url).pathname;
export const REPO = join(LAB_WEB, '..');

export interface Expected {
  bundles: Array<Record<string, any>>;
}
export const expected: Expected = JSON.parse(
  readFileSync(join(LAB_WEB, 'test/golden/expected.json'), 'utf-8'),
);

export function readBundleDir(dir: string): { manifest: Uint8Array; arrays: Uint8Array; name: string } {
  const manifest = new Uint8Array(readFileSync(join(dir, 'manifest.json')));
  for (const name of ['arrays.bin', 'arrays.bin.gz']) {
    const p = join(dir, name);
    if (existsSync(p)) return { manifest, arrays: new Uint8Array(readFileSync(p)), name };
  }
  throw new Error(`no arrays file in ${dir}`);
}

export async function loadDir(dir: string, opts: DecodeOptions = {}) {
  const { manifest, arrays } = readBundleDir(dir);
  return loadBundleBytes(manifest, arrays, opts);
}
