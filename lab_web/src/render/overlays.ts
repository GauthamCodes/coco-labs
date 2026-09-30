// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Recorded-run overlays: ground truth, AMCL belief and the published plan,
 * as polylines in canvas CELL units. Pure: the source arrays are read, never
 * modified, decimated or smoothed (gt is at most ~3,900 samples, so no
 * display decimation is needed; if one is ever added it lives here, as a
 * view over the untouched arrays).
 *
 * A group is placed only when (1) the map has geo and (2) the group's frame
 * is the map's frame. Otherwise it is REFUSED with a reason -- never
 * guessed. A missing group is named ("cmd: not captured"), never drawn as
 * an empty line. `cmd` is in the base_footprint frame (velocities), so it
 * is never a map overlay; 1D reports its count, 1E plots it.
 */

import type { DecodedBundle, RecordingGroup } from '../bundle/model';
import { metricToCell } from '../trace/coords';

export const POSE_GROUPS = ['gt', 'amcl', 'plan'] as const;

export type Overlay =
  | { group: RecordingGroup; placed: true; points: Array<[number, number]> }
  | { group: RecordingGroup; placed: false; reason: string };

export function recordingOverlays(b: DecodedBundle): Overlay[] {
  const rec = b.recording;
  if (!rec) return [];
  const out: Overlay[] = [];
  for (const g of POSE_GROUPS) {
    if (rec.missing.includes(g)) {
      out.push({ group: g, placed: false, reason: `${g}: not captured` });
      continue;
    }
    const info = rec.groups[g]!;
    if (!b.map.geo) {
      out.push({ group: g, placed: false, reason: 'no geo — cannot place (the map has no resolution/origin)' });
      continue;
    }
    const mapFrame = b.map.geo.frame;
    if (info.frame !== mapFrame) {
      out.push({ group: g, placed: false, reason: `frame ${info.frame} is not the map's frame ${mapFrame}` });
      continue;
    }
    const s = rec.streams[g]!;
    const pts: Array<[number, number]> = [];
    for (let i = 0; i < s.x.length; i++) pts.push(metricToCell(b.map, s.x[i], s.y[i]));
    out.push({ group: g, placed: true, points: pts });
  }
  return out;
}

/** Non-pose groups, reported by count or as not captured. */
export function otherGroups(b: DecodedBundle): string[] {
  const rec = b.recording;
  if (!rec) return [];
  return rec.missing.includes('cmd')
    ? ['cmd: not captured']
    : [`cmd: ${rec.groups.cmd!.count} wheel commands (${rec.groups.cmd!.frame}; plotted in Phase 1E)`];
}
