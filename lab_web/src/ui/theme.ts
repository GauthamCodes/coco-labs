// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { readPref, writePref, reducedMotion } from '../prefs';
import type { Theme } from './tokens';
export const isTheme = (value: unknown): value is Theme => value === 'light' || value === 'dark';
export function activeTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  const own = typeof document === 'undefined' ? null : document.documentElement.dataset.theme;
  if (isTheme(own)) return own;
  const query = new URLSearchParams(window.location.search).get('theme');
  if (isTheme(query)) return query;
  return readPref('theme', 'dark', isTheme);
}
export function applyTheme(theme = activeTheme(), remember = false) {
  document.documentElement.dataset.theme = theme;
  applyMotion();
  if (remember) writePref('theme', theme);
}

export function applyMotion() { document.documentElement.dataset.motion = reducedMotion() ? "reduced" : "normal"; }
