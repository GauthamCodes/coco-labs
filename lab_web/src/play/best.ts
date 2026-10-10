// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Personal bests (M3.5), kept in this browser only. Every storage access is
 * wrapped: in a private window, with storage blocked, or in a preview the
 * page plays exactly the same and simply remembers nothing.
 */

export interface PlayResult {
  challenge: string; level: string; level_hash: string; valid: boolean; why: string | null;
  score: { name: string; value: number | null }; stars: number;
  metrics: { name: string; value: unknown; unit: string; meaning: string }[];
  thresholds: string[]; hash: string;
}

export interface Best { stars: number; score: number; hash: string; level_hash: string }

/** Whether a higher score is better, per challenge's primary score. */
const HIGHER_IS_BETTER: Record<string, boolean> = {
  'beat-the-planner': false, 'next-node': true, 'search-the-bays': false,
  'map-the-arena': true, 'case-file-detective': false,
};

const key = (challenge: string, level: string) => `coco.play.best.v1.${challenge}.${level}`;

export function readBest(challenge: string, level: string, levelHash: string): Best | null {
  try {
    const raw = window.localStorage.getItem(key(challenge, level));
    if (!raw) return null;
    const b = JSON.parse(raw) as Best;
    // a best set on another version of the level is not a best on this one
    return b.level_hash === levelHash ? b : null;
  } catch {
    return null;
  }
}

/** A best to SHOW beside a level's name (whatever version of the level it was set on). */
export function readShownBest(challenge: string, level: string): Best | null {
  try {
    const raw = window.localStorage.getItem(key(challenge, level));
    return raw ? (JSON.parse(raw) as Best) : null;
  } catch {
    return null;
  }
}

/** Whether `r` beats `b`: more stars, then the better score. */
export function beats(r: PlayResult, b: Best | null): boolean {
  if (!r.valid || r.score.value === null) return false;
  if (!b) return true;
  if (r.stars !== b.stars) return r.stars > b.stars;
  return HIGHER_IS_BETTER[r.challenge] ? r.score.value > b.score : r.score.value < b.score;
}

/** Keep `r` if it is a new best; return the best now held (or null if storage is unavailable). */
export function keepBest(r: PlayResult): Best | null {
  const old = readBest(r.challenge, r.level, r.level_hash);
  if (!beats(r, old)) return old;
  const b: Best = { stars: r.stars, score: r.score.value as number, hash: r.hash, level_hash: r.level_hash };
  try {
    window.localStorage.setItem(key(r.challenge, r.level), JSON.stringify(b));
    return b;
  } catch {
    return null;
  }
}
