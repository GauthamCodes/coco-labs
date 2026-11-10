// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** R4: the Learn course's links, CSV and progress rules (the page side; grading is Python's). */
import { describe, expect, it } from 'vitest';
import { assignmentFragment, completionFragment, csvCell, readAssignment, readCompletion } from '../src/course/links';
import { importProgress, stars } from '../src/course/progress';
import { parseGrade } from '../src/course/grader';

describe('completion links', () => {
  it('round-trips answers, hints, solution flags and an optional name', async () => {
    const frag = await completionFragment({ title: 'Module 1', name: 'Ada', issued: '2026-11-10', entries: [
      { lesson: 'write-the-heuristic', exercise: 'm1-heuristic', answer: { code: 'def plan(c, s, g, ctx):\n    return None\n' }, hints: 2, solution: false },
      { lesson: 'astar-vs-dijkstra', exercise: 'm1-tune-weight', answer: { params: { heuristic_weight: 2 } }, hints: 0, solution: false },
    ] });
    const c = await readCompletion('#' + frag);
    expect(c.name).toBe('Ada');
    expect(c.entries).toHaveLength(2);
    expect(c.entries[0].answer.code).toContain('def plan');
    expect(c.entries[0].hints).toBe(2);
    expect(c.entries[1].answer.params).toEqual({ heuristic_weight: 2 });
  });
  it('refuses a damaged or foreign link and clamps declared hints', async () => {
    await expect(readCompletion('#done=!!!')).rejects.toThrow();
    await expect(readCompletion('#code=abc')).rejects.toThrow();
    const frag = await completionFragment({ title: 't', issued: 'x', entries: [{ lesson: 'l', exercise: 'e', answer: { choice: 1 }, hints: 9 as number, solution: true }] });
    expect((await readCompletion(frag)).entries[0].hints).toBe(3);
  });
  it('refuses an answer with unexpected fields', async () => {
    const frag = await completionFragment({ title: 't', issued: 'x', entries: [{ lesson: 'l', exercise: 'e', answer: { choice: 1, evil: 1 } as never, hints: 0, solution: false }] });
    await expect(readCompletion(frag)).rejects.toThrow(/damaged/);
  });
  it('strips markup from names', async () => {
    const frag = await completionFragment({ title: 't', name: '<img src=x>Bob', issued: 'x', entries: [] });
    expect((await readCompletion(frag)).name).toBe('img src=xBob');
  });
});

describe('assignment links', () => {
  it('carry the teacher\'s choices and no student data', async () => {
    const a = await readAssignment(await assignmentFragment({ title: 'Week 1', lessons: ['astar-vs-dijkstra'], deadline: 'Friday', askName: true }));
    expect(a).toEqual({ v: 1, kind: 'assignment', title: 'Week 1', lessons: ['astar-vs-dijkstra'], deadline: 'Friday', askName: true });
  });
});

describe('the class CSV', () => {
  it('quotes every cell and neutralises formula-looking text', () => {
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`);
    expect(csvCell('+1')).toBe(`"'+1"`);
    expect(csvCell('plain, text')).toBe('"plain, text"');
    expect(csvCell(null)).toBe('""');
  });
});

describe('stars and progress files', () => {
  const base = { passed: true, hints: 0, solution: false, attempts: 1 };
  it('are honest about help', () => {
    expect(stars({ ...base, passed: false })).toBe(0);
    expect(stars(base)).toBe(3);
    expect(stars({ ...base, hints: 2 })).toBe(2);
    expect(stars({ ...base, hints: 3 })).toBe(1);
    expect(stars({ ...base, solution: true })).toBe(1);
  });
  it('an imported file must be a progress file', () => {
    expect(() => importProgress('not json')).toThrow();
    expect(() => importProgress(JSON.stringify({ schema: 'other' }))).toThrow();
    const ok = importProgress(JSON.stringify({ schema: 'coco.lesson.progress.v1', lessons: { a: base } }));
    expect(ok.lessons.a.passed).toBe(true);
  });
});

describe('the grader\'s reply is data', () => {
  it('rejects anything that is not a grade for this exercise', () => {
    expect(() => parseGrade('{"schema":"x"}', 'e')).toThrow();
    expect(() => parseGrade(JSON.stringify({ schema: 'coco.lesson.grade.v1', exercise: 'other', passed: true, results: [], digest: 'd' }), 'e')).toThrow();
    const g = parseGrade(JSON.stringify({ schema: 'coco.lesson.grade.v1', exercise: 'e', passed: false, results: [{ passed: false, message: 'm' }], digest: 'd' }), 'e');
    expect(g.passed).toBe(false);
  });
});
