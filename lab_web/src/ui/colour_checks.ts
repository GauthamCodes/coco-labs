// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Machado 2009 severity-100 matrices, verified against colorspacious/cvd.py.
 * Source: https://github.com/njsmith/colorspacious/blob/master/colorspacious/cvd.py
 * This is a simulation for design checks, not a human usability result.
 */
export const CVD = {
  protanopia: [[.152286, 1.052583, -.204868], [.114503, .786281, .099216], [-.003882, -.048116, 1.051998]],
  deuteranopia: [[.367322, .860646, -.227968], [.280085, .672501, .047413], [-.011820, .042940, .968881]],
} as const;
export type Cvd = keyof typeof CVD;
export const linear = (value: number) => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
export const rgb = (hex: string) => [1, 3, 5].map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255);
export function contrast(a: string, b: string): number {
  const luminance = (hex: string) => rgb(hex).map(linear).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
export function simulate(hex: string, kind: Cvd): string {
  const source = rgb(hex).map(linear);
  return '#' + CVD[kind].map((row) => {
    const v = Math.min(1, Math.max(0, row.reduce((sum, weight, index) => sum + weight * source[index], 0)));
    return Math.round(255 * (v <= .0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - .055)).toString(16).padStart(2, '0');
  }).join('');
}
/** Browser SVG matrix in linear RGB; screenshot harness checks the real scenes. */
export function svgMatrix(kind: Cvd): string {
  return [...CVD[kind].flatMap((row) => [...row, 0, 0]), 0, 0, 0, 1, 0].join(' ');
}
/** CIELAB (D65) separation of opaque role swatches; never substitutes for labels. */
export function lab(hex: string): number[] {
  const [r, g, b] = rgb(hex).map(linear);
  const f = (value: number) => value > 216 / 24389 ? Math.cbrt(value) : (24389 / 27 * value + 16) / 116;
  const x = f((.4124564 * r + .3575761 * g + .1804375 * b) / .95047);
  const y = f(.2126729 * r + .7151522 * g + .0721750 * b);
  const z = f((.0193339 * r + .1191920 * g + .9503041 * b) / 1.08883);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}
export const deltaE = (a: string, b: string) => Math.hypot(...lab(a).map((value, index) => value - lab(b)[index]));
