// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R4: the page's side of grading. Every answer -- a choice, a tick, slider values or a file -- is
 * graded by coco_lab.course.grade inside the Studio's locked-down sandbox worker (ADR 0012): the
 * same Python the native check runs, so browser and native verdicts are byte-identical (their
 * digests are compared in CI). A predict's choice is graded the same way, never in TypeScript.
 */
import { Sandbox, type Family } from '../studio/sandbox';
import type { Answer, Exercise, Grade } from './types';

let box: Sandbox | null = null;
const sandbox = () => (box ??= new Sandbox());

/** The watchdog family for an exercise (control runs beat every tick; others per call). */
const familyOf = (e: Exercise): Family => (e.family === 'control' ? 'control' : e.family === 'localisation' ? 'localisation' : 'planning');

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

/** Validate the worker's answer as data (it is untrusted text). */
export function parseGrade(text: string, exercise: string): Grade {
  const g = JSON.parse(text) as unknown;
  if (!isObj(g) || g.schema !== 'coco.lesson.grade.v1' || g.exercise !== exercise || typeof g.passed !== 'boolean'
    || !Array.isArray(g.results) || typeof g.digest !== 'string') throw new Error('the grader returned something that is not a grade');
  for (const r of g.results) {
    if (!isObj(r) || typeof r.passed !== 'boolean' || typeof r.message !== 'string') throw new Error('a malformed check result');
  }
  return g as unknown as Grade;
}

export async function grade(e: Exercise, answer: Answer): Promise<Grade> {
  const end = await sandbox().run({ op: 'grade', exercise: e.id, answer }, familyOf(e));
  if (!end.ok) {
    // the worker was stopped (time or memory limit, a crash): that is the answer's grade
    return { schema: 'coco.lesson.grade.v1', exercise: e.id, type: e.type, answer_sha256: '', passed: false,
      checks_passed: 0, checks: 1, digest: '', results: [{ check: 'sandbox', label: 'the sandbox', passed: false,
        which: 'public', scenario: null, measured: null, target: null, message: end.message }] };
  }
  return parseGrade(end.result, e.id);
}

/** Boot the interpreter ahead of the first check (it takes a few seconds). */
export function warmUp(): void { void sandbox().start().catch(() => {}); }
