// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R1.7: the Workbench and Learn routes; every older link keeps its home. */
import { describe, expect, it } from 'vitest';
import { needsRunIds, route } from '../src/landing';
import { MODES } from '../src/ui/ModeNav';
import { urlFieldError } from '../src/links/bounds.mjs';
import { MISSION_EXPERIMENTS } from '../src/learn/LearnPage';
import { META } from '../src/workbench/spec';

describe('R1 routes', () => {
  it('opens the Workbench and the Learn page', () => {
    expect(route('?view=workbench', 'arena')).toEqual({ app: 'workbench' });
    expect(route('?view=workbench&tab=benchmarks', 'v1')).toEqual({ app: 'workbench' });
    expect(route('?view=learn', 'arena')).toEqual({ app: 'learnhome' });
    expect(needsRunIds('?view=workbench&v=1')).toBe(false);
  });

  it('keeps every older link where it was', () => {
    expect(route('?view=learn&mission=find-a-path&beat=2', 'v1')).toEqual({ redirect: '?view=compare&beat=2&tour=find-a-path' });
    expect(route('?view=learn&tour=', 'arena')).toEqual({ redirect: '?view=compare&tour=' });
    expect(route('?view=research', 'arena')).toEqual({ app: 'casefiles' });
    expect(route('?view=research&casefile=x', 'arena')).toEqual({ app: 'arena' });
    expect(route('?view=compare', 'arena')).toEqual({ app: 'compare' });
  });

  it('the top bar is Play · Learn · Compare · Workbench (Gautham, 2026-10-31)', () => {
    expect(MODES.map((m) => m.label)).toEqual(['Play', 'Learn', 'Compare', 'Workbench']);
  });

  it('bounds an experiment link like every other encoded field', () => {
    expect(urlFieldError(new URLSearchParams(`exp=${'a'.repeat(10)}`))).toBeNull();
    expect(urlFieldError(new URLSearchParams(`exp=${'a'.repeat(200000)}`))).toMatch(/exp exceeds/);
  });

  it('every mission links a pre-made experiment on a shipped world and suite', () => {
    const missions = ['find-a-path', 'world-changes', 'where-it-is', 'build-a-map', 'avoid-things', 'where-to-look', 'why-did-it-fail'];
    expect(Object.keys(MISSION_EXPERIMENTS).sort()).toEqual([...missions].sort());
    for (const { spec } of Object.values(MISSION_EXPERIMENTS)) {
      expect(META.worlds.map((w) => w.id)).toContain(spec.world);
      if (spec.scenarios.kind === 'suite') expect(META.suites.map((s) => s.id)).toContain(spec.scenarios.id);
      for (const a of spec.algorithms) expect(META.algorithms[spec.family]).toContain(a.name);
    }
  });
});
