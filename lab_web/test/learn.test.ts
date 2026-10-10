// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';

import { evidenceHref, githubSlug, LABEL_MEANING } from '../src/learn/LearnApp';
import { arenaHref, cfgFromParams, missionBackLink } from '../src/learn/links';

describe('Learn links (M2.8)', () => {
  it('a beat opens the Arena with its lens, level, settings and the way back', () => {
    const href = arenaHref('where-it-is', 3, { lens: 'localise', level: 'explain', cfg: ['localise.filter=both', 'arena.range_sigma=0.02'] });
    const q = new URLSearchParams(href.slice(1));
    expect(q.get('view')).toBe('arena');
    expect(q.get('lens')).toBe('localise');
    expect(q.get('level')).toBe('explain');
    expect(cfgFromParams(q)).toEqual(['localise.filter=both', 'arena.range_sigma=0.02']);
    expect(missionBackLink(q)).toBe('?view=learn&mission=where-it-is&beat=3');
  });

  it('a recording beat names the replay', () => {
    const q = new URLSearchParams(arenaHref('find-a-path', 5, { replay: 'lab1c_astar', level: 'explain' }).slice(1));
    expect(q.get('replay')).toBe('lab1c_astar');
  });

  it('the Arena takes only lines with a config form, at most twelve', () => {
    const q = new URLSearchParams();
    for (const c of ['map.algorithm=pose_graph', 'goal=1', '<script>=x', 'a.b=c d', 'localise.mcl.injection=augmented']) q.append('cfg', c);
    expect(cfgFromParams(q)).toEqual(['map.algorithm=pose_graph', 'localise.mcl.injection=augmented']);
    const many = new URLSearchParams();
    for (let i = 0; i < 20; i++) many.append('cfg', 'move.controller=dwa');
    expect(cfgFromParams(many)).toHaveLength(12);
  });

  it('the way back is only to a mission-shaped id and a beat 0..6', () => {
    expect(missionBackLink(new URLSearchParams('mission=find-a-path&beat=6'))).toBe('?view=learn&mission=find-a-path&beat=6');
    expect(missionBackLink(new URLSearchParams('mission=find-a-path&beat=7'))).toBeNull();
    expect(missionBackLink(new URLSearchParams('mission=../x&beat=1'))).toBeNull();
    expect(missionBackLink(new URLSearchParams('beat=1'))).toBeNull();
  });

  it('evidence links go to the committed file, a heading to its GitHub anchor', () => {
    expect(evidenceHref('coco_lab/test/test_replan.py::test_x')).toBe('https://github.com/GauthamCodes/coco-labs/blob/main/coco_lab/test/test_replan.py');
    expect(evidenceHref('docs/RESULTS.md > COCO Lab Phase 6 — Move (Lab 5) (measured 2026-10-07)'))
      .toBe('https://github.com/GauthamCodes/coco-labs/blob/main/docs/RESULTS.md#coco-lab-phase-6--move-lab-5-measured-2026-10-07');
    expect(githubSlug('A\\* — SmacPlanner2D, and the evidence for it')).toBe('a--smacplanner2d-and-the-evidence-for-it');
  });

  it('every label a mission may use has a meaning on the page, and none is a real-robot label', () => {
    expect(Object.keys(LABEL_MEANING).sort()).toEqual(
      ['ASSUMPTION', 'INFERENCE', 'MEASURED', 'SIMPLIFIED MODEL', 'SIMULATION RESULT', 'TESTED', 'UNRESOLVED']);
  });
});
