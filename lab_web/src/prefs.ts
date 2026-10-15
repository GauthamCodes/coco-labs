// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Preferences (M4.5): the ONE module that touches browser storage.
 *
 * It holds what a person chose, in this browser only: Play's personal bests
 * (M3.5; their keys are unchanged, so a best set before M4 is still there),
 * key bindings, the camera mode, the 3D quality tier, the sound toggle,
 * reduced motion, the wheel-speed bars and tank mode. Local storage only -- no cookie, no session storage, no
 * indexed database -- and every access is inside try: in a private window, with
 * storage blocked or in a preview the page behaves exactly the same and
 * simply remembers nothing (test/site.test.ts and tools/check_dist.mjs
 * guard all of this).
 */

/** Every key this site writes starts with one of these. */
export const PREF_PREFIXES = ['coco.play.best.v1.', 'coco.prefs.v1.'] as const;

/** The named preferences (one key each). */
export type PrefName = 'keys' | 'camera' | 'quality' | 'sound' | 'motion' | 'bars' | 'tank' | 'theme';
const KEY: Record<PrefName, string> = {
  theme: 'coco.prefs.v1.theme',
  keys: 'coco.prefs.v1.keys', camera: 'coco.prefs.v1.camera', quality: 'coco.prefs.v1.quality',
  sound: 'coco.prefs.v1.sound', motion: 'coco.prefs.v1.motion', bars: 'coco.prefs.v1.bars', tank: 'coco.prefs.v1.tank',
};

export const isBool = (v: unknown): v is boolean => typeof v === 'boolean';

function allowed(key: string): boolean {
  return PREF_PREFIXES.some((p) => key.startsWith(p));
}

/** Read a raw value; null when absent or when storage is unavailable. */
export function readRaw(key: string): string | null {
  if (!allowed(key)) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Write a raw value; false when storage is unavailable (the page goes on without it). */
export function writeRaw(key: string, value: string): boolean {
  if (!allowed(key)) return false;
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

/** Forget a value (a setting back to its default). */
export function removeRaw(key: string): void {
  if (!allowed(key)) return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* nothing remembered, nothing to forget */
  }
}

/** A named preference, parsed as JSON; `fallback` when absent, unreadable, or rejected by `valid`. */
export function readPref<T>(name: PrefName, fallback: T, valid: (v: unknown) => v is T): T {
  const raw = readRaw(KEY[name]);
  if (raw === null) return fallback;
  try {
    const v = JSON.parse(raw) as unknown;
    return valid(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

export function writePref(name: PrefName, value: unknown): boolean {
  return writeRaw(KEY[name], JSON.stringify(value));
}

export function resetPref(name: PrefName): void {
  removeRaw(KEY[name]);
}

/** Whether the person asked for less motion: the setting, else the system's preference. */
export function reducedMotion(): boolean {
  const own = readPref<boolean | null>('motion', null, (v): v is boolean | null => v === null || typeof v === 'boolean');
  if (own !== null) return own;
  try {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  } catch {
    return false;
  }
}
