// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Quality tiers for the 3D view (M4.4; README §5.3): high, medium and low,
 * chosen from MEASURED frame time, with hysteresis and a manual override,
 * and the verdict to fall back to the top-down view when even the low tier
 * cannot hold about 24 fps.
 *
 * Pure: it is fed frame intervals (ms, from requestAnimationFrame) and says
 * which tier to use; the renderer applies it. Presentation only (README §3
 * invariant 11): nothing here touches the model.
 *
 * How it decides, over WINDOW_MS windows of frame intervals:
 * - it ignores the first SETTLE_MS after a start, a tier change or a return
 *   from a hidden tab, and any interval longer than STALL_MS (a hidden tab or
 *   a one-off stall is not the device's frame rate);
 * - a window whose 90th-percentile interval is above DOWN_MS steps DOWN one
 *   tier, at once;
 * - UP_WINDOWS consecutive windows whose 90th percentile is below UP_MS step
 *   UP one tier, and never back to a tier this session already stepped down
 *   from twice (the hysteresis that stops it oscillating);
 * - on the low tier, FALLBACK_WINDOWS consecutive windows whose median
 *   interval is above FALLBACK_MS (under about 24 fps) give the verdict
 *   'fallback': the page goes top-down and says why;
 * - an override (high, medium or low) holds that tier and never steps; the
 *   fallback verdict still stands on a device that cannot draw the low tier.
 */

export type Tier = 'high' | 'medium' | 'low';
export type TierChoice = Tier | 'auto';
export const TIERS: Tier[] = ['high', 'medium', 'low'];
export const TIER_CHOICES: TierChoice[] = ['auto', 'high', 'medium', 'low'];

/** What a tier changes: drawing-buffer pixel ratio cap, the sun's shadow map (0 = none), the environment map. */
export interface TierSettings { pixelRatioCap: number; shadowMapSize: number; envMap: boolean }
export const TIER_SETTINGS: Record<Tier, TierSettings> = {
  high: { pixelRatioCap: 2, shadowMapSize: 2048, envMap: true },
  medium: { pixelRatioCap: 1.5, shadowMapSize: 1024, envMap: true },
  low: { pixelRatioCap: 1, shadowMapSize: 0, envMap: false },
};

export const WINDOW_MS = 2000;
export const SETTLE_MS = 3000;
export const STALL_MS = 250;
/** p90 above this (about 45 fps) steps down */
export const DOWN_MS = 1000 / 45;
/** p90 below this (about 58 fps) counts toward stepping up */
export const UP_MS = 1000 / 58;
export const UP_WINDOWS = 4;
/** median above this (24 fps) on the low tier counts toward the fallback */
export const FALLBACK_MS = 1000 / 24;
export const FALLBACK_WINDOWS = 2;

export type QualityEvent =
  | { kind: 'tier'; tier: Tier; reason: string }
  | { kind: 'fallback'; reason: string };

const pct = (v: number[], q: number) => {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.round(q * (s.length - 1)))];
};

export class QualityController {
  tier: Tier;
  choice: TierChoice;
  fellBack = false;
  private settleUntil: number;
  private windowStart: number;
  private intervals: number[] = [];
  private good = 0;
  private slow = 0;
  private visibleStalls = 0;
  /** how many times this session stepped down FROM each tier */
  private downsFrom: Record<Tier, number> = { high: 0, medium: 0, low: 0 };

  constructor(now: number, choice: TierChoice = 'auto', start: Tier = 'high') {
    this.choice = choice;
    this.tier = choice === 'auto' ? start : choice;
    this.settleUntil = now + SETTLE_MS;
    this.windowStart = this.settleUntil;
  }

  /** A person's choice in settings: a tier holds it; 'auto' measures again from the current tier. */
  setChoice(choice: TierChoice, now: number): QualityEvent | null {
    this.choice = choice;
    this.restart(now);
    if (choice !== 'auto' && choice !== this.tier) {
      this.tier = choice;
      return { kind: 'tier', tier: choice, reason: 'chosen in settings' };
    }
    return null;
  }

  /** After the tab was hidden, or the 3D view was off: the next frames are not the device's rate. */
  restart(now: number) {
    this.settleUntil = now + SETTLE_MS;
    this.windowStart = this.settleUntil;
    this.intervals = [];
    this.good = 0;
    this.slow = 0; this.visibleStalls = 0;
  }

  /** One frame: `interval` ms since the previous one, at time `now` (ms). */
  frame(now: number, interval: number, continuouslyVisible = false): QualityEvent | null {
    if (this.fellBack || now < this.settleUntil || interval <= 0) return null;
    if (interval > STALL_MS) {
      // Known-visible sustained sub-4-fps rendering is a real slow tier,
      // not an endless sequence of hidden-tab stalls. Ignore one isolated gap.
      if (!continuouslyVisible || ++this.visibleStalls < 2) return null;
    } else this.visibleStalls = 0;
    this.intervals.push(interval);
    if (now - this.windowStart < WINDOW_MS) return null;
    const p90 = pct(this.intervals, 0.9);
    const p50 = pct(this.intervals, 0.5);
    this.intervals = [];
    this.windowStart = now;
    if (this.tier === 'low' && p50 > FALLBACK_MS) {
      this.slow += 1;
      if (this.slow >= FALLBACK_WINDOWS) {
        this.fellBack = true;
        return { kind: 'fallback', reason: `the low tier drew at ${(1000 / p50).toFixed(0)} fps, under 24` };
      }
    } else this.slow = 0;
    if (this.choice !== 'auto') return null;
    if (p90 > DOWN_MS && this.tier !== 'low') {
      this.downsFrom[this.tier] += 1;
      return this.change(TIERS[TIERS.indexOf(this.tier) + 1], now, `90th-percentile frame ${p90.toFixed(1)} ms`);
    }
    if (p90 < UP_MS && this.tier !== 'high') {
      this.good += 1;
      const up = TIERS[TIERS.indexOf(this.tier) - 1];
      if (this.good >= UP_WINDOWS && this.downsFrom[up] < 2) {
        return this.change(up, now, `90th-percentile frame ${p90.toFixed(1)} ms for ${UP_WINDOWS} windows`);
      }
    } else this.good = 0;
    return null;
  }

  private change(tier: Tier, now: number, reason: string): QualityEvent {
    this.tier = tier;
    this.restart(now);
    return { kind: 'tier', tier, reason };
  }
}
