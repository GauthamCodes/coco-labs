// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * bundle bytes -> DecodedBundle, and the catalog gate.
 *
 * `loadBundleBytes` is `coco_lab.bundle.load_bundle` minus the filesystem:
 * the manifest bytes and the arrays FILE bytes (compressed or not, as the
 * manifest says) in, a structurally validated bundle out. `fetchBundle`
 * reads the two files over HTTP with the same bounds.
 */

import { BundleError, fail } from './errors';
import { boundedGunzip } from './gzip';
import { decode, MAX_ARRAY_BYTES, MAX_MANIFEST_BYTES, parseManifest, type DecodeOptions } from './decode';
import type { DecodedBundle, ValidatedBy } from './model';

export async function loadBundleBytes(manifest: Uint8Array, arraysFile: Uint8Array,
  opts: DecodeOptions = {}): Promise<DecodedBundle> {
  const parsed = parseManifest(manifest);
  const raw = parsed.compression === 'gzip'
    ? await boundedGunzip(arraysFile, parsed.total)
    : arraysFile.subarray(0, parsed.total + 1); // Python: f.read(total + 1)
  return decode(parsed, raw, opts);
}

/** The arrays file name the manifest's `encoding.compression` implies. */
export function arraysFileName(compression: 'none' | 'gzip'): string {
  return compression === 'gzip' ? 'arrays.bin.gz' : 'arrays.bin';
}

async function fetchCapped(url: string, cap: number): Promise<Uint8Array> {
  let res: Response;
  try {
    res = await fetch(url, { credentials: 'omit', cache: 'no-cache' });
  } catch (exc) {
    return fail('fetch', `cannot fetch ${url}: ${(exc as Error).message}`);
  }
  if (!res.ok) fail('fetch', `cannot fetch ${url}: HTTP ${res.status}`);
  const declared = Number(res.headers.get('Content-Length') ?? NaN);
  if (Number.isFinite(declared) && declared > cap && !res.headers.get('Content-Encoding')) {
    fail('bounds', `${url} is ${declared} bytes, over ${cap}`);
  }
  const reader = res.body!.getReader();
  const parts: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > cap) {
      await reader.cancel();
      // keep one byte over the cap so the caller's bound check fires
      parts.push(value.subarray(0, value.length - (total - cap - 1)));
      total = cap + 1;
      break;
    }
    parts.push(value);
  }
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) {
    out.set(p, off);
    off += p.length;
  }
  return out;
}

export interface BundleFiles {
  manifest: Uint8Array;
  arraysName: string;
  arraysFile: Uint8Array;
}

/** Fetch `<dirUrl>manifest.json` and its arrays file, bounded like Python. */
export async function fetchBundleFiles(dirUrl: string): Promise<BundleFiles> {
  const manifest = await fetchCapped(`${dirUrl}manifest.json`, MAX_MANIFEST_BYTES);
  const parsed = parseManifest(manifest);
  const arraysName = arraysFileName(parsed.compression);
  // raw: the declared total + 1 is enough to detect padding; gzip: the
  // compressed file is bounded by the array cap (its output by the total).
  const cap = parsed.compression === 'gzip' ? MAX_ARRAY_BYTES : parsed.total + 1;
  const arraysFile = await fetchCapped(`${dirUrl}${arraysName}`, cap);
  return { manifest, arraysName, arraysFile };
}

export async function fetchBundle(dirUrl: string): Promise<{ bundle: DecodedBundle; files: BundleFiles }> {
  const files = await fetchBundleFiles(dirUrl);
  return { bundle: await loadBundleBytes(files.manifest, files.arraysFile), files };
}

// -- the catalog gate ------------------------------------------------------------

export interface CatalogEntry {
  id: string;
  title: string;
  group: string;
  path: string;
  arrays_file: string;
  bytes: number;
  content_hash: string;
  map_hash: string;
  source_kind: string;
  algorithm: string;
  events: number;
  editable: boolean;
  validated: { by: string; replay: string };
  citation: string;
}

export interface Catalog {
  schema: 'coco_lab.catalog';
  version: string;
  coco_lab_version: string;
  built_from: { commit: string; dirty: boolean } | null;
  tool: string;
  wheel: { path: string; sha256: string; bytes: number } | null;
  bundles: CatalogEntry[];
  /** 1.1: coco_lab's verdicts for the settings panel (src/lab/settings.ts). */
  settings?: SettingsAnalysis;
  /** 1.1: the map ladder, lowest rung first. */
  ladder?: LadderRung[];
  /** 1.1: COCO's footprint, derived from coco_config. */
  footprint?: Footprint;
}

/** One move model's verdicts, computed by coco_lab at site build time. */
export interface ModelAnalysis {
  connectivity: 4 | 8;
  diagonal_cost: number | null;
  heuristic: string;
  admissible: boolean;
  consistent: boolean;
  reason: string;
  witness: number[] | null;
  /** Per algorithm: cost <= bound x optimal, or null (no guarantee). */
  bounds: Record<'bfs' | 'dijkstra' | 'astar' | 'greedy', number | null> & {
    weighted_astar: Array<number | null>; // one per SettingsAnalysis.weights
  };
}

export interface SettingsAnalysis {
  by: string;
  cite: string;
  algorithms: string[];
  heuristics: string[];
  tie_breaks: string[];
  weights: number[];
  models: ModelAnalysis[];
}

export interface LadderRung {
  rung: number;
  id: string;
  title: string;
  note: string;
}

export interface Footprint {
  length_m: number;
  width_m: number;
  source: string;
  derivation: string;
}

/**
 * The browser checks structure; `coco_lab` checks semantics. A bundle is
 * drawable only when `coco_lab` validated exactly these bytes: at build
 * time (its content hash is the catalog entry's) -- else `catalog_mismatch`.
 */
export function requireValidated(b: DecodedBundle, entry: CatalogEntry): ValidatedBy {
  if (b.contentHash !== entry.content_hash) {
    throw new BundleError('catalog_mismatch',
      `content_hash ${b.contentHash} is not the one coco_lab validated for ${entry.id} ` +
      `(${entry.content_hash})`);
  }
  return { by: 'catalog', detail: `${entry.validated.by}; ${entry.validated.replay}` };
}
