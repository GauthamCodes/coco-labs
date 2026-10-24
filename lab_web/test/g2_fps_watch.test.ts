// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G2.1 (Gautham, 2026-10-23): heavy saved settings are never overridden silently; if the
 * drawn frame rate stays under 55 fps for 10 s, Play offers "Switch to recommended settings"
 * (src/game/fps_watch.ts). Frames are fed at a chosen rate on a synthetic clock.
 */
import { describe, expect, it } from 'vitest';
import { FpsWatch, heavier, recommendedSettings, RECOMMEND_AFTER_S, RECOMMEND_FPS } from '../src/game/fps_watch';

/** Feed `seconds` of frames at `fps` from `t0` (ms); return when the watch fired (ms) or null. */
function feed(w: FpsWatch, fps: number, seconds: number, t0 = 0): { fired: number | null; end: number } {
  let fired: number | null = null, t = t0;
  const dt = 1000 / fps;
  for (let k = 0; k <= seconds * fps; k++) {
    t = t0 + k * dt;
    if (w.frame(t) && fired === null) fired = t;
  }
  return { fired, end: t };
}

describe('the slow-phone watch', () => {
  it('is the decision: under 55 fps, for 10 s', () => {
    expect(RECOMMEND_FPS).toBe(55);
    expect(RECOMMEND_AFTER_S).toBe(10);
  });

  it('fires once, at the end of the tenth slow second', () => {
    const w = new FpsWatch();
    const { fired } = feed(w, 40, 30);
    expect(fired).not.toBeNull();
    expect(fired!).toBeGreaterThanOrEqual(10_000);
    expect(fired!).toBeLessThan(11_100);
    expect(w.last).toBeLessThan(55);
    expect(feed(w, 40, 30, 40_000).fired).toBeNull();   // never again in this session
  });

  it('never fires at 60 fps, nor at 56', () => {
    expect(feed(new FpsWatch(), 60, 60).fired).toBeNull();
    expect(feed(new FpsWatch(), 56, 60).fired).toBeNull();
  });

  it('needs ten slow seconds in a row: one fast second starts the count again', () => {
    const w = new FpsWatch();
    let r = feed(w, 40, 8);
    r = feed(w, 60, 2, r.end + 1);
    expect(feed(w, 40, 8, r.end + 1).fired).toBeNull();
    expect(feed(w, 40, 4, r.end + 8_100).fired).not.toBeNull();
  });

  it('a pause or a hidden tab (reset) never counts as slow', () => {
    const w = new FpsWatch();
    const r = feed(w, 40, 9);
    w.reset();
    expect(feed(w, 40, 9, r.end + 60_000).fired).toBeNull();
  });
});

describe('what is recommended, and when', () => {
  it('is the shipped default: medium and the 60 fps cap on a phone', () => {
    expect(recommendedSettings(true)).toEqual({ quality: 'medium', phone120: false });
    expect(recommendedSettings(false)).toEqual({ quality: 'high', phone120: false });
  });

  it('is offered only when it is lighter than what is saved', () => {
    const rec = recommendedSettings(true);
    expect(heavier({ quality: 'high', phone120: true }, rec)).toBe(true);   // Gautham's saved settings (G1.13)
    expect(heavier({ quality: 'high', phone120: false }, rec)).toBe(true);
    expect(heavier({ quality: 'medium', phone120: true }, rec)).toBe(true);
    expect(heavier({ quality: 'medium', phone120: false }, rec)).toBe(false);
    expect(heavier({ quality: 'low', phone120: false }, rec)).toBe(false);   // never suggests heavier settings
  });
});
