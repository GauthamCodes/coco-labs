// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Why a bundle was refused. The codes mirror the classes of rejection in
 * `coco_lab/bundle.py` (the corpus in `test/invalid/index.json` pins each
 * case to one code), plus `catalog_mismatch`, which only the browser
 * raises: a structurally valid bundle whose content hash `coco_lab` never
 * validated.
 */
export type BundleErrorCode =
  | 'json' // not UTF-8 / not JSON / a NaN literal / a duplicate key
  | 'bounds' // a size, depth or count limit
  | 'schema'
  | 'version'
  | 'structure' // a required manifest member is missing or mistyped
  | 'table' // the array table
  | 'length' // array bytes truncated or padded
  | 'hash' // content_hash
  | 'map' // the map block cannot build a map
  | 'map_hash'
  | 'dtype'
  | 'nonfinite'
  | 'provenance'
  | 'recording'
  | 'run'
  | 'run_header' // the run block disagrees with the trace header or map
  | 'trace_invariant'
  | 'compression'
  | 'fetch'
  | 'catalog_mismatch';

export class BundleError extends Error {
  readonly code: BundleErrorCode;

  constructor(code: BundleErrorCode, message: string) {
    super(`${code}: ${message}`);
    this.name = 'BundleError';
    this.code = code;
  }
}

export function fail(code: BundleErrorCode, message: string): never {
  throw new BundleError(code, message);
}
