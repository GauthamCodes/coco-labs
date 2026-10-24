// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.6: "Race Nav2 (real ROS 2 recording)". A ghost of COCO driven by a recorded run of the same
 * round: the full ROS 2 stack (Nav2) in Gazebo Harmonic, headless (STACK; tools/g2/make_ghost.py).
 * It is replayed, never simulated here: its pose at round time t is the recording's truth at t.
 * What it is not is in the file and shown with it: no grasp (Nav2 drove the legs only), Gazebo's
 * actors parked, never hardware.
 */

const BASE = import.meta.env.BASE_URL;

export interface GhostIndexEntry { file: string; rules: number; mode: string; seed: number; bytes: number; sha256: string; driving_s: number; all_succeeded: boolean }
export interface GhostIndex { schema: string; version: number; evidence: 'STACK'; ghosts: GhostIndexEntry[] }
export interface StackGhost {
  evidence: 'STACK'; what: string; not: string[];
  round: { rules: number; mode: string; seed: number; region: string; orders: [string, string][]; ghost_m: number[]; reference_time_s: number; start: [number, number, number] };
  legs: { id: string; status: string; t0: number; sim_s: number; driven_m: number }[];
  all_succeeded: boolean; driving_s: number; driven_m: number;
  track: [number, number, number, number][];
  source: Record<string, unknown>;
}

export async function loadGhostIndex(): Promise<GhostIndex | null> {
  try {
    const r = await fetch(`${BASE}stack/ghosts/index.json`, { credentials: 'omit' });
    return r.ok ? (await r.json() as GhostIndex) : null;
  } catch { return null; }
}

export function ghostFor(index: GhostIndex | null, rules: number, mode: string, seed: number): GhostIndexEntry | null {
  return index?.ghosts.find((g) => g.rules === rules && g.mode === mode && g.seed === seed && g.all_succeeded) ?? null;
}

export async function loadGhost(entry: GhostIndexEntry): Promise<StackGhost> {
  const r = await fetch(`${BASE}stack/ghosts/${entry.file}`, { credentials: 'omit' });
  if (!r.ok) throw new Error(`ghost ${entry.file}: ${r.status}`);
  return await r.json() as StackGhost;
}

/** The recording's pose at round time t (s): linear between its 10 Hz samples, held at both ends. */
export function ghostPoseAt(track: StackGhost['track'], t: number): [number, number, number] {
  if (!track.length) return [0, 0, 0];
  if (t <= track[0][0]) return [track[0][1], track[0][2], track[0][3]];
  const last = track[track.length - 1];
  if (t >= last[0]) return [last[1], last[2], last[3]];
  let lo = 0, hi = track.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (track[m][0] <= t) lo = m; else hi = m; }
  const a = track[lo], b = track[hi], f = (t - a[0]) / (b[0] - a[0] || 1);
  const dth = Math.atan2(Math.sin(b[3] - a[3]), Math.cos(b[3] - a[3]));
  return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + dth * f];
}
