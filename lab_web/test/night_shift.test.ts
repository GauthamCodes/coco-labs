// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { TOKENS, TOKEN_CSS } from '../src/ui/tokens';
import { contrast, simulate, svgMatrix, deltaE } from '../src/ui/colour_checks';
describe('Night Shift legibility', () => {
  for (const theme of ['dark', 'light'] as const) {
    const c = TOKENS.colours[theme];
    it(`${theme}: text, muted text and interactive labels meet AA`, () => {
      for (const background of [c.bg, c.panel, c.panel2]) {
        for (const foreground of [c.fg, c.muted, c.accent, c.recorded, c.browser, c.glass]) {
          expect(contrast(foreground, background), `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
        }
      }
      expect(contrast(c.errorFg, c.errorBg)).toBeGreaterThanOrEqual(4.5);
    });
    it(`${theme}: computation identity is retained under both simulations`, () => {
      const p = TOKENS.computation[theme];
      for (const role of ['frontier', 'closed', 'path', 'truth', 'chosen'] as const) expect(contrast(p[role], p.free), role).toBeGreaterThanOrEqual(3);
      const roles = ['frontier', 'closed', 'path', 'rejected', 'particles', 'truth'] as const;
      for (const kind of ['deuteranopia', 'protanopia'] as const) {
        const swatches = roles.map((role) => simulate(p[role], kind));
        for (let a = 0; a < swatches.length; a++) for (let b = a + 1; b < swatches.length; b++) {
          // Declared design check, not a clinical/user-test threshold.
          expect(deltaE(swatches[a], swatches[b]), `${roles[a]} / ${roles[b]} under ${kind}`).toBeGreaterThanOrEqual(10);
        }
        expect(svgMatrix(kind).split(' ')).toHaveLength(20);
      }
    });
  }
  it('the initial paint and explicit themes use the same token source', () => {
    expect(TOKEN_CSS).toContain(':root:not([data-theme="light"])');
    expect(TOKEN_CSS).toContain('--compute-path:' + TOKENS.computation.dark.path);
    expect(TOKEN_CSS).toContain('prefers-reduced-motion:reduce');
    expect(TOKENS.type.label).toBeGreaterThanOrEqual(14);
  });
});
