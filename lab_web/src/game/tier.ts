// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * G1: the starting quality tier. A saved choice wins; otherwise phones start on
 * medium (the provisional phone default, docs/v2/PHONE_PROFILE.md) and other
 * devices on high. Presentation only: no tier changes the model.
 */
import { readPref } from '../prefs';
import type { Tier } from './world/build3d';

const isTier = (v: unknown): v is Tier => v === 'low' || v === 'medium' || v === 'high';
export function pickTier(): Tier {
  const saved = readPref<Tier | 'auto'>('quality', 'auto', (v): v is Tier | 'auto' => v === 'auto' || isTier(v));
  if (isTier(saved)) return saved;
  const q = new URLSearchParams(window.location.search).get('tier');
  if (isTier(q)) return q;
  const coarse = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
  return coarse ? 'medium' : 'high';
}
