// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1: an experiment as a link. The spec travels as base64url JSON in `?exp=` when the
 * link stays short, otherwise deflated in the fragment (`#expz=`, never sent to a
 * server); both decode through links/bounds.mjs's boundedJson (M5's link limits, a
 * bomb-safe inflate). `d=` carries the creator's experiment digest (the sha256 over
 * every run's status, chain and counts, coco_lab.experiments.digest), so whoever
 * opens the link can see that re-running it reproduced every count exactly.
 */
import { deflateSync } from 'three/addons/libs/fflate.module.js';
import { boundedJson } from '../links/bounds.mjs';
import type { ExperimentSpec } from './spec';

/** Longest `?exp=` link before the compressed fragment is used. */
export const SHORT_LINK = 1800;

const b64 = (bytes: Uint8Array) => {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

/** The link for a spec (and, once it has run, its digest). `base` is the site root URL. */
export function experimentLink(spec: ExperimentSpec, base: string, digest?: string): string {
  const json = JSON.stringify(spec);
  const d = digest ? `&d=${digest}` : '';
  const plain = `${base}?view=workbench&exp=${b64(new TextEncoder().encode(json))}${d}`;
  if (plain.length <= SHORT_LINK) return plain;
  return `${base}?view=workbench${d}#expz=${b64(deflateSync(new TextEncoder().encode(json), { level: 9 }))}`;
}

export interface OpenedLink { spec: ExperimentSpec; digest: string | null }

/** The experiment a URL carries, or null; throws (with the reason) for a malformed one. */
export function readExperimentLink(search: string, hash: string): OpenedLink | null {
  const q = new URLSearchParams(search);
  const h = new URLSearchParams(hash.replace(/^#/, ''));
  const digest = q.get('d');
  if (digest !== null && !/^[0-9a-f]{64}$/.test(digest)) throw new Error('Link digest must be 64 hexadecimal digits');
  let spec: unknown = null;
  if (q.has('exp')) spec = boundedJson(q.get('exp')!, false);
  else if (h.has('expz')) spec = boundedJson(h.get('expz')!, true);
  else return null;
  if (!spec || typeof spec !== 'object' || (spec as { schema?: unknown }).schema !== 'coco.experiment.v1') {
    throw new Error('Link does not carry a coco.experiment.v1 spec');
  }
  return { spec: spec as ExperimentSpec, digest };
}
