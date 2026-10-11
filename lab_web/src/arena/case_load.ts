// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Load a Case File so its first frame draws before its scans arrive (M3 review,
 * decision D6; ADR 0005, amendment D6). A Case File is one file with its scans
 * written after everything else (lab_web/tools/layout_casefiles.mjs); it is read
 * as it arrives, so the recording -- without scans -- resolves as soon as the
 * last message before the scans is here, and `scans` resolves when the file has
 * arrived.
 */

import { streamCase, type ReadMessage } from '../schemas/mcap';
import type { WorldGrid } from '../schemas/gen/coco/world/v1/world_pb';
import { isCaseFile, parseCase } from './replay_case';
import type { ConvertedRun } from './replay';

export async function loadCase(base: string, id: string, grid: Promise<WorldGrid>):
  Promise<{ rec: ConvertedRun; scans: Promise<ReadMessage[]> }> {
  const missing = `no Case File "${id}"`;
  const res = await fetch(`${base}generated/casefiles/${id}.mcap`, { credentials: 'omit' });
  if (!res.ok || !res.body) throw new Error(missing);
  return new Promise((resolve, reject) => {
    const scans = streamCase(res.body!, (run) => {
      if (!isCaseFile(run.manifest)) { reject(new Error(missing)); return; }
      grid.then((g) => resolve({ rec: parseCase(run.manifest, run.messages, g), scans })).catch(reject);
    });
    scans.catch(reject);
  });
}
