// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { DEFAULT_LANDING } from '../site.config';
import { chooseApp } from '../src/landing';

// Every v1 URL form: the six labs, the exhibit, Lab 1's bundles and share links.
const V1_LINKS = [
  '?view=plan', '?view=live', '?view=localise', '?view=map', '?view=search', '?view=move', '?view=exhibit',
  '?bundle=astar_open', '?bundle=astar_open&v=1', '?v=1', '?view=plan&bundle=astar_open&v=1',
];
const ARENA_LINKS = ['?view=arena', '?view=arena&perf', '?view=arena&run=abc', '?view=arena&replay=lab1c_astar'];

describe('the landing switch (LANDING=arena|v1, M1 review fix)', () => {
  it('ships the Arena as the default landing page', () => {
    expect(DEFAULT_LANDING).toBe('arena');
    expect(__LANDING__).toBe(process.env.LANDING ?? 'arena');
  });

  for (const landing of ['arena', 'v1'] as const) {
    it(`landing=${landing}: only the bare URL follows the switch`, () => {
      expect(chooseApp('', landing)).toBe(landing);
      expect(chooseApp('?perf', landing)).toBe(landing);
      for (const q of V1_LINKS) expect(chooseApp(q, landing), q).toBe('v1');
      for (const q of ARENA_LINKS) expect(chooseApp(q, landing), q).toBe('arena');
      // a hand-trimmed Arena link (no view=arena) is still the Arena's
      expect(chooseApp('?run=abc', landing)).toBe('arena');
      expect(chooseApp('?replay=lab1c_astar', landing)).toBe('arena');
      // Learn (M2.8) opens only by name, whatever the switch
      for (const q of ['?view=learn', '?view=learn&mission=find-a-path&beat=2']) expect(chooseApp(q, landing), q).toBe('learn');
    });
  }

  it('matches the rule main.tsx used before the switch, for landing=arena', () => {
    const old = (s: string) => {
      const q = new URLSearchParams(s);
      return q.get('view') === 'arena' || (!q.has('view') && !q.has('bundle') && !q.has('v')) ? 'arena' : 'v1';
    };
    for (const q of ['', '?perf', ...V1_LINKS, ...ARENA_LINKS, '?run=abc', '?replay=x']) expect(chooseApp(q, 'arena'), q).toBe(old(q));
  });
});
