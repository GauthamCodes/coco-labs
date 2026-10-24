// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * G2.1 (Gautham, 2026-10-23): heavy saved settings on phones are never overridden silently.
 * If the drawn frame rate stays under RECOMMEND_FPS for RECOMMEND_AFTER_S seconds, Play offers
 * a one-tap "Switch to recommended settings"; nothing changes unless the player taps it.
 *
 * Measured why (G1.13, docs/v2/g1/G1_REVIEW.md): the real Nothing Phone (1) with quality high
 * and the 120 fps cap saved ran hot. Presentation only: the model's clock never depends on it.
 */

import type { Tier } from './world/build3d';

export const RECOMMEND_FPS = 55;
export const RECOMMEND_AFTER_S = 10;

/**
 * Counts drawn frames in 1 s windows. `frame(now)` returns true once: at the end of the
 * RECOMMEND_AFTER_S-th consecutive window under RECOMMEND_FPS. `reset()` (paused, hidden)
 * starts the count again, so a pause or a hidden tab never counts as slow.
 */
export class FpsWatch {
  private start = -1;
  private frames = 0;
  private slow = 0;
  fired = false;
  /** the last full window's frame rate (fps) */
  last = 0;

  frame(now: number): boolean {
    if (this.fired) return false;
    if (this.start < 0) { this.start = now; this.frames = 0; return false; }
    this.frames += 1;
    if (now - this.start < 1000) return false;
    this.last = (this.frames * 1000) / (now - this.start);
    this.slow = this.last < RECOMMEND_FPS ? this.slow + 1 : 0;
    this.start = now;
    this.frames = 0;
    if (this.slow >= RECOMMEND_AFTER_S) { this.fired = true; return true; }
    return false;
  }

  reset() { this.start = -1; this.frames = 0; this.slow = 0; }
}

export interface PlaySettings { quality: Tier; phone120: boolean }

/** The recommended settings: the shipped defaults (tier.ts: medium on a touch screen, else high; the 60 fps cap). */
export function recommendedSettings(coarsePointer: boolean): PlaySettings {
  return { quality: coarsePointer ? 'medium' : 'high', phone120: false };
}

const WEIGHT: Record<Tier, number> = { low: 0, medium: 1, high: 2 };

/**
 * Whether the recommended settings would be LIGHTER than the current ones (a higher tier, or
 * the 120 fps cap): only then is there something to offer a slow phone. Already on (or below)
 * them, the toast never appears -- it never suggests heavier settings.
 */
export function heavier(now: PlaySettings, rec: PlaySettings): boolean {
  return WEIGHT[now.quality] > WEIGHT[rec.quality] || (now.phone120 && !rec.phone120);
}
