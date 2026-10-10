// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Lens drawers (M2.2): each lens turns the batches the model emitted, at the
 * shown tick, into primitives (render/lensLayers.ts). A drawer lays out and
 * aggregates; it never computes the algorithm. The Plan lens draws through
 * the M1 renderer (render/Renderer.ts); the others register here as their
 * checkpoints land (Localise M2.3, Map M2.4, Move M2.5, Decide M2.6).
 */

import type { World } from '../protocol';
import type { LensLayers } from '../render/lensLayers';
import type { ArenaSession } from '../session';
import type { LensId } from './registry';

export interface DrawContext {
  layers: LensLayers;
  session: ArenaSession;
  tick: number;
  world: World;
  /** Whether a layer is switched on. */
  on: (id: string) => boolean;
}

export type Drawer = (c: DrawContext) => void;

export const DRAWERS: Partial<Record<LensId, Drawer>> = {};

export function registerDrawer(id: LensId, d: Drawer) {
  DRAWERS[id] = d;
}

/** Explain level: a value label for the point (x, y) in the map frame, or null. */
export type Hover = (c: DrawContext, x: number, y: number) => string | null;

export const HOVERS: Partial<Record<LensId, Hover>> = {};

export function registerHover(id: LensId, h: Hover) {
  HOVERS[id] = h;
}

/** Draw every lens that has a drawer (a hidden layer is drawn hidden, so toggling is instant). */
export function drawLenses(c: DrawContext) {
  for (const d of Object.values(DRAWERS)) d?.(c);
}
