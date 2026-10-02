// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

/**
 * Stick and keys to a velocity request. Pure; the server clamps again.
 *
 * Same mapping as coco_web's own page (app.js), so a person moving between
 * the two drives the same robot: stick up is forward, stick right turns
 * right (negative angular), keys ask for 60 % of the limit.
 */

export interface Velocity { linear: number; angular: number }

const clamp = (v: number, lim: number) => Math.max(-lim, Math.min(lim, v));

/**
 * Joystick displacement (dx right, dy up, both in [-1, 1] of the pad's
 * radius) to a request within `limits`. Outside the pad saturates at 1.
 */
export function stickVelocity(dx: number, dy: number, limits: { linear: number; angular: number }): Velocity {
  if (!Number.isFinite(dx) || !Number.isFinite(dy)) return { linear: 0, angular: 0 };
  const r = Math.hypot(dx, dy);
  const s = r > 1 ? 1 / r : 1;
  const lin = clamp(dy * s * limits.linear, limits.linear);
  const ang = clamp(-dx * s * limits.angular, limits.angular);
  return { linear: lin === 0 ? 0 : lin, angular: ang === 0 ? 0 : ang };
}

export const KEYS: Record<string, 'w' | 'a' | 's' | 'd'> = {
  w: 'w', a: 'a', s: 's', d: 'd', W: 'w', A: 'a', S: 's', D: 'd',
  ArrowUp: 'w', ArrowLeft: 'a', ArrowDown: 's', ArrowRight: 'd',
};

/** Held keys to a request; opposite keys cancel. */
export function keysVelocity(held: ReadonlySet<string>, limits: { linear: number; angular: number }): Velocity {
  let lin = 0;
  let ang = 0;
  if (held.has('w')) lin += limits.linear * 0.6;
  if (held.has('s')) lin -= limits.linear * 0.6;
  if (held.has('a')) ang += limits.angular * 0.6;
  if (held.has('d')) ang -= limits.angular * 0.6;
  return { linear: lin, angular: ang };
}

/** True when a request asks for no motion at all. */
export const isZero = (v: Velocity) => v.linear === 0 && v.angular === 0;
